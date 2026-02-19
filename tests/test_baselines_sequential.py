"""Tests for Sprint 4 sequential baseline runner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import baselines.sequential as sequential_module
from environment.pheromone_store import PheromoneStore


def _build_config(base_path: Path) -> dict:
    return {
        "pheromones": {
            "task_intensity_clamp": [0.1, 1.0],
            "decay_type": "exponential",
            "decay_rate": 0.05,
            "inhibition_decay_rate": 0.08,
            "inhibition_threshold": 0.1,
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
            "temperature": 0.2,
            "max_tokens_total": 100000,
            "max_budget_usd": 0.0,
        },
        "loop": {
            "max_ticks": 5,
            "idle_cycles_to_stop": 1,
        },
        "runtime": {
            "base_path": str(base_path),
        },
    }


class FakeIdleAgent:
    """Agent stub that never acts."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def run(self) -> bool:
        return False


class FakeAlwaysActAgent:
    """Agent stub that always reports action."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def run(self) -> bool:
        return True


class FakeLLMClient:
    """LLM stub exposing deterministic budget counters."""

    def __init__(self, config: dict[str, Any]) -> None:
        llm_cfg = config.get("llm", {})
        if not isinstance(llm_cfg, dict):
            llm_cfg = {}
        self.total_tokens_used = int(llm_cfg.get("initial_tokens", 0))
        self.total_cost_usd = float(llm_cfg.get("initial_cost_usd", 0.0))


def test_sequential_baseline_stops_on_idle_cycles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _build_config(tmp_path)
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    store = PheromoneStore(config=config, base_path=tmp_path)

    monkeypatch.setattr(sequential_module, "LLMClient", FakeLLMClient)
    monkeypatch.setattr(sequential_module, "Scout", FakeIdleAgent)
    monkeypatch.setattr(sequential_module, "Transformer", FakeIdleAgent)
    monkeypatch.setattr(sequential_module, "Tester", FakeIdleAgent)
    monkeypatch.setattr(sequential_module, "Validator", FakeIdleAgent)

    result = sequential_module.run_sequential_baseline(
        config=config,
        target_repo_path=repo_path,
        pheromone_store=store,
        run_id="seq_idle",
    )

    summary = result["summary"]
    assert summary["run_id"] == "seq_idle"
    assert summary["baseline"] == "sequential"
    assert summary["scheduler"] == "sequential"
    assert summary["stop_reason"] == "idle_cycles"


def test_sequential_baseline_stops_on_budget_exhaustion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _build_config(tmp_path)
    config["llm"]["max_tokens_total"] = 5
    config["llm"]["initial_tokens"] = 10

    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    store = PheromoneStore(config=config, base_path=tmp_path)

    monkeypatch.setattr(sequential_module, "LLMClient", FakeLLMClient)
    monkeypatch.setattr(sequential_module, "Scout", FakeIdleAgent)
    monkeypatch.setattr(sequential_module, "Transformer", FakeIdleAgent)
    monkeypatch.setattr(sequential_module, "Tester", FakeIdleAgent)
    monkeypatch.setattr(sequential_module, "Validator", FakeIdleAgent)

    result = sequential_module.run_sequential_baseline(
        config=config,
        target_repo_path=repo_path,
        pheromone_store=store,
        run_id="seq_budget",
    )

    assert result["summary"]["stop_reason"] == "budget_exhausted"


def test_sequential_baseline_caps_stage_actions_per_tick(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _build_config(tmp_path)
    config["loop"]["max_ticks"] = 2
    config["loop"]["idle_cycles_to_stop"] = 99
    config["loop"]["sequential_stage_action_cap"] = 3

    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    (repo_path / "sample.py").write_text("print('ok')\n", encoding="utf-8")
    store = PheromoneStore(config=config, base_path=tmp_path)

    monkeypatch.setattr(sequential_module, "LLMClient", FakeLLMClient)
    monkeypatch.setattr(sequential_module, "Scout", FakeAlwaysActAgent)
    monkeypatch.setattr(sequential_module, "Transformer", FakeIdleAgent)
    monkeypatch.setattr(sequential_module, "Tester", FakeIdleAgent)
    monkeypatch.setattr(sequential_module, "Validator", FakeIdleAgent)

    result = sequential_module.run_sequential_baseline(
        config=config,
        target_repo_path=repo_path,
        pheromone_store=store,
        run_id="seq_cap",
    )

    assert result["summary"]["stop_reason"] == "max_ticks"
    assert len(result["tick_rows"]) == 2
