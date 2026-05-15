from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel


@dataclass(frozen=True)
class ToolContext:
    session_id: int
    repository_id: int
    repo_path: Path


@dataclass(frozen=True)
class ToolResult:
    content: str
    is_error: bool = False


class Tool(ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    args_model: ClassVar[type[BaseModel]]

    def parameters_schema(self) -> dict[str, Any]:
        schema = self.args_model.model_json_schema()
        schema.pop("title", None)
        for prop in schema.get("properties", {}).values():
            prop.pop("title", None)
        return schema

    @abstractmethod
    def execute(self, ctx: ToolContext, args: Any) -> str: ...
