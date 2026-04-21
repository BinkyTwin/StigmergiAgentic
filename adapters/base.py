"""Domain adapter contracts for V2 runtime."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from core.marker import Marker, StateMachine
from core.tool_registry import ToolRegistry


@dataclass(slots=True)
class Objective:
    """Domain objective passed to one adapter run."""

    objective_id: str
    description: str
    payload: dict[str, Any] = field(default_factory=dict)


class Workspace(ABC):
    """Abstract workspace manipulated by domain tools."""

    @abstractmethod
    def list_targets(self) -> list[str]:
        """List logical targets available in workspace."""


class DomainAdapter(ABC):
    """Adapter contract separating domain logic from core orchestration."""

    @abstractmethod
    def create_workspace(self, config: dict[str, Any]) -> Workspace:
        """Build workspace implementation for one run."""

    @abstractmethod
    def create_objective(
        self,
        user_input: dict[str, Any],
        config: dict[str, Any],
    ) -> Objective:
        """Convert user input into typed objective."""

    @abstractmethod
    def register_tools(self, registry: ToolRegistry) -> None:
        """Register domain tools in registry."""

    @abstractmethod
    def define_state_machine(self) -> StateMachine:
        """Provide domain-specific state machine."""

    @abstractmethod
    def initial_markers(self, objective: Objective, agent_id: str) -> list[Marker]:
        """Produce initial marker set for objective."""

    def compile_protocol(
        self,
        objective: Objective,
        config: dict[str, Any],
        llm_client: Any | None = None,
    ) -> list[Marker] | None:
        """Optionally compile a coordination protocol from the objective.

        Returning ``None`` signals that the runtime must fall back to
        :meth:`initial_markers`.
        """
        return None

    @abstractmethod
    def evaluate_run(self, env_snapshot: dict[str, Any]) -> dict[str, Any]:
        """Compute domain-level evaluation result."""
