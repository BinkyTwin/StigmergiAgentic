"""V11 scheduler activation tests."""

from __future__ import annotations

from core_v10.contracts import FeedbackDigest
from core_v10.signals import SignalKind, SignalStore
from core_v10.stigmergy.records import Affordance
from core_v10.stigmergy.scheduler import StigmergicScheduler


def test_scheduler_selects_worker_matching_affordance_kind() -> None:
    affordance = Affordance(
        affordance_id="aff-compile",
        action_type="ensure_maven_compiler_release",
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
        action_type="ensure_maven_compiler_release",
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


def test_scheduler_does_not_inhibit_worker_from_failure_type_signal() -> None:
    diagnostic = Affordance(
        affordance_id="aff-dependency-diagnostic",
        action_type="classify_missing_external_dependency",
        target="dependency_graph",
        reason="dependency_resolution_error",
        priority=0.9,
        expected_worker_kind="dependency_operator",
    )
    generic = Affordance(
        affordance_id="aff-generic-compile",
        action_type="fix_compile_error",
        target="fix_compile_error",
        reason="dependency_resolution_error",
        priority=0.7,
        expected_worker_kind="maven_compiler_operator",
    )
    feedback = FeedbackDigest(
        candidate_id="c1",
        failure_type="dependency_resolution_error",
        severity="blocking",
        summary="Could not resolve internal snapshot artifact",
    )
    store = SignalStore()
    failure_signal = store.emit(
        kind=SignalKind.INHIBIT,
        target="failure_type:dependency_resolution_error",
        intensity=0.8,
        now_seq=1,
    )

    activation = StigmergicScheduler().select(
        decision_id="dec-dependency",
        affordances=(diagnostic, generic),
        signals=(failure_signal,),
        feedback=feedback,
    )

    assert activation.worker.worker_id == "dependency_operator"
    assert activation.affordance == diagnostic
    assert activation.score_terms["inhibition"] == 0.0


def test_scheduler_prioritizes_specific_operator_affordance_over_low_cost_guard() -> None:
    bundle = Affordance(
        affordance_id="aff-bundle",
        action_type="upgrade_bundle_plugin",
        target="pom.xml",
        reason="test_failure",
        priority=0.72,
        expected_worker_kind="maven_compiler_operator",
    )
    guard_tests = Affordance(
        affordance_id="aff-tests",
        action_type="guard_existing_tests",
        target="tests",
        reason="anti_action:preserve_existing_tests",
        priority=0.58,
        expected_worker_kind="test_preservation_checker",
    )
    feedback = FeedbackDigest(
        candidate_id="c1",
        failure_type="test_failure",
        severity="blocking",
        summary="maven-bundle-plugin ConcurrentModificationException",
    )

    activation = StigmergicScheduler().select(
        decision_id="dec-bundle",
        affordances=(bundle, guard_tests),
        signals=(),
        feedback=feedback,
    )

    assert activation.worker.worker_id == "maven_compiler_operator"
    assert activation.affordance == bundle
