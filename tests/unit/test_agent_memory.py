"""Unit tests for episodic memory in stigmergic agents."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from core.agent import AgentMemory, StigmergicAgent
from core.environment import Environment
from core.marker import Marker
from core.marker_store import MarkerStore
from core.tool_registry import ActionResult, Tool, ToolRegistry


class SimpleTool(Tool):
    """Minimal tool used for memory integration tests."""

    action_type = "think"

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
        return ActionResult(
            action_type=self.action_type,
            marker_updates=[updated],
            metadata={"quality_score": 0.9},
        )


def _make_marker(marker_id: str, **overrides: object) -> Marker:
    payload = {
        "id": marker_id,
        "marker_type": "task",
        "target": f"{marker_id}.py",
        "intensity": 1.0,
        "state": "pending",
        "payload": {"task": f"handle {marker_id}"},
        "created_by": "seed",
        "created_at": "2026-03-04T12:00:00+00:00",
        "updated_by": "seed",
        "updated_at": "2026-03-04T12:00:00+00:00",
        "history": ["created"],
    }
    payload.update(overrides)
    return Marker(**payload)


def _build_environment(tmp_path: Path, config_dict: dict[str, Any]) -> Environment:
    store = MarkerStore(db_path=tmp_path / "pheromones" / "markers.db")
    return Environment(store=store, config=config_dict)


def _build_agent(config_dict: dict[str, Any]) -> StigmergicAgent:
    registry = ToolRegistry()
    registry.register(SimpleTool())
    return StigmergicAgent(agent_id="agent-1", tool_registry=registry, config=config_dict)


def test_memory_remember_evicts_weakest_entry() -> None:
    memory = AgentMemory(capacity=2, decay_rate=0.1)
    memory.remember(context="ctx-a", action="a", result="ok", tick=0, relevance=0.9)
    memory.remember(context="ctx-b", action="b", result="ok", tick=1, relevance=0.2)
    memory.remember(context="ctx-c", action="c", result="ok", tick=2, relevance=0.8)

    contexts = [entry.context for entry in memory._entries]  # noqa: SLF001
    assert "ctx-b" not in contexts
    assert len(contexts) == 2


def test_memory_recall_uses_overlap_relevance_and_recency() -> None:
    memory = AgentMemory(capacity=5, decay_rate=0.0)
    memory.remember(
        context="read design doc architecture",
        action="file_read",
        result="ok",
        tick=0,
        relevance=0.9,
    )
    memory.remember(
        context="run benchmark tests",
        action="bash_exec",
        result="ok",
        tick=4,
        relevance=1.0,
    )
    memory.remember(
        context="read architecture notes",
        action="file_read",
        result="ok",
        tick=3,
        relevance=1.0,
    )

    recalled = memory.recall(
        current_context="read architecture",
        current_tick=5,
        top_k=2,
    )
    assert len(recalled) == 2
    assert recalled[0].action == "file_read"
    assert "architecture" in recalled[0].context


def test_memory_decay_all_reduces_relevance() -> None:
    memory = AgentMemory(capacity=2, decay_rate=0.2)
    entry = memory.remember(
        context="ctx",
        action="think",
        result="ok",
        tick=0,
        relevance=1.0,
    )

    memory.decay_all()
    stored = next(item for item in memory._entries if item.entry_id == entry.entry_id)  # noqa: SLF001
    assert stored.relevance == 0.8


def test_memory_reinforce_increases_relevance_with_cap() -> None:
    memory = AgentMemory(capacity=2, decay_rate=0.0)
    entry = memory.remember(
        context="ctx",
        action="think",
        result="ok",
        tick=0,
        relevance=0.95,
    )
    memory.reinforce(entry_id=entry.entry_id, reward=0.2)
    stored = next(item for item in memory._entries if item.entry_id == entry.entry_id)  # noqa: SLF001
    assert stored.relevance == 1.0


def test_agent_initializes_memory_from_config(config_dict: dict[str, Any]) -> None:
    config_dict["agents"]["memory_capacity"] = 7
    config_dict["agents"]["memory_decay_rate"] = 0.25
    agent = _build_agent(config_dict)

    assert agent.memory.capacity == 7
    assert agent.memory.decay_rate == 0.25


def test_agent_execute_remembers_outcome(tmp_path: Path, config_dict: dict[str, Any]) -> None:
    agent = _build_agent(config_dict)
    env = _build_environment(tmp_path, config_dict)
    env.store.upsert_marker(_make_marker("m1"), agent_id="seed")
    env.acquire_lock("m1", "agent-1", tick=0)

    decision = asyncio.run(agent.perceive_and_decide(env.snapshot(tick=0)))
    assert decision is not None
    asyncio.run(agent.execute(decision=decision, environment=env))

    assert len(agent.memory._entries) == 1  # noqa: SLF001
    assert agent.memory._entries[0].action == "think"  # noqa: SLF001


def test_agent_perceive_injects_recalled_memories(
    tmp_path: Path,
    config_dict: dict[str, Any],
) -> None:
    agent = _build_agent(config_dict)
    env = _build_environment(tmp_path, config_dict)
    env.store.upsert_marker(_make_marker("m2"), agent_id="seed")

    agent.memory.remember(
        context="think | task | m2.py",
        action="think",
        result="states:active",
        tick=0,
        relevance=1.0,
    )
    decision = asyncio.run(agent.perceive_and_decide(env.snapshot(tick=1)))
    assert decision is not None
    assert decision.recalled_memories
    assert decision.recalled_memories[0]["action"] == "think"


def test_agent_perceive_injects_lesson_markers(
    tmp_path: Path,
    config_dict: dict[str, Any],
) -> None:
    agent = _build_agent(config_dict)
    env = _build_environment(tmp_path, config_dict)
    env.store.upsert_marker(_make_marker("m3"), agent_id="seed")
    env.store.upsert_marker(
        _make_marker(
            "lesson::m3",
            marker_type="lesson",
            state="terminal",
            payload={
                "lesson": "Prefer explicit dependency ordering.",
                "source_marker": "m3",
                "source_agent": "agent-1",
            },
            target="m3.py",
            intensity=0.8,
        ),
        agent_id="seed",
    )

    decision = asyncio.run(agent.perceive_and_decide(env.snapshot(tick=1)))
    assert decision is not None
    assert decision.lesson_markers
    assert "dependency ordering" in decision.lesson_markers[0]["lesson"]
