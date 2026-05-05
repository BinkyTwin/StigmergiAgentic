from __future__ import annotations

from core_v10.blackboard import build_blackboard
from core_v10.contracts import (
    Candidate,
    CandidateKind,
    FeedbackDigest,
    ValidationResult,
    ValidationStatus,
)
from core_v10.event_log import JsonlEventLog
from core_v10.hypothesis_graph import HypothesisGraph, HypothesisScore
from core_v10.signals import SignalKind


def test_blackboard_reconstructs_active_projection_from_events_and_graph(
    tmp_path,
) -> None:
    event_log = JsonlEventLog(tmp_path / "events.jsonl")
    event_log.append(
        run_id="run-001",
        instance_id="inst-001",
        event_type="validation.completed",
        actor="verifier",
        hypothesis_id="h-good",
        payload={"status": "passed"},
    )
    event_log.append(
        run_id="run-001",
        instance_id="inst-001",
        event_type="feedback.created",
        actor="diagnoser",
        hypothesis_id="h-bad",
        payload={"failure_type": "compile_error"},
    )

    graph = HypothesisGraph()
    graph.add_candidate(
        Candidate(
            candidate_id="h-good",
            kind=CandidateKind.PATCH,
            payload={},
            origin="unit-test",
        )
    )
    graph.attach_validation(
        "h-good",
        ValidationResult(
            candidate_id="h-good",
            status=ValidationStatus.PASSED,
            validator_name="unit",
        ),
        score=HypothesisScore(quality=0.8, confidence=0.6),
    )
    graph.add_candidate(
        Candidate(
            candidate_id="h-bad",
            kind=CandidateKind.PATCH,
            payload={},
            origin="unit-test",
        )
    )
    graph.attach_validation(
        "h-bad",
        ValidationResult(
            candidate_id="h-bad",
            status=ValidationStatus.FAILED,
            validator_name="unit",
        ),
    )
    graph.attach_feedback(
        "h-bad",
        FeedbackDigest(
            candidate_id="h-bad",
            failure_type="compile_error",
            severity="blocking",
            summary="compile failed",
        ),
    )
    graph.select_best(["h-good"])

    blackboard = build_blackboard(events=event_log.read_all(), graph=graph)

    assert blackboard.run_id == "run-001"
    assert blackboard.instance_id == "inst-001"
    assert blackboard.selected_hypothesis_id == "h-good"
    assert blackboard.validated_hypotheses == ("h-good",)
    assert blackboard.failed_hypotheses == ("h-bad",)
    assert blackboard.metrics["hypothesis_count"] == 2
    assert blackboard.metrics["feedback_events"] == 1
    assert blackboard.signals_by_kind(SignalKind.SUPPORT)
    assert blackboard.signals_by_kind(SignalKind.INHIBIT)[0].target == (
        "failure:compile_error"
    )
    assert blackboard.to_dict()["signals"]


def test_blackboard_can_reconstruct_graph_from_event_log_only(tmp_path) -> None:
    event_log = JsonlEventLog(tmp_path / "events.jsonl")
    event_log.append(
        run_id="run-001",
        instance_id="inst-001",
        event_type="candidate.created",
        actor="strategy",
        hypothesis_id="h-good",
        payload={
            "candidate": Candidate(
                candidate_id="h-good",
                kind=CandidateKind.TEXT,
                payload={"answer": "ok"},
                origin="unit-test",
            )
        },
    )
    event_log.append(
        run_id="run-001",
        instance_id="inst-001",
        event_type="validation.completed",
        actor="verifier",
        hypothesis_id="h-good",
        payload={
            "validation": ValidationResult(
                candidate_id="h-good",
                status=ValidationStatus.PASSED,
                validator_name="unit",
            )
        },
    )
    event_log.append(
        run_id="run-001",
        instance_id="inst-001",
        event_type="run.completed",
        actor="strategy_runner",
        payload={"selected_hypothesis_id": "h-good"},
    )

    blackboard = build_blackboard(events=event_log.read_all())

    assert blackboard.selected_hypothesis_id == "h-good"
    assert blackboard.validated_hypotheses == ("h-good",)
    assert blackboard.metrics["hypothesis_count"] == 1
