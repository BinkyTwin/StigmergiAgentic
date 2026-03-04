"""Minimal generic assistant adapter powered by infrastructure tools."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from adapters.base import DomainAdapter, Objective, Workspace
from core.marker import Marker, StateMachine, utc_now_iso
from core.tool_registry import ToolRegistry
from tools import register_infrastructure_tools

from .workspace import LocalWorkspace


TERMINAL_STATES = {"terminal", "skipped", "escalated"}


class AssistantAdapter(DomainAdapter):
    """DomainAdapter implementation for generic assistant mode."""

    def __init__(self, *, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    def create_workspace(self, config: dict[str, Any]) -> Workspace:
        tools_cfg = dict(config.get("tools", {}))
        return LocalWorkspace(
            root=tools_cfg.get("sandbox_root", "."),
            max_file_size_bytes=int(tools_cfg.get("max_file_size_bytes", 1_048_576)),
        )

    def create_objective(
        self,
        user_input: dict[str, Any],
        config: dict[str, Any],
    ) -> Objective:
        description = str(user_input.get("objective", "")).strip()
        if not description:
            raise ValueError("assistant objective cannot be empty")

        payload: dict[str, Any] = {}
        subtasks = user_input.get("subtasks")
        if isinstance(subtasks, list):
            payload["subtasks"] = [
                str(item).strip() for item in subtasks if str(item).strip()
            ]
        if "subtask_count" in user_input:
            payload["subtask_count"] = int(user_input["subtask_count"])

        return Objective(
            objective_id=str(uuid4()),
            description=description,
            payload=payload,
        )

    def register_tools(self, registry: ToolRegistry) -> None:
        register_infrastructure_tools(registry=registry, config=self.config)

    def define_state_machine(self) -> StateMachine:
        return StateMachine()

    def initial_markers(self, objective: Objective, agent_id: str) -> list[Marker]:
        now = utc_now_iso()
        base_payload: dict[str, Any] = {"objective": objective.description}
        if "subtask_count" in objective.payload:
            base_payload["subtask_count"] = int(objective.payload["subtask_count"])

        subtasks = objective.payload.get("subtasks", [])
        if isinstance(subtasks, list) and subtasks:
            root = Marker(
                id=objective.objective_id,
                marker_type="task",
                target=objective.objective_id,
                intensity=1.0,
                state="active",
                payload={
                    **base_payload,
                    "decomposed": True,
                    "subtask_count": len(subtasks),
                },
                created_by=agent_id,
                created_at=now,
                updated_by=agent_id,
                updated_at=now,
                history=["created"],
            )
            children: list[Marker] = []
            for index, subtask in enumerate(subtasks, start=1):
                children.append(
                    Marker(
                        id=f"{objective.objective_id}::subtask::{index}",
                        marker_type="task",
                        target=f"{objective.objective_id}::{index}",
                        intensity=0.8,
                        state="pending",
                        payload={
                            "task": str(subtask),
                            "objective": objective.description,
                            "parent_id": objective.objective_id,
                        },
                        created_by=agent_id,
                        created_at=now,
                        updated_by=agent_id,
                        updated_at=now,
                        history=["created"],
                    )
                )
            return [root, *children]

        return [
            Marker(
                id=objective.objective_id,
                marker_type="task",
                target=objective.objective_id,
                intensity=1.0,
                state="pending",
                payload={**base_payload},
                created_by=agent_id,
                created_at=now,
                updated_by=agent_id,
                updated_at=now,
                history=["created"],
            )
        ]

    def evaluate_run(self, env_snapshot: dict[str, Any]) -> dict[str, Any]:
        markers = env_snapshot.get("markers", [])
        total = len(markers)
        terminal_count = sum(1 for marker in markers if marker.state in TERMINAL_STATES)
        completed_count = sum(
            1
            for marker in markers
            if marker.state in {"completed", "verified", *TERMINAL_STATES}
        )
        return {
            "markers_total": total,
            "markers_terminal": terminal_count,
            "markers_completed_or_more": completed_count,
            "terminal_ratio": (float(terminal_count) / float(total)) if total else 0.0,
        }
