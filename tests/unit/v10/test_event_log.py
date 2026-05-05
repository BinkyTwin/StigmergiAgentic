from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from core_v10.event_log import JsonlEventLog


def test_event_log_appends_reads_and_replays_events(tmp_path) -> None:
    event_log = JsonlEventLog(tmp_path / "events.jsonl")

    first = event_log.append(
        run_id="run-001",
        instance_id="inst-001",
        event_type="observation.created",
        actor="adapter",
        payload={"summary": "observed"},
        timestamp="2026-05-03T00:00:00+00:00",
    )
    second = event_log.append(
        run_id="run-001",
        instance_id="inst-001",
        event_type="validation.completed",
        actor="verifier",
        hypothesis_id="hyp-001",
        payload={"status": "passed"},
        timestamp="2026-05-03T00:00:01+00:00",
    )

    events = event_log.read_all()
    snapshot = event_log.replay("run-001")

    assert [event.sequence for event in events] == [1, 2]
    assert first.event_id.startswith("evt_000001_")
    assert second.event_id.startswith("evt_000002_")
    assert snapshot.run_id == "run-001"
    assert snapshot.event_count == 2
    assert snapshot.counts_by_type == {
        "observation.created": 1,
        "validation.completed": 1,
    }
    assert snapshot.latest_by_hypothesis["hyp-001"]["payload"] == {
        "status": "passed"
    }


def test_event_log_continues_sequence_when_reopened(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    JsonlEventLog(path).append(
        run_id="run-001",
        instance_id="inst-001",
        event_type="run.started",
        actor="runner",
        payload={},
    )

    event = JsonlEventLog(path).append(
        run_id="run-001",
        instance_id="inst-001",
        event_type="run.completed",
        actor="runner",
        payload={},
    )

    assert event.sequence == 2


def test_event_log_exports_replay_bundle(tmp_path) -> None:
    event_log = JsonlEventLog(tmp_path / "events.jsonl")
    event_log.append(
        run_id="run-001",
        instance_id="inst-001",
        event_type="run.started",
        actor="runner",
        payload={"strategy": "agentless_basic"},
    )

    bundle = event_log.export_bundle(tmp_path / "bundle")
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))

    assert (bundle / "events.jsonl").exists()
    assert manifest["format"] == "stigmergiagentic.v10.event_log_bundle"
    assert manifest["event_count"] == 1


def test_event_log_serializes_concurrent_appends(tmp_path) -> None:
    path = tmp_path / "events.jsonl"

    def append_event(index: int) -> int:
        event = JsonlEventLog(path).append(
            run_id="run-001",
            instance_id="inst-001",
            event_type="concurrent.event",
            actor="worker",
            payload={"index": index},
        )
        return event.sequence

    with ThreadPoolExecutor(max_workers=8) as executor:
        sequences = list(executor.map(append_event, range(20)))

    events = JsonlEventLog(path).read_all()

    assert sorted(sequences) == list(range(1, 21))
    assert [event.sequence for event in events] == list(range(1, 21))
