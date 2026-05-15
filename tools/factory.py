from tools.code_exploration import (
    GetFileSummaryTool,
    ListFilesTool,
    ReadFileTool,
    SearchCodeTool,
)
from tools.database import (
    GetPreviousFindingsTool,
    ListPastSessionsTool,
    SaveFindingTool,
)
from tools.registry import ToolRegistry


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ListFilesTool())
    registry.register(ReadFileTool())
    registry.register(SearchCodeTool())
    registry.register(GetFileSummaryTool())
    registry.register(SaveFindingTool())
    registry.register(GetPreviousFindingsTool())
    registry.register(ListPastSessionsTool())
    return registry
