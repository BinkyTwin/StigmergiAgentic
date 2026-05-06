"""B6 guard tests for free-form LLM fallback candidates."""

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
from core_v10.stigmergy.events import OPERATOR_UNAVAILABLE_EVENT
from core_v10.strategy_runner import StopReason, StrategyConfig, StrategyRunner


class GuardedFallbackAdapter(DomainAdapterV10):
    """Adapter that exposes a real parent branch file to the B6 guard."""

    name = "guarded-fallback"
    artifact_contract = ArtifactContract(required_artifacts=("patch.diff",))

    def __init__(self, root: Path) -> None:
        self.root = root
        self.applied_candidate_ids: list[str] = []
        self.validated_candidate_ids: list[str] = []

    def setup(self, instance: RunInstance) -> WorkspaceHandle:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "pom.xml").write_text(
            "<project><name>real-parent</name></project>\n",
            encoding="utf-8",
        )
        return WorkspaceHandle(root=self.root, instance_id=instance.instance_id)

    def observe(self, workspace: WorkspaceHandle) -> Observation:
        return Observation(summary="guarded", data={"path": "pom.xml"})

    def capabilities(self) -> list[Capability]:
        return []

    def apply(self, candidate: Candidate, workspace: WorkspaceHandle) -> ApplyResult:
        self.applied_candidate_ids.append(candidate.candidate_id)
        branch = workspace.root / candidate.candidate_id
        branch.mkdir(parents=True, exist_ok=True)
        source = workspace.root / "pom.xml"
        if source.exists():
            (branch / "pom.xml").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        return ApplyResult(
            candidate_id=candidate.candidate_id,
            applied=True,
            workspace=WorkspaceHandle(
                root=branch,
                instance_id=f"{workspace.instance_id}:{candidate.candidate_id}",
            ),
        )

    def validate(self, candidate: Candidate, workspace: WorkspaceHandle) -> ValidationResult:
        self.validated_candidate_ids.append(candidate.candidate_id)
        return ValidationResult(
            candidate_id=candidate.candidate_id,
            status=ValidationStatus.FAILED,
            validator_name="guarded-unit",
            signals={"patch_applies": True},
            summary="replacement_count_too_low in pom.xml",
            errors=["replacement_count_too_low"],
        )

    def diagnose(
        self, validation: ValidationResult, workspace: WorkspaceHandle
    ) -> FeedbackDigest:
        return FeedbackDigest(
            candidate_id=validation.candidate_id,
            failure_type="replacement_count_too_low",
            severity="blocking",
            summary="replacement_count_too_low in pom.xml",
            locations=[{"path": "pom.xml"}],
            evidence=["old span was not found"],
        )

    def finalize(self, candidate: Candidate, workspace: WorkspaceHandle) -> ArtifactResult:
        return ArtifactResult(
            candidate_id=candidate.candidate_id,
            status=ArtifactStatus.MISSING,
            artifacts={},
        )

    def score(self, artifact: ArtifactResult) -> ScoreResult:
        return ScoreResult(
            candidate_id=artifact.candidate_id,
            strict_success=False,
            metrics={"strict_success": False},
        )


def test_b6_rejects_invalid_llm_fallback_before_adapter_validation(tmp_path: Path) -> None:
    adapter = GuardedFallbackAdapter(tmp_path / "workspace")
    runner = StrategyRunner(
        adapter=adapter,
        event_log_path=tmp_path / "events.jsonl",
    )
    instance = RunInstance(
        instance_id="inst-b6-guard",
        adapter_name="guarded-fallback",
        objective="reject unsafe repair fallback",
    )

    def candidate_provider(_observation, _instance):
        return [
            Candidate(
                candidate_id="llm-initial",
                kind=CandidateKind.PATCH,
                payload={"note": "initial candidate intentionally fails validation"},
                origin="llm_initial",
            )
        ]

    def operator_provider(_feedback, _candidate, _observation, _instance, _affordance):
        return []

    def repair_provider(_feedback, _candidate, _observation, _instance):
        return [
            Candidate(
                candidate_id="llm-repair-invalid",
                kind=CandidateKind.PATCH,
                payload={
                    "edit_set": {
                        "edits": [
                            {
                                "type": "replace_text",
                                "path": "pom.xml",
                                "old": "<name>prompt-only</name>",
                                "new": "<name>fixed</name>",
                                "expected_replacements": 1,
                            }
                        ]
                    }
                },
                origin="llm_repair_fallback_no_operator_candidate",
            )
        ]

    result = runner.run_operator_search(
        run_id="run-b6-guard",
        instance=instance,
        candidate_provider=candidate_provider,
        repair_provider=repair_provider,
        operator_provider=operator_provider,
        config=StrategyConfig(
            name="operator_search",
            max_candidates=1,
            max_repair_rounds=1,
            max_repairs_per_candidate=1,
            fallback_policy="guarded_only",
        ),
    )

    events = runner.event_log.for_run("run-b6-guard")
    event_types = [event.event_type for event in events]

    assert result.stop_reason == StopReason.REPAIR_EXHAUSTED
    assert adapter.applied_candidate_ids == ["llm-initial"]
    assert adapter.validated_candidate_ids == ["llm-initial"]
    assert OPERATOR_UNAVAILABLE_EVENT in event_types
    assert "candidate.rejected" in event_types
    assert "llm-repair-invalid" not in {
        event.payload.get("candidate", {}).get("candidate_id")
        for event in events
        if event.event_type == "candidate.created"
    }

    rejection = next(event for event in events if event.event_type == "candidate.rejected")
    assert rejection.payload["candidate_id"] == "llm-repair-invalid"
    assert rejection.payload["guard"]["ok"] is False
    assert rejection.payload["guard"]["issues"][0]["reason"] == "old_span_absent"

    signal_targets = [
        event.payload.get("record", {}).get("target")
        for event in events
        if event.event_type == "signal.emitted"
    ]
    assert "origin:llm_repair_fallback_no_operator_candidate" in signal_targets
    assert "action:free_replace_text" in signal_targets
    assert "worker:exact_edit_guard" in signal_targets
