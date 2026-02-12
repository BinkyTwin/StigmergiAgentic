"""Unit tests for BaseAgent lifecycle behavior."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent
from environment.pheromone_store import PheromoneStore


class DummyAgent(BaseAgent):
    """Concrete test double for BaseAgent."""

    def __init__(
        self,
        should_act_value: bool,
        config: dict[str, Any],
        store: PheromoneStore,
        target_repo_path: Path,
    ) -> None:
        super().__init__(
            name="dummy",
            config=config,
            pheromone_store=store,
            target_repo_path=target_repo_path,
            llm_client=None,
        )
        self.should_act_value = should_act_value
        self.trace: list[str] = []

    def perceive(self) -> dict[str, Any]:
        self.trace.append("perceive")
        return {"ok": True}

    def should_act(self, perception: dict[str, Any]) -> bool:
        self.trace.append("should_act")
        return self.should_act_value

    def decide(self, perception: dict[str, Any]) -> dict[str, Any]:
        self.trace.append("decide")
        return {"decision": 1}

    def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        self.trace.append("execute")
        return {"result": 1}

    def deposit(self, result: dict[str, Any]) -> None:
        self.trace.append("deposit")


def _build_config() -> dict:
    return {
        "llm": {"max_tokens_total": 1000},
        "thresholds": {"max_retry_count": 3, "scope_lock_ttl": 3},
        "pheromones": {"decay_type": "exponential", "decay_rate": 0.05},
    }


def test_run_returns_false_when_idle(tmp_path: Path) -> None:
    store = PheromoneStore(_build_config(), base_path=tmp_path)
    agent = DummyAgent(False, _build_config(), store, tmp_path)

    acted = agent.run()

    assert acted is False
    assert agent.trace == ["perceive", "should_act"]


def test_run_executes_full_cycle_when_active(tmp_path: Path) -> None:
    store = PheromoneStore(_build_config(), base_path=tmp_path)
    agent = DummyAgent(True, _build_config(), store, tmp_path)

    acted = agent.run()

    assert acted is True
    assert agent.trace == ["perceive", "should_act", "decide", "execute", "deposit"]
