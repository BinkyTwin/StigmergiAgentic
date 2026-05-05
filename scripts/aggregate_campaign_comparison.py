"""Aggregate the final scientific campaign across models and frameworks.

Reads per-query JSON outputs from:
  - Gemma × stigmergie C3  (campaign_results/gemma-stigmergie/c3)
  - DeepSeek × stigmergie C3  (campaign_results/deepseek-stigmergie/c3)
  - Gemma × baselines  (campaign_results/gemma-baselines/{framework}/)
  - Qwen × stigmergie C3 fixture (benchmark_summary.json from v6c_retry_20260420)

Produces under output/final_campaign/:
  - per_query_summary.csv   — one row per (model, framework, query_idx)
  - matrix_A.csv            — orchestration effect (Gemma constant)
  - matrix_B.csv            — model effect (stigmergy C3 constant)
  - aggregates.json         — dict of per-(model, framework) summary stats
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

BASELINE_FRAMEWORKS = (
    "solo_direct",
    "solo_cot",
    "solo_self_refine",
    "planner_executor",
    "metagpt_sequential",
    "langgraph_supervisor",
)

QUERY_FILE_RE = re.compile(r"query_(\d+)\.json$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gemma",
        type=Path,
        default=Path("campaign_results/gemma-stigmergie"),
        help="Root of Gemma × stigmergie campaign outputs.",
    )
    parser.add_argument(
        "--deepseek",
        type=Path,
        default=Path("campaign_results/deepseek-stigmergie"),
        help="Root of DeepSeek × stigmergie campaign outputs.",
    )
    parser.add_argument(
        "--baselines",
        type=Path,
        default=Path("campaign_results/gemma-baselines"),
        help="Root of Gemma baselines campaign outputs.",
    )
    parser.add_argument(
        "--qwen-fixture",
        type=Path,
        default=Path(
            "output/travelplanner_framework_compare/"
            "v6c_retry_20260420_seed42/v6_C/seed42/benchmark_summary.json"
        ),
        help="Path to pre-computed Qwen stigmergie C3 benchmark_summary.json.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/final_campaign"),
    )
    return parser.parse_args()


def _load_stigmergy_row(
    path: Path, model: str, framework: str
) -> dict[str, Any] | None:
    try:
        text = path.read_text()
    except OSError:
        return None
    start = text.find('{\n  "adapter"')
    if start < 0:
        start = text.find("{\n")
    if start < 0:
        return None
    try:
        payload = json.loads(text[start:].strip())
    except json.JSONDecodeError:
        return None
    query_idx_match = QUERY_FILE_RE.search(path.name)
    query_idx = int(query_idx_match.group(1)) if query_idx_match else -1
    evaluation = payload.get("evaluation") or {}
    query_results = evaluation.get("query_results") or [{}]
    qr = query_results[0] if query_results else {}
    plan = payload.get("final_plan") or payload.get("plan") or []
    assistant_response = str(payload.get("assistant_response", "")).strip()
    evaluated_queries = int(evaluation.get("evaluated_queries", 0) or 0)
    artifact_delivered = bool(plan)
    official_delivered = evaluated_queries > 0 and (
        bool(plan)
        and (
            bool(qr.get("delivered", False))
            or float(evaluation.get("delivery_rate", 0.0) or 0.0) > 0.0
        )
    )
    if assistant_response == "No travel plan generated.":
        official_delivered = False
    raw_final_pass = bool(
        payload.get("raw_final_pass", qr.get("raw_final_pass", qr.get("final_pass", False)))
    )
    strict_final_pass = bool(
        payload.get(
            "strict_final_pass",
            qr.get("strict_final_pass", raw_final_pass and artifact_delivered),
        )
        and artifact_delivered
    )
    return {
        "model": model,
        "framework": framework,
        "query_idx": query_idx,
        "raw_final_pass": raw_final_pass,
        "strict_final_pass": strict_final_pass,
        "final_pass": strict_final_pass,
        "delivered": official_delivered,
        "artifact_delivered": artifact_delivered,
        "official_delivered": official_delivered,
        "tokens": int(payload.get("tokens_used", 0) or 0),
        "cost_usd": float(payload.get("cost_used", 0.0) or 0.0),
        "runtime_seconds": float(payload.get("runtime_seconds", 0.0) or 0.0),
        "failure_reason": str(qr.get("failure_reason", "")),
    }


def _load_baseline_row(
    path: Path, model: str, framework: str
) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    summary = payload.get("summary") or {}
    query_idx_match = QUERY_FILE_RE.search(path.name)
    query_idx = int(query_idx_match.group(1)) if query_idx_match else int(
        payload.get("query_idx", -1)
    )
    plan = payload.get("final_plan") or payload.get("plan") or []
    official_delivered = bool(plan)
    raw_final_pass = bool(payload.get("raw_final_pass", payload.get("final_pass", False)))
    strict_final_pass = bool(
        payload.get("strict_final_pass", raw_final_pass and official_delivered)
        and official_delivered
    )
    return {
        "model": model,
        "framework": framework,
        "query_idx": query_idx,
        "raw_final_pass": raw_final_pass,
        "strict_final_pass": strict_final_pass,
        "final_pass": strict_final_pass,
        "delivered": official_delivered,
        "artifact_delivered": official_delivered,
        "official_delivered": official_delivered,
        "tokens": int(summary.get("tokens_used", 0) or 0),
        "cost_usd": float(summary.get("cost_used", 0.0) or 0.0),
        "runtime_seconds": float(summary.get("runtime_seconds", 0.0) or 0.0),
        "failure_reason": (
            ";".join(summary.get("validation_failures", []))
            if summary.get("validation_failures")
            else ""
        ),
    }


def collect_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in (args.gemma / "c3").glob("query_*.json"):
        row = _load_stigmergy_row(candidate, "gemma", "stigmergiagentic_c3")
        if row:
            rows.append(row)
    for candidate in (args.deepseek / "c3").glob("query_*.json"):
        row = _load_stigmergy_row(candidate, "deepseek", "stigmergiagentic_c3")
        if row:
            rows.append(row)
    for framework in BASELINE_FRAMEWORKS:
        folder = args.baselines / framework
        if not folder.exists():
            continue
        for candidate in folder.glob("query_*.json"):
            row = _load_baseline_row(candidate, "gemma", framework)
            if row:
                rows.append(row)
    return rows


def load_qwen_fixture(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return {
        "model": "qwen-3.5-9b",
        "framework": "stigmergiagentic_c3",
        "queries": int(data.get("queries", 0) or 0),
        "raw_final_pass_rate": float(data.get("final_pass_rate_raw", 0.0) or 0.0),
        "strict_final_pass_rate": float(data.get("final_pass_rate_raw", 0.0) or 0.0),
        "final_pass_rate": float(data.get("final_pass_rate_raw", 0.0) or 0.0),
        "delivery_rate": float(data.get("success_rate", 0.0) or 0.0),
        "artifact_delivery_rate": float(data.get("success_rate", 0.0) or 0.0),
        "official_delivery_rate": float(data.get("success_rate", 0.0) or 0.0),
        "tokens_total": int(data.get("tokens_total", 0) or 0),
        "cost_total_usd": float(data.get("cost_total_usd", 0.0) or 0.0),
        "avg_tokens": float(data.get("avg_tokens_per_query", 0.0) or 0.0),
        "avg_cost_usd": float(data.get("avg_cost_per_query_usd", 0.0) or 0.0),
        "avg_runtime_seconds": float(
            data.get("avg_runtime_per_query_seconds", 0.0) or 0.0
        ),
        "avg_coordination_overhead": float(
            data.get("avg_coordination_overhead", 0.0) or 0.0
        ),
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[(row["model"], row["framework"])].append(row)
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for key, items in buckets.items():
        n = len(items)
        raw_passes = sum(1 for r in items if r["raw_final_pass"])
        strict_passes = sum(1 for r in items if r["strict_final_pass"])
        artifact_deliv = sum(1 for r in items if r["artifact_delivered"])
        official_deliv = sum(1 for r in items if r["official_delivered"])
        official_delivery_rate = official_deliv / n if n else 0.0
        out[key] = {
            "queries": n,
            "raw_final_pass_rate": raw_passes / n if n else 0.0,
            "strict_final_pass_rate": strict_passes / n if n else 0.0,
            "final_pass_rate": strict_passes / n if n else 0.0,
            "delivery_rate": official_delivery_rate,
            "artifact_delivery_rate": artifact_deliv / n if n else 0.0,
            "official_delivery_rate": official_delivery_rate,
            "avg_tokens": (sum(r["tokens"] for r in items) / n) if n else 0.0,
            "avg_cost_usd": (sum(r["cost_usd"] for r in items) / n) if n else 0.0,
            "avg_runtime_seconds": (
                sum(r["runtime_seconds"] for r in items) / n if n else 0.0
            ),
            "tokens_total": sum(r["tokens"] for r in items),
            "cost_total_usd": sum(r["cost_usd"] for r in items),
        }
    return out


def mcnemar_counts(
    rows_a: list[dict[str, Any]], rows_b: list[dict[str, Any]]
) -> dict[str, int]:
    index_a = {r["query_idx"]: r["strict_final_pass"] for r in rows_a}
    index_b = {r["query_idx"]: r["strict_final_pass"] for r in rows_b}
    both = set(index_a) & set(index_b)
    b_only = sum(1 for q in both if index_a[q] and not index_b[q])
    c_only = sum(1 for q in both if not index_a[q] and index_b[q])
    return {
        "paired_queries": len(both),
        "a_passes_b_fails": b_only,
        "a_fails_b_passes": c_only,
        "both_pass": sum(1 for q in both if index_a[q] and index_b[q]),
        "both_fail": sum(1 for q in both if not index_a[q] and not index_b[q]),
    }


def write_per_query_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "model",
        "framework",
        "query_idx",
        "raw_final_pass",
        "strict_final_pass",
        "final_pass",
        "delivered",
        "artifact_delivered",
        "official_delivered",
        "tokens",
        "cost_usd",
        "runtime_seconds",
        "failure_reason",
    ]
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: (r["model"], r["framework"], r["query_idx"])))


def write_matrix(
    path: Path,
    aggregates: dict[tuple[str, str], dict[str, Any]],
    *,
    models: list[str],
    frameworks: list[str],
    qwen_point: dict[str, Any] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "model",
        "framework",
        "queries",
        "raw_final_pass_rate",
        "strict_final_pass_rate",
        "final_pass_rate",
        "delivery_rate",
        "artifact_delivery_rate",
        "official_delivery_rate",
        "avg_tokens",
        "avg_cost_usd",
        "avg_runtime_seconds",
        "tokens_total",
        "cost_total_usd",
    ]
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for model in models:
            for framework in frameworks:
                agg = aggregates.get((model, framework))
                if not agg:
                    continue
                writer.writerow({"model": model, "framework": framework, **agg})
        if qwen_point and "qwen-3.5-9b" in models and (
            "stigmergiagentic_c3" in frameworks
        ):
            writer.writerow(
                {
                    "model": "qwen-3.5-9b",
                    "framework": "stigmergiagentic_c3",
                    "queries": qwen_point["queries"],
                    "raw_final_pass_rate": qwen_point["raw_final_pass_rate"],
                    "strict_final_pass_rate": qwen_point["strict_final_pass_rate"],
                    "final_pass_rate": qwen_point["final_pass_rate"],
                    "delivery_rate": qwen_point["delivery_rate"],
                    "artifact_delivery_rate": qwen_point["artifact_delivery_rate"],
                    "official_delivery_rate": qwen_point["official_delivery_rate"],
                    "avg_tokens": qwen_point["avg_tokens"],
                    "avg_cost_usd": qwen_point["avg_cost_usd"],
                    "avg_runtime_seconds": qwen_point["avg_runtime_seconds"],
                    "tokens_total": qwen_point["tokens_total"],
                    "cost_total_usd": qwen_point["cost_total_usd"],
                }
            )


def main() -> int:
    args = parse_args()
    rows = collect_rows(args)
    aggregates = aggregate(rows)
    qwen_point = load_qwen_fixture(args.qwen_fixture)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_per_query_csv(rows, args.output_dir / "per_query_summary.csv")

    # Matrix A — orchestration effect, Gemma constant
    write_matrix(
        args.output_dir / "matrix_A.csv",
        aggregates,
        models=["gemma"],
        frameworks=[
            *BASELINE_FRAMEWORKS,
            "stigmergiagentic_c3",
        ],
    )
    # Matrix B — model effect, stigmergy C3 constant
    write_matrix(
        args.output_dir / "matrix_B.csv",
        aggregates,
        models=["qwen-3.5-9b", "gemma", "deepseek"],
        frameworks=["stigmergiagentic_c3"],
        qwen_point=qwen_point,
    )

    # McNemar pairs — Gemma stigmergie C3 vs each Gemma baseline
    stig_rows = [r for r in rows if r["model"] == "gemma" and r["framework"] == "stigmergiagentic_c3"]
    pairs: dict[str, dict[str, int]] = {}
    for framework in BASELINE_FRAMEWORKS:
        baseline_rows = [
            r for r in rows if r["model"] == "gemma" and r["framework"] == framework
        ]
        pairs[framework] = mcnemar_counts(stig_rows, baseline_rows)

    summary_payload = {
        "aggregates": {
            f"{m}::{f}": agg for (m, f), agg in aggregates.items()
        },
        "qwen_fixture": qwen_point,
        "mcnemar_gemma_stigmergie_vs_baselines": pairs,
    }
    (args.output_dir / "aggregates.json").write_text(
        json.dumps(summary_payload, indent=2, sort_keys=True)
    )

    print(f"Wrote per_query_summary.csv, matrix_A.csv, matrix_B.csv, aggregates.json to {args.output_dir}")
    print(f"Total rows aggregated: {len(rows)}")
    print(f"Aggregates: {len(aggregates)} cells")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
