import uuid
from typing import Any

from google import genai

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


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash") -> None:
        self._model_name = model_name
        self._client = genai.Client(api_key=api_key)

    @property
    def provider_name(self) -> str:
        return "gemini"

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
        config_kwargs: dict[str, Any] = {
            "system_instruction": system_prompt,
            "max_output_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            config_kwargs["tools"] = self._build_tools(tools)

        response = self._client.models.generate_content(
            model=self._model_name,
            contents=self._build_contents(messages),
            config=genai.types.GenerateContentConfig(**config_kwargs),
        )
        return self._parse_response(response)

    def _build_tools(self, tools: list[ToolDefinition]) -> list[Any]:
        return [
            genai.types.Tool(
                function_declarations=[
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters_schema,
                    }
                    for tool in tools
                ]
            )
        ]

    def _build_contents(self, messages: list[Message]) -> list[dict[str, Any]]:
        tool_id_to_name: dict[str, str] = {}
        contents: list[dict[str, Any]] = []
        for message in messages:
            role = "user" if message.role == "user" else "model"
            parts: list[dict[str, Any]] = []
            for block in message.content:
                if isinstance(block, TextBlock):
                    parts.append({"text": block.text})
                elif isinstance(block, ToolUseBlock):
                    tool_id_to_name[block.id] = block.name
                    parts.append(
                        {"function_call": {"name": block.name, "args": block.arguments}}
                    )
                elif isinstance(block, ToolResultBlock):
                    name = tool_id_to_name.get(block.tool_use_id, "unknown")
                    parts.append(
                        {
                            "function_response": {
                                "name": name,
                                "response": {"content": block.content},
                            }
                        }
                    )
            contents.append({"role": role, "parts": parts})
        return contents

    def _parse_response(self, response: Any) -> LLMResponse:
        candidate = response.candidates[0]
        blocks: list[ContentBlock] = []
        has_tool_use = False

        for part in candidate.content.parts:
            if part.text:
                blocks.append(TextBlock(text=part.text))
            elif part.function_call and part.function_call.name:
                fc = part.function_call
                blocks.append(
                    ToolUseBlock(
                        id=uuid.uuid4().hex,
                        name=fc.name,
                        arguments=dict(fc.args) if fc.args else {},
                    )
                )
                has_tool_use = True

        usage = response.usage_metadata
        return LLMResponse(
            content=blocks,
            stop_reason=self._map_finish_reason(candidate.finish_reason, has_tool_use),
            usage=TokenUsage(
                input_tokens=usage.prompt_token_count or 0,
                output_tokens=usage.candidates_token_count or 0,
            ),
            raw_provider_response=response,
        )

    def _map_finish_reason(self, finish_reason: Any, has_tool_use: bool) -> Any:
        if has_tool_use:
            return "tool_use"
        name = getattr(finish_reason, "name", None)
        if name == "MAX_TOKENS":
            return "max_tokens"
        return "end_turn"
