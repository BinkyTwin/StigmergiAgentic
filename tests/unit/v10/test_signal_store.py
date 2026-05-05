"""Unit tests for the active SignalStore introduced in Phase 6."""

from __future__ import annotations

import json

from core_v10.event_log import JsonlEventLog
from core_v10.signal_policy import SIGNAL_EMITTED_EVENT, store_from_events
from core_v10.signals import (
    DEFAULT_HALF_LIFE,
    SignalKind,
    SignalRecord,
    SignalStore,
    clamp_intensity,
    signal_id_for,
)


def test_signal_id_is_deterministic_for_kind_and_target() -> None:
    sid_a = signal_id_for(SignalKind.INHIBIT, "failure_type:compile_error")
    sid_b = signal_id_for(SignalKind.INHIBIT, "failure_type:compile_error")
    sid_c = signal_id_for(SignalKind.SUPPORT, "failure_type:compile_error")
    assert sid_a == sid_b
    assert sid_a != sid_c
    assert len(sid_a) == 16


def test_emit_inserts_record_and_clamps_intensity() -> None:
    store = SignalStore()
    record = store.emit(
        kind=SignalKind.INHIBIT,
        target="failure_type:dependency_resolution_error",
        intensity=1.5,  # above max → must clamp to 1.0
        now_seq=10,
        evidence=("c-1",),
    )
    assert record.intensity == 1.0
    assert record.evidence == ("c-1",)
    assert record.created_at_seq == 10
    assert record.last_seen_seq == 10
    assert record.emit_count == 1
    assert len(store) == 1


def test_emit_upserts_and_keeps_max_intensity() -> None:
    store = SignalStore()
    store.emit(
        kind=SignalKind.INHIBIT,
        target="failure_type:test_failure",
        intensity=0.5,
        now_seq=5,
        evidence=("c-1",),
    )
    record = store.emit(
        kind=SignalKind.INHIBIT,
        target="failure_type:test_failure",
        intensity=0.4,  # weaker — store must keep the strongest
        now_seq=6,
        evidence=("c-2",),
    )
    assert record.intensity >= 0.4
    assert record.evidence == ("c-1", "c-2")
    assert record.emit_count == 2


def test_reinforce_adds_delta_after_decay() -> None:
    store = SignalStore()
    store.emit(
        kind=SignalKind.SUPPORT,
        target="origin:llm_t0.0",
        intensity=0.6,
        now_seq=0,
        evidence=("c-1",),
        half_life=8,
    )
    record = store.reinforce(
        target="origin:llm_t0.0",
        kind=SignalKind.SUPPORT,
        delta=0.1,
        now_seq=0,
        evidence=("c-2",),
    )
    assert record.intensity > 0.6  # base 0.6 + delta 0.1, clamped


def test_decay_halves_intensity_after_one_half_life() -> None:
    store = SignalStore()
    store.emit(
        kind=SignalKind.INHIBIT,
        target="failure_type:compile_error",
        intensity=0.8,
        now_seq=0,
        half_life=4,
    )
    store.decay(now_seq=4)  # exactly one half-life later
    record = store.get(SignalKind.INHIBIT, "failure_type:compile_error")
    assert record is not None
    assert abs(record.intensity - 0.4) < 1e-6


def test_decay_is_idempotent_at_same_seq() -> None:
    store = SignalStore()
    store.emit(
        kind=SignalKind.INHIBIT,
        target="failure_type:compile_error",
        intensity=0.8,
        now_seq=0,
        half_life=4,
    )
    store.decay(now_seq=4)
    intensity_first = store.get(SignalKind.INHIBIT, "failure_type:compile_error").intensity
    store.decay(now_seq=4)
    intensity_second = store.get(SignalKind.INHIBIT, "failure_type:compile_error").intensity
    assert intensity_first == intensity_second


def test_support_for_returns_zero_when_missing() -> None:
    store = SignalStore()
    assert store.support_for("origin:nope") == 0.0


def test_by_kind_returns_only_matching_records() -> None:
    store = SignalStore()
    store.emit(
        kind=SignalKind.SUPPORT,
        target="origin:a",
        intensity=0.5,
        now_seq=0,
    )
    store.emit(
        kind=SignalKind.INHIBIT,
        target="failure_type:x",
        intensity=0.5,
        now_seq=0,
    )
    supports = store.by_kind(SignalKind.SUPPORT)
    inhibits = store.by_kind(SignalKind.INHIBIT)
    assert {r.target for r in supports} == {"origin:a"}
    assert {r.target for r in inhibits} == {"failure_type:x"}


def test_to_dict_roundtrip_via_signal_record_from_dict() -> None:
    store = SignalStore()
    store.emit(
        kind=SignalKind.INHIBIT,
        target="failure_type:compile_error",
        intensity=0.6,
        now_seq=2,
        evidence=("c-1",),
    )
    snapshot = store.to_dict()
    rebuilt = SignalRecord.from_dict(snapshot["records"][0])
    assert rebuilt.kind == SignalKind.INHIBIT
    assert rebuilt.target == "failure_type:compile_error"
    assert rebuilt.intensity == 0.6
    assert rebuilt.evidence == ("c-1",)


def test_from_events_replays_signal_emitted_events_into_store(tmp_path) -> None:
    log = JsonlEventLog(tmp_path / "events.jsonl")
    # Emit two signals via the event log directly so we test the replay path.
    record_a = SignalRecord(
        kind=SignalKind.INHIBIT,
        target="failure_type:compile_error",
        intensity=0.5,
        evidence=("c-1",),
        half_life=DEFAULT_HALF_LIFE,
        created_at_seq=1,
        last_seen_seq=1,
        emit_count=1,
    )
    record_b = SignalRecord(
        kind=SignalKind.SUPPORT,
        target="origin:llm_t0.0",
        intensity=0.7,
        evidence=("c-2",),
        half_life=DEFAULT_HALF_LIFE,
        created_at_seq=2,
        last_seen_seq=2,
        emit_count=1,
    )
    log.append(
        run_id="r-1",
        instance_id="i-1",
        event_type=SIGNAL_EMITTED_EVENT,
        actor="signal_policy",
        payload={"record": record_a.to_dict(), "op": "emit"},
    )
    log.append(
        run_id="r-1",
        instance_id="i-1",
        event_type=SIGNAL_EMITTED_EVENT,
        actor="signal_policy",
        payload={"record": record_b.to_dict(), "op": "emit"},
    )
    store = store_from_events(log.read_all())
    assert len(store) == 2
    inhibit = store.get(SignalKind.INHIBIT, "failure_type:compile_error")
    support = store.get(SignalKind.SUPPORT, "origin:llm_t0.0")
    assert inhibit is not None and abs(inhibit.intensity - 0.5) < 1e-6
    assert support is not None and abs(support.intensity - 0.7) < 1e-6


def test_clamp_intensity_bounds() -> None:
    assert clamp_intensity(-1.0) == 0.0
    assert clamp_intensity(0.0) == 0.0
    assert clamp_intensity(0.42) == 0.42
    assert clamp_intensity(1.5) == 1.0
