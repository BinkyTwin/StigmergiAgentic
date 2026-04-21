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
    marker_type: str = ""
    selection_affinity: float = 0.0
    tick: int = 0
    context: str = ""
    recalled_memories: list[dict[str, Any]] = field(default_factory=list)
    lesson_markers: list[dict[str, Any]] = field(default_factory=list)
    skill_markers: list[dict[str, Any]] = field(default_factory=list)
    stickiness_applied: bool = False
    recovery_preference_applied: bool = False


@dataclass(slots=True)
class RepairRequest:
    """Generic targeted-repair request emitted by a validation-capable tool."""

    target_marker_id: str
    attempt: int = 1
    max_attempts: int = 1
    feedback: list[str] = field(default_factory=list)
    eligible_actions: list[str] = field(default_factory=list)
    intensity: float | None = None
    marker_type: str = "repair"
    payload_updates: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ValidationResult:
    """Structured validation outcome optionally coupled with a repair request."""

    status: str
    source_marker_id: str
    targets: list[str] = field(default_factory=list)
    feedback: list[str] = field(default_factory=list)
    repair: RepairRequest | None = None


def build_repair_marker_id(
    *,
    source_marker_id: str,
    target_marker_id: str,
    attempt: int,
) -> str:
    """Return a deterministic repair marker ID shared by tools and runtime."""
    return (
        f"repair::{str(source_marker_id).strip()}::"
        f"{str(target_marker_id).strip()}::attempt::{max(1, int(attempt))}"
    )


@dataclass(slots=True)
class ActionResult:
    """Execution output returned by tools.

    ``metadata`` may include ``credited_lesson_ids`` to report which recalled
    lesson markers materially contributed to a successful execution.
    """

    action_type: str
    marker_updates: list[Marker] = field(default_factory=list)
    consumed_tokens: int = 0
    cost_usd: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    validation: ValidationResult | None = None


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
        return sorted(self._tools.keys())

    def eligible_actions_for(self, marker: Marker) -> list[str]:
        """Return action types eligible for a marker."""
        actions: list[str] = []
        for action_type, tool in self._tools.items():
            if tool.is_eligible(marker):
                actions.append(action_type)
        return actions
