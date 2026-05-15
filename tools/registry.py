from typing import Any

from pydantic import ValidationError

from llm.types import ToolDefinition
from tools.base import Tool, ToolContext, ToolResult


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get_definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name=tool.name,
                description=tool.description,
                parameters_schema=tool.parameters_schema(),
            )
            for tool in self._tools.values()
        ]

    def dispatch(
        self, name: str, arguments: dict[str, Any], ctx: ToolContext
    ) -> ToolResult:
        if name not in self._tools:
            return ToolResult(content=f"Unknown tool: {name}", is_error=True)

        tool = self._tools[name]
        try:
            args = tool.args_model.model_validate(arguments)
        except ValidationError as e:
            return ToolResult(content=f"Invalid arguments: {e}", is_error=True)

        try:
            content = tool.execute(ctx, args)
        except Exception as e:
            return ToolResult(content=f"{type(e).__name__}: {e}", is_error=True)

        return ToolResult(content=content, is_error=False)
