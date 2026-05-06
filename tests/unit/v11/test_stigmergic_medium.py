"""V11 medium replay lifecycle tests."""

from __future__ import annotations

from dataclasses import replace

from core_v10.event_log import JsonlEventLog
from core_v10.signal_policy import SIGNAL_EMITTED_EVENT
from core_v10.signals import SignalKind, SignalStore
from core_v10.stigmergy.events import (
    AFFORDANCE_CONSUMED_EVENT,
    AFFORDANCE_CREATED_EVENT,
    AFFORDANCE_EXPIRED_EVENT,
    AFFORDANCE_INHIBITED_EVENT,
    SIGNAL_DECAYED_EVENT,
    SIGNAL_RETIRED_EVENT,
)
from core_v10.stigmergy.medium import StigmergicMediumKernel
from core_v10.stigmergy.records import Affordance


def _affordance(affordance_id: str, priority: float) -> Affordance:
    return Affordance(
        affordance_id=affordance_id,
        action_type="replace_answer",
        target="answer.txt",
        reason="answer_mismatch",
        priority=priority,
        expected_worker_kind="exact_edit_guard",
    )


def test_medium_from_events_replays_affordance_lifecycle_and_signal_state(tmp_path) -> None:
    log = JsonlEventLog(tmp_path / "events.jsonl")
    store = SignalStore()
    signal = store.emit(
        kind=SignalKind.SUPPORT,
        target="worker:exact_edit_guard",
        intensity=0.8,
        now_seq=1,
    )
    decayed = replace(signal, intensity=0.4, last_seen_seq=5)
    aff_consumed = _affordance("aff-consumed", 0.9)
    aff_expired = _affordance("aff-expired", 0.8)
    aff_inhibited = _affordance("aff-inhibited", 0.7)
    aff_active = _affordance("aff-active", 0.6)

    log.append(
        run_id="r1",
        instance_id="i1",
        event_type=SIGNAL_EMITTED_EVENT,
        actor="medium",
        payload={"record": signal.to_dict()},
    )
    for affordance in (aff_consumed, aff_expired, aff_inhibited, aff_active):
        log.append(
            run_id="r1",
            instance_id="i1",
            event_type=AFFORDANCE_CREATED_EVENT,
            actor="medium",
            payload={"affordance": affordance.to_dict()},
        )
    log.append(
        run_id="r1",
        instance_id="i1",
        event_type=AFFORDANCE_CONSUMED_EVENT,
        actor="worker",
        payload={"affordance_id": aff_consumed.affordance_id},
    )
    log.append(
        run_id="r1",
        instance_id="i1",
        event_type=AFFORDANCE_EXPIRED_EVENT,
        actor="medium",
        payload={"affordance_id": aff_expired.affordance_id},
    )
    log.append(
        run_id="r1",
        instance_id="i1",
        event_type=AFFORDANCE_INHIBITED_EVENT,
        actor="medium",
        payload={"affordance_id": aff_inhibited.affordance_id},
    )
    log.append(
        run_id="r1",
        instance_id="i1",
        event_type=SIGNAL_DECAYED_EVENT,
        actor="medium",
        payload={"record": decayed.to_dict()},
    )
    log.append(
        run_id="r1",
        instance_id="i1",
        event_type=SIGNAL_RETIRED_EVENT,
        actor="medium",
        payload={"signal_id": signal.signal_id},
    )

    rebuilt = StigmergicMediumKernel.from_events(log.read_all())
    snapshot = rebuilt.snapshot()

    assert [item["affordance_id"] for item in snapshot["affordances"]] == [
        "aff-active"
    ]
    assert snapshot["consumed_affordance_ids"] == ["aff-consumed"]
    assert snapshot["expired_affordance_ids"] == ["aff-expired"]
    assert snapshot["inhibited_affordance_ids"] == ["aff-inhibited"]
    assert snapshot["retired_signal_ids"] == [signal.signal_id]
    assert snapshot["signals"]["records"][0]["intensity"] == 0.4
