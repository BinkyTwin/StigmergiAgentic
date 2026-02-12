"""Unit tests for the Tester agent."""

from __future__ import annotations

from pathlib import Path

from agents.tester import Tester
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


def test_tester_runs_pytest_and_deposits_quality(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    tests_path = repo_path / "tests"
    tests_path.mkdir(parents=True)

    (repo_path / "sample.py").write_text(
        "def add(a, b):\n    return a + b\n", encoding="utf-8"
    )
    (tests_path / "test_sample.py").write_text(
        "from sample import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )

    store = PheromoneStore(_build_config(), base_path=tmp_path)
    store.write(
        "status",
        "sample.py",
        {"status": "transformed", "retry_count": 0, "inhibition": 0.0},
        agent_id="transformer",
    )

    tester = Tester(
        name="tester",
        config=_build_config(),
        pheromone_store=store,
        target_repo_path=repo_path,
    )

    acted = tester.run()

    assert acted is True
    quality = store.read_one("quality", "sample.py")
    status = store.read_one("status", "sample.py")

    assert quality is not None
    assert quality["tests_total"] >= 1
    assert quality["tests_failed"] == 0
    assert quality["confidence"] == 1.0

    assert status is not None
    assert status["status"] == "tested"


def test_tester_fallback_compile_import_sets_neutral_confidence(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)

    (repo_path / "fallback_module.py").write_text(
        "def ping():\n    return 'pong'\n",
        encoding="utf-8",
    )

    store = PheromoneStore(_build_config(), base_path=tmp_path)
    store.write(
        "status",
        "fallback_module.py",
        {"status": "transformed", "retry_count": 0, "inhibition": 0.0},
        agent_id="transformer",
    )

    tester = Tester(
        name="tester",
        config=_build_config(),
        pheromone_store=store,
        target_repo_path=repo_path,
    )

    tester.run()

    quality = store.read_one("quality", "fallback_module.py")
    assert quality is not None
    assert quality["tests_total"] == 0
    assert quality["confidence"] == 0.5
