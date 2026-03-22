"""Marker primitives for the generic stigmergic environment."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Mapping


class InvalidMarkerError(ValueError):
    """Raised when marker data is invalid."""


class InvalidTransitionError(ValueError):
    """Raised when a state transition is not allowed."""


class MarkerType(str, Enum):
    """Built-in marker types.

    The framework accepts dynamic marker types as plain strings; this enum exposes
    the common defaults used in Sprint 1.
    """

    TASK = "task"
    PROGRESS = "progress"
    QUALITY = "quality"
    LESSON = "lesson"


def utc_now_iso() -> str:
    """Return a UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(slots=True)
class Marker:
    """Generic environmental marker used for stigmergic coordination."""

    id: str
    marker_type: str
    target: str
    intensity: float
    state: str
    payload: dict[str, Any]

    created_by: str
    created_at: str
    updated_by: str
    updated_at: str
    last_active_at: str = ""

    lock_owner: str | None = None
    lock_tick: int | None = None
    inhibition: float = 0.0
    retry_count: int = 0
    history: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.id:
            raise InvalidMarkerError("marker id cannot be empty")
        if not self.marker_type:
            raise InvalidMarkerError("marker_type cannot be empty")
        if not self.target:
            raise InvalidMarkerError("target cannot be empty")
        if not isinstance(self.payload, dict):
            raise InvalidMarkerError("payload must be a dictionary")
        self.last_active_at = str(self.last_active_at or "")

        self.intensity = _validate_unit_interval(self.intensity, "intensity")
        self.inhibition = _validate_unit_interval(self.inhibition, "inhibition")

        if self.retry_count < 0:
            raise InvalidMarkerError("retry_count must be >= 0")
        if self.lock_tick is not None and self.lock_tick < 0:
            raise InvalidMarkerError("lock_tick must be >= 0 when present")

    def to_dict(self) -> dict[str, Any]:
        """Convert marker to a serializable dictionary."""
        return {
            "id": self.id,
            "marker_type": self.marker_type,
            "target": self.target,
            "intensity": self.intensity,
            "state": self.state,
            "payload": dict(self.payload),
            "created_by": self.created_by,
            "created_at": self.created_at,
            "updated_by": self.updated_by,
            "updated_at": self.updated_at,
            "last_active_at": self.last_active_at,
            "lock_owner": self.lock_owner,
            "lock_tick": self.lock_tick,
            "inhibition": self.inhibition,
            "retry_count": self.retry_count,
            "history": list(self.history),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Marker":
        """Instantiate marker from a dictionary payload."""
        return cls(
            id=str(data["id"]),
            marker_type=str(data["marker_type"]),
            target=str(data["target"]),
            intensity=float(data["intensity"]),
            state=str(data["state"]),
            payload=dict(data["payload"]),
            created_by=str(data["created_by"]),
            created_at=str(data["created_at"]),
            updated_by=str(data["updated_by"]),
            updated_at=str(data["updated_at"]),
            last_active_at=str(data.get("last_active_at", "") or ""),
            lock_owner=(
                None if data.get("lock_owner") is None else str(data.get("lock_owner"))
            ),
            lock_tick=(
                None if data.get("lock_tick") is None else int(data.get("lock_tick"))
            ),
            inhibition=float(data.get("inhibition", 0.0)),
            retry_count=int(data.get("retry_count", 0)),
            history=[str(item) for item in data.get("history", [])],
        )


def _validate_unit_interval(value: float, field_name: str) -> float:
    numeric = float(value)
    if not 0.0 <= numeric <= 1.0:
        raise InvalidMarkerError(f"{field_name} must be in [0.0, 1.0], got {numeric}")
    return numeric


class StateMachine:
    """Configurable finite-state machine for marker lifecycle transitions."""

    DEFAULT_TRANSITIONS: dict[str, set[str]] = {
        "pending": {"active", "skipped", "escalated"},
        "active": {"completed", "failed", "skipped", "escalated"},
        "failed": {"retry", "skipped", "escalated"},
        "retry": {"pending", "skipped", "escalated"},
        "completed": {"verified", "skipped", "escalated"},
        "verified": {"terminal", "skipped", "escalated"},
        "terminal": {"terminal", "skipped", "escalated"},
        "skipped": {"skipped"},
        "escalated": {"escalated"},
    }

    def __init__(self, transitions: Mapping[str, Iterable[str]] | None = None) -> None:
        if transitions is None:
            base = self.DEFAULT_TRANSITIONS
        else:
            base = {
                state: set(next_states)
                for state, next_states in transitions.items()
            }
            for terminal_state in ("skipped", "escalated"):
                base.setdefault(terminal_state, {terminal_state})

        self._transitions: dict[str, set[str]] = {
            state: set(next_states) for state, next_states in base.items()
        }

    def can_transition(self, from_state: str, to_state: str) -> bool:
        """Return True when transition from one state to another is legal."""
        allowed = self._transitions.get(from_state, set())
        return to_state in allowed

    def validate_transition(self, from_state: str, to_state: str) -> None:
        """Raise InvalidTransitionError if transition is illegal."""
        if not self.can_transition(from_state, to_state):
            raise InvalidTransitionError(
                f"Invalid transition: {from_state!r} -> {to_state!r}"
            )
