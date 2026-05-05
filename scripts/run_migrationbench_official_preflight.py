"""Official MigrationBench preflight on selected repositories before adapter claims."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.migrationbench.workspace import MigrationBenchWorkspace, run_command
from scripts.run_migrationbench_query_export import load_instances


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subset", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--migrationbench-root", type=Path, default=Path("external/MigrationBench"))
    parser.add_argument("--workspace-root", type=Path, default=Path("workspaces/migrationbench_preflight"))
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--force", action="store_true", default=False)
    parser.add_argument("--timeout-seconds", type=float, default=1800)
    return parser.parse_args()


def git_commit(path: Path) -> str:
    result = run_command(["git", "rev-parse", "HEAD"], cwd=path)
    return result.stdout.strip() if result.ok else ""


def parse_success(text: str) -> bool:
    return "Success = True" in text or "Migration success (count) `True`" in text or "Migration success (count) `1`" in text


def official_eval_env(migrationbench_root: Path) -> dict[str, str]:
    """Expose MigrationBench's package root when calling its script directly."""
    env = os.environ.copy()
    src_path = str((migrationbench_root / "src").resolve())
    current = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = src_path if not current else f"{src_path}{os.pathsep}{current}"
    return env


def run_preflight_instance(args: argparse.Namespace, instance: Any) -> dict[str, Any]:
    started = time.perf_counter()
    row: dict[str, Any] = {
        "instance_id": instance.instance_id,
        "repo_url": instance.repo_url,
        "base_commit": instance.base_commit,
        "clone_checkout_ok": False,
        "official_eval_ran": False,
        "official_base_java8_success": False,
        "failure_reason": "unknown",
        "runtime_seconds": 0.0,
    }
    log_dir = args.out_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    workspace = MigrationBenchWorkspace(
        instance=instance,
        root_dir=args.workspace_root / instance.instance_id,
        timeout_seconds=args.timeout_seconds,
    )
    try:
        workspace.prepare(force=args.force)
        row["clone_checkout_ok"] = True
    except Exception as exc:  # noqa: BLE001
        row["failure_reason"] = f"clone_checkout_failed:{type(exc).__name__}:{exc}"
        row["runtime_seconds"] = round(time.perf_counter() - started, 4)
        return row

    script = args.migrationbench_root / "src" / "migration_bench" / "run_eval.py"
    if not script.exists():
        row["failure_reason"] = "official_evaluator_missing"
        row["runtime_seconds"] = round(time.perf_counter() - started, 4)
        return row
    command = [
        sys.executable,
        str(script.resolve()),
        "--github_url",
        instance.repo_url,
        "--migrated_root_dir",
        str(workspace.repo_dir),
        "--base_commit_id",
        instance.base_commit,
        "--is_maximal_migration",
        "0",
        "--require_compiled_java_major_version",
        "52",
        "--max_workers",
        "1",
    ]
    completed = subprocess.run(
        command,
        cwd=args.migrationbench_root,
        env=official_eval_env(args.migrationbench_root),
        text=True,
        capture_output=True,
        check=False,
        timeout=args.timeout_seconds,
    )
    combined = (completed.stdout or "") + "\n" + (completed.stderr or "")
    (log_dir / f"{instance.instance_id}.log").write_text(combined, encoding="utf-8")
    row.update(
        {
            "official_eval_ran": True,
            "official_eval_process_ok": completed.returncode == 0,
            "official_base_java8_success": parse_success(combined),
            "official_eval_returncode": completed.returncode,
            "official_eval_command": command,
            "stdout_tail": (completed.stdout or "")[-3000:],
            "stderr_tail": (completed.stderr or "")[-3000:],
        }
    )
    row["failure_reason"] = "ok" if row["official_eval_process_ok"] else "official_eval_process_failed"
    row["runtime_seconds"] = round(time.perf_counter() - started, 4)
    return row


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    instances = load_instances(args.subset)[: max(0, int(args.limit))]
    rows = [run_preflight_instance(args, instance) for instance in instances]
    failures = Counter(row["failure_reason"] for row in rows)
    setup_failures = sum(
        1
        for row in rows
        if not row.get("clone_checkout_ok")
        or not row.get("official_eval_ran")
        or not row.get("official_eval_process_ok", False)
    )
    denom = len(rows) or 1
    manifest = {
        "campaign_type": "migrationbench_official_preflight",
        "subset": str(args.subset),
        "instances": [instance.model_dump() for instance in instances],
        "requested_instances": len(instances),
        "migrationbench_root": str(args.migrationbench_root),
        "migrationbench_commit": git_commit(args.migrationbench_root),
        "official_evaluator": str((args.migrationbench_root / "src" / "migration_bench" / "run_eval.py").resolve()),
        "preflight_semantics": (
            "Clone/checkout plus official evaluator process smoke. "
            "Base Java 8 success is diagnostic only because unmigrated repositories "
            "are not expected to satisfy the final migration contract."
        ),
    }
    summary = {
        "requested_instances": len(rows),
        "clone_checkout_ok": sum(1 for row in rows if row.get("clone_checkout_ok")),
        "official_eval_ran": sum(1 for row in rows if row.get("official_eval_ran")),
        "official_eval_process_ok": sum(1 for row in rows if row.get("official_eval_process_ok")),
        "official_base_java8_successes": sum(1 for row in rows if row.get("official_base_java8_success")),
        "official_base_java8_success_rate": (
            sum(1 for row in rows if row.get("official_base_java8_success")) / denom
        ),
        "setup_failure_rate": setup_failures / denom,
        "mortality_gate_exceeded": (setup_failures / denom) > 0.10,
        "failure_reasons": dict(sorted(failures.items())),
    }
    (args.out_dir / "campaign_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.out_dir / "official_eval.json").write_text(json.dumps({"rows": rows}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.out_dir / "benchmark_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
