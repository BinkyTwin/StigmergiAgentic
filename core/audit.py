"""Append-only audit logging for marker mutations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class AuditEvent:
    """Single immutable audit event."""

    timestamp: str
    agent_id: str
    action: str
    marker_id: str
    marker_type: str
    target: str
    before: dict[str, Any]
    after: dict[str, Any]
    tick: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert event to JSON-serializable dictionary."""
        payload: dict[str, Any] = {
            "timestamp": self.timestamp,
            "agent_id": self.agent_id,
            "action": self.action,
            "marker_id": self.marker_id,
            "marker_type": self.marker_type,
            "target": self.target,
            "before": self.before,
            "after": self.after,
        }
        if self.tick is not None:
            payload["tick"] = self.tick
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditEvent":
        """Instantiate AuditEvent from dictionary data."""
        return cls(
            timestamp=str(data["timestamp"]),
            agent_id=str(data["agent_id"]),
            action=str(data["action"]),
            marker_id=str(data["marker_id"]),
            marker_type=str(data["marker_type"]),
            target=str(data["target"]),
            before=dict(data.get("before", {})),
            after=dict(data.get("after", {})),
            tick=(None if "tick" not in data else int(data["tick"])),
        )


class AuditLog:
    """Append-only JSONL audit file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def append(self, event: AuditEvent) -> None:
        """Append one event to the audit trail."""
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")

    def read_all(self) -> list[AuditEvent]:
        """Read all audit events in insertion order."""
        if not self.path.exists():
            return []

        events: list[AuditEvent] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                data = json.loads(raw)
                events.append(AuditEvent.from_dict(data))
        return events


def utc_timestamp() -> str:
    """Return UTC timestamp in ISO-8601 format with second precision."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
