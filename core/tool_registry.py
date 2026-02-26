"""Tool contracts and registry for generic stigmergic actions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .marker import Marker

if TYPE_CHECKING:
    from .environment import Environment


@dataclass(slots=True)
class Decision:
    """Decision emitted by one agent for one marker/action pair."""

    agent_id: str
    action_type: str
    marker_id: str
    target: str
    pressures: dict[str, float]
    selected_pressure: float


@dataclass(slots=True)
class ActionResult:
    """Execution output returned by tools."""

    action_type: str
    marker_updates: list[Marker] = field(default_factory=list)
    consumed_tokens: int = 0
    cost_usd: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class Tool(ABC):
    """Domain-specific action primitive executed by agents."""

    action_type: str

    @abstractmethod
    def is_eligible(self, marker: Marker) -> bool:
        """Return True when this tool can act on marker."""

    @abstractmethod
    async def execute(
        self,
        *,
        agent_id: str,
        marker: Marker,
        environment: "Environment",
        llm_client: Any | None = None,
    ) -> ActionResult:
        """Execute domain logic and return marker updates."""


class ToolRegistry:
    """In-memory registry of available tools by action type."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register one tool instance by its action type."""
        action_type = getattr(tool, "action_type", "").strip()
        if not action_type:
            raise ValueError("tool.action_type cannot be empty")
        if action_type in self._tools:
            raise ValueError(f"Tool already registered for action_type={action_type!r}")
        self._tools[action_type] = tool

    def get(self, action_type: str) -> Tool:
        """Get one tool or raise KeyError when missing."""
        if action_type not in self._tools:
            raise KeyError(f"Unknown action type: {action_type}")
        return self._tools[action_type]

    def action_types(self) -> list[str]:
        """List registered action types."""
        return list(self._tools.keys())

    def eligible_actions_for(self, marker: Marker) -> list[str]:
        """Return action types eligible for a marker."""
        actions: list[str] = []
        for action_type, tool in self._tools.items():
            if tool.is_eligible(marker):
                actions.append(action_type)
        return actions
