from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel

from llm.types import ToolDefinition
from tools.base import Tool, ToolContext
from tools.registry import ToolRegistry


class _EchoArgs(BaseModel):
    text: str


class _EchoTool(Tool):
    name: ClassVar[str] = "echo"
    description: ClassVar[str] = "Echo the input back"
    args_model: ClassVar[type[BaseModel]] = _EchoArgs

    def execute(self, ctx: ToolContext, args: _EchoArgs) -> str:
        return args.text


class _BoomArgs(BaseModel):
    pass


class _BoomTool(Tool):
    name: ClassVar[str] = "boom"
    description: ClassVar[str] = "Always raises"
    args_model: ClassVar[type[BaseModel]] = _BoomArgs

    def execute(self, ctx: ToolContext, args: _BoomArgs) -> str:
        raise RuntimeError("kaboom")


def _ctx() -> ToolContext:
    return ToolContext(session_id=1, repository_id=1, repo_path=Path("/tmp"))


def test_registry_dispatches_to_correct_tool() -> None:
    registry = ToolRegistry()
    registry.register(_EchoTool())

    result = registry.dispatch("echo", {"text": "hello"}, _ctx())

    assert result.content == "hello"
    assert result.is_error is False


def test_registry_returns_error_for_unknown_tool() -> None:
    registry = ToolRegistry()

    result = registry.dispatch("missing", {}, _ctx())

    assert result.is_error is True
    assert "Unknown tool" in result.content


def test_registry_returns_error_for_invalid_args() -> None:
    registry = ToolRegistry()
    registry.register(_EchoTool())

    result = registry.dispatch("echo", {}, _ctx())

    assert result.is_error is True
    assert "Invalid arguments" in result.content


def test_registry_catches_exceptions_from_tool() -> None:
    registry = ToolRegistry()
    registry.register(_BoomTool())

    result = registry.dispatch("boom", {}, _ctx())

    assert result.is_error is True
    assert "kaboom" in result.content


def test_registry_emits_tool_definitions() -> None:
    registry = ToolRegistry()
    registry.register(_EchoTool())

    definitions = registry.get_definitions()

    assert len(definitions) == 1
    assert isinstance(definitions[0], ToolDefinition)
    assert definitions[0].name == "echo"
    assert "properties" in definitions[0].parameters_schema
    assert "text" in definitions[0].parameters_schema["properties"]
