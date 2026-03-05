"""Unit tests for TravelPlanner adapter contract implementation."""

from __future__ import annotations

import copy
from pathlib import Path

from adapters.travelplanner.adapter import TravelPlannerAdapter
from core.marker import StateMachine
from core.tool_registry import ToolRegistry
from travelplanner_data import sample_query_rows, write_sample_database


def _build_config(tmp_path: Path, config_dict: dict) -> dict:
    config = copy.deepcopy(config_dict)
    config["travelplanner"] = {
        "database_path": str(write_sample_database(tmp_path / "database")),
        "dataset_split": "validation",
        "query_rows": sample_query_rows(),
        "default_query_idx": 0,
    }
    return config


def test_create_workspace_uses_configured_database(tmp_path: Path, config_dict: dict) -> None:
    config = _build_config(tmp_path, config_dict)
    adapter = TravelPlannerAdapter(config=config)
    workspace = adapter.create_workspace(config)

    assert str(workspace.database_root).endswith("database")
    assert "flights" in workspace.list_targets()


def test_create_objective_with_query_idx(tmp_path: Path, config_dict: dict) -> None:
    config = _build_config(tmp_path, config_dict)
    adapter = TravelPlannerAdapter(config=config)
    adapter.create_workspace(config)

    objective = adapter.create_objective({"objective": "ignored", "query_idx": 1}, config)
    assert objective.payload["query_idx"] == 1
    assert objective.payload["org"] == "Washington"


def test_create_objective_parses_query_number_from_text(tmp_path: Path, config_dict: dict) -> None:
    config = _build_config(tmp_path, config_dict)
    adapter = TravelPlannerAdapter(config=config)
    adapter.create_workspace(config)

    objective = adapter.create_objective({"objective": "Query 1"}, config)
    assert objective.payload["query_idx"] == 1


def test_register_tools_exposes_domain_and_reasoning_actions(
    tmp_path: Path,
    config_dict: dict,
) -> None:
    config = _build_config(tmp_path, config_dict)
    adapter = TravelPlannerAdapter(config=config)
    registry = ToolRegistry()

    adapter.register_tools(registry)
    assert set(registry.action_types()) == {
        "search_flights",
        "search_hotels",
        "search_restaurants",
        "search_attractions",
        "plan_itinerary",
        "validate_constraints",
        "think",
        "decompose",
    }


def test_define_state_machine_returns_custom_machine(
    tmp_path: Path,
    config_dict: dict,
) -> None:
    config = _build_config(tmp_path, config_dict)
    adapter = TravelPlannerAdapter(config=config)

    machine = adapter.define_state_machine()
    assert isinstance(machine, StateMachine)
    assert machine.can_transition("pending", "searching") is True
    assert machine.can_transition("validating", "planning") is True


def test_initial_markers_follow_dag_pattern(tmp_path: Path, config_dict: dict) -> None:
    config = _build_config(tmp_path, config_dict)
    adapter = TravelPlannerAdapter(config=config)
    adapter.create_workspace(config)
    objective = adapter.create_objective({"objective": "Query 0"}, config)

    markers = adapter.initial_markers(objective=objective, agent_id="seed")
    ids = {marker.id for marker in markers}

    plan_marker = next(marker for marker in markers if marker.id.endswith("::plan_itinerary"))
    validate_marker = next(marker for marker in markers if marker.id.endswith("::validate_constraints"))
    finalize_marker = next(marker for marker in markers if marker.id.endswith("::finalize"))

    assert len(markers) == 6
    assert set(plan_marker.payload.get("depends_on", [])) <= ids
    assert validate_marker.payload.get("depends_on") == [plan_marker.id]
    assert finalize_marker.payload.get("depends_on") == [validate_marker.id]


def test_evaluate_run_returns_travelplanner_metrics(tmp_path: Path, config_dict: dict) -> None:
    config = _build_config(tmp_path, config_dict)
    adapter = TravelPlannerAdapter(config=config)
    workspace = adapter.create_workspace(config)
    query = workspace.get_query(0)

    metrics = adapter.evaluate_run(
        {
            "markers": [
                {
                    "id": "final",
                    "marker_type": "task",
                    "target": "final",
                    "intensity": 0.1,
                    "state": "terminal",
                    "payload": {"query_data": query, "final_plan": []},
                    "created_by": "seed",
                    "created_at": "2026-03-05T00:00:00+00:00",
                    "updated_by": "seed",
                    "updated_at": "2026-03-05T00:00:00+00:00",
                    "history": ["created"],
                }
            ]
        }
    )

    assert "final_pass_rate" in metrics
    assert "delivery_rate" in metrics


def test_default_query_idx_used_when_objective_not_parseable(
    tmp_path: Path,
    config_dict: dict,
) -> None:
    config = _build_config(tmp_path, config_dict)
    config["travelplanner"]["default_query_idx"] = 1
    adapter = TravelPlannerAdapter(config=config)
    adapter.create_workspace(config)

    objective = adapter.create_objective({"objective": "not-a-query"}, config)
    assert objective.payload["query_idx"] == 1
