from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

import pytest

from llm.providers.gemini import GeminiProvider
from llm.types import (
    Message,
    TextBlock,
    ToolDefinition,
    ToolResultBlock,
    ToolUseBlock,
)


@pytest.fixture
def mock_genai() -> Iterator[Any]:
    with patch("llm.providers.gemini.genai") as m:
        yield m


def _text_response(text: str, prompt_tokens: int = 10, candidate_tokens: int = 5) -> SimpleNamespace:
    return SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[
                        SimpleNamespace(
                            text=text,
                            function_call=SimpleNamespace(name="", args=None),
                        )
                    ],
                ),
                finish_reason=SimpleNamespace(name="STOP"),
            )
        ],
        usage_metadata=SimpleNamespace(
            prompt_token_count=prompt_tokens,
            candidates_token_count=candidate_tokens,
        ),
    )


def _tool_call_response(name: str, args: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[
                        SimpleNamespace(
                            text="",
                            function_call=SimpleNamespace(name=name, args=args),
                        )
                    ],
                ),
                finish_reason=SimpleNamespace(name="STOP"),
            )
        ],
        usage_metadata=SimpleNamespace(
            prompt_token_count=20,
            candidates_token_count=10,
        ),
    )


def _mock_client(mock_genai: Any, response: Any) -> Mock:
    client = Mock()
    client.models.generate_content.return_value = response
    mock_genai.Client.return_value = client
    return client


def test_gemini_returns_text_block_for_simple_response(mock_genai: Any) -> None:
    client = _mock_client(mock_genai, _text_response("FastAPI uses solve_dependencies()"))

    provider = GeminiProvider(api_key="fake")
    response = provider.chat(
        system_prompt="be helpful",
        messages=[Message(role="user", content=[TextBlock(text="hi")])],
        tools=[],
    )

    assert len(response.content) == 1
    assert isinstance(response.content[0], TextBlock)
    assert response.content[0].text == "FastAPI uses solve_dependencies()"
    assert response.stop_reason == "end_turn"
    assert response.usage.input_tokens == 10
    assert response.usage.output_tokens == 5
    client.models.generate_content.assert_called_once()


def test_gemini_returns_tool_use_block_when_model_calls_function(mock_genai: Any) -> None:
    _mock_client(mock_genai, _tool_call_response("read_file", {"path": "main.py"}))

    provider = GeminiProvider(api_key="fake")
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


def test_gemini_translates_tool_definitions_to_function_declarations(mock_genai: Any) -> None:
    _mock_client(mock_genai, _text_response("ok"))

    provider = GeminiProvider(api_key="fake")
    provider.chat(
        system_prompt="be helpful",
        messages=[Message(role="user", content=[TextBlock(text="hi")])],
        tools=[
            ToolDefinition(
                name="list_files",
                description="List files at a path",
                parameters_schema={
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            )
        ],
    )

    tool_kwargs = mock_genai.types.Tool.call_args.kwargs
    assert tool_kwargs["function_declarations"] == [
        {
            "name": "list_files",
            "description": "List files at a path",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        }
    ]


def _rate_limit_error(retry_seconds: float = 1.0) -> Any:
    from google.genai.errors import ClientError

    return ClientError(
        429,
        {
            "error": {
                "code": 429,
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": f"{retry_seconds}s",
                    }
                ],
            }
        },
    )


def test_gemini_retries_on_429_when_backoff_enabled(mock_genai: Any) -> None:
    client = Mock()
    client.models.generate_content.side_effect = [
        _rate_limit_error(retry_seconds=1.5),
        _text_response("recovered"),
    ]
    mock_genai.Client.return_value = client

    provider = GeminiProvider(api_key="fake", retry_on_rate_limit=True)
    with patch("llm.providers.gemini.time.sleep") as mock_sleep:
        response = provider.chat(
            system_prompt="be helpful",
            messages=[Message(role="user", content=[TextBlock(text="hi")])],
            tools=[],
        )

    assert isinstance(response.content[0], TextBlock)
    assert response.content[0].text == "recovered"
    assert client.models.generate_content.call_count == 2
    mock_sleep.assert_called_once()
    slept_seconds = mock_sleep.call_args.args[0]
    assert slept_seconds == pytest.approx(2.5)


def test_gemini_does_not_retry_when_backoff_disabled(mock_genai: Any) -> None:
    client = Mock()
    client.models.generate_content.side_effect = _rate_limit_error()
    mock_genai.Client.return_value = client

    provider = GeminiProvider(api_key="fake", retry_on_rate_limit=False)
    from google.genai.errors import ClientError

    with pytest.raises(ClientError):
        provider.chat(
            system_prompt="be helpful",
            messages=[Message(role="user", content=[TextBlock(text="hi")])],
            tools=[],
        )

    assert client.models.generate_content.call_count == 1


def test_gemini_gives_up_after_max_retries(mock_genai: Any) -> None:
    client = Mock()
    client.models.generate_content.side_effect = _rate_limit_error()
    mock_genai.Client.return_value = client

    provider = GeminiProvider(api_key="fake", retry_on_rate_limit=True)
    from google.genai.errors import ClientError

    with patch("llm.providers.gemini.time.sleep"), pytest.raises(ClientError):
        provider.chat(
            system_prompt="be helpful",
            messages=[Message(role="user", content=[TextBlock(text="hi")])],
            tools=[],
        )

    assert client.models.generate_content.call_count == GeminiProvider.MAX_RETRIES + 1


def test_gemini_round_trips_tool_use_id_to_function_name(mock_genai: Any) -> None:
    client = _mock_client(mock_genai, _text_response("done"))

    provider = GeminiProvider(api_key="fake")
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

    contents = client.models.generate_content.call_args.kwargs["contents"]
    function_response_part = contents[2]["parts"][0]["function_response"]
    assert function_response_part["name"] == "read_file"
    assert function_response_part["response"] == {"content": "file contents"}
