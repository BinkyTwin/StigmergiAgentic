"""Tests for CLI wiring and review mode behaviors."""

from __future__ import annotations

import errno
from pathlib import Path

import pytest
import yaml
from git import Repo

import main as main_module
from environment.pheromone_store import PheromoneStore


def _write_config(path: Path) -> None:
    payload = {
        "pheromones": {
            "decay_type": "exponential",
            "decay_rate": 0.05,
            "inhibition_decay_rate": 0.08,
            "inhibition_threshold": 0.1,
            "task_intensity_clamp": [0.1, 1.0],
        },
        "thresholds": {
            "transformer_intensity_min": 0.2,
            "validator_confidence_high": 0.8,
            "validator_confidence_low": 0.5,
            "max_retry_count": 3,
            "scope_lock_ttl": 3,
        },
        "llm": {
            "provider": "openrouter",
            "model": "qwen/qwen3-235b-a22b-2507",
            "max_tokens_total": 100000,
        },
        "loop": {
            "max_ticks": 5,
            "idle_cycles_to_stop": 2,
        },
        "metrics": {
            "output_dir": "metrics/output",
        },
        "tester": {
            "fallback_quality": {
                "compile_import_fail": 0.4,
                "related_regression": 0.6,
                "pass_or_inconclusive": 0.8,
            }
        },
    }
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")


def test_main_requires_repo_for_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config.yaml"
    _write_config(config_path)

    monkeypatch.setattr(main_module, "_configure_logging", lambda base_path, verbose: None)
    monkeypatch.setattr(main_module, "load_dotenv", lambda *args, **kwargs: None)

    with pytest.raises(ValueError, match="--repo is required"):
        main_module.main(["--config", str(config_path)])


def test_main_forwards_repo_ref(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config.yaml"
    _write_config(config_path)

    prepared_repo_path = tmp_path / "prepared_repo"
    prepared_repo_path.mkdir(parents=True)
    (prepared_repo_path / "module.py").write_text("x = 1\n", encoding="utf-8")
    repo = Repo.init(prepared_repo_path)
    repo.git.add(".")
    repo.index.commit("initial")

    captured: dict[str, str | None] = {}

    def fake_prepare(repo_spec, repo_ref, base_path, config, resume):  # type: ignore[no-untyped-def]
        captured["repo_ref"] = repo_ref
        return prepared_repo_path, repo

    monkeypatch.setattr(main_module, "_configure_logging", lambda base_path, verbose: None)
    monkeypatch.setattr(main_module, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "_prepare_target_repo", fake_prepare)
    monkeypatch.setattr(main_module, "_reset_pheromone_state", lambda base_path: None)
    monkeypatch.setattr(
        main_module,
        "_build_run_manifest",
        lambda **kwargs: {"run_id": kwargs["run_id"], "target_repo_commit": repo.head.commit.hexsha},
    )
    monkeypatch.setattr(main_module, "ensure_output_dir", lambda output_dir: output_dir)
    monkeypatch.setattr(main_module, "write_manifest_json", lambda path, manifest: None)
    monkeypatch.setattr(
        main_module,
        "run_loop",
        lambda config, target_repo_path: {"summary": {"stop_reason": "idle_cycles", "success_rate": 1.0}},
    )

    exit_code = main_module.main(
        [
            "--repo",
            "https://github.com/docopt/docopt.git",
            "--repo-ref",
            "0.6.2",
            "--config",
            str(config_path),
        ]
    )

    assert exit_code == 0
    assert captured["repo_ref"] == "0.6.2"


def test_review_mode_validate_action(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = {
        "pheromones": {
            "decay_type": "exponential",
            "decay_rate": 0.05,
            "inhibition_decay_rate": 0.08,
        },
        "thresholds": {
            "validator_confidence_high": 0.8,
            "max_retry_count": 3,
            "scope_lock_ttl": 3,
        },
        "llm": {"max_tokens_total": 100000},
    }

    store = PheromoneStore(config=config, base_path=tmp_path)
    store.write(
        "status",
        "module.py",
        {"status": "needs_review", "retry_count": 0, "inhibition": 0.0},
        agent_id="validator",
    )
    store.write(
        "quality",
        "module.py",
        {
            "confidence": 0.6,
            "tests_total": 1,
            "tests_passed": 1,
            "tests_failed": 0,
            "coverage": 1.0,
            "issues": ["manual check"],
        },
        agent_id="tester",
    )

    inputs = iter(["validate"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    exit_code = main_module._run_review_mode(
        config=config,
        base_path=tmp_path,
        target_repo_path=tmp_path / "target_repo",
    )

    assert exit_code == 0
    status = store.read_one("status", "module.py")
    quality = store.read_one("quality", "module.py")
    assert status is not None and status["status"] == "validated"
    assert quality is not None and quality["confidence"] >= 0.8


def test_clear_target_repo_path_handles_busy_mount(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target_repo = tmp_path / "target_repo"
    target_repo.mkdir(parents=True)
    (target_repo / "module.py").write_text("x = 1\n", encoding="utf-8")
    nested = target_repo / "nested"
    nested.mkdir()
    (nested / "child.py").write_text("y = 2\n", encoding="utf-8")

    original_rmtree = main_module.shutil.rmtree
    state = {"raised": False}

    def fake_rmtree(path: Path, *args: object, **kwargs: object) -> None:
        if Path(path) == target_repo and not state["raised"]:
            state["raised"] = True
            raise OSError(errno.EBUSY, "resource busy")
        original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(main_module.shutil, "rmtree", fake_rmtree)

    main_module._clear_target_repo_path(target_repo)

    assert target_repo.exists()
    assert list(target_repo.iterdir()) == []
