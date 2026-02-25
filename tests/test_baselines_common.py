"""Tests for shared baseline utilities."""

from __future__ import annotations

import argparse
from pathlib import Path

import baselines.common as common_module
import pytest


def _build_config(base_path: Path) -> dict:
    return {
        "llm": {
            "model": "qwen/qwen3-235b-a22b-2507",
            "max_tokens_total": 100000,
            "max_budget_usd": 0.0,
        },
        "runtime": {
            "base_path": str(base_path),
        },
    }


def test_build_run_id_keeps_prefix_and_counter() -> None:
    run_id = common_module.build_run_id(prefix="single_agent", run_index=3)
    assert run_id.startswith("single_agent_")
    assert run_id.endswith("_r03")


def test_build_manifest_contains_expected_fields(tmp_path: Path) -> None:
    manifest = common_module.build_manifest(
        run_id="single_agent_20260217T120000Z_r01",
        baseline_name="single_agent",
        config=_build_config(tmp_path),
        target_repo_path=tmp_path / "repo",
        seed=42,
    )
    assert manifest["baseline"] == "single_agent"
    assert manifest["run_id"] == "single_agent_20260217T120000Z_r01"
    assert manifest["model"] == "qwen/qwen3-235b-a22b-2507"
    assert manifest["seed"] == 42
    assert "manifest_hash" in manifest


def test_prepare_run_environment_resets_pheromones_when_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _build_config(tmp_path)
    args = argparse.Namespace(
        repo="tests/fixtures/synthetic_py2_repo", repo_ref=None, resume=False
    )
    target_repo = tmp_path / "target_repo"
    target_repo.mkdir(parents=True)

    called = {"prepare": 0, "reset": 0}

    def fake_prepare_target_repo(
        repo_spec: str,
        repo_ref: str | None,
        base_path: Path,
        config: dict,
        resume: bool,
    ) -> tuple[Path, object]:
        called["prepare"] += 1
        return target_repo, object()

    def fake_reset_pheromone_state(base_path: Path) -> None:
        called["reset"] += 1

    monkeypatch.setattr(common_module, "_prepare_target_repo", fake_prepare_target_repo)
    monkeypatch.setattr(
        common_module, "_reset_pheromone_state", fake_reset_pheromone_state
    )

    prepared_path, store = common_module.prepare_run_environment(
        args=args,
        base_path=tmp_path,
        config=config,
        reset_pheromones=True,
    )
    assert prepared_path == target_repo
    assert store.base_path == tmp_path
    assert called == {"prepare": 1, "reset": 1}
