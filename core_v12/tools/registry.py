"""Tool registry for V12 autonomous agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from core_v10.contracts import WorkspaceHandle

from core_v12.tools.schema import ToolCall, ToolResult, ToolSpec


ToolHandler = Callable[["ToolExecutionContext", ToolCall], ToolResult]


@dataclass(frozen=True)
class ToolExecutionContext:
    """Runtime state available to a tool execution."""

    workspace: Any
    migration_context: Any | None = None
    objective: str = ""
    timeout_seconds: float = 600.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def workspace_handle(self) -> WorkspaceHandle | None:
        """Return the workspace if it already is a V10 handle."""

        return self.workspace if isinstance(self.workspace, WorkspaceHandle) else None


@dataclass(frozen=True)
class Tool:
    """Registered tool plus its implementation."""

    spec: ToolSpec
    handler: ToolHandler

    def execute(self, context: ToolExecutionContext, call: ToolCall) -> ToolResult:
        return self.handler(context, call)


class ToolRegistry:
    """Deterministic, inspectable registry of agent-facing tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, spec: ToolSpec, handler: ToolHandler) -> None:
        """Register one tool, replacing no existing tool."""

        if spec.name in self._tools:
            raise ValueError(f"tool already registered: {spec.name}")
        self._tools[spec.name] = Tool(spec=spec, handler=handler)

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"unknown V12 tool: {name}") from exc

    def specs(self) -> tuple[ToolSpec, ...]:
        return tuple(self._tools[name].spec for name in sorted(self._tools))

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def to_public_schema(self) -> list[dict[str, Any]]:
        """Return JSON-serializable tool specs for prompts and traces."""

        return [spec.model_dump(mode="json") for spec in self.specs()]


__all__ = ["Tool", "ToolExecutionContext", "ToolRegistry"]
