"""Infrastructure tools for generic assistant-like workloads."""

from __future__ import annotations

from core.tool_registry import ToolRegistry

from .bash_exec import BashExecTool
from .decompose import DecomposeTool
from .file_read import FileReadTool
from .file_write import FileWriteTool
from .think import ThinkTool
from .web_search import WebSearchTool


def register_infrastructure_tools(registry: ToolRegistry, config: dict) -> None:
    """Register generic infrastructure tools in one place."""
    hintable_tools = ["file_read", "file_write", "bash_exec", "web_search"]
    registry.register(FileReadTool(config=config))
    registry.register(FileWriteTool(config=config))
    registry.register(BashExecTool(config=config))
    registry.register(WebSearchTool(config=config))
    registry.register(ThinkTool(config=config, available_hint_tools=hintable_tools))
    registry.register(DecomposeTool(config=config))


__all__ = [
    "BashExecTool",
    "DecomposeTool",
    "FileReadTool",
    "FileWriteTool",
    "ThinkTool",
    "WebSearchTool",
    "register_infrastructure_tools",
]
