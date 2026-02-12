"""Unit tests for the Tester agent."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.tester import Tester
from environment.pheromone_store import PheromoneStore


def _build_config() -> dict:
    return {
        "pheromones": {
            "decay_type": "exponential",
            "decay_rate": 0.05,
            "inhibition_decay_rate": 0.08,
        },
        "tester": {
            "fallback_quality": {
                "compile_import_fail": 0.4,
                "related_regression": 0.6,
                "pass_or_inconclusive": 0.8,
            },
            "optional_dependency_hints": [
                "requires that",
                "pip install",
                "optional dependency",
            ],
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


def test_tester_fallback_compile_import_sets_adaptive_confidence(tmp_path: Path) -> None:
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
    assert quality["confidence"] == 0.8
    assert quality["metadata"]["test_mode"].startswith("fallback_global_")


def test_tester_fallback_related_regression_sets_medium_confidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)

    (repo_path / "module.py").write_text("def value():\n    return 1\n", encoding="utf-8")

    store = PheromoneStore(_build_config(), base_path=tmp_path)
    store.write(
        "status",
        "module.py",
        {"status": "transformed", "retry_count": 0, "inhibition": 0.0},
        agent_id="transformer",
    )

    tester = Tester(
        name="tester",
        config=_build_config(),
        pheromone_store=store,
        target_repo_path=repo_path,
    )

    monkeypatch.setattr(
        tester,
        "_run_global_pytest",
        lambda file_path: {
            "tests_total": 1,
            "tests_passed": 0,
            "tests_failed": 1,
            "issues": ["module.py regression"],
            "classification": "related",
        },
    )

    tester.run()
    quality = store.read_one("quality", "module.py")
    assert quality is not None
    assert quality["confidence"] == 0.6


def test_tester_fallback_usage_on_import_is_inconclusive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)

    (repo_path / "cli_module.py").write_text(
        "raise SystemExit('Usage: cli_module.py <arg>')\n",
        encoding="utf-8",
    )

    store = PheromoneStore(_build_config(), base_path=tmp_path)
    store.write(
        "status",
        "cli_module.py",
        {"status": "transformed", "retry_count": 0, "inhibition": 0.0},
        agent_id="transformer",
    )

    tester = Tester(
        name="tester",
        config=_build_config(),
        pheromone_store=store,
        target_repo_path=repo_path,
    )

    monkeypatch.setattr(
        tester,
        "_run_global_pytest",
        lambda file_path: {
            "tests_total": 1,
            "tests_passed": 0,
            "tests_failed": 1,
            "issues": ["Usage: cli_module.py <arg>"],
            "classification": "inconclusive",
        },
    )

    tester.run()
    quality = store.read_one("quality", "cli_module.py")
    assert quality is not None
    assert quality["confidence"] == 0.8
    assert quality["metadata"]["test_mode"] == "fallback_global_inconclusive"


def test_tester_fallback_missing_py2_stdlib_module_is_related_failure(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)

    (repo_path / "legacy_import.py").write_text("import urllib2\n", encoding="utf-8")

    store = PheromoneStore(_build_config(), base_path=tmp_path)
    store.write(
        "status",
        "legacy_import.py",
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
    quality = store.read_one("quality", "legacy_import.py")
    assert quality is not None
    assert quality["confidence"] == 0.4
    assert quality["metadata"]["test_mode"] == "fallback_compile_import_fail"


def test_tester_optional_dependency_message_is_inconclusive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)

    (repo_path / "plugin_example.py").write_text(
        "raise RuntimeError('This optional dependency is missing; pip install extras')\n",
        encoding="utf-8",
    )

    store = PheromoneStore(_build_config(), base_path=tmp_path)
    store.write(
        "status",
        "plugin_example.py",
        {"status": "transformed", "retry_count": 0, "inhibition": 0.0},
        agent_id="transformer",
    )

    tester = Tester(
        name="tester",
        config=_build_config(),
        pheromone_store=store,
        target_repo_path=repo_path,
    )

    monkeypatch.setattr(
        tester,
        "_run_global_pytest",
        lambda file_path: {
            "tests_total": 1,
            "tests_passed": 0,
            "tests_failed": 1,
            "issues": ["This optional dependency is missing; pip install extras"],
            "classification": "inconclusive",
        },
    )

    tester.run()
    quality = store.read_one("quality", "plugin_example.py")
    assert quality is not None
    assert quality["confidence"] == 0.8
    assert quality["metadata"]["test_mode"] == "fallback_global_inconclusive"
