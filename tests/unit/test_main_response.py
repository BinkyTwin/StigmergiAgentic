"""Unit tests for assistant response rendering in CLI entrypoint."""

from __future__ import annotations

from core.marker import Marker
from main import _build_assistant_response


def _marker(*, marker_id: str, payload: dict, state: str = "terminal") -> Marker:
    return Marker(
        id=marker_id,
        marker_type="task",
        target=marker_id,
        intensity=0.6,
        state=state,
        payload=payload,
        created_by="seed",
        created_at="2026-03-04T12:00:00+00:00",
        updated_by="seed",
        updated_at="2026-03-04T12:00:00+00:00",
        history=["created"],
    )


def test_build_assistant_response_includes_concrete_tool_outputs() -> None:
    objective_id = "obj-1"
    markers = [
        _marker(
            marker_id="obj-1::subtask::1",
            payload={
                "task": "Read README",
                "last_thought": {"analysis": "Collected project intent."},
                "last_read": {
                    "path": "README.md",
                    "content": "Project overview and setup instructions.",
                },
            },
        )
    ]

    rendered = _build_assistant_response(objective_id=objective_id, markers=markers)

    assert "Read README" in rendered
    assert "Collected project intent." in rendered
    assert "read `README.md`" in rendered


def test_build_assistant_response_prefers_subtasks_over_root_marker() -> None:
    objective_id = "obj-2"
    markers = [
        _marker(
            marker_id=objective_id,
            payload={"last_thought": {"analysis": "Root analysis"}},
        ),
        _marker(
            marker_id="obj-2::subtask::1",
            payload={
                "task": "Run tests",
                "last_bash": {"command": ["pytest"], "returncode": 0},
            },
        ),
    ]

    rendered = _build_assistant_response(objective_id=objective_id, markers=markers)

    assert "Run tests" in rendered
    assert "bash `pytest`" in rendered
    assert "Root analysis" not in rendered
