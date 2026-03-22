"""Unit tests for TravelPlanner domain tools."""

from __future__ import annotations

import asyncio
import copy
from pathlib import Path

from core.environment import Environment
from core.marker import Marker
from core.marker_store import MarkerStore

from adapters.travelplanner.tools import (
    PlanDayTool,
    SearchFlightsTool,
    SearchGroundTransportTool,
    SearchHotelsTool,
    ValidateConstraintsTool,
)
from adapters.travelplanner.workspace import TravelPlannerWorkspace
from travelplanner_data import (
    sample_query_rows,
    sample_valid_plan,
    write_sample_database,
)


def _build_env(
    tmp_path: Path, config_dict: dict
) -> tuple[Environment, dict, TravelPlannerWorkspace]:
    config = copy.deepcopy(config_dict)
    database_root = write_sample_database(tmp_path / "database")
    workspace = TravelPlannerWorkspace(
        database_root=database_root,
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


def test_search_flights_is_eligible_for_pending_marker() -> None:
    tool = SearchFlightsTool(
        config={"markers": {"intensity_step_tool": 0.05, "intensity_floor": 0.1}}
    )
    marker = _marker(
        "m",
        "pending",
        {
            "origin": "Washington",
            "dest": "Myrtle Beach",
            "date": "2022-03-13",
            "eligible_actions": ["search_flights"],
        },
    )
    assert tool.is_eligible(marker) is True


def test_search_flights_execute_progresses_state(
    tmp_path: Path, config_dict: dict
) -> None:
    env, config, _ = _build_env(tmp_path, config_dict)
    tool = SearchFlightsTool(config=config)

    marker = _marker(
        "search-flights",
        "pending",
        {
            "origin": "Washington",
            "dest": "Myrtle Beach",
            "date": "2022-03-13",
            "eligible_actions": ["search_flights"],
        },
    )
    first = asyncio.run(tool.execute(agent_id="a", marker=marker, environment=env))
    assert first.marker_updates[0].state == "searching"
    assert first.marker_updates[0].payload["result_count"] >= 1

    second = asyncio.run(
        tool.execute(agent_id="a", marker=first.marker_updates[0], environment=env)
    )
    assert second.marker_updates[0].state == "terminal"


def test_search_hotels_missing_city_fails(tmp_path: Path, config_dict: dict) -> None:
    env, config, _ = _build_env(tmp_path, config_dict)
    tool = SearchHotelsTool(config=config)
    marker = _marker(
        "search-hotels", "pending", {"eligible_actions": ["search_hotels"]}
    )

    result = asyncio.run(tool.execute(agent_id="a", marker=marker, environment=env))
    assert result.metadata.get("failed") is True


def test_search_ground_transport_execute_progresses_state(
    tmp_path: Path, config_dict: dict
) -> None:
    env, config, _ = _build_env(tmp_path, config_dict)
    tool = SearchGroundTransportTool(config=config)

    marker = _marker(
        "search-ground",
        "pending",
        {
            "origin": "Washington",
            "dest": "Myrtle Beach",
            "result_key": "search_ground_transport_outbound",
            "eligible_actions": ["search_ground_transport"],
        },
    )

    first = asyncio.run(tool.execute(agent_id="a", marker=marker, environment=env))
    assert first.marker_updates[0].state == "searching"
    assert first.marker_updates[0].payload["result_count"] == 2
    assert first.marker_updates[0].payload["result_key"] == "search_ground_transport_outbound"


def test_plan_tool_without_llm_keeps_empty_plan(
    tmp_path: Path, config_dict: dict
) -> None:
    env, config, workspace = _build_env(tmp_path, config_dict)
    query = workspace.get_query(0)
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

    first = asyncio.run(tool.execute(agent_id="a", marker=marker, environment=env))
    assert first.marker_updates[0].state == "planning"
    assert first.marker_updates[0].payload.get("plan", []) == []
    assert first.metadata.get("failed") is True

    second = asyncio.run(
        tool.execute(agent_id="a", marker=first.marker_updates[0], environment=env)
    )
    assert second.marker_updates[0].state == "planning"
    assert second.metadata.get("failed") is True

    # 3rd attempt (max_planning_attempts=3 default) -> terminal
    third = asyncio.run(
        tool.execute(agent_id="a", marker=second.marker_updates[0], environment=env)
    )
    assert third.marker_updates[0].state == "terminal"
    assert third.metadata.get("failed") is True
    assert third.metadata.get("reason") == "empty_plan_after_max_attempts"


def test_plan_prompt_omits_reference_information_and_compacts_payload(
    tmp_path: Path, config_dict: dict
) -> None:
    _, config, workspace = _build_env(tmp_path, config_dict)
    query = workspace.get_query(0)
    tool = PlanDayTool(config=config)

    search_payload = {
        "search_hotels": [
            {
                "NAME": "Private Room A",
                "price": 120.0,
                "room type": "Private room",
                "house_rules": "No smoking",
                "minimum nights": 1,
                "maximum occupancy": 2,
                "review rate number": 4.0,
                "city": "Myrtle Beach",
                "ignored_field": "drop me",
            }
        ],
        "search_restaurants": [
            {
                "Name": "Exotic India",
                "Average Cost": 81,
                "Cuisines": "Indian, BBQ, Fast Food",
                "Aggregate Rating": 4.1,
                "City": "Myrtle Beach",
                "ignored_field": "drop me too",
            }
        ],
    }

    prompt = tool._build_prompt(
        query_data=query,
        search_payload=search_payload,
        validation_feedback=[],
    )

    assert "reference_information" not in prompt
    assert "ignored_field" not in prompt
    assert '"search_restaurants"' in prompt


def test_plan_prompt_includes_routing_data_with_canonical_transport_strings(
    tmp_path: Path, config_dict: dict
) -> None:
    _, config, workspace = _build_env(tmp_path, config_dict)
    query = workspace.get_query(0)
    tool = PlanDayTool(config=config)

    prompt = tool._build_prompt(
        query_data=query,
        search_payload={
            "search_flights_outbound": workspace.search_flights(
                "Washington", "Myrtle Beach", "2022-03-13"
            ).to_dict(orient="records"),
            "search_ground_transport_outbound": workspace.search_ground_transport(
                "Washington", "Myrtle Beach"
            ).to_dict(orient="records"),
        },
        validation_feedback=[],
    )

    assert "RoutingData" in prompt
    assert "Flight Number: F3792603, from Washington to Myrtle Beach" in prompt
    assert "Self-driving, from Washington to Myrtle Beach" in prompt


def test_collect_search_payloads_injects_restaurants_from_workspace(
    tmp_path: Path, config_dict: dict
) -> None:
    env, config, workspace = _build_env(tmp_path, config_dict)
    query = workspace.get_query(0)
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

    assert "search_restaurants" in payload
    assert len(payload["search_restaurants"]) >= 1
    assert "search_flights_outbound" in payload
    assert "search_flights_return" in payload
    assert "search_ground_transport_outbound" in payload
    assert "search_ground_transport_return" in payload


def test_compact_search_payload_filters_hotels_that_cannot_cover_stay(
    tmp_path: Path, config_dict: dict
) -> None:
    _, config, workspace = _build_env(tmp_path, config_dict)
    query = workspace.get_query(0)
    tool = PlanDayTool(config=config)

    compact = tool._compact_search_payload(
        {
            "search_hotels": [
                {
                    "NAME": "Too Long Stay",
                    "price": 80.0,
                    "room type": "Private room",
                    "house_rules": "No parties",
                    "minimum nights": 5,
                    "maximum occupancy": 2,
                    "review rate number": 4.0,
                    "city": "Myrtle Beach",
                },
                {
                    "NAME": "Valid Stay",
                    "price": 100.0,
                    "room type": "Private room",
                    "house_rules": "No parties",
                    "minimum nights": 1,
                    "maximum occupancy": 2,
                    "review rate number": 4.5,
                    "city": "Myrtle Beach",
                },
            ]
        },
        query_data=query,
    )

    assert compact["search_hotels"] == [
        {
            "NAME": "Valid Stay",
            "price": 100.0,
            "room type": "Private room",
            "house_rules": "No parties",
            "minimum nights": 1,
            "maximum occupancy": 2,
            "review rate number": 4.5,
            "city": "Myrtle Beach",
        }
    ]


def test_plan_tool_normalizes_canonical_fields_from_search_payload(
    tmp_path: Path, config_dict: dict
) -> None:
    _, config, workspace = _build_env(tmp_path, config_dict)
    query = workspace.get_query(0)
    tool = PlanDayTool(config=config)

    normalized = tool._normalize_itinerary(
        itinerary=[
            {
                "current_city": "Myrtle Beach",
                "transportation": "Flight F3792603 from Washington",
                "breakfast": "Exotic India",
                "attraction": "SkyWheel Myrtle Beach",
                "lunch": "Seafood Place",
                "dinner": "Cafe Blue",
                "accommodation": "Private Room A",
            },
            {
                "current_city": "Myrtle Beach",
                "transportation": "Local transport",
                "breakfast": "BBQ Dock",
                "attraction": "Broadway at the Beach",
                "lunch": "Pasta Corner",
                "dinner": "Seafood Place",
                "accommodation": "Private Room A",
            },
        ],
        query_data=query,
        search_payload={
            "search_flights_outbound": workspace.search_flights(
                "Washington", "Myrtle Beach", "2022-03-13"
            ).to_dict(orient="records"),
            "search_restaurants": workspace.search_restaurants(
                "Myrtle Beach"
            ).to_dict(orient="records"),
            "search_attractions": workspace.search_attractions(
                "Myrtle Beach"
            ).to_dict(orient="records"),
            "search_hotels": workspace.search_hotels("Myrtle Beach").to_dict(
                orient="records"
            ),
        },
    )

    assert normalized[0]["current_city"] == "from Washington to Myrtle Beach"
    assert normalized[0]["transportation"] == "Flight Number: F3792603, from Washington to Myrtle Beach"
    assert normalized[0]["breakfast"] == "Exotic India, Myrtle Beach"
    assert normalized[0]["attraction"] == "SkyWheel Myrtle Beach, Myrtle Beach"
    assert normalized[0]["accommodation"] == "Private Room A, Myrtle Beach"
    assert normalized[1]["transportation"] == "-"


def test_validate_constraints_passes_on_valid_plan(
    tmp_path: Path, config_dict: dict
) -> None:
    env, config, workspace = _build_env(tmp_path, config_dict)
    query = workspace.get_query(0)
    plan_marker = _marker(
        "plan",
        "terminal",
        {
            "query_data": query,
            "plan": sample_valid_plan(),
        },
    )
    env.store.upsert_marker(plan_marker, agent_id="seed")

    validate_marker = _marker(
        "validate",
        "pending",
        {
            "depends_on": ["plan"],
            "eligible_actions": ["validate_constraints"],
        },
    )

    tool = ValidateConstraintsTool(config=config, max_retries=2)
    result = asyncio.run(
        tool.execute(agent_id="a", marker=validate_marker, environment=env)
    )

    assert result.marker_updates[0].state == "terminal"
    assert result.metadata.get("final_pass") is True


def test_validate_constraints_triggers_replan_on_failure(
    tmp_path: Path, config_dict: dict
) -> None:
    env, config, workspace = _build_env(tmp_path, config_dict)
    query = workspace.get_query(0)
    bad_plan = sample_valid_plan()
    bad_plan[0]["breakfast"] = "Unknown, Myrtle Beach"

    plan_marker = _marker(
        "plan",
        "terminal",
        {
            "query_data": query,
            "plan": bad_plan,
        },
    )
    env.store.upsert_marker(plan_marker, agent_id="seed")

    validate_marker = _marker(
        "validate",
        "pending",
        {
            "depends_on": ["plan"],
            "eligible_actions": ["validate_constraints"],
        },
    )

    tool = ValidateConstraintsTool(config=config, max_retries=2)
    result = asyncio.run(
        tool.execute(agent_id="a", marker=validate_marker, environment=env)
    )

    assert result.metadata.get("replan") is True
    assert any(
        update.id == "plan" and update.state == "planning"
        for update in result.marker_updates
    )
    plan_update = next(update for update in result.marker_updates if update.id == "plan")
    feedback = plan_update.payload.get("validation_feedback", [])
    assert any("invalid in the sandbox" in item for item in feedback)


def test_validate_constraints_retry_bound_to_terminal(
    tmp_path: Path, config_dict: dict
) -> None:
    env, config, workspace = _build_env(tmp_path, config_dict)
    query = workspace.get_query(0)
    bad_plan = sample_valid_plan()
    bad_plan[0]["breakfast"] = "Unknown, Myrtle Beach"

    plan_marker = _marker("plan", "terminal", {"query_data": query, "plan": bad_plan})
    env.store.upsert_marker(plan_marker, agent_id="seed")

    tool = ValidateConstraintsTool(config=config, max_retries=1)

    marker = _marker(
        "validate",
        "pending",
        {"depends_on": ["plan"], "eligible_actions": ["validate_constraints"]},
    )
    first = asyncio.run(tool.execute(agent_id="a", marker=marker, environment=env))
    retry_marker = next(
        update for update in first.marker_updates if update.id == "validate"
    )

    plan_again = next(update for update in first.marker_updates if update.id == "plan")
    plan_again.state = "terminal"
    env.store.upsert_marker(plan_again, agent_id="seed")

    second = asyncio.run(
        tool.execute(agent_id="a", marker=retry_marker, environment=env)
    )
    final_marker = next(
        update for update in second.marker_updates if update.id == "validate"
    )
    assert final_marker.state == "terminal"
    assert second.metadata.get("replan") is False


def test_finalize_stage_copies_evaluation(tmp_path: Path, config_dict: dict) -> None:
    env, config, workspace = _build_env(tmp_path, config_dict)
    query = workspace.get_query(0)
    validate_marker = _marker(
        "validate",
        "terminal",
        {
            "query_data": query,
            "plan": sample_valid_plan(),
            "evaluation": {"final_pass": True},
        },
    )
    env.store.upsert_marker(validate_marker, agent_id="seed")

    finalize = _marker(
        "finalize",
        "pending",
        {
            "stage": "finalize",
            "depends_on": ["validate"],
            "eligible_actions": ["validate_constraints"],
        },
    )

    tool = ValidateConstraintsTool(config=config, max_retries=2)
    result = asyncio.run(tool.execute(agent_id="a", marker=finalize, environment=env))
    update = result.marker_updates[0]

    assert update.state == "terminal"
    assert update.payload["final_pass"] is True
    assert isinstance(update.payload.get("final_plan"), list)
