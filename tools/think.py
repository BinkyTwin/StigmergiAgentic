"""Infrastructure tool for generic reasoning over marker context."""

from __future__ import annotations

import json
from typing import Any

from core.marker import Marker
from core.schemas import ThinkOutput
from core.tool_registry import ActionResult, Tool
from llm.prompts import (
    SYSTEM_STIGMERGIC_AGENT_PROMPT,
    build_action_prompt,
    build_system_prompt,
)


STATE_PROGRESS = {
    "pending": "active",
    "completed": "verified",
    "verified": "terminal",
}


class ThinkTool(Tool):
    """Produce one reasoning step and persist it in marker payload."""

    action_type = "think"

    def __init__(
        self,
        *,
        config: dict[str, Any],
        available_hint_tools: list[str] | None = None,
    ) -> None:
        self.config = config
        markers_cfg = dict(config.get("markers", {}))
        self.intensity_step = float(markers_cfg.get("intensity_step_think", 0.1))
        self.intensity_floor = float(markers_cfg.get("intensity_floor", 0.1))
        self.available_hint_tools = list(
            available_hint_tools
            or ["file_read", "file_write", "bash_exec", "web_search"]
        )

    def is_eligible(self, marker: Marker) -> bool:
        raw = marker.payload.get("eligible_actions")
        if isinstance(raw, (list, tuple, set)) and len(raw) > 0:
            return self.action_type in {str(item) for item in raw}
        if marker.state != "active":
            return True
        is_root_marker = bool(marker.payload.get("decomposed")) and not isinstance(
            marker.payload.get("parent_id"), str
        )
        return is_root_marker

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
        workspace_context = self._workspace_context(environment)
        if not prompt:
            prompt = build_action_prompt(
                action_type=self.action_type,
                target=marker.target,
                objective=objective,
                marker_payload=marker.payload,
                available_tools=self.available_hint_tools,
                workspace_context=workspace_context,
            )

        analysis = ""
        tool_hints: dict[str, Any] = {}
        consumed_tokens = 0
        cost_usd = 0.0
        model = "fallback"
        system_prompt = SYSTEM_STIGMERGIC_AGENT_PROMPT
        if workspace_context:
            system_prompt = build_system_prompt(
                workspace_context=workspace_context,
                available_tools=self.available_hint_tools,
            )

        if llm_client is not None and (
            hasattr(llm_client, "acall") or hasattr(llm_client, "call")
        ):
            try:
                response = None
                if hasattr(llm_client, "acall"):
                    response = await llm_client.acall(
                        prompt=prompt,
                        system=system_prompt,
                        response_schema=ThinkOutput,
                    )
                elif hasattr(llm_client, "call"):
                    response = llm_client.call(
                        prompt=prompt,
                        system=system_prompt,
                    )

                if response is None:
                    raise RuntimeError("llm_response_missing")

                raw_content = str(getattr(response, "content", "")).strip()
                parsed = getattr(response, "parsed", None)
                if isinstance(parsed, ThinkOutput):
                    analysis = parsed.analysis.strip() or raw_content
                    tool_hints = self._collect_tool_hints(parsed.model_dump())
                else:
                    analysis, tool_hints = self._extract_analysis_and_hints(
                        raw_content=raw_content,
                        llm_client=llm_client,
                    )
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
        payload.update(tool_hints)
        updated.payload = payload
        if updated.state == "active":
            is_root_marker = bool(updated.payload.get("decomposed")) and not isinstance(
                updated.payload.get("parent_id"), str
            )
            if is_root_marker:
                updated.state = "completed"
        else:
            updated.state = STATE_PROGRESS.get(updated.state, updated.state)
        updated.intensity = max(
            self.intensity_floor,
            float(updated.intensity) - self.intensity_step,
        )

        return ActionResult(
            action_type=self.action_type,
            marker_updates=[updated],
            consumed_tokens=consumed_tokens,
            cost_usd=cost_usd,
        )

    def _workspace_context(self, environment: Any) -> str:
        workspace = getattr(environment, "workspace", None)
        if workspace is None:
            return ""
        if not hasattr(workspace, "get_context_summary"):
            return ""
        try:
            return str(workspace.get_context_summary()).strip()
        except Exception:  # noqa: BLE001
            return ""

    def _extract_analysis_and_hints(
        self,
        *,
        raw_content: str,
        llm_client: Any | None,
    ) -> tuple[str, dict[str, Any]]:
        candidates = [raw_content]
        if llm_client is not None and hasattr(llm_client, "extract_code_block"):
            try:
                candidates.insert(
                    0, str(llm_client.extract_code_block(raw_content)).strip()
                )
            except Exception:  # noqa: BLE001
                pass

        for candidate in candidates:
            text = str(candidate).strip()
            if not text:
                continue
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                continue
            if not isinstance(parsed, dict):
                continue

            analysis = str(parsed.get("analysis", "")).strip() or raw_content
            tool_hints = self._collect_tool_hints(parsed)
            return analysis, tool_hints

        return raw_content, {}

    def _collect_tool_hints(self, parsed: dict[str, Any]) -> dict[str, Any]:
        hints: dict[str, Any] = {}
        for key in ("path", "command", "query"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                hints[key] = value.strip()

        write_value = parsed.get("write")
        if isinstance(write_value, dict):
            hints["write"] = write_value

        return hints
