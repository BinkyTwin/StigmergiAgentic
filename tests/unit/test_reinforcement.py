"""Unit tests for reinforcement helpers."""

from __future__ import annotations

from core.marker import Marker
from core.reinforcement import (
    penalize_on_failure,
    propagate_backward,
    reinforce_on_success,
)


def _marker(marker_id: str, intensity: float = 0.4, depends_on: list[str] | None = None) -> Marker:
    payload = {}
    if depends_on is not None:
        payload["depends_on"] = depends_on
    return Marker(
        id=marker_id,
        marker_type="task",
        target=marker_id,
        intensity=intensity,
        state="pending",
        payload=payload,
        created_by="seed",
        created_at="2026-03-04T10:00:00+00:00",
        updated_by="seed",
        updated_at="2026-03-04T10:00:00+00:00",
    )


def test_reinforce_on_success_increases_intensity() -> None:
    marker = _marker("a", intensity=0.4)
    updated = reinforce_on_success(marker, reinforcement_rate=0.2, quality_score=0.9, max_intensity=1.0)
    assert updated > marker.intensity


def test_reinforce_on_success_sigmoid_quality_behavior() -> None:
    marker = _marker("a", intensity=0.4)
    low_quality = reinforce_on_success(marker, reinforcement_rate=0.2, quality_score=0.1, max_intensity=1.0)
    high_quality = reinforce_on_success(marker, reinforcement_rate=0.2, quality_score=0.9, max_intensity=1.0)
    assert high_quality > low_quality


def test_propagate_backward_returns_ancestor_deltas() -> None:
    markers = [
        _marker("root"),
        _marker("mid", depends_on=["root"]),
        _marker("leaf", depends_on=["mid"]),
    ]
    updates = dict(propagate_backward("leaf", markers, propagation_factor=0.5))
    assert "mid" in updates
    assert "root" in updates
    assert updates["mid"] > updates["root"]


def test_reinforce_on_success_clamps_to_max_intensity() -> None:
    marker = _marker("a", intensity=0.95)
    updated = reinforce_on_success(marker, reinforcement_rate=0.5, quality_score=1.0, max_intensity=1.0)
    assert updated <= 1.0


def test_reinforce_on_success_zero_quality_still_safe_and_penalty_outputs_tuple() -> None:
    marker = _marker("a", intensity=0.5)
    updated = reinforce_on_success(marker, reinforcement_rate=0.2, quality_score=0.0, max_intensity=1.0)
    new_intensity, new_inhibition = penalize_on_failure(marker, penalty_rate=0.3)

    assert updated >= 0.0
    assert new_intensity < marker.intensity
    assert 0.0 <= new_inhibition <= 1.0
