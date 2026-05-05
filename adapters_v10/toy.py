"""Deterministic toy adapter for V10 end-to-end contract tests."""

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
)


class ToyTextAdapter(DomainAdapterV10):
    """Small adapter that validates whether a candidate writes expected text."""

    name = "toy_text"
    artifact_contract = ArtifactContract(required_artifacts=("answer.txt",))

    def setup(self, instance: RunInstance) -> WorkspaceHandle:
        workspace_root = Path(instance.metadata["workspace_root"])
        workspace_root.mkdir(parents=True, exist_ok=True)
        return WorkspaceHandle(
            root=workspace_root,
            instance_id=instance.instance_id,
            metadata={"expected": instance.metadata["expected"]},
        )

    def observe(self, workspace: WorkspaceHandle) -> Observation:
        return Observation(
            summary="write the expected answer text",
            data={"expected": workspace.metadata["expected"]},
        )

    def capabilities(self) -> list[Capability]:
        return [
            Capability(
                name="exact_text_validator",
                kind="validator",
                description="Checks whether answer.txt equals the expected text.",
            )
        ]

    def apply(self, candidate: Candidate, workspace: WorkspaceHandle) -> ApplyResult:
        if candidate.kind != CandidateKind.TEXT:
            return ApplyResult(
                candidate_id=candidate.candidate_id,
                applied=False,
                workspace=workspace,
                summary="unsupported candidate kind",
                errors=[f"unsupported candidate kind: {candidate.kind.value}"],
            )

        branch_workspace = WorkspaceHandle(
            root=workspace.root / candidate.candidate_id,
            instance_id=f"{workspace.instance_id}:{candidate.candidate_id}",
            metadata=workspace.metadata,
        )
        branch_workspace.root.mkdir(parents=True, exist_ok=True)
        answer = str(candidate.payload.get("answer", ""))
        answer_path = branch_workspace.root / "answer.txt"
        answer_path.write_text(answer, encoding="utf-8")
        return ApplyResult(
            candidate_id=candidate.candidate_id,
            applied=True,
            workspace=branch_workspace,
            artifacts={"answer.txt": answer_path},
            summary="candidate answer written",
        )

    def validate(
        self, candidate: Candidate, workspace: WorkspaceHandle
    ) -> ValidationResult:
        answer_path = workspace.root / "answer.txt"
        expected = str(workspace.metadata["expected"])
        if not answer_path.exists():
            return ValidationResult(
                candidate_id=candidate.candidate_id,
                status=ValidationStatus.ERROR,
                validator_name="exact_text_validator",
                signals={"artifact_exists": False},
                summary="answer artifact missing",
                errors=["answer.txt is missing"],
            )

        actual = answer_path.read_text(encoding="utf-8")
        passed = actual == expected
        return ValidationResult(
            candidate_id=candidate.candidate_id,
            status=ValidationStatus.PASSED if passed else ValidationStatus.FAILED,
            validator_name="exact_text_validator",
            signals={
                "artifact_exists": True,
                "exact_match": passed,
                "actual": actual,
                "expected": expected,
            },
            summary="answer matched" if passed else "answer mismatch",
        )

    def diagnose(
        self, validation: ValidationResult, workspace: WorkspaceHandle
    ) -> FeedbackDigest:
        if validation.passed:
            return FeedbackDigest(
                candidate_id=validation.candidate_id,
                failure_type="none",
                severity="info",
                summary="no failure",
            )
        return FeedbackDigest(
            candidate_id=validation.candidate_id,
            failure_type="answer_mismatch",
            severity="blocking",
            summary=validation.summary,
            evidence=[
                f"actual={validation.signals.get('actual', '')}",
                f"expected={validation.signals.get('expected', '')}",
            ],
            candidate_causes=["candidate answer did not match expected text"],
            recommended_next_actions=[
                {
                    "action": "replace_answer",
                    "target": "answer.txt",
                    "rationale": "Write the expected text exactly.",
                }
            ],
            anti_actions=["do not reuse the same wrong answer"],
        )

    def finalize(
        self, candidate: Candidate, workspace: WorkspaceHandle
    ) -> ArtifactResult:
        answer_path = workspace.root / "answer.txt"
        status = (
            ArtifactStatus.DELIVERED
            if answer_path.exists()
            else ArtifactStatus.MISSING
        )
        return ArtifactResult(
            candidate_id=candidate.candidate_id,
            status=status,
            artifacts={"answer.txt": answer_path} if answer_path.exists() else {},
            summary="answer artifact finalized",
        )

    def score(self, artifact: ArtifactResult) -> ScoreResult:
        path = artifact.artifacts.get("answer.txt")
        strict_success = artifact.delivered and isinstance(path, Path) and path.exists()
        return ScoreResult(
            candidate_id=artifact.candidate_id,
            strict_success=strict_success,
            metrics={"artifact_delivered": artifact.delivered},
            summary="strict success" if strict_success else "artifact missing",
        )
