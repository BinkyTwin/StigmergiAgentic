"""Unit tests for TravelPlanner evaluator constraints and aggregation."""

from __future__ import annotations

from pathlib import Path

from core.marker import Marker
from travelplanner_data import clone_plan, sample_query_rows, sample_valid_plan, write_sample_database

from adapters.travelplanner.evaluator import TravelPlannerEvaluator
from adapters.travelplanner.workspace import TravelPlannerWorkspace


def _build_evaluator(tmp_path: Path) -> tuple[TravelPlannerEvaluator, dict]:
    root = write_sample_database(tmp_path / "database")
    workspace = TravelPlannerWorkspace(
        database_root=root,
        dataset_split="validation",
        query_rows=sample_query_rows(),
    )
    query = workspace.get_query(0)
    return TravelPlannerEvaluator(workspace=workspace), query


def test_evaluate_plan_valid_case(tmp_path: Path) -> None:
    evaluator, query = _build_evaluator(tmp_path)
    plan = sample_valid_plan()

    result = evaluator.evaluate_plan(query_data=query, plan=plan)
    assert result.delivered is True
    assert result.commonsense["reasonable_city_route"] is True
    assert result.hard["valid_cost"] is True


def test_commonsense_restaurant_duplicates_fail(tmp_path: Path) -> None:
    evaluator, query = _build_evaluator(tmp_path)
    plan = clone_plan(sample_valid_plan())
    plan[1]["lunch"] = plan[1]["breakfast"]

    result = evaluator.evaluate_plan(query_data=query, plan=plan)
    assert result.commonsense["valid_restaurants"] is False


def test_commonsense_transport_conflict_fails(tmp_path: Path) -> None:
    evaluator, query = _build_evaluator(tmp_path)
    plan = clone_plan(sample_valid_plan())
    plan[1]["transportation"] = "Self-driving, from Myrtle Beach to Washington, cost: 34"

    result = evaluator.evaluate_plan(query_data=query, plan=plan)
    assert result.commonsense["valid_transportation"] is False


def test_hard_budget_fails_when_too_low(tmp_path: Path) -> None:
    evaluator, query = _build_evaluator(tmp_path)
    query_low = dict(query)
    query_low["budget"] = 10

    result = evaluator.evaluate_plan(query_data=query_low, plan=sample_valid_plan())
    assert result.hard["valid_cost"] is False


def test_hard_room_rule_detects_violation(tmp_path: Path) -> None:
    evaluator, query = _build_evaluator(tmp_path)
    query_hard = dict(query)
    query_hard["local_constraint"] = {
        "house rule": "parties",
        "cuisine": None,
        "room type": None,
        "transportation": None,
    }

    result = evaluator.evaluate_plan(query_data=query_hard, plan=sample_valid_plan())
    assert result.hard["valid_room_rule"] is False


def test_hard_room_type_detects_violation(tmp_path: Path) -> None:
    evaluator, query = _build_evaluator(tmp_path)
    query_hard = dict(query)
    query_hard["local_constraint"] = {
        "house rule": None,
        "cuisine": None,
        "room type": "shared room",
        "transportation": None,
    }

    result = evaluator.evaluate_plan(query_data=query_hard, plan=sample_valid_plan())
    assert result.hard["valid_room_type"] is False


def test_hard_cuisine_constraint(tmp_path: Path) -> None:
    evaluator, query = _build_evaluator(tmp_path)
    query_hard = dict(query)
    query_hard["local_constraint"] = {
        "house rule": None,
        "cuisine": ["Japanese"],
        "room type": None,
        "transportation": None,
    }

    result = evaluator.evaluate_plan(query_data=query_hard, plan=sample_valid_plan())
    assert result.hard["valid_cuisine"] is False


def test_not_absent_fails_missing_required_field(tmp_path: Path) -> None:
    evaluator, query = _build_evaluator(tmp_path)
    plan = clone_plan(sample_valid_plan())
    plan[1].pop("lunch")

    result = evaluator.evaluate_plan(query_data=query, plan=plan)
    assert result.commonsense["not_absent"] is False


def test_aggregate_metrics_include_final_pass_rate(tmp_path: Path) -> None:
    evaluator, query = _build_evaluator(tmp_path)
    good = evaluator.evaluate_plan(query_data=query, plan=sample_valid_plan())
    bad_plan = clone_plan(sample_valid_plan())
    bad_plan[0]["breakfast"] = "Unknown, Myrtle Beach"
    bad = evaluator.evaluate_plan(query_data=query, plan=bad_plan)

    aggregate = evaluator.aggregate([good, bad])
    assert aggregate["evaluated_queries"] == 2
    assert 0.0 <= aggregate["final_pass_rate"] <= 1.0


def test_evaluate_snapshot_reads_marker_payloads(tmp_path: Path) -> None:
    evaluator, query = _build_evaluator(tmp_path)
    marker = Marker(
        id="tp::finalize",
        marker_type="task",
        target="tp::finalize",
        intensity=0.5,
        state="terminal",
        payload={"query_data": query, "final_plan": sample_valid_plan()},
        created_by="seed",
        created_at="2026-03-05T00:00:00+00:00",
        updated_by="seed",
        updated_at="2026-03-05T00:00:00+00:00",
    )

    metrics = evaluator.evaluate_snapshot([marker])
    assert metrics["evaluated_queries"] == 1
    assert "delivery_rate" in metrics
