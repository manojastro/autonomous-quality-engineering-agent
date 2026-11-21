"""Tool registry assembly and exports."""
from backend.app.tools.base import ToolError, ToolRegistry, registry
from backend.app.tools.catalog import (
    AnalyzeFailuresTool,
    ClassifyFlakyTool,
    ComputeConfidenceTool,
    EvaluateQualityGateTool,
    ExecuteTestsTool,
    ScanDependenciesTool,
    SelectTestsTool,
    TriggerRegressionBugTool,
)


def build_default_registry() -> ToolRegistry:
    reg = ToolRegistry()
    for tool in (
        ScanDependenciesTool(),
        SelectTestsTool(),
        ExecuteTestsTool(),
        AnalyzeFailuresTool(),
        ClassifyFlakyTool(),
        ComputeConfidenceTool(),
        EvaluateQualityGateTool(),
        TriggerRegressionBugTool(),
    ):
        reg.register(tool)
    return reg


default_registry = build_default_registry()

__all__ = [
    "ToolError",
    "ToolRegistry",
    "registry",
    "default_registry",
    "build_default_registry",
]
