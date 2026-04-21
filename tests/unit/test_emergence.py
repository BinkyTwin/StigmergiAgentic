"""Unit tests for emergence metrics."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.emergence import (
    clamp_cross_run_adaptations,
    compute_adaptations,
    compute_emergence_metrics,
    compute_protocol_score,
)
from core.orchestrator import TickRow


def _row(
    *,
    tick: int,
    decisions: dict[str, str | None],
    lock_conflicts: int = 0,
    active_agents: int = 0,
    pressures: dict[str, float] | None = None,
    terminal_progress: float = 0.0,
) -> TickRow:
    actions_by_type: dict[str, int] = {}
    for action in decisions.values():
        if action is None:
            continue
        actions_by_type[action] = actions_by_type.get(action, 0) + 1
    return TickRow(
        tick=tick,
        decisions=decisions,
        executed_actions=sum(actions_by_type.values()),
        lock_conflicts=lock_conflicts,
        active_agents=active_agents,
        pressures=pressures or {},
        actions_by_type=actions_by_type,
        terminal_progress=terminal_progress,
        maintenance={},
    )


def test_specialization_entropy_is_normalized() -> None:
    rows = [
        _row(tick=0, decisions={"a1": "think", "a2": "read"}),
        _row(tick=1, decisions={"a1": "read", "a2": "read"}),
        _row(tick=2, decisions={"a1": "think", "a2": "read"}),
    ]
    metrics = compute_emergence_metrics(rows, total_agents=2)
    assert 0.0 < metrics["specialization_entropy"] <= 1.0


def test_colony_specialization_increases_with_stable_roles() -> None:
    rows = [
        _row(tick=0, decisions={"a1": "think", "a2": "read"}),
        _row(tick=1, decisions={"a1": "think", "a2": "read"}),
        _row(tick=2, decisions={"a1": "think", "a2": "read"}),
    ]
    metrics = compute_emergence_metrics(rows, total_agents=2)
    assert metrics["colony_specialization"] == pytest.approx(1.0)


def test_collaboration_density_uses_audit_log(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit_log.jsonl"
    events = [
        {"marker_id": "m1", "agent_id": "agent-1"},
        {"marker_id": "m1", "agent_id": "agent-2"},
        {"marker_id": "m2", "agent_id": "agent-1"},
    ]
    with audit_path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")

    metrics = compute_emergence_metrics(
        [_row(tick=0, decisions={"a1": "think"})],
        total_agents=1,
        audit_log_path=audit_path,
    )
    assert metrics["collaboration_density"] == pytest.approx(0.5)


def test_action_switching_rate_counts_transitions() -> None:
    rows = [
        _row(tick=0, decisions={"a1": "think"}),
        _row(tick=1, decisions={"a1": "read"}),
        _row(tick=2, decisions={"a1": "read"}),
        _row(tick=3, decisions={"a1": "bash"}),
    ]
    metrics = compute_emergence_metrics(rows, total_agents=1)
    assert metrics["action_switching_rate"] == pytest.approx(2.0 / 3.0)


def test_convergence_tick_detects_first_threshold_crossing() -> None:
    rows = [
        _row(tick=0, decisions={"a1": "think"}, terminal_progress=0.2),
        _row(tick=1, decisions={"a1": "read"}, terminal_progress=0.8),
        _row(tick=2, decisions={"a1": "bash"}, terminal_progress=1.0),
    ]
    metrics = compute_emergence_metrics(rows, total_agents=1)
    assert metrics["convergence_tick"] == 1


def test_lock_contention_rate_uses_decision_attempts() -> None:
    rows = [
        _row(
            tick=0,
            decisions={"a1": "think", "a2": "read", "a3": None},
            lock_conflicts=1,
        ),
        _row(
            tick=1,
            decisions={"a1": "think", "a2": None, "a3": None},
            lock_conflicts=0,
        ),
    ]
    metrics = compute_emergence_metrics(rows, total_agents=3)
    assert metrics["lock_contention_rate"] == pytest.approx(1.0 / 3.0)


def test_parallel_utilization_averages_active_agents() -> None:
    rows = [
        _row(tick=0, decisions={"a1": "think"}, active_agents=1),
        _row(tick=1, decisions={"a1": "think"}, active_agents=3),
    ]
    metrics = compute_emergence_metrics(rows, total_agents=4)
    assert metrics["parallel_utilization"] == pytest.approx(0.5)


def test_pressure_entropy_computes_distribution_entropy() -> None:
    rows = [
        _row(
            tick=0,
            decisions={"a1": "think"},
            pressures={"think": 0.9, "read": 0.1},
        ),
        _row(
            tick=1,
            decisions={"a1": "read"},
            pressures={"think": 0.1, "read": 0.9},
        ),
    ]
    metrics = compute_emergence_metrics(rows, total_agents=1)
    assert metrics["pressure_entropy"] == pytest.approx(1.0)


def test_compute_adaptations_adjusts_exploration_and_temperature(
    config_dict: dict,
) -> None:
    config = {
        **config_dict,
        "emergence": {
            **config_dict["emergence"],
            "feedback_loop": {
                "enabled": True,
                "interval_ticks": 1,
                "max_adaptation_delta": 0.2,
            },
        },
    }
    metrics = {
        "colony_specialization": 0.1,
        "lock_contention_rate": 0.0,
        "parallel_utilization": 0.5,
        "pressure_entropy": 0.1,
    }

    adaptations = compute_adaptations(metrics, config)
    assert "agents.local_sensing.affinity_exploration_rate" in adaptations
    assert "agents.selection_temperature" in adaptations


def test_clamp_cross_run_adaptations_uses_fixed_baseline() -> None:
    baseline = {
        "agents": {"selection_temperature": 0.1},
        "markers": {"inhibition_increment": 0.5},
    }
    derived = {
        "agents": {"selection_temperature": 0.24},
        "markers": {"inhibition_increment": 0.62},
    }

    clamped = clamp_cross_run_adaptations(
        {
            "agents.selection_temperature": 0.35,
            "markers.inhibition_increment": 0.8,
        },
        baseline,
        max_total_delta=0.15,
    )

    assert clamped["agents.selection_temperature"] == pytest.approx(0.25)
    assert clamped["markers.inhibition_increment"] == pytest.approx(0.65)
    assert derived["agents"]["selection_temperature"] == pytest.approx(0.24)


def test_compute_protocol_score_prioritizes_pass_rate() -> None:
    lower_pass = compute_protocol_score(
        {
            "final_pass_rate": 0.70,
            "hard_constraint_micro": 1.0,
            "delivery_rate": 1.0,
            "convergence_tick": 1,
        }
    )
    higher_pass = compute_protocol_score(
        {
            "final_pass_rate": 0.71,
            "hard_constraint_micro": 0.0,
            "delivery_rate": 0.0,
            "convergence_tick": 999,
        }
    )

    assert higher_pass > lower_pass
