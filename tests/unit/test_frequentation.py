"""Unit tests for read-traffic reinforcement."""

from __future__ import annotations

import copy

from core.agent import StigmergicAgent
from core.environment import Environment
from core.marker import Marker
from core.marker_store import MarkerStore
from core.orchestrator import Orchestrator
from core.reinforcement import frequentation_boost
from core.tool_registry import ActionResult, Tool, ToolRegistry


class PendingTool(Tool):
    """Minimal pending-state tool for orchestration tests."""

    action_type = "work"

    def is_eligible(self, marker: Marker) -> bool:
        return marker.state == "pending"

    async def execute(self, *, agent_id, marker, environment, llm_client=None) -> ActionResult:
        updated = Marker.from_dict(marker.to_dict())
        updated.state = "active"
        return ActionResult(action_type=self.action_type, marker_updates=[updated])


def _marker(
    marker_id: str,
    *,
    intensity: float = 0.4,
    state: str = "pending",
) -> Marker:
    return Marker(
        id=marker_id,
        marker_type="task",
        target=marker_id,
        intensity=intensity,
        state=state,
        payload={},
        created_by="seed",
        created_at="2026-03-04T12:00:00+00:00",
        updated_by="seed",
        updated_at="2026-03-04T12:00:00+00:00",
        last_active_at="2026-03-04T12:00:00+00:00",
        history=["created"],
    )


def test_record_read_is_unique_per_marker_agent_tick(tmp_path) -> None:
    store = MarkerStore(db_path=tmp_path / "pheromones" / "markers.db")
    store.record_read("m1", "agent-1", 1)
    store.record_read("m1", "agent-1", 1)
    store.record_read("m1", "agent-2", 1)
    store.record_read("m1", "agent-1", 2)

    assert store.read_count("m1") == 3
    assert store.read_count("m1", since_tick=2) == 1


def test_frequentation_boost_has_diminishing_returns_and_cap() -> None:
    one = frequentation_boost(1, base_boost=0.02, max_boost=0.1, diminishing_factor=0.5)
    three = frequentation_boost(3, base_boost=0.02, max_boost=0.1, diminishing_factor=0.5)
    many = frequentation_boost(20, base_boost=0.02, max_boost=0.1, diminishing_factor=0.5)

    assert three > one
    assert three < (one * 3)
    assert many <= 0.1


def test_environment_maintain_applies_frequentation_boost(
    tmp_path,
    config_dict: dict,
) -> None:
    config = copy.deepcopy(config_dict)
    config["markers"]["decay_rate"] = 0.0
    config["markers"]["default_decay_rate"] = 0.0
    config["markers"]["decay_rates_by_type"]["task"] = 0.0
    config["reinforcement"]["frequentation"]["enabled"] = True

    store = MarkerStore(db_path=tmp_path / "pheromones" / "markers.db")
    store.upsert_marker(_marker("m1", intensity=0.4), agent_id="seed")
    store.record_read("m1", "agent-1", 1)
    store.record_read("m1", "agent-2", 1)

    env = Environment(store=store, config=config)
    result = env.maintain(current_tick=1)
    updated = store.get_marker("m1")

    assert result["frequentation_boosted_markers"] == 1
    assert updated is not None
    assert updated.intensity > 0.4


def test_completed_marker_receives_completion_boost(
    tmp_path,
    config_dict: dict,
) -> None:
    config = copy.deepcopy(config_dict)
    config["markers"]["decay_rate"] = 0.0
    config["markers"]["default_decay_rate"] = 0.0
    config["markers"]["decay_rates_by_type"]["task"] = 0.0
    config["reinforcement"]["frequentation"]["enabled"] = True

    store = MarkerStore(db_path=tmp_path / "pheromones" / "markers.db")
    store.upsert_marker(_marker("done", intensity=0.4, state="completed"), agent_id="seed")
    store.record_read("done", "agent-1", 2)

    env = Environment(store=store, config=config)
    env.maintain(current_tick=2)
    updated = store.get_marker("done")

    assert updated is not None
    assert updated.intensity > 0.45


def test_orchestrator_binds_perception_reads_to_store(
    tmp_path,
    config_dict: dict,
) -> None:
    config = copy.deepcopy(config_dict)
    config["orchestrator"]["max_ticks"] = 1
    config["orchestrator"]["idle_cycles_to_stop"] = 99

    store = MarkerStore(db_path=tmp_path / "pheromones" / "markers.db")
    store.upsert_marker(_marker("m1", intensity=1.0), agent_id="seed")
    env = Environment(store=store, config=config)

    registry = ToolRegistry()
    registry.register(PendingTool())
    agents = [StigmergicAgent(agent_id="agent-1", tool_registry=registry, config=config)]

    Orchestrator(environment=env, agents=agents, config=config).run_sync()
    assert store.read_count("m1") == 1
