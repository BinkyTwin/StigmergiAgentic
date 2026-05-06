"""V11 Stigmergic Medium Kernel.

The EventLog remains the source of truth. This in-memory kernel is the live
projection used during a run and the replay target rebuilt from event streams.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Sequence

from core_v10.contracts import Candidate, FeedbackDigest, JsonDict, ValidationResult
from core_v10.event_log import EventRecord
from core_v10.signal_policy import (
    PolicyEffect,
    reinforce_origin,
    SIGNAL_EMITTED_EVENT,
    store_from_events,
    update_from_feedback,
)
from core_v10.signals import SignalRecord, SignalStore
from core_v10.stigmergy.affordances import affordances_from_feedback
from core_v10.stigmergy.events import (
    AFFORDANCE_CONSUMED_EVENT,
    AFFORDANCE_CREATED_EVENT,
    AFFORDANCE_EXPIRED_EVENT,
    AFFORDANCE_INHIBITED_EVENT,
    SIGNAL_DECAYED_EVENT,
    SIGNAL_RETIRED_EVENT,
)
from core_v10.stigmergy.records import (
    Affordance,
    DecisionInfluence,
    SignalRead,
)


class StigmergicMediumKernel:
    """Active, typed, replayable V11 stigmergic medium."""

    def __init__(self, *, signal_store: SignalStore | None = None) -> None:
        self.signal_store = signal_store or SignalStore()
        self._affordances: dict[str, Affordance] = {}
        self._consumed_affordances: set[str] = set()
        self._expired_affordances: set[str] = set()
        self._inhibited_affordances: set[str] = set()
        self._retired_signals: set[str] = set()

    def emit_from_feedback(
        self,
        *,
        feedback: FeedbackDigest,
        candidate: Candidate,
        event_context: JsonDict | None = None,
        now_seq: int = 0,
    ) -> tuple[PolicyEffect, ...]:
        """Emit verifier-gated feedback signals into the medium."""

        effects = update_from_feedback(
            self.signal_store,
            feedback=feedback,
            candidate=candidate,
            now_seq=now_seq,
        )
        # V11 provenance is carried in the EventLog payload by the caller; the
        # SignalStore remains backward-compatible with Phase 6 records.
        _ = event_context
        return effects

    def emit_from_success(
        self,
        *,
        validation: ValidationResult,
        candidate: Candidate,
        event_context: JsonDict | None = None,
        now_seq: int = 0,
    ) -> tuple[PolicyEffect, ...]:
        """Emit support/reinforcement signals from a passed verifier result."""

        _ = event_context
        return reinforce_origin(
            self.signal_store,
            candidate=candidate,
            validation=validation,
            now_seq=now_seq,
        )

    def create_affordances(
        self,
        *,
        feedback: FeedbackDigest,
        signals: Sequence[SignalRecord] = (),
        context: JsonDict | None = None,
        now_seq: int = 0,
    ) -> tuple[Affordance, ...]:
        """Create affordances from feedback and currently active signals."""

        context = dict(context or {})
        created = affordances_from_feedback(
            feedback=feedback,
            signals=signals,
            source_event_ids=tuple(str(x) for x in context.get("source_event_ids", ())),
            now_seq=now_seq,
        )
        for affordance in created:
            self._affordances[affordance.affordance_id] = affordance
        return created

    def read(
        self,
        *,
        actor: str,
        decision_id: str,
        region: str,
        query: JsonDict | None = None,
        top_k: int = 3,
        read_policy: str = "top_k_by_activation",
    ) -> SignalRead:
        """Return a local view and record what was seen."""

        signals = self.top_signals(top_k=top_k)
        affordances = self.top_affordances(top_k=top_k)
        return SignalRead(
            actor=actor,
            decision_id=decision_id,
            region=region,
            read_policy=read_policy,
            query=dict(query or {}),
            signals_seen=tuple(record.signal_id for record in signals),
            affordances_seen=tuple(aff.affordance_id for aff in affordances),
        )

    def influence(
        self,
        *,
        decision_id: str,
        decision_kind: str,
        actor: str,
        baseline_choice: JsonDict,
        stigmergic_choice: JsonDict,
        signals_used: Sequence[str] = (),
        affordances_used: Sequence[str] = (),
        effect: str = "decision_changed",
    ) -> DecisionInfluence:
        """Return a typed influence record."""

        return DecisionInfluence(
            decision_id=decision_id,
            decision_kind=decision_kind,
            actor=actor,
            baseline_choice=dict(baseline_choice),
            stigmergic_choice=dict(stigmergic_choice),
            signals_used=tuple(str(x) for x in signals_used),
            affordances_used=tuple(str(x) for x in affordances_used),
            effect=effect,
        )

    def decay(self, now_seq: int) -> None:
        self.signal_store.decay(now_seq=now_seq)

    def retire(self, signal_id: str, reason: str) -> None:
        _ = reason
        self._retired_signals.add(str(signal_id))

    def consume_affordance(self, affordance_id: str) -> Affordance | None:
        affordance = self._affordances.get(affordance_id)
        if affordance is not None:
            self._consumed_affordances.add(affordance_id)
        return affordance

    def expire_affordance(self, affordance_id: str) -> Affordance | None:
        affordance = self._affordances.get(affordance_id)
        if affordance is not None:
            self._expired_affordances.add(affordance_id)
        return affordance

    def inhibit_affordance(self, affordance_id: str) -> Affordance | None:
        affordance = self._affordances.get(affordance_id)
        if affordance is not None:
            self._inhibited_affordances.add(affordance_id)
        return affordance

    def top_signals(self, *, top_k: int = 3) -> tuple[SignalRecord, ...]:
        records = [
            record
            for record in self.signal_store.items()
            if record.signal_id not in self._retired_signals
        ]
        return tuple(
            sorted(records, key=lambda record: (-record.intensity, record.target))[
                : max(0, int(top_k))
            ]
        )

    def top_affordances(self, *, top_k: int = 3) -> tuple[Affordance, ...]:
        active = [
            affordance
            for affordance in self._affordances.values()
            if affordance.affordance_id not in self._inactive_affordance_ids()
        ]
        return tuple(
            sorted(active, key=lambda aff: (-aff.priority, aff.affordance_id))[
                : max(0, int(top_k))
            ]
        )

    def _inactive_affordance_ids(self) -> set[str]:
        return (
            set(self._consumed_affordances)
            | set(self._expired_affordances)
            | set(self._inhibited_affordances)
        )

    def snapshot(self) -> JsonDict:
        return {
            "signals": self.signal_store.to_dict(),
            "affordances": [aff.to_dict() for aff in self.top_affordances(top_k=10_000)],
            "consumed_affordance_ids": sorted(self._consumed_affordances),
            "expired_affordance_ids": sorted(self._expired_affordances),
            "inhibited_affordance_ids": sorted(self._inhibited_affordances),
            "retired_signal_ids": sorted(self._retired_signals),
        }

    @classmethod
    def from_events(cls, events: Iterable[EventRecord]) -> "StigmergicMediumKernel":
        """Rebuild the medium from signal and affordance events."""

        ordered = sorted(list(events), key=lambda event: event.sequence)
        medium = cls(signal_store=store_from_events(ordered))
        for event in ordered:
            payload = event.payload or {}
            if event.event_type == AFFORDANCE_CREATED_EVENT:
                data = payload.get("affordance") or payload
                try:
                    affordance = Affordance.from_dict(data)
                except (KeyError, TypeError, ValueError):
                    continue
                medium._affordances[affordance.affordance_id] = affordance
            elif event.event_type == AFFORDANCE_CONSUMED_EVENT:
                _remember_affordance_lifecycle(
                    medium._consumed_affordances,
                    payload,
                )
            elif event.event_type == AFFORDANCE_EXPIRED_EVENT:
                _remember_affordance_lifecycle(
                    medium._expired_affordances,
                    payload,
                )
            elif event.event_type == AFFORDANCE_INHIBITED_EVENT:
                _remember_affordance_lifecycle(
                    medium._inhibited_affordances,
                    payload,
                )
            elif event.event_type == SIGNAL_RETIRED_EVENT:
                signal_id = _signal_id_from_payload(payload)
                if signal_id:
                    medium._retired_signals.add(signal_id)
            elif event.event_type in {SIGNAL_DECAYED_EVENT, SIGNAL_EMITTED_EVENT}:
                record_data = payload.get("record")
                if isinstance(record_data, dict):
                    try:
                        record = SignalRecord.from_dict(record_data)
                    except (KeyError, TypeError, ValueError):
                        continue
                    medium.signal_store._records[(record.kind, record.target)] = record  # type: ignore[attr-defined]
        return medium


def _remember_affordance_lifecycle(target: set[str], payload: JsonDict) -> None:
    affordance_id = str(payload.get("affordance_id") or "")
    if not affordance_id:
        affordance = payload.get("affordance")
        if isinstance(affordance, dict):
            affordance_id = str(affordance.get("affordance_id") or "")
    if affordance_id:
        target.add(affordance_id)


def _signal_id_from_payload(payload: JsonDict) -> str:
    if payload.get("signal_id"):
        return str(payload["signal_id"])
    record = payload.get("record")
    if isinstance(record, dict) and record.get("signal_id"):
        return str(record["signal_id"])
    return ""


__all__ = ["StigmergicMediumKernel"]
