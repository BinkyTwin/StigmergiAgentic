"""V11 scheduler activation tests."""

from __future__ import annotations

from core_v10.contracts import FeedbackDigest
from core_v10.signals import SignalKind, SignalStore
from core_v10.stigmergy.records import Affordance
from core_v10.stigmergy.scheduler import StigmergicScheduler


def test_scheduler_selects_worker_matching_affordance_kind() -> None:
    affordance = Affordance(
        affordance_id="aff-compile",
        action_type="set_maven_compiler_release",
        target="pom.xml",
        reason="compile_error",
        priority=0.8,
        expected_worker_kind="maven_compiler_operator",
    )
    feedback = FeedbackDigest(
        candidate_id="c1",
        failure_type="compile_error",
        severity="blocking",
        summary="source option 5 is no longer supported",
    )
    store = SignalStore()
    signal = store.emit(
        kind=SignalKind.SUPPORT,
        target="worker:maven_compiler_operator",
        intensity=0.7,
        now_seq=1,
    )

    activation = StigmergicScheduler().select(
        decision_id="dec-1",
        affordances=(affordance,),
        signals=(signal,),
        feedback=feedback,
    )

    assert activation.worker.worker_id == "maven_compiler_operator"
    assert activation.affordance == affordance
    assert activation.activation_score > 0
    assert activation.score_terms["capability_match"] == 1.0
    assert activation.source_signal_ids == (signal.signal_id,)


def test_scheduler_falls_back_to_generic_repairer_without_affordance() -> None:
    feedback = FeedbackDigest(
        candidate_id="c1",
        failure_type="unknown_failure",
        severity="blocking",
        summary="unknown",
    )

    activation = StigmergicScheduler().select(
        decision_id="dec-2",
        affordances=(),
        signals=(),
        feedback=feedback,
    )

    assert activation.worker.worker_id == "generic_repairer"
    assert activation.affordance is None


def test_scheduler_scores_all_worker_affordance_pairs() -> None:
    first_affordance = Affordance(
        affordance_id="aff-answer",
        action_type="replace_answer",
        target="answer.txt",
        reason="answer_mismatch",
        priority=0.9,
        expected_worker_kind="exact_edit_guard",
    )
    second_affordance = Affordance(
        affordance_id="aff-compile",
        action_type="set_maven_compiler_release",
        target="pom.xml",
        reason="compile_error",
        priority=0.7,
        expected_worker_kind="maven_compiler_operator",
    )
    feedback = FeedbackDigest(
        candidate_id="c1",
        failure_type="compile_error",
        severity="blocking",
        summary="source option 5 is no longer supported",
    )
    store = SignalStore()
    signal = store.emit(
        kind=SignalKind.SUPPORT,
        target="worker:maven_compiler_operator",
        intensity=0.8,
        now_seq=1,
    )

    activation = StigmergicScheduler().select(
        decision_id="dec-3",
        affordances=(first_affordance, second_affordance),
        signals=(signal,),
        feedback=feedback,
    )

    assert activation.worker.worker_id == "maven_compiler_operator"
    assert activation.affordance == second_affordance
    assert {
        (item["worker_id"], item["affordance_id"])
        for item in activation.competitors
    } >= {
        ("exact_edit_guard", "aff-answer"),
        ("maven_compiler_operator", "aff-compile"),
    }
