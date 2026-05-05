from __future__ import annotations

import pytest

from core_v10.event_log import JsonlEventLog
from core_v10.replay import replay_jsonl


def test_replay_jsonl_filters_by_run_id(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    event_log = JsonlEventLog(path)
    event_log.append(
        run_id="run-a",
        instance_id="inst-001",
        event_type="run.started",
        actor="runner",
        payload={},
    )
    event_log.append(
        run_id="run-b",
        instance_id="inst-002",
        event_type="run.started",
        actor="runner",
        payload={},
    )

    snapshot = replay_jsonl(path, run_id="run-b")

    assert snapshot.run_id == "run-b"
    assert snapshot.event_count == 1
    assert snapshot.counts_by_type == {"run.started": 1}


def test_replay_jsonl_rejects_corrupt_events(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text('{"event_id": "evt_1"}\nnot json\n', encoding="utf-8")

    with pytest.raises(ValueError, match="invalid JSONL event"):
        replay_jsonl(path)
