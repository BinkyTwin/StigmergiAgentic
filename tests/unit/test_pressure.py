"""Unit tests for pressure computation and action selection."""

from __future__ import annotations

import random

import pytest

from core.marker import Marker
from core.pressure import compute_pressures, select_action


def _make_marker(marker_id: str, **overrides: object) -> Marker:
    payload = {
        "id": marker_id,
        "marker_type": "task",
        "target": f"{marker_id}.py",
        "intensity": 1.0,
        "state": "pending",
        "payload": {"eligible_actions": ["increment", "check"]},
        "created_by": "agent-1",
        "created_at": "2026-02-26T12:00:00+00:00",
        "updated_by": "agent-1",
        "updated_at": "2026-02-26T12:00:00+00:00",
        "inhibition": 0.0,
        "retry_count": 0,
        "history": ["created"],
    }
    payload.update(overrides)
    return Marker(**payload)


def test_compute_pressures_returns_zero_when_no_eligible_markers() -> None:
    marker = _make_marker("m1", inhibition=0.9)
    pressures = compute_pressures(
        markers=[marker],
        action_types=["increment", "check"],
        inhibition_threshold=0.5,
    )
    assert pressures == {"increment": 0.0, "check": 0.0}


def test_compute_pressures_applies_action_weights() -> None:
    marker = _make_marker("m1", payload={"eligible_actions": ["increment", "check"]})
    pressures = compute_pressures(
        markers=[marker],
        action_types=["increment", "check"],
        weights={"increment": 2.0, "check": 1.0},
    )
    assert pressures["increment"] == pytest.approx(2.0 / 3.0)
    assert pressures["check"] == pytest.approx(1.0 / 3.0)


def test_compute_pressures_filters_markers_by_inhibition() -> None:
    allowed = _make_marker("m1", inhibition=0.1)
    blocked = _make_marker("m2", inhibition=0.8)
    pressures = compute_pressures(
        markers=[allowed, blocked],
        action_types=["increment", "check"],
        inhibition_threshold=0.5,
    )
    assert pressures["increment"] == pytest.approx(0.5)
    assert pressures["check"] == pytest.approx(0.5)


def test_compute_pressures_normalizes_distribution() -> None:
    m1 = _make_marker("m1", intensity=0.7, payload={"eligible_actions": ["increment"]})
    m2 = _make_marker("m2", intensity=0.3, payload={"eligible_actions": ["check"]})
    pressures = compute_pressures(
        markers=[m1, m2],
        action_types=["increment", "check"],
    )
    assert sum(pressures.values()) == pytest.approx(1.0)


def test_compute_pressures_treats_empty_eligible_actions_as_all() -> None:
    marker = _make_marker("m1", intensity=1.0, payload={"eligible_actions": []})
    pressures = compute_pressures(
        markers=[marker],
        action_types=["increment", "check"],
    )
    assert pressures["increment"] == pytest.approx(0.5)
    assert pressures["check"] == pytest.approx(0.5)


def test_select_action_returns_none_for_zero_distribution() -> None:
    assert select_action({"increment": 0.0, "check": 0.0}, temperature=0.1) is None


def test_select_action_is_deterministic_with_seeded_rng() -> None:
    seeded_a = random.Random(42)
    seeded_b = random.Random(42)
    pressures = {"increment": 0.7, "check": 0.3}

    first = select_action(pressures, temperature=0.2, rng=seeded_a)
    second = select_action(pressures, temperature=0.2, rng=seeded_b)
    greedy = select_action(pressures, temperature=0.0)

    assert first == second
    assert first in {"increment", "check"}
    assert greedy == "increment"
