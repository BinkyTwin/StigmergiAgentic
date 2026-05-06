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
from core_v10.hypothesis_graph import HypothesisGraph, HypothesisScore
from core_v10.strategy_runner import StopReason, StrategyConfig, StrategyRunner


class RunnerFakeAdapter(DomainAdapterV10):
    name = "runner-fake"
    artifact_contract = ArtifactContract(required_artifacts=("answer.txt",))

    def __init__(self, *, validate_ok: bool = True, deliver_ok: bool = True) -> None:
        self.validate_ok = validate_ok
        self.deliver_ok = deliver_ok
        self.apply_base_roots: list[Path] = []

    def setup(self, instance: RunInstance) -> WorkspaceHandle:
        return WorkspaceHandle(
            root=Path("/tmp/v10-runner"),
            instance_id=instance.instance_id,
        )

    def observe(self, workspace: WorkspaceHandle) -> Observation:
        return Observation(summary="observed", data={"instance": workspace.instance_id})

    def capabilities(self) -> list[Capability]:
        return [Capability(name="unit", kind="validator")]

    def apply(self, candidate: Candidate, workspace: WorkspaceHandle) -> ApplyResult:
        self.apply_base_roots.append(workspace.root)
        branch_workspace = WorkspaceHandle(
            root=workspace.root / candidate.candidate_id,
            instance_id=f"{workspace.instance_id}:{candidate.candidate_id}",
            metadata=workspace.metadata,
        )
        return ApplyResult(
            candidate_id=candidate.candidate_id,
            applied=True,
            workspace=branch_workspace,
        )

    def validate(
        self, candidate: Candidate, workspace: WorkspaceHandle
    ) -> ValidationResult:
        candidate_valid = candidate.payload.get("answer") == "ok"
        return ValidationResult(
            candidate_id=candidate.candidate_id,
            status=ValidationStatus.PASSED
            if self.validate_ok and candidate_valid
            else ValidationStatus.FAILED,
            validator_name="unit",
            signals={"quality": candidate.payload.get("quality", 1.0)},
        )

    def diagnose(
        self, validation: ValidationResult, workspace: WorkspaceHandle
    ) -> FeedbackDigest:
        return FeedbackDigest(
            candidate_id=validation.candidate_id,
            failure_type="none" if validation.passed else "failed",
            severity="info" if validation.passed else "blocking",
            summary="ok" if validation.passed else "failed",
        )

    def finalize(
        self, candidate: Candidate, workspace: WorkspaceHandle
    ) -> ArtifactResult:
        artifacts = {"answer.txt": "ok"} if self.deliver_ok else {}
        return ArtifactResult(
            candidate_id=candidate.candidate_id,
            status=ArtifactStatus.DELIVERED,
            artifacts=artifacts,
        )

    def score(self, artifact: ArtifactResult) -> ScoreResult:
        return ScoreResult(
            candidate_id=artifact.candidate_id,
            strict_success=artifact.delivered,
            metrics={},
        )


def candidate_provider(_observation: Observation, _instance: RunInstance):
    return [
        Candidate(
            candidate_id="cand-001",
            kind=CandidateKind.TEXT,
            payload={"answer": "ok"},
            origin="unit-test",
        )
    ]


def bad_candidate_provider(_observation: Observation, _instance: RunInstance):
    return [
        Candidate(
            candidate_id="cand-bad",
            kind=CandidateKind.TEXT,
            payload={"answer": "bad"},
            origin="unit-test",
        )
    ]


def repair_provider(
    _feedback: FeedbackDigest,
    candidate: Candidate,
    _observation: Observation,
    _instance: RunInstance,
):
    return [
        Candidate(
            candidate_id=f"{candidate.candidate_id}-repair",
            kind=CandidateKind.TEXT,
            payload={"answer": "ok"},
            origin="repair-provider",
        )
    ]


def test_strategy_runner_executes_agentless_success_path(tmp_path) -> None:
    runner = StrategyRunner(
        adapter=RunnerFakeAdapter(),
        event_log_path=tmp_path / "events.jsonl",
    )
    instance = RunInstance(
        instance_id="inst-001",
        adapter_name="runner-fake",
        objective="solve fake task",
    )

    result = runner.run_agentless(
        run_id="run-001",
        instance=instance,
        candidate_provider=candidate_provider,
    )

    assert result.strict_success is True
    assert result.stop_reason == StopReason.STRICT_SUCCESS
    assert result.selected_hypothesis_id == "cand-001"
    assert result.finalization is not None
    assert result.replay is not None
    assert result.blackboard is not None
    assert result.replay.counts_by_type["run.completed"] == 1


def test_strategy_runner_stops_when_no_candidate_is_generated(tmp_path) -> None:
    runner = StrategyRunner(
        adapter=RunnerFakeAdapter(),
        event_log_path=tmp_path / "events.jsonl",
    )
    instance = RunInstance(
        instance_id="inst-001",
        adapter_name="runner-fake",
        objective="solve fake task",
    )

    result = runner.run_agentless(
        run_id="run-001",
        instance=instance,
        candidate_provider=lambda _observation, _instance: [],
    )

    assert result.strict_success is False
    assert result.stop_reason == StopReason.NO_CANDIDATE_GENERATED
    assert result.candidate_count == 0


def test_strategy_runner_stops_when_all_candidates_fail_validation(tmp_path) -> None:
    runner = StrategyRunner(
        adapter=RunnerFakeAdapter(),
        event_log_path=tmp_path / "events.jsonl",
    )
    instance = RunInstance(
        instance_id="inst-001",
        adapter_name="runner-fake",
        objective="solve fake task",
    )

    result = runner.run_agentless(
        run_id="run-001",
        instance=instance,
        candidate_provider=bad_candidate_provider,
    )

    assert result.strict_success is False
    assert result.stop_reason == StopReason.ALL_CANDIDATES_INVALID
    assert result.selected_hypothesis_id is None


def test_strategy_runner_branching_repair_selects_repaired_candidate(tmp_path) -> None:
    adapter = RunnerFakeAdapter()
    runner = StrategyRunner(
        adapter=adapter,
        event_log_path=tmp_path / "events.jsonl",
    )
    instance = RunInstance(
        instance_id="inst-001",
        adapter_name="runner-fake",
        objective="solve fake task",
    )

    result = runner.run_branching_repair(
        run_id="run-001",
        instance=instance,
        candidate_provider=bad_candidate_provider,
        repair_provider=repair_provider,
        config=StrategyConfig(
            name="branching_repair",
            max_candidates=1,
            max_repair_rounds=1,
        ),
    )

    assert result.strict_success is True
    assert result.selected_hypothesis_id == "cand-bad-repair"
    assert result.blackboard is not None
    assert result.blackboard.metrics["branching_factor"] == 1.0
    assert [node.hypothesis_id for node in runner.graph.lineage("cand-bad-repair")] == [
        "cand-bad",
        "cand-bad-repair",
    ]
    assert adapter.apply_base_roots[1] == (
        Path("/tmp/v10-runner") / "cand-bad"
    )


def test_strategy_runner_branching_repair_stops_when_repairs_fail(tmp_path) -> None:
    runner = StrategyRunner(
        adapter=RunnerFakeAdapter(),
        event_log_path=tmp_path / "events.jsonl",
    )
    instance = RunInstance(
        instance_id="inst-001",
        adapter_name="runner-fake",
        objective="solve fake task",
    )

    result = runner.run_branching_repair(
        run_id="run-001",
        instance=instance,
        candidate_provider=bad_candidate_provider,
        repair_provider=lambda _feedback, _candidate, _observation, _instance: [],
        config=StrategyConfig(
            name="branching_repair",
            max_candidates=1,
            max_repair_rounds=1,
        ),
    )

    assert result.strict_success is False
    assert result.stop_reason == StopReason.REPAIR_EXHAUSTED
    assert result.blackboard is not None
    assert result.blackboard.failed_hypotheses == ("cand-bad",)


def test_branching_repair_continues_from_best_observed_parent(tmp_path) -> None:
    class FunnelAdapter(RunnerFakeAdapter):
        def validate(
            self, candidate: Candidate, workspace: WorkspaceHandle
        ) -> ValidationResult:
            signals = dict(candidate.payload.get("signals", {}))
            return ValidationResult(
                candidate_id=candidate.candidate_id,
                status=ValidationStatus.FAILED,
                validator_name="unit",
                signals=signals,
                summary="not strict yet",
            )

    runner = StrategyRunner(
        adapter=FunnelAdapter(),
        event_log_path=tmp_path / "events.jsonl",
    )
    instance = RunInstance(
        instance_id="inst-001",
        adapter_name="runner-fake",
        objective="solve fake task",
    )
    repaired_parents: list[str] = []

    def provide(_observation, _instance):
        return [
            Candidate(
                candidate_id="cand-patch",
                kind=CandidateKind.TEXT,
                payload={"signals": {"patch_applies": True}},
                origin="unit-test",
            ),
            Candidate(
                candidate_id="cand-compile",
                kind=CandidateKind.TEXT,
                payload={"signals": {"compile_success": True}},
                origin="unit-test",
            ),
        ]

    def repair(_feedback, candidate, _observation, _instance):
        repaired_parents.append(candidate.candidate_id)
        return []

    result = runner.run_branching_repair(
        run_id="run-001",
        instance=instance,
        candidate_provider=provide,
        repair_provider=repair,
        config=StrategyConfig(
            name="branching_repair",
            max_candidates=2,
            max_repair_rounds=1,
        ),
    )

    assert repaired_parents == ["cand-compile"]
    assert result.stop_reason == StopReason.REPAIR_EXHAUSTED
    assert result.selected_hypothesis_id == "cand-compile"
    assert result.best_observed == {
        "best_candidate_id": "cand-compile",
        "best_hypothesis_id": "cand-compile",
        "best_funnel_score": 40,
        "best_stage": "compile_success",
        "best_feedback": {
            "candidate_id": "cand-compile",
            "failure_type": "failed",
            "severity": "blocking",
            "summary": "failed",
            "locations": [],
            "evidence": [],
            "candidate_causes": [],
            "recommended_next_actions": [],
            "anti_actions": [],
            "metadata": {},
        },
        "best_signals": {"compile_success": True},
        "best_validation_status": "failed",
    }
    assert any(
        event.event_type == "artifact.best_partial"
        and event.hypothesis_id == "cand-compile"
        for event in runner.event_log.for_run("run-001")
    )


def test_strategy_runner_falls_back_to_next_validated_finalization(tmp_path) -> None:
    class FallbackAdapter(RunnerFakeAdapter):
        def finalize(
            self, candidate: Candidate, workspace: WorkspaceHandle
        ) -> ArtifactResult:
            artifacts = (
                {}
                if candidate.candidate_id == "cand-high"
                else {"answer.txt": "ok"}
            )
            return ArtifactResult(
                candidate_id=candidate.candidate_id,
                status=ArtifactStatus.DELIVERED,
                artifacts=artifacts,
            )

    runner = StrategyRunner(
        adapter=FallbackAdapter(),
        event_log_path=tmp_path / "events.jsonl",
    )
    instance = RunInstance(
        instance_id="inst-001",
        adapter_name="runner-fake",
        objective="solve fake task",
    )

    result = runner.run_agentless(
        run_id="run-001",
        instance=instance,
        candidate_provider=lambda _observation, _instance: [
            Candidate(
                candidate_id="cand-low",
                kind=CandidateKind.TEXT,
                payload={"answer": "ok"},
                origin="unit-test",
            ),
            Candidate(
                candidate_id="cand-high",
                kind=CandidateKind.TEXT,
                payload={"answer": "ok", "quality": 9},
                origin="unit-test",
            ),
        ],
        config=StrategyConfig(max_candidates=2),
    )

    assert result.strict_success is True
    assert result.selected_hypothesis_id == "cand-low"


def test_strategy_runner_reports_artifact_contract_failure(tmp_path) -> None:
    runner = StrategyRunner(
        adapter=RunnerFakeAdapter(deliver_ok=False),
        event_log_path=tmp_path / "events.jsonl",
    )
    instance = RunInstance(
        instance_id="inst-001",
        adapter_name="runner-fake",
        objective="solve fake task",
    )

    result = runner.run_agentless(
        run_id="run-001",
        instance=instance,
        candidate_provider=candidate_provider,
        config=StrategyConfig(max_candidates=1),
    )

    assert result.strict_success is False
    assert result.stop_reason == StopReason.ARTIFACT_CONTRACT_FAILED
    assert result.finalization is not None
    assert result.finalization.contract_errors == ("missing artifact: answer.txt",)


def test_strategy_runner_starts_each_run_with_fresh_graph(tmp_path) -> None:
    graph = HypothesisGraph()
    graph.add_candidate(
        Candidate(
            candidate_id="stale",
            kind=CandidateKind.TEXT,
            payload={},
            origin="previous-run",
        )
    )
    graph.attach_validation(
        "stale",
        ValidationResult(
            candidate_id="stale",
            status=ValidationStatus.PASSED,
            validator_name="unit",
        ),
        score=HypothesisScore(quality=100.0),
    )
    runner = StrategyRunner(
        adapter=RunnerFakeAdapter(),
        event_log_path=tmp_path / "events.jsonl",
        graph=graph,
    )
    instance = RunInstance(
        instance_id="inst-001",
        adapter_name="runner-fake",
        objective="solve fake task",
    )

    result = runner.run_agentless(
        run_id="run-001",
        instance=instance,
        candidate_provider=candidate_provider,
    )

    assert result.selected_hypothesis_id == "cand-001"
    assert [node.hypothesis_id for node in runner.graph.nodes()] == ["cand-001"]


def test_strategy_runner_reuses_instance_without_candidate_id_contamination(
    tmp_path,
) -> None:
    runner = StrategyRunner(
        adapter=RunnerFakeAdapter(),
        event_log_path=tmp_path / "events.jsonl",
    )
    first = RunInstance(
        instance_id="inst-001",
        adapter_name="runner-fake",
        objective="solve first task",
    )
    second = RunInstance(
        instance_id="inst-002",
        adapter_name="runner-fake",
        objective="solve second task",
    )

    first_result = runner.run_agentless(
        run_id="run-001",
        instance=first,
        candidate_provider=candidate_provider,
    )
    second_result = runner.run_agentless(
        run_id="run-002",
        instance=second,
        candidate_provider=candidate_provider,
    )

    assert first_result.strict_success is True
    assert second_result.strict_success is True
    assert second_result.replay is not None
    assert second_result.replay.run_id == "run-002"
