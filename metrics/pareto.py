"""Pareto frontier analysis for Sprint 4 baseline comparison."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, pstdev
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


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for Pareto analysis."""
    parser = argparse.ArgumentParser(description="Build Pareto cost/quality chart from run summaries")
    parser.add_argument("--input-dir", type=str, default="metrics/output", help="Directory containing run_*_summary.json")
    parser.add_argument("--output", type=str, default="metrics/output/pareto.png", help="Output image path")
    parser.add_argument("--x-metric", choices=["total_tokens", "total_cost_usd"], default="total_tokens")
    parser.add_argument("--export-json", type=str, default=None, help="Optional aggregated JSON export path")
    return parser.parse_args()


def load_run_points(input_dir: Path) -> list[RunPoint]:
    """Load run points from exported summary files."""
    points: list[RunPoint] = []
    for summary_path in sorted(input_dir.glob("run_*_summary.json")):
        with summary_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        baseline = str(payload.get("baseline") or payload.get("scheduler") or "stigmergic")
        points.append(
            RunPoint(
                baseline=baseline,
                run_id=str(payload.get("run_id", summary_path.stem.replace("run_", "").replace("_summary", ""))),
                success_rate=float(payload.get("success_rate", 0.0)),
                total_tokens=int(payload.get("total_tokens", 0)),
                total_cost_usd=float(payload.get("total_cost_usd", 0.0)),
            )
        )
    return points


def aggregate_by_baseline(points: list[RunPoint], x_metric: str) -> list[dict[str, Any]]:
    """Aggregate mean/std values per baseline."""
    grouped: dict[str, list[RunPoint]] = {}
    for point in points:
        grouped.setdefault(point.baseline, []).append(point)

    rows: list[dict[str, Any]] = []
    for baseline, bucket in sorted(grouped.items()):
        x_values = [getattr(point, x_metric) for point in bucket]
        y_values = [point.success_rate for point in bucket]
        rows.append(
            {
                "baseline": baseline,
                "runs": len(bucket),
                "x_mean": float(mean(x_values)),
                "x_std": float(pstdev(x_values)) if len(x_values) > 1 else 0.0,
                "success_mean": float(mean(y_values)),
                "success_std": float(pstdev(y_values)) if len(y_values) > 1 else 0.0,
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


def render_plot(rows: list[dict[str, Any]], frontier: list[dict[str, Any]], output_path: Path, x_metric: str) -> None:
    """Render Pareto scatter plot with error bars."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(10, 6))

    for row in rows:
        plt.errorbar(
            row["x_mean"],
            row["success_mean"],
            xerr=row["x_std"],
            yerr=row["success_std"],
            fmt="o",
            capsize=4,
            label=f"{row['baseline']} (n={row['runs']})",
        )
        plt.annotate(row["baseline"], (row["x_mean"], row["success_mean"]), textcoords="offset points", xytext=(5, 5))

    if frontier:
        frontier_x = [row["x_mean"] for row in frontier]
        frontier_y = [row["success_mean"] for row in frontier]
        plt.plot(frontier_x, frontier_y, linestyle="--", linewidth=1.5, color="black", label="Pareto frontier")

    x_label = "Total tokens" if x_metric == "total_tokens" else "Total cost (USD)"
    plt.xlabel(x_label)
    plt.ylabel("Success rate")
    plt.title("Sprint 4 Pareto frontier (cost vs precision)")
    plt.grid(alpha=0.25)
    plt.legend(loc="best")
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_path = Path(args.output)

    points = load_run_points(input_dir=input_dir)
    if not points:
        raise ValueError(f"No run summary found in {input_dir}")

    rows = aggregate_by_baseline(points=points, x_metric=str(args.x_metric))
    frontier = pareto_frontier(rows=rows)
    render_plot(rows=rows, frontier=frontier, output_path=output_path, x_metric=str(args.x_metric))

    if args.export_json:
        export_payload = {
            "x_metric": args.x_metric,
            "rows": rows,
            "pareto_frontier": frontier,
        }
        export_path = Path(args.export_json)
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(json.dumps(export_payload, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps({"points": len(points), "baselines": len(rows), "output": str(output_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
