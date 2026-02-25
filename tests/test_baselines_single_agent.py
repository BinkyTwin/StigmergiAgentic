"""Tests for Sprint 4 single-agent baseline runner."""

from __future__ import annotations

from pathlib import Path

import pytest

import baselines.single_agent as single_agent_module
from baselines.single_agent import FileTask, SingleAgentRunner


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
            "idle_cycles_to_stop": 2,
        },
        "runtime": {
            "base_path": str(base_path),
        },
    }


class FakeLLMClient:
    """LLM stub for deterministic baseline runner tests."""

    def __init__(self, config: dict[str, object]) -> None:
        self.total_tokens_used = 0
        self.total_cost_usd = 0.0


def test_single_agent_next_pending_task_prefers_first_pending(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(single_agent_module, "LLMClient", FakeLLMClient)

    tasks = [
        FileTask(file_key="a.py", intensity=1.0, patterns=[]),
        FileTask(file_key="b.py", intensity=0.9, patterns=[]),
    ]
    statuses = {
        "a.py": {"status": "validated"},
        "b.py": {"status": "retry"},
    }
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    runner = SingleAgentRunner(
        config=_build_config(tmp_path), target_repo_path=repo_path
    )
    next_task = runner._next_pending_task(statuses=statuses, tasks=tasks)
    assert next_task is not None
    assert next_task.file_key == "b.py"


def test_single_agent_run_records_validated_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(single_agent_module, "LLMClient", FakeLLMClient)

    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    (repo_path / "sample.py").write_text("print('ok')\n", encoding="utf-8")

    runner = SingleAgentRunner(
        config=_build_config(tmp_path), target_repo_path=repo_path
    )
    task = FileTask(file_key="sample.py", intensity=1.0, patterns=["print_statement"])

    monkeypatch.setattr(runner, "_collect_tasks", lambda: [task])

    def fake_process_task(
        *,
        task: FileTask,
        statuses: dict[str, dict[str, object]],
        retries: dict[str, int],
    ) -> None:
        statuses[task.file_key] = {
            "status": "validated",
            "retry_count": retries[task.file_key],
            "inhibition": 0.0,
        }

    monkeypatch.setattr(runner, "_process_task", fake_process_task)

    result = runner.run(run_id="single_agent_test")
    summary = result["summary"]

    assert summary["run_id"] == "single_agent_test"
    assert summary["baseline"] == "single_agent"
    assert summary["scheduler"] == "single_agent"
    assert summary["stop_reason"] == "all_terminal"
    assert summary["files_total"] == 1
    assert summary["files_validated"] == 1
