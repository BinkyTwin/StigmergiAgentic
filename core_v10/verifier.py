"""Verifier loop for V10 candidate hypotheses."""

from __future__ import annotations

from dataclasses import dataclass

from core_v10.contracts import (
    ApplyResult,
    ArtifactResult,
    Candidate,
    DomainAdapterV10,
    FeedbackDigest,
    ScoreResult,
    ValidationResult,
    ValidationStatus,
    WorkspaceHandle,
    to_jsonable,
)
from core_v10.event_log import EventRecord, JsonlEventLog
from core_v10.hypothesis_graph import HypothesisGraph, HypothesisNode
from core_v10.hypothesis_graph import HypothesisScore


@dataclass(frozen=True)
class VerifierReport:
    """Output of applying, validating, and diagnosing one candidate."""

    hypothesis_id: str
    candidate_id: str
    apply_result: ApplyResult
    validation: ValidationResult
    feedback: FeedbackDigest
    event_ids: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """Return whether validation fully passed."""

        return self.validation.status == ValidationStatus.PASSED


@dataclass(frozen=True)
class FinalizationReport:
    """Output of verifier-gated finalization."""

    hypothesis_id: str
    artifact: ArtifactResult
    score: ScoreResult
    contract_errors: tuple[str, ...]
    event_ids: tuple[str, ...]

    @property
    def strict_success(self) -> bool:
        """Return strict success only when score and artifact contract agree."""

        return self.score.strict_success and not self.contract_errors


class VerifierLoop:
    """Apply candidates through adapter validation and auditable events."""

    def __init__(
        self,
        *,
        adapter: DomainAdapterV10,
        event_log: JsonlEventLog,
        graph: HypothesisGraph,
        run_id: str,
        instance_id: str,
    ) -> None:
        self.adapter = adapter
        self.event_log = event_log
        self.graph = graph
        self.run_id = run_id
        self.instance_id = instance_id

    def verify(
        self,
        candidate: Candidate,
        workspace: WorkspaceHandle,
        *,
        hypothesis_id: str | None = None,
    ) -> VerifierReport:
        """Apply, validate, diagnose, log, and graph one candidate."""

        node = self._add_node(candidate, hypothesis_id=hypothesis_id)
        emitted: list[EventRecord] = [
            self._append(
                event_type="candidate.created",
                actor="strategy",
                hypothesis_id=node.hypothesis_id,
                payload={"candidate": candidate},
            )
        ]

        apply_result = self.adapter.apply(candidate, workspace)
        applied_workspace = apply_result.workspace
        self.graph.attach_workspace(node.hypothesis_id, applied_workspace)
        emitted.append(
            self._append(
                event_type="candidate.applied",
                actor="adapter",
                hypothesis_id=node.hypothesis_id,
                payload={"apply_result": apply_result},
            )
        )

        if apply_result.applied:
            self.graph.mark_applied(node.hypothesis_id)
            validation = self.adapter.validate(candidate, applied_workspace)
        else:
            validation = ValidationResult(
                candidate_id=candidate.candidate_id,
                status=ValidationStatus.ERROR,
                validator_name="apply",
                signals={"applied": False},
                summary=apply_result.summary or "candidate did not apply",
                errors=apply_result.errors,
                metadata=apply_result.metadata,
            )

        self.graph.attach_validation(
            node.hypothesis_id,
            validation,
            score=_score_from_validation(validation),
        )
        emitted.append(
            self._append(
                event_type="validation.completed",
                actor="verifier",
                hypothesis_id=node.hypothesis_id,
                payload={"validation": validation},
            )
        )

        feedback = self.adapter.diagnose(validation, applied_workspace)
        self.graph.attach_feedback(node.hypothesis_id, feedback)
        emitted.append(
            self._append(
                event_type="feedback.created",
                actor="diagnoser",
                hypothesis_id=node.hypothesis_id,
                payload={"feedback": feedback},
            )
        )

        return VerifierReport(
            hypothesis_id=node.hypothesis_id,
            candidate_id=candidate.candidate_id,
            apply_result=apply_result,
            validation=validation,
            feedback=feedback,
            event_ids=tuple(event.event_id for event in emitted),
        )

    def finalize_verified(
        self, hypothesis_id: str, workspace: WorkspaceHandle | None = None
    ) -> FinalizationReport:
        """Finalize only hypotheses that passed adapter validation."""

        node = self.graph.get(hypothesis_id)
        if node.validation is None or not node.validation.passed:
            raise ValueError(
                f"cannot finalize unverified hypothesis: {hypothesis_id}"
            )
        final_workspace = node.workspace or workspace
        if final_workspace is None:
            raise ValueError(f"missing workspace for hypothesis: {hypothesis_id}")

        artifact = self.adapter.finalize(node.candidate, final_workspace)
        artifact_errors = self.adapter.artifact_contract.validate_artifact(artifact)
        score = self.adapter.score(artifact)
        score_errors = self.adapter.artifact_contract.validate_score(score)
        contract_errors = tuple(artifact_errors + score_errors)

        emitted = [
            self._append(
                event_type="artifact.finalized",
                actor="adapter",
                hypothesis_id=hypothesis_id,
                payload={"artifact": artifact, "contract_errors": contract_errors},
            ),
            self._append(
                event_type="score.completed",
                actor="adapter",
                hypothesis_id=hypothesis_id,
                payload={
                    "score": score,
                    "strict_success": score.strict_success and not contract_errors,
                },
            ),
        ]

        return FinalizationReport(
            hypothesis_id=hypothesis_id,
            artifact=artifact,
            score=score,
            contract_errors=contract_errors,
            event_ids=tuple(event.event_id for event in emitted),
        )

    def _add_node(
        self, candidate: Candidate, *, hypothesis_id: str | None
    ) -> HypothesisNode:
        node_id = hypothesis_id or candidate.candidate_id
        return self.graph.add_candidate(
            candidate,
            hypothesis_id=node_id,
            parent_id=candidate.parent_id,
        )

    def _append(
        self,
        *,
        event_type: str,
        actor: str,
        hypothesis_id: str,
        payload: dict,
    ) -> EventRecord:
        return self.event_log.append(
            run_id=self.run_id,
            instance_id=self.instance_id,
            event_type=event_type,
            actor=actor,
            hypothesis_id=hypothesis_id,
            payload=to_jsonable(payload),
        )


def _score_from_validation(validation: ValidationResult) -> HypothesisScore:
    signals = validation.signals
    funnel_score = _funnel_score_from_validation(validation)
    if funnel_score != 0:
        return HypothesisScore(
            quality=max(0.0, funnel_score / 100.0),
            confidence=1.0 if validation.passed else 0.0,
            cost=_as_float(
                signals.get("cost", validation.metadata.get("cost", 0.0)),
                default=0.0,
            ),
            risk=0.0 if funnel_score > 0 else 0.2,
        )
    raw_quality = signals.get("quality", signals.get("score"))
    raw_confidence = signals.get("confidence")
    raw_cost = signals.get("cost", validation.metadata.get("cost", 0.0))
    raw_risk = signals.get("risk")
    if validation.passed:
        quality = _as_float(raw_quality, default=1.0)
        confidence = _as_float(raw_confidence, default=1.0)
        risk = _as_float(raw_risk, default=0.0)
    else:
        quality = _as_float(raw_quality, default=0.0)
        confidence = _as_float(raw_confidence, default=0.0)
        risk = _as_float(raw_risk, default=1.0)
    return HypothesisScore(
        quality=quality,
        confidence=confidence,
        cost=_as_float(raw_cost, default=0.0),
        risk=risk,
    )


def _funnel_score_from_validation(validation: ValidationResult) -> int:
    haystack = "\n".join(
        [validation.summary or "", *[str(err) for err in validation.errors]]
    )
    if "replacement_count_too_low" in haystack:
        return -20
    signals = dict(validation.signals or {})
    for key, score in (
        ("strict_success", 100),
        ("official_success", 80),
        ("test_success", 60),
        ("class_version_ok", 50),
        ("compile_success", 40),
        ("patch_applies", 20),
        ("patch_delivered", 10),
        ("applied", 10),
    ):
        if bool(signals.get(key)):
            return score
    return 0


def _as_float(value, *, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
