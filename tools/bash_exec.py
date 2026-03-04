"""Infrastructure tool for guarded bash command execution."""

from __future__ import annotations

import shlex
import subprocess
from typing import Any

from core.marker import Marker
from core.tool_registry import ActionResult, Tool


STATE_PROGRESS = {
    "pending": "active",
    "active": "completed",
    "completed": "verified",
    "verified": "terminal",
}


class BashExecTool(Tool):
    """Execute one command with timeout and allowlist checks."""

    action_type = "bash_exec"

    def __init__(self, *, config: dict[str, Any]) -> None:
        tools_cfg = dict(config.get("tools", {}))
        markers_cfg = dict(config.get("markers", {}))
        allowed = tools_cfg.get("allowed_commands", [])
        self.allowed_commands = {
            str(command).strip() for command in allowed if str(command).strip()
        }
        self.default_timeout_seconds = float(tools_cfg.get("bash_timeout_seconds", 120))
        self.intensity_step = float(markers_cfg.get("intensity_step_tool", 0.05))
        self.intensity_floor = float(markers_cfg.get("intensity_floor", 0.1))

    def is_eligible(self, marker: Marker) -> bool:
        raw = marker.payload.get("eligible_actions")
        if isinstance(raw, (list, tuple, set)) and len(raw) > 0:
            return self.action_type in {str(item) for item in raw}

        command = marker.payload.get("command")
        if isinstance(command, str):
            return bool(command.strip())
        if isinstance(command, (list, tuple)):
            return len(command) > 0
        return False

    async def execute(
        self,
        *,
        agent_id: str,
        marker: Marker,
        environment: Any,
        llm_client: Any | None = None,
    ) -> ActionResult:
        workspace = getattr(environment, "workspace", None)
        root = getattr(workspace, "root", None)
        if workspace is None or root is None:
            return ActionResult(
                action_type=self.action_type,
                metadata={"failed": True, "reason": "workspace_missing"},
            )

        command_parts = self._parse_command(marker.payload.get("command"))
        if not command_parts:
            return ActionResult(
                action_type=self.action_type,
                metadata={"failed": True, "reason": "missing_command"},
            )

        executable = command_parts[0]
        if executable not in self.allowed_commands:
            return ActionResult(
                action_type=self.action_type,
                metadata={
                    "failed": True,
                    "reason": f"command_not_allowed:{executable}",
                },
            )

        timeout_seconds = float(
            marker.payload.get("timeout_seconds", self.default_timeout_seconds)
        )
        try:
            process = subprocess.run(
                command_parts,
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return ActionResult(
                action_type=self.action_type,
                metadata={
                    "failed": True,
                    "reason": "timeout",
                    "stdout": str(exc.stdout or ""),
                    "stderr": str(exc.stderr or ""),
                },
            )
        except Exception as exc:  # noqa: BLE001
            return ActionResult(
                action_type=self.action_type,
                metadata={"failed": True, "reason": str(exc)},
            )

        updated = Marker.from_dict(marker.to_dict())
        payload = dict(updated.payload)
        payload["last_bash"] = {
            "command": command_parts,
            "returncode": int(process.returncode),
            "stdout": process.stdout,
            "stderr": process.stderr,
            "timed_out": False,
        }
        updated.payload = payload
        updated.state = STATE_PROGRESS.get(updated.state, updated.state)
        updated.intensity = max(
            self.intensity_floor,
            float(updated.intensity) - self.intensity_step,
        )

        return ActionResult(action_type=self.action_type, marker_updates=[updated])

    def _parse_command(self, raw_command: Any) -> list[str]:
        if isinstance(raw_command, str):
            return shlex.split(raw_command)
        if isinstance(raw_command, (list, tuple)):
            return [str(part) for part in raw_command if str(part)]
        return []
