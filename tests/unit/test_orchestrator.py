"""Unit tests for tick-based orchestrator."""

from __future__ import annotations

import copy
import json

from core.agent import StigmergicAgent
from core.environment import Environment
from core.marker import Marker, StateMachine
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


class LongRunningTool(Tool):
    """Tool that keeps work active to simulate stagnation with contention."""

    action_type = "stall"

    def is_eligible(self, marker: Marker) -> bool:
        return marker.state in {"pending", "active"}

    async def execute(self, *, agent_id, marker, environment, llm_client=None) -> ActionResult:
        updated = Marker.from_dict(marker.to_dict())
        updated.state = "active"
        return ActionResult(action_type=self.action_type, marker_updates=[updated])


class TerminalTool(Tool):
    """Tool that makes immediate terminal progress."""

    action_type = "finish"

    def is_eligible(self, marker: Marker) -> bool:
        return marker.state == "pending"

    async def execute(self, *, agent_id, marker, environment, llm_client=None) -> ActionResult:
        updated = Marker.from_dict(marker.to_dict())
        updated.state = "terminal"
        updated.intensity = 0.1
        return ActionResult(action_type=self.action_type, marker_updates=[updated])


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


def test_orchestrator_elastic_agent_pool_respects_min_max(tmp_path, config_dict: dict) -> None:
    config, env, agents = _build_runtime(
        tmp_path,
        config_dict,
        user_input={"item_count": 12, "target_count": 100},
    )
    config["agents"]["num_agents_mode"] = "elastic"
    config["agents"]["elastic"] = {
        "min_agents": 2,
        "max_agents": 5,
        "markers_per_agent": 1,
    }
    config["orchestrator"]["max_ticks"] = 2
    agents = agents[:2]

    result = Orchestrator(environment=env, agents=agents, config=config).run_sync()
    pool = result.emergence_summary["agent_pool"]

    assert pool["dynamic_agents_min"] >= 2
    assert pool["dynamic_agents_max"] <= 5
    assert pool["dynamic_agents_max"] > 2
    assert "action_switching_rate" in result.emergence_summary


def test_elastic_pool_counts_planning_markers_with_eligible_actions(
    tmp_path,
    config_dict: dict,
) -> None:
    config, env, agents = _build_runtime(tmp_path, config_dict)
    for marker in env.store.query_markers():
        updated = Marker.from_dict(marker.to_dict())
        updated.state = "terminal"
        env.store.upsert_marker(updated, agent_id="seed")
    planning = Marker(
        id="migrationbench::local::patch::b1",
        marker_type="patch_hypothesis",
        target="patch::b1",
        intensity=1.0,
        state="planning",
        payload={"eligible_actions": ["run_build_validation"]},
        created_by="seed",
        created_at="2026-01-01T00:00:00+00:00",
        updated_by="seed",
        updated_at="2026-01-01T00:00:00+00:00",
        history=["created"],
    )
    env.store.upsert_marker(planning, agent_id="seed")
    orchestrator = Orchestrator(environment=env, agents=agents, config=config)

    assert orchestrator._unblocked_marker_count(env.snapshot(tick=0)) == 1


def test_orchestrator_tick_emergence_payload_present(tmp_path, config_dict: dict) -> None:
    config, env, agents = _build_runtime(tmp_path, config_dict)
    config["orchestrator"]["max_ticks"] = 1

    result = Orchestrator(environment=env, agents=agents, config=config).run_sync()
    assert result.tick_rows
    tick_emergence = result.tick_rows[0].emergence
    assert "lock_contention_rate" in tick_emergence
    assert "parallel_utilization" in tick_emergence


def test_orchestrator_activates_recovery_controller_on_stagnation(
    tmp_path,
    config_dict: dict,
) -> None:
    config = copy.deepcopy(config_dict)
    config["agents"]["selection_temperature"] = 0.0
    config["orchestrator"]["parallel"] = True
    config["orchestrator"]["max_ticks"] = 4
    config["orchestrator"]["idle_cycles_to_stop"] = 99
    config["orchestrator"]["recovery_controller"] = {
        "enabled": True,
        "stagnation_ticks": 1,
        "contention_threshold": 0.5,
        "recovery_cooldown_ticks": 0,
        "temperature_boost": 0.1,
        "temperature_boost_duration": 2,
        "inhibition_relief": 0.2,
        "dynamic_idle": {
            "enabled": False,
            "node_per_idle_cycle": 6,
            "max_extra_idle_cycles": 8,
        },
    }

    store = MarkerStore(db_path=tmp_path / "pheromones" / "markers.db")
    marker = Marker(
        id="stalled",
        marker_type="task",
        target="stalled",
        intensity=1.0,
        state="pending",
        payload={"eligible_actions": ["stall"]},
        created_by="seed",
        created_at="2026-04-18T10:00:00+00:00",
        updated_by="seed",
        updated_at="2026-04-18T10:00:00+00:00",
        history=["created"],
    )
    store.upsert_marker(marker, agent_id="seed")

    env = Environment(
        store=store,
        config=config,
        state_machine=StateMachine(
            transitions={
                "pending": {"terminal"},
                "terminal": {"terminal"},
                "skipped": {"skipped"},
                "escalated": {"escalated"},
            }
        ),
    )
    registry = ToolRegistry()
    registry.register(LongRunningTool())
    agents = [
        StigmergicAgent(agent_id=f"agent-{idx}", tool_registry=registry, config=config)
        for idx in range(3)
    ]

    result = Orchestrator(environment=env, agents=agents, config=config).run_sync()

    assert any(
        bool(row.control.get("recovery", {}).get("active", False))
        for row in result.tick_rows[1:]
    )

    audit_actions = []
    with env.store.audit_log.path.open("r", encoding="utf-8") as handle:
        for line in handle:
            audit_actions.append(json.loads(line).get("action"))
    assert "recovery_activation" in audit_actions


def test_orchestrator_skips_recovery_when_terminal_progress_is_recent(
    tmp_path,
    config_dict: dict,
) -> None:
    config = copy.deepcopy(config_dict)
    config["agents"]["selection_temperature"] = 0.0
    config["orchestrator"]["parallel"] = False
    config["orchestrator"]["max_ticks"] = 4
    config["orchestrator"]["idle_cycles_to_stop"] = 99
    config["orchestrator"]["recovery_controller"] = {
        "enabled": True,
        "stagnation_ticks": 2,
        "contention_threshold": 0.0,
        "recovery_cooldown_ticks": 0,
        "temperature_boost": 0.1,
        "temperature_boost_duration": 2,
        "inhibition_relief": 0.2,
        "dynamic_idle": {
            "enabled": False,
            "node_per_idle_cycle": 6,
            "max_extra_idle_cycles": 8,
        },
    }

    store = MarkerStore(db_path=tmp_path / "pheromones" / "markers.db")
    for marker_id in ("a", "b"):
        store.upsert_marker(
            Marker(
                id=marker_id,
                marker_type="task",
                target=marker_id,
                intensity=1.0,
                state="pending",
                payload={"eligible_actions": ["finish"]},
                created_by="seed",
                created_at="2026-04-18T10:00:00+00:00",
                updated_by="seed",
                updated_at="2026-04-18T10:00:00+00:00",
                history=["created"],
            ),
            agent_id="seed",
        )

    env = Environment(
        store=store,
        config=config,
        state_machine=StateMachine(
            transitions={
                "pending": {"terminal"},
                "terminal": {"terminal"},
                "skipped": {"skipped"},
                "escalated": {"escalated"},
            }
        ),
    )
    registry = ToolRegistry()
    registry.register(TerminalTool())
    agents = [StigmergicAgent(agent_id="agent-1", tool_registry=registry, config=config)]

    result = Orchestrator(environment=env, agents=agents, config=config).run_sync()

    assert result.stop_reason == "all_terminal"
    assert not any(
        bool(row.control.get("recovery", {}).get("active", False))
        for row in result.tick_rows
    )
