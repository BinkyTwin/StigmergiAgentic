"""Minimal generic assistant adapter powered by infrastructure tools."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from adapters.base import DomainAdapter, Objective, Workspace
from core.dependency import validate_dag
from core.marker import Marker, StateMachine, utc_now_iso
from core.schemas import ProtocolSpec
from core.tool_registry import ToolRegistry
from llm.prompts import SYSTEM_PROTOCOL_COMPILER, build_protocol_compiler_prompt
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

    def compile_protocol(
        self,
        objective: Objective,
        config: dict[str, Any],
        llm_client: Any | None = None,
    ) -> list[Marker] | None:
        compiler_cfg = dict(config.get("agents", {}).get("protocol_compiler", {}))
        if not bool(compiler_cfg.get("enabled", False)) or llm_client is None:
            return None

        registry = ToolRegistry()
        self.register_tools(registry)
        available_actions = registry.action_types()
        if not available_actions:
            return None

        try:
            response = llm_client.call(
                prompt=build_protocol_compiler_prompt(
                    objective=objective.description,
                    available_actions=available_actions,
                    state_machine=self.define_state_machine(),
                ),
                system=SYSTEM_PROTOCOL_COMPILER,
                response_schema=ProtocolSpec,
            )
        except Exception:  # noqa: BLE001
            return None

        parsed = getattr(response, "parsed", None)
        if not isinstance(parsed, ProtocolSpec) or not parsed.markers:
            return None

        seen_ids: set[str] = set()
        compiled: list[Marker] = []
        now = utc_now_iso()
        for spec in parsed.markers:
            if spec.id in seen_ids:
                return None
            seen_ids.add(spec.id)

            allowed_actions = [
                action for action in spec.eligible_actions if action in available_actions
            ]
            if not allowed_actions:
                return None

            payload = {
                "objective": objective.description,
                "eligible_actions": allowed_actions,
                **dict(spec.payload),
            }
            if spec.depends_on:
                payload["depends_on"] = list(spec.depends_on)
            if spec.priority:
                payload["priority"] = spec.priority

            compiled.append(
                Marker(
                    id=spec.id,
                    marker_type=spec.marker_type,
                    target=spec.target,
                    intensity=spec.intensity,
                    state="pending",
                    payload=payload,
                    created_by="system_compiler",
                    created_at=now,
                    updated_by="system_compiler",
                    updated_at=now,
                    last_active_at=now,
                    history=["compiled"],
                )
            )

        if not validate_dag(compiled):
            return None
        return compiled

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
