"""Deterministic V11 worker scheduler."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from core_v10.contracts import FeedbackDigest, JsonDict
from core_v10.signals import SignalKind, SignalRecord
from core_v10.stigmergy.records import (
    Affordance,
    WorkerActivation,
    WorkerSpec,
)


def default_worker_specs() -> tuple[WorkerSpec, ...]:
    """Return the initial V11 worker registry."""

    common_reads = (
        "observation_region",
        "verification_region",
        "repair_region",
        "affordance_region",
    )
    return (
        WorkerSpec(
            worker_id="exact_edit_guard",
            worker_kind="exact_edit_guard",
            reads=common_reads,
            writes=("repair_region",),
            handles=("answer_mismatch", "replacement_count_too_low", "replace_answer", "derive_exact_old_span"),
            cost=0.05,
            risk=0.05,
        ),
        WorkerSpec(
            worker_id="maven_compiler_operator",
            worker_kind="maven_compiler_operator",
            reads=common_reads,
            writes=("repair_region",),
            handles=(
                "compile_error",
                "class_version_error",
                "ensure_maven_compiler_release",
                "select_compile_operator",
            ),
            cost=0.15,
            risk=0.2,
        ),
        WorkerSpec(
            worker_id="dependency_operator",
            worker_kind="dependency_operator",
            reads=common_reads,
            writes=("repair_region",),
            handles=("dependency_resolution_error", "javax_missing", "jaxb", "add_missing_dependency"),
            cost=0.2,
            risk=0.25,
        ),
        WorkerSpec(
            worker_id="surefire_operator",
            worker_kind="surefire_operator",
            reads=common_reads,
            writes=("repair_region",),
            handles=("official_eval_failed", "test_summary_missing", "interpret_official_eval"),
            cost=0.18,
            risk=0.18,
        ),
        WorkerSpec(
            worker_id="official_eval_interpreter",
            worker_kind="official_eval_interpreter",
            reads=common_reads,
            writes=("verification_region", "repair_region"),
            handles=("official_eval_failed", "interpret_official_eval", "#tests=-2"),
            cost=0.1,
            risk=0.1,
        ),
        WorkerSpec(
            worker_id="test_preservation_checker",
            worker_kind="test_preservation_checker",
            reads=common_reads,
            writes=("repair_region",),
            handles=("preserve_existing_tests", "guard_existing_tests", "preserve_test_count"),
            cost=0.05,
            risk=0.05,
        ),
        WorkerSpec(
            worker_id="operator_selector",
            worker_kind="operator_selector",
            reads=common_reads,
            writes=("repair_region",),
            handles=("recommended_action", "operator_selector"),
            cost=0.12,
            risk=0.15,
        ),
        WorkerSpec(
            worker_id="generic_repairer",
            worker_kind="generic_repairer",
            reads=common_reads,
            writes=("repair_region",),
            handles=("generic",),
            cost=0.3,
            risk=0.35,
        ),
    )


@dataclass(frozen=True)
class StigmergicScheduler:
    """Score affordance/worker pairs and select a deterministic activation."""

    workers: tuple[WorkerSpec, ...] = default_worker_specs()

    def eligible_workers(
        self,
        *,
        affordance: Affordance | None,
        feedback: FeedbackDigest,
    ) -> tuple[WorkerSpec, ...]:
        if affordance is None:
            return tuple(w for w in self.workers if w.worker_id == "generic_repairer")
        eligible = [
            worker
            for worker in self.workers
            if _capability_match(worker, affordance, feedback) > 0.0
        ]
        if not eligible:
            eligible = [w for w in self.workers if w.worker_id == "generic_repairer"]
        return tuple(sorted(eligible, key=lambda worker: worker.worker_id))

    def select(
        self,
        *,
        decision_id: str,
        affordances: Sequence[Affordance],
        signals: Sequence[SignalRecord],
        feedback: FeedbackDigest,
    ) -> WorkerActivation:
        scored: list[tuple[float, WorkerSpec, Affordance | None, JsonDict]] = []
        candidate_affordances: tuple[Affordance | None, ...] = (
            tuple(affordances) if affordances else (None,)
        )
        for affordance in candidate_affordances:
            for worker in self.eligible_workers(affordance=affordance, feedback=feedback):
                score, terms = _activation_score(worker, affordance, signals, feedback)
                scored.append((score, worker, affordance, terms))
        scored.sort(
            key=lambda item: (
                -item[0],
                item[1].worker_id,
                item[2].affordance_id if item[2] is not None else "",
            )
        )
        best_score, best_worker, best_affordance, best_terms = scored[0]
        signal_ids = tuple(record.signal_id for record in signals)
        return WorkerActivation(
            decision_id=decision_id,
            worker=best_worker,
            affordance=best_affordance,
            activation_score=best_score,
            score_terms=best_terms,
            source_signal_ids=signal_ids,
            competitors=tuple(
                {
                    "worker_id": worker.worker_id,
                    "affordance_id": (
                        pair_affordance.affordance_id
                        if pair_affordance is not None
                        else None
                    ),
                    "activation_score": float(score),
                    "score_terms": dict(terms),
                }
                for score, worker, pair_affordance, terms in scored
            ),
        )


def _capability_match(
    worker: WorkerSpec,
    affordance: Affordance | None,
    feedback: FeedbackDigest,
) -> float:
    handles = set(worker.handles)
    if affordance is not None:
        if affordance.expected_worker_kind == worker.worker_kind:
            return 1.0
        if affordance.action_type in handles or affordance.reason in handles:
            return 0.9
    if feedback.failure_type in handles:
        return 0.8
    return 0.0


def _activation_score(
    worker: WorkerSpec,
    affordance: Affordance | None,
    signals: Sequence[SignalRecord],
    feedback: FeedbackDigest,
) -> tuple[float, JsonDict]:
    capability = _capability_match(worker, affordance, feedback)
    failure_relevance = 1.0 if feedback.failure_type in set(worker.handles) else 0.4
    signal_support = _support_score(worker, affordance, signals)
    inhibition = _inhibition_score(worker, affordance, signals)
    novelty = _novelty_score(signals)
    affinity = _affinity_score(worker, signals)
    cost = float(worker.cost)
    risk = float(worker.risk)
    score = (
        0.35 * capability
        + 0.20 * signal_support
        + 0.15 * failure_relevance
        + 0.10 * affinity
        + 0.10 * novelty
        - 0.15 * inhibition
        - 0.10 * cost
        - 0.10 * risk
    )
    terms = {
        "capability_match": capability,
        "signal_support": signal_support,
        "failure_relevance": failure_relevance,
        "affinity": affinity,
        "novelty": novelty,
        "inhibition": inhibition,
        "cost": cost,
        "risk": risk,
    }
    return float(score), terms


def _support_score(
    worker: WorkerSpec,
    affordance: Affordance | None,
    signals: Sequence[SignalRecord],
) -> float:
    targets = {f"worker:{worker.worker_id}", f"worker:{worker.worker_kind}"}
    if affordance is not None:
        targets.add(f"action:{affordance.action_type}")
        targets.add(affordance.reason)
    values = [
        record.intensity
        for record in signals
        if record.kind in {SignalKind.SUPPORT, SignalKind.REINFORCE}
        and (record.target in targets or any(handle in record.target for handle in worker.handles))
    ]
    return max(values) if values else 0.0


def _inhibition_score(
    worker: WorkerSpec,
    affordance: Affordance | None,
    signals: Sequence[SignalRecord],
) -> float:
    targets = {f"worker:{worker.worker_id}", f"worker:{worker.worker_kind}"}
    if affordance is not None:
        targets.add(f"action:{affordance.action_type}")
    values = [
        record.intensity
        for record in signals
        if record.kind == SignalKind.INHIBIT
        and (record.target in targets or any(handle in record.target for handle in worker.handles))
    ]
    return max(values) if values else 0.0


def _novelty_score(signals: Sequence[SignalRecord]) -> float:
    values = [record.intensity for record in signals if record.kind == SignalKind.NOVELTY]
    return max(values) if values else 0.0


def _affinity_score(worker: WorkerSpec, signals: Sequence[SignalRecord]) -> float:
    values = [
        record.intensity
        for record in signals
        if record.target in {f"worker:{worker.worker_id}", f"worker:{worker.worker_kind}"}
    ]
    return max(values) if values else 0.0


__all__ = ["StigmergicScheduler", "default_worker_specs"]
