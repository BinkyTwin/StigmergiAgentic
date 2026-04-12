"""Unit tests for multi-city TravelPlanner support."""

from __future__ import annotations

import copy
from pathlib import Path

from adapters.travelplanner.adapter import TravelPlannerAdapter
from adapters.travelplanner.tools import PlanDayTool
from adapters.travelplanner.workspace import TravelPlannerWorkspace
from core.environment import Environment
from core.marker import Marker
from core.marker_store import MarkerStore
from travelplanner_data import sample_query_rows, write_sample_database


def _build_config(tmp_path: Path, config_dict: dict) -> dict:
    config = copy.deepcopy(config_dict)
    config["travelplanner"] = {
        "database_path": str(write_sample_database(tmp_path / "database")),
        "dataset_split": "validation",
        "query_rows": sample_query_rows(),
        "default_query_idx": 2,
    }
    return config


def _build_env(
    tmp_path: Path, config_dict: dict
) -> tuple[Environment, dict, TravelPlannerWorkspace]:
    config = _build_config(tmp_path, config_dict)
    workspace = TravelPlannerWorkspace(
        database_root=config["travelplanner"]["database_path"],
        dataset_split="validation",
        query_rows=sample_query_rows(),
    )
    store = MarkerStore(db_path=tmp_path / "pheromones" / "markers.db")
    env = Environment(store=store, config=config, workspace=workspace)
    return env, config, workspace


def _marker(marker_id: str, state: str, payload: dict) -> Marker:
    return Marker(
        id=marker_id,
        marker_type="task",
        target=marker_id,
        intensity=1.0,
        state=state,
        payload=payload,
        created_by="seed",
        created_at="2026-03-05T00:00:00+00:00",
        updated_by="seed",
        updated_at="2026-03-05T00:00:00+00:00",
        history=["created"],
    )


def test_build_city_sequence_returns_requested_number_of_cities(
    tmp_path: Path,
    config_dict: dict,
) -> None:
    config = _build_config(tmp_path, config_dict)
    workspace = TravelPlannerWorkspace(
        database_root=config["travelplanner"]["database_path"],
        dataset_split="validation",
        query_rows=sample_query_rows(),
    )

    query = workspace.get_query(2)

    assert query["city_sequence"] == ["Myrtle Beach", "Charleston", "Greenville"]
    assert len(query["city_sequence"]) == query["visiting_city_number"]
    assert query["leg_dates"] == [
        "2022-03-13",
        "2022-03-15",
        "2022-03-17",
        "2022-03-19",
    ]


def test_initial_markers_create_per_city_search_tasks_and_linear_legs(
    tmp_path: Path,
    config_dict: dict,
) -> None:
    config = _build_config(tmp_path, config_dict)
    adapter = TravelPlannerAdapter(config=config)
    adapter.create_workspace(config)
    objective = adapter.create_objective({"objective": "Query 2"}, config)

    markers = adapter.initial_markers(objective=objective, agent_id="seed")
    assert len(markers) == 20

    city_markers = {
        city: [
            marker
            for marker in markers
            if marker.payload.get("city") == city
        ]
        for city in ["Myrtle Beach", "Charleston", "Greenville"]
    }
    assert all(len(city_markers[city]) == 3 for city in city_markers)

    outbound_ids = {
        marker.id
        for marker in markers
        if marker.id.endswith("::search_flights_outbound")
        or marker.id.endswith("::search_ground_transport_outbound")
    }
    leg1_ids = {
        marker.id
        for marker in markers
        if marker.id.endswith("::search_flights_leg_1")
        or marker.id.endswith("::search_ground_transport_leg_1")
    }
    leg2_ids = {
        marker.id
        for marker in markers
        if marker.id.endswith("::search_flights_leg_2")
        or marker.id.endswith("::search_ground_transport_leg_2")
    }

    assert all(set(marker.payload.get("depends_on", [])) == outbound_ids for marker in city_markers["Myrtle Beach"])
    assert all(set(marker.payload.get("depends_on", [])) == leg1_ids for marker in city_markers["Charleston"])
    assert all(set(marker.payload.get("depends_on", [])) == leg2_ids for marker in city_markers["Greenville"])

    first_leg = next(marker for marker in markers if marker.id.endswith("::search_flights_leg_1"))
    second_leg = next(marker for marker in markers if marker.id.endswith("::search_flights_leg_2"))
    return_leg = next(marker for marker in markers if marker.id.endswith("::search_flights_return"))

    assert set(first_leg.payload.get("depends_on", [])) == {marker.id for marker in city_markers["Myrtle Beach"]}
    assert set(second_leg.payload.get("depends_on", [])) == {marker.id for marker in city_markers["Charleston"]}
    assert set(return_leg.payload.get("depends_on", [])) == {marker.id for marker in city_markers["Greenville"]}

    plan_marker = next(marker for marker in markers if marker.id.endswith("::plan_itinerary"))
    assert set(plan_marker.payload.get("depends_on", [])) == {
        marker.id
        for marker in markers
        if not marker.id.endswith("::plan_itinerary")
        and not marker.id.endswith("::validate_constraints")
        and not marker.id.endswith("::finalize")
    }


def test_plan_tool_collects_multi_city_payloads_and_mentions_order(
    tmp_path: Path,
    config_dict: dict,
) -> None:
    env, config, workspace = _build_env(tmp_path, config_dict)
    query = workspace.get_query(2)
    tool = PlanDayTool(config=config)

    marker = _marker(
        "plan",
        "pending",
        {
            "query_data": query,
            "eligible_actions": ["plan_itinerary"],
            "depends_on": [],
        },
    )

    payload = tool._collect_search_payloads(marker=marker, environment=env)
    assert "search_hotels_myrtle_beach" in payload
    assert "search_hotels_charleston" in payload
    assert "search_hotels_greenville" in payload
    assert "search_flights_leg_1" in payload
    assert "search_flights_leg_2" in payload
    assert "search_flights_return" in payload

    prompt = tool._build_prompt(
        query_data=query,
        search_payload=payload,
        validation_feedback=[],
    )

    assert "Visit these cities in order: Myrtle Beach -> Charleston -> Greenville." in prompt
