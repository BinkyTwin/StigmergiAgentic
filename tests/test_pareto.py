"""Tests for Sprint 4 Pareto analysis module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from metrics.pareto import aggregate_by_baseline, load_run_points, pareto_frontier


def test_load_run_points_and_aggregate(tmp_path: Path) -> None:
    data = [
        {"run_id": "a", "baseline": "stigmergic", "success_rate": 0.9, "total_tokens": 1000, "total_cost_usd": 0.1},
        {"run_id": "b", "baseline": "stigmergic", "success_rate": 0.8, "total_tokens": 1200, "total_cost_usd": 0.15},
        {"run_id": "c", "baseline": "single_agent", "success_rate": 0.7, "total_tokens": 600, "total_cost_usd": 0.05},
    ]
    for row in data:
        path = tmp_path / f"run_{row['run_id']}_summary.json"
        path.write_text(json.dumps(row), encoding="utf-8")

    points = load_run_points(input_dir=tmp_path)
    assert len(points) == 3

    rows = aggregate_by_baseline(points=points, x_metric="total_tokens")
    assert len(rows) == 2
    stigmergic = next(item for item in rows if item["baseline"] == "stigmergic")
    assert stigmergic["x_mean"] == 1100.0
    assert stigmergic["success_mean"] == pytest.approx(0.85)


def test_pareto_frontier_filters_dominated_points() -> None:
    rows = [
        {"baseline": "A", "x_mean": 100.0, "success_mean": 0.5},
        {"baseline": "B", "x_mean": 120.0, "success_mean": 0.45},
        {"baseline": "C", "x_mean": 130.0, "success_mean": 0.6},
    ]
    frontier = pareto_frontier(rows)
    baseline_names = [row["baseline"] for row in frontier]
    assert baseline_names == ["A", "C"]
