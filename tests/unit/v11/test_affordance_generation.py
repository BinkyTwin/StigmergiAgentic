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


def test_official_failure_creates_interpreter_and_test_preservation_affordances() -> (
    None
):
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
    assert by_action["fix_official_test_summary"].expected_worker_kind == (
        "surefire_operator"
    )
    assert by_action["interpret_official_eval"].expected_worker_kind == (
        "official_eval_interpreter"
    )
    assert by_action["preserve_test_count"].expected_worker_kind == (
        "test_preservation_checker"
    )
    assert by_action["guard_existing_tests"].reason == (
        "anti_action:preserve_existing_tests"
    )


def test_compile_affordance_carries_migration_context_metadata() -> None:
    feedback = FeedbackDigest(
        candidate_id="c1",
        failure_type="class_version_error",
        severity="blocking",
        summary="class_version_error release mismatch",
        metadata={
            "migration_context": {
                "source_java": 8,
                "target_java": 21,
                "target_class_major": 65,
                "build_system": "maven",
                "migration_mode": "minimal",
                "dependency_policy": "minimal",
            }
        },
    )

    affordances = affordances_from_feedback(
        feedback=feedback,
        signals=(),
        source_event_ids=("evt-3",),
        now_seq=12,
    )

    by_action = {aff.action_type: aff for aff in affordances}
    affordance = by_action["ensure_maven_compiler_release"]
    assert affordance.metadata["target_java"] == 21
    assert affordance.metadata["build_system"] == "maven"


def test_specific_operator_unavailable_families_create_specific_affordances() -> None:
    feedback = FeedbackDigest(
        candidate_id="c1",
        failure_type="compile_error",
        severity="blocking",
        summary=(
            "IllegalAccessError lombok com.sun.tools.javac jdk.compiler "
            "javafx.application.Application sun.misc.BASE64Encoder"
        ),
        metadata={
            "migration_context": {
                "source_java": 8,
                "target_java": 17,
                "target_class_major": 61,
                "build_system": "maven",
            }
        },
    )

    affordances = affordances_from_feedback(
        feedback=feedback,
        signals=(),
        source_event_ids=("evt-specific",),
        now_seq=2,
    )

    by_action = {aff.action_type: aff for aff in affordances}
    assert "upgrade_lombok_for_target_java" in by_action
    assert by_action["upgrade_lombok_for_target_java"].metadata["target_java"] == 17
    assert "add_javafx_dependencies" in by_action
    assert "replace_sun_misc_base64" in by_action


def test_jdk_internal_api_compile_error_prefers_source_operator() -> None:
    feedback = FeedbackDigest(
        candidate_id="c1",
        failure_type="compile_error",
        severity="blocking",
        summary=(
            "package jdk.jfr.events is not visible "
            "import jdk.jfr.events.ExceptionThrownEvent;"
        ),
    )

    affordances = affordances_from_feedback(
        feedback=feedback,
        signals=(),
        source_event_ids=(),
        now_seq=1,
    )

    by_action = {aff.action_type: aff for aff in affordances}
    assert (
        by_action["replace_jdk_internal_api"].expected_worker_kind
        == "java_source_operator"
    )
    assert (
        by_action["replace_jdk_internal_api"].priority
        > by_action["select_compile_operator"].priority
    )


def test_javafx_affordance_handles_symbol_only_compile_logs() -> None:
    feedback = FeedbackDigest(
        candidate_id="c1",
        failure_type="compile_error",
        severity="blocking",
        summary="cannot find symbol class StageStyle ObservableValue ChangeListener",
    )

    affordances = affordances_from_feedback(
        feedback=feedback,
        signals=(),
        source_event_ids=(),
        now_seq=1,
    )

    by_action = {aff.action_type: aff for aff in affordances}
    assert (
        by_action["add_javafx_dependencies"].priority
        > by_action["select_compile_operator"].priority
    )


def test_bytecode_reader_and_internal_dependency_are_classified_not_generic() -> None:
    bytecode_feedback = FeedbackDigest(
        candidate_id="c1",
        failure_type="class_version_error",
        severity="blocking",
        summary="Unsupported class file major version 61 Spring ASM ClassReader",
    )
    dependency_feedback = FeedbackDigest(
        candidate_id="c2",
        failure_type="dependency_resolution_error",
        severity="blocking",
        summary="Could not resolve internal snapshot spring-boot-hashids",
    )

    bytecode_actions = {
        aff.action_type
        for aff in affordances_from_feedback(
            feedback=bytecode_feedback,
            signals=(),
            source_event_ids=(),
            now_seq=1,
        )
    }
    dependency_actions = {
        aff.action_type
        for aff in affordances_from_feedback(
            feedback=dependency_feedback,
            signals=(),
            source_event_ids=(),
            now_seq=1,
        )
    }

    assert "diagnose_bytecode_reader_incompatibility" in bytecode_actions
    assert "ensure_maven_compiler_release" not in bytecode_actions
    assert "classify_missing_external_dependency" in dependency_actions
    assert "add_missing_dependency" not in dependency_actions
