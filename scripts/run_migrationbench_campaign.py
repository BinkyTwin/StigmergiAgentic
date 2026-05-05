"""Run several MigrationBench framework arms sequentially."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


DEFAULT_FRAMEWORKS = [
    "no_change",
    "dependency_only_script",
    "solo_direct",
    "planner_executor",
    "agentless_self_debug",
    "stigmergic_v6_static",
    "stigmergic_v7_repair_colony",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subset", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--frameworks", nargs="*", default=DEFAULT_FRAMEWORKS)
    parser.add_argument("--config", type=Path, default=Path("config/migrationbench_v6_static_deepseek.yaml"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--force", action="store_true", default=False)
    parser.add_argument("--skip-official-eval", action="store_true", default=False)
    parser.add_argument("--query-timeout-seconds", type=float, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for framework in args.frameworks:
        command = [
            sys.executable,
            "scripts/run_migrationbench_framework_benchmark.py",
            "--framework",
            framework,
            "--subset",
            str(args.subset),
            "--out-dir",
            str(args.out_dir / framework),
            "--config",
            str(args.config),
            "--seed",
            str(args.seed),
        ]
        if args.force:
            command.append("--force")
        if args.skip_official_eval:
            command.append("--skip-official-eval")
        if args.query_timeout_seconds is not None:
            command.extend(["--query-timeout-seconds", str(args.query_timeout_seconds)])
        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
