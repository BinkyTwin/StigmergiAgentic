"""Unit tests for SQLite marker store."""

from __future__ import annotations

from multiprocessing import Process, Queue
from pathlib import Path

import pytest

from core.marker import Marker
from core.marker_store import MarkerStore
from core.guardrails import ScopeLockError, TraceabilityError


def _make_marker(marker_id: str = "m-1", **overrides: object) -> Marker:
    payload = {
        "id": marker_id,
        "marker_type": "task",
        "target": "file.py",
        "intensity": 1.0,
        "state": "pending",
        "payload": {"score": 1},
        "created_by": "agent-1",
        "created_at": "2026-02-26T12:00:00+00:00",
        "updated_by": "agent-1",
        "updated_at": "2026-02-26T12:00:00+00:00",
        "lock_owner": None,
        "lock_tick": None,
        "inhibition": 0.5,
        "retry_count": 0,
        "history": ["created"],
    }
    payload.update(overrides)
    return Marker(**payload)


def _read_worker(db_path: str, queue: Queue) -> None:
    store = MarkerStore(db_path=db_path)
    snapshot = store.snapshot()
    queue.put(len(snapshot.get("task", [])))


def test_upsert_and_get_marker(marker_store: MarkerStore) -> None:
    marker = _make_marker()
    marker_store.upsert_marker(marker, agent_id="agent-1")

    loaded = marker_store.get_marker("m-1")
    assert loaded is not None
    assert loaded.target == "file.py"


def test_upsert_updates_existing_marker(marker_store: MarkerStore) -> None:
    marker_store.upsert_marker(_make_marker(), agent_id="agent-1")
    marker_store.upsert_marker(
        _make_marker(marker_id="m-1", intensity=0.7, state="active"),
        agent_id="agent-2",
    )

    loaded = marker_store.get_marker("m-1")
    assert loaded is not None
    assert loaded.intensity == pytest.approx(0.7)
    assert loaded.updated_by == "agent-2"


def test_get_by_type_target(marker_store: MarkerStore) -> None:
    marker_store.upsert_marker(_make_marker(marker_id="a", target="x.py"), "agent-1")
    marker_store.upsert_marker(_make_marker(marker_id="b", target="y.py"), "agent-1")

    loaded = marker_store.get_by_type_target(marker_type="task", target="y.py")
    assert loaded is not None
    assert loaded.id == "b"


def test_query_filters(marker_store: MarkerStore) -> None:
    marker_store.upsert_marker(_make_marker(marker_id="a", intensity=0.9), "agent-1")
    marker_store.upsert_marker(_make_marker(marker_id="b", intensity=0.2), "agent-1")

    high = marker_store.query_markers(intensity__gt=0.5)
    assert [marker.id for marker in high] == ["a"]

    selected = marker_store.query_markers(id__in=["a", "x"])
    assert [marker.id for marker in selected] == ["a"]


def test_acquire_lock_success_and_conflict(marker_store: MarkerStore) -> None:
    marker_store.upsert_marker(_make_marker(), "agent-1")

    acquired = marker_store.acquire_lock("m-1", agent_id="agent-1", tick=3)
    assert acquired is True

    acquired_other = marker_store.acquire_lock("m-1", agent_id="agent-2", tick=4)
    assert acquired_other is False


def test_release_lock_owner_only(marker_store: MarkerStore) -> None:
    marker_store.upsert_marker(_make_marker(), "agent-1")
    marker_store.acquire_lock("m-1", agent_id="agent-1", tick=1)

    assert marker_store.release_lock("m-1", agent_id="agent-2") is False
    assert marker_store.release_lock("m-1", agent_id="agent-1") is True


def test_upsert_rejects_locked_marker_from_other_agent(marker_store: MarkerStore) -> None:
    marker_store.upsert_marker(_make_marker(state="active"), "agent-1")
    marker_store.acquire_lock("m-1", agent_id="agent-1", tick=2)

    with pytest.raises(ScopeLockError):
        marker_store.upsert_marker(_make_marker(marker_id="m-1", state="completed"), "agent-2")


def test_apply_decay_updates_non_terminal_markers(
    marker_store: MarkerStore,
    config_dict: dict,
) -> None:
    marker_store.upsert_marker(_make_marker(marker_id="a", intensity=1.0), "agent-1")
    marker_store.upsert_marker(
        _make_marker(marker_id="b", state="terminal", intensity=1.0),
        "agent-1",
    )

    changed = marker_store.apply_decay(current_tick=5, config=config_dict)
    updated_a = marker_store.get_marker("a")
    updated_b = marker_store.get_marker("b")

    assert changed == 1
    assert updated_a is not None and updated_a.intensity < 1.0
    assert updated_b is not None and updated_b.intensity == pytest.approx(1.0)


def test_maintain_locks_releases_expired_and_requeues(marker_store: MarkerStore) -> None:
    marker_store.upsert_marker(
        _make_marker(state="active", lock_owner="agent-1", lock_tick=1),
        "agent-1",
    )

    released = marker_store.maintain_locks(current_tick=5, ttl=3)
    updated = marker_store.get_marker("m-1")

    assert released == ["m-1"]
    assert updated is not None
    assert updated.lock_owner is None
    assert updated.state == "pending"
    assert updated.retry_count == 1


def test_retry_overflow_sets_marker_to_skipped(marker_store: MarkerStore) -> None:
    marker_store.upsert_marker(
        _make_marker(marker_id="retry", retry_count=4, state="retry"),
        "agent-1",
    )

    loaded = marker_store.get_marker("retry")
    assert loaded is not None
    assert loaded.state == "skipped"


def test_traceability_required_on_mutation(marker_store: MarkerStore) -> None:
    with pytest.raises(TraceabilityError):
        marker_store.upsert_marker(_make_marker(marker_id="trace"), agent_id="")


def test_snapshot_and_multiprocess_read_smoke(db_path: Path) -> None:
    store = MarkerStore(db_path=db_path)
    store.upsert_marker(_make_marker(marker_id="m-1"), "agent-1")
    store.upsert_marker(_make_marker(marker_id="m-2"), "agent-1")

    snapshot = store.snapshot()
    snapshot["task"].append(_make_marker(marker_id="fake"))

    refreshed = store.snapshot()
    assert len(refreshed["task"]) == 2

    queue: Queue = Queue()
    workers = [Process(target=_read_worker, args=(str(db_path), queue)) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)
        assert worker.exitcode == 0

    counts = [queue.get(timeout=2) for _ in workers]
    assert counts == [2, 2]
