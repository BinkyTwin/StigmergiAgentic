"""Unit tests for the Scout agent."""

from __future__ import annotations

from pathlib import Path

from agents.scout import Scout
from environment.pheromone_store import PheromoneStore


def _build_config() -> dict:
    return {
        "pheromones": {
            "task_intensity_clamp": [0.1, 1.0],
            "decay_type": "exponential",
            "decay_rate": 0.05,
            "inhibition_decay_rate": 0.08,
        },
        "thresholds": {
            "max_retry_count": 3,
            "scope_lock_ttl": 3,
            "transformer_intensity_min": 0.2,
        },
        "llm": {
            "max_tokens_total": 100000,
        },
    }


def test_scout_deposits_tasks_and_pending_status(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)

    (repo_path / "main.py").write_text(
        'print "hello"\nname = raw_input("x")\nfor i in xrange(2):\n    print i\n',
        encoding="utf-8",
    )
    (repo_path / "utils.py").write_text(
        "def x(d):\n    return d.iteritems()\n",
        encoding="utf-8",
    )

    store = PheromoneStore(_build_config(), base_path=tmp_path)
    scout = Scout(
        name="scout",
        config=_build_config(),
        pheromone_store=store,
        target_repo_path=repo_path,
    )

    acted = scout.run()

    assert acted is True

    tasks = store.read_all("tasks")
    status = store.read_all("status")

    assert sorted(tasks.keys()) == ["main.py", "utils.py"]
    assert sorted(status.keys()) == ["main.py", "utils.py"]

    main_task = tasks["main.py"]
    assert main_task["intensity"] >= 0.1
    assert "raw_input" in main_task["patterns_found"]
    assert any(detail["source"] == "regex" for detail in main_task["pattern_details"])

    assert status["main.py"]["status"] == "pending"
    assert status["main.py"]["retry_count"] == 0
    assert status["main.py"]["inhibition"] == 0.0


def test_scout_min_max_normalization_degenerate_case(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)

    content = "def run(d):\n    return d.iteritems()\n"
    (repo_path / "a.py").write_text(content, encoding="utf-8")
    (repo_path / "b.py").write_text(content, encoding="utf-8")

    store = PheromoneStore(_build_config(), base_path=tmp_path)
    scout = Scout(
        name="scout",
        config=_build_config(),
        pheromone_store=store,
        target_repo_path=repo_path,
    )

    scout.run()

    tasks = store.read_all("tasks")
    assert tasks["a.py"]["intensity"] == 0.5
    assert tasks["b.py"]["intensity"] == 0.5
