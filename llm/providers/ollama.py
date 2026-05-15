import uuid
from typing import Any, ClassVar

import ollama

from llm.providers.base import LLMProvider
from llm.types import (
    ContentBlock,
    LLMResponse,
    Message,
    TextBlock,
    TokenUsage,
    ToolDefinition,
    ToolResultBlock,
    ToolUseBlock,
)


class OllamaProvider(LLMProvider):
    DEFAULT_HOST: ClassVar[str] = "http://localhost:11434"

    def __init__(
        self,
        model_name: str = "qwen2.5:7b",
        host: str = DEFAULT_HOST,
    ) -> None:
        self._model_name = model_name
        self._client = ollama.Client(host=host)

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model_name

    def chat(
        self,
        system_prompt: str,
        messages: list[Message],
        tools: list[ToolDefinition],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self._model_name,
            "messages": self._build_messages(system_prompt, messages),
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if tools:
            kwargs["tools"] = self._build_tools(tools)

        response = self._client.chat(**kwargs)
        return self._parse_response(response)

    def _build_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters_schema,
                },
            }
            for tool in tools
        ]

    def _build_messages(
        self, system_prompt: str, messages: list[Message]
    ) -> list[dict[str, Any]]:
        ollama_messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]
        tool_id_to_name: dict[str, str] = {}

        for message in messages:
            text_parts: list[str] = []
            tool_calls: list[dict[str, Any]] = []
            tool_results: list[dict[str, Any]] = []

            for block in message.content:
                if isinstance(block, TextBlock):
                    text_parts.append(block.text)
                elif isinstance(block, ToolUseBlock):
                    tool_id_to_name[block.id] = block.name
                    tool_calls.append(
                        {
                            "function": {
                                "name": block.name,
                                "arguments": block.arguments,
                            }
                        }
                    )
                elif isinstance(block, ToolResultBlock):
                    name = tool_id_to_name.get(block.tool_use_id, "unknown")
                    tool_results.append(
                        {
                            "role": "tool",
                            "tool_name": name,
                            "content": block.content,
                        }
                    )

            if message.role == "user":
                if text_parts:
                    ollama_messages.append(
                        {"role": "user", "content": "\n".join(text_parts)}
                    )
                ollama_messages.extend(tool_results)
            else:
                assistant_message: dict[str, Any] = {
                    "role": "assistant",
                    "content": "\n".join(text_parts),
                }
                if tool_calls:
                    assistant_message["tool_calls"] = tool_calls
                ollama_messages.append(assistant_message)

        return ollama_messages

    def _parse_response(self, response: Any) -> LLMResponse:
        message = response.message
        blocks: list[ContentBlock] = []
        has_tool_use = False

        text = getattr(message, "content", None)
        if text:
            blocks.append(TextBlock(text=text))

        for call in getattr(message, "tool_calls", None) or []:
            fn = call.function
            arguments = dict(fn.arguments) if fn.arguments else {}
            blocks.append(
                ToolUseBlock(
                    id=uuid.uuid4().hex,
                    name=fn.name,
                    arguments=arguments,
                )
            )
            has_tool_use = True

        done_reason = getattr(response, "done_reason", "stop") or "stop"
        if has_tool_use:
            stop_reason: Any = "tool_use"
        elif done_reason == "length":
            stop_reason = "max_tokens"
        else:
            stop_reason = "end_turn"

        return LLMResponse(
            content=blocks,
            stop_reason=stop_reason,
            usage=TokenUsage(
                input_tokens=getattr(response, "prompt_eval_count", 0) or 0,
                output_tokens=getattr(response, "eval_count", 0) or 0,
            ),
            raw_provider_response=response,
        )
