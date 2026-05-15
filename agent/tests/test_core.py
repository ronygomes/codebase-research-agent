from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from agent.core import Agent
from llm.providers.base import LLMProvider
from llm.types import (
    LLMResponse,
    TextBlock,
    TokenUsage,
    ToolUseBlock,
)
from repos.models import Repository
from research.models import ResearchSession, ToolCall
from tools.base import ToolResult
from tools.registry import ToolRegistry


@pytest.fixture
def session(repository: Repository) -> ResearchSession:
    return ResearchSession.objects.create(
        repository=repository,
        question="How does X work?",
        llm_provider="gemini",
        llm_model="gemini-2.0-flash",
    )


def _llm_response(
    text: str = "",
    tool_uses: list[ToolUseBlock] | None = None,
    stop_reason: str = "end_turn",
) -> LLMResponse:
    content: list[Any] = []
    if text:
        content.append(TextBlock(text=text))
    if tool_uses:
        content.extend(tool_uses)
    return LLMResponse(
        content=content,
        stop_reason=stop_reason,
        usage=TokenUsage(input_tokens=10, output_tokens=5),
    )


def _make_agent(
    session: ResearchSession,
    llm: Any,
    registry: Any = None,
) -> Agent:
    if registry is None:
        registry = Mock(spec=ToolRegistry)
        registry.get_definitions.return_value = []
    return Agent(
        session=session,
        llm_provider=llm,
        tool_registry=registry,
        repo_path=Path("/tmp"),
    )


@pytest.mark.django_db
def test_agent_completes_when_llm_returns_text_only(session: ResearchSession) -> None:
    llm = Mock(spec=LLMProvider)
    llm.chat.return_value = _llm_response(text="FastAPI uses solve_dependencies()")

    _make_agent(session, llm).run()

    session.refresh_from_db()
    assert session.status == ResearchSession.Status.COMPLETED
    assert session.termination_reason == ResearchSession.TerminationReason.COMPLETED
    assert session.answer == "FastAPI uses solve_dependencies()"
    assert session.iteration_count == 1
    assert session.input_tokens == 10
    assert session.output_tokens == 5


@pytest.mark.django_db
def test_agent_dispatches_tool_call_and_continues(session: ResearchSession) -> None:
    llm = Mock(spec=LLMProvider)
    llm.chat.side_effect = [
        _llm_response(
            tool_uses=[ToolUseBlock(id="x", name="read_file", arguments={"path": "main.py"})],
            stop_reason="tool_use",
        ),
        _llm_response(text="The answer is in main.py"),
    ]

    registry = Mock(spec=ToolRegistry)
    registry.get_definitions.return_value = []
    registry.dispatch.return_value = ToolResult(content="file contents", is_error=False)

    _make_agent(session, llm, registry).run()

    session.refresh_from_db()
    assert session.status == ResearchSession.Status.COMPLETED
    assert session.iteration_count == 2
    assert session.answer == "The answer is in main.py"

    tool_call = ToolCall.objects.get()
    assert tool_call.tool_name == "read_file"
    assert tool_call.sequence == 1
    assert tool_call.result_content == "file contents"


@pytest.mark.django_db
def test_agent_hits_max_iterations_and_falls_back(
    session: ResearchSession, monkeypatch: Any
) -> None:
    monkeypatch.setattr("agent.core.MAX_AGENT_ITERATIONS", 2)

    llm = Mock(spec=LLMProvider)
    llm.chat.side_effect = [
        _llm_response(
            tool_uses=[ToolUseBlock(id="a", name="t", arguments={"x": 1})],
            stop_reason="tool_use",
        ),
        _llm_response(
            tool_uses=[ToolUseBlock(id="b", name="t", arguments={"x": 2})],
            stop_reason="tool_use",
        ),
        _llm_response(text="best effort answer"),
    ]
    registry = Mock(spec=ToolRegistry)
    registry.get_definitions.return_value = []
    registry.dispatch.return_value = ToolResult(content="ok", is_error=False)

    _make_agent(session, llm, registry).run()

    session.refresh_from_db()
    assert session.status == ResearchSession.Status.COMPLETED
    assert session.termination_reason == ResearchSession.TerminationReason.MAX_ITERATIONS
    assert session.answer == "best effort answer"


@pytest.mark.django_db
def test_agent_detects_duplicate_calls_and_falls_back(
    session: ResearchSession, monkeypatch: Any
) -> None:
    monkeypatch.setattr("agent.core.MAX_CONSECUTIVE_DUPLICATE_CALLS", 2)
    monkeypatch.setattr("agent.core.MAX_AGENT_ITERATIONS", 10)

    llm = Mock(spec=LLMProvider)
    llm.chat.side_effect = [
        _llm_response(
            tool_uses=[ToolUseBlock(id="a", name="t", arguments={"x": 1})],
            stop_reason="tool_use",
        ),
        _llm_response(
            tool_uses=[ToolUseBlock(id="b", name="t", arguments={"x": 1})],
            stop_reason="tool_use",
        ),
        _llm_response(text="i give up"),
    ]
    registry = Mock(spec=ToolRegistry)
    registry.get_definitions.return_value = []
    registry.dispatch.return_value = ToolResult(content="ok", is_error=False)

    _make_agent(session, llm, registry).run()

    session.refresh_from_db()
    assert session.termination_reason == ResearchSession.TerminationReason.DUPLICATE_CALLS
    assert session.answer == "i give up"


@pytest.mark.django_db
def test_agent_marks_failed_when_llm_raises_exception(
    session: ResearchSession,
) -> None:
    llm = Mock(spec=LLMProvider)
    llm.chat.side_effect = RuntimeError("API down")

    agent = _make_agent(session, llm)
    with pytest.raises(RuntimeError, match="API down"):
        agent.run()

    session.refresh_from_db()
    assert session.status == ResearchSession.Status.FAILED
    assert session.termination_reason == ResearchSession.TerminationReason.ERROR
    assert "API down" in session.error_message


@pytest.mark.django_db
def test_agent_updates_repository_last_analyzed_at_on_completion(
    session: ResearchSession,
) -> None:
    assert session.repository.last_analyzed_at is None
    llm = Mock(spec=LLMProvider)
    llm.chat.return_value = _llm_response(text="done")

    _make_agent(session, llm).run()

    session.repository.refresh_from_db()
    assert session.repository.last_analyzed_at is not None


@pytest.mark.django_db
def test_agent_truncates_oversized_tool_results(
    session: ResearchSession, monkeypatch: Any
) -> None:
    monkeypatch.setattr("agent.core.MAX_TOOL_RESULT_CHARS", 100)

    llm = Mock(spec=LLMProvider)
    llm.chat.side_effect = [
        _llm_response(
            tool_uses=[ToolUseBlock(id="x", name="read_file", arguments={"path": "big.py"})],
            stop_reason="tool_use",
        ),
        _llm_response(text="done"),
    ]
    registry = Mock(spec=ToolRegistry)
    registry.get_definitions.return_value = []
    registry.dispatch.return_value = ToolResult(content="x" * 500, is_error=False)

    _make_agent(session, llm, registry).run()

    tool_call = ToolCall.objects.get()
    assert tool_call.result_truncated is True
    assert "[truncated after 100 chars" in tool_call.result_content
