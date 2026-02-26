"""Unit tests for generic stigmergic agent."""

from __future__ import annotations

import asyncio
import random
from typing import Any

import pytest

from core.agent import StigmergicAgent
from core.environment import Environment
from core.guardrails import BudgetExceededError
from core.marker import Marker
from core.marker_store import MarkerStore
from core.tool_registry import ActionResult, Tool, ToolRegistry


class StubTool(Tool):
    """Simple tool used to test agent execution paths."""

    def __init__(
        self,
        *,
        action_type: str,
        eligible_states: set[str],
        next_state: str,
        consumed_tokens: int = 0,
        raises: Exception | None = None,
    ) -> None:
        self.action_type = action_type
        self.eligible_states = eligible_states
        self.next_state = next_state
        self.consumed_tokens = consumed_tokens
        self.raises = raises

    def is_eligible(self, marker: Marker) -> bool:
        return marker.state in self.eligible_states

    async def execute(
        self,
        *,
        agent_id: str,
        marker: Marker,
        environment: Any,
        llm_client: Any | None = None,
    ) -> ActionResult:
        if self.raises is not None:
            raise self.raises

        updated = Marker.from_dict(marker.to_dict())
        updated.state = self.next_state
        updated.intensity = max(0.1, marker.intensity - 0.1)
        return ActionResult(
            action_type=self.action_type,
            marker_updates=[updated],
            consumed_tokens=self.consumed_tokens,
        )


def _make_marker(marker_id: str = "m-1", **overrides: object) -> Marker:
    payload = {
        "id": marker_id,
        "marker_type": "task",
        "target": "file.py",
        "intensity": 1.0,
        "state": "pending",
        "payload": {},
        "created_by": "seed",
        "created_at": "2026-02-26T12:00:00+00:00",
        "updated_by": "seed",
        "updated_at": "2026-02-26T12:00:00+00:00",
        "inhibition": 0.0,
        "retry_count": 0,
        "history": ["created"],
    }
    payload.update(overrides)
    return Marker(**payload)


def _build_environment(tmp_path, config_dict: dict) -> Environment:
    store = MarkerStore(db_path=tmp_path / "pheromones" / "markers.db")
    return Environment(store=store, config=config_dict)


def test_perceive_returns_none_when_no_eligible_markers(tmp_path, config_dict: dict) -> None:
    registry = ToolRegistry()
    registry.register(StubTool(action_type="increment", eligible_states={"active"}, next_state="completed"))
    agent = StigmergicAgent(agent_id="agent-1", tool_registry=registry, config=config_dict)
    env = _build_environment(tmp_path, config_dict)
    env.store.upsert_marker(_make_marker(state="pending"), agent_id="seed")

    snapshot = env.snapshot(tick=0)
    decision = asyncio.run(agent.perceive_and_decide(snapshot))
    assert decision is None


def test_perceive_chooses_action_from_pressure_distribution(tmp_path, config_dict: dict) -> None:
    config_dict["agents"]["selection_temperature"] = 0.0

    registry = ToolRegistry()
    registry.register(StubTool(action_type="increment", eligible_states={"pending"}, next_state="active"))
    registry.register(StubTool(action_type="check", eligible_states={"pending"}, next_state="completed"))

    env = _build_environment(tmp_path, config_dict)
    env.store.upsert_marker(
        _make_marker(payload={"eligible_actions": ["increment"]}),
        agent_id="seed",
    )

    agent = StigmergicAgent(
        agent_id="agent-1",
        tool_registry=registry,
        config=config_dict,
        rng=random.Random(1),
    )

    decision = asyncio.run(agent.perceive_and_decide(env.snapshot(tick=0)))
    assert decision is not None
    assert decision.action_type == "increment"


def test_perceive_ignores_marker_locked_by_other_agent(tmp_path, config_dict: dict) -> None:
    registry = ToolRegistry()
    registry.register(StubTool(action_type="increment", eligible_states={"pending"}, next_state="active"))
    agent = StigmergicAgent(agent_id="agent-1", tool_registry=registry, config=config_dict)

    env = _build_environment(tmp_path, config_dict)
    env.store.upsert_marker(_make_marker(lock_owner="agent-2", lock_tick=1), agent_id="seed")

    decision = asyncio.run(agent.perceive_and_decide(env.snapshot(tick=0)))
    assert decision is None


def test_execute_persists_updates(tmp_path, config_dict: dict) -> None:
    registry = ToolRegistry()
    registry.register(StubTool(action_type="increment", eligible_states={"pending"}, next_state="active"))
    agent = StigmergicAgent(agent_id="agent-1", tool_registry=registry, config=config_dict)

    env = _build_environment(tmp_path, config_dict)
    env.store.upsert_marker(_make_marker(), agent_id="seed")
    env.acquire_lock("m-1", "agent-1", tick=0)

    decision = asyncio.run(agent.perceive_and_decide(env.snapshot(tick=0)))
    assert decision is not None

    result = asyncio.run(agent.execute(decision=decision, environment=env))
    stored = env.store.get_marker("m-1")

    assert result.metadata == {}
    assert stored is not None
    assert stored.state == "active"


def test_execute_updates_history_on_transition(tmp_path, config_dict: dict) -> None:
    registry = ToolRegistry()
    registry.register(StubTool(action_type="increment", eligible_states={"pending"}, next_state="active"))
    agent = StigmergicAgent(agent_id="agent-1", tool_registry=registry, config=config_dict)

    env = _build_environment(tmp_path, config_dict)
    env.store.upsert_marker(_make_marker(), agent_id="seed")
    env.acquire_lock("m-1", "agent-1", tick=0)

    decision = asyncio.run(agent.perceive_and_decide(env.snapshot(tick=0)))
    assert decision is not None
    asyncio.run(agent.execute(decision=decision, environment=env))

    updated = env.store.get_marker("m-1")
    assert updated is not None
    assert "pending->active" in updated.history


def test_execute_returns_failed_result_on_tool_exception(tmp_path, config_dict: dict) -> None:
    registry = ToolRegistry()
    registry.register(
        StubTool(
            action_type="increment",
            eligible_states={"pending"},
            next_state="active",
            raises=RuntimeError("tool crashed"),
        )
    )
    agent = StigmergicAgent(agent_id="agent-1", tool_registry=registry, config=config_dict)

    env = _build_environment(tmp_path, config_dict)
    env.store.upsert_marker(_make_marker(), agent_id="seed")
    env.acquire_lock("m-1", "agent-1", tick=0)

    decision = asyncio.run(agent.perceive_and_decide(env.snapshot(tick=0)))
    assert decision is not None

    result = asyncio.run(agent.execute(decision=decision, environment=env))
    assert result.metadata.get("failed") is True
    assert "tool crashed" in str(result.metadata.get("error"))


def test_execute_returns_failed_result_when_marker_missing(tmp_path, config_dict: dict) -> None:
    registry = ToolRegistry()
    registry.register(StubTool(action_type="increment", eligible_states={"pending"}, next_state="active"))
    agent = StigmergicAgent(agent_id="agent-1", tool_registry=registry, config=config_dict)
    env = _build_environment(tmp_path, config_dict)

    decision = asyncio.run(
        agent.perceive_and_decide(
            env.snapshot(tick=0)
        )
    )
    assert decision is None

    result = asyncio.run(
        agent.execute(
            decision=
            type("FakeDecision", (), {
                "action_type": "increment",
                "marker_id": "missing",
                "target": "file.py",
            })(),
            environment=env,
        )
    )
    assert result.metadata.get("failed") is True
    assert result.metadata.get("reason") == "marker_not_found"


def test_perceive_filters_high_inhibition(tmp_path, config_dict: dict) -> None:
    config_dict["markers"]["inhibition_threshold"] = 0.2

    registry = ToolRegistry()
    registry.register(StubTool(action_type="increment", eligible_states={"pending"}, next_state="active"))
    agent = StigmergicAgent(agent_id="agent-1", tool_registry=registry, config=config_dict)

    env = _build_environment(tmp_path, config_dict)
    env.store.upsert_marker(_make_marker(inhibition=0.8), agent_id="seed")

    decision = asyncio.run(agent.perceive_and_decide(env.snapshot(tick=0)))
    assert decision is None


def test_perceive_selects_highest_intensity_target(tmp_path, config_dict: dict) -> None:
    registry = ToolRegistry()
    registry.register(StubTool(action_type="increment", eligible_states={"pending"}, next_state="active"))
    agent = StigmergicAgent(agent_id="agent-1", tool_registry=registry, config=config_dict)

    env = _build_environment(tmp_path, config_dict)
    env.store.upsert_marker(_make_marker(marker_id="low", intensity=0.3, target="low.py"), agent_id="seed")
    env.store.upsert_marker(_make_marker(marker_id="high", intensity=0.9, target="high.py"), agent_id="seed")

    decision = asyncio.run(agent.perceive_and_decide(env.snapshot(tick=0)))
    assert decision is not None
    assert decision.marker_id == "high"


def test_execute_raises_budget_error_when_environment_budget_exceeded(
    tmp_path,
    config_dict: dict,
) -> None:
    config_dict["llm"]["max_tokens_total"] = 5

    registry = ToolRegistry()
    registry.register(
        StubTool(
            action_type="increment",
            eligible_states={"pending"},
            next_state="active",
            consumed_tokens=10,
        )
    )
    agent = StigmergicAgent(agent_id="agent-1", tool_registry=registry, config=config_dict)

    env = _build_environment(tmp_path, config_dict)
    env.store.upsert_marker(_make_marker(), agent_id="seed")
    env.acquire_lock("m-1", "agent-1", tick=0)

    decision = asyncio.run(agent.perceive_and_decide(env.snapshot(tick=0)))
    assert decision is not None

    with pytest.raises(BudgetExceededError):
        asyncio.run(agent.execute(decision=decision, environment=env))
