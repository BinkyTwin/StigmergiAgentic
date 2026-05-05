"""Minimal V10 strategy runner.

The first runner is intentionally workflow-first: setup, observe, generate
candidates, verify, select, finalize, report. More autonomous strategies should
reuse this contract instead of bypassing verification.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path

from core_v10.blackboard import BlackboardSnapshot, build_blackboard
from core_v10.contracts import (
    Candidate,
    DomainAdapterV10,
    FeedbackDigest,
    JsonDict,
    Observation,
    RunInstance,
    to_jsonable,
)
from core_v10.event_log import JsonlEventLog, ReplaySnapshot
from core_v10.hypothesis_graph import HypothesisGraph, HypothesisNode
from core_v10.signal_policy import (
    SIGNAL_APPLIED_EVENT,
    SIGNAL_EMITTED_EVENT,
    PolicyEffect,
    digest as policy_digest,
    inhibit_signature,
    reinforce_origin,
    update_from_feedback,
)
from core_v10.signals import SignalKind, SignalStore
from core_v10.verifier import FinalizationReport, VerifierLoop, VerifierReport


CandidateProvider = Callable[[Observation, RunInstance], Sequence[Candidate]]
RepairProvider = Callable[
    [FeedbackDigest, Candidate, Observation, RunInstance],
    Sequence[Candidate],
]


class StopReason(str, Enum):
    """Typed terminal reasons for V10 strategy runs."""

    STRICT_SUCCESS = "strict_success"
    NO_CANDIDATE_GENERATED = "no_candidate_generated"
    ALL_CANDIDATES_INVALID = "all_candidates_invalid"
    ARTIFACT_CONTRACT_FAILED = "artifact_contract_failed"
    REPAIR_EXHAUSTED = "repair_exhausted"


@dataclass(frozen=True)
class StrategyConfig:
    """Small strategy configuration surface for early V10 runners."""

    name: str = "agentless_basic"
    max_candidates: int = 1
    max_repair_rounds: int = 1
    max_repairs_per_candidate: int = 1


@dataclass(frozen=True)
class SelectionRationale:
    """Evidence-backed explanation for the deterministic selection step.

    The rationale is emitted as the ``selection.completed`` event payload and
    persisted on :class:`StrategyResult` so that downstream tooling can answer
    "why was hypothesis X chosen over Y" without re-deriving the score.
    """

    selected_hypothesis_id: str | None
    reason: str
    selected_score: float | None = None
    competitors: tuple[JsonDict, ...] = field(default_factory=tuple)

    def to_dict(self) -> JsonDict:
        """Return a JSON-friendly rationale representation."""

        return {
            "selected_hypothesis_id": self.selected_hypothesis_id,
            "reason": self.reason,
            "selected_score": self.selected_score,
            "competitors": [dict(item) for item in self.competitors],
        }


@dataclass(frozen=True)
class StrategyResult:
    """End-to-end V10 strategy result."""

    run_id: str
    instance_id: str
    strategy_name: str
    stop_reason: StopReason
    observation: Observation | None
    candidate_count: int
    selected_hypothesis_id: str | None
    verifier_reports: tuple[VerifierReport, ...] = field(default_factory=tuple)
    finalization: FinalizationReport | None = None
    replay: ReplaySnapshot | None = None
    blackboard: BlackboardSnapshot | None = None
    selection_rationale: SelectionRationale | None = None
    dedup_skipped: int = 0
    repeat_failure_suppressed: int = 0
    signal_emitted_count: int = 0
    signal_applied_count: int = 0
    signal_store_snapshot: JsonDict | None = None

    @property
    def strict_success(self) -> bool:
        """Return whether this run achieved strict success."""

        return self.stop_reason == StopReason.STRICT_SUCCESS


class StrategyRunner:
    """Execute workflow-first V10 strategies against a domain adapter."""

    def __init__(
        self,
        *,
        adapter: DomainAdapterV10,
        event_log_path: Path | str,
        graph: HypothesisGraph | None = None,
    ) -> None:
        self.adapter = adapter
        self.event_log = JsonlEventLog(event_log_path)
        self.graph = graph or HypothesisGraph()

    def run_agentless(
        self,
        *,
        run_id: str,
        instance: RunInstance,
        candidate_provider: CandidateProvider,
        config: StrategyConfig | None = None,
    ) -> StrategyResult:
        """Run the minimal A1-style workflow."""

        config = config or StrategyConfig()
        self.graph = HypothesisGraph()
        self.event_log.append(
            run_id=run_id,
            instance_id=instance.instance_id,
            event_type="run.started",
            actor="strategy_runner",
            payload={"strategy": config.name, "adapter": self.adapter.name},
        )

        workspace = self.adapter.setup(instance)
        observation = self.adapter.observe(workspace)
        self.event_log.append(
            run_id=run_id,
            instance_id=instance.instance_id,
            event_type="observation.created",
            actor="adapter",
            payload={"observation": observation},
        )

        candidates = list(candidate_provider(observation, instance))[
            : config.max_candidates
        ]
        if not candidates:
            return self._complete(
                run_id=run_id,
                instance_id=instance.instance_id,
                config=config,
                observation=observation,
                stop_reason=StopReason.NO_CANDIDATE_GENERATED,
                candidate_count=0,
                selected_hypothesis_id=None,
                selection_rationale=SelectionRationale(
                    selected_hypothesis_id=None,
                    reason="no_candidate_generated",
                ),
            )

        verifier = VerifierLoop(
            adapter=self.adapter,
            event_log=self.event_log,
            graph=self.graph,
            run_id=run_id,
            instance_id=instance.instance_id,
        )
        reports = tuple(
            verifier.verify(candidate, workspace) for candidate in candidates
        )
        candidate_ids = tuple(report.hypothesis_id for report in reports)
        selected = self.graph.select_best(candidate_ids)
        if selected is None:
            rationale = self._rationale_for_invalid_set(candidate_ids)
            return self._complete(
                run_id=run_id,
                instance_id=instance.instance_id,
                config=config,
                observation=observation,
                stop_reason=StopReason.ALL_CANDIDATES_INVALID,
                candidate_count=len(candidates),
                selected_hypothesis_id=None,
                verifier_reports=reports,
                selection_rationale=rationale,
            )

        finalization = self._finalize_best_validated(verifier, candidate_ids)
        stop_reason = _stop_reason_from_finalization(finalization)
        rationale = self._rationale_for_finalization(
            hypothesis_ids=candidate_ids,
            finalization=finalization,
        )
        return self._complete(
            run_id=run_id,
            instance_id=instance.instance_id,
            config=config,
            observation=observation,
            stop_reason=stop_reason,
            candidate_count=len(candidates),
            selected_hypothesis_id=finalization.hypothesis_id,
            verifier_reports=reports,
            finalization=finalization,
            selection_rationale=rationale,
        )

    def run_branching_repair(
        self,
        *,
        run_id: str,
        instance: RunInstance,
        candidate_provider: CandidateProvider,
        repair_provider: RepairProvider,
        config: StrategyConfig | None = None,
    ) -> StrategyResult:
        """Run A3-style branching repair with explicit hypothesis lineage."""

        config = config or StrategyConfig(name="branching_repair")
        self.graph = HypothesisGraph()
        self.event_log.append(
            run_id=run_id,
            instance_id=instance.instance_id,
            event_type="run.started",
            actor="strategy_runner",
            payload={"strategy": config.name, "adapter": self.adapter.name},
        )
        workspace = self.adapter.setup(instance)
        observation = self.adapter.observe(workspace)
        self.event_log.append(
            run_id=run_id,
            instance_id=instance.instance_id,
            event_type="observation.created",
            actor="adapter",
            payload={"observation": observation},
        )

        signature_tracker = _SignatureTracker()
        dedup_skipped = 0
        repeat_failure_suppressed = 0

        raw_candidates = list(candidate_provider(observation, instance))[
            : config.max_candidates
        ]
        accepted_initial: list[Candidate] = []
        for cand in raw_candidates:
            sig = signature_tracker.signature(cand)
            duplicate_of = signature_tracker.first_seen_id(sig)
            if duplicate_of is not None:
                dedup_skipped += 1
                self._emit_dedup_event(
                    run_id=run_id,
                    instance_id=instance.instance_id,
                    candidate=cand,
                    signature=sig,
                    duplicate_of=duplicate_of,
                    parent_id=None,
                )
                continue
            signature_tracker.mark_seen(sig, cand.candidate_id)
            accepted_initial.append(cand)

        if not accepted_initial:
            stop_reason = (
                StopReason.NO_CANDIDATE_GENERATED
                if not raw_candidates
                else StopReason.ALL_CANDIDATES_INVALID
            )
            return self._complete(
                run_id=run_id,
                instance_id=instance.instance_id,
                config=config,
                observation=observation,
                stop_reason=stop_reason,
                candidate_count=0,
                selected_hypothesis_id=None,
                selection_rationale=SelectionRationale(
                    selected_hypothesis_id=None,
                    reason=stop_reason.value,
                ),
                dedup_skipped=dedup_skipped,
                repeat_failure_suppressed=repeat_failure_suppressed,
            )

        verifier = VerifierLoop(
            adapter=self.adapter,
            event_log=self.event_log,
            graph=self.graph,
            run_id=run_id,
            instance_id=instance.instance_id,
        )
        # Attach signature metadata to the initial nodes after verifier creates them.
        reports: list[VerifierReport] = []
        frontier = list(accepted_initial)
        for round_index in range(config.max_repair_rounds + 1):
            current_reports: list[VerifierReport] = []
            for candidate in frontier:
                verify_workspace = _workspace_for_candidate(
                    candidate,
                    graph=self.graph,
                    fallback=workspace,
                )
                report = verifier.verify(candidate, verify_workspace)
                node = self.graph.get(report.hypothesis_id)
                node.metadata["signature"] = signature_tracker.signature(candidate)
                current_reports.append(report)
            reports.extend(current_reports)
            for report in current_reports:
                if not report.passed:
                    sig = self.graph.get(report.hypothesis_id).metadata.get(
                        "signature"
                    )
                    if sig:
                        signature_tracker.mark_failed(sig)
            if any(report.passed for report in current_reports):
                break
            if round_index >= config.max_repair_rounds:
                break

            repairs: list[Candidate] = []
            for report in current_reports:
                parent_node = self.graph.get(report.hypothesis_id)
                original = parent_node.candidate
                repair_observation = _attach_live_files(
                    observation, parent_node.workspace
                )
                suggested = list(
                    repair_provider(
                        report.feedback,
                        original,
                        repair_observation,
                        instance,
                    )
                )[: config.max_repairs_per_candidate]
                for r_cand in suggested:
                    r_sig = signature_tracker.signature(r_cand)
                    if signature_tracker.failure_count(r_sig) > 0:
                        repeat_failure_suppressed += 1
                        self._emit_repeat_failure_event(
                            run_id=run_id,
                            instance_id=instance.instance_id,
                            candidate=r_cand,
                            signature=r_sig,
                            parent_id=report.hypothesis_id,
                            previous_failures=signature_tracker.failure_count(r_sig),
                        )
                        continue
                    duplicate_of = signature_tracker.first_seen_id(r_sig)
                    if duplicate_of is not None:
                        dedup_skipped += 1
                        self._emit_dedup_event(
                            run_id=run_id,
                            instance_id=instance.instance_id,
                            candidate=r_cand,
                            signature=r_sig,
                            duplicate_of=duplicate_of,
                            parent_id=report.hypothesis_id,
                        )
                        continue
                    signature_tracker.mark_seen(r_sig, r_cand.candidate_id)
                    repairs.append(_with_parent(r_cand, parent_id=report.hypothesis_id))
            if not repairs:
                break
            frontier = repairs

        candidate_ids = tuple(report.hypothesis_id for report in reports)
        selected = self.graph.select_best(candidate_ids)
        if selected is None:
            rationale = self._rationale_for_invalid_set(candidate_ids)
            return self._complete(
                run_id=run_id,
                instance_id=instance.instance_id,
                config=config,
                observation=observation,
                stop_reason=StopReason.REPAIR_EXHAUSTED,
                candidate_count=len(reports),
                selected_hypothesis_id=None,
                verifier_reports=tuple(reports),
                selection_rationale=replace(
                    rationale, reason=StopReason.REPAIR_EXHAUSTED.value
                ),
                dedup_skipped=dedup_skipped,
                repeat_failure_suppressed=repeat_failure_suppressed,
            )

        finalization = self._finalize_best_validated(verifier, candidate_ids)
        stop_reason = _stop_reason_from_finalization(finalization)
        rationale = self._rationale_for_finalization(
            hypothesis_ids=candidate_ids,
            finalization=finalization,
        )
        return self._complete(
            run_id=run_id,
            instance_id=instance.instance_id,
            config=config,
            observation=observation,
            stop_reason=stop_reason,
            candidate_count=len(reports),
            selected_hypothesis_id=finalization.hypothesis_id,
            verifier_reports=tuple(reports),
            finalization=finalization,
            selection_rationale=rationale,
            dedup_skipped=dedup_skipped,
            repeat_failure_suppressed=repeat_failure_suppressed,
        )

    def run_stigmergic_blackboard(
        self,
        *,
        run_id: str,
        instance: RunInstance,
        candidate_provider: CandidateProvider,
        repair_provider: RepairProvider,
        config: StrategyConfig | None = None,
    ) -> StrategyResult:
        """Run A4-style branching repair augmented with an active SignalStore.

        Invariant: when no signal-driven decision is taken (empty store, no
        anti_actions, no repeated failure), this routine produces the same
        candidate verification sequence as :meth:`run_branching_repair`. The
        only difference in the EventLog is a sequence of ``signal.emitted``
        records (and possibly ``signal.applied`` when a signal effectively
        changed a decision).
        """

        config = config or StrategyConfig(name="stigmergic_blackboard")
        self.graph = HypothesisGraph()
        store = SignalStore()
        signal_emitted_count = 0
        signal_applied_count = 0

        self.event_log.append(
            run_id=run_id,
            instance_id=instance.instance_id,
            event_type="run.started",
            actor="strategy_runner",
            payload={"strategy": config.name, "adapter": self.adapter.name},
        )
        workspace = self.adapter.setup(instance)
        observation = self.adapter.observe(workspace)
        self.event_log.append(
            run_id=run_id,
            instance_id=instance.instance_id,
            event_type="observation.created",
            actor="adapter",
            payload={"observation": observation},
        )

        signature_tracker = _SignatureTracker()
        dedup_skipped = 0
        repeat_failure_suppressed = 0

        def _emit_signals(effects: Sequence[PolicyEffect], hyp_id: str | None = None) -> None:
            nonlocal signal_emitted_count
            for effect in effects:
                self.event_log.append(
                    run_id=run_id,
                    instance_id=instance.instance_id,
                    event_type=SIGNAL_EMITTED_EVENT,
                    actor="signal_policy",
                    hypothesis_id=hyp_id,
                    payload={
                        "record": store.get(effect.kind, effect.target).to_dict()
                        if store.get(effect.kind, effect.target)
                        else {},
                        "op": effect.op,
                        "rationale": effect.rationale,
                    },
                )
                signal_emitted_count += 1

        def _emit_applied(
            *,
            kind: SignalKind,
            target: str,
            effect: str,
            hypothesis_id: str | None,
            rationale: str,
            intensity: float,
        ) -> None:
            nonlocal signal_applied_count
            self.event_log.append(
                run_id=run_id,
                instance_id=instance.instance_id,
                event_type=SIGNAL_APPLIED_EVENT,
                actor="strategy_runner",
                hypothesis_id=hypothesis_id,
                payload={
                    "kind": kind.value,
                    "target": target,
                    "effect": effect,
                    "rationale": rationale,
                    "intensity": float(intensity),
                },
            )
            signal_applied_count += 1

        raw_candidates = list(candidate_provider(observation, instance))[
            : config.max_candidates
        ]
        accepted_initial: list[Candidate] = []
        for cand in raw_candidates:
            sig = signature_tracker.signature(cand)
            duplicate_of = signature_tracker.first_seen_id(sig)
            if duplicate_of is not None:
                dedup_skipped += 1
                self._emit_dedup_event(
                    run_id=run_id,
                    instance_id=instance.instance_id,
                    candidate=cand,
                    signature=sig,
                    duplicate_of=duplicate_of,
                    parent_id=None,
                )
                continue
            # Signal-driven drop on a strongly inhibited signature.
            if store.inhibit_for(f"signature:{sig}") >= 0.8:
                dedup_skipped += 1
                _emit_applied(
                    kind=SignalKind.INHIBIT,
                    target=f"signature:{sig}",
                    effect="drop",
                    hypothesis_id=None,
                    rationale="signal_driven_signature_inhibit",
                    intensity=store.inhibit_for(f"signature:{sig}"),
                )
                continue
            signature_tracker.mark_seen(sig, cand.candidate_id)
            accepted_initial.append(cand)

        if not accepted_initial:
            stop_reason = (
                StopReason.NO_CANDIDATE_GENERATED
                if not raw_candidates
                else StopReason.ALL_CANDIDATES_INVALID
            )
            return self._complete(
                run_id=run_id,
                instance_id=instance.instance_id,
                config=config,
                observation=observation,
                stop_reason=stop_reason,
                candidate_count=0,
                selected_hypothesis_id=None,
                selection_rationale=SelectionRationale(
                    selected_hypothesis_id=None,
                    reason=stop_reason.value,
                ),
                dedup_skipped=dedup_skipped,
                repeat_failure_suppressed=repeat_failure_suppressed,
                signal_emitted_count=signal_emitted_count,
                signal_applied_count=signal_applied_count,
                signal_store_snapshot=store.to_dict(),
            )

        verifier = VerifierLoop(
            adapter=self.adapter,
            event_log=self.event_log,
            graph=self.graph,
            run_id=run_id,
            instance_id=instance.instance_id,
        )
        reports: list[VerifierReport] = []
        frontier = list(_signal_reorder(accepted_initial, store, _emit_applied))
        for round_index in range(config.max_repair_rounds + 1):
            current_reports: list[VerifierReport] = []
            for candidate in frontier:
                verify_workspace = _workspace_for_candidate(
                    candidate,
                    graph=self.graph,
                    fallback=workspace,
                )
                report = verifier.verify(candidate, verify_workspace)
                node = self.graph.get(report.hypothesis_id)
                signature = signature_tracker.signature(candidate)
                node.metadata["signature"] = signature
                current_reports.append(report)
                # Update the signal layer based on the verifier outcome.
                now_seq = max(0, self.event_log.next_sequence() - 1)
                if report.passed and node.validation is not None:
                    effects = reinforce_origin(
                        store,
                        candidate=candidate,
                        validation=node.validation,
                        now_seq=now_seq,
                    )
                    _emit_signals(effects, hyp_id=report.hypothesis_id)
                else:
                    if report.feedback is not None:
                        effects = update_from_feedback(
                            store,
                            feedback=report.feedback,
                            candidate=candidate,
                            now_seq=now_seq,
                        )
                        _emit_signals(effects, hyp_id=report.hypothesis_id)
                    sig_effect = inhibit_signature(
                        store,
                        signature=signature,
                        evidence_id=report.hypothesis_id,
                        now_seq=now_seq,
                    )
                    _emit_signals((sig_effect,), hyp_id=report.hypothesis_id)
            reports.extend(current_reports)
            for report in current_reports:
                if not report.passed:
                    sig = self.graph.get(report.hypothesis_id).metadata.get(
                        "signature"
                    )
                    if sig:
                        signature_tracker.mark_failed(sig)
            if any(report.passed for report in current_reports):
                break
            if round_index >= config.max_repair_rounds:
                break

            repairs: list[Candidate] = []
            for report in current_reports:
                parent_node = self.graph.get(report.hypothesis_id)
                original = parent_node.candidate
                # Inject the stigmergic digest *and* the parent branch's
                # current files so the repair_provider grounds its output in
                # the post-apply state (not the pristine base workspace).
                aug_observation = _attach_digest(observation, store)
                aug_observation = _attach_live_files(
                    aug_observation, parent_node.workspace
                )
                suggested = list(
                    repair_provider(
                        report.feedback,
                        original,
                        aug_observation,
                        instance,
                    )
                )[: config.max_repairs_per_candidate]
                for r_cand in suggested:
                    r_sig = signature_tracker.signature(r_cand)
                    if signature_tracker.failure_count(r_sig) > 0:
                        repeat_failure_suppressed += 1
                        self._emit_repeat_failure_event(
                            run_id=run_id,
                            instance_id=instance.instance_id,
                            candidate=r_cand,
                            signature=r_sig,
                            parent_id=report.hypothesis_id,
                            previous_failures=signature_tracker.failure_count(r_sig),
                        )
                        continue
                    duplicate_of = signature_tracker.first_seen_id(r_sig)
                    if duplicate_of is not None:
                        dedup_skipped += 1
                        self._emit_dedup_event(
                            run_id=run_id,
                            instance_id=instance.instance_id,
                            candidate=r_cand,
                            signature=r_sig,
                            duplicate_of=duplicate_of,
                            parent_id=report.hypothesis_id,
                        )
                        continue
                    if store.inhibit_for(f"signature:{r_sig}") >= 0.8:
                        repeat_failure_suppressed += 1
                        _emit_applied(
                            kind=SignalKind.INHIBIT,
                            target=f"signature:{r_sig}",
                            effect="drop",
                            hypothesis_id=report.hypothesis_id,
                            rationale="signal_driven_signature_inhibit_repair",
                            intensity=store.inhibit_for(f"signature:{r_sig}"),
                        )
                        continue
                    signature_tracker.mark_seen(r_sig, r_cand.candidate_id)
                    repairs.append(_with_parent(r_cand, parent_id=report.hypothesis_id))
            if not repairs:
                break
            frontier = list(_signal_reorder(repairs, store, _emit_applied))

        candidate_ids = tuple(report.hypothesis_id for report in reports)
        selected = self.graph.select_best(candidate_ids)
        if selected is None:
            rationale = self._rationale_for_invalid_set(candidate_ids)
            return self._complete(
                run_id=run_id,
                instance_id=instance.instance_id,
                config=config,
                observation=observation,
                stop_reason=StopReason.REPAIR_EXHAUSTED,
                candidate_count=len(reports),
                selected_hypothesis_id=None,
                verifier_reports=tuple(reports),
                selection_rationale=replace(
                    rationale, reason=StopReason.REPAIR_EXHAUSTED.value
                ),
                dedup_skipped=dedup_skipped,
                repeat_failure_suppressed=repeat_failure_suppressed,
                signal_emitted_count=signal_emitted_count,
                signal_applied_count=signal_applied_count,
                signal_store_snapshot=store.to_dict(),
            )

        finalization = self._finalize_best_validated_signal_aware(
            verifier=verifier,
            hypothesis_ids=candidate_ids,
            store=store,
            on_signal_applied=_emit_applied,
        )
        stop_reason = _stop_reason_from_finalization(finalization)
        rationale = self._rationale_for_finalization(
            hypothesis_ids=candidate_ids,
            finalization=finalization,
            store=store,
        )
        return self._complete(
            run_id=run_id,
            instance_id=instance.instance_id,
            config=config,
            observation=observation,
            stop_reason=stop_reason,
            candidate_count=len(reports),
            selected_hypothesis_id=finalization.hypothesis_id,
            verifier_reports=tuple(reports),
            finalization=finalization,
            selection_rationale=rationale,
            dedup_skipped=dedup_skipped,
            repeat_failure_suppressed=repeat_failure_suppressed,
            signal_emitted_count=signal_emitted_count,
            signal_applied_count=signal_applied_count,
            signal_store_snapshot=store.to_dict(),
        )

    def _emit_dedup_event(
        self,
        *,
        run_id: str,
        instance_id: str,
        candidate: Candidate,
        signature: str,
        duplicate_of: str,
        parent_id: str | None,
    ) -> None:
        self.event_log.append(
            run_id=run_id,
            instance_id=instance_id,
            event_type="candidate.deduped",
            actor="strategy_runner",
            payload={
                "candidate_id": candidate.candidate_id,
                "signature": signature,
                "duplicate_of": duplicate_of,
                "parent_id": parent_id,
                "origin": candidate.origin,
            },
        )

    def _emit_repeat_failure_event(
        self,
        *,
        run_id: str,
        instance_id: str,
        candidate: Candidate,
        signature: str,
        parent_id: str | None,
        previous_failures: int,
    ) -> None:
        self.event_log.append(
            run_id=run_id,
            instance_id=instance_id,
            event_type="candidate.repeat_failure_suppressed",
            actor="strategy_runner",
            payload={
                "candidate_id": candidate.candidate_id,
                "signature": signature,
                "parent_id": parent_id,
                "previous_failures": int(previous_failures),
                "origin": candidate.origin,
            },
        )

    def _rationale_for_finalization(
        self,
        *,
        hypothesis_ids: tuple[str, ...],
        finalization: FinalizationReport,
        store: SignalStore | None = None,
    ) -> SelectionRationale:
        nodes = _validated_nodes_in_priority_order(
            self.graph,
            hypothesis_ids=hypothesis_ids,
        )

        def _origin_signal_score(node: HypothesisNode) -> float:
            if store is None:
                return 0.0
            return store.support_for(f"origin:{node.candidate.origin}")

        competitors = tuple(
            {
                "hypothesis_id": node.hypothesis_id,
                "score": dict(node.score.to_dict()),
                "status": node.status.value,
                "passed": bool(node.validation and node.validation.passed),
                "signal_score": float(_origin_signal_score(node)),
            }
            for node in nodes
        )
        selected_node = self.graph.get(finalization.hypothesis_id)
        reason = (
            "strict_success"
            if finalization.strict_success
            else "fallback_validated_finalization"
        )
        return SelectionRationale(
            selected_hypothesis_id=finalization.hypothesis_id,
            reason=reason,
            selected_score=float(selected_node.score.total),
            competitors=competitors,
        )

    def _rationale_for_invalid_set(
        self, hypothesis_ids: tuple[str, ...]
    ) -> SelectionRationale:
        allowed = set(hypothesis_ids)
        competitors = tuple(
            {
                "hypothesis_id": node.hypothesis_id,
                "score": dict(node.score.to_dict()),
                "status": node.status.value,
                "passed": bool(node.validation and node.validation.passed),
            }
            for node in self.graph.nodes()
            if node.hypothesis_id in allowed
        )
        return SelectionRationale(
            selected_hypothesis_id=None,
            reason="no_validated_candidate",
            selected_score=None,
            competitors=competitors,
        )

    def _finalize_best_validated(
        self,
        verifier: VerifierLoop,
        hypothesis_ids,
    ) -> FinalizationReport:
        candidates = _validated_nodes_in_priority_order(
            self.graph,
            hypothesis_ids=hypothesis_ids,
        )
        if not candidates:
            raise ValueError("no validated candidates to finalize")
        last_finalization: FinalizationReport | None = None
        for node in candidates:
            finalization = verifier.finalize_verified(node.hypothesis_id)
            if finalization.strict_success:
                self.graph.select_best([node.hypothesis_id])
                return finalization
            last_finalization = finalization
        assert last_finalization is not None
        self.graph.select_best([last_finalization.hypothesis_id])
        return last_finalization

    def _finalize_best_validated_signal_aware(
        self,
        *,
        verifier: VerifierLoop,
        hypothesis_ids,
        store: SignalStore,
        on_signal_applied,
    ) -> FinalizationReport:
        """A4 finalize: same as A3 but breaks ties using SUPPORT(origin)."""

        candidates = _validated_nodes_in_priority_order(
            self.graph,
            hypothesis_ids=hypothesis_ids,
        )
        if not candidates:
            raise ValueError("no validated candidates to finalize")

        # Determine if signal-driven tie-breaking actually changes the order.
        baseline = list(candidates)
        signal_sorted = sorted(
            candidates,
            key=lambda node: (
                -float(node.score.total),
                -float(node.score.quality),
                -store.support_for(f"origin:{node.candidate.origin}"),
                node.hypothesis_id,
            ),
        )
        if [n.hypothesis_id for n in signal_sorted] != [
            n.hypothesis_id for n in baseline
        ]:
            top = signal_sorted[0]
            on_signal_applied(
                kind=SignalKind.SUPPORT,
                target=f"origin:{top.candidate.origin}",
                effect="finalize_tiebreak",
                hypothesis_id=top.hypothesis_id,
                rationale="signal_driven_finalize_priority",
                intensity=store.support_for(f"origin:{top.candidate.origin}"),
            )
            ordered = signal_sorted
        else:
            ordered = baseline

        last_finalization: FinalizationReport | None = None
        for node in ordered:
            finalization = verifier.finalize_verified(node.hypothesis_id)
            if finalization.strict_success:
                self.graph.select_best([node.hypothesis_id])
                return finalization
            last_finalization = finalization
        assert last_finalization is not None
        self.graph.select_best([last_finalization.hypothesis_id])
        return last_finalization

    def _complete(
        self,
        *,
        run_id: str,
        instance_id: str,
        config: StrategyConfig,
        observation: Observation | None,
        stop_reason: StopReason,
        candidate_count: int,
        selected_hypothesis_id: str | None,
        verifier_reports: tuple[VerifierReport, ...] = (),
        finalization: FinalizationReport | None = None,
        selection_rationale: SelectionRationale | None = None,
        dedup_skipped: int = 0,
        repeat_failure_suppressed: int = 0,
        signal_emitted_count: int = 0,
        signal_applied_count: int = 0,
        signal_store_snapshot: JsonDict | None = None,
    ) -> StrategyResult:
        if selection_rationale is not None:
            self.event_log.append(
                run_id=run_id,
                instance_id=instance_id,
                event_type="selection.completed",
                actor="strategy_runner",
                hypothesis_id=selection_rationale.selected_hypothesis_id,
                payload={"rationale": selection_rationale.to_dict()},
            )
        self.event_log.append(
            run_id=run_id,
            instance_id=instance_id,
            event_type="run.completed",
            actor="strategy_runner",
            payload={
                "strategy": config.name,
                "stop_reason": stop_reason.value,
                "candidate_count": candidate_count,
                "selected_hypothesis_id": selected_hypothesis_id,
                "dedup_skipped": int(dedup_skipped),
                "repeat_failure_suppressed": int(repeat_failure_suppressed),
                "signal_emitted_count": int(signal_emitted_count),
                "signal_applied_count": int(signal_applied_count),
            },
        )
        return StrategyResult(
            run_id=run_id,
            instance_id=instance_id,
            strategy_name=config.name,
            stop_reason=stop_reason,
            observation=observation,
            candidate_count=candidate_count,
            selected_hypothesis_id=selected_hypothesis_id,
            verifier_reports=verifier_reports,
            finalization=finalization,
            replay=self.event_log.replay(run_id),
            blackboard=build_blackboard(
                events=self.event_log.for_run(run_id),
                graph=self.graph,
            ),
            selection_rationale=selection_rationale,
            dedup_skipped=int(dedup_skipped),
            repeat_failure_suppressed=int(repeat_failure_suppressed),
            signal_emitted_count=int(signal_emitted_count),
            signal_applied_count=int(signal_applied_count),
            signal_store_snapshot=signal_store_snapshot,
        )


def _with_parent(candidate: Candidate, *, parent_id: str) -> Candidate:
    """Return a candidate attached to a repair parent."""

    return replace(candidate, parent_id=parent_id)


def _workspace_for_candidate(
    candidate: Candidate,
    *,
    graph: HypothesisGraph,
    fallback,
):
    if candidate.parent_id is None:
        return fallback
    parent = graph.get(candidate.parent_id)
    return parent.workspace or fallback


def _signal_reorder(
    candidates: Sequence[Candidate],
    store: SignalStore,
    on_signal_applied,
) -> list[Candidate]:
    """Stable, signal-aware reordering of a candidate frontier.

    Sorts by ``(-support_for(origin), -support_for(kind), candidate_id)``.
    If the order actually changes, emits one ``signal.applied`` event.
    When the store is empty (or no SUPPORT signal is active), the sort is
    stable and returns the original sequence — preserving the A4 ≡ A3
    invariant.
    """

    if len(candidates) <= 1:
        return list(candidates)
    baseline = list(candidates)

    def _key(c: Candidate) -> tuple:
        origin_score = store.support_for(f"origin:{c.origin}")
        kind_score = store.support_for(
            f"kind:{c.kind.value}", kind=SignalKind.REINFORCE
        )
        return (-float(origin_score), -float(kind_score), c.candidate_id)

    sorted_candidates = sorted(baseline, key=_key)
    if [c.candidate_id for c in sorted_candidates] != [
        c.candidate_id for c in baseline
    ]:
        top = sorted_candidates[0]
        on_signal_applied(
            kind=SignalKind.SUPPORT,
            target=f"origin:{top.origin}",
            effect="reorder",
            hypothesis_id=None,
            rationale="signal_driven_frontier_reorder",
            intensity=store.support_for(f"origin:{top.origin}"),
        )
    return sorted_candidates


def _attach_digest(observation: Observation, store: SignalStore) -> Observation:
    """Return ``observation`` with the stigmergic digest attached to ``data``."""

    digest_payload = policy_digest(store).to_dict()
    new_data = dict(observation.data or {})
    new_data["stigmergic_digest"] = digest_payload
    return replace(observation, data=new_data)


_LIVE_FILES_MAX_BYTES = 200_000  # per file, conservative cap to keep prompts small
_LIVE_FILES_MAX_FILES = 10


def _attach_live_files(
    observation: Observation,
    parent_workspace,
) -> Observation:
    """Attach the parent branch's current file contents to the observation.

    This bridges a critical gap: providers (LLM repair) must see the *current*
    workspace state (after the parent candidate's edits were applied), not the
    pristine base workspace. The strategy runner calls this before invoking
    ``repair_provider`` so the LLM grounds its repair in the real state.

    The override is stored under ``data["__live_files__"]`` and read back by
    ``scripts/bench/providers_llm._read_target_files``. The set of files is
    derived from ``observation.data["pom_files"]`` and
    ``observation.data["java_files_sample"]`` — same shape as the initial
    provider, just refreshed from the parent workspace.
    """

    if parent_workspace is None or not hasattr(parent_workspace, "read_file"):
        return observation
    pom_files = list(observation.data.get("pom_files") or [])
    java_files = list(observation.data.get("java_files_sample") or [])
    rel_paths = (pom_files + java_files)[:_LIVE_FILES_MAX_FILES]
    live: dict[str, str] = {}
    for rel in rel_paths:
        try:
            text = parent_workspace.read_file(rel, max_bytes=_LIVE_FILES_MAX_BYTES)
        except Exception:  # noqa: BLE001
            continue
        live[str(rel)] = str(text)
    if not live:
        return observation
    new_data = dict(observation.data or {})
    new_data["__live_files__"] = live
    return replace(observation, data=new_data)


def _validated_nodes_in_priority_order(
    graph: HypothesisGraph,
    *,
    hypothesis_ids,
) -> list[HypothesisNode]:
    allowed_ids = set(hypothesis_ids)
    nodes = [
        node
        for node in graph.nodes()
        if node.hypothesis_id in allowed_ids
        and node.validation
        and node.validation.passed
    ]
    return sorted(
        nodes,
        key=lambda node: (
            node.score.total,
            node.score.quality,
            node.hypothesis_id,
        ),
        reverse=True,
    )


def _stop_reason_from_finalization(finalization: FinalizationReport) -> StopReason:
    return (
        StopReason.STRICT_SUCCESS
        if finalization.strict_success
        else StopReason.ARTIFACT_CONTRACT_FAILED
    )


class _SignatureTracker:
    """Track candidate signatures within a single branching_repair run."""

    def __init__(self) -> None:
        self._first_seen: dict[str, str] = {}
        self._failures: dict[str, int] = {}

    @staticmethod
    def signature(candidate: Candidate) -> str:
        """Return a stable hash of the candidate kind+payload."""

        canonical = json.dumps(
            {
                "kind": candidate.kind.value,
                "payload": to_jsonable(candidate.payload),
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    def first_seen_id(self, signature: str) -> str | None:
        """Return the candidate id that first produced this signature, if any."""

        return self._first_seen.get(signature)

    def mark_seen(self, signature: str, candidate_id: str) -> None:
        """Record that a signature has now been emitted by ``candidate_id``."""

        self._first_seen.setdefault(signature, candidate_id)

    def mark_failed(self, signature: str) -> None:
        """Increment the failure counter for a signature."""

        self._failures[signature] = self._failures.get(signature, 0) + 1

    def failure_count(self, signature: str) -> int:
        """Return how many times this signature has failed verification."""

        return self._failures.get(signature, 0)
