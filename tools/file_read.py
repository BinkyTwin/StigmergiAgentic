"""Infrastructure tool for file reads inside the assistant workspace."""

from __future__ import annotations

from typing import Any

from core.marker import Marker
from core.tool_registry import ActionResult, Tool


STATE_PROGRESS = {
    "pending": "active",
    "active": "completed",
    "completed": "verified",
    "verified": "terminal",
}


class FileReadTool(Tool):
    """Read one file from workspace and store content in marker payload."""

    action_type = "file_read"

    def __init__(self, *, config: dict[str, Any]) -> None:
        tools_cfg = dict(config.get("tools", {}))
        self.max_file_size_bytes = int(tools_cfg.get("max_file_size_bytes", 1_048_576))

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
        workspace = getattr(environment, "workspace", None)
        if workspace is None or not hasattr(workspace, "read_text"):
            return ActionResult(
                action_type=self.action_type,
                metadata={"failed": True, "reason": "workspace_missing"},
            )

        path = str(marker.payload.get("path", "")).strip()
        if not path:
            return ActionResult(
                action_type=self.action_type,
                metadata={"failed": True, "reason": "missing_path"},
            )

        try:
            content = workspace.read_text(
                path=path,
                max_bytes=self.max_file_size_bytes,
            )
        except Exception as exc:  # noqa: BLE001
            return ActionResult(
                action_type=self.action_type,
                metadata={"failed": True, "reason": str(exc)},
            )

        updated = Marker.from_dict(marker.to_dict())
        payload = dict(updated.payload)
        payload["last_read"] = {
            "path": path,
            "content": content,
            "size_bytes": len(content.encode("utf-8")),
        }
        updated.payload = payload
        updated.state = STATE_PROGRESS.get(updated.state, updated.state)
        updated.intensity = max(0.1, float(updated.intensity) - 0.05)

        return ActionResult(action_type=self.action_type, marker_updates=[updated])
