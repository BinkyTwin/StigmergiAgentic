"""Unit tests for the Phase 6 feedback→signal policy."""

from __future__ import annotations

from core_v10.contracts import (
    Candidate,
    CandidateKind,
    FeedbackDigest,
    ValidationResult,
    ValidationStatus,
)
from core_v10.signal_policy import (
    INHIBIT_ANTI_ACTION_BASE,
    INHIBIT_FAILURE_TYPE_BASE,
    INHIBIT_FAILURE_TYPE_BLOCKING,
    INHIBIT_SIGNATURE_BASE,
    SUPPORT_ORIGIN_BASE,
    digest,
    emit_novelty,
    inhibit_signature,
    reinforce_origin,
    update_from_feedback,
)
from core_v10.signals import SignalKind, SignalStore


def _candidate(cid: str = "c-1", origin: str = "llm_t0.0") -> Candidate:
    return Candidate(
        candidate_id=cid,
        kind=CandidateKind.PATCH,
        payload={"answer": "x"},
        origin=origin,
    )


def _feedback(
    *,
    failure_type: str = "compile_error",
    severity: str = "warning",
    anti_actions: tuple[str, ...] = (),
    candidate_id: str = "c-1",
) -> FeedbackDigest:
    return FeedbackDigest(
        candidate_id=candidate_id,
        failure_type=failure_type,
        severity=severity,
        summary="…",
        anti_actions=list(anti_actions),
    )


def test_update_from_feedback_emits_failure_type_inhibit() -> None:
    store = SignalStore()
    feedback = _feedback(failure_type="compile_error", severity="warning")
    effects = update_from_feedback(
        store, feedback=feedback, candidate=_candidate(), now_seq=1
    )
    assert len(effects) == 1
    record = store.get(SignalKind.INHIBIT, "failure_type:compile_error")
    assert record is not None
    assert abs(record.intensity - INHIBIT_FAILURE_TYPE_BASE) < 1e-6
    assert effects[0].op == "emit"


def test_update_from_feedback_blocking_severity_uses_higher_intensity() -> None:
    store = SignalStore()
    feedback = _feedback(failure_type="dependency_resolution_error", severity="blocking")
    update_from_feedback(
        store, feedback=feedback, candidate=_candidate(), now_seq=1
    )
    record = store.get(SignalKind.INHIBIT, "failure_type:dependency_resolution_error")
    assert record is not None
    assert abs(record.intensity - INHIBIT_FAILURE_TYPE_BLOCKING) < 1e-6


def test_repeat_feedback_reinforces_existing_inhibit() -> None:
    store = SignalStore()
    fb = _feedback(failure_type="test_failure", severity="warning")
    update_from_feedback(store, feedback=fb, candidate=_candidate("c-1"), now_seq=1)
    update_from_feedback(store, feedback=fb, candidate=_candidate("c-2"), now_seq=2)
    record = store.get(SignalKind.INHIBIT, "failure_type:test_failure")
    assert record is not None
    assert record.emit_count == 2
    assert record.intensity > INHIBIT_FAILURE_TYPE_BASE  # reinforced


def test_anti_action_preserve_existing_tests_emits_inhibit_signal() -> None:
    store = SignalStore()
    feedback = _feedback(
        failure_type="test_failure",
        severity="warning",
        anti_actions=("preserve_existing_tests",),
    )
    effects = update_from_feedback(
        store, feedback=feedback, candidate=_candidate(), now_seq=1
    )
    assert any(e.target == "anti:preserve_existing_tests" for e in effects)
    record = store.get(SignalKind.INHIBIT, "anti:preserve_existing_tests")
    assert record is not None
    assert abs(record.intensity - INHIBIT_ANTI_ACTION_BASE) < 1e-6


def test_unknown_anti_actions_are_ignored() -> None:
    store = SignalStore()
    feedback = _feedback(anti_actions=("delete_pom",))  # not in tracked set
    effects = update_from_feedback(
        store, feedback=feedback, candidate=_candidate(), now_seq=1
    )
    # Only the failure_type INHIBIT should be emitted.
    assert all(not e.target.startswith("anti:") for e in effects)


def test_empty_failure_type_emits_no_effect() -> None:
    store = SignalStore()
    feedback = _feedback(failure_type="")
    effects = update_from_feedback(
        store, feedback=feedback, candidate=_candidate(), now_seq=1
    )
    assert effects == ()
    assert len(store) == 0


def test_reinforce_origin_emits_support_and_reinforce_when_validation_passed() -> None:
    store = SignalStore()
    candidate = _candidate(origin="llm_initial_t0.0")
    validation = ValidationResult(
        candidate_id=candidate.candidate_id,
        status=ValidationStatus.PASSED,
        validator_name="verifier",
    )
    effects = reinforce_origin(
        store, candidate=candidate, validation=validation, now_seq=3
    )
    targets = {(e.kind, e.target) for e in effects}
    assert (SignalKind.SUPPORT, "origin:llm_initial_t0.0") in targets
    assert (SignalKind.REINFORCE, "kind:patch") in targets
    record = store.get(SignalKind.SUPPORT, "origin:llm_initial_t0.0")
    assert record is not None
    assert abs(record.intensity - SUPPORT_ORIGIN_BASE) < 1e-6


def test_reinforce_origin_no_op_when_validation_failed() -> None:
    store = SignalStore()
    candidate = _candidate()
    validation = ValidationResult(
        candidate_id=candidate.candidate_id,
        status=ValidationStatus.FAILED,
        validator_name="verifier",
    )
    effects = reinforce_origin(
        store, candidate=candidate, validation=validation, now_seq=3
    )
    assert effects == ()
    assert len(store) == 0


def test_inhibit_signature_emits_strong_inhibit_on_failed_signature() -> None:
    store = SignalStore()
    effect = inhibit_signature(
        store,
        signature="abc123",
        evidence_id="h-1",
        now_seq=4,
    )
    assert effect.kind == SignalKind.INHIBIT
    assert effect.target == "signature:abc123"
    record = store.get(SignalKind.INHIBIT, "signature:abc123")
    assert record is not None
    assert abs(record.intensity - INHIBIT_SIGNATURE_BASE) < 1e-6


def test_emit_novelty_returns_none_when_only_one_hypothesis() -> None:
    store = SignalStore()
    assert emit_novelty(store, hypothesis_count=1, now_seq=1) is None
    assert len(store) == 0


def test_emit_novelty_clamps_intensity_for_large_hypothesis_count() -> None:
    store = SignalStore()
    effect = emit_novelty(store, hypothesis_count=100, now_seq=1)
    assert effect is not None
    assert effect.intensity <= 1.0
    record = store.get(SignalKind.NOVELTY, "hypothesis_space")
    assert record is not None
    assert record.intensity == 1.0


def test_digest_returns_top_k_per_kind_in_intensity_order() -> None:
    store = SignalStore()
    store.emit(
        kind=SignalKind.INHIBIT,
        target="failure_type:a",
        intensity=0.4,
        now_seq=0,
    )
    store.emit(
        kind=SignalKind.INHIBIT,
        target="failure_type:b",
        intensity=0.7,
        now_seq=0,
    )
    store.emit(
        kind=SignalKind.SUPPORT,
        target="origin:x",
        intensity=0.6,
        now_seq=0,
    )
    d = digest(store, top_k=1)
    assert len(d.top_inhibitions) == 1
    assert d.top_inhibitions[0].target == "failure_type:b"
    assert d.top_supports[0].target == "origin:x"
    assert d.top_novelties == ()


def test_digest_empty_store_returns_empty_digest() -> None:
    store = SignalStore()
    d = digest(store, top_k=3)
    assert d.is_empty
    assert d.to_dict() == {
        "top_inhibitions": [],
        "top_supports": [],
        "top_novelties": [],
    }
