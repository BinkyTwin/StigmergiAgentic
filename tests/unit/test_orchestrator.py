"""Unit tests for tick-based orchestrator."""

from __future__ import annotations

import copy

from core.agent import StigmergicAgent
from core.environment import Environment
from core.marker import Marker
from core.marker_store import MarkerStore
from core.orchestrator import Orchestrator
from core.tool_registry import ActionResult, Tool, ToolRegistry
from mock_adapter import MockAdapter, seed_mock_markers


class BudgetBurnTool(Tool):
    """Tool that burns budget to trigger budget stop condition."""

    action_type = "burn"

    def is_eligible(self, marker: Marker) -> bool:
        return marker.state == "pending"

    async def execute(self, *, agent_id, marker, environment, llm_client=None) -> ActionResult:
        updated = Marker.from_dict(marker.to_dict())
        updated.state = "active"
        return ActionResult(
            action_type=self.action_type,
            marker_updates=[updated],
            consumed_tokens=100,
        )


def _build_runtime(tmp_path, config_dict: dict, user_input: dict | None = None):
    config = copy.deepcopy(config_dict)
    config["orchestrator"]["parallel"] = True

    adapter = MockAdapter()
    registry = ToolRegistry()
    adapter.register_tools(registry)

    store = MarkerStore(db_path=tmp_path / "pheromones" / "markers.db")
    objective = adapter.create_objective(user_input or {}, config)
    seed_mock_markers(adapter=adapter, objective=objective, store=store, agent_id="seed")

    env = Environment(
        store=store,
        config=config,
        workspace=adapter.create_workspace(config),
        state_machine=adapter.define_state_machine(),
    )

    agents = [
        StigmergicAgent(agent_id=f"agent-{idx}", tool_registry=registry, config=config)
        for idx in range(4)
    ]

    return config, env, agents


def test_orchestrator_runs_ten_ticks_and_releases_all_locks(tmp_path, config_dict: dict) -> None:
    config, env, agents = _build_runtime(
        tmp_path,
        config_dict,
        user_input={"item_count": 1, "target_count": 50},
    )
    config["orchestrator"]["max_ticks"] = 10
    config["orchestrator"]["idle_cycles_to_stop"] = 99

    orchestrator = Orchestrator(environment=env, agents=agents, config=config)
    result = orchestrator.run_sync()

    assert result.stop_reason == "max_ticks"
    assert result.total_ticks == 10

    marker = env.store.get_marker("mock-1")
    assert marker is not None
    assert marker.lock_owner is None


def test_orchestrator_resolves_lock_conflicts(tmp_path, config_dict: dict) -> None:
    config, env, agents = _build_runtime(
        tmp_path,
        config_dict,
        user_input={"item_count": 1, "target_count": 10},
    )
    config["orchestrator"]["max_ticks"] = 1

    result = Orchestrator(environment=env, agents=agents, config=config).run_sync()
    assert result.tick_rows[0].lock_conflicts >= 1


def test_orchestrator_calls_maintenance_decay_each_tick(tmp_path, config_dict: dict) -> None:
    config, env, _ = _build_runtime(
        tmp_path,
        config_dict,
        user_input={"item_count": 1, "target_count": 100},
    )
    config["orchestrator"]["max_ticks"] = 2
    config["orchestrator"]["idle_cycles_to_stop"] = 99

    result = Orchestrator(environment=env, agents=[], config=config).run_sync()
    marker = env.store.get_marker("mock-1")

    assert result.stop_reason == "max_ticks"
    assert marker is not None
    assert marker.intensity < 1.0


def test_orchestrator_stops_on_all_terminal(tmp_path, config_dict: dict) -> None:
    config, env, _ = _build_runtime(tmp_path, config_dict)
    for marker in env.store.query_markers():
        updated = Marker.from_dict(marker.to_dict())
        updated.state = "terminal"
        env.store.upsert_marker(updated, agent_id="seed")

    result = Orchestrator(environment=env, agents=[], config=config).run_sync()
    assert result.stop_reason == "all_terminal"


def test_orchestrator_stops_on_idle_cycles(tmp_path, config_dict: dict) -> None:
    config, env, _ = _build_runtime(tmp_path, config_dict)
    config["orchestrator"]["max_ticks"] = 10
    config["orchestrator"]["idle_cycles_to_stop"] = 2

    result = Orchestrator(environment=env, agents=[], config=config).run_sync()
    assert result.stop_reason == "idle_cycles"
    assert result.total_ticks == 2


def test_orchestrator_stops_on_max_ticks(tmp_path, config_dict: dict) -> None:
    config, env, _ = _build_runtime(tmp_path, config_dict)
    config["orchestrator"]["max_ticks"] = 3
    config["orchestrator"]["idle_cycles_to_stop"] = 99

    result = Orchestrator(environment=env, agents=[], config=config).run_sync()
    assert result.stop_reason == "max_ticks"
    assert result.total_ticks == 3


def test_orchestrator_stops_on_budget_exhausted(tmp_path, config_dict: dict) -> None:
    config = copy.deepcopy(config_dict)
    config["llm"]["max_tokens_total"] = 10
    config["orchestrator"]["max_ticks"] = 5

    store = MarkerStore(db_path=tmp_path / "pheromones" / "markers.db")
    seed = Marker(
        id="budget-1",
        marker_type="task",
        target="budget.py",
        intensity=1.0,
        state="pending",
        payload={},
        created_by="seed",
        created_at="2026-02-26T12:00:00+00:00",
        updated_by="seed",
        updated_at="2026-02-26T12:00:00+00:00",
        history=["created"],
    )
    store.upsert_marker(seed, agent_id="seed")

    env = Environment(store=store, config=config)
    registry = ToolRegistry()
    registry.register(BudgetBurnTool())
    agents = [StigmergicAgent(agent_id="agent-1", tool_registry=registry, config=config)]

    result = Orchestrator(environment=env, agents=agents, config=config).run_sync()
    assert result.stop_reason == "budget_exhausted"


def test_orchestrator_tick_rows_are_coherent(tmp_path, config_dict: dict) -> None:
    config, env, agents = _build_runtime(tmp_path, config_dict)
    config["orchestrator"]["max_ticks"] = 2

    result = Orchestrator(environment=env, agents=agents, config=config).run_sync()
    assert result.tick_rows

    first_row = result.tick_rows[0]
    assert first_row.tick == 0
    assert isinstance(first_row.decisions, dict)
    assert isinstance(first_row.actions_by_type, dict)
    assert 0.0 <= first_row.terminal_progress <= 1.0


def test_orchestrator_emergence_summary_is_computed(tmp_path, config_dict: dict) -> None:
    config, env, agents = _build_runtime(tmp_path, config_dict)
    config["orchestrator"]["max_ticks"] = 2

    result = Orchestrator(environment=env, agents=agents, config=config).run_sync()
    assert "colony_specialization" in result.emergence_summary
    assert "action_switching_rate" in result.emergence_summary


def test_orchestrator_tick_emergence_payload_present(tmp_path, config_dict: dict) -> None:
    config, env, agents = _build_runtime(tmp_path, config_dict)
    config["orchestrator"]["max_ticks"] = 1

    result = Orchestrator(environment=env, agents=agents, config=config).run_sync()
    assert result.tick_rows
    tick_emergence = result.tick_rows[0].emergence
    assert "lock_contention_rate" in tick_emergence
    assert "parallel_utilization" in tick_emergence
