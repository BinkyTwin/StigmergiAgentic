"""Unit tests for TravelPlanner marker shaping rules."""

from __future__ import annotations

import asyncio
import copy
from pathlib import Path

from core.environment import Environment
from core.marker import Marker
from core.marker_store import MarkerStore

from adapters.travelplanner.tools import (
    PlanDayTool,
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


def test_validate_shaping_on_violation(tmp_path: Path, config_dict: dict) -> None:
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

    validate_update = next(update for update in result.marker_updates if update.id == "validate")
    plan_update = next(update for update in result.marker_updates if update.id == "plan")

    assert validate_update.intensity == 0.9
    assert validate_update.inhibition == 0.0
    assert plan_update.inhibition == 0.3
    assert result.metadata["replan"] is True


def test_search_shaping_empty_results(tmp_path: Path, config_dict: dict) -> None:
    env, config, _ = _build_env(tmp_path, config_dict)
    tool = SearchHotelsTool(config=config)
    marker = _marker(
        "search-hotels",
        "pending",
        {
            "city": "Atlantis",
            "eligible_actions": ["search_hotels"],
        },
    )

    result = asyncio.run(tool.execute(agent_id="a", marker=marker, environment=env))
    update = result.marker_updates[0]

    assert update.payload["result_count"] == 0
    assert update.intensity == 1.0


def test_plan_shaping_empty_plan(tmp_path: Path, config_dict: dict) -> None:
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

    result = asyncio.run(tool.execute(agent_id="a", marker=marker, environment=env))
    update = result.marker_updates[0]

    assert result.metadata["reason"] == "empty_plan_from_llm"
    assert update.payload["plan"] == []
    assert update.intensity == 0.8
