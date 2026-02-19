"""Tests for Sprint 4 Pareto analysis module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from metrics.pareto import (
    aggregate_by_baseline,
    build_export_payload,
    enforce_required_baselines,
    load_run_points,
    pareto_frontier,
    render_aggregated_plot,
    render_per_run_plot,
)


def test_load_run_points_and_aggregate_with_ci95(tmp_path: Path) -> None:
    data = [
        {
            "run_id": "a",
            "baseline": "stigmergic",
            "success_rate": 0.9,
            "total_tokens": 1000,
            "total_cost_usd": 0.10,
        },
        {
            "run_id": "b",
            "baseline": "stigmergic",
            "success_rate": 0.8,
            "total_tokens": 1200,
            "total_cost_usd": 0.15,
        },
        {
            "run_id": "c",
            "baseline": "single_agent",
            "success_rate": 0.7,
            "total_tokens": 600,
            "total_cost_usd": 0.05,
        },
    ]
    for row in data:
        path = tmp_path / f"run_{row['run_id']}_summary.json"
        path.write_text(json.dumps(row), encoding="utf-8")

    points = load_run_points(input_dir=tmp_path)
    assert len(points) == 3

    rows = aggregate_by_baseline(points=points, x_metric="total_tokens")
    assert len(rows) == 2
    stigmergic = next(item for item in rows if item["baseline"] == "stigmergic")
    single_agent = next(item for item in rows if item["baseline"] == "single_agent")

    assert stigmergic["x_mean"] == 1100.0
    assert stigmergic["success_mean"] == pytest.approx(0.85)
    assert stigmergic["x_ci95"] > 0.0
    assert stigmergic["success_ci95"] > 0.0

    assert single_agent["runs"] == 1
    assert single_agent["x_ci95"] == 0.0
    assert single_agent["success_ci95"] == 0.0


def test_pareto_frontier_filters_dominated_points() -> None:
    rows = [
        {"baseline": "A", "x_mean": 100.0, "success_mean": 0.5},
        {"baseline": "B", "x_mean": 120.0, "success_mean": 0.45},
        {"baseline": "C", "x_mean": 130.0, "success_mean": 0.6},
    ]
    frontier = pareto_frontier(rows)
    baseline_names = [row["baseline"] for row in frontier]
    assert baseline_names == ["A", "C"]


def test_enforce_required_baselines_raises_when_missing(tmp_path: Path) -> None:
    payload = {
        "run_id": "only_stig",
        "baseline": "stigmergic",
        "success_rate": 1.0,
        "total_tokens": 100,
        "total_cost_usd": 0.01,
    }
    (tmp_path / "run_only_stig_summary.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )
    points = load_run_points(tmp_path)

    with pytest.raises(ValueError, match="single_agent"):
        enforce_required_baselines(
            points=points,
            required_baselines=["stigmergic", "single_agent", "sequential"],
        )


def test_build_export_payload_contains_raw_points_and_aggregates(
    tmp_path: Path,
) -> None:
    data = [
        {
            "run_id": "a",
            "baseline": "stigmergic",
            "success_rate": 0.9,
            "total_tokens": 1000,
            "total_cost_usd": 0.1,
        },
        {
            "run_id": "b",
            "baseline": "single_agent",
            "success_rate": 0.8,
            "total_tokens": 900,
            "total_cost_usd": 0.2,
        },
    ]
    for row in data:
        path = tmp_path / f"run_{row['run_id']}_summary.json"
        path.write_text(json.dumps(row), encoding="utf-8")

    points = load_run_points(tmp_path)
    rows = aggregate_by_baseline(points=points, x_metric="total_tokens")
    frontier = pareto_frontier(rows)
    payload = build_export_payload(
        x_metric="total_tokens",
        plot_mode="per-run",
        points=points,
        rows=rows,
        frontier=frontier,
    )

    assert "raw_points" in payload
    assert "aggregates" in payload
    assert "rows" in payload
    assert payload["aggregates"] == payload["rows"]
    assert len(payload["raw_points"]) == 2
    assert "x_ci95" in payload["aggregates"][0]
    assert "success_ci95" in payload["aggregates"][0]


def test_render_plot_modes_write_output_files(tmp_path: Path) -> None:
    data = [
        {
            "run_id": "a",
            "baseline": "stigmergic",
            "success_rate": 0.9,
            "total_tokens": 1000,
            "total_cost_usd": 0.1,
        },
        {
            "run_id": "b",
            "baseline": "single_agent",
            "success_rate": 0.8,
            "total_tokens": 900,
            "total_cost_usd": 0.2,
        },
    ]
    for row in data:
        path = tmp_path / f"run_{row['run_id']}_summary.json"
        path.write_text(json.dumps(row), encoding="utf-8")

    points = load_run_points(tmp_path)
    rows = aggregate_by_baseline(points=points, x_metric="total_tokens")
    frontier = pareto_frontier(rows)

    aggregated_output = tmp_path / "pareto_aggregated.png"
    per_run_output = tmp_path / "pareto_per_run.png"

    render_aggregated_plot(
        rows=rows,
        frontier=frontier,
        output_path=aggregated_output,
        x_metric="total_tokens",
    )
    render_per_run_plot(
        points=points,
        rows=rows,
        frontier=frontier,
        output_path=per_run_output,
        x_metric="total_tokens",
    )

    assert aggregated_output.exists()
    assert per_run_output.exists()
