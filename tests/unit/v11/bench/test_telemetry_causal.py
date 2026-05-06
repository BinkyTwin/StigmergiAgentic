"""V11 causal telemetry reconstruction tests."""

from __future__ import annotations

from core_v10.event_log import JsonlEventLog
from scripts.bench.telemetry import (
    AFFORDANCE_CONSUMED_EVENT,
    AFFORDANCE_CREATED_EVENT,
    DECISION_INFLUENCED_EVENT,
    SIGNAL_READ_EVENT,
    TRAJECTORY_DIVERGED_EVENT,
    WORKER_ACTIVATED_EVENT,
    WORKER_SELECTED_EVENT,
    build_summary,
)


def test_summary_reconstructs_v11_causal_counts(tmp_path) -> None:
    log = JsonlEventLog(tmp_path / "events.jsonl")
    log.append(
        run_id="r1",
        instance_id="i1",
        event_type="signal.emitted",
        actor="medium",
        payload={
            "record": {
                "signal_id": "sig-a",
                "kind": "inhibit",
                "target": "failure_type:answer_mismatch",
                "intensity": 0.8,
            }
        },
    )
    log.append(
        run_id="r1",
        instance_id="i1",
        event_type=AFFORDANCE_CREATED_EVENT,
        actor="medium",
        payload={"affordance": {"affordance_id": "aff-a"}},
    )
    log.append(
        run_id="r1",
        instance_id="i1",
        event_type=SIGNAL_READ_EVENT,
        actor="scheduler",
        payload={"signals_seen": ["sig-a"], "affordances_seen": ["aff-a"]},
    )
    log.append(
        run_id="r1",
        instance_id="i1",
        event_type=WORKER_SELECTED_EVENT,
        actor="scheduler",
        payload={"worker_id": "exact_edit_guard"},
    )
    log.append(
        run_id="r1",
        instance_id="i1",
        event_type=WORKER_ACTIVATED_EVENT,
        actor="scheduler",
        payload={"worker_id": "exact_edit_guard"},
    )
    log.append(
        run_id="r1",
        instance_id="i1",
        event_type=AFFORDANCE_CONSUMED_EVENT,
        actor="exact_edit_guard",
        payload={"affordance_id": "aff-a"},
    )
    log.append(
        run_id="r1",
        instance_id="i1",
        event_type=DECISION_INFLUENCED_EVENT,
        actor="scheduler",
        payload={"decision_id": "dec-a", "changed": True},
    )
    log.append(
        run_id="r1",
        instance_id="i1",
        event_type=DECISION_INFLUENCED_EVENT,
        actor="scheduler",
        payload={"decision_id": "dec-noop", "changed": False},
    )
    log.append(
        run_id="r1",
        instance_id="i1",
        event_type=TRAJECTORY_DIVERGED_EVENT,
        actor="scheduler",
        payload={
            "decision_id": "dec-a",
            "downstream_delta": {
                "compile_success": "worse",
                "test_success": "same",
            },
        },
    )
    log.append(
        run_id="r1",
        instance_id="i1",
        event_type="run.completed",
        actor="strategy_runner",
        payload={
            "strategy": "stigmergic_scheduler",
            "stop_reason": "repair_exhausted",
            "candidate_count": 1,
        },
    )

    summary = build_summary(
        campaign_id="c1",
        adapter_name="toy",
        strategy_name="stigmergic_scheduler",
        instance_ids=["i1"],
        events_by_instance={"i1": log.read_all()},
    )
    inst = summary.instances[0]

    assert inst.signal_read_count == 1
    assert inst.unique_signal_read_count == 1
    assert inst.decision_influenced_count == 1
    assert inst.trajectory_divergence_count == 1
    assert inst.affordance_created_count == 1
    assert inst.affordance_consumed_count == 1
    assert inst.unused_signal_rate == 0.0
    assert inst.unused_affordance_rate == 0.0
    assert inst.signal_harm_rate == 1.0
    assert summary.stigmergic_causality_rate == 1.0
