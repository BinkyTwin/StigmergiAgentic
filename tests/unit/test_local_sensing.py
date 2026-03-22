"""Unit tests for agent-local sensing and affinity profiling."""

from __future__ import annotations

import asyncio
import copy
import random
from typing import Any

from core.agent import AgentAffinityProfile, StigmergicAgent
from core.environment import Environment
from core.marker import Marker
from core.marker_store import MarkerStore
from core.tool_registry import ActionResult, Tool, ToolRegistry


class PendingTool(Tool):
    """Minimal tool eligible on pending markers."""

    action_type = "work"

    def is_eligible(self, marker: Marker) -> bool:
        return marker.state == "pending"

    async def execute(
        self,
        *,
        agent_id: str,
        marker: Marker,
        environment: Any,
        llm_client: Any | None = None,
    ) -> ActionResult:
        updated = Marker.from_dict(marker.to_dict())
        updated.state = "active"
        return ActionResult(action_type=self.action_type, marker_updates=[updated])


def _make_marker(
    marker_id: str,
    *,
    target: str,
    intensity: float = 1.0,
    marker_type: str = "task",
    updated_at: str = "2026-03-04T12:00:00+00:00",
) -> Marker:
    return Marker(
        id=marker_id,
        marker_type=marker_type,
        target=target,
        intensity=intensity,
        state="pending",
        payload={},
        created_by="seed",
        created_at=updated_at,
        updated_by="seed",
        updated_at=updated_at,
        last_active_at=updated_at,
        history=["created"],
    )


def _build_environment(tmp_path, config: dict[str, Any]) -> Environment:
    store = MarkerStore(db_path=tmp_path / "pheromones" / "markers.db")
    return Environment(store=store, config=config)


def _build_agent(config: dict[str, Any]) -> StigmergicAgent:
    registry = ToolRegistry()
    registry.register(PendingTool())
    return StigmergicAgent(
        agent_id="agent-1",
        tool_registry=registry,
        config=config,
        rng=random.Random(7),
    )


def test_affinity_profile_cold_start_is_neutral() -> None:
    profile = AgentAffinityProfile(type_counts={}, target_keywords={})
    assert profile.type_affinity("task") == 0.5
    assert profile.semantic_affinity("travel planner") == 0.5
    assert profile.combined_affinity("task", "travel planner") == 0.5


def test_local_sensing_disabled_preserves_highest_intensity_choice(
    tmp_path,
    config_dict: dict,
) -> None:
    config = copy.deepcopy(config_dict)
    agent = _build_agent(config)
    env = _build_environment(tmp_path, config)
    env.store.upsert_marker(_make_marker("low", target="low.py", intensity=0.2), "seed")
    env.store.upsert_marker(_make_marker("high", target="high.py", intensity=0.9), "seed")

    decision = asyncio.run(agent.perceive_and_decide(env.snapshot(tick=0)))
    assert decision is not None
    assert decision.marker_id == "high"


def test_local_sensing_prefers_affine_marker_when_enabled(
    tmp_path,
    config_dict: dict,
) -> None:
    config = copy.deepcopy(config_dict)
    config["agents"]["local_sensing"]["enabled"] = True
    config["agents"]["local_sensing"]["max_candidates"] = 1
    config["agents"]["local_sensing"]["affinity_exploration_rate"] = 0.0

    agent = _build_agent(config)
    agent.affinity.record_action("task", "hotel paris booking")
    agent.affinity.record_action("task", "hotel paris center")

    env = _build_environment(tmp_path, config)
    env.store.upsert_marker(
        _make_marker("flight", target="flight tokyo itinerary", intensity=0.95),
        "seed",
    )
    env.store.upsert_marker(
        _make_marker("hotel", target="hotel paris booking", intensity=0.6),
        "seed",
    )

    candidates = agent._candidate_markers(env.snapshot(tick=0))
    assert [marker.id for marker in candidates] == ["hotel"]


def test_local_sensing_respects_intensity_threshold(
    tmp_path,
    config_dict: dict,
) -> None:
    config = copy.deepcopy(config_dict)
    config["agents"]["local_sensing"]["enabled"] = True
    config["agents"]["local_sensing"]["intensity_threshold"] = 0.5
    config["agents"]["local_sensing"]["affinity_exploration_rate"] = 0.0

    agent = _build_agent(config)
    env = _build_environment(tmp_path, config)
    env.store.upsert_marker(_make_marker("low", target="low.py", intensity=0.3), "seed")
    env.store.upsert_marker(_make_marker("high", target="high.py", intensity=0.8), "seed")

    candidates = agent._candidate_markers(env.snapshot(tick=0))
    assert [marker.id for marker in candidates] == ["high"]


def test_local_sensing_exploration_rate_one_keeps_all_candidates(
    tmp_path,
    config_dict: dict,
) -> None:
    config = copy.deepcopy(config_dict)
    config["agents"]["local_sensing"]["enabled"] = True
    config["agents"]["local_sensing"]["max_candidates"] = 1
    config["agents"]["local_sensing"]["affinity_exploration_rate"] = 1.0

    agent = _build_agent(config)
    agent.affinity.record_action("task", "hotel paris booking")

    env = _build_environment(tmp_path, config)
    env.store.upsert_marker(_make_marker("a", target="hotel paris booking"), "seed")
    env.store.upsert_marker(_make_marker("b", target="flight rome"), "seed")

    candidates = agent._candidate_markers(env.snapshot(tick=0))
    assert {marker.id for marker in candidates} == {"a", "b"}
