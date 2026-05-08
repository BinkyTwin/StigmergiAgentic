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
from core_v10.stigmergy.events import (
    OPERATOR_REJECTED_EVENT,
    OPERATOR_UNAVAILABLE_EVENT,
)
from core_v10.strategy_runner import StopReason, StrategyConfig, StrategyRunner
from core_v10.strategy_runner import _annotate_v11_candidate


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
            (branch / "pom.xml").write_text(
                source.read_text(encoding="utf-8"), encoding="utf-8"
            )
        return ApplyResult(
            candidate_id=candidate.candidate_id,
            applied=True,
            workspace=WorkspaceHandle(
                root=branch,
                instance_id=f"{workspace.instance_id}:{candidate.candidate_id}",
            ),
        )

    def validate(
        self, candidate: Candidate, workspace: WorkspaceHandle
    ) -> ValidationResult:
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

    def finalize(
        self, candidate: Candidate, workspace: WorkspaceHandle
    ) -> ArtifactResult:
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


def test_b6_rejects_invalid_llm_fallback_before_adapter_validation(
    tmp_path: Path,
) -> None:
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
    assert result.selected_hypothesis_id is None
    assert adapter.applied_candidate_ids == ["llm-initial"]
    assert adapter.validated_candidate_ids == ["llm-initial"]
    assert OPERATOR_UNAVAILABLE_EVENT in event_types
    assert "candidate.rejected" in event_types
    assert "llm-repair-invalid" not in {
        event.payload.get("candidate", {}).get("candidate_id")
        for event in events
        if event.event_type == "candidate.created"
    }

    rejection = next(
        event for event in events if event.event_type == "candidate.rejected"
    )
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


def test_b6_exports_best_partial_for_non_terminal_funnel_progress(
    tmp_path: Path,
) -> None:
    class PartialAdapter(GuardedFallbackAdapter):
        def validate(
            self, candidate: Candidate, workspace: WorkspaceHandle
        ) -> ValidationResult:
            self.validated_candidate_ids.append(candidate.candidate_id)
            return ValidationResult(
                candidate_id=candidate.candidate_id,
                status=ValidationStatus.PARTIAL,
                validator_name="guarded-unit",
                signals={"compile_success": True},
                summary="compile succeeded but tests still fail",
            )

        def diagnose(
            self, validation: ValidationResult, workspace: WorkspaceHandle
        ) -> FeedbackDigest:
            return FeedbackDigest(
                candidate_id=validation.candidate_id,
                failure_type="test_failure",
                severity="blocking",
                summary="tests still fail",
            )

    adapter = PartialAdapter(tmp_path / "workspace")
    runner = StrategyRunner(
        adapter=adapter,
        event_log_path=tmp_path / "events.jsonl",
    )
    instance = RunInstance(
        instance_id="inst-b6-partial",
        adapter_name="guarded-fallback",
        objective="track partial funnel progress",
    )

    result = runner.run_operator_search(
        run_id="run-b6-partial",
        instance=instance,
        candidate_provider=lambda _observation, _instance: [
            Candidate(
                candidate_id="llm-initial",
                kind=CandidateKind.PATCH,
                payload={},
                origin="llm_initial",
            )
        ],
        repair_provider=lambda _feedback, _candidate, _observation, _instance: [],
        operator_provider=lambda _feedback, _candidate, _observation, _instance, _affordance: [],
        config=StrategyConfig(
            name="operator_search",
            max_candidates=1,
            max_repair_rounds=1,
            max_repairs_per_candidate=1,
            fallback_policy="guarded_only",
        ),
    )

    events = runner.event_log.for_run("run-b6-partial")
    assert result.stop_reason == StopReason.REPAIR_EXHAUSTED
    assert result.selected_hypothesis_id == "llm-initial"
    assert result.best_observed["best_candidate_id"] == "llm-initial"
    assert result.best_observed["best_funnel_score"] == 40
    assert result.best_observed["best_stage"] == "compile_success"
    assert any(
        event.event_type == "artifact.best_partial"
        and event.hypothesis_id == "llm-initial"
        for event in events
    )


def test_b6_rejects_operator_candidate_that_regresses_parent_funnel(
    tmp_path: Path,
) -> None:
    class RegressionAdapter(GuardedFallbackAdapter):
        def validate(
            self, candidate: Candidate, workspace: WorkspaceHandle
        ) -> ValidationResult:
            self.validated_candidate_ids.append(candidate.candidate_id)
            if "op" in candidate.candidate_id:
                return ValidationResult(
                    candidate_id=candidate.candidate_id,
                    status=ValidationStatus.FAILED,
                    validator_name="guarded-unit",
                    signals={"patch_applies": True},
                    summary="operator regressed to patch_applies",
                )
            return ValidationResult(
                candidate_id=candidate.candidate_id,
                status=ValidationStatus.PARTIAL,
                validator_name="guarded-unit",
                signals={"test_success": True},
                summary="parent reached tests",
            )

        def diagnose(
            self, validation: ValidationResult, workspace: WorkspaceHandle
        ) -> FeedbackDigest:
            return FeedbackDigest(
                candidate_id=validation.candidate_id,
                failure_type="official_eval_failed",
                severity="blocking",
                summary=validation.summary,
                evidence=["official #tests=-2"],
            )

    adapter = RegressionAdapter(tmp_path / "workspace")
    runner = StrategyRunner(
        adapter=adapter,
        event_log_path=tmp_path / "events.jsonl",
    )
    instance = RunInstance(
        instance_id="inst-b6-regression",
        adapter_name="guarded-fallback",
        objective="reject regressed operator",
    )

    def operator_provider(_feedback, original, _observation, _instance, _affordance):
        return [
            Candidate(
                candidate_id=f"{original.candidate_id}-op",
                kind=CandidateKind.PATCH,
                payload={"branch_id": f"{original.candidate_id}-op"},
                origin="v11_operator_search",
                parent_id=original.candidate_id,
                metadata={
                    "worker_id": "maven_compiler_operator",
                    "operator_invocation": {
                        "operator_id": "MavenEnsureCompilerRelease",
                        "params": {
                            "failure_type": "official_eval_failed",
                            "action_type": "ensure_maven_compiler_release",
                        },
                        "target_files": ["pom.xml"],
                        "rationale": "unit regression candidate",
                    },
                },
            )
        ]

    result = runner.run_operator_search(
        run_id="run-b6-regression",
        instance=instance,
        candidate_provider=lambda _observation, _instance: [
            Candidate(
                candidate_id="llm-initial",
                kind=CandidateKind.PATCH,
                payload={},
                origin="llm_initial",
            )
        ],
        repair_provider=lambda _feedback, _candidate, _observation, _instance: [],
        operator_provider=operator_provider,
        config=StrategyConfig(
            name="operator_search",
            max_candidates=1,
            max_repair_rounds=1,
            max_repairs_per_candidate=1,
            fallback_policy="guarded_only",
        ),
    )

    events = runner.event_log.for_run("run-b6-regression")
    rejected = [
        event
        for event in events
        if event.event_type == OPERATOR_REJECTED_EVENT
        and event.payload.get("reason") == "operator_regressed_funnel"
    ]

    assert result.selected_hypothesis_id == "llm-initial"
    assert result.best_observed["best_stage"] == "test_success"
    assert rejected
    assert rejected[0].payload["parent_score"] == 60
    assert rejected[0].payload["operator_score"] == 20


def test_b6_annotation_preserves_adapter_parent_branch_for_repairs() -> None:
    parent = Candidate(
        candidate_id="inst-c1-llm0",
        kind=CandidateKind.PATCH,
        payload={"branch_id": "c1_llm0"},
        origin="llm_initial",
    )
    repair = Candidate(
        candidate_id="inst-c1-llm0-r0-llm0",
        kind=CandidateKind.PATCH,
        payload={
            "branch_id": "c1_llm_r0",
            "edit_set": {
                "edits": [
                    {
                        "type": "replace_text",
                        "path": "pom.xml",
                        "old": "<java.version>17</java.version>",
                        "new": "<java.version>17</java.version>",
                    }
                ]
            },
        },
        origin="llm_repair_deepseek-chat_t0",
    )

    annotated = _annotate_v11_candidate(
        repair,
        parent_id=parent.candidate_id,
        parent_candidate=parent,
        worker_id="maven_compiler_operator",
        decision_id="dec-1",
        affordance=None,
    )

    assert annotated.parent_id == parent.candidate_id
    assert annotated.payload["branch_id"] == "c1_llm_r0"
    assert annotated.payload["parent_branch_id"] == "c1_llm0"
