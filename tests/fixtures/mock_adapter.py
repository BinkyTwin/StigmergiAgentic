"""Mock adapter and tools used by Sprint 2 unit tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from adapters.base import DomainAdapter, Objective, Workspace
from core.marker import Marker, StateMachine, utc_now_iso
from core.tool_registry import ActionResult, Tool, ToolRegistry


@dataclass(slots=True)
class MockWorkspace(Workspace):
    """In-memory workspace with a fixed target list."""

    targets: list[str]

    def list_targets(self) -> list[str]:
        return list(self.targets)


class IncrementTool(Tool):
    """Increment progress counter until item can be checked."""

    action_type = "increment"

    def is_eligible(self, marker: Marker) -> bool:
        if marker.marker_type != "task":
            return False
        if marker.state not in {"pending", "active"}:
            return False
        current = int(marker.payload.get("counter", 0))
        target = int(marker.payload.get("target_count", 2))
        return current < target

    async def execute(
        self,
        *,
        agent_id: str,
        marker: Marker,
        environment: Any,
        llm_client: Any | None = None,
    ) -> ActionResult:
        updated = Marker.from_dict(marker.to_dict())
        payload = dict(updated.payload)

        counter = int(payload.get("counter", 0)) + 1
        target_count = int(payload.get("target_count", 2))
        payload["counter"] = counter
        updated.payload = payload

        updated.state = "completed" if counter >= target_count else "active"
        updated.intensity = 0.7 if updated.state == "completed" else 1.0

        return ActionResult(
            action_type=self.action_type,
            marker_updates=[updated],
            consumed_tokens=10,
            cost_usd=0.01,
        )


class CheckTool(Tool):
    """Promote completed task to verified."""

    action_type = "check"

    def is_eligible(self, marker: Marker) -> bool:
        return marker.marker_type == "task" and marker.state == "completed"

    async def execute(
        self,
        *,
        agent_id: str,
        marker: Marker,
        environment: Any,
        llm_client: Any | None = None,
    ) -> ActionResult:
        updated = Marker.from_dict(marker.to_dict())
        updated.state = "verified"
        updated.intensity = 0.4
        return ActionResult(
            action_type=self.action_type,
            marker_updates=[updated],
            consumed_tokens=2,
            cost_usd=0.002,
        )


class FinalizeTool(Tool):
    """Promote verified task to terminal."""

    action_type = "finalize"

    def is_eligible(self, marker: Marker) -> bool:
        return marker.marker_type == "task" and marker.state == "verified"

    async def execute(
        self,
        *,
        agent_id: str,
        marker: Marker,
        environment: Any,
        llm_client: Any | None = None,
    ) -> ActionResult:
        updated = Marker.from_dict(marker.to_dict())
        updated.state = "terminal"
        updated.intensity = 0.1
        return ActionResult(
            action_type=self.action_type,
            marker_updates=[updated],
            consumed_tokens=1,
            cost_usd=0.001,
        )


class MockAdapter(DomainAdapter):
    """Mock domain adapter with a 3-step workflow."""

    def create_workspace(self, config: dict[str, Any]) -> Workspace:
        item_count = int(config.get("mock", {}).get("item_count", 3))
        return MockWorkspace(targets=[f"item-{idx}" for idx in range(1, item_count + 1)])

    def create_objective(
        self,
        user_input: dict[str, Any],
        config: dict[str, Any],
    ) -> Objective:
        item_count = int(user_input.get("item_count", config.get("mock", {}).get("item_count", 3)))
        target_count = int(user_input.get("target_count", config.get("mock", {}).get("target_count", 2)))
        return Objective(
            objective_id="mock-objective",
            description="Mock adapter objective",
            payload={"item_count": item_count, "target_count": target_count},
        )

    def register_tools(self, registry: ToolRegistry) -> None:
        registry.register(IncrementTool())
        registry.register(CheckTool())
        registry.register(FinalizeTool())

    def define_state_machine(self) -> StateMachine:
        return StateMachine()

    def initial_markers(self, objective: Objective, agent_id: str) -> list[Marker]:
        now = utc_now_iso()
        markers: list[Marker] = []
        item_count = int(objective.payload.get("item_count", 3))
        target_count = int(objective.payload.get("target_count", 2))

        for idx in range(1, item_count + 1):
            markers.append(
                Marker(
                    id=f"mock-{idx}",
                    marker_type="task",
                    target=f"item-{idx}",
                    intensity=1.0,
                    state="pending",
                    payload={"counter": 0, "target_count": target_count},
                    created_by=agent_id,
                    created_at=now,
                    updated_by=agent_id,
                    updated_at=now,
                    history=["created"],
                )
            )
        return markers

    def evaluate_run(self, env_snapshot: dict[str, Any]) -> dict[str, Any]:
        markers = env_snapshot.get("markers", [])
        terminal = sum(1 for marker in markers if marker.state == "terminal")
        total = len(markers)
        return {
            "terminal_count": terminal,
            "total_count": total,
            "terminal_ratio": (float(terminal) / float(total)) if total else 0.0,
        }


def seed_mock_markers(*, adapter: MockAdapter, objective: Objective, store: Any, agent_id: str) -> None:
    """Seed marker store with adapter initial markers."""
    for marker in adapter.initial_markers(objective=objective, agent_id=agent_id):
        store.upsert_marker(marker=marker, agent_id=agent_id)
