"""Run the controlled TravelPlanner scientific study across organization philosophies."""

from __future__ import annotations

import argparse
import copy
import csv
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
PACK_DIRNAME = "scientific_pack"
ARM_SPECS: dict[str, dict[str, Any]] = {
    "solo_direct": {
        "label": "Direct Solo",
        "config_budget_arg": "solo_direct_budget_usd",
        "extra_args": [],
        "description": "single direct call without explicit visible reasoning",
        "implementation": "single-call prompt",
    },
    "solo_cot": {
        "label": "CoT Solo",
        "config_budget_arg": "solo_cot_budget_usd",
        "extra_args": [],
        "description": "single call with guided reasoning before final JSON",
        "implementation": "single-call prompt",
    },
    "solo_self_refine": {
        "label": "Self-Refine Solo",
        "config_budget_arg": "solo_self_refine_budget_usd",
        "extra_args": [],
        "description": "draft, critique, revise",
        "implementation": "single-agent iterative refinement",
    },
    "planner_executor": {
        "label": "Central Planner-Executor",
        "config_budget_arg": "planner_executor_budget_usd",
        "extra_args": [],
        "description": "central planner emits blueprint, executor composes final itinerary",
        "implementation": "centralized two-stage planning",
    },
    "langgraph_supervisor": {
        "label": "Central Graph Supervisor",
        "config_budget_arg": "langgraph_budget_usd",
        "extra_args": lambda args: [  # noqa: ARG005 - fixed closure
            "--max-validation-retries",
            str(args.max_validation_retries),
        ],
        "description": "deterministic graph supervisor with explicit specialist nodes",
        "implementation": "LangGraph backend",
    },
    "stigmergiagentic": {
        "label": "StigmergiAgentic",
        "config_budget_arg": "stigmergiagentic_budget_usd",
        "extra_args": lambda args: [
            "--max-ticks",
            str(args.our_max_ticks),
            "--agents",
            str(args.our_agents),
        ],
        "description": "emergent stigmergic coordination without central supervisor",
        "implementation": "repository runtime",
    },
}
REGISTRY_FIELDS = [
    "stage",
    "arm",
    "arm_label",
    "seed",
    "status",
    "failure_kind",
    "failure_message",
    "queries_requested",
    "query_json_count",
    "started_at_utc",
    "ended_at_utc",
    "runtime_wall_seconds",
    "out_dir",
    "config_path",
    "runs_json",
    "official_eval_json",
    "benchmark_summary_json",
    "log_path",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the TravelPlanner scientific study across organization philosophies"
    )
    parser.add_argument("--study-root", type=Path, required=True)
    parser.add_argument("--provider", type=str, default="openrouter")
    parser.add_argument("--model", type=str, default="qwen/qwen3.5-9b")
    parser.add_argument(
        "--base-url",
        type=str,
        default="https://openrouter.ai/api/v1",
    )
    parser.add_argument("--database-root", type=Path, default=Path("data/travelplanner/database"))
    parser.add_argument("--split", type=str, default="validation")
    parser.add_argument(
        "--stage",
        choices=["preflight", "pilot", "full", "all"],
        default="all",
    )
    parser.add_argument(
        "--arms",
        type=str,
        default=",".join(ARM_SPECS),
        help="Comma-separated framework ids",
    )
    parser.add_argument("--seeds", type=str, default="42,43,44")
    parser.add_argument("--preflight-count", type=int, default=3)
    parser.add_argument("--pilot-count", type=int, default=20)
    parser.add_argument("--full-count", type=int, default=180)
    parser.add_argument("--request-timeout-seconds", type=int, default=120)
    parser.add_argument("--retry-attempts", type=int, default=2)
    parser.add_argument("--max-response-tokens", type=int, default=512)
    parser.add_argument("--max-validation-retries", type=int, default=2)
    parser.add_argument("--our-max-ticks", type=int, default=30)
    parser.add_argument("--our-agents", type=int, default=3)
    parser.add_argument("--solo-direct-budget-usd", type=float, default=20.0)
    parser.add_argument("--solo-cot-budget-usd", type=float, default=20.0)
    parser.add_argument("--solo-self-refine-budget-usd", type=float, default=20.0)
    parser.add_argument("--planner-executor-budget-usd", type=float, default=20.0)
    parser.add_argument("--langgraph-budget-usd", type=float, default=20.0)
    parser.add_argument("--stigmergiagentic-budget-usd", type=float, default=20.0)
    parser.add_argument("--force", action="store_true", default=False)
    return parser.parse_args(argv)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_csv_list(raw: str) -> list[str]:
    return [item.strip() for item in str(raw).split(",") if item.strip()]


def parse_seed_list(raw: str) -> list[int]:
    seeds: list[int] = []
    for item in parse_csv_list(raw):
        seeds.append(int(item))
    if not seeds:
        raise ValueError("At least one seed is required")
    return seeds


def study_pack_dir(study_root: Path) -> Path:
    return study_root / PACK_DIRNAME


def load_registry(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_registry(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REGISTRY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in REGISTRY_FIELDS})


def replace_registry_row(rows: list[dict[str, Any]], new_row: dict[str, Any]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for row in rows:
        if (
            row.get("stage") == new_row.get("stage")
            and row.get("arm") == new_row.get("arm")
            and row.get("seed") == str(new_row.get("seed"))
        ):
            continue
        kept.append(row)
    kept.append(new_row)
    return kept


def build_openrouter_config(args: argparse.Namespace, *, max_budget_usd: float) -> dict[str, Any]:
    base = yaml.safe_load((REPO_ROOT / "config" / "travelplanner.yaml").read_text(encoding="utf-8"))
    config = copy.deepcopy(base)
    config.setdefault("travelplanner", {})
    config["travelplanner"]["database_path"] = "data/travelplanner/database"
    config["travelplanner"]["dataset_split"] = args.split
    config.setdefault("llm", {})
    config["llm"].update(
        {
            "provider": args.provider,
            "model": args.model,
            "base_url": args.base_url,
            "temperature": 0.0,
            "retry_attempts": args.retry_attempts,
            "request_timeout_seconds": args.request_timeout_seconds,
            "max_response_tokens": args.max_response_tokens,
            "max_budget_usd": max_budget_usd,
            "reasoning": {"effort": "none", "exclude": True},
        }
    )
    return config


def config_for_arm(args: argparse.Namespace, arm: str) -> dict[str, Any]:
    budget_arg = ARM_SPECS[arm]["config_budget_arg"]
    config = build_openrouter_config(args, max_budget_usd=float(getattr(args, budget_arg)))
    if arm == "stigmergiagentic":
        config.setdefault("agents", {})
        config["agents"]["num_agents"] = int(args.our_agents)
        config.setdefault("orchestrator", {})
        config["orchestrator"]["max_ticks"] = int(args.our_max_ticks)
    return config


def write_arm_config(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


def failure_kind_from_text(text: str) -> str:
    lowered = text.casefold()
    infra_signatures = [
        "504",
        "provider returned error",
        "the operation was aborted",
        "timeout",
        "timed out",
        "rate limit",
        "api connection",
        "internalservererror",
        "apitimeouterror",
        "api connection error",
        "temporarily unavailable",
        "service unavailable",
        "connection reset",
    ]
    if any(signature in lowered for signature in infra_signatures):
        return "infra_failure"
    return "framework_failure"


def count_query_results(out_dir: Path) -> int:
    query_dir = out_dir / "queries"
    if not query_dir.exists():
        return 0
    return len(list(query_dir.glob("query_*.json")))


def run_stage_command(
    *,
    args: argparse.Namespace,
    arm: str,
    seed: int,
    stage: str,
    query_count: int,
    config_path: Path,
    out_dir: Path,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    runs_json = out_dir / "runs.json"
    official_eval_json = out_dir / "official_eval.json"
    benchmark_summary_json = out_dir / "benchmark_summary.json"
    log_path = out_dir / "stage_command.log"

    started_at = utc_now()
    start_monotonic = time.perf_counter()

    if (
        (not args.force)
        and runs_json.exists()
        and official_eval_json.exists()
        and benchmark_summary_json.exists()
    ):
        return {
            "stage": stage,
            "arm": arm,
            "arm_label": ARM_SPECS[arm]["label"],
            "seed": seed,
            "status": "success",
            "failure_kind": "",
            "failure_message": "",
            "queries_requested": query_count,
            "query_json_count": count_query_results(out_dir),
            "started_at_utc": started_at,
            "ended_at_utc": utc_now(),
            "runtime_wall_seconds": 0.0,
            "out_dir": str(out_dir.resolve()),
            "config_path": str(config_path.resolve()),
            "runs_json": str(runs_json.resolve()),
            "official_eval_json": str(official_eval_json.resolve()),
            "benchmark_summary_json": str(benchmark_summary_json.resolve()),
            "log_path": str(log_path.resolve()),
        }

    command = [
        sys.executable,
        "scripts/run_travelplanner_framework_benchmark.py",
        "--framework",
        arm,
        "--out-dir",
        str(out_dir),
        "--config",
        str(config_path),
        "--database-root",
        str(args.database_root),
        "--split",
        args.split,
        "--max-queries",
        str(query_count),
        "--seed",
        str(seed),
    ]
    extra_args = ARM_SPECS[arm].get("extra_args", [])
    if callable(extra_args):
        extra_args = extra_args(args)
    command.extend(extra_args)
    if args.force:
        command.append("--force")

    print(f"[{stage}] arm={arm} seed={seed} queries={query_count}")
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    combined_output = completed.stdout + (
        ""
        if not completed.stderr
        else ("\n" if completed.stdout and not completed.stdout.endswith("\n") else "") + completed.stderr
    )
    log_path.write_text(combined_output, encoding="utf-8")

    query_json_count = count_query_results(out_dir)
    ended_at = utc_now()
    runtime_wall_seconds = round(time.perf_counter() - start_monotonic, 4)
    if completed.returncode == 0 and runs_json.exists() and official_eval_json.exists():
        status = "success"
        failure_kind = ""
        failure_message = ""
    else:
        failure_kind = failure_kind_from_text(combined_output)
        if query_json_count > 0:
            status = "partial_success"
        else:
            status = failure_kind
        failure_message = "\n".join(combined_output.splitlines()[-20:])[:4000]

    return {
        "stage": stage,
        "arm": arm,
        "arm_label": ARM_SPECS[arm]["label"],
        "seed": seed,
        "status": status,
        "failure_kind": failure_kind,
        "failure_message": failure_message,
        "queries_requested": query_count,
        "query_json_count": query_json_count,
        "started_at_utc": started_at,
        "ended_at_utc": ended_at,
        "runtime_wall_seconds": runtime_wall_seconds,
        "out_dir": str(out_dir.resolve()),
        "config_path": str(config_path.resolve()),
        "runs_json": str(runs_json.resolve()),
        "official_eval_json": str(official_eval_json.resolve()),
        "benchmark_summary_json": str(benchmark_summary_json.resolve()),
        "log_path": str(log_path.resolve()),
    }


def latest_status_for(
    rows: list[dict[str, Any]],
    *,
    stage: str,
    arm: str,
    seed: int,
) -> str | None:
    for row in reversed(rows):
        if row.get("stage") == stage and row.get("arm") == arm and row.get("seed") == str(seed):
            return str(row.get("status") or "")
    return None


def build_manifest(args: argparse.Namespace, *, arms: list[str], seeds: list[int]) -> dict[str, Any]:
    return {
        "study_root": str(args.study_root.resolve()),
        "run_tag": args.study_root.name,
        "created_at_utc": utc_now(),
        "question": (
            "At backbone-constant conditions and under the official TravelPlanner scorer, "
            "does stigmergic organization outperform reproducible centralized or monolithic organizations, "
            "and at what operational cost?"
        ),
        "primary_metric": "final_pass_rate",
        "secondary_metrics": [
            "delivery_rate",
            "commonsense_micro",
            "commonsense_macro",
            "hard_constraint_micro",
            "hard_constraint_macro",
            "tokens_total",
            "cost_total_usd",
            "runtime_wall_seconds",
            "avg_coordination_overhead",
            "reproducibility",
        ],
        "controlled_dimensions": {
            "provider": args.provider,
            "model": args.model,
            "base_url": args.base_url,
            "split": args.split,
            "temperature": 0.0,
            "request_timeout_seconds": args.request_timeout_seconds,
            "retry_attempts": args.retry_attempts,
            "max_response_tokens": args.max_response_tokens,
            "reasoning": {"effort": "none", "exclude": True},
        },
        "gates": {
            "preflight_queries": args.preflight_count,
            "pilot_queries": args.pilot_count,
            "full_queries": args.full_count,
            "canonical_seed": seeds[0],
        },
        "seeds": seeds,
        "arms": [
            {
                "id": arm,
                "label": ARM_SPECS[arm]["label"],
                "description": ARM_SPECS[arm]["description"],
                "implementation": ARM_SPECS[arm]["implementation"],
            }
            for arm in arms
        ],
    }


def print_stage_summary(rows: list[dict[str, Any]], *, stage: str) -> None:
    stage_rows = [row for row in rows if row.get("stage") == stage]
    summary = {
        "stage": stage,
        "rows": [
            {
                "arm": row.get("arm"),
                "seed": row.get("seed"),
                "status": row.get("status"),
                "query_json_count": row.get("query_json_count"),
                "queries_requested": row.get("queries_requested"),
            }
            for row in stage_rows
        ],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    study_root = args.study_root.expanduser().resolve()
    study_root.mkdir(parents=True, exist_ok=True)
    pack_root = study_pack_dir(study_root)
    pack_root.mkdir(parents=True, exist_ok=True)
    registry_path = pack_root / "run_registry.csv"
    manifest_path = pack_root / "study_manifest.json"
    config_root = study_root / "configs"
    config_root.mkdir(parents=True, exist_ok=True)

    arms = parse_csv_list(args.arms)
    unknown_arms = [arm for arm in arms if arm not in ARM_SPECS]
    if unknown_arms:
        raise ValueError(f"Unknown arms requested: {', '.join(unknown_arms)}")
    seeds = parse_seed_list(args.seeds)
    canonical_seed = seeds[0]

    manifest = build_manifest(args, arms=arms, seeds=seeds)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    registry_rows = load_registry(registry_path)
    configs: dict[str, Path] = {}
    for arm in arms:
        config_path = config_root / f"{arm}.yaml"
        write_arm_config(config_path, config_for_arm(args, arm))
        configs[arm] = config_path

    stages = ["preflight", "pilot", "full"] if args.stage == "all" else [args.stage]
    for stage in stages:
        if stage == "preflight":
            eligible_arms = list(arms)
            stage_seeds = [canonical_seed]
            query_count = args.preflight_count
        elif stage == "pilot":
            eligible_arms = [
                arm
                for arm in arms
                if latest_status_for(registry_rows, stage="preflight", arm=arm, seed=canonical_seed)
                == "success"
            ]
            stage_seeds = [canonical_seed]
            query_count = args.pilot_count
        else:
            eligible_arms = [
                arm
                for arm in arms
                if latest_status_for(registry_rows, stage="pilot", arm=arm, seed=canonical_seed)
                == "success"
            ]
            stage_seeds = list(seeds)
            query_count = args.full_count

        if not eligible_arms:
            print(json.dumps({"stage": stage, "rows": [], "note": "No eligible arms"}, indent=2))
            continue

        for arm in eligible_arms:
            for seed in stage_seeds:
                out_dir = study_root / "runs" / arm / f"seed_{seed}" / stage
                row = run_stage_command(
                    args=args,
                    arm=arm,
                    seed=seed,
                    stage=stage,
                    query_count=query_count,
                    config_path=configs[arm],
                    out_dir=out_dir,
                )
                registry_rows = replace_registry_row(registry_rows, row)
                write_registry(registry_path, registry_rows)

        print_stage_summary(registry_rows, stage=stage)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
