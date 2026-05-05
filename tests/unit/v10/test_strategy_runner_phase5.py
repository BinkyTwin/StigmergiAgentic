"""Phase 5 unit tests — branching_repair signature dedup, repeated failure
suppression, and explainable selection rationale."""

from __future__ import annotations

from dataclasses import replace
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
from core_v10.strategy_runner import (
    SelectionRationale,
    StopReason,
    StrategyConfig,
    StrategyRunner,
    _SignatureTracker,
)
from scripts.bench.telemetry import (
    DEDUPED_EVENT,
    REPEAT_FAILURE_EVENT,
    SELECTION_EVENT,
)


class FakeAdapter(DomainAdapterV10):
    """Tiny adapter whose validate/finalize behavior is steered by payload flags."""

    name = "phase5-fake"
    artifact_contract = ArtifactContract(required_artifacts=("answer.txt",))

    def setup(self, instance: RunInstance) -> WorkspaceHandle:
        return WorkspaceHandle(root=Path("/tmp/p5"), instance_id=instance.instance_id)

    def observe(self, workspace: WorkspaceHandle) -> Observation:
        return Observation(summary="phase5", data={})

    def capabilities(self) -> list[Capability]:
        return []

    def apply(self, candidate: Candidate, workspace: WorkspaceHandle) -> ApplyResult:
        branch = WorkspaceHandle(
            root=workspace.root / candidate.candidate_id,
            instance_id=f"{workspace.instance_id}:{candidate.candidate_id}",
        )
        return ApplyResult(
            candidate_id=candidate.candidate_id,
            applied=True,
            workspace=branch,
        )

    def validate(self, candidate: Candidate, workspace: WorkspaceHandle) -> ValidationResult:
        passed = bool(candidate.payload.get("passes", False))
        return ValidationResult(
            candidate_id=candidate.candidate_id,
            status=ValidationStatus.PASSED if passed else ValidationStatus.FAILED,
            validator_name="unit",
            signals={"quality": float(candidate.payload.get("quality", 1.0))},
        )

    def diagnose(self, validation: ValidationResult, workspace: WorkspaceHandle) -> FeedbackDigest:
        return FeedbackDigest(
            candidate_id=validation.candidate_id,
            failure_type="ok" if validation.passed else "fixable",
            severity="info" if validation.passed else "blocking",
            summary="diagnosis",
        )

    def finalize(self, candidate: Candidate, workspace: WorkspaceHandle) -> ArtifactResult:
        return ArtifactResult(
            candidate_id=candidate.candidate_id,
            status=ArtifactStatus.DELIVERED,
            artifacts={"answer.txt": "done"},
        )

    def score(self, artifact: ArtifactResult) -> ScoreResult:
        return ScoreResult(
            candidate_id=artifact.candidate_id,
            strict_success=True,
            metrics={"strict_success": True},
        )


def _instance() -> RunInstance:
    return RunInstance(
        instance_id="inst-p5",
        adapter_name="phase5-fake",
        objective="phase 5",
    )


def _candidate(candidate_id: str, *, passes: bool, quality: float = 1.0) -> Candidate:
    return Candidate(
        candidate_id=candidate_id,
        kind=CandidateKind.TEXT,
        payload={"passes": passes, "quality": quality},
        origin="phase5-test",
    )


def test_signature_tracker_treats_same_payload_as_one_signature() -> None:
    tracker = _SignatureTracker()
    a = _candidate("c1", passes=True)
    b = _candidate("c2", passes=True)
    assert tracker.signature(a) == tracker.signature(b)
    tracker.mark_seen(tracker.signature(a), "c1")
    assert tracker.first_seen_id(tracker.signature(b)) == "c1"


def test_signature_tracker_distinguishes_payloads() -> None:
    tracker = _SignatureTracker()
    a = _candidate("c1", passes=True, quality=1.0)
    b = _candidate("c2", passes=True, quality=9.0)
    assert tracker.signature(a) != tracker.signature(b)


def test_branching_repair_dedups_initial_duplicate_candidates(tmp_path) -> None:
    runner = StrategyRunner(
        adapter=FakeAdapter(),
        event_log_path=tmp_path / "events.jsonl",
    )

    def provide(_observation, _instance):
        return [
            _candidate("good-1", passes=True),
            _candidate("good-2", passes=True),  # same payload → duplicate signature
        ]

    def repair(_feedback, _candidate, _observation, _instance):
        return []

    result = runner.run_branching_repair(
        run_id="run-p5-dedup",
        instance=_instance(),
        candidate_provider=provide,
        repair_provider=repair,
        config=StrategyConfig(
            name="branching_repair",
            max_candidates=2,
            max_repair_rounds=0,
        ),
    )

    assert result.strict_success is True
    assert result.dedup_skipped == 1
    events = runner.event_log.for_run("run-p5-dedup")
    deduped = [e for e in events if e.event_type == DEDUPED_EVENT]
    assert len(deduped) == 1
    assert deduped[0].payload["duplicate_of"] == "good-1"
    assert deduped[0].payload["candidate_id"] == "good-2"


def test_branching_repair_suppresses_repair_with_already_failed_signature(
    tmp_path,
) -> None:
    runner = StrategyRunner(
        adapter=FakeAdapter(),
        event_log_path=tmp_path / "events.jsonl",
    )

    def provide(_observation, _instance):
        return [_candidate("bad-1", passes=False)]

    def repair(_feedback, parent, _observation, _instance):
        # propose a "repair" with the same payload-signature as the failure
        return [
            replace(parent, candidate_id=f"{parent.candidate_id}-repeat"),
        ]

    result = runner.run_branching_repair(
        run_id="run-p5-repeat",
        instance=_instance(),
        candidate_provider=provide,
        repair_provider=repair,
        config=StrategyConfig(
            name="branching_repair",
            max_candidates=1,
            max_repair_rounds=2,
            max_repairs_per_candidate=1,
        ),
    )

    assert result.strict_success is False
    assert result.stop_reason == StopReason.REPAIR_EXHAUSTED
    assert result.repeat_failure_suppressed >= 1
    events = runner.event_log.for_run("run-p5-repeat")
    suppressed = [e for e in events if e.event_type == REPEAT_FAILURE_EVENT]
    assert len(suppressed) >= 1
    assert suppressed[0].payload["previous_failures"] >= 1


def test_branching_repair_emits_selection_rationale_with_competitors(tmp_path) -> None:
    runner = StrategyRunner(
        adapter=FakeAdapter(),
        event_log_path=tmp_path / "events.jsonl",
    )

    def provide(_observation, _instance):
        return [
            _candidate("low-quality", passes=True, quality=1.0),
            _candidate("high-quality", passes=True, quality=9.0),
        ]

    def repair(_feedback, _candidate, _observation, _instance):
        return []

    result = runner.run_branching_repair(
        run_id="run-p5-selector",
        instance=_instance(),
        candidate_provider=provide,
        repair_provider=repair,
        config=StrategyConfig(
            name="branching_repair",
            max_candidates=2,
            max_repair_rounds=0,
        ),
    )

    assert result.strict_success is True
    assert isinstance(result.selection_rationale, SelectionRationale)
    rationale = result.selection_rationale
    assert rationale.selected_hypothesis_id == result.selected_hypothesis_id
    assert rationale.reason == "strict_success"
    competitor_ids = {item["hypothesis_id"] for item in rationale.competitors}
    assert competitor_ids == {"low-quality", "high-quality"}
    events = runner.event_log.for_run("run-p5-selector")
    selection_events = [e for e in events if e.event_type == SELECTION_EVENT]
    assert len(selection_events) == 1
    assert selection_events[0].payload["rationale"]["reason"] == "strict_success"


def test_agentless_emits_no_validated_candidate_rationale(tmp_path) -> None:
    runner = StrategyRunner(
        adapter=FakeAdapter(),
        event_log_path=tmp_path / "events.jsonl",
    )

    def provide(_observation, _instance):
        return [_candidate("bad", passes=False)]

    result = runner.run_agentless(
        run_id="run-p5-no-validated",
        instance=_instance(),
        candidate_provider=provide,
        config=StrategyConfig(name="agentless_basic", max_candidates=1),
    )

    assert result.strict_success is False
    assert result.stop_reason == StopReason.ALL_CANDIDATES_INVALID
    rationale = result.selection_rationale
    assert rationale is not None
    assert rationale.selected_hypothesis_id is None
    assert rationale.reason == "no_validated_candidate"
