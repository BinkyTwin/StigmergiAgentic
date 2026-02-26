"""Infrastructure tool for controlled file writes inside workspace."""

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


class FileWriteTool(Tool):
    """Write or patch one workspace file using a structured payload."""

    action_type = "file_write"

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
        if workspace is None or not hasattr(workspace, "write_text"):
            return ActionResult(
                action_type=self.action_type,
                metadata={"failed": True, "reason": "workspace_missing"},
            )

        raw_write = marker.payload.get("write")
        if not isinstance(raw_write, dict):
            return ActionResult(
                action_type=self.action_type,
                metadata={"failed": True, "reason": "missing_write_spec"},
            )

        mode = str(raw_write.get("mode", "")).strip().lower()
        path = str(raw_write.get("path", marker.payload.get("path", ""))).strip()
        if not mode:
            return ActionResult(
                action_type=self.action_type,
                metadata={"failed": True, "reason": "missing_mode"},
            )
        if not path:
            return ActionResult(
                action_type=self.action_type,
                metadata={"failed": True, "reason": "missing_path"},
            )

        bytes_written = 0
        replacements = 0

        try:
            if mode == "overwrite":
                content = str(raw_write.get("content", ""))
                bytes_written = workspace.write_text(
                    path=path,
                    content=content,
                    mode="overwrite",
                    max_bytes=self.max_file_size_bytes,
                )
            elif mode == "append":
                content = str(raw_write.get("content", ""))
                bytes_written = workspace.write_text(
                    path=path,
                    content=content,
                    mode="append",
                    max_bytes=self.max_file_size_bytes,
                )
            elif mode == "replace_text":
                old = str(raw_write.get("old", ""))
                new = str(raw_write.get("new", ""))
                count = int(raw_write.get("count", -1))
                replacements, bytes_written = workspace.replace_text(
                    path=path,
                    old=old,
                    new=new,
                    count=count,
                    max_bytes=self.max_file_size_bytes,
                )
            else:
                return ActionResult(
                    action_type=self.action_type,
                    metadata={"failed": True, "reason": f"unsupported_mode:{mode}"},
                )
        except Exception as exc:  # noqa: BLE001
            return ActionResult(
                action_type=self.action_type,
                metadata={"failed": True, "reason": str(exc)},
            )

        updated = Marker.from_dict(marker.to_dict())
        payload = dict(updated.payload)
        payload["last_write"] = {
            "mode": mode,
            "path": path,
            "bytes_written": int(bytes_written),
            "replacements": int(replacements),
        }
        updated.payload = payload
        updated.state = STATE_PROGRESS.get(updated.state, updated.state)
        updated.intensity = max(0.1, float(updated.intensity) - 0.05)

        return ActionResult(action_type=self.action_type, marker_updates=[updated])
