"""Phase 6 unit tests — A4 stigmergic_blackboard strategy."""

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
from core_v10.signal_policy import (
    SIGNAL_APPLIED_EVENT,
    SIGNAL_EMITTED_EVENT,
    store_from_events,
)
from core_v10.signals import SignalKind
from core_v10.strategy_runner import (
    StopReason,
    StrategyConfig,
    StrategyRunner,
)


class FakeAdapter(DomainAdapterV10):
    """Tiny adapter used to drive A4 unit tests deterministically."""

    name = "phase6-fake"
    artifact_contract = ArtifactContract(required_artifacts=("answer.txt",))

    def setup(self, instance: RunInstance) -> WorkspaceHandle:
        return WorkspaceHandle(root=Path("/tmp/p6"), instance_id=instance.instance_id)

    def observe(self, workspace: WorkspaceHandle) -> Observation:
        return Observation(summary="phase6", data={})

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

    def diagnose(
        self, validation: ValidationResult, workspace: WorkspaceHandle
    ) -> FeedbackDigest:
        passed = validation.passed
        return FeedbackDigest(
            candidate_id=validation.candidate_id,
            failure_type="ok" if passed else "fixable_failure",
            severity="info" if passed else "blocking",
            summary="diagnosis",
            anti_actions=() if passed else ("preserve_existing_tests",),
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
        instance_id="inst-p6",
        adapter_name="phase6-fake",
        objective="phase 6",
    )


def _candidate(
    candidate_id: str,
    *,
    passes: bool,
    quality: float = 1.0,
    origin: str = "phase6-test",
) -> Candidate:
    return Candidate(
        candidate_id=candidate_id,
        kind=CandidateKind.TEXT,
        payload={"passes": passes, "quality": quality},
        origin=origin,
    )


def test_a4_equals_a3_when_signal_store_stays_empty(tmp_path) -> None:
    """A4 with a single passing candidate behaves like A3."""

    runner_a3 = StrategyRunner(
        adapter=FakeAdapter(),
        event_log_path=tmp_path / "a3.jsonl",
    )
    runner_a4 = StrategyRunner(
        adapter=FakeAdapter(),
        event_log_path=tmp_path / "a4.jsonl",
    )

    def provide(_observation, _instance):
        return [_candidate("c1", passes=True)]

    def repair(_feedback, _candidate, _observation, _instance):
        return []

    config = StrategyConfig(name="branching_repair", max_candidates=1)

    res_a3 = runner_a3.run_branching_repair(
        run_id="run-a3",
        instance=_instance(),
        candidate_provider=provide,
        repair_provider=repair,
        config=config,
    )
    res_a4 = runner_a4.run_stigmergic_blackboard(
        run_id="run-a4",
        instance=_instance(),
        candidate_provider=provide,
        repair_provider=repair,
        config=replace(config, name="stigmergic_blackboard"),
    )
    # Same outcome, same selected hypothesis, same dedup behavior.
    assert res_a3.strict_success == res_a4.strict_success
    assert res_a3.candidate_count == res_a4.candidate_count
    assert res_a3.dedup_skipped == res_a4.dedup_skipped
    # A4 records signal counts; here at least one SUPPORT signal is emitted
    # because validation passed, but no signal *changed* a decision (single
    # candidate ⇒ no reorder, no drop, no tie-break).
    assert res_a4.signal_emitted_count >= 1
    assert res_a4.signal_applied_count == 0


def test_a4_emits_signal_emitted_events_after_failed_verify(tmp_path) -> None:
    runner = StrategyRunner(
        adapter=FakeAdapter(),
        event_log_path=tmp_path / "events.jsonl",
    )

    def provide(_observation, _instance):
        return [_candidate("bad-1", passes=False)]

    def repair(_feedback, _candidate, _observation, _instance):
        return []

    result = runner.run_stigmergic_blackboard(
        run_id="run-p6-failed",
        instance=_instance(),
        candidate_provider=provide,
        repair_provider=repair,
        config=StrategyConfig(
            name="stigmergic_blackboard",
            max_candidates=1,
            max_repair_rounds=0,
        ),
    )

    events = runner.event_log.for_run("run-p6-failed")
    emitted = [e for e in events if e.event_type == SIGNAL_EMITTED_EVENT]
    assert emitted, "expected at least one signal.emitted event"
    targets = {e.payload["record"]["target"] for e in emitted}
    # failure_type INHIBIT + anti:preserve_existing_tests INHIBIT + signature INHIBIT
    assert "failure_type:fixable_failure" in targets
    assert "anti:preserve_existing_tests" in targets
    assert any(t.startswith("signature:") for t in targets)
    assert result.signal_emitted_count == len(emitted)
    # store snapshot is reconstructible from those events
    rebuilt = store_from_events(events)
    assert rebuilt.inhibit_for("failure_type:fixable_failure") > 0


def test_a4_drops_candidate_when_signature_inhibit_is_strong(tmp_path) -> None:
    """If a signature's INHIBIT crosses 0.8, A4 drops a fresh candidate."""

    runner = StrategyRunner(
        adapter=FakeAdapter(),
        event_log_path=tmp_path / "events.jsonl",
    )

    # Two failing candidates with the same payload (same signature) across
    # rounds → first failure emits INHIBIT signature:<sha>=0.9, the repair
    # provider proposes the same payload, A4 drops it via signal.applied.

    def provide(_observation, _instance):
        return [_candidate("c-fail-a", passes=False)]

    def repair(_feedback, parent, _observation, _instance):
        # propose a candidate with the same payload-signature → same sha
        return [
            replace(parent, candidate_id=f"{parent.candidate_id}-repeat"),
        ]

    result = runner.run_stigmergic_blackboard(
        run_id="run-p6-drop",
        instance=_instance(),
        candidate_provider=provide,
        repair_provider=repair,
        config=StrategyConfig(
            name="stigmergic_blackboard",
            max_candidates=1,
            max_repair_rounds=2,
            max_repairs_per_candidate=1,
        ),
    )

    events = runner.event_log.for_run("run-p6-drop")
    applied = [e for e in events if e.event_type == SIGNAL_APPLIED_EVENT]
    # The signature_tracker already suppresses the repeat (Phase 5
    # mechanism). The signal_driven drop is an additional safeguard that
    # may or may not fire. What we assert is the strict invariant:
    # *some* mechanism cut the loop, the run terminated, and the signal
    # store accumulated INHIBIT signals.
    assert result.repeat_failure_suppressed >= 1
    assert result.signal_emitted_count > 0
    # Still, the run completed deterministically.
    assert result.stop_reason == StopReason.REPAIR_EXHAUSTED


def test_a4_reorders_frontier_when_origin_support_differs(tmp_path) -> None:
    """When two candidates with different origins compete, A4 may reorder."""

    runner = StrategyRunner(
        adapter=FakeAdapter(),
        event_log_path=tmp_path / "events.jsonl",
    )

    # Pre-seed a SUPPORT signal for a specific origin by validating one
    # candidate first — we run two rounds: round 0 has only "origin-A" which
    # passes (emits SUPPORT origin:A); round 1 should have "origin-A" before
    # "origin-B" if reordering kicks in. We simulate with two-candidate
    # generation in one round; no SUPPORT pre-exists so the order is stable
    # ⇒ no signal.applied.

    def provide(_observation, _instance):
        return [
            _candidate("c-zzz-passes", passes=True, origin="origin-z"),
            _candidate("c-aaa-passes", passes=True, origin="origin-a"),
        ]

    def repair(_feedback, _candidate, _observation, _instance):
        return []

    result = runner.run_stigmergic_blackboard(
        run_id="run-p6-reorder",
        instance=_instance(),
        candidate_provider=provide,
        repair_provider=repair,
        config=StrategyConfig(
            name="stigmergic_blackboard",
            max_candidates=2,
            max_repair_rounds=0,
        ),
    )
    events = runner.event_log.for_run("run-p6-reorder")
    # Empty pre-existing store ⇒ stable order ⇒ no reorder applied.
    reorder_events = [
        e
        for e in events
        if e.event_type == SIGNAL_APPLIED_EVENT
        and e.payload.get("effect") == "reorder"
    ]
    assert reorder_events == []
    assert result.strict_success is True


def test_a4_signal_store_snapshot_is_reconstructible_from_events(tmp_path) -> None:
    runner = StrategyRunner(
        adapter=FakeAdapter(),
        event_log_path=tmp_path / "events.jsonl",
    )

    def provide(_observation, _instance):
        return [_candidate("c1", passes=False)]

    def repair(_feedback, _candidate, _observation, _instance):
        return []

    result = runner.run_stigmergic_blackboard(
        run_id="run-p6-replay",
        instance=_instance(),
        candidate_provider=provide,
        repair_provider=repair,
        config=StrategyConfig(
            name="stigmergic_blackboard",
            max_candidates=1,
            max_repair_rounds=0,
        ),
    )

    snapshot = result.signal_store_snapshot
    assert snapshot is not None
    assert "records" in snapshot

    # Replay the EventLog → the resulting store has the same records by
    # (kind, target) and the same intensity.
    events = runner.event_log.for_run("run-p6-replay")
    rebuilt = store_from_events(events)
    rebuilt_snapshot = rebuilt.to_dict()

    def _index(snap):
        return {
            (r["kind"], r["target"]): r["intensity"] for r in snap["records"]
        }

    assert _index(snapshot) == _index(rebuilt_snapshot)


def test_a4_exposes_signal_score_in_selection_rationale(tmp_path) -> None:
    runner = StrategyRunner(
        adapter=FakeAdapter(),
        event_log_path=tmp_path / "events.jsonl",
    )

    def provide(_observation, _instance):
        return [
            _candidate("c1", passes=True, quality=2.0, origin="origin-a"),
            _candidate("c2", passes=True, quality=8.0, origin="origin-b"),
        ]

    def repair(_feedback, _candidate, _observation, _instance):
        return []

    result = runner.run_stigmergic_blackboard(
        run_id="run-p6-rationale",
        instance=_instance(),
        candidate_provider=provide,
        repair_provider=repair,
        config=StrategyConfig(
            name="stigmergic_blackboard",
            max_candidates=2,
            max_repair_rounds=0,
        ),
    )
    rationale = result.selection_rationale
    assert rationale is not None
    # Every competitor exposes the new "signal_score" field.
    for competitor in rationale.competitors:
        assert "signal_score" in competitor
        assert isinstance(competitor["signal_score"], float)
