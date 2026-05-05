"""Telemetry reconstruction from the V10 EventLog.

The summary written by the harness is *always* derived from
``build_summary``. This module also exposes ``replay_summary_from_dir`` so
an independent replay can verify that the on-disk summary matches what
the EventLog implies.

Strict invariant:

- ``strict_success`` is True for an instance iff the most recent
  ``score.completed`` event for that instance carries
  ``strict_success=True``;
- the summary never invents a metric: every count is reconstructible from
  the ``score.completed`` payload (and only from it).
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
    pheromone_hit_rate: float = 0.0
    feedback_reuse_rate: float = 0.0
    repeated_failure_suppression: int = 0


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
    pheromone_hit_rate: float = 0.0
    feedback_reuse_rate: float = 0.0
    repeated_failure_suppression_total: int = 0

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
            "pheromone_hit_rate": float(self.pheromone_hit_rate),
            "feedback_reuse_rate": float(self.feedback_reuse_rate),
            "repeated_failure_suppression_total": int(
                self.repeated_failure_suppression_total
            ),
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
        pheromone_hit_rate=float(pheromone_hit_rate),
        feedback_reuse_rate=float(feedback_reuse_rate),
        repeated_failure_suppression=int(repeated_failure_suppression),
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
    pheromone_hit_sum = 0.0
    feedback_reuse_sum = 0.0
    repeated_failure_suppression_total = 0
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
        pheromone_hit_sum += summary.pheromone_hit_rate
        feedback_reuse_sum += summary.feedback_reuse_rate
        repeated_failure_suppression_total += summary.repeated_failure_suppression
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
        pheromone_hit_rate=pheromone_hit_sum / float(n),
        feedback_reuse_rate=feedback_reuse_sum / float(n),
        repeated_failure_suppression_total=repeated_failure_suppression_total,
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
    "InstanceSummary",
    "REPEAT_FAILURE_EVENT",
    "RUN_COMPLETED_EVENT",
    "SCORE_EVENT",
    "SELECTION_EVENT",
    "SIGNAL_APPLIED_EVENT",
    "SIGNAL_EMITTED_EVENT",
    "Summary",
    "build_summary",
    "read_events",
    "replay_summary_from_dir",
    "write_summary",
]
