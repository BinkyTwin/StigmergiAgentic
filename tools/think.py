"""Infrastructure tool for generic reasoning over marker context."""

from __future__ import annotations

from typing import Any

from core.marker import Marker
from core.tool_registry import ActionResult, Tool
from llm.prompts import SYSTEM_STIGMERGIC_AGENT_PROMPT, build_action_prompt


STATE_PROGRESS = {
    "pending": "active",
    "active": "completed",
    "completed": "verified",
    "verified": "terminal",
}


class ThinkTool(Tool):
    """Produce one reasoning step and persist it in marker payload."""

    action_type = "think"

    def __init__(self, *, config: dict[str, Any]) -> None:
        self.config = config

    def is_eligible(self, marker: Marker) -> bool:
        raw = marker.payload.get("eligible_actions", [])
        if not isinstance(raw, (list, tuple, set)):
            return False
        return self.action_type in {str(item) for item in raw}

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
        )
        prompt = str(marker.payload.get("prompt", "")).strip()
        if not prompt:
            prompt = build_action_prompt(
                action_type=self.action_type,
                target=marker.target,
                objective=objective,
                marker_payload=marker.payload,
            )

        analysis = ""
        consumed_tokens = 0
        cost_usd = 0.0
        model = "fallback"

        if llm_client is not None and hasattr(llm_client, "call"):
            try:
                response = llm_client.call(prompt=prompt, system=SYSTEM_STIGMERGIC_AGENT_PROMPT)
                analysis = str(getattr(response, "content", "")).strip()
                consumed_tokens = int(getattr(response, "tokens_used", 0))
                cost_usd = float(getattr(response, "cost_usd", 0.0))
                model = str(getattr(response, "model", "unknown"))
            except Exception:  # noqa: BLE001
                analysis = f"Fallback thought for target={marker.target}"
        else:
            analysis = f"Fallback thought for target={marker.target}"

        updated = Marker.from_dict(marker.to_dict())
        payload = dict(updated.payload)
        payload["last_thought"] = {
            "analysis": analysis,
            "model": model,
        }
        updated.payload = payload
        updated.state = STATE_PROGRESS.get(updated.state, updated.state)
        updated.intensity = max(0.1, float(updated.intensity) - 0.1)

        return ActionResult(
            action_type=self.action_type,
            marker_updates=[updated],
            consumed_tokens=consumed_tokens,
            cost_usd=cost_usd,
        )
