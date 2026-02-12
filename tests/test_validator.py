"""Unit tests for the Validator agent."""

from __future__ import annotations

from pathlib import Path

from git import Repo

from agents.validator import Validator
from environment.pheromone_store import PheromoneStore


def _build_config() -> dict:
    return {
        "pheromones": {
            "decay_type": "exponential",
            "decay_rate": 0.05,
            "inhibition_decay_rate": 0.08,
        },
        "thresholds": {
            "validator_confidence_high": 0.8,
            "validator_confidence_low": 0.5,
            "max_retry_count": 3,
            "scope_lock_ttl": 3,
        },
        "llm": {
            "max_tokens_total": 100000,
        },
    }


def _init_repo_with_file(repo_path: Path, filename: str, content: str) -> Repo:
    repo_path.mkdir(parents=True)
    file_path = repo_path / filename
    file_path.write_text(content, encoding="utf-8")

    repo = Repo.init(repo_path)
    repo.git.add(filename)
    repo.index.commit("initial")
    return repo


def test_validator_validates_and_commits_high_confidence(tmp_path: Path) -> None:
    repo = _init_repo_with_file(
        tmp_path / "repo", "module.py", "def value():\n    return 1\n"
    )
    repo_path = Path(repo.working_tree_dir or "")

    (repo_path / "module.py").write_text(
        "def value():\n    return 2\n", encoding="utf-8"
    )

    store = PheromoneStore(_build_config(), base_path=tmp_path)
    store.write(
        "status",
        "module.py",
        {"status": "tested", "retry_count": 0, "inhibition": 0.0},
        agent_id="tester",
    )
    store.write(
        "quality",
        "module.py",
        {
            "confidence": 0.9,
            "tests_total": 1,
            "tests_passed": 1,
            "tests_failed": 0,
            "coverage": 1.0,
            "issues": [],
        },
        agent_id="tester",
    )

    validator = Validator(
        name="validator",
        config=_build_config(),
        pheromone_store=store,
        target_repo_path=repo_path,
    )

    validator.run()

    status = store.read_one("status", "module.py")
    quality = store.read_one("quality", "module.py")

    assert status is not None and status["status"] == "validated"
    assert quality is not None and quality["confidence"] == 1.0
    assert len(list(repo.iter_commits("HEAD"))) == 2


def test_validator_escalates_medium_confidence(tmp_path: Path) -> None:
    repo = _init_repo_with_file(
        tmp_path / "repo", "module.py", "def value():\n    return 1\n"
    )
    repo_path = Path(repo.working_tree_dir or "")

    store = PheromoneStore(_build_config(), base_path=tmp_path)
    store.write(
        "status",
        "module.py",
        {"status": "tested", "retry_count": 0, "inhibition": 0.0},
        agent_id="tester",
    )
    store.write(
        "quality",
        "module.py",
        {
            "confidence": 0.6,
            "tests_total": 1,
            "tests_passed": 1,
            "tests_failed": 0,
            "coverage": 0.8,
            "issues": ["manual review"],
        },
        agent_id="tester",
    )

    validator = Validator(
        name="validator",
        config=_build_config(),
        pheromone_store=store,
        target_repo_path=repo_path,
    )

    validator.run()

    status = store.read_one("status", "module.py")
    assert status is not None
    assert status["status"] == "needs_review"


def test_validator_rolls_back_low_confidence_to_retry(tmp_path: Path) -> None:
    repo = _init_repo_with_file(
        tmp_path / "repo", "module.py", "def value():\n    return 1\n"
    )
    repo_path = Path(repo.working_tree_dir or "")

    (repo_path / "module.py").write_text(
        "def value():\n    return 999\n", encoding="utf-8"
    )

    store = PheromoneStore(_build_config(), base_path=tmp_path)
    store.write(
        "status",
        "module.py",
        {"status": "tested", "retry_count": 0, "inhibition": 0.0},
        agent_id="tester",
    )
    store.write(
        "quality",
        "module.py",
        {
            "confidence": 0.2,
            "tests_total": 1,
            "tests_passed": 0,
            "tests_failed": 1,
            "coverage": 0.1,
            "issues": ["failing tests"],
        },
        agent_id="tester",
    )

    validator = Validator(
        name="validator",
        config=_build_config(),
        pheromone_store=store,
        target_repo_path=repo_path,
    )

    validator.run()

    status = store.read_one("status", "module.py")
    quality = store.read_one("quality", "module.py")
    restored_content = (repo_path / "module.py").read_text(encoding="utf-8")

    assert status is not None
    assert status["status"] == "retry"
    assert status["retry_count"] == 1
    assert status["inhibition"] == 0.5

    assert quality is not None
    assert quality["confidence"] == 0.0
    assert "return 1" in restored_content
