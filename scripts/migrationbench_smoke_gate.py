"""Run or verify the MigrationBench V7 smoke gate before `main_30`."""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path


FRAMEWORK = "stigmergic_v7_repair_colony"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=Path("config/migrationbench_v7_repair_colony_deepseek.yaml"))
    parser.add_argument("--subset", type=Path, default=Path("fixtures/migrationbench/subsets/smoke_5.jsonl"))
    parser.add_argument("--out-dir", type=Path, default=Path("campaign_results/migrationbench_v7_smoke_gated"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--skip-run", action="store_true", default=False)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.report or args.out_dir
    if args.report is None and not args.skip_run:
        command = [
            sys.executable,
            "scripts/run_migrationbench_framework_benchmark.py",
            "--framework",
            FRAMEWORK,
            "--subset",
            str(args.subset),
            "--out-dir",
            str(args.out_dir),
            "--config",
            str(args.config),
            "--seed",
            str(args.seed),
            "--force",
        ]
        completed = subprocess.run(command, text=True, check=False)
        if completed.returncode != 0:
            print(f"[gate] smoke command failed with {completed.returncode}", file=sys.stderr)
            return completed.returncode
    return verify_report(root)


def verify_report(root: Path) -> int:
    arm = root / FRAMEWORK if (root / FRAMEWORK).exists() else root
    errors: list[str] = []
    warnings: list[str] = []
    instances_dir = arm / "instances"
    logs_dir = arm / "logs"
    runs_json = arm / "runs.json"

    if not runs_json.exists():
        errors.append(f"missing runs.json: {runs_json}")
    else:
        runs = json.loads(runs_json.read_text(encoding="utf-8")).get("runs", [])
        selected = 0
        for row in runs:
            instance_id = str(row.get("instance_id", "")).strip()
            branch_count = int(row.get("branch_count", 0) or 0)
            db_path = instances_dir / f"{instance_id}_artifacts" / "markers.db"
            if not db_path.exists():
                errors.append(f"{instance_id}: missing markers.db")
                continue
            patch_count, distinct_objectives, db_selected, max_digest = inspect_markers(db_path)
            selected += db_selected
            if patch_count > 0 and branch_count <= 0:
                errors.append(f"{instance_id}: branch_count=0 but markers.db has {patch_count} patch_hypothesis")
            if distinct_objectives != 1:
                errors.append(f"{instance_id}: expected 1 objective_id, found {distinct_objectives}")
            if max_digest > 4500:
                warnings.append(f"{instance_id}: max build_feedback_digest length={max_digest}")
        if selected <= 0:
            errors.append("no selected patch candidate found in smoke run")

    if logs_dir.exists():
        for log in logs_dir.glob("*.log"):
            text = log.read_text(encoding="utf-8", errors="replace")
            if "Traceback" in text and ("ValidationError" in text or "JSONDecodeError" in text):
                errors.append(f"{log.name}: uncaught schema/json exception")
    else:
        errors.append(f"missing logs dir: {logs_dir}")

    for warning in warnings:
        print(f"[gate:warning] {warning}", file=sys.stderr)
    if errors:
        for error in errors:
            print(f"[gate:error] {error}", file=sys.stderr)
        return 1
    print("[gate] MigrationBench V7 smoke gate passed")
    return 0


def inspect_markers(db_path: Path) -> tuple[int, int, int, int]:
    connection = sqlite3.connect(str(db_path))
    try:
        patch_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM markers WHERE marker_type='patch_hypothesis'"
            ).fetchone()[0]
            or 0
        )
        objective_rows = connection.execute(
            """
            SELECT DISTINCT json_extract(payload_json, '$.objective_id')
            FROM markers
            WHERE marker_type='patch_hypothesis'
              AND json_extract(payload_json, '$.objective_id') IS NOT NULL
            """
        ).fetchall()
        selected = int(
            connection.execute(
                """
                SELECT COUNT(*) FROM markers
                WHERE marker_type='patch_hypothesis'
                  AND (
                    json_extract(payload_json, '$.selected_for_official_eval') = 1
                    OR json_extract(payload_json, '$.eligible_actions') LIKE '%finalize_evaluated_patch%'
                  )
                """
            ).fetchone()[0]
            or 0
        )
        lengths = [
            int(row[0] or 0)
            for row in connection.execute(
                """
                SELECT LENGTH(json_extract(payload_json, '$.build_feedback_digest'))
                FROM markers
                WHERE marker_type='patch_hypothesis'
                """
            ).fetchall()
        ]
    finally:
        connection.close()
    return patch_count, len(objective_rows), selected, max(lengths or [0])


if __name__ == "__main__":
    raise SystemExit(main())
