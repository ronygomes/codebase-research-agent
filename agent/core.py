import collections
import json
import time
from pathlib import Path

from celery.exceptions import SoftTimeLimitExceeded
from django.utils import timezone

from agent.config import (
    MAX_AGENT_ITERATIONS,
    MAX_CONSECUTIVE_DUPLICATE_CALLS,
    MAX_SESSION_WALL_CLOCK_SECONDS,
    MAX_TOKENS_PER_SESSION,
    MAX_TOOL_RESULT_CHARS,
)
from agent.prompts import (
    FALLBACK_USER_MESSAGE,
    SYSTEM_PROMPT,
    build_first_user_message,
)
from llm.providers.base import LLMProvider
from llm.types import (
    ContentBlock,
    LLMResponse,
    Message,
    TextBlock,
    TokenUsage,
    ToolResultBlock,
    ToolUseBlock,
)
from research.models import ResearchSession, ToolCall
from tools.base import ToolContext
from tools.registry import ToolRegistry


class GuardrailHit(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class Agent:
    def __init__(
        self,
        session: ResearchSession,
        llm_provider: LLMProvider,
        tool_registry: ToolRegistry,
        repo_path: Path,
    ) -> None:
        self.session = session
        self.llm = llm_provider
        self.tool_registry = tool_registry
        self.tool_context = ToolContext(
            session_id=session.id,
            repository_id=session.repository_id,
            repo_path=repo_path,
        )
        self._messages: list[Message] = []
        self._tool_sequence = 0
        self._recent_calls: collections.deque[tuple[str, str]] = collections.deque(
            maxlen=MAX_CONSECUTIVE_DUPLICATE_CALLS
        )
        self._start_monotonic = 0.0

    def run(self) -> None:
        self._mark_running()
        try:
            self._loop()
        except GuardrailHit as e:
            self._finalize_with_fallback(e.reason)
        except SoftTimeLimitExceeded:
            self._finalize_with_fallback(ResearchSession.TerminationReason.TIMEOUT)
        except Exception as e:
            self._mark_failed(e)
            raise

    def _mark_running(self) -> None:
        self._start_monotonic = time.monotonic()
        self.session.status = ResearchSession.Status.RUNNING
        self.session.started_at = timezone.now()
        self.session.save(update_fields=["status", "started_at"])

    def _loop(self) -> None:
        self._messages.append(
            Message(
                role="user",
                content=[TextBlock(text=build_first_user_message(self.session))],
            )
        )

        for iteration in range(MAX_AGENT_ITERATIONS):
            self._check_guardrails()

            response = self.llm.chat(
                system_prompt=SYSTEM_PROMPT,
                messages=self._messages,
                tools=self.tool_registry.get_definitions(),
            )
            self._update_tokens(response.usage)
            self.session.iteration_count = iteration + 1
            self.session.save(
                update_fields=["input_tokens", "output_tokens", "iteration_count"]
            )

            self._messages.append(Message(role="assistant", content=list(response.content)))

            tool_uses = [b for b in response.content if isinstance(b, ToolUseBlock)]
            if not tool_uses:
                self._finalize_with_answer(response)
                return

            tool_results: list[ContentBlock] = []
            for tool_use in tool_uses:
                self._check_duplicate_call(tool_use)
                self._tool_sequence += 1
                tool_results.append(self._execute_tool(tool_use, self._tool_sequence))

            self._messages.append(Message(role="user", content=tool_results))

        raise GuardrailHit(ResearchSession.TerminationReason.MAX_ITERATIONS)

    def _check_guardrails(self) -> None:
        elapsed = time.monotonic() - self._start_monotonic
        if elapsed > MAX_SESSION_WALL_CLOCK_SECONDS:
            raise GuardrailHit(ResearchSession.TerminationReason.TIMEOUT)
        if self.session.input_tokens + self.session.output_tokens > MAX_TOKENS_PER_SESSION:
            raise GuardrailHit(ResearchSession.TerminationReason.MAX_TOKENS)

    def _check_duplicate_call(self, tool_use: ToolUseBlock) -> None:
        key = (tool_use.name, json.dumps(tool_use.arguments, sort_keys=True))
        self._recent_calls.append(key)
        if (
            len(self._recent_calls) == MAX_CONSECUTIVE_DUPLICATE_CALLS
            and all(c == self._recent_calls[0] for c in self._recent_calls)
        ):
            raise GuardrailHit(ResearchSession.TerminationReason.DUPLICATE_CALLS)

    def _execute_tool(self, tool_use: ToolUseBlock, sequence: int) -> ToolResultBlock:
        started_at = timezone.now()
        result = self.tool_registry.dispatch(
            tool_use.name, tool_use.arguments, self.tool_context
        )
        content, truncated = self._truncate(result.content)
        completed_at = timezone.now()

        ToolCall.objects.create(
            session=self.session,
            sequence=sequence,
            tool_name=tool_use.name,
            arguments=tool_use.arguments,
            result_content=content,
            result_truncated=truncated,
            is_error=result.is_error,
            started_at=started_at,
            completed_at=completed_at,
        )
        return ToolResultBlock(
            tool_use_id=tool_use.id,
            content=content,
            is_error=result.is_error,
        )

    def _truncate(self, content: str) -> tuple[str, bool]:
        if len(content) <= MAX_TOOL_RESULT_CHARS:
            return content, False
        marker = (
            f"\n\n[truncated after {MAX_TOOL_RESULT_CHARS} chars; "
            f"total was {len(content)} chars]"
        )
        return content[:MAX_TOOL_RESULT_CHARS] + marker, True

    def _update_tokens(self, usage: TokenUsage) -> None:
        self.session.input_tokens += usage.input_tokens
        self.session.output_tokens += usage.output_tokens

    def _extract_text(self, content: list[ContentBlock]) -> str:
        return "".join(b.text for b in content if isinstance(b, TextBlock))

    def _finalize_with_answer(self, response: LLMResponse) -> None:
        answer = self._extract_text(response.content)
        self._finalize(answer, ResearchSession.TerminationReason.COMPLETED)

    def _finalize_with_fallback(self, reason: str) -> None:
        self._messages.append(
            Message(role="user", content=[TextBlock(text=FALLBACK_USER_MESSAGE)])
        )
        try:
            response = self.llm.chat(
                system_prompt=SYSTEM_PROMPT,
                messages=self._messages,
                tools=[],
            )
            self._update_tokens(response.usage)
            answer = self._extract_text(response.content)
        except Exception:
            answer = "Agent terminated before producing an answer."
        self._finalize(answer, reason)

    def _finalize(self, answer: str, reason: str) -> None:
        now = timezone.now()
        self.session.answer = answer
        self.session.status = ResearchSession.Status.COMPLETED
        self.session.termination_reason = reason
        self.session.completed_at = now
        self.session.save(
            update_fields=[
                "answer",
                "status",
                "termination_reason",
                "completed_at",
                "input_tokens",
                "output_tokens",
            ]
        )

        self.session.repository.last_analyzed_at = now
        self.session.repository.save(update_fields=["last_analyzed_at"])

    def _mark_failed(self, exception: Exception) -> None:
        self.session.status = ResearchSession.Status.FAILED
        self.session.termination_reason = ResearchSession.TerminationReason.ERROR
        self.session.error_message = f"{type(exception).__name__}: {exception}"
        self.session.completed_at = timezone.now()
        self.session.save(
            update_fields=["status", "termination_reason", "error_message", "completed_at"]
        )
