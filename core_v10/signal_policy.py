"""Pure feedback→signal policy used by the A4 stigmergic strategy (Phase 6).

The policy is intentionally deterministic, side-effect-free apart from the
``SignalStore`` mutations it requests, and free of LLM/network access. This
keeps it unit-testable and replayable.

The policy turns the verifier's structured outputs into the canonical signal
shapes pre-registered in
``documentation/decisions/20260505-phase-6-stigmergic-blackboard-a4.md``:

* feedback (``failure_type``, severity, anti_actions) → ``INHIBIT`` signals;
* validated candidates → ``SUPPORT`` (origin) and ``REINFORCE`` (kind);
* repeat-failure suppression → ``INHIBIT signature:<sha>``;
* multi-hypothesis runs → ``NOVELTY``.

Every mutation is observable from outside via :class:`PolicyEffect` so the
strategy runner can persist a ``signal.emitted`` event with the exact same
content the policy applied to the store.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from core_v10.contracts import Candidate, FeedbackDigest, ValidationResult
from core_v10.signals import (
    DEFAULT_HALF_LIFE,
    SignalKind,
    SignalRecord,
    SignalStore,
)


# ---------------------------------------------------------------------------
# Tunables — pre-registered in ADR 20260505 (intensities + deltas)
# ---------------------------------------------------------------------------


INHIBIT_FAILURE_TYPE_BASE: float = 0.5
"""Initial INHIBIT intensity for a brand-new failure_type."""

INHIBIT_FAILURE_TYPE_BLOCKING: float = 0.8
"""Initial INHIBIT intensity when severity is blocking/fatal."""

INHIBIT_FAILURE_TYPE_DELTA: float = 0.1
"""Reinforcement delta applied each time a failure_type repeats."""

INHIBIT_ANTI_ACTION_BASE: float = 0.6
"""Initial INHIBIT intensity for a tracked anti_action (e.g. preserve_existing_tests)."""

INHIBIT_ANTI_ACTION_DELTA: float = 0.05
"""Reinforcement delta applied each time the same anti_action recurs."""

SUPPORT_ORIGIN_BASE: float = 0.7
"""Initial SUPPORT intensity for an origin that just produced a validated candidate."""

REINFORCE_KIND_BASE: float = 0.5
"""Initial REINFORCE intensity for a kind that just produced a validated candidate."""

INHIBIT_SIGNATURE_BASE: float = 0.9
"""INHIBIT intensity for a candidate signature whose hypothesis already failed."""

NOVELTY_DIVISOR: float = 10.0
"""Divisor for the NOVELTY hypothesis-space intensity (clamp(n / divisor))."""


_TRACKED_ANTI_ACTIONS: tuple[str, ...] = ("preserve_existing_tests",)


# ---------------------------------------------------------------------------
# Effects — what the policy decided to write
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PolicyEffect:
    """A single store mutation applied by the policy.

    The runner is expected to persist one ``signal.emitted`` event per
    effect so the EventLog remains the source of truth for the store.
    """

    kind: SignalKind
    target: str
    intensity: float
    evidence: tuple[str, ...]
    op: str  # "emit" | "reinforce" | "inhibit"
    half_life: int = DEFAULT_HALF_LIFE
    rationale: str = ""


def _failure_type_target(failure_type: str) -> str:
    return f"failure_type:{failure_type}"


def _anti_action_target(anti: str) -> str:
    return f"anti:{anti}"


def _origin_target(origin: str) -> str:
    return f"origin:{origin}"


def _kind_target(kind: str) -> str:
    return f"kind:{kind}"


def _signature_target(signature: str) -> str:
    return f"signature:{signature}"


# ---------------------------------------------------------------------------
# Policy entry points
# ---------------------------------------------------------------------------


def update_from_feedback(
    store: SignalStore,
    *,
    feedback: FeedbackDigest,
    candidate: Candidate,
    now_seq: int,
) -> tuple[PolicyEffect, ...]:
    """Translate one verifier feedback into INHIBIT signals on ``store``.

    Always emits at least one effect (the failure_type INHIBIT) when the
    feedback is non-trivial; otherwise returns an empty tuple.
    """

    if not feedback.failure_type:
        return ()
    effects: list[PolicyEffect] = []

    target = _failure_type_target(feedback.failure_type)
    existing = store.get(SignalKind.INHIBIT, target)
    if existing is None:
        intensity = (
            INHIBIT_FAILURE_TYPE_BLOCKING
            if feedback.is_blocking
            else INHIBIT_FAILURE_TYPE_BASE
        )
        op = "emit"
        delta = intensity
    else:
        op = "reinforce"
        delta = INHIBIT_FAILURE_TYPE_DELTA
        intensity = delta
    record = (
        store.emit(
            kind=SignalKind.INHIBIT,
            target=target,
            intensity=intensity,
            now_seq=now_seq,
            evidence=(candidate.candidate_id,),
        )
        if existing is None
        else store.reinforce(
            kind=SignalKind.INHIBIT,
            target=target,
            delta=delta,
            now_seq=now_seq,
            evidence=(candidate.candidate_id,),
        )
    )
    effects.append(
        PolicyEffect(
            kind=record.kind,
            target=record.target,
            intensity=record.intensity,
            evidence=(candidate.candidate_id,),
            op=op,
            half_life=record.half_life,
            rationale=f"feedback:{feedback.failure_type}",
        )
    )

    for anti in feedback.anti_actions:
        if anti not in _TRACKED_ANTI_ACTIONS:
            continue
        atarget = _anti_action_target(anti)
        a_existing = store.get(SignalKind.INHIBIT, atarget)
        if a_existing is None:
            a_record = store.emit(
                kind=SignalKind.INHIBIT,
                target=atarget,
                intensity=INHIBIT_ANTI_ACTION_BASE,
                now_seq=now_seq,
                evidence=(candidate.candidate_id,),
            )
            a_op = "emit"
        else:
            a_record = store.reinforce(
                kind=SignalKind.INHIBIT,
                target=atarget,
                delta=INHIBIT_ANTI_ACTION_DELTA,
                now_seq=now_seq,
                evidence=(candidate.candidate_id,),
            )
            a_op = "reinforce"
        effects.append(
            PolicyEffect(
                kind=a_record.kind,
                target=a_record.target,
                intensity=a_record.intensity,
                evidence=(candidate.candidate_id,),
                op=a_op,
                half_life=a_record.half_life,
                rationale=f"anti_action:{anti}",
            )
        )

    return tuple(effects)


def reinforce_origin(
    store: SignalStore,
    *,
    candidate: Candidate,
    validation: ValidationResult,
    now_seq: int,
) -> tuple[PolicyEffect, ...]:
    """Emit SUPPORT/REINFORCE signals for a validated candidate."""

    if not validation.passed:
        return ()
    effects: list[PolicyEffect] = []
    origin_record = store.emit(
        kind=SignalKind.SUPPORT,
        target=_origin_target(candidate.origin),
        intensity=SUPPORT_ORIGIN_BASE,
        now_seq=now_seq,
        evidence=(candidate.candidate_id,),
    )
    effects.append(
        PolicyEffect(
            kind=origin_record.kind,
            target=origin_record.target,
            intensity=origin_record.intensity,
            evidence=(candidate.candidate_id,),
            op="emit",
            half_life=origin_record.half_life,
            rationale=f"validation_passed:{candidate.origin}",
        )
    )
    kind_record = store.emit(
        kind=SignalKind.REINFORCE,
        target=_kind_target(candidate.kind.value),
        intensity=REINFORCE_KIND_BASE,
        now_seq=now_seq,
        evidence=(candidate.candidate_id,),
    )
    effects.append(
        PolicyEffect(
            kind=kind_record.kind,
            target=kind_record.target,
            intensity=kind_record.intensity,
            evidence=(candidate.candidate_id,),
            op="emit",
            half_life=kind_record.half_life,
            rationale=f"validation_passed_kind:{candidate.kind.value}",
        )
    )
    return tuple(effects)


def inhibit_signature(
    store: SignalStore,
    *,
    signature: str,
    evidence_id: str,
    now_seq: int,
) -> PolicyEffect:
    """Emit a strong INHIBIT on a signature that just failed."""

    record = store.emit(
        kind=SignalKind.INHIBIT,
        target=_signature_target(signature),
        intensity=INHIBIT_SIGNATURE_BASE,
        now_seq=now_seq,
        evidence=(evidence_id,),
    )
    return PolicyEffect(
        kind=record.kind,
        target=record.target,
        intensity=record.intensity,
        evidence=(evidence_id,),
        op="emit",
        half_life=record.half_life,
        rationale=f"failed_signature:{signature}",
    )


def emit_novelty(
    store: SignalStore,
    *,
    hypothesis_count: int,
    now_seq: int,
    evidence: Sequence[str] = (),
) -> PolicyEffect | None:
    """Emit a NOVELTY signal when more than one hypothesis is alive."""

    if hypothesis_count <= 1:
        return None
    intensity = min(1.0, max(0.0, hypothesis_count / NOVELTY_DIVISOR))
    record = store.emit(
        kind=SignalKind.NOVELTY,
        target="hypothesis_space",
        intensity=intensity,
        now_seq=now_seq,
        evidence=evidence,
    )
    return PolicyEffect(
        kind=record.kind,
        target=record.target,
        intensity=record.intensity,
        evidence=tuple(evidence),
        op="emit",
        half_life=record.half_life,
        rationale=f"hypothesis_count:{hypothesis_count}",
    )


# ---------------------------------------------------------------------------
# Digest — top-K supports / inhibitions for downstream consumers (LLM, etc.)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Digest:
    """Top-K view over a :class:`SignalStore` used by the LLM digest block."""

    top_inhibitions: tuple[SignalRecord, ...]
    top_supports: tuple[SignalRecord, ...]
    top_novelties: tuple[SignalRecord, ...]

    def to_dict(self) -> dict:
        return {
            "top_inhibitions": [r.to_dict() for r in self.top_inhibitions],
            "top_supports": [r.to_dict() for r in self.top_supports],
            "top_novelties": [r.to_dict() for r in self.top_novelties],
        }

    @property
    def is_empty(self) -> bool:
        return not (
            self.top_inhibitions or self.top_supports or self.top_novelties
        )


def digest(store: SignalStore, *, top_k: int = 3) -> Digest:
    """Return the top-K signals per kind (INHIBIT, SUPPORT, NOVELTY)."""

    def _top(kind: SignalKind) -> tuple[SignalRecord, ...]:
        records = sorted(
            store.by_kind(kind),
            key=lambda r: (-float(r.intensity), r.target),
        )
        return tuple(records[: max(0, int(top_k))])

    return Digest(
        top_inhibitions=_top(SignalKind.INHIBIT),
        top_supports=_top(SignalKind.SUPPORT),
        top_novelties=_top(SignalKind.NOVELTY),
    )


# ---------------------------------------------------------------------------
# Reconstruction from EventLog
# ---------------------------------------------------------------------------


SIGNAL_EMITTED_EVENT = "signal.emitted"
SIGNAL_APPLIED_EVENT = "signal.applied"


def store_from_events(events: Iterable) -> SignalStore:
    """Rebuild a :class:`SignalStore` from ``signal.emitted`` events.

    Replays the events in sequence order; the resulting store is bit-identical
    to the live store at the end of the run for any deterministic policy.
    """

    store = SignalStore()
    sorted_events = sorted(
        list(events),
        key=lambda e: getattr(e, "sequence", 0),
    )
    for event in sorted_events:
        if getattr(event, "event_type", None) != SIGNAL_EMITTED_EVENT:
            continue
        payload = getattr(event, "payload", {}) or {}
        record_data = payload.get("record") or {}
        if not record_data:
            continue
        try:
            record = SignalRecord.from_dict(record_data)
        except (KeyError, ValueError):
            continue
        store._records[(record.kind, record.target)] = record  # type: ignore[attr-defined]
    return store


__all__ = [
    "Digest",
    "INHIBIT_ANTI_ACTION_BASE",
    "INHIBIT_ANTI_ACTION_DELTA",
    "INHIBIT_FAILURE_TYPE_BASE",
    "INHIBIT_FAILURE_TYPE_BLOCKING",
    "INHIBIT_FAILURE_TYPE_DELTA",
    "INHIBIT_SIGNATURE_BASE",
    "NOVELTY_DIVISOR",
    "PolicyEffect",
    "REINFORCE_KIND_BASE",
    "SIGNAL_APPLIED_EVENT",
    "SIGNAL_EMITTED_EVENT",
    "SUPPORT_ORIGIN_BASE",
    "digest",
    "emit_novelty",
    "inhibit_signature",
    "reinforce_origin",
    "store_from_events",
    "update_from_feedback",
]
