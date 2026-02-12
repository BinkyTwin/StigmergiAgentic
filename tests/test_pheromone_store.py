"""Unit and targeted integration tests for the pheromone store."""

from __future__ import annotations

import json
import math
from multiprocessing import Process
from pathlib import Path

import pytest

from environment.pheromone_store import PheromoneStore


def _build_config() -> dict:
    return {
        "pheromones": {
            "decay_type": "exponential",
            "decay_rate": 0.05,
            "inhibition_decay_rate": 0.08,
        },
        "thresholds": {
            "max_retry_count": 3,
            "scope_lock_ttl": 3,
        },
        "llm": {
            "max_tokens_total": 100000,
        },
    }


def _worker_write(base_path: str, worker_id: int, writes: int) -> None:
    store = PheromoneStore(_build_config(), base_path=Path(base_path))
    for offset in range(writes):
        file_key = f"worker_{worker_id}_{offset}.py"
        store.write(
            pheromone_type="tasks",
            file_key=file_key,
            data={"intensity": 0.9, "pattern_count": 2},
            agent_id=f"worker_{worker_id}",
        )


@pytest.fixture
def store(tmp_path: Path) -> PheromoneStore:
    return PheromoneStore(_build_config(), base_path=tmp_path)


def test_pheromone_read_write(store: PheromoneStore) -> None:
    store.write(
        pheromone_type="tasks",
        file_key="utils.py",
        data={"intensity": 0.9, "pattern_count": 3},
        agent_id="scout",
    )

    entry = store.read_one("tasks", "utils.py")
    assert entry is not None
    assert entry["intensity"] == 0.9
    assert entry["created_by"] == "scout"
    assert "timestamp" in entry

    store.update(
        pheromone_type="tasks",
        file_key="utils.py",
        agent_id="scout",
        pattern_count=5,
    )
    updated = store.read_one("tasks", "utils.py")
    assert updated is not None
    assert updated["pattern_count"] == 5
    assert updated["updated_by"] == "scout"


def test_query_filters(store: PheromoneStore) -> None:
    store.write("tasks", "a.py", {"intensity": 0.8}, agent_id="scout")
    store.write("tasks", "b.py", {"intensity": 0.2}, agent_id="scout")
    store.write(
        "status",
        "a.py",
        {"status": "pending", "retry_count": 0, "inhibition": 0.0},
        agent_id="scout",
    )
    store.write(
        "status",
        "b.py",
        {"status": "transformed", "retry_count": 0, "inhibition": 0.0},
        agent_id="transformer",
    )

    high_intensity = store.query("tasks", intensity__gt=0.5)
    pending = store.query("status", status="pending")

    assert list(high_intensity.keys()) == ["a.py"]
    assert list(pending.keys()) == ["a.py"]


def test_pheromone_locking_with_concurrent_writes(tmp_path: Path) -> None:
    workers = 4
    writes_per_worker = 12
    processes: list[Process] = []

    for worker_id in range(workers):
        process = Process(
            target=_worker_write,
            args=(str(tmp_path), worker_id, writes_per_worker),
        )
        process.start()
        processes.append(process)

    for process in processes:
        process.join(timeout=20)
        assert process.exitcode == 0

    tasks_path = tmp_path / "pheromones" / "tasks.json"
    loaded = json.loads(tasks_path.read_text(encoding="utf-8"))
    assert len(loaded) == workers * writes_per_worker


def test_apply_decay_for_pending_and_retry_only(store: PheromoneStore) -> None:
    store.write("tasks", "pending.py", {"intensity": 1.0}, agent_id="scout")
    store.write("tasks", "retry.py", {"intensity": 1.0}, agent_id="scout")
    store.write("tasks", "stable.py", {"intensity": 1.0}, agent_id="scout")

    store.write(
        "status",
        "pending.py",
        {"status": "pending", "retry_count": 0, "inhibition": 0.0},
        agent_id="scout",
    )
    store.write(
        "status",
        "retry.py",
        {"status": "retry", "retry_count": 1, "inhibition": 0.5},
        agent_id="validator",
    )
    store.write(
        "status",
        "stable.py",
        {"status": "transformed", "retry_count": 0, "inhibition": 0.0},
        agent_id="transformer",
    )

    store.apply_decay("tasks")

    pending = store.read_one("tasks", "pending.py")
    retry = store.read_one("tasks", "retry.py")
    stable = store.read_one("tasks", "stable.py")

    assert pending is not None and retry is not None and stable is not None
    assert pending["intensity"] == pytest.approx(math.exp(-0.05))
    assert retry["intensity"] == pytest.approx(math.exp(-0.05))
    assert stable["intensity"] == pytest.approx(1.0)


def test_apply_decay_inhibition(store: PheromoneStore) -> None:
    store.write(
        "status",
        "retrying.py",
        {"status": "retry", "retry_count": 1, "inhibition": 0.5},
        agent_id="validator",
    )
    store.write(
        "status",
        "clean.py",
        {"status": "pending", "retry_count": 0, "inhibition": 0.0},
        agent_id="scout",
    )

    store.apply_decay_inhibition()

    retrying = store.read_one("status", "retrying.py")
    clean = store.read_one("status", "clean.py")

    assert retrying is not None and clean is not None
    assert retrying["inhibition"] == pytest.approx(0.5 * math.exp(-0.08))
    assert clean["inhibition"] == pytest.approx(0.0)


def test_audit_log_append_only(store: PheromoneStore) -> None:
    store.write("tasks", "audit.py", {"intensity": 0.4}, agent_id="scout")
    store.update("tasks", "audit.py", agent_id="scout", intensity=0.6)

    audit_path = store.pheromone_dir / "audit_log.jsonl"
    lines = [
        line for line in audit_path.read_text(encoding="utf-8").splitlines() if line
    ]
    events = [json.loads(line) for line in lines]

    assert len(events) == 2
    assert events[0]["action"] == "write"
    assert events[1]["action"] == "update"
    assert events[1]["fields_changed"]["intensity"] == 0.6
