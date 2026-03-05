"""Integration tests for TravelPlanner adapter end-to-end runtime."""

from __future__ import annotations

import copy
from types import SimpleNamespace

from adapters.travelplanner.adapter import TravelPlannerAdapter
from core.agent import StigmergicAgent
from core.environment import Environment
from core.marker_store import MarkerStore
from core.orchestrator import Orchestrator
from core.tool_registry import ToolRegistry
from travelplanner_data import sample_query_rows, write_sample_database


class FakeTravelLLM:
    """Deterministic fake planner output for integration tests."""

    def call(self, prompt: str, system: str | None = None) -> SimpleNamespace:
        content = (
            '{"plan":['
            '{"current_city":"from Washington to Myrtle Beach",'
            '"transportation":"Flight Number: F3792603, from Washington to Myrtle Beach",'
            '"breakfast":"-",'
            '"attraction":"SkyWheel Myrtle Beach, Myrtle Beach",'
            '"lunch":"-",'
            '"dinner":"-",'
            '"accommodation":"Private Room A, Myrtle Beach"},'
            '{"current_city":"Myrtle Beach",'
            '"transportation":"-",'
            '"breakfast":"Exotic India, Myrtle Beach",'
            '"attraction":"Broadway at the Beach, Myrtle Beach",'
            '"lunch":"Seafood Place, Myrtle Beach",'
            '"dinner":"Cafe Blue, Myrtle Beach",'
            '"accommodation":"Private Room A, Myrtle Beach"},'
            '{"current_city":"from Myrtle Beach to Washington",'
            '"transportation":"Flight Number: F3791200, from Myrtle Beach to Washington",'
            '"breakfast":"-",'
            '"attraction":"-",'
            '"lunch":"-",'
            '"dinner":"-",'
            '"accommodation":"-"}'
            ']}'
        )
        return SimpleNamespace(
            content=content,
            tokens_used=8,
            cost_usd=0.001,
            model="fake-travel-model",
            latency_ms=1,
            parsed=None,
        )

    def extract_code_block(self, text: str) -> str:
        return text


def _build_runtime(tmp_path, config_dict: dict):
    config = copy.deepcopy(config_dict)
    config["agents"]["num_agents"] = 3
    config["agents"]["selection_temperature"] = 0.0
    config["orchestrator"]["parallel"] = False
    config["orchestrator"]["max_ticks"] = 30
    config["orchestrator"]["idle_cycles_to_stop"] = 5
    config["travelplanner"] = {
        "database_path": str(write_sample_database(tmp_path / "database")),
        "dataset_split": "validation",
        "query_rows": sample_query_rows(),
        "default_query_idx": 0,
    }

    adapter = TravelPlannerAdapter(config=config)
    workspace = adapter.create_workspace(config)
    objective = adapter.create_objective({"objective": "Query 0"}, config)

    store = MarkerStore(db_path=tmp_path / "pheromones" / "markers.db")
    env = Environment(
        store=store,
        config=config,
        workspace=workspace,
        state_machine=adapter.define_state_machine(),
    )

    registry = ToolRegistry()
    adapter.register_tools(registry)
    for marker in adapter.initial_markers(objective=objective, agent_id="seed"):
        env.store.upsert_marker(marker=marker, agent_id="seed")

    agents = [
        StigmergicAgent(agent_id=f"agent-{index + 1}", tool_registry=registry, config=config)
        for index in range(int(config["agents"]["num_agents"]))
    ]

    return config, adapter, env, agents


def test_travelplanner_run_end_to_end_with_mock_llm(tmp_path, config_dict: dict) -> None:
    config, adapter, env, agents = _build_runtime(tmp_path, config_dict)

    result = Orchestrator(
        environment=env,
        agents=agents,
        config=config,
        llm_client=FakeTravelLLM(),
    ).run_sync()

    assert result.stop_reason in {"all_terminal", "max_ticks", "idle_cycles"}
    assert result.total_ticks >= 1

    final_marker = next(
        marker for marker in result.final_snapshot.markers if marker.id.endswith("::finalize")
    )
    assert final_marker.state == "terminal"

    evaluation = adapter.evaluate_run({"markers": result.final_snapshot.markers})
    assert "final_pass_rate" in evaluation


def test_travelplanner_dag_dependency_order(tmp_path, config_dict: dict) -> None:
    config, _, env, agents = _build_runtime(tmp_path, config_dict)
    result = Orchestrator(
        environment=env,
        agents=agents,
        config=config,
        llm_client=FakeTravelLLM(),
    ).run_sync()

    plan_marker = next(marker for marker in result.final_snapshot.markers if marker.id.endswith("::plan_itinerary"))
    validate_marker = next(marker for marker in result.final_snapshot.markers if marker.id.endswith("::validate_constraints"))

    assert isinstance(plan_marker.payload.get("depends_on"), list)
    assert validate_marker.payload.get("depends_on") == [plan_marker.id]


def test_travelplanner_emergence_metrics_present(tmp_path, config_dict: dict) -> None:
    config, _, env, agents = _build_runtime(tmp_path, config_dict)
    result = Orchestrator(
        environment=env,
        agents=agents,
        config=config,
        llm_client=FakeTravelLLM(),
    ).run_sync()

    assert "parallel_utilization" in result.emergence_summary
    assert "lock_contention_rate" in result.emergence_summary


def test_travelplanner_validate_retry_path_is_bounded(tmp_path, config_dict: dict) -> None:
    config, _, env, agents = _build_runtime(tmp_path, config_dict)

    class BadLLM(FakeTravelLLM):
        def call(self, prompt: str, system: str | None = None) -> SimpleNamespace:
            response = super().call(prompt, system)
            response.content = response.content.replace("Exotic India, Myrtle Beach", "Unknown, Myrtle Beach")
            return response

    result = Orchestrator(
        environment=env,
        agents=agents,
        config=config,
        llm_client=BadLLM(),
    ).run_sync()

    validate_marker = next(marker for marker in result.final_snapshot.markers if marker.id.endswith("::validate_constraints"))
    assert int(validate_marker.retry_count) <= 3


def test_travelplanner_metrics_payload_shape(tmp_path, config_dict: dict) -> None:
    config, adapter, env, agents = _build_runtime(tmp_path, config_dict)

    result = Orchestrator(
        environment=env,
        agents=agents,
        config=config,
        llm_client=FakeTravelLLM(),
    ).run_sync()
    metrics = adapter.evaluate_run({"markers": result.final_snapshot.markers})

    assert set(metrics.keys()) >= {
        "delivery_rate",
        "commonsense_micro",
        "commonsense_macro",
        "hard_constraint_micro",
        "hard_constraint_macro",
        "final_pass_rate",
    }
