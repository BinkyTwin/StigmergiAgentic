"""Build the TravelPlanner scientific paper pack from study artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any


PRIMARY_METRICS = [
    ("delivery_rate", "Delivery"),
    ("commonsense_micro", "Commonsense Micro"),
    ("commonsense_macro", "Commonsense Macro"),
    ("hard_constraint_micro", "Hard Constraint Micro"),
    ("hard_constraint_macro", "Hard Constraint Macro"),
    ("final_pass_rate", "Final Pass"),
]
OPS_METRICS = [
    ("tokens_total", "Tokens"),
    ("cost_total_usd", "Cost (USD)"),
    ("runtime_wall_seconds", "Runtime Wall (s)"),
    ("avg_runtime_per_query_seconds", "Avg Runtime / Query (s)"),
    ("avg_coordination_overhead", "Avg Coordination Overhead"),
]
CANONICAL_COMPARISONS = [
    "solo_direct",
    "solo_cot",
    "solo_self_refine",
    "planner_executor",
    "langgraph_supervisor",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build markdown/csv/json paper-pack outputs from a TravelPlanner scientific study"
    )
    parser.add_argument("--study-root", type=Path, required=True)
    parser.add_argument("--canonical-seed", type=int, default=42)
    parser.add_argument("--bootstrap-iters", type=int, default=5000)
    return parser.parse_args(argv)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_registry(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:  # noqa: BLE001
        return default


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:  # noqa: BLE001
        return default


def mean_sd(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        return values[0], 0.0
    return statistics.mean(values), statistics.stdev(values)


def format_percent_with_sd(values: list[float]) -> str:
    mean_value, sd_value = mean_sd(values)
    return f"{mean_value * 100:.1f} ± {sd_value * 100:.1f}"


def format_number_with_sd(values: list[float], digits: int = 4) -> str:
    mean_value, sd_value = mean_sd(values)
    return f"{mean_value:.{digits}f} ± {sd_value:.{digits}f}"


def render_markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_run_metrics(row: dict[str, Any]) -> dict[str, Any]:
    official_eval = load_json(Path(row["official_eval_json"]))
    benchmark_summary = load_json(Path(row["benchmark_summary_json"]))
    scores = dict(official_eval.get("scores", {}))
    return {
        "arm": row["arm"],
        "arm_label": row["arm_label"],
        "seed": as_int(row["seed"]),
        "status": row["status"],
        **{metric: as_float(scores.get(metric)) for metric, _ in PRIMARY_METRICS},
        **{metric: as_float(benchmark_summary.get(metric)) for metric, _ in OPS_METRICS},
        "runs_json": row["runs_json"],
        "official_eval_json": row["official_eval_json"],
        "benchmark_summary_json": row["benchmark_summary_json"],
    }


def build_arm_row(
    *,
    arm: str,
    arm_label: str,
    run_metrics: list[dict[str, Any]],
    expected_runs: int,
    failed_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    success_metrics = [row for row in run_metrics if row["status"] == "success"]
    is_valid = len(success_metrics) == expected_runs
    failure_notes = [str(row.get("failure_message", "")).strip() for row in failed_rows if row.get("failure_message")]
    failure_note = failure_notes[-1] if failure_notes else ""
    aggregate: dict[str, Any] = {
        "arm": arm,
        "arm_label": arm_label,
        "status": "valid" if is_valid else ("partial_success" if success_metrics else "failed"),
        "valid_runs": len(success_metrics),
        "expected_runs": expected_runs,
        "failure_note": failure_note,
    }
    for metric, _label in PRIMARY_METRICS:
        values = [as_float(row.get(metric)) for row in success_metrics]
        aggregate[f"{metric}_mean"] = mean_sd(values)[0] if values else None
        aggregate[f"{metric}_sd"] = mean_sd(values)[1] if values else None
        aggregate[f"{metric}_display"] = format_percent_with_sd(values) if values else "NA"
    for metric, _label in OPS_METRICS:
        values = [as_float(row.get(metric)) for row in success_metrics]
        aggregate[f"{metric}_mean"] = mean_sd(values)[0] if values else None
        aggregate[f"{metric}_sd"] = mean_sd(values)[1] if values else None
        aggregate[f"{metric}_display"] = format_number_with_sd(values) if values else "NA"
    return aggregate


def exact_mcnemar_p(wins: int, losses: int) -> float:
    discordant = wins + losses
    if discordant <= 0:
        return 1.0
    smaller = min(wins, losses)
    cumulative = 0.0
    for value in range(0, smaller + 1):
        cumulative += math.comb(discordant, value) * (0.5**discordant)
    return min(1.0, 2.0 * cumulative)


def bootstrap_ci_from_pairs(
    pairs: list[tuple[bool, bool]],
    *,
    iterations: int,
    seed: int,
) -> tuple[float, float]:
    if not pairs:
        return 0.0, 0.0
    rng = random.Random(seed)
    n = len(pairs)
    diffs: list[float] = []
    for _ in range(iterations):
        sample = [pairs[rng.randrange(n)] for _ in range(n)]
        delta = sum(int(left) - int(right) for left, right in sample) / n
        diffs.append(delta)
    diffs.sort()
    lower_idx = max(0, int(0.025 * (len(diffs) - 1)))
    upper_idx = min(len(diffs) - 1, int(0.975 * (len(diffs) - 1)))
    return diffs[lower_idx], diffs[upper_idx]


def load_runs_by_query_idx(path: Path) -> dict[int, dict[str, Any]]:
    payload = load_json(path)
    result: dict[int, dict[str, Any]] = {}
    for item in payload.get("runs", []):
        if not isinstance(item, dict):
            continue
        try:
            query_idx = int(item.get("query_idx"))
        except Exception:  # noqa: BLE001
            continue
        result[query_idx] = item
    return result


def build_pairwise_stats(
    *,
    registry_rows: list[dict[str, Any]],
    canonical_seed: int,
    bootstrap_iters: int,
) -> list[dict[str, Any]]:
    canonical_success = {
        row["arm"]: row
        for row in registry_rows
        if row.get("stage") == "full"
        and as_int(row.get("seed")) == canonical_seed
        and row.get("status") == "success"
    }
    stig_row = canonical_success.get("stigmergiagentic")
    if stig_row is None:
        return []

    left_runs = load_runs_by_query_idx(Path(stig_row["runs_json"]))
    results: list[dict[str, Any]] = []
    for arm in CANONICAL_COMPARISONS:
        right_row = canonical_success.get(arm)
        if right_row is None:
            results.append(
                {
                    "left": "StigmergiAgentic",
                    "right": arm,
                    "available": False,
                    "reason": "missing_successful_canonical_run",
                }
            )
            continue
        right_runs = load_runs_by_query_idx(Path(right_row["runs_json"]))
        common_idx = sorted(set(left_runs) & set(right_runs))
        pairs = [
            (
                bool(left_runs[index].get("final_pass", False)),
                bool(right_runs[index].get("final_pass", False)),
            )
            for index in common_idx
        ]
        wins = sum(1 for left, right in pairs if left and not right)
        losses = sum(1 for left, right in pairs if right and not left)
        ties = sum(1 for left, right in pairs if left == right)
        left_rate = sum(int(left) for left, _ in pairs) / len(pairs) if pairs else 0.0
        right_rate = sum(int(right) for _, right in pairs) / len(pairs) if pairs else 0.0
        ci_low, ci_high = bootstrap_ci_from_pairs(
            pairs,
            iterations=bootstrap_iters,
            seed=canonical_seed + len(common_idx),
        )
        results.append(
            {
                "left": "StigmergiAgentic",
                "right": right_row["arm_label"],
                "available": True,
                "paired_queries": len(pairs),
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "left_rate": left_rate,
                "right_rate": right_rate,
                "delta_final_pass_rate": left_rate - right_rate,
                "mcnemar_exact_p": exact_mcnemar_p(wins, losses),
                "bootstrap_ci_low": ci_low,
                "bootstrap_ci_high": ci_high,
            }
        )
    return results


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    study_root = args.study_root.expanduser().resolve()
    pack_root = study_root / "scientific_pack"
    pack_root.mkdir(parents=True, exist_ok=True)
    manifest_path = pack_root / "study_manifest.json"
    registry_path = pack_root / "run_registry.csv"
    if not manifest_path.exists():
        raise FileNotFoundError(manifest_path)
    if not registry_path.exists():
        raise FileNotFoundError(registry_path)

    manifest = load_json(manifest_path)
    registry_rows = load_registry(registry_path)
    full_rows = [row for row in registry_rows if row.get("stage") == "full"]
    full_metrics = [build_run_metrics(row) for row in full_rows if row.get("status") == "success"]

    arm_entries = {entry["id"]: entry for entry in manifest.get("arms", [])}
    expected_runs = len(manifest.get("seeds", []))
    aggregated_rows: list[dict[str, Any]] = []
    for arm, entry in arm_entries.items():
        arm_metrics = [row for row in full_metrics if row["arm"] == arm]
        arm_failures = [row for row in full_rows if row.get("arm") == arm and row.get("status") != "success"]
        aggregated_rows.append(
            build_arm_row(
                arm=arm,
                arm_label=entry["label"],
                run_metrics=arm_metrics,
                expected_runs=expected_runs,
                failed_rows=arm_failures,
            )
        )

    valid_rows = [row for row in aggregated_rows if row["status"] == "valid"]
    invalid_rows = [row for row in aggregated_rows if row["status"] != "valid"]

    main_md_path = pack_root / "paper_table_main.md"
    main_csv_path = pack_root / "paper_table_main.csv"
    secondary_csv_path = pack_root / "paper_table_secondary.csv"
    pairwise_json_path = pack_root / "pairwise_final_pass_stats.json"
    pairwise_md_path = pack_root / "pairwise_final_pass_stats.md"
    pareto_csv_path = pack_root / "pareto_summary.csv"
    reproducibility_path = pack_root / "reproducibility_report.md"
    threats_path = pack_root / "threats_to_validity.md"
    dsr_path = pack_root / "dsr_episode1_summary.md"

    valid_headers = ["Philosophy", "Valid Runs", *[label for _, label in PRIMARY_METRICS]]
    valid_markdown_rows = [
        [
            row["arm_label"],
            f"{row['valid_runs']}/{row['expected_runs']}",
            *[str(row[f"{metric}_display"]) for metric, _ in PRIMARY_METRICS],
        ]
        for row in valid_rows
    ]
    invalid_headers = ["Philosophy", "Status", "Successful Full Runs", "Failure Note"]
    invalid_markdown_rows = [
        [
            row["arm_label"],
            row["status"],
            f"{row['valid_runs']}/{row['expected_runs']}",
            row["failure_note"][:120].replace("\n", " "),
        ]
        for row in invalid_rows
    ]
    main_markdown = "# Paper Table — Main Results\n\n"
    main_markdown += "## Valid Arms\n\n"
    main_markdown += render_markdown_table(valid_headers, valid_markdown_rows)
    if invalid_markdown_rows:
        main_markdown += "\n## Invalid or Failed Arms\n\n"
        main_markdown += render_markdown_table(invalid_headers, invalid_markdown_rows)
    main_md_path.write_text(main_markdown, encoding="utf-8")

    main_csv_rows: list[dict[str, Any]] = []
    for row in aggregated_rows:
        csv_row = {
            "arm": row["arm"],
            "arm_label": row["arm_label"],
            "status": row["status"],
            "valid_runs": row["valid_runs"],
            "expected_runs": row["expected_runs"],
            "failure_note": row["failure_note"],
        }
        for metric, _ in PRIMARY_METRICS:
            csv_row[f"{metric}_mean"] = row.get(f"{metric}_mean")
            csv_row[f"{metric}_sd"] = row.get(f"{metric}_sd")
        for metric, _ in OPS_METRICS:
            csv_row[f"{metric}_mean"] = row.get(f"{metric}_mean")
            csv_row[f"{metric}_sd"] = row.get(f"{metric}_sd")
        main_csv_rows.append(csv_row)
    write_csv(main_csv_path, list(main_csv_rows[0].keys()) if main_csv_rows else ["arm"], main_csv_rows)

    secondary_rows = [
        {
            "arm": row["arm"],
            "arm_label": row["arm_label"],
            "seed": row["seed"],
            **{metric: row[metric] for metric, _ in PRIMARY_METRICS},
            **{metric: row[metric] for metric, _ in OPS_METRICS},
            "status": row["status"],
            "runs_json": row["runs_json"],
            "official_eval_json": row["official_eval_json"],
        }
        for row in full_metrics
    ]
    write_csv(
        secondary_csv_path,
        list(secondary_rows[0].keys()) if secondary_rows else ["arm"],
        secondary_rows,
    )

    pairwise_rows = build_pairwise_stats(
        registry_rows=registry_rows,
        canonical_seed=args.canonical_seed,
        bootstrap_iters=args.bootstrap_iters,
    )
    pairwise_json_path.write_text(json.dumps({"rows": pairwise_rows}, indent=2) + "\n", encoding="utf-8")
    pairwise_markdown_rows: list[list[str]] = []
    for row in pairwise_rows:
        if not row.get("available"):
            pairwise_markdown_rows.append(
                [str(row["left"]), str(row["right"]), "NA", "NA", "NA", "NA", "NA"]
            )
            continue
        pairwise_markdown_rows.append(
            [
                str(row["left"]),
                str(row["right"]),
                f"{row['wins']}/{row['losses']}/{row['ties']}",
                f"{row['delta_final_pass_rate'] * 100:.1f}",
                f"{row['mcnemar_exact_p']:.4f}",
                f"{row['bootstrap_ci_low'] * 100:.1f}",
                f"{row['bootstrap_ci_high'] * 100:.1f}",
            ]
        )
    pairwise_markdown = "# Pairwise Final-Pass Statistics\n\n"
    pairwise_markdown += render_markdown_table(
        ["Left", "Right", "Wins/Losses/Ties", "Delta Final Pass", "McNemar p", "CI Low", "CI High"],
        pairwise_markdown_rows,
    )
    pairwise_md_path.write_text(pairwise_markdown, encoding="utf-8")

    pareto_rows = [
        {
            "arm": row["arm"],
            "arm_label": row["arm_label"],
            "status": row["status"],
            "final_pass_rate_mean": row.get("final_pass_rate_mean"),
            "cost_total_usd_mean": row.get("cost_total_usd_mean"),
            "runtime_wall_seconds_mean": row.get("runtime_wall_seconds_mean"),
            "avg_coordination_overhead_mean": row.get("avg_coordination_overhead_mean"),
        }
        for row in aggregated_rows
    ]
    write_csv(
        pareto_csv_path,
        list(pareto_rows[0].keys()) if pareto_rows else ["arm"],
        pareto_rows,
    )

    status_counts: dict[str, int] = {}
    for row in registry_rows:
        key = f"{row.get('stage')}::{row.get('status')}"
        status_counts[key] = status_counts.get(key, 0) + 1
    reproducibility_lines = [
        "# Reproducibility Report",
        "",
        f"- Study root: `{study_root}`",
        f"- Canonical seed for paired analysis: `{args.canonical_seed}`",
        f"- Valid full arms: `{len(valid_rows)}/{len(aggregated_rows)}`",
        "",
        "## Status Counts",
        "",
    ]
    for key, value in sorted(status_counts.items()):
        reproducibility_lines.append(f"- `{key}`: {value}")
    failures = [row for row in registry_rows if row.get("status") != "success"]
    if failures:
        reproducibility_lines.extend(["", "## Failure Notes", ""])
        for row in failures:
            reproducibility_lines.append(
                f"- `{row.get('stage')}` / `{row.get('arm_label')}` / seed `{row.get('seed')}`: "
                f"{row.get('status')} ({row.get('failure_kind') or 'n/a'})"
            )
    reproducibility_path.write_text("\n".join(reproducibility_lines) + "\n", encoding="utf-8")

    threats_lines = [
        "# Threats to Validity",
        "",
        "- Internal validity: prompt engineering and baseline-specific decomposition choices can influence results, even under controlled backbone/provider settings.",
        "- Construct validity: TravelPlanner primarily measures constrained itinerary planning, not the full space of software-engineering coordination tasks.",
        "- External validity: results on TravelPlanner do not automatically transfer to code migration or general enterprise work.",
        "- Conclusion validity: the study uses a controlled protocol with three replications, which improves robustness but does not constitute an industrial field trial.",
        "- Provider validity: OpenRouter and upstream serving variability can affect latency, malformed outputs, and run reproducibility.",
    ]
    threats_path.write_text("\n".join(threats_lines) + "\n", encoding="utf-8")

    best_arm = None
    if valid_rows:
        best_arm = max(valid_rows, key=lambda row: row.get("final_pass_rate_mean") or 0.0)
    dsr_lines = [
        "# DSR Episode 1 Summary",
        "",
        "This scientific pack operationalizes OC3 and FEDS Episode 1 as a controlled same-backbone benchmark across organization philosophies on TravelPlanner.",
        f"- Valid arms in the principal table: `{len(valid_rows)}/{len(aggregated_rows)}`",
        f"- Replications per valid arm targeted: `{expected_runs}`",
        f"- Primary criterion: `Final Pass Rate`",
    ]
    if best_arm is not None:
        dsr_lines.append(
            f"- Best valid arm by mean final pass: `{best_arm['arm_label']}` "
            f"({best_arm['final_pass_rate_display']})"
        )
    dsr_lines.extend(
        [
            "",
            "Interpretation should remain cautious: the study compares reproducible organization philosophies under a controlled TravelPlanner protocol, not universal framework superiority across all domains.",
        ]
    )
    dsr_path.write_text("\n".join(dsr_lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "main_table_md": str(main_md_path),
                "main_table_csv": str(main_csv_path),
                "secondary_csv": str(secondary_csv_path),
                "pairwise_json": str(pairwise_json_path),
                "pairwise_md": str(pairwise_md_path),
                "pareto_csv": str(pareto_csv_path),
                "reproducibility_report": str(reproducibility_path),
                "threats_to_validity": str(threats_path),
                "dsr_episode1_summary": str(dsr_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
