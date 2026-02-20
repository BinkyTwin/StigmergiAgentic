"""Tests for Sprint 4 single-agent baseline runner."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import baselines.single_agent as single_agent_module
from baselines.single_agent import FileTask, SingleAgentRunner
from environment.guardrails import ScopeLockError


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
        "tester": {
            "fallback_quality": {
                "compile_import_fail": 0.4,
                "related_regression": 0.6,
                "pass_or_inconclusive": 0.8,
            },
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


@dataclass
class _FakeLLMResponse:
    content: str


class FakeLLMClientWithCode:
    """LLM stub that returns a fixed code block."""

    def __init__(self, config: dict[str, Any], *, code: str) -> None:
        self.total_tokens_used = 0
        self.total_cost_usd = 0.0
        self._code = code

    def call(self, *, prompt: str, system: str) -> _FakeLLMResponse:
        return _FakeLLMResponse(content=f"```python\n{self._code}\n```")

    def extract_code_block(self, content: str) -> str:
        return self._code


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


def test_single_agent_tester_validates_correct_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Success path: valid Python 3 code → Tester fallback → confidence 0.8 → validated."""
    valid_py3 = "x = 1\n"
    fake_llm = FakeLLMClientWithCode(config={}, code=valid_py3)

    monkeypatch.setattr(single_agent_module, "LLMClient", lambda config: fake_llm)

    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    (repo_path / "hello.py").write_text("x = 1\n", encoding="utf-8")

    config = _build_config(tmp_path)
    runner = SingleAgentRunner(config=config, target_repo_path=repo_path)
    runner.llm_client = fake_llm

    task = FileTask(file_key="hello.py", intensity=1.0, patterns=["print_statement"])
    statuses: dict[str, dict[str, Any]] = {
        "hello.py": {"status": "pending", "retry_count": 0, "inhibition": 0.0},
    }
    retries: dict[str, int] = {"hello.py": 0}

    runner._process_task(task=task, statuses=statuses, retries=retries)

    assert statuses["hello.py"]["status"] == "validated"
    quality = runner.store.read_one("quality", "hello.py")
    assert quality is not None
    assert "test_mode" in quality.get("metadata", quality)


def test_single_agent_tester_retries_on_import_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Low-confidence path: Py2 stdlib import → Tester confidence 0.4 → retry + revert."""
    broken_code = "import ConfigParser\nprint('hello')\n"
    original_source = "print 'hello'\n"
    fake_llm = FakeLLMClientWithCode(config={}, code=broken_code)

    monkeypatch.setattr(single_agent_module, "LLMClient", lambda config: fake_llm)

    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    (repo_path / "broken.py").write_text(original_source, encoding="utf-8")

    config = _build_config(tmp_path)
    runner = SingleAgentRunner(config=config, target_repo_path=repo_path)
    runner.llm_client = fake_llm

    task = FileTask(file_key="broken.py", intensity=1.0, patterns=["print_statement"])
    statuses: dict[str, dict[str, Any]] = {
        "broken.py": {"status": "pending", "retry_count": 0, "inhibition": 0.0},
    }
    retries: dict[str, int] = {"broken.py": 0}

    runner._process_task(task=task, statuses=statuses, retries=retries)

    assert statuses["broken.py"]["status"] == "retry"
    restored = (repo_path / "broken.py").read_text(encoding="utf-8")
    assert restored == original_source


def test_single_agent_scope_lock_does_not_abort_file_processing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stale/foreign locks should not crash the full single-agent run."""
    valid_py3 = "x = 1\n"
    fake_llm = FakeLLMClientWithCode(config={}, code=valid_py3)
    monkeypatch.setattr(single_agent_module, "LLMClient", lambda config: fake_llm)

    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    original_source = "print 'legacy'\n"
    (repo_path / "locked.py").write_text(original_source, encoding="utf-8")

    runner = SingleAgentRunner(
        config=_build_config(tmp_path), target_repo_path=repo_path
    )
    runner.llm_client = fake_llm

    def always_locked_write(*args: Any, **kwargs: Any) -> None:
        raise ScopeLockError(
            "Scope lock violation for locked.py: held by transformer, not single_agent"
        )

    monkeypatch.setattr(runner.store, "write", always_locked_write)

    task = FileTask(file_key="locked.py", intensity=1.0, patterns=["print_statement"])
    statuses: dict[str, dict[str, Any]] = {
        "locked.py": {"status": "pending", "retry_count": 0, "inhibition": 0.0},
    }
    retries: dict[str, int] = {"locked.py": 0}

    runner._process_task(task=task, statuses=statuses, retries=retries)

    assert statuses["locked.py"]["status"] == "retry"
    assert retries["locked.py"] == 1
