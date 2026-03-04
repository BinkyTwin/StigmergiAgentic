"""Infrastructure tool that decomposes one objective into sub-markers."""

from __future__ import annotations

import json
from typing import Any

from core.marker import Marker, utc_now_iso
from core.schemas import DecomposeOutput, SubtaskSpec
from core.tool_registry import ActionResult, Tool
from llm.prompts import SYSTEM_STIGMERGIC_AGENT_PROMPT


STATE_PROGRESS = {
    "pending": "active",
    "active": "completed",
    "completed": "verified",
    "verified": "terminal",
}


class DecomposeTool(Tool):
    """Generate subtasks and persist them as child markers."""

    action_type = "decompose"

    def __init__(self, *, config: dict[str, Any]) -> None:
        self.config = config
        markers_cfg = dict(config.get("markers", {}))
        decompose_cfg = dict(config.get("decompose", {}))
        self.intensity_step = float(markers_cfg.get("intensity_step_decompose", 0.1))
        self.child_intensity_offset = float(
            markers_cfg.get("child_intensity_offset", 0.2)
        )
        self.intensity_floor = float(markers_cfg.get("intensity_floor", 0.1))
        self.max_depth = int(decompose_cfg.get("max_depth", 3))
        self.max_subtasks = int(decompose_cfg.get("max_subtasks", 8))
        self.allow_redecompose = bool(decompose_cfg.get("allow_redecompose", False))

    def is_eligible(self, marker: Marker) -> bool:
        raw = marker.payload.get("eligible_actions")
        if isinstance(raw, (list, tuple, set)) and len(raw) > 0:
            return self.action_type in {str(item) for item in raw}

        if bool(marker.payload.get("decomposed")) and not self.allow_redecompose:
            return False
        parent_id = marker.payload.get("parent_id")
        return not isinstance(parent_id, str)

    async def execute(
        self,
        *,
        agent_id: str,
        marker: Marker,
        environment: Any,
        llm_client: Any | None = None,
    ) -> ActionResult:
        objective = str(
            marker.payload.get("objective", marker.payload.get("task", marker.target))
        ).strip()
        desired_count: int | None = (
            int(marker.payload["subtask_count"])
            if "subtask_count" in marker.payload
            else None
        )
        depth = self._decomposition_depth(marker=marker, environment=environment)
        if depth >= self.max_depth:
            return ActionResult(
                action_type=self.action_type,
                metadata={
                    "failed": True,
                    "reason": "max_depth_reached",
                    "depth": depth,
                },
            )

        subtasks: list[SubtaskSpec] = []
        consumed_tokens = 0
        cost_usd = 0.0

        if llm_client is not None and (
            hasattr(llm_client, "acall") or hasattr(llm_client, "call")
        ):
            prompt = (
                "Decompose the following objective into concrete executable subtasks.\n"
                "Use as many or as few subtasks as the objective requires -- "
                "do not force a fixed number.\n"
                "Return strict JSON: "
                '{"subtasks":[{"title":"...","description":"",'
                '"depends_on_indices":[],"eligible_actions":[]}]}'
                "\n"
                f"Objective: {objective}"
            )
            if desired_count is not None:
                prompt += f"\nSuggested target: around {desired_count} subtasks"
            try:
                if hasattr(llm_client, "acall"):
                    response = await llm_client.acall(
                        prompt=prompt,
                        system=SYSTEM_STIGMERGIC_AGENT_PROMPT,
                        response_schema=DecomposeOutput,
                    )
                else:
                    response = llm_client.call(
                        prompt=prompt,
                        system=SYSTEM_STIGMERGIC_AGENT_PROMPT,
                    )
                consumed_tokens = int(getattr(response, "tokens_used", 0))
                cost_usd = float(getattr(response, "cost_usd", 0.0))
                parsed = getattr(response, "parsed", None)
                if isinstance(parsed, DecomposeOutput):
                    subtasks = list(parsed.subtasks)
                else:
                    raw_content = str(getattr(response, "content", ""))
                    subtasks = self._parse_subtasks(
                        raw_content=raw_content, llm_client=llm_client
                    )
            except Exception:  # noqa: BLE001
                subtasks = []

        if not subtasks:
            subtasks = self._fallback_subtasks(
                objective=objective, desired_count=desired_count
            )
        subtasks = subtasks[: max(1, self.max_subtasks)]

        updated_parent = Marker.from_dict(marker.to_dict())
        parent_payload = dict(updated_parent.payload)
        parent_payload["decomposed"] = True
        parent_payload["subtask_count"] = len(subtasks)
        updated_parent.payload = parent_payload
        updated_parent.state = STATE_PROGRESS.get(
            updated_parent.state, updated_parent.state
        )
        updated_parent.intensity = max(
            self.intensity_floor,
            float(updated_parent.intensity) - self.intensity_step,
        )

        now = utc_now_iso()
        child_markers: list[Marker] = []
        child_ids = {
            idx: f"{marker.id}::subtask::{idx + 1}"
            for idx in range(len(subtasks))
        }
        for index, subtask in enumerate(subtasks, start=1):
            child_id = f"{marker.id}::subtask::{index}"
            dependencies = self._resolve_dependency_ids(
                depends_on_indices=subtask.depends_on_indices,
                child_ids=child_ids,
            )
            dependencies = [dep for dep in dependencies if dep != child_id]
            payload: dict[str, Any] = {
                "task": subtask.title,
                "description": subtask.description,
                "objective": objective,
                "parent_id": marker.id,
            }
            if dependencies:
                payload["depends_on"] = dependencies
            if subtask.eligible_actions:
                payload["eligible_actions"] = list(subtask.eligible_actions)
            child_markers.append(
                Marker(
                    id=child_id,
                    marker_type="task",
                    target=f"{marker.target}::{index}",
                    intensity=max(
                        self.intensity_floor,
                        float(marker.intensity) - self.child_intensity_offset,
                    ),
                    state="pending",
                    payload=payload,
                    created_by=agent_id,
                    created_at=now,
                    updated_by=agent_id,
                    updated_at=now,
                    history=["created"],
                )
            )

        return ActionResult(
            action_type=self.action_type,
            marker_updates=[updated_parent, *child_markers],
            consumed_tokens=consumed_tokens,
            cost_usd=cost_usd,
            metadata={"subtask_count": len(subtasks), "depth": depth},
        )

    def _parse_subtasks(
        self,
        *,
        raw_content: str,
        llm_client: Any | None,
    ) -> list[SubtaskSpec]:
        candidates = [raw_content]
        if llm_client is not None and hasattr(llm_client, "extract_code_block"):
            try:
                candidates.insert(0, str(llm_client.extract_code_block(raw_content)))
            except Exception:  # noqa: BLE001
                pass

        for candidate in candidates:
            text = candidate.strip()
            if not text:
                continue
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                continue
            if not isinstance(parsed, dict):
                continue
            try:
                validated = DecomposeOutput.model_validate(parsed)
            except Exception:  # noqa: BLE001
                continue
            if validated.subtasks:
                return list(validated.subtasks)
        return []

    def _fallback_subtasks(
        self, *, objective: str, desired_count: int | None
    ) -> list[SubtaskSpec]:
        parts = [
            segment.strip(" -\n\t")
            for segment in objective.replace(";", ".").split(".")
            if segment.strip(" -\n\t")
        ]
        if not parts:
            return [SubtaskSpec(title=objective or "Handle objective")]

        unique: list[str] = []
        for part in parts:
            if part not in unique:
                unique.append(part)

        rows = [SubtaskSpec(title=part) for part in unique]
        if desired_count is not None:
            return rows[: max(1, desired_count)]
        return rows if rows else [SubtaskSpec(title=objective or "Handle objective")]

    def _decomposition_depth(self, *, marker: Marker, environment: Any) -> int:
        depth = 0
        parent_id = marker.payload.get("parent_id")
        visited: set[str] = set()
        while isinstance(parent_id, str) and parent_id:
            if parent_id in visited:
                break
            visited.add(parent_id)
            depth += 1
            parent = environment.store.get_marker(parent_id)
            if parent is None:
                break
            parent_id = parent.payload.get("parent_id")
        return depth

    def _resolve_dependency_ids(
        self,
        *,
        depends_on_indices: list[int],
        child_ids: dict[int, str],
    ) -> list[str]:
        resolved: list[str] = []
        for raw_index in depends_on_indices:
            try:
                idx = int(raw_index)
            except (TypeError, ValueError):
                continue
            if idx in child_ids:
                resolved.append(child_ids[idx])
                continue
            one_based = idx - 1
            if one_based in child_ids:
                resolved.append(child_ids[one_based])
        return sorted(set(resolved))
