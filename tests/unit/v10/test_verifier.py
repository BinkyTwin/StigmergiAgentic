from __future__ import annotations

from pathlib import Path

import pytest

from core_v10.contracts import (
    ApplyResult,
    ArtifactContract,
    ArtifactResult,
    ArtifactStatus,
    Candidate,
    CandidateKind,
    Capability,
    DomainAdapterV10,
    FeedbackDigest,
    Observation,
    RunInstance,
    ScoreResult,
    ValidationResult,
    ValidationStatus,
    WorkspaceHandle,
)
from core_v10.event_log import JsonlEventLog
from core_v10.hypothesis_graph import HypothesisGraph, HypothesisStatus
from core_v10.verifier import VerifierLoop


class VerifierFakeAdapter(DomainAdapterV10):
    name = "verifier-fake"
    artifact_contract = ArtifactContract(required_artifacts=("patch.diff",))

    def __init__(
        self,
        *,
        apply_ok: bool = True,
        validate_ok: bool = True,
        score_ok: bool = True,
    ) -> None:
        self.apply_ok = apply_ok
        self.validate_ok = validate_ok
        self.score_ok = score_ok
        self.validated_workspace: WorkspaceHandle | None = None
        self.diagnosed_workspace: WorkspaceHandle | None = None
        self.finalized_workspace: WorkspaceHandle | None = None

    def setup(self, instance: RunInstance) -> WorkspaceHandle:
        return WorkspaceHandle(
            root=Path("/tmp/v10"),
            instance_id=instance.instance_id,
        )

    def observe(self, workspace: WorkspaceHandle) -> Observation:
        return Observation(summary="observed")

    def capabilities(self) -> list[Capability]:
        return [Capability(name="unit", kind="validator")]

    def apply(self, candidate: Candidate, workspace: WorkspaceHandle) -> ApplyResult:
        branch_workspace = WorkspaceHandle(
            root=workspace.root / "branch-a",
            instance_id=f"{workspace.instance_id}:branch-a",
        )
        return ApplyResult(
            candidate_id=candidate.candidate_id,
            applied=self.apply_ok,
            workspace=branch_workspace,
            summary="applied" if self.apply_ok else "apply failed",
            errors=[] if self.apply_ok else ["patch does not apply"],
        )

    def validate(
        self, candidate: Candidate, workspace: WorkspaceHandle
    ) -> ValidationResult:
        self.validated_workspace = workspace
        return ValidationResult(
            candidate_id=candidate.candidate_id,
            status=ValidationStatus.PASSED
            if self.validate_ok
            else ValidationStatus.FAILED,
            validator_name="unit",
            signals={"local_valid": self.validate_ok},
        )

    def diagnose(
        self, validation: ValidationResult, workspace: WorkspaceHandle
    ) -> FeedbackDigest:
        self.diagnosed_workspace = workspace
        return FeedbackDigest(
            candidate_id=validation.candidate_id,
            failure_type="none" if validation.passed else "validation_failed",
            severity="info" if validation.passed else "blocking",
            summary="ok" if validation.passed else "needs repair",
        )

    def finalize(
        self, candidate: Candidate, workspace: WorkspaceHandle
    ) -> ArtifactResult:
        self.finalized_workspace = workspace
        return ArtifactResult(
            candidate_id=candidate.candidate_id,
            status=ArtifactStatus.DELIVERED,
            artifacts={"patch.diff": "diff --git a/x b/x"},
        )

    def score(self, artifact: ArtifactResult) -> ScoreResult:
        return ScoreResult(
            candidate_id=artifact.candidate_id,
            strict_success=artifact.delivered and self.score_ok,
            metrics={"local_valid": True},
        )


def make_candidate(candidate_id: str = "cand-001") -> Candidate:
    return Candidate(
        candidate_id=candidate_id,
        kind=CandidateKind.PATCH,
        payload={"diff": "diff --git a/x b/x"},
        origin="unit-test",
    )


def make_loop(tmp_path, adapter: DomainAdapterV10) -> VerifierLoop:
    return VerifierLoop(
        adapter=adapter,
        event_log=JsonlEventLog(tmp_path / "events.jsonl"),
        graph=HypothesisGraph(),
        run_id="run-001",
        instance_id="inst-001",
    )


def test_verifier_loop_logs_validation_and_updates_graph(tmp_path) -> None:
    adapter = VerifierFakeAdapter()
    loop = make_loop(tmp_path, adapter)
    workspace = WorkspaceHandle(root=tmp_path, instance_id="inst-001")
    candidate = make_candidate()

    report = loop.verify(candidate, workspace)

    assert report.passed is True
    assert adapter.validated_workspace is not None
    assert adapter.validated_workspace.root == tmp_path / "branch-a"
    assert adapter.diagnosed_workspace == adapter.validated_workspace
    assert len(report.event_ids) == 4
    node = loop.graph.get("cand-001")
    assert node.status == HypothesisStatus.VALIDATED
    assert node.validation is not None
    assert node.feedback is not None
    assert loop.event_log.replay("run-001").counts_by_type == {
        "candidate.created": 1,
        "candidate.applied": 1,
        "validation.completed": 1,
        "feedback.created": 1,
    }


def test_verifier_loop_turns_apply_failure_into_validation_error(tmp_path) -> None:
    loop = make_loop(tmp_path, VerifierFakeAdapter(apply_ok=False))
    workspace = WorkspaceHandle(root=tmp_path, instance_id="inst-001")

    report = loop.verify(make_candidate(), workspace)

    assert report.passed is False
    assert report.validation.status == ValidationStatus.ERROR
    assert report.validation.errors == ["patch does not apply"]
    assert loop.graph.get("cand-001").status == HypothesisStatus.FAILED


def test_verifier_loop_rejects_duplicate_hypothesis_id(tmp_path) -> None:
    loop = make_loop(tmp_path, VerifierFakeAdapter())
    workspace = WorkspaceHandle(root=tmp_path, instance_id="inst-001")
    loop.verify(make_candidate("cand-001"), workspace)

    with pytest.raises(ValueError, match="duplicate hypothesis id"):
        loop.verify(make_candidate("cand-001"), workspace)


def test_finalize_verified_blocks_unverified_candidates(tmp_path) -> None:
    loop = make_loop(tmp_path, VerifierFakeAdapter(validate_ok=False))
    workspace = WorkspaceHandle(root=tmp_path, instance_id="inst-001")
    loop.verify(make_candidate(), workspace)

    with pytest.raises(ValueError, match="cannot finalize unverified hypothesis"):
        loop.finalize_verified("cand-001", workspace)


def test_finalize_verified_scores_only_validated_candidates(tmp_path) -> None:
    adapter = VerifierFakeAdapter()
    loop = make_loop(tmp_path, adapter)
    workspace = WorkspaceHandle(root=tmp_path, instance_id="inst-001")
    loop.verify(make_candidate(), workspace)

    finalization = loop.finalize_verified("cand-001")

    assert finalization.strict_success is True
    assert adapter.finalized_workspace is not None
    assert adapter.finalized_workspace.root == tmp_path / "branch-a"
    assert finalization.contract_errors == ()
    assert loop.event_log.replay("run-001").counts_by_type["artifact.finalized"] == 1
    assert loop.event_log.replay("run-001").counts_by_type["score.completed"] == 1


def test_finalize_verified_logs_adapter_score_failure(tmp_path) -> None:
    loop = make_loop(tmp_path, VerifierFakeAdapter(score_ok=False))
    workspace = WorkspaceHandle(root=tmp_path, instance_id="inst-001")
    loop.verify(make_candidate(), workspace)

    finalization = loop.finalize_verified("cand-001", workspace)
    latest_score = loop.event_log.replay("run-001").latest_by_type["score.completed"]

    assert finalization.strict_success is False
    assert finalization.contract_errors == ()
    assert latest_score["payload"]["strict_success"] is False
