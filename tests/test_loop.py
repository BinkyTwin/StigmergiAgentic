"""Integration-style tests for the Sprint 3 round-robin loop."""

from __future__ import annotations

from pathlib import Path

from environment.pheromone_store import PheromoneStore
from stigmergy.loop import run_loop


class FakeLLMClient:
    """Minimal LLM stub for loop tests."""

    def __init__(self, total_tokens_used: int = 0, total_cost_usd: float = 0.0) -> None:
        self.total_tokens_used = total_tokens_used
        self.total_cost_usd = total_cost_usd

    def call(self, prompt: str, system: str | None = None):  # type: ignore[no-untyped-def]
        class Response:
            def __init__(self) -> None:
                self.content = "print('ok')\n"
                self.tokens_used = 0
                self.latency_ms = 1

        return Response()

    def extract_code_block(self, text: str) -> str:
        return text


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
            "max_tokens_total": 100000,
            "max_budget_usd": 0.0,
        },
        "loop": {
            "max_ticks": 10,
            "idle_cycles_to_stop": 2,
        },
        "metrics": {
            "output_dir": "metrics/output",
        },
        "runtime": {
            "base_path": str(base_path),
            "run_id": "test_run",
        },
    }


def test_loop_stops_when_all_terminal(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    config = _build_config(tmp_path)
    store = PheromoneStore(config=config, base_path=tmp_path)
    store.write(
        "status",
        "done.py",
        {"status": "validated", "retry_count": 0, "inhibition": 0.0},
        agent_id="validator",
    )

    result = run_loop(
        config=config,
        target_repo_path=repo_path,
        llm_client=FakeLLMClient(),
        store=store,
    )
    assert result["stop_reason"] == "all_terminal"


def test_loop_stops_on_budget_exhaustion(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    config = _build_config(tmp_path)
    config["llm"]["max_tokens_total"] = 5

    result = run_loop(
        config=config,
        target_repo_path=repo_path,
        llm_client=FakeLLMClient(total_tokens_used=10),
    )
    assert result["stop_reason"] == "budget_exhausted"


def test_loop_stops_on_cost_budget_exhaustion(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    config = _build_config(tmp_path)
    config["llm"]["max_budget_usd"] = 0.01

    result = run_loop(
        config=config,
        target_repo_path=repo_path,
        llm_client=FakeLLMClient(total_tokens_used=1, total_cost_usd=0.02),
    )
    assert result["stop_reason"] == "budget_exhausted"


def test_loop_stops_on_idle_cycles(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    config = _build_config(tmp_path)
    config["loop"]["idle_cycles_to_stop"] = 2

    result = run_loop(
        config=config,
        target_repo_path=repo_path,
        llm_client=FakeLLMClient(),
    )
    assert result["stop_reason"] == "idle_cycles"


def test_loop_stops_on_max_ticks(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    config = _build_config(tmp_path)
    config["loop"]["max_ticks"] = 3
    config["loop"]["idle_cycles_to_stop"] = 99

    result = run_loop(
        config=config,
        target_repo_path=repo_path,
        llm_client=FakeLLMClient(),
    )
    assert result["stop_reason"] == "max_ticks"
    assert result["summary"]["total_ticks"] == 3


def test_loop_maintains_retry_to_pending(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    config = _build_config(tmp_path)
    config["loop"]["max_ticks"] = 1
    config["loop"]["idle_cycles_to_stop"] = 99

    store = PheromoneStore(config=config, base_path=tmp_path)
    store.write(
        "status",
        "queued.py",
        {"status": "retry", "retry_count": 1, "inhibition": 0.5},
        agent_id="validator",
    )

    run_loop(
        config=config,
        target_repo_path=repo_path,
        llm_client=FakeLLMClient(),
        store=store,
    )
    status = store.read_one("status", "queued.py")
    assert status is not None
    assert status["status"] == "pending"


def test_loop_releases_ttl_zombie_lock(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    config = _build_config(tmp_path)
    config["loop"]["max_ticks"] = 1
    config["loop"]["idle_cycles_to_stop"] = 99
    config["thresholds"]["scope_lock_ttl"] = -1

    store = PheromoneStore(config=config, base_path=tmp_path)
    store.write(
        "status",
        "zombie.py",
        {
            "status": "in_progress",
            "retry_count": 0,
            "inhibition": 0.0,
            "lock_owner": "transformer",
            "lock_acquired_tick": -10,
        },
        agent_id="transformer",
    )

    run_loop(
        config=config,
        target_repo_path=repo_path,
        llm_client=FakeLLMClient(),
        store=store,
    )
    status = store.read_one("status", "zombie.py")
    assert status is not None
    assert status["status"] == "pending"
    assert status["retry_count"] == 1
