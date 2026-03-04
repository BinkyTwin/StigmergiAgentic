"""Infrastructure tool that decomposes one objective into sub-markers."""

from __future__ import annotations

import json
from typing import Any

from core.marker import Marker, utc_now_iso
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
        self.intensity_step = float(markers_cfg.get("intensity_step_decompose", 0.1))
        self.child_intensity_offset = float(
            markers_cfg.get("child_intensity_offset", 0.2)
        )
        self.intensity_floor = float(markers_cfg.get("intensity_floor", 0.1))

    def is_eligible(self, marker: Marker) -> bool:
        raw = marker.payload.get("eligible_actions")
        if isinstance(raw, (list, tuple, set)) and len(raw) > 0:
            return self.action_type in {str(item) for item in raw}

        if bool(marker.payload.get("decomposed")):
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

        subtasks: list[str] = []
        consumed_tokens = 0
        cost_usd = 0.0

        if llm_client is not None and hasattr(llm_client, "call"):
            prompt = (
                "Decompose the following objective into concrete executable subtasks.\n"
                "Use as many or as few subtasks as the objective requires -- "
                "do not force a fixed number.\n"
                "Return strict JSON: "
                '{"subtasks":[{"title":"..."}]}\n'
                f"Objective: {objective}"
            )
            if desired_count is not None:
                prompt += f"\nSuggested target: around {desired_count} subtasks"
            try:
                response = llm_client.call(
                    prompt=prompt,
                    system=SYSTEM_STIGMERGIC_AGENT_PROMPT,
                )
                consumed_tokens = int(getattr(response, "tokens_used", 0))
                cost_usd = float(getattr(response, "cost_usd", 0.0))
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
        for index, subtask in enumerate(subtasks, start=1):
            child_markers.append(
                Marker(
                    id=f"{marker.id}::subtask::{index}",
                    marker_type="task",
                    target=f"{marker.target}::{index}",
                    intensity=max(
                        self.intensity_floor,
                        float(marker.intensity) - self.child_intensity_offset,
                    ),
                    state="pending",
                    payload={
                        "task": subtask,
                        "objective": objective,
                        "parent_id": marker.id,
                    },
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
            metadata={"subtask_count": len(subtasks)},
        )

    def _parse_subtasks(self, *, raw_content: str, llm_client: Any | None) -> list[str]:
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
            rows = parsed.get("subtasks", []) if isinstance(parsed, dict) else []
            if not isinstance(rows, list):
                continue
            subtasks: list[str] = []
            for row in rows:
                if isinstance(row, dict):
                    title = str(row.get("title", "")).strip()
                else:
                    title = str(row).strip()
                if title:
                    subtasks.append(title)
            if subtasks:
                return subtasks
        return []

    def _fallback_subtasks(
        self, *, objective: str, desired_count: int | None
    ) -> list[str]:
        parts = [
            segment.strip(" -\n\t")
            for segment in objective.replace(";", ".").split(".")
            if segment.strip(" -\n\t")
        ]
        if not parts:
            return [objective or "Handle objective"]

        unique: list[str] = []
        for part in parts:
            if part not in unique:
                unique.append(part)
        if desired_count is not None:
            return unique[: max(1, desired_count)]
        return unique if unique else [objective or "Handle objective"]
