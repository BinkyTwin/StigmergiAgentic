"""Telemetry reconstruction from the V10 EventLog.

The summary written by the harness is *always* derived from
``build_summary``. This module also exposes ``replay_summary_from_dir`` so
an independent replay can verify that the on-disk summary matches what
the EventLog implies.

Strict invariant:

- ``strict_success`` is True for an instance iff the most recent
  ``score.completed`` event for that instance carries
  ``strict_success=True``;
- the summary never invents a metric: final score signals are reconstructed
  from ``score.completed`` events, while apply/validation counters are
  reconstructed from their own EventLog records.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from core_v10.event_log import EventRecord, JsonlEventLog


SCORE_EVENT = "score.completed"
RUN_COMPLETED_EVENT = "run.completed"
SELECTION_EVENT = "selection.completed"
DEDUPED_EVENT = "candidate.deduped"
REPEAT_FAILURE_EVENT = "candidate.repeat_failure_suppressed"
SIGNAL_EMITTED_EVENT = "signal.emitted"
SIGNAL_APPLIED_EVENT = "signal.applied"
SIGNAL_READ_EVENT = "signal.read"
AFFORDANCE_CREATED_EVENT = "affordance.created"
AFFORDANCE_CONSUMED_EVENT = "affordance.consumed"
AFFORDANCE_EXPIRED_EVENT = "affordance.expired"
AFFORDANCE_INHIBITED_EVENT = "affordance.inhibited"
WORKER_ELIGIBLE_EVENT = "worker.eligible"
WORKER_SELECTED_EVENT = "worker.selected"
WORKER_ACTIVATED_EVENT = "worker.activated"
WORKER_OUTPUT_EVENT = "worker.output"
OPERATOR_INVOKED_EVENT = "operator.invoked"
OPERATOR_APPLIED_EVENT = "operator.applied"
OPERATOR_REJECTED_EVENT = "operator.rejected"
OPERATOR_FAILED_EVENT = "operator.failed"
DECISION_INFLUENCED_EVENT = "decision.influenced"
TRAJECTORY_DIVERGED_EVENT = "trajectory.diverged"
CANDIDATE_APPLIED_EVENT = "candidate.applied"
VALIDATION_EVENT = "validation.completed"


@dataclass(frozen=True)
class InstanceSummary:
    """One-row summary derived from EventLog events of a single instance."""

    instance_id: str
    strategy_name: str
    stop_reason: str
    strict_success: bool
    selected_hypothesis_id: str | None
    candidate_count: int
    signals: dict[str, Any] = field(default_factory=dict)
    dedup_skipped: int = 0
    repeat_failure_suppressed: int = 0
    selection_rationale: dict[str, Any] | None = None
    # Phase 6 — stigmergic signal counts derived from signal.* events.
    signal_emitted_count: int = 0
    signal_applied_count: int = 0
    signal_read_count: int = 0
    unique_signal_read_count: int = 0
    signal_read_rate: float = 0.0
    decision_influenced_count: int = 0
    decision_influence_rate: float = 0.0
    trajectory_divergence_count: int = 0
    trajectory_divergence_rate: float = 0.0
    affordance_created_count: int = 0
    affordance_consumed_count: int = 0
    affordance_expired_count: int = 0
    affordance_inhibited_count: int = 0
    unused_signal_rate: float = 0.0
    unused_affordance_rate: float = 0.0
    cosmetic_signal_rate: float = 0.0
    stigmergic_causality_rate: float = 0.0
    signal_harm_rate: float = 0.0
    worker_eligible_count: int = 0
    worker_selected_count: int = 0
    worker_activated_count: int = 0
    worker_output_count: int = 0
    operator_invoked_count: int = 0
    operator_applied_count: int = 0
    operator_rejected_count: int = 0
    operator_failed_count: int = 0
    pheromone_hit_rate: float = 0.0
    feedback_reuse_rate: float = 0.0
    repeated_failure_suppression: int = 0
    apply_ok_count: int = 0
    validation_completed_count: int = 0
    validation_passed_count: int = 0
    validation_partial_count: int = 0
    validation_failed_count: int = 0
    validation_error_count: int = 0


@dataclass(frozen=True)
class Summary:
    """Aggregate campaign summary across instances."""

    campaign_id: str
    adapter_name: str
    strategy_name: str
    instance_count: int
    strict_success_count: int
    by_signal: dict[str, int]
    instances: list[InstanceSummary]
    dedup_skipped_total: int = 0
    repeat_failure_suppressed_total: int = 0
    # Phase 6 — campaign-wide stigmergic metrics (canonical, pre-registered).
    signal_emitted_total: int = 0
    signal_applied_total: int = 0
    signal_read_total: int = 0
    unique_signal_read_total: int = 0
    signal_read_rate: float = 0.0
    decision_influenced_total: int = 0
    decision_influence_rate: float = 0.0
    trajectory_divergence_total: int = 0
    trajectory_divergence_rate: float = 0.0
    affordance_created_total: int = 0
    affordance_consumed_total: int = 0
    affordance_expired_total: int = 0
    affordance_inhibited_total: int = 0
    unused_signal_rate: float = 0.0
    unused_affordance_rate: float = 0.0
    cosmetic_signal_rate: float = 0.0
    stigmergic_causality_rate: float = 0.0
    signal_harm_rate: float = 0.0
    worker_eligible_total: int = 0
    worker_selected_total: int = 0
    worker_activated_total: int = 0
    worker_output_total: int = 0
    operator_invoked_total: int = 0
    operator_applied_total: int = 0
    operator_rejected_total: int = 0
    operator_failed_total: int = 0
    pheromone_hit_rate: float = 0.0
    feedback_reuse_rate: float = 0.0
    repeated_failure_suppression_total: int = 0
    apply_ok_total: int = 0
    validation_completed_total: int = 0
    validation_passed_total: int = 0
    validation_partial_total: int = 0
    validation_failed_total: int = 0
    validation_error_total: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "adapter_name": self.adapter_name,
            "strategy_name": self.strategy_name,
            "instance_count": int(self.instance_count),
            "strict_success_count": int(self.strict_success_count),
            "by_signal": dict(self.by_signal),
            "instances": [asdict(inst) for inst in self.instances],
            "dedup_skipped_total": int(self.dedup_skipped_total),
            "repeat_failure_suppressed_total": int(self.repeat_failure_suppressed_total),
            "signal_emitted_total": int(self.signal_emitted_total),
            "signal_applied_total": int(self.signal_applied_total),
            "signal_read_total": int(self.signal_read_total),
            "unique_signal_read_total": int(self.unique_signal_read_total),
            "signal_read_rate": float(self.signal_read_rate),
            "decision_influenced_total": int(self.decision_influenced_total),
            "decision_influence_rate": float(self.decision_influence_rate),
            "trajectory_divergence_total": int(self.trajectory_divergence_total),
            "trajectory_divergence_rate": float(self.trajectory_divergence_rate),
            "affordance_created_total": int(self.affordance_created_total),
            "affordance_consumed_total": int(self.affordance_consumed_total),
            "affordance_expired_total": int(self.affordance_expired_total),
            "affordance_inhibited_total": int(self.affordance_inhibited_total),
            "unused_signal_rate": float(self.unused_signal_rate),
            "unused_affordance_rate": float(self.unused_affordance_rate),
            "cosmetic_signal_rate": float(self.cosmetic_signal_rate),
            "stigmergic_causality_rate": float(self.stigmergic_causality_rate),
            "signal_harm_rate": float(self.signal_harm_rate),
            "worker_eligible_total": int(self.worker_eligible_total),
            "worker_selected_total": int(self.worker_selected_total),
            "worker_activated_total": int(self.worker_activated_total),
            "worker_output_total": int(self.worker_output_total),
            "operator_invoked_total": int(self.operator_invoked_total),
            "operator_applied_total": int(self.operator_applied_total),
            "operator_rejected_total": int(self.operator_rejected_total),
            "operator_failed_total": int(self.operator_failed_total),
            "pheromone_hit_rate": float(self.pheromone_hit_rate),
            "feedback_reuse_rate": float(self.feedback_reuse_rate),
            "repeated_failure_suppression_total": int(
                self.repeated_failure_suppression_total
            ),
            "apply_ok_total": int(self.apply_ok_total),
            "validation_completed_total": int(self.validation_completed_total),
            "validation_passed_total": int(self.validation_passed_total),
            "validation_partial_total": int(self.validation_partial_total),
            "validation_failed_total": int(self.validation_failed_total),
            "validation_error_total": int(self.validation_error_total),
        }


def _last_event(events: Sequence[EventRecord], event_type: str) -> EventRecord | None:
    for event in reversed(events):
        if event.event_type == event_type:
            return event
    return None


def _coerce_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    score = payload.get("score") or {}
    if isinstance(score, dict):
        metrics = score.get("metrics") or {}
        if isinstance(metrics, dict):
            return dict(metrics)
    return {}


def _signal_identity_from_emitted(event: EventRecord) -> str:
    record = event.payload.get("record") or {}
    if not isinstance(record, dict):
        return ""
    if record.get("signal_id"):
        return str(record["signal_id"])
    kind = str(record.get("kind") or "")
    target = str(record.get("target") or "")
    return f"{kind}:{target}" if kind and target else ""


def _affordance_identity_from_created(event: EventRecord) -> str:
    payload = event.payload.get("affordance") or event.payload
    if isinstance(payload, dict) and payload.get("affordance_id"):
        return str(payload["affordance_id"])
    return ""


def _signal_harm_rate(events: Sequence[EventRecord]) -> float:
    if not events:
        return 0.0
    harmful = 0
    for event in events:
        delta = event.payload.get("downstream_delta") or {}
        if not isinstance(delta, dict):
            continue
        if _has_harmful_delta(delta):
            harmful += 1
    return harmful / float(len(events))


def _has_harmful_delta(value) -> bool:
    harmful_values = {"worse", "regressed", "harm"}
    if isinstance(value, dict):
        return any(_has_harmful_delta(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_has_harmful_delta(item) for item in value)
    return str(value).lower() in harmful_values


def _instance_summary(
    *,
    instance_id: str,
    strategy_name: str,
    events: Sequence[EventRecord],
) -> InstanceSummary:
    instance_events = [e for e in events if e.instance_id == instance_id]
    score_event = _last_event(instance_events, SCORE_EVENT)
    completed_event = _last_event(instance_events, RUN_COMPLETED_EVENT)

    strict_success = False
    signals: dict[str, Any] = {}
    selected_id: str | None = None

    if score_event is not None:
        signals = _coerce_metrics(score_event.payload)
        raw_strict = score_event.payload.get("strict_success")
        strict_success = bool(raw_strict) if raw_strict is not None else bool(
            signals.get("strict_success", False)
        )
        selected_id = score_event.hypothesis_id

    stop_reason = "unknown"
    candidate_count = 0
    dedup_skipped = 0
    repeat_failure_suppressed = 0
    if completed_event is not None:
        payload = completed_event.payload
        stop_reason = str(payload.get("stop_reason") or stop_reason)
        candidate_count = int(payload.get("candidate_count") or 0)
        dedup_skipped = int(payload.get("dedup_skipped") or 0)
        repeat_failure_suppressed = int(payload.get("repeat_failure_suppressed") or 0)
        if selected_id is None:
            selected_id = payload.get("selected_hypothesis_id")

    selection_event = _last_event(instance_events, SELECTION_EVENT)
    selection_rationale: dict[str, Any] | None = None
    if selection_event is not None:
        rationale_payload = selection_event.payload.get("rationale")
        if isinstance(rationale_payload, dict):
            selection_rationale = dict(rationale_payload)

    # Cross-check the run.completed counters against the actual events to keep
    # the summary self-consistent under replay (live==replay invariant).
    if dedup_skipped == 0:
        dedup_skipped = sum(
            1 for e in instance_events if e.event_type == DEDUPED_EVENT
        )
    if repeat_failure_suppressed == 0:
        repeat_failure_suppressed = sum(
            1 for e in instance_events if e.event_type == REPEAT_FAILURE_EVENT
        )

    # Phase 6 stigmergic counters — reconstructed from signal.* events.
    signal_emitted_events = [
        e for e in instance_events if e.event_type == SIGNAL_EMITTED_EVENT
    ]
    signal_applied_events = [
        e for e in instance_events if e.event_type == SIGNAL_APPLIED_EVENT
    ]
    actionable_applied = [
        e
        for e in signal_applied_events
        if str(e.payload.get("kind") or "") != "novelty"
        and str(e.payload.get("effect") or "")
        in {"drop", "reorder", "finalize_tiebreak"}
    ]
    signal_emitted_count = len(signal_emitted_events)
    signal_applied_count = len(signal_applied_events)
    pheromone_hit_rate = (
        len(actionable_applied) / float(candidate_count)
        if candidate_count > 0
        else 0.0
    )
    # feedback_reuse_rate: fraction of anti-action signals that were *applied*
    # beyond their first emission. We approximate it as the ratio of
    # (applied targets that match anti:* and have ≥2 emissions) over total
    # anti:* signals emitted, when at least one anti:* signal exists.
    anti_targets = [
        str(e.payload.get("record", {}).get("target") or "")
        for e in signal_emitted_events
        if str(e.payload.get("record", {}).get("target") or "").startswith("anti:")
    ]
    anti_unique_targets = set(anti_targets)
    anti_repeated_targets = {
        target for target in anti_unique_targets if anti_targets.count(target) >= 2
    }
    anti_applied_targets = {
        str(e.payload.get("target") or "")
        for e in actionable_applied
        if str(e.payload.get("target") or "").startswith("anti:")
    }
    feedback_reuse_rate = (
        len(anti_repeated_targets & anti_applied_targets)
        / float(len(anti_unique_targets))
        if anti_unique_targets
        else 0.0
    )
    signal_driven_drops = sum(
        1
        for e in signal_applied_events
        if str(e.payload.get("effect") or "") == "drop"
        and str(e.payload.get("target") or "").startswith("signature:")
    )
    repeated_failure_suppression = (
        int(repeat_failure_suppressed) + int(signal_driven_drops)
    )

    # V11 causal stigmergy counters — all reconstructed from EventLog events.
    signal_read_events = [
        e for e in instance_events if e.event_type == SIGNAL_READ_EVENT
    ]
    decision_influenced_events = [
        e
        for e in instance_events
        if e.event_type == DECISION_INFLUENCED_EVENT
        and bool(e.payload.get("changed", True))
    ]
    trajectory_diverged_events = [
        e for e in instance_events if e.event_type == TRAJECTORY_DIVERGED_EVENT
    ]
    affordance_created_events = [
        e for e in instance_events if e.event_type == AFFORDANCE_CREATED_EVENT
    ]
    affordance_consumed_events = [
        e for e in instance_events if e.event_type == AFFORDANCE_CONSUMED_EVENT
    ]
    affordance_expired_events = [
        e for e in instance_events if e.event_type == AFFORDANCE_EXPIRED_EVENT
    ]
    affordance_inhibited_events = [
        e for e in instance_events if e.event_type == AFFORDANCE_INHIBITED_EVENT
    ]
    worker_eligible_events = [
        e for e in instance_events if e.event_type == WORKER_ELIGIBLE_EVENT
    ]
    worker_selected_events = [
        e for e in instance_events if e.event_type == WORKER_SELECTED_EVENT
    ]
    worker_activated_events = [
        e for e in instance_events if e.event_type == WORKER_ACTIVATED_EVENT
    ]
    worker_output_events = [
        e for e in instance_events if e.event_type == WORKER_OUTPUT_EVENT
    ]
    operator_invoked_events = [
        e for e in instance_events if e.event_type == OPERATOR_INVOKED_EVENT
    ]
    operator_applied_events = [
        e for e in instance_events if e.event_type == OPERATOR_APPLIED_EVENT
    ]
    operator_rejected_events = [
        e for e in instance_events if e.event_type == OPERATOR_REJECTED_EVENT
    ]
    operator_failed_events = [
        e for e in instance_events if e.event_type == OPERATOR_FAILED_EVENT
    ]

    emitted_signal_ids = {
        _signal_identity_from_emitted(e) for e in signal_emitted_events
    }
    emitted_signal_ids.discard("")
    read_signal_ids: set[str] = set()
    for event in signal_read_events:
        for signal_id in event.payload.get("signals_seen") or ():
            read_signal_ids.add(str(signal_id))
    created_affordance_ids = {
        _affordance_identity_from_created(e) for e in affordance_created_events
    }
    created_affordance_ids.discard("")
    consumed_affordance_ids = {
        str(e.payload.get("affordance_id") or "")
        for e in affordance_consumed_events
    }
    consumed_affordance_ids.discard("")

    signal_read_count = len(signal_read_events)
    unique_signal_read_count = len(read_signal_ids)
    signal_read_rate = (
        unique_signal_read_count / float(len(emitted_signal_ids))
        if emitted_signal_ids
        else 0.0
    )
    decision_influenced_count = len(decision_influenced_events)
    worker_selected_count = len(worker_selected_events)
    worker_activated_count = len(worker_activated_events)
    decision_influence_rate = (
        decision_influenced_count / float(worker_selected_count)
        if worker_selected_count
        else 0.0
    )
    trajectory_divergence_count = len(trajectory_diverged_events)
    trajectory_divergence_rate = (
        trajectory_divergence_count / float(decision_influenced_count)
        if decision_influenced_count
        else 0.0
    )
    unused_signal_rate = (
        len(emitted_signal_ids - read_signal_ids) / float(len(emitted_signal_ids))
        if emitted_signal_ids
        else 0.0
    )
    unused_affordance_rate = (
        len(created_affordance_ids - consumed_affordance_ids)
        / float(len(created_affordance_ids))
        if created_affordance_ids
        else 0.0
    )
    cosmetic_signal_rate = (
        max(0, signal_applied_count - decision_influenced_count)
        / float(signal_applied_count)
        if signal_applied_count
        else 0.0
    )
    stigmergic_causality_rate = (
        decision_influenced_count / float(worker_selected_count)
        if worker_selected_count
        else 0.0
    )
    signal_harm_rate = _signal_harm_rate(trajectory_diverged_events)

    apply_ok_count = sum(
        1
        for e in instance_events
        if e.event_type == CANDIDATE_APPLIED_EVENT
        and bool((e.payload.get("apply_result") or {}).get("applied"))
    )
    validation_events = [
        e for e in instance_events if e.event_type == VALIDATION_EVENT
    ]
    validation_status_counts = {
        "passed": 0,
        "partial": 0,
        "failed": 0,
        "error": 0,
    }
    for event in validation_events:
        validation = event.payload.get("validation") or {}
        status = str(validation.get("status") or "").lower()
        if status in validation_status_counts:
            validation_status_counts[status] += 1

    return InstanceSummary(
        instance_id=instance_id,
        strategy_name=strategy_name,
        stop_reason=stop_reason,
        strict_success=strict_success,
        selected_hypothesis_id=selected_id,
        candidate_count=candidate_count,
        signals=signals,
        dedup_skipped=int(dedup_skipped),
        repeat_failure_suppressed=int(repeat_failure_suppressed),
        selection_rationale=selection_rationale,
        signal_emitted_count=int(signal_emitted_count),
        signal_applied_count=int(signal_applied_count),
        signal_read_count=int(signal_read_count),
        unique_signal_read_count=int(unique_signal_read_count),
        signal_read_rate=float(signal_read_rate),
        decision_influenced_count=int(decision_influenced_count),
        decision_influence_rate=float(decision_influence_rate),
        trajectory_divergence_count=int(trajectory_divergence_count),
        trajectory_divergence_rate=float(trajectory_divergence_rate),
        affordance_created_count=len(affordance_created_events),
        affordance_consumed_count=len(affordance_consumed_events),
        affordance_expired_count=len(affordance_expired_events),
        affordance_inhibited_count=len(affordance_inhibited_events),
        unused_signal_rate=float(unused_signal_rate),
        unused_affordance_rate=float(unused_affordance_rate),
        cosmetic_signal_rate=float(cosmetic_signal_rate),
        stigmergic_causality_rate=float(stigmergic_causality_rate),
        signal_harm_rate=float(signal_harm_rate),
        worker_eligible_count=len(worker_eligible_events),
        worker_selected_count=int(worker_selected_count),
        worker_activated_count=int(worker_activated_count),
        worker_output_count=len(worker_output_events),
        operator_invoked_count=len(operator_invoked_events),
        operator_applied_count=len(operator_applied_events),
        operator_rejected_count=len(operator_rejected_events),
        operator_failed_count=len(operator_failed_events),
        pheromone_hit_rate=float(pheromone_hit_rate),
        feedback_reuse_rate=float(feedback_reuse_rate),
        repeated_failure_suppression=int(repeated_failure_suppression),
        apply_ok_count=int(apply_ok_count),
        validation_completed_count=len(validation_events),
        validation_passed_count=int(validation_status_counts["passed"]),
        validation_partial_count=int(validation_status_counts["partial"]),
        validation_failed_count=int(validation_status_counts["failed"]),
        validation_error_count=int(validation_status_counts["error"]),
    )


def build_summary(
    *,
    campaign_id: str,
    adapter_name: str,
    strategy_name: str,
    instance_ids: Iterable[str],
    events_by_instance: dict[str, list[EventRecord]],
) -> Summary:
    """Aggregate per-instance EventLog reads into a campaign-wide summary."""

    instance_ids = list(instance_ids)
    instances: list[InstanceSummary] = []
    by_signal: dict[str, int] = {}
    strict_count = 0
    dedup_total = 0
    repeat_total = 0
    signal_emitted_total = 0
    signal_applied_total = 0
    signal_read_total = 0
    unique_signal_read_total = 0
    signal_read_rate_sum = 0.0
    decision_influenced_total = 0
    decision_influence_rate_sum = 0.0
    trajectory_divergence_total = 0
    trajectory_divergence_rate_sum = 0.0
    affordance_created_total = 0
    affordance_consumed_total = 0
    affordance_expired_total = 0
    affordance_inhibited_total = 0
    unused_signal_rate_sum = 0.0
    unused_affordance_rate_sum = 0.0
    cosmetic_signal_rate_sum = 0.0
    stigmergic_causality_rate_sum = 0.0
    signal_harm_rate_sum = 0.0
    worker_eligible_total = 0
    worker_selected_total = 0
    worker_activated_total = 0
    worker_output_total = 0
    operator_invoked_total = 0
    operator_applied_total = 0
    operator_rejected_total = 0
    operator_failed_total = 0
    pheromone_hit_sum = 0.0
    feedback_reuse_sum = 0.0
    repeated_failure_suppression_total = 0
    apply_ok_total = 0
    validation_completed_total = 0
    validation_passed_total = 0
    validation_partial_total = 0
    validation_failed_total = 0
    validation_error_total = 0
    for instance_id in instance_ids:
        events = events_by_instance.get(instance_id, [])
        summary = _instance_summary(
            instance_id=instance_id,
            strategy_name=strategy_name,
            events=events,
        )
        instances.append(summary)
        if summary.strict_success:
            strict_count += 1
        dedup_total += summary.dedup_skipped
        repeat_total += summary.repeat_failure_suppressed
        signal_emitted_total += summary.signal_emitted_count
        signal_applied_total += summary.signal_applied_count
        signal_read_total += summary.signal_read_count
        unique_signal_read_total += summary.unique_signal_read_count
        signal_read_rate_sum += summary.signal_read_rate
        decision_influenced_total += summary.decision_influenced_count
        decision_influence_rate_sum += summary.decision_influence_rate
        trajectory_divergence_total += summary.trajectory_divergence_count
        trajectory_divergence_rate_sum += summary.trajectory_divergence_rate
        affordance_created_total += summary.affordance_created_count
        affordance_consumed_total += summary.affordance_consumed_count
        affordance_expired_total += summary.affordance_expired_count
        affordance_inhibited_total += summary.affordance_inhibited_count
        unused_signal_rate_sum += summary.unused_signal_rate
        unused_affordance_rate_sum += summary.unused_affordance_rate
        cosmetic_signal_rate_sum += summary.cosmetic_signal_rate
        stigmergic_causality_rate_sum += summary.stigmergic_causality_rate
        signal_harm_rate_sum += summary.signal_harm_rate
        worker_eligible_total += summary.worker_eligible_count
        worker_selected_total += summary.worker_selected_count
        worker_activated_total += summary.worker_activated_count
        worker_output_total += summary.worker_output_count
        operator_invoked_total += summary.operator_invoked_count
        operator_applied_total += summary.operator_applied_count
        operator_rejected_total += summary.operator_rejected_count
        operator_failed_total += summary.operator_failed_count
        pheromone_hit_sum += summary.pheromone_hit_rate
        feedback_reuse_sum += summary.feedback_reuse_rate
        repeated_failure_suppression_total += summary.repeated_failure_suppression
        apply_ok_total += summary.apply_ok_count
        validation_completed_total += summary.validation_completed_count
        validation_passed_total += summary.validation_passed_count
        validation_partial_total += summary.validation_partial_count
        validation_failed_total += summary.validation_failed_count
        validation_error_total += summary.validation_error_count
        for key, value in summary.signals.items():
            if value is True:
                by_signal[key] = by_signal.get(key, 0) + 1

    n = max(1, len(instance_ids))
    return Summary(
        campaign_id=campaign_id,
        adapter_name=adapter_name,
        strategy_name=strategy_name,
        instance_count=len(instance_ids),
        strict_success_count=strict_count,
        by_signal=by_signal,
        instances=instances,
        dedup_skipped_total=dedup_total,
        repeat_failure_suppressed_total=repeat_total,
        signal_emitted_total=signal_emitted_total,
        signal_applied_total=signal_applied_total,
        signal_read_total=signal_read_total,
        unique_signal_read_total=unique_signal_read_total,
        signal_read_rate=signal_read_rate_sum / float(n),
        decision_influenced_total=decision_influenced_total,
        decision_influence_rate=decision_influence_rate_sum / float(n),
        trajectory_divergence_total=trajectory_divergence_total,
        trajectory_divergence_rate=trajectory_divergence_rate_sum / float(n),
        affordance_created_total=affordance_created_total,
        affordance_consumed_total=affordance_consumed_total,
        affordance_expired_total=affordance_expired_total,
        affordance_inhibited_total=affordance_inhibited_total,
        unused_signal_rate=unused_signal_rate_sum / float(n),
        unused_affordance_rate=unused_affordance_rate_sum / float(n),
        cosmetic_signal_rate=cosmetic_signal_rate_sum / float(n),
        stigmergic_causality_rate=stigmergic_causality_rate_sum / float(n),
        signal_harm_rate=signal_harm_rate_sum / float(n),
        worker_eligible_total=worker_eligible_total,
        worker_selected_total=worker_selected_total,
        worker_activated_total=worker_activated_total,
        worker_output_total=worker_output_total,
        operator_invoked_total=operator_invoked_total,
        operator_applied_total=operator_applied_total,
        operator_rejected_total=operator_rejected_total,
        operator_failed_total=operator_failed_total,
        pheromone_hit_rate=pheromone_hit_sum / float(n),
        feedback_reuse_rate=feedback_reuse_sum / float(n),
        repeated_failure_suppression_total=repeated_failure_suppression_total,
        apply_ok_total=apply_ok_total,
        validation_completed_total=validation_completed_total,
        validation_passed_total=validation_passed_total,
        validation_partial_total=validation_partial_total,
        validation_failed_total=validation_failed_total,
        validation_error_total=validation_error_total,
    )


def write_summary(out_dir: Path | str, summary: Summary, *, filename: str = "summary.json") -> Path:
    """Serialize a :class:`Summary` to ``out_dir/<filename>``."""

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / filename
    target.write_text(
        json.dumps(summary.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def read_events(out_dir: Path | str, instance_id: str) -> list[EventRecord]:
    """Read the per-instance event log written by the harness."""

    path = Path(out_dir) / "events" / instance_id / "eventlog.jsonl"
    if not path.exists():
        return []
    return JsonlEventLog(path).read_all()


def replay_summary_from_dir(out_dir: Path | str) -> Summary:
    """Reconstruct a :class:`Summary` from the campaign tree on disk."""

    out_dir = Path(out_dir)
    manifest_path = out_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"missing manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    instance_ids = list(manifest.get("instance_ids") or [])
    events_by_instance = {
        instance_id: read_events(out_dir, instance_id) for instance_id in instance_ids
    }
    return build_summary(
        campaign_id=str(manifest["campaign_id"]),
        adapter_name=str(manifest["adapter_name"]),
        strategy_name=str(manifest["strategy_name"]),
        instance_ids=instance_ids,
        events_by_instance=events_by_instance,
    )


__all__ = [
    "DEDUPED_EVENT",
    "AFFORDANCE_CONSUMED_EVENT",
    "AFFORDANCE_CREATED_EVENT",
    "AFFORDANCE_EXPIRED_EVENT",
    "AFFORDANCE_INHIBITED_EVENT",
    "CANDIDATE_APPLIED_EVENT",
    "DECISION_INFLUENCED_EVENT",
    "InstanceSummary",
    "OPERATOR_APPLIED_EVENT",
    "OPERATOR_FAILED_EVENT",
    "OPERATOR_INVOKED_EVENT",
    "OPERATOR_REJECTED_EVENT",
    "REPEAT_FAILURE_EVENT",
    "RUN_COMPLETED_EVENT",
    "SCORE_EVENT",
    "SELECTION_EVENT",
    "SIGNAL_APPLIED_EVENT",
    "SIGNAL_EMITTED_EVENT",
    "SIGNAL_READ_EVENT",
    "Summary",
    "TRAJECTORY_DIVERGED_EVENT",
    "VALIDATION_EVENT",
    "WORKER_ACTIVATED_EVENT",
    "WORKER_ELIGIBLE_EVENT",
    "WORKER_OUTPUT_EVENT",
    "WORKER_SELECTED_EVENT",
    "build_summary",
    "read_events",
    "replay_summary_from_dir",
    "write_summary",
]
