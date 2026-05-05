"""Structured V10 coordination signals and active SignalStore (Phase 6 A4).

Signals are the first concrete form of the V10 stigmergic layer: compact,
inspectable traces that can support, inhibit, reinforce, or diversify future
actions without direct agent-to-agent messaging.

This module exposes two layers:

* the lightweight ``CoordinationSignal`` projection used by Phase 5 and below,
  derived post-hoc from the hypothesis graph;
* the active ``SignalStore`` introduced in Phase 6 (A4 strategy), which
  receives writes during a run, applies time decay, and is fully
  reconstructible from the EventLog (``signal.emitted`` events).

The store is intentionally small and deterministic: every state transition is
serializable and replayable so that ``live==replay`` stays true on A4 runs.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Iterable, Sequence

from core_v10.contracts import JsonDict, to_jsonable


class SignalKind(str, Enum):
    """Supported coordination signal types."""

    SUPPORT = "support"
    INHIBIT = "inhibit"
    REINFORCE = "reinforce"
    NOVELTY = "novelty"
    CONFIDENCE = "confidence"


@dataclass(frozen=True)
class CoordinationSignal:
    """Actionable blackboard signal derived from runtime evidence.

    Used by ``BlackboardSnapshot`` for the post-hoc projection. Phase 6
    keeps this representation for backward compatibility; the active
    write surface is ``SignalRecord`` / ``SignalStore`` below.
    """

    kind: SignalKind
    target: str
    intensity: float
    source: str
    hypothesis_id: str | None = None
    rationale: str = ""
    metadata: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        """Return a JSON-friendly signal representation."""

        return {
            "kind": self.kind.value,
            "target": self.target,
            "intensity": self.intensity,
            "source": self.source,
            "hypothesis_id": self.hypothesis_id,
            "rationale": self.rationale,
            "metadata": to_jsonable(self.metadata),
        }


def clamp_intensity(value: float) -> float:
    """Clamp signal intensity to the public 0..1 range."""

    return max(0.0, min(1.0, value))


# ---------------------------------------------------------------------------
# Phase 6 — active SignalStore
# ---------------------------------------------------------------------------


DEFAULT_HALF_LIFE: int = 8
"""Default half-life (in event-log sequence units) used for signal decay."""


@dataclass(frozen=True)
class SignalRecord:
    """Active stigmergic signal tracked inside :class:`SignalStore`.

    A record's identity is the ``(kind, target)`` pair. ``intensity`` evolves
    over the run via ``emit`` / ``reinforce`` / ``inhibit`` (writes) and
    ``decay`` (time-based attenuation). The ``evidence`` tuple records the
    event ids or hypothesis ids that justified each write.
    """

    kind: SignalKind
    target: str
    intensity: float
    evidence: tuple[str, ...] = ()
    half_life: int = DEFAULT_HALF_LIFE
    created_at_seq: int = 0
    last_seen_seq: int = 0
    emit_count: int = 1

    @property
    def signal_id(self) -> str:
        """Stable identifier derived from the ``(kind, target)`` pair."""

        return signal_id_for(self.kind, self.target)

    def to_dict(self) -> JsonDict:
        """Return a JSON-friendly representation suitable for events."""

        return {
            "signal_id": self.signal_id,
            "kind": self.kind.value,
            "target": self.target,
            "intensity": float(self.intensity),
            "evidence": list(self.evidence),
            "half_life": int(self.half_life),
            "created_at_seq": int(self.created_at_seq),
            "last_seen_seq": int(self.last_seen_seq),
            "emit_count": int(self.emit_count),
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "SignalRecord":
        """Rebuild a record from its JSON form."""

        return cls(
            kind=SignalKind(str(data["kind"])),
            target=str(data["target"]),
            intensity=float(data["intensity"]),
            evidence=tuple(str(e) for e in (data.get("evidence") or ())),
            half_life=int(data.get("half_life", DEFAULT_HALF_LIFE)),
            created_at_seq=int(data.get("created_at_seq", 0)),
            last_seen_seq=int(data.get("last_seen_seq", 0)),
            emit_count=int(data.get("emit_count", 1)),
        )


def signal_id_for(kind: SignalKind, target: str) -> str:
    """Return the deterministic id for a ``(kind, target)`` pair."""

    raw = f"{kind.value}:{target}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _decay_intensity(
    intensity: float, *, last_seq: int, now_seq: int, half_life: int
) -> float:
    """Apply half-life decay between ``last_seq`` and ``now_seq``."""

    if half_life <= 0:
        return clamp_intensity(intensity)
    elapsed = max(0, int(now_seq) - int(last_seq))
    if elapsed == 0:
        return clamp_intensity(intensity)
    factor = 0.5 ** (elapsed / float(half_life))
    return clamp_intensity(intensity * factor)


class SignalStore:
    """Active write-surface for stigmergic signals.

    The store is a light abstraction over a ``dict`` keyed on
    ``(kind, target)``. It is not thread-safe by design — strategies execute
    instances sequentially. Every mutation is exposed via the iterators so the
    runner can persist a ``signal.emitted`` event and replay can reconstruct
    the store from the EventLog.
    """

    def __init__(self) -> None:
        self._records: dict[tuple[SignalKind, str], SignalRecord] = {}

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self):
        return iter(self._records.values())

    def get(
        self, kind: SignalKind, target: str
    ) -> SignalRecord | None:
        """Return the active record for ``(kind, target)`` or ``None``."""

        return self._records.get((kind, target))

    def by_kind(self, kind: SignalKind) -> tuple[SignalRecord, ...]:
        """Return all active records of one kind."""

        return tuple(
            record for record in self._records.values() if record.kind == kind
        )

    def support_for(self, target: str, kind: SignalKind = SignalKind.SUPPORT) -> float:
        """Return the current intensity for ``(kind, target)``, or 0.0."""

        record = self._records.get((kind, target))
        return float(record.intensity) if record is not None else 0.0

    def inhibit_for(self, target: str) -> float:
        """Convenience: return the current INHIBIT intensity for ``target``."""

        return self.support_for(target, kind=SignalKind.INHIBIT)

    def items(self) -> tuple[SignalRecord, ...]:
        """Return all records in deterministic order (kind, target)."""

        return tuple(
            self._records[key]
            for key in sorted(self._records.keys(), key=lambda k: (k[0].value, k[1]))
        )

    def to_dict(self) -> JsonDict:
        """Return a JSON-friendly snapshot of every record."""

        return {"records": [record.to_dict() for record in self.items()]}

    # ------------------------------------------------------------------
    # Mutations — every write also bumps last_seen_seq for decay tracking
    # ------------------------------------------------------------------

    def emit(
        self,
        *,
        kind: SignalKind,
        target: str,
        intensity: float,
        now_seq: int,
        evidence: Sequence[str] = (),
        half_life: int = DEFAULT_HALF_LIFE,
    ) -> SignalRecord:
        """Insert or upsert a signal at ``(kind, target)``.

        If a record already exists, the new intensity is merged via ``max`` to
        keep the strongest evidence visible; the evidence list is appended.
        """

        key = (kind, target)
        existing = self._records.get(key)
        if existing is None:
            record = SignalRecord(
                kind=kind,
                target=target,
                intensity=clamp_intensity(intensity),
                evidence=tuple(str(e) for e in evidence),
                half_life=int(half_life),
                created_at_seq=int(now_seq),
                last_seen_seq=int(now_seq),
                emit_count=1,
            )
        else:
            decayed = _decay_intensity(
                existing.intensity,
                last_seq=existing.last_seen_seq,
                now_seq=now_seq,
                half_life=existing.half_life,
            )
            new_intensity = max(decayed, clamp_intensity(intensity))
            record = replace(
                existing,
                intensity=new_intensity,
                evidence=existing.evidence + tuple(str(e) for e in evidence),
                last_seen_seq=int(now_seq),
                emit_count=existing.emit_count + 1,
            )
        self._records[key] = record
        return record

    def reinforce(
        self,
        *,
        target: str,
        kind: SignalKind = SignalKind.SUPPORT,
        delta: float,
        now_seq: int,
        evidence: Sequence[str] = (),
    ) -> SignalRecord:
        """Increase intensity by ``delta`` (after decaying)."""

        existing = self._records.get((kind, target))
        base = (
            _decay_intensity(
                existing.intensity,
                last_seq=existing.last_seen_seq,
                now_seq=now_seq,
                half_life=existing.half_life,
            )
            if existing is not None
            else 0.0
        )
        return self.emit(
            kind=kind,
            target=target,
            intensity=base + float(delta),
            now_seq=now_seq,
            evidence=evidence,
            half_life=(
                existing.half_life if existing is not None else DEFAULT_HALF_LIFE
            ),
        )

    def inhibit(
        self,
        *,
        target: str,
        delta: float,
        now_seq: int,
        evidence: Sequence[str] = (),
        half_life: int = DEFAULT_HALF_LIFE,
    ) -> SignalRecord:
        """Increase the INHIBIT intensity at ``target`` by ``delta``."""

        return self.reinforce(
            target=target,
            kind=SignalKind.INHIBIT,
            delta=delta,
            now_seq=now_seq,
            evidence=evidence,
        )

    def decay(self, now_seq: int) -> None:
        """Apply half-life decay to every record up to ``now_seq``.

        This is idempotent — repeated calls with the same ``now_seq`` keep the
        record stable (decay is computed from ``last_seen_seq`` which is
        bumped on every decay pass).
        """

        for key, record in list(self._records.items()):
            new_intensity = _decay_intensity(
                record.intensity,
                last_seq=record.last_seen_seq,
                now_seq=now_seq,
                half_life=record.half_life,
            )
            self._records[key] = replace(
                record,
                intensity=new_intensity,
                last_seen_seq=int(now_seq),
            )

    # ------------------------------------------------------------------
    # Replay
    # ------------------------------------------------------------------

    @classmethod
    def from_records(cls, records: Iterable[SignalRecord]) -> "SignalStore":
        """Rebuild a store from a sequence of records (e.g. from a snapshot)."""

        store = cls()
        for record in records:
            store._records[(record.kind, record.target)] = record
        return store

    @classmethod
    def from_events(cls, events) -> "SignalStore":  # pragma: no cover - thin shim
        """Rebuild a store by replaying ``signal.emitted`` events.

        The full implementation lives in :mod:`core_v10.signal_policy` to avoid
        a circular import; this method delegates to it.
        """

        from core_v10.signal_policy import store_from_events

        return store_from_events(events)


__all__ = [
    "DEFAULT_HALF_LIFE",
    "CoordinationSignal",
    "SignalKind",
    "SignalRecord",
    "SignalStore",
    "clamp_intensity",
    "signal_id_for",
]
