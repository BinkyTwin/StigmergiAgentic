"""Integration tests for cross-run protocol persistence (Sprint 9 T2)."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from core.marker_store import MarkerStore

from main import (
    _build_protocol_namespace,
    _maybe_apply_cross_run_protocol,
    _persist_protocol,
)


@dataclass
class _FakeResult:
    emergence_summary: dict[str, Any] = field(default_factory=dict)
    stop_reason: str = "all_terminal"
    total_ticks: int = 3


def _build_cross_run_config(base: dict) -> dict:
    cfg = copy.deepcopy(base)
    cfg["protocol"] = dict(cfg.get("protocol", {}))
    cfg["protocol"]["enabled"] = True
    cfg["protocol"]["read_only"] = False
    cfg["emergence"] = dict(cfg.get("emergence", {}))
    cfg["emergence"]["cross_run"] = dict(
        cfg.get("emergence", {}).get("cross_run", {})
    )
    cfg["emergence"]["cross_run"]["enabled"] = True
    cfg["emergence"]["cross_run"]["read_only"] = False
    cfg["emergence"]["cross_run"]["max_total_delta"] = 0.15
    # Enable feedback loop so compute_adaptations produces adaptations.
    cfg["emergence"]["feedback_loop"] = dict(
        cfg.get("emergence", {}).get("feedback_loop", {})
    )
    cfg["emergence"]["feedback_loop"]["enabled"] = True
    cfg["emergence"]["feedback_loop"]["max_adaptation_delta"] = 0.2
    return cfg


def test_second_run_applies_clamped_adaptations_from_best_slot(
    tmp_path,
    config_dict: dict,
) -> None:
    config_run1 = _build_cross_run_config(config_dict)
    config_run1["llm"]["model"] = "model-A"
    config_run1["pressures"] = dict(config_run1.get("pressures", {}))
    config_run1["pressures"]["alpha"] = 1.0
    config_run1["pressures"]["beta"] = 2.0
    config_run1["agents"] = dict(config_run1["agents"])
    config_run1["agents"]["selection_temperature"] = 0.1

    namespace = _build_protocol_namespace(config_run1, "travelplanner")
    protocol_store = MarkerStore(db_path=tmp_path / "protocols.db")

    # Run 1 — no cross-run artefact exists yet; applying should be a no-op.
    applied_before = _maybe_apply_cross_run_protocol(
        config=config_run1,
        protocol_store=protocol_store,
        namespace=namespace,
    )
    assert applied_before is False

    # Simulate low parallel utilization to push selection_temperature lower.
    result_run1 = _FakeResult(
        emergence_summary={
            "colony_specialization": 0.5,
            "lock_contention_rate": 0.1,
            "parallel_utilization": 0.1,
            "pressure_entropy": 0.6,
        }
    )
    evaluation_run1 = {
        "final_pass_rate": 0.0,
        "hard_constraint_micro": 0.0,
        "delivery_rate": 0.0,
        "convergence_tick": 10.0,
    }
    _persist_protocol(
        result=result_run1,
        evaluation=evaluation_run1,
        config=config_run1,
        protocol_store=protocol_store,
        namespace=namespace,
        session_id="sess-1",
    )

    baseline = protocol_store.load_protocol_marker(slot="baseline", namespace=namespace)
    latest = protocol_store.load_protocol_marker(slot="latest", namespace=namespace)
    best = protocol_store.load_protocol_marker(slot="best", namespace=namespace)
    assert baseline is not None
    assert latest is not None
    assert best is not None
    assert best["session_id"] == "sess-1"

    # Run 2 — cross-run adaptations are applied from the persisted best slot.
    config_run2 = _build_cross_run_config(config_dict)
    config_run2["llm"]["model"] = "model-A"
    config_run2["pressures"] = dict(config_run2.get("pressures", {}))
    config_run2["pressures"]["alpha"] = 1.0
    config_run2["pressures"]["beta"] = 2.0
    config_run2["agents"] = dict(config_run2["agents"])
    config_run2["agents"]["selection_temperature"] = 0.1

    original_temp = config_run2["agents"]["selection_temperature"]
    applied = _maybe_apply_cross_run_protocol(
        config=config_run2,
        protocol_store=protocol_store,
        namespace=namespace,
    )
    assert applied is True
    # Temperature should have been lowered by the clamp + feedback adaptation.
    assert (
        config_run2["agents"]["selection_temperature"] != original_temp
        or config_run2["agents"].get("local_sensing", {}).get(
            "affinity_exploration_rate"
        )
        != config_dict["agents"]["local_sensing"]["affinity_exploration_rate"]
    )

    # Run 2 with a weaker run — score must not overwrite best.
    result_run2 = _FakeResult(
        emergence_summary={
            "colony_specialization": 0.5,
            "lock_contention_rate": 0.1,
            "parallel_utilization": 0.1,
            "pressure_entropy": 0.6,
        }
    )
    evaluation_weak = {
        "final_pass_rate": 0.0,
        "hard_constraint_micro": 0.0,
        "delivery_rate": 0.0,
        "convergence_tick": 50.0,  # worse than run 1
    }
    _persist_protocol(
        result=result_run2,
        evaluation=evaluation_weak,
        config=config_run2,
        protocol_store=protocol_store,
        namespace=namespace,
        session_id="sess-2",
    )

    best_after = protocol_store.load_protocol_marker(slot="best", namespace=namespace)
    latest_after = protocol_store.load_protocol_marker(
        slot="latest", namespace=namespace
    )
    assert best_after is not None and latest_after is not None
    assert best_after["session_id"] == "sess-1"  # unchanged
    assert latest_after["session_id"] == "sess-2"


def test_baseline_is_never_overwritten(tmp_path, config_dict: dict) -> None:
    config = _build_cross_run_config(config_dict)
    namespace = _build_protocol_namespace(config, "assistant")
    protocol_store = MarkerStore(db_path=tmp_path / "protocols.db")

    result1 = _FakeResult(emergence_summary={"parallel_utilization": 0.1})
    evaluation1 = {"final_pass_rate": 0.5, "convergence_tick": 10.0}
    _persist_protocol(
        result=result1,
        evaluation=evaluation1,
        config=config,
        protocol_store=protocol_store,
        namespace=namespace,
        session_id="first",
    )
    baseline_first = protocol_store.load_protocol_marker(
        slot="baseline", namespace=namespace
    )
    assert baseline_first is not None
    assert baseline_first["session_id"] == "first"

    result2 = _FakeResult(emergence_summary={"parallel_utilization": 0.2})
    evaluation2 = {"final_pass_rate": 1.0, "convergence_tick": 5.0}
    _persist_protocol(
        result=result2,
        evaluation=evaluation2,
        config=config,
        protocol_store=protocol_store,
        namespace=namespace,
        session_id="second",
    )
    baseline_second = protocol_store.load_protocol_marker(
        slot="baseline", namespace=namespace
    )
    assert baseline_second is not None
    assert baseline_second["session_id"] == "first"  # unchanged
