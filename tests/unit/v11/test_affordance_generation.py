"""V11 affordance policy tests."""

from __future__ import annotations

from core_v10.contracts import FeedbackDigest
from core_v10.signals import SignalKind, SignalStore
from core_v10.stigmergy.affordances import affordances_from_feedback


def test_replacement_count_too_low_generates_exact_edit_affordances() -> None:
    store = SignalStore()
    record = store.emit(
        kind=SignalKind.INHIBIT,
        target="failure_type:replacement_count_too_low",
        intensity=0.8,
        now_seq=1,
    )
    feedback = FeedbackDigest(
        candidate_id="c1",
        failure_type="replacement_count_too_low",
        severity="blocking",
        summary="replacement_count_too_low:pom.xml:expected>=1:actual=0",
        locations=[{"path": "pom.xml"}],
    )

    affordances = affordances_from_feedback(
        feedback=feedback,
        signals=(record,),
        source_event_ids=("evt-1",),
        now_seq=4,
    )

    action_types = {aff.action_type for aff in affordances}
    assert "inspect_current_file" in action_types
    assert "derive_exact_old_span" in action_types
    assert {aff.expected_worker_kind for aff in affordances} == {"exact_edit_guard"}
    assert all(record.signal_id in aff.source_signal_ids for aff in affordances)


def test_official_failure_creates_interpreter_and_test_preservation_affordances() -> None:
    feedback = FeedbackDigest(
        candidate_id="c1",
        failure_type="official_eval_failed",
        severity="blocking",
        summary="#tests=-2 official evaluator rejected patch",
        anti_actions=["preserve_existing_tests"],
    )

    affordances = affordances_from_feedback(
        feedback=feedback,
        signals=(),
        source_event_ids=("evt-2",),
        now_seq=10,
    )

    by_action = {aff.action_type: aff for aff in affordances}
    assert by_action["interpret_official_eval"].expected_worker_kind == (
        "official_eval_interpreter"
    )
    assert by_action["preserve_test_count"].expected_worker_kind == (
        "test_preservation_checker"
    )
    assert by_action["guard_existing_tests"].reason == (
        "anti_action:preserve_existing_tests"
    )
