"""Typed records for the V11 stigmergic medium."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from core_v10.contracts import JsonDict, to_jsonable


def stable_v11_id(prefix: str, payload: JsonDict) -> str:
    """Return a compact deterministic id from a JSON-compatible payload."""

    canonical = json.dumps(
        to_jsonable(payload),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


@dataclass(frozen=True)
class Affordance:
    """Actionable opportunity derived from verifier feedback and signals."""

    affordance_id: str
    action_type: str
    target: str
    reason: str
    priority: float
    source_event_ids: tuple[str, ...] = ()
    source_signal_ids: tuple[str, ...] = ()
    expected_worker_kind: str | None = None
    expires_at_seq: int | None = None
    metadata: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "affordance_id": self.affordance_id,
            "action_type": self.action_type,
            "target": self.target,
            "reason": self.reason,
            "priority": float(self.priority),
            "source_event_ids": list(self.source_event_ids),
            "source_signal_ids": list(self.source_signal_ids),
            "expected_worker_kind": self.expected_worker_kind,
            "expires_at_seq": self.expires_at_seq,
            "metadata": to_jsonable(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "Affordance":
        return cls(
            affordance_id=str(data["affordance_id"]),
            action_type=str(data["action_type"]),
            target=str(data["target"]),
            reason=str(data.get("reason", "")),
            priority=float(data.get("priority", 0.0)),
            source_event_ids=tuple(str(x) for x in data.get("source_event_ids", ())),
            source_signal_ids=tuple(str(x) for x in data.get("source_signal_ids", ())),
            expected_worker_kind=(
                str(data["expected_worker_kind"])
                if data.get("expected_worker_kind") is not None
                else None
            ),
            expires_at_seq=(
                int(data["expires_at_seq"])
                if data.get("expires_at_seq") is not None
                else None
            ),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True)
class SignalRead:
    """Trace that a component locally read a typed medium region."""

    actor: str
    decision_id: str
    region: str
    read_policy: str
    query: JsonDict
    signals_seen: tuple[str, ...] = ()
    affordances_seen: tuple[str, ...] = ()

    def to_dict(self) -> JsonDict:
        return {
            "actor": self.actor,
            "decision_id": self.decision_id,
            "region": self.region,
            "read_policy": self.read_policy,
            "query": to_jsonable(self.query),
            "signals_seen": list(self.signals_seen),
            "affordances_seen": list(self.affordances_seen),
        }


@dataclass(frozen=True)
class DecisionInfluence:
    """Counterfactual explanation for a stigmergy-influenced decision."""

    decision_id: str
    decision_kind: str
    actor: str
    baseline_choice: JsonDict
    stigmergic_choice: JsonDict
    signals_used: tuple[str, ...] = ()
    affordances_used: tuple[str, ...] = ()
    effect: str = "decision_changed"

    @property
    def changed(self) -> bool:
        return self.baseline_choice != self.stigmergic_choice

    def to_dict(self) -> JsonDict:
        return {
            "decision_id": self.decision_id,
            "decision_kind": self.decision_kind,
            "actor": self.actor,
            "baseline_choice": to_jsonable(self.baseline_choice),
            "stigmergic_choice": to_jsonable(self.stigmergic_choice),
            "signals_used": list(self.signals_used),
            "affordances_used": list(self.affordances_used),
            "effect": self.effect,
            "changed": self.changed,
        }


@dataclass(frozen=True)
class TrajectoryDivergence:
    """Comparable divergence point between a control and V11 treatment path."""

    instance_id: str
    control_arm: str
    treatment_arm: str
    divergence_point: str
    decision_id: str
    cause: str
    signals_used: tuple[str, ...] = ()
    affordances_used: tuple[str, ...] = ()
    downstream_delta: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "instance_id": self.instance_id,
            "control_arm": self.control_arm,
            "treatment_arm": self.treatment_arm,
            "divergence_point": self.divergence_point,
            "decision_id": self.decision_id,
            "cause": self.cause,
            "signals_used": list(self.signals_used),
            "affordances_used": list(self.affordances_used),
            "downstream_delta": to_jsonable(self.downstream_delta),
        }


@dataclass(frozen=True)
class WorkerSpec:
    """Static worker declaration consumed by the scheduler."""

    worker_id: str
    worker_kind: str
    reads: tuple[str, ...]
    writes: tuple[str, ...]
    handles: tuple[str, ...]
    cost: float = 0.0
    risk: float = 0.0

    def to_dict(self) -> JsonDict:
        return {
            "worker_id": self.worker_id,
            "worker_kind": self.worker_kind,
            "reads": list(self.reads),
            "writes": list(self.writes),
            "handles": list(self.handles),
            "cost": float(self.cost),
            "risk": float(self.risk),
        }


@dataclass(frozen=True)
class WorkerActivation:
    """Scheduler choice for one worker-affordance pair."""

    decision_id: str
    worker: WorkerSpec
    affordance: Affordance | None
    activation_score: float
    score_terms: JsonDict
    source_signal_ids: tuple[str, ...] = ()
    competitors: tuple[JsonDict, ...] = ()

    def to_dict(self) -> JsonDict:
        return {
            "decision_id": self.decision_id,
            "worker_id": self.worker.worker_id,
            "worker_kind": self.worker.worker_kind,
            "affordance_id": (
                self.affordance.affordance_id if self.affordance is not None else None
            ),
            "activation_score": float(self.activation_score),
            "score_terms": to_jsonable(self.score_terms),
            "source_signal_ids": list(self.source_signal_ids),
            "competitors": [dict(item) for item in self.competitors],
        }


@dataclass(frozen=True)
class OperatorInvocation:
    """Typed operator request attached to a candidate."""

    operator_id: str
    params: JsonDict
    target_files: tuple[str, ...]
    rationale: str
    source_affordance_id: str | None = None

    def to_dict(self) -> JsonDict:
        return {
            "operator_id": self.operator_id,
            "params": to_jsonable(self.params),
            "target_files": list(self.target_files),
            "rationale": self.rationale,
            "source_affordance_id": self.source_affordance_id,
        }

    @classmethod
    def from_any(cls, value: Any) -> "OperatorInvocation | None":
        if isinstance(value, OperatorInvocation):
            return value
        if not isinstance(value, dict) or "operator_id" not in value:
            return None
        return cls(
            operator_id=str(value["operator_id"]),
            params=dict(value.get("params") or {}),
            target_files=tuple(str(x) for x in value.get("target_files", ())),
            rationale=str(value.get("rationale", "")),
            source_affordance_id=(
                str(value["source_affordance_id"])
                if value.get("source_affordance_id") is not None
                else None
            ),
        )


__all__ = [
    "Affordance",
    "DecisionInfluence",
    "OperatorInvocation",
    "SignalRead",
    "TrajectoryDivergence",
    "WorkerActivation",
    "WorkerSpec",
    "stable_v11_id",
]
