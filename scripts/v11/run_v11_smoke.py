"""Run the V11 causal smoke suite programmatically.

This script is intentionally deterministic and LLM-free by default. It writes
campaign artifacts under the requested output directory and verifies replay
parity for every V11 arm it runs.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Sequence

from scripts.bench.compare_strategies import V11_ARMS, run_comparison
from scripts.bench.telemetry import replay_summary_from_dir


def _write_toy_subset(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"instance_id": "toy-v11-a", "expected": "alpha"},
        {"instance_id": "toy-v11-b", "expected": "beta"},
        {"instance_id": "toy-v11-c", "expected": "gamma"},
    ]
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def _clean_child(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _assert_replay_parity(out_dir: Path, arm_ids: Sequence[str]) -> None:
    for arm_id in arm_ids:
        arm_dir = out_dir / arm_id
        live_path = arm_dir / "summary.json"
        live = json.loads(live_path.read_text(encoding="utf-8"))
        replay = replay_summary_from_dir(arm_dir).to_dict()
        if live != replay:
            raise AssertionError(f"live != replay for {arm_id}")


def run_toy_smoke(out_dir: Path) -> dict:
    _clean_child(out_dir / "toy")
    subset = out_dir / "_inputs" / "toy_v11.jsonl"
    _write_toy_subset(subset)
    comparison = run_comparison(
        adapter_name="toy",
        subset_path=subset,
        out_dir=out_dir / "toy",
        seed=42,
        extras={"out_dir": str(out_dir / "toy"), "toy_initial_wrong": True},
        arms=V11_ARMS,
    )
    arm_ids = [arm["arm_id"] for arm in comparison["arms"]]
    _assert_replay_parity(out_dir / "toy", arm_ids)
    by_arm = {arm["arm_id"]: arm for arm in comparison["arms"]}
    b6 = by_arm["B6_operator_search"]
    required_positive = (
        "signal_read_total",
        "decision_influenced_total",
        "trajectory_divergence_total",
        "operator_invoked_total",
        "operator_applied_total",
    )
    missing = [key for key in required_positive if int(b6.get(key, 0)) <= 0]
    if missing:
        raise AssertionError(f"B6 missing positive causal metrics: {missing}")
    return comparison


def run_migrationbench_smoke(
    *,
    subset_path: Path,
    out_dir: Path,
    limit: int | None,
    official_eval: bool,
) -> dict:
    _clean_child(out_dir / "migrationbench")
    comparison = run_comparison(
        adapter_name="migrationbench",
        subset_path=subset_path,
        out_dir=out_dir / "migrationbench",
        seed=42,
        limit=limit,
        extras={
            "out_dir": str(out_dir / "migrationbench"),
            "official_eval": bool(official_eval),
        },
        arms=V11_ARMS,
    )
    arm_ids = [arm["arm_id"] for arm in comparison["arms"]]
    _assert_replay_parity(out_dir / "migrationbench", arm_ids)
    return comparison


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("campaign_results/v11/smoke"),
        help="Output directory for V11 smoke artifacts.",
    )
    parser.add_argument(
        "--migrationbench-subset",
        type=Path,
        default=None,
        help="Optional MigrationBench JSONL subset to run after toy smoke.",
    )
    parser.add_argument("--migrationbench-limit", type=int, default=None)
    parser.add_argument(
        "--official-eval",
        action="store_true",
        help="Enable official MigrationBench evaluator for the optional MB smoke.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {"toy": run_toy_smoke(out_dir)}
    if args.migrationbench_subset is not None:
        result["migrationbench"] = run_migrationbench_smoke(
            subset_path=Path(args.migrationbench_subset),
            out_dir=out_dir,
            limit=args.migrationbench_limit,
            official_eval=bool(args.official_eval),
        )
    summary_path = out_dir / "v11_smoke_summary.json"
    summary_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "ok", "summary_path": str(summary_path)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
