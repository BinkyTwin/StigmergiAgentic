"""Unit tests for marker model and state machine."""

from __future__ import annotations

import pytest

from core.marker import (
    InvalidMarkerError,
    InvalidTransitionError,
    Marker,
    StateMachine,
)


def _make_marker(**overrides: object) -> Marker:
    payload = {
        "id": "m-1",
        "marker_type": "task",
        "target": "file.py",
        "intensity": 0.9,
        "state": "pending",
        "payload": {"detail": "x"},
        "created_by": "agent-1",
        "created_at": "2026-02-26T12:00:00+00:00",
        "updated_by": "agent-1",
        "updated_at": "2026-02-26T12:00:00+00:00",
        "inhibition": 0.1,
        "retry_count": 0,
        "history": ["created"],
    }
    payload.update(overrides)
    return Marker(**payload)


def test_marker_creation_accepts_valid_values() -> None:
    marker = _make_marker()
    assert marker.id == "m-1"
    assert marker.intensity == 0.9
    assert marker.inhibition == 0.1


def test_marker_rejects_invalid_intensity() -> None:
    with pytest.raises(InvalidMarkerError):
        _make_marker(intensity=1.2)


def test_marker_rejects_negative_retry_count() -> None:
    with pytest.raises(InvalidMarkerError):
        _make_marker(retry_count=-1)


def test_state_machine_accepts_default_transition() -> None:
    machine = StateMachine()
    machine.validate_transition("pending", "active")


def test_state_machine_rejects_invalid_transition() -> None:
    machine = StateMachine()
    with pytest.raises(InvalidTransitionError):
        machine.validate_transition("pending", "verified")
