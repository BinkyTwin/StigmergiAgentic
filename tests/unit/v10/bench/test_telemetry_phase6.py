"""Phase 6 unit tests — stigmergic counters in the bench telemetry."""

from __future__ import annotations

from core_v10.event_log import JsonlEventLog
from scripts.bench.telemetry import (
    SIGNAL_APPLIED_EVENT,
    SIGNAL_EMITTED_EVENT,
    build_summary,
)


def _append_score_event(log: JsonlEventLog, instance_id: str, *, candidate_count: int) -> None:
    log.append(
        run_id="r-1",
        instance_id=instance_id,
        event_type="run.completed",
        actor="strategy_runner",
        payload={
            "strategy": "stigmergic_blackboard",
            "stop_reason": "strict_success",
            "candidate_count": candidate_count,
        },
    )
    log.append(
        run_id="r-1",
        instance_id=instance_id,
        event_type="score.completed",
        actor="adapter",
        payload={
            "score": {"metrics": {"strict_success": True}},
            "strict_success": True,
        },
    )


def _emit_signal(
    log: JsonlEventLog,
    *,
    instance_id: str,
    target: str,
    kind: str = "inhibit",
    intensity: float = 0.5,
) -> None:
    log.append(
        run_id="r-1",
        instance_id=instance_id,
        event_type=SIGNAL_EMITTED_EVENT,
        actor="signal_policy",
        payload={
            "record": {
                "kind": kind,
                "target": target,
                "intensity": intensity,
                "evidence": [],
                "half_life": 8,
                "created_at_seq": 1,
                "last_seen_seq": 1,
                "emit_count": 1,
            },
            "op": "emit",
        },
    )


def _apply_signal(
    log: JsonlEventLog,
    *,
    instance_id: str,
    target: str,
    effect: str,
    kind: str = "inhibit",
    intensity: float = 0.9,
) -> None:
    log.append(
        run_id="r-1",
        instance_id=instance_id,
        event_type=SIGNAL_APPLIED_EVENT,
        actor="strategy_runner",
        payload={
            "kind": kind,
            "target": target,
            "effect": effect,
            "rationale": "test",
            "intensity": intensity,
        },
    )


def test_summary_zero_phase6_metrics_when_no_signal_events(tmp_path) -> None:
    log = JsonlEventLog(tmp_path / "events.jsonl")
    _append_score_event(log, "i-1", candidate_count=1)
    summary = build_summary(
        campaign_id="c-1",
        adapter_name="toy",
        strategy_name="agentless_basic",
        instance_ids=["i-1"],
        events_by_instance={"i-1": log.read_all()},
    )
    payload = summary.to_dict()
    assert payload["signal_emitted_total"] == 0
    assert payload["signal_applied_total"] == 0
    assert payload["pheromone_hit_rate"] == 0.0
    assert payload["feedback_reuse_rate"] == 0.0
    assert payload["repeated_failure_suppression_total"] == 0


def test_summary_counts_signal_emitted_and_applied_events(tmp_path) -> None:
    log = JsonlEventLog(tmp_path / "events.jsonl")
    _emit_signal(log, instance_id="i-1", target="failure_type:compile_error")
    _emit_signal(log, instance_id="i-1", target="signature:abc123")
    _apply_signal(
        log,
        instance_id="i-1",
        target="signature:abc123",
        effect="drop",
    )
    _append_score_event(log, "i-1", candidate_count=2)
    summary = build_summary(
        campaign_id="c-1",
        adapter_name="toy",
        strategy_name="stigmergic_blackboard",
        instance_ids=["i-1"],
        events_by_instance={"i-1": log.read_all()},
    )
    inst = summary.instances[0]
    assert inst.signal_emitted_count == 2
    assert inst.signal_applied_count == 1
    # actionable_applied count = 1 (drop), candidate_count = 2 → 0.5
    assert abs(inst.pheromone_hit_rate - 0.5) < 1e-6
    # signal-driven signature drop counts in repeated_failure_suppression
    assert inst.repeated_failure_suppression == 1


def test_feedback_reuse_rate_when_anti_action_applied_after_repeats(tmp_path) -> None:
    log = JsonlEventLog(tmp_path / "events.jsonl")
    # Anti-action emitted twice → "repeated"
    _emit_signal(
        log,
        instance_id="i-1",
        target="anti:preserve_existing_tests",
    )
    _emit_signal(
        log,
        instance_id="i-1",
        target="anti:preserve_existing_tests",
    )
    # Then applied as a tiebreak/reorder
    _apply_signal(
        log,
        instance_id="i-1",
        target="anti:preserve_existing_tests",
        effect="reorder",
    )
    _append_score_event(log, "i-1", candidate_count=2)
    summary = build_summary(
        campaign_id="c-1",
        adapter_name="toy",
        strategy_name="stigmergic_blackboard",
        instance_ids=["i-1"],
        events_by_instance={"i-1": log.read_all()},
    )
    inst = summary.instances[0]
    assert inst.feedback_reuse_rate == 1.0


def test_novelty_signal_applied_excluded_from_pheromone_hit_rate(tmp_path) -> None:
    log = JsonlEventLog(tmp_path / "events.jsonl")
    _apply_signal(
        log,
        instance_id="i-1",
        target="hypothesis_space",
        effect="reorder",
        kind="novelty",
        intensity=0.5,
    )
    _append_score_event(log, "i-1", candidate_count=2)
    summary = build_summary(
        campaign_id="c-1",
        adapter_name="toy",
        strategy_name="stigmergic_blackboard",
        instance_ids=["i-1"],
        events_by_instance={"i-1": log.read_all()},
    )
    inst = summary.instances[0]
    assert inst.signal_applied_count == 1
    assert inst.pheromone_hit_rate == 0.0


def test_summary_phase6_metrics_aggregate_across_instances(tmp_path) -> None:
    log_a = JsonlEventLog(tmp_path / "a.jsonl")
    log_b = JsonlEventLog(tmp_path / "b.jsonl")
    _emit_signal(log_a, instance_id="i-a", target="failure_type:x")
    _apply_signal(
        log_a, instance_id="i-a", target="signature:hh", effect="drop"
    )
    _append_score_event(log_a, "i-a", candidate_count=2)
    _append_score_event(log_b, "i-b", candidate_count=2)

    summary = build_summary(
        campaign_id="c-1",
        adapter_name="toy",
        strategy_name="stigmergic_blackboard",
        instance_ids=["i-a", "i-b"],
        events_by_instance={
            "i-a": log_a.read_all(),
            "i-b": log_b.read_all(),
        },
    )
    payload = summary.to_dict()
    assert payload["signal_emitted_total"] == 1
    assert payload["signal_applied_total"] == 1
    # average over 2 instances: (0.5 + 0.0) / 2 = 0.25
    assert abs(payload["pheromone_hit_rate"] - 0.25) < 1e-6
    assert payload["repeated_failure_suppression_total"] == 1
