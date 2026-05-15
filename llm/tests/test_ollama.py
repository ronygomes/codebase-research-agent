from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

import pytest

from llm.providers.ollama import OllamaProvider
from llm.types import (
    Message,
    TextBlock,
    ToolDefinition,
    ToolResultBlock,
    ToolUseBlock,
)


@pytest.fixture
def mock_ollama() -> Iterator[Any]:
    with patch("llm.providers.ollama.ollama") as m:
        yield m


def _text_response(
    text: str, prompt_tokens: int = 10, eval_tokens: int = 5
) -> SimpleNamespace:
    return SimpleNamespace(
        message=SimpleNamespace(content=text, tool_calls=None),
        done_reason="stop",
        prompt_eval_count=prompt_tokens,
        eval_count=eval_tokens,
    )


def _tool_call_response(name: str, args: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        message=SimpleNamespace(
            content="",
            tool_calls=[
                SimpleNamespace(function=SimpleNamespace(name=name, arguments=args))
            ],
        ),
        done_reason="stop",
        prompt_eval_count=20,
        eval_count=10,
    )


def _mock_client(mock_ollama: Any, response: Any) -> Mock:
    client = Mock()
    client.chat.return_value = response
    mock_ollama.Client.return_value = client
    return client


def test_ollama_returns_text_block_for_simple_response(mock_ollama: Any) -> None:
    client = _mock_client(mock_ollama, _text_response("Flask routes via @app.route()"))

    provider = OllamaProvider(model_name="qwen2.5:7b")
    response = provider.chat(
        system_prompt="be helpful",
        messages=[Message(role="user", content=[TextBlock(text="hi")])],
        tools=[],
    )

    assert len(response.content) == 1
    assert isinstance(response.content[0], TextBlock)
    assert response.content[0].text == "Flask routes via @app.route()"
    assert response.stop_reason == "end_turn"
    assert response.usage.input_tokens == 10
    assert response.usage.output_tokens == 5
    client.chat.assert_called_once()


def test_ollama_returns_tool_use_block_when_model_calls_function(
    mock_ollama: Any,
) -> None:
    _mock_client(
        mock_ollama, _tool_call_response("read_file", {"path": "main.py"})
    )

    provider = OllamaProvider(model_name="qwen2.5:7b")
    response = provider.chat(
        system_prompt="be helpful",
        messages=[Message(role="user", content=[TextBlock(text="what's in main.py")])],
        tools=[
            ToolDefinition(
                name="read_file",
                description="Read a file",
                parameters_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            )
        ],
    )

    assert len(response.content) == 1
    assert isinstance(response.content[0], ToolUseBlock)
    assert response.content[0].name == "read_file"
    assert response.content[0].arguments == {"path": "main.py"}
    assert response.content[0].id != ""
    assert response.stop_reason == "tool_use"


def test_ollama_translates_tools_to_openai_function_format(mock_ollama: Any) -> None:
    client = _mock_client(mock_ollama, _text_response("ok"))

    provider = OllamaProvider(model_name="qwen2.5:7b")
    provider.chat(
        system_prompt="be helpful",
        messages=[Message(role="user", content=[TextBlock(text="hi")])],
        tools=[
            ToolDefinition(
                name="list_files",
                description="List files",
                parameters_schema={
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            )
        ],
    )

    tools_kwarg = client.chat.call_args.kwargs["tools"]
    assert tools_kwarg == [
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        }
    ]


def test_ollama_includes_system_prompt_as_first_message(mock_ollama: Any) -> None:
    client = _mock_client(mock_ollama, _text_response("ok"))

    provider = OllamaProvider(model_name="qwen2.5:7b")
    provider.chat(
        system_prompt="You are a research agent",
        messages=[Message(role="user", content=[TextBlock(text="hello")])],
        tools=[],
    )

    sent_messages = client.chat.call_args.kwargs["messages"]
    assert sent_messages[0] == {"role": "system", "content": "You are a research agent"}
    assert sent_messages[1]["role"] == "user"


def test_ollama_round_trips_tool_use_id_to_function_name(mock_ollama: Any) -> None:
    client = _mock_client(mock_ollama, _text_response("done"))

    provider = OllamaProvider(model_name="qwen2.5:7b")
    provider.chat(
        system_prompt="be helpful",
        messages=[
            Message(role="user", content=[TextBlock(text="check main.py")]),
            Message(
                role="assistant",
                content=[
                    ToolUseBlock(id="abc123", name="read_file", arguments={"path": "main.py"})
                ],
            ),
            Message(
                role="user",
                content=[ToolResultBlock(tool_use_id="abc123", content="file contents")],
            ),
        ],
        tools=[],
    )

    sent_messages = client.chat.call_args.kwargs["messages"]
    tool_message = next(m for m in sent_messages if m.get("role") == "tool")
    assert tool_message["tool_name"] == "read_file"
    assert tool_message["content"] == "file contents"


def test_ollama_maps_length_done_reason_to_max_tokens(mock_ollama: Any) -> None:
    response = SimpleNamespace(
        message=SimpleNamespace(content="truncated", tool_calls=None),
        done_reason="length",
        prompt_eval_count=10,
        eval_count=4096,
    )
    _mock_client(mock_ollama, response)

    provider = OllamaProvider(model_name="qwen2.5:7b")
    result = provider.chat(
        system_prompt="be helpful",
        messages=[Message(role="user", content=[TextBlock(text="hi")])],
        tools=[],
    )

    assert result.stop_reason == "max_tokens"
