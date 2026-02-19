"""Pareto frontier analysis for Sprint 4 baseline comparison."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, stdev
from typing import Any

import matplotlib.pyplot as plt


@dataclass
class RunPoint:
    """One run point used for Pareto analysis."""

    baseline: str
    run_id: str
    success_rate: float
    total_tokens: int
    total_cost_usd: float


PARETO_TITLE = "Sprint 4 Pareto frontier (cost vs precision)"


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for Pareto analysis."""
    parser = argparse.ArgumentParser(
        description="Build Pareto cost/quality chart from run summaries"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default="metrics/output",
        help="Directory containing run_*_summary.json",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="metrics/output/pareto.png",
        help="Output image path",
    )
    parser.add_argument(
        "--x-metric",
        choices=["total_tokens", "total_cost_usd"],
        default="total_tokens",
    )
    parser.add_argument(
        "--plot-mode",
        choices=["aggregated", "per-run"],
        default="aggregated",
        help="Plot aggregate means only, or one point per run with aggregate CI95 overlay",
    )
    parser.add_argument(
        "--require-baselines",
        type=str,
        default=None,
        help="Optional comma-separated baseline names that must exist in inputs",
    )
    parser.add_argument(
        "--export-json",
        type=str,
        default=None,
        help="Optional aggregated JSON export path",
    )
    return parser.parse_args()


def load_run_points(input_dir: Path) -> list[RunPoint]:
    """Load run points from exported summary files."""
    points: list[RunPoint] = []
    for summary_path in sorted(input_dir.glob("run_*_summary.json")):
        with summary_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        baseline = str(
            payload.get("baseline") or payload.get("scheduler") or "stigmergic"
        )
        points.append(
            RunPoint(
                baseline=baseline,
                run_id=str(
                    payload.get(
                        "run_id",
                        summary_path.stem.replace("run_", "").replace("_summary", ""),
                    )
                ),
                success_rate=float(payload.get("success_rate", 0.0)),
                total_tokens=int(payload.get("total_tokens", 0)),
                total_cost_usd=float(payload.get("total_cost_usd", 0.0)),
            )
        )
    return points


def _ci95_half_width(values: list[float]) -> tuple[float, float, float]:
    """Return mean, sample std, and 95% confidence interval half width."""
    avg = float(mean(values))
    if len(values) <= 1:
        return avg, 0.0, 0.0

    sample_std = float(stdev(values))
    ci95 = 1.96 * sample_std / math.sqrt(len(values))
    return avg, sample_std, float(ci95)


def aggregate_by_baseline(
    points: list[RunPoint], x_metric: str
) -> list[dict[str, Any]]:
    """Aggregate mean/std/CI95 values per baseline."""
    grouped: dict[str, list[RunPoint]] = defaultdict(list)
    for point in points:
        grouped[point.baseline].append(point)

    rows: list[dict[str, Any]] = []
    for baseline, bucket in sorted(grouped.items()):
        x_values = [float(getattr(point, x_metric)) for point in bucket]
        success_values = [float(point.success_rate) for point in bucket]
        x_mean, x_std, x_ci95 = _ci95_half_width(x_values)
        success_mean, success_std, success_ci95 = _ci95_half_width(success_values)
        rows.append(
            {
                "baseline": baseline,
                "runs": len(bucket),
                "x_mean": x_mean,
                "x_std": x_std,
                "x_ci95": x_ci95,
                "success_mean": success_mean,
                "success_std": success_std,
                "success_ci95": success_ci95,
            }
        )
    return rows


def pareto_frontier(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return Pareto-optimal baselines (min cost, max success)."""
    sorted_rows = sorted(rows, key=lambda row: (row["x_mean"], -row["success_mean"]))
    frontier: list[dict[str, Any]] = []
    best_success = -1.0
    for row in sorted_rows:
        success = float(row["success_mean"])
        if success > best_success:
            frontier.append(row)
            best_success = success
    return frontier


def enforce_required_baselines(
    points: list[RunPoint], required_baselines: list[str]
) -> None:
    """Validate that all required baselines exist in points."""
    if not required_baselines:
        return

    found = {point.baseline for point in points}
    missing = sorted(set(required_baselines) - found)
    if missing:
        raise ValueError(
            "Missing required baselines in input summaries: " + ", ".join(missing)
        )


def _x_axis_label(x_metric: str) -> str:
    return "Total tokens" if x_metric == "total_tokens" else "Total cost (USD)"


def _plot_frontier(frontier: list[dict[str, Any]]) -> None:
    if not frontier:
        return

    frontier_x = [row["x_mean"] for row in frontier]
    frontier_y = [row["success_mean"] for row in frontier]
    plt.plot(
        frontier_x,
        frontier_y,
        linestyle="--",
        linewidth=1.5,
        color="black",
        label="Pareto frontier",
    )


def render_aggregated_plot(
    rows: list[dict[str, Any]],
    frontier: list[dict[str, Any]],
    output_path: Path,
    x_metric: str,
) -> None:
    """Render Pareto plot from aggregate means with CI95 error bars."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(10, 6))

    for row in rows:
        plt.errorbar(
            row["x_mean"],
            row["success_mean"],
            xerr=row["x_ci95"],
            yerr=row["success_ci95"],
            fmt="o",
            capsize=4,
            label=f"{row['baseline']} (n={row['runs']})",
        )
        plt.annotate(
            row["baseline"],
            (row["x_mean"], row["success_mean"]),
            textcoords="offset points",
            xytext=(5, 5),
        )

    _plot_frontier(frontier)

    plt.xlabel(_x_axis_label(x_metric))
    plt.ylabel("Success rate")
    plt.title(PARETO_TITLE)
    plt.grid(alpha=0.25)
    plt.legend(loc="best")
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def render_per_run_plot(
    points: list[RunPoint],
    rows: list[dict[str, Any]],
    frontier: list[dict[str, Any]],
    output_path: Path,
    x_metric: str,
) -> None:
    """Render one point per run plus aggregate CI95 overlays per baseline."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(10, 6))

    grouped: dict[str, list[RunPoint]] = defaultdict(list)
    for point in points:
        grouped[point.baseline].append(point)

    for baseline, bucket in sorted(grouped.items()):
        x_values = [float(getattr(point, x_metric)) for point in bucket]
        y_values = [float(point.success_rate) for point in bucket]
        plt.scatter(
            x_values,
            y_values,
            alpha=0.55,
            s=30,
            label=f"{baseline} runs (n={len(bucket)})",
        )

    for row in rows:
        plt.errorbar(
            row["x_mean"],
            row["success_mean"],
            xerr=row["x_ci95"],
            yerr=row["success_ci95"],
            fmt="D",
            markersize=5,
            capsize=4,
            color="black",
            label=f"{row['baseline']} mean ±95% CI",
        )
        plt.annotate(
            row["baseline"],
            (row["x_mean"], row["success_mean"]),
            textcoords="offset points",
            xytext=(5, 5),
        )

    _plot_frontier(frontier)

    plt.xlabel(_x_axis_label(x_metric))
    plt.ylabel("Success rate")
    plt.title(PARETO_TITLE)
    plt.grid(alpha=0.25)
    plt.legend(loc="best", fontsize=8)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def build_export_payload(
    *,
    x_metric: str,
    plot_mode: str,
    points: list[RunPoint],
    rows: list[dict[str, Any]],
    frontier: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build JSON export payload while preserving backward-compatible keys."""
    raw_points = [asdict(point) for point in points]
    return {
        "x_metric": x_metric,
        "plot_mode": plot_mode,
        "raw_points": raw_points,
        "aggregates": rows,
        "rows": rows,
        "pareto_frontier": frontier,
    }


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_path = Path(args.output)

    points = load_run_points(input_dir=input_dir)
    if not points:
        raise ValueError(f"No run summary found in {input_dir}")

    required_baselines = (
        [
            item.strip()
            for item in str(args.require_baselines).split(",")
            if item.strip()
        ]
        if args.require_baselines
        else []
    )
    enforce_required_baselines(points=points, required_baselines=required_baselines)

    rows = aggregate_by_baseline(points=points, x_metric=str(args.x_metric))
    frontier = pareto_frontier(rows=rows)
    if args.plot_mode == "per-run":
        render_per_run_plot(
            points=points,
            rows=rows,
            frontier=frontier,
            output_path=output_path,
            x_metric=str(args.x_metric),
        )
    else:
        render_aggregated_plot(
            rows=rows,
            frontier=frontier,
            output_path=output_path,
            x_metric=str(args.x_metric),
        )

    if args.export_json:
        export_payload = build_export_payload(
            x_metric=str(args.x_metric),
            plot_mode=str(args.plot_mode),
            points=points,
            rows=rows,
            frontier=frontier,
        )
        export_path = Path(args.export_json)
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(
            json.dumps(export_payload, indent=2, sort_keys=True), encoding="utf-8"
        )

    print(
        json.dumps(
            {
                "points": len(points),
                "baselines": len(rows),
                "plot_mode": str(args.plot_mode),
                "output": str(output_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
