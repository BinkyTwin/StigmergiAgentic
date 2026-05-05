from __future__ import annotations

from pathlib import Path

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
    to_jsonable,
)


class FakeAdapter(DomainAdapterV10):
    name = "fake"
    artifact_contract = ArtifactContract(
        required_artifacts=("answer.txt",),
        required_metrics=("strict_success", "local_valid"),
    )

    def setup(self, instance: RunInstance) -> WorkspaceHandle:
        return WorkspaceHandle(
            root=Path("/tmp/fake-workspace"),
            instance_id=instance.instance_id,
            metadata={"objective": instance.objective},
        )

    def observe(self, workspace: WorkspaceHandle) -> Observation:
        return Observation(
            summary="fake task observed",
            data={"workspace": str(workspace.root)},
        )

    def capabilities(self) -> list[Capability]:
        return [
            Capability(
                name="fake_validator",
                kind="validator",
                description="Deterministic fake validator.",
            )
        ]

    def apply(self, candidate: Candidate, workspace: WorkspaceHandle) -> ApplyResult:
        return ApplyResult(
            candidate_id=candidate.candidate_id,
            applied=True,
            workspace=workspace,
            summary="candidate applied",
            artifacts={"answer.txt": candidate.payload["answer"]},
        )

    def validate(
        self, candidate: Candidate, workspace: WorkspaceHandle
    ) -> ValidationResult:
        return ValidationResult(
            candidate_id=candidate.candidate_id,
            status=ValidationStatus.PASSED,
            validator_name="fake_validator",
            signals={"local_valid": True},
            summary=f"validated in {workspace.instance_id}",
        )

    def diagnose(
        self, validation: ValidationResult, workspace: WorkspaceHandle
    ) -> FeedbackDigest:
        return FeedbackDigest(
            candidate_id=validation.candidate_id,
            failure_type="none",
            severity="info",
            summary="no failure",
        )

    def finalize(
        self, candidate: Candidate, workspace: WorkspaceHandle
    ) -> ArtifactResult:
        return ArtifactResult(
            candidate_id=candidate.candidate_id,
            status=ArtifactStatus.DELIVERED,
            artifacts={"answer.txt": candidate.payload["answer"]},
            summary="artifact delivered",
        )

    def score(self, artifact: ArtifactResult) -> ScoreResult:
        errors = self.artifact_contract.validate_artifact(artifact)
        return ScoreResult(
            candidate_id=artifact.candidate_id,
            strict_success=not errors,
            metrics={"local_valid": not errors},
            summary="strict success" if not errors else "; ".join(errors),
        )


def test_fake_adapter_exercises_minimal_v10_contract() -> None:
    adapter = FakeAdapter()
    instance = RunInstance(
        instance_id="fake-001",
        adapter_name=adapter.name,
        objective="produce a checked artifact",
    )
    candidate = Candidate(
        candidate_id="cand-001",
        kind=CandidateKind.TEXT,
        payload={"answer": "ok"},
        origin="unit-test",
    )

    workspace = adapter.setup(instance)
    observation = adapter.observe(workspace)
    capabilities = adapter.capabilities()
    apply_result = adapter.apply(candidate, workspace)
    validation = adapter.validate(candidate, workspace)
    feedback = adapter.diagnose(validation, workspace)
    artifact = adapter.finalize(candidate, workspace)
    score = adapter.score(artifact)

    assert observation.summary == "fake task observed"
    assert capabilities[0].kind == "validator"
    assert apply_result.applied is True
    assert validation.passed is True
    assert feedback.is_blocking is False
    assert artifact.delivered is True
    assert score.strict_success is True
    assert adapter.artifact_contract.validate_score(score) == []


def test_artifact_contract_rejects_missing_required_artifact() -> None:
    contract = ArtifactContract(required_artifacts=("patch.diff",))
    artifact = ArtifactResult(
        candidate_id="cand-001",
        status=ArtifactStatus.DELIVERED,
        artifacts={},
    )

    assert contract.validate_artifact(artifact) == ["missing artifact: patch.diff"]


def test_artifact_contract_rejects_empty_required_artifact() -> None:
    contract = ArtifactContract(required_artifacts=("patch.diff",))
    artifact = ArtifactResult(
        candidate_id="cand-001",
        status=ArtifactStatus.DELIVERED,
        artifacts={"patch.diff": ""},
    )

    assert contract.validate_artifact(artifact) == ["empty artifact: patch.diff"]


def test_artifact_contract_rejects_missing_artifact_path(tmp_path) -> None:
    contract = ArtifactContract(required_artifacts=("patch.diff",))
    artifact = ArtifactResult(
        candidate_id="cand-001",
        status=ArtifactStatus.DELIVERED,
        artifacts={"patch.diff": tmp_path / "missing.patch"},
    )

    assert contract.validate_artifact(artifact) == [
        "artifact path does not exist: patch.diff"
    ]


def test_artifact_contract_rejects_directory_artifact(tmp_path) -> None:
    artifact_dir = tmp_path / "patch-dir"
    artifact_dir.mkdir()
    contract = ArtifactContract(required_artifacts=("patch.diff",))
    artifact = ArtifactResult(
        candidate_id="cand-001",
        status=ArtifactStatus.DELIVERED,
        artifacts={"patch.diff": artifact_dir},
    )

    assert contract.validate_artifact(artifact) == [
        "artifact path is not a file: patch.diff"
    ]


def test_artifact_contract_rejects_unsupported_artifact_type() -> None:
    contract = ArtifactContract(required_artifacts=("patch.diff",))
    artifact = ArtifactResult(
        candidate_id="cand-001",
        status=ArtifactStatus.DELIVERED,
        artifacts={"patch.diff": {"not": "a supported artifact"}},
    )

    assert contract.validate_artifact(artifact) == [
        "unsupported artifact type: patch.diff"
    ]


def test_contract_values_are_jsonable() -> None:
    candidate = Candidate(
        candidate_id="cand-001",
        kind=CandidateKind.PATCH,
        payload={"path": Path("patch.diff")},
        origin="unit-test",
    )

    serialized = to_jsonable(candidate)

    assert serialized["kind"] == "patch"
    assert serialized["payload"]["path"] == "patch.diff"
