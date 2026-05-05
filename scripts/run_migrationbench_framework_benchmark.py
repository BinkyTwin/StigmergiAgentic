"""Batch runner for one MigrationBench framework arm."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_migrationbench_query_export import load_campaign_config, load_instances


FRAMEWORKS = {
    "no_change",
    "dependency_only_script",
    "solo_direct",
    "solo_cot",
    "solo_self_refine",
    "planner_executor",
    "sd_feedback",
    "agentless_self_debug",
    "stigmergic_v6_static",
    "stigmergic_v7_repair_colony",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--framework", choices=sorted(FRAMEWORKS), required=True)
    parser.add_argument("--subset", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("config/migrationbench_v6_static_deepseek.yaml"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workspace-root", type=Path, default=Path("workspaces/migrationbench"))
    parser.add_argument("--migrationbench-root", type=Path, default=Path("external/MigrationBench"))
    parser.add_argument("--force", action="store_true", default=False)
    parser.add_argument("--skip-official-eval", action="store_true", default=False)
    parser.add_argument("--query-timeout-seconds", type=float, default=None)
    parser.add_argument("--sd-feedback-command", type=str, default="")
    parser.add_argument("--agentless-iterations", type=int, default=3)
    return parser.parse_args(argv)


def extract_last_json(stdout: str) -> dict[str, Any]:
    lines = stdout.splitlines()
    for idx in range(len(lines) - 1, -1, -1):
        if not lines[idx].lstrip().startswith("{"):
            continue
        try:
            payload = json.loads("\n".join(lines[idx:]))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ValueError("No JSON object found in exporter stdout")


def failed_payload(instance: dict[str, Any], framework: str, seed: int, reason: str, runtime: float) -> dict[str, Any]:
    return {
        "instance_id": instance.get("instance_id", ""),
        "framework": framework,
        "provider": "",
        "model": "",
        "seed": seed,
        "artifact_delivered": False,
        "patch_delivered": False,
        "patch_applies": False,
        "official_success": False,
        "strict_success": False,
        "failure_reason": reason,
        "migration_mode": instance.get("migration_mode", "minimal"),
        "target_java": int(instance.get("target_java", 17) or 17),
        "build_success": False,
        "test_success": False,
        "compiled_major_version_ok": None,
        "test_count_non_decreasing": None,
        "dependency_policy_ok": None,
        "tokens_total": 0,
        "cost_total_usd": 0.0,
        "runtime_seconds": round(runtime, 4),
        "repair_cycles": 0,
        "llm_calls": 0,
        "branch_count": 0,
        "best_branch_id": "",
        "failure_taxonomy": "",
        "dynamic_agents_min": None,
        "dynamic_agents_max": None,
        "dynamic_agents_avg": None,
        "caps_hit": {},
        "last_progress_at": None,
        "manual_abort": False,
        "abort_reason": "",
        "files_modified_count": 0,
        "patch_lines_added": 0,
        "patch_lines_deleted": 0,
        "markers_created": 0,
        "coordination_overhead": 0,
        "instance": instance,
    }


def _enrich_failed_payload_from_markers(payload: dict[str, Any], markers_db: Path) -> None:
    """Recover branch_count, repair_cycles, llm telemetry from a markers.db left behind
    by a subprocess that timed out or crashed before writing its output JSON.

    Without this, timeout/crash payloads always report 0 branches and 0 repairs,
    which silently hides V7 progress in campaign aggregates.
    """
    if not markers_db.exists():
        return
    try:
        connection = sqlite3.connect(str(markers_db))
        try:
            branch_ids = {
                str(row[0] or "").strip()
                for row in connection.execute(
                    "SELECT json_extract(payload_json, '$.branch_id') "
                    "FROM markers WHERE marker_type='patch_hypothesis'"
                )
                if str(row[0] or "").strip()
            }
            repair_max = connection.execute(
                "SELECT COALESCE(MAX(CAST(json_extract(payload_json, '$.attempt') AS INTEGER)), 0) "
                "FROM markers WHERE marker_type='patch_hypothesis'"
            ).fetchone()[0] or 0
            patch_count = connection.execute(
                "SELECT COUNT(*) FROM markers WHERE marker_type='patch_hypothesis'"
            ).fetchone()[0] or 0
            latest_taxonomy_row = connection.execute(
                "SELECT json_extract(payload_json, '$.failure_taxonomy') "
                "FROM markers WHERE marker_type='patch_hypothesis' "
                "ORDER BY CAST(json_extract(payload_json, '$.attempt') AS INTEGER) DESC LIMIT 1"
            ).fetchone()
        finally:
            connection.close()
    except Exception:  # noqa: BLE001
        return
    if branch_ids:
        payload["branch_count"] = len(branch_ids)
    if repair_max:
        payload["repair_cycles"] = int(repair_max)
    if patch_count:
        payload["markers_created"] = int(patch_count)
    if latest_taxonomy_row and latest_taxonomy_row[0]:
        payload["failure_taxonomy"] = str(latest_taxonomy_row[0])


def _run_exporter_command(
    command: list[str],
    *,
    timeout_seconds: float | None,
) -> tuple[int, str, str, bool]:
    """Run an exporter command and kill its whole process group on timeout."""
    process = subprocess.Popen(
        command,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
        return int(process.returncode or 0), stdout or "", stderr or "", False
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=10)
        except Exception:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate()
        timeout_msg = f"\n[benchmark] query timed out after {timeout_seconds} seconds\n"
        return 124, stdout or "", (stderr or "") + timeout_msg, True


def run_one(args: argparse.Namespace, instance: dict[str, Any], result_path: Path, log_path: Path) -> dict[str, Any]:
    started = time.perf_counter()
    command = [
        sys.executable,
        "scripts/run_migrationbench_query_export.py",
        "--framework",
        args.framework,
        "--subset",
        str(args.subset),
        "--instance-id",
        str(instance["instance_id"]),
        "--out-dir",
        str(result_path.parent / f"{instance['instance_id']}_artifacts"),
        "--config",
        str(args.config),
        "--seed",
        str(args.seed),
        "--workspace-root",
        str(args.workspace_root),
        "--migrationbench-root",
        str(args.migrationbench_root),
    ]
    if args.force:
        command.append("--force")
    if args.skip_official_eval:
        command.append("--skip-official-eval")
    if args.sd_feedback_command:
        command.extend(["--sd-feedback-command", args.sd_feedback_command])
    if args.agentless_iterations:
        command.extend(["--agentless-iterations", str(args.agentless_iterations)])

    artifacts_dir = result_path.parent / f"{instance['instance_id']}_artifacts"
    returncode, stdout, stderr, timed_out = _run_exporter_command(
        command,
        timeout_seconds=args.query_timeout_seconds,
    )
    log_path.write_text(stdout + "\n" + stderr, encoding="utf-8")
    if timed_out:
        payload = failed_payload(
            instance,
            args.framework,
            args.seed,
            f"timeout_after_{args.query_timeout_seconds:g}s",
            time.perf_counter() - started,
        )
        _enrich_failed_payload_from_markers(payload, artifacts_dir / "markers.db")
        return payload
    if returncode != 0:
        payload = failed_payload(
            instance,
            args.framework,
            args.seed,
            f"exporter_returncode_{returncode}",
            time.perf_counter() - started,
        )
        _enrich_failed_payload_from_markers(payload, artifacts_dir / "markers.db")
        return payload
    try:
        payload = extract_last_json(stdout or "")
    except Exception as exc:  # noqa: BLE001
        payload = failed_payload(
            instance,
            args.framework,
            args.seed,
            f"invalid_exporter_json:{type(exc).__name__}",
            time.perf_counter() - started,
        )
    payload.setdefault("instance", instance)
    return payload


def build_manifest(args: argparse.Namespace, instances: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    llm = dict(config.get("llm", {}))
    monitoring = dict(config.get("migrationbench", {}).get("campaign_monitoring", {}))
    return {
        "campaign_type": "migrationbench_framework",
        "framework": args.framework,
        "subset": str(args.subset),
        "instances": instances,
        "requested_instances": len(instances),
        "seed": int(args.seed),
        "provider": str(llm.get("provider", "")),
        "model": str(llm.get("model", "")),
        "config": str(args.config),
        "migrationbench_root": str(args.migrationbench_root),
        "workspace_root": str(args.workspace_root),
        "official_eval_enabled": not args.skip_official_eval,
        "query_timeout_seconds": args.query_timeout_seconds,
        "campaign_monitoring": monitoring or {
            "mode": "monitor_only",
            "manual_abort_supported": True,
            "record_tokens_runtime_calls_and_cycles": True,
        },
    }


def synthesize_missing(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = {row.get("instance_id") for row in rows}
    out = list(rows)
    for instance in manifest.get("instances", []):
        if instance.get("instance_id") not in seen:
            out.append(
                failed_payload(
                    instance,
                    str(manifest.get("framework", "")),
                    int(manifest.get("seed", 42)),
                    "missing_output",
                    0.0,
                )
            )
    return out


def summarize(manifest: dict[str, Any], rows: list[dict[str, Any]], out_dir: Path) -> dict[str, Any]:
    rows = synthesize_missing(manifest, rows)
    denom = max(1, int(manifest.get("requested_instances", len(rows)) or len(rows)))
    failures = Counter(str(row.get("failure_reason", "ok")) for row in rows)
    strict = sum(1 for row in rows if row.get("strict_success"))
    delivered = sum(1 for row in rows if row.get("artifact_delivered"))
    patch_applies = sum(1 for row in rows if row.get("patch_applies"))
    official = sum(1 for row in rows if row.get("official_success"))
    repair_cycles_total = sum(int(row.get("repair_cycles", 0) or 0) for row in rows)
    llm_calls_total = sum(int(row.get("llm_calls", 0) or 0) for row in rows)
    branch_counts = [int(row.get("branch_count", 0) or 0) for row in rows]
    dynamic_agent_avgs = [
        float(row.get("dynamic_agents_avg", 0.0) or 0.0)
        for row in rows
        if row.get("dynamic_agents_avg") is not None
    ]
    return {
        "framework": manifest.get("framework"),
        "provider": manifest.get("provider"),
        "model": manifest.get("model"),
        "seed": manifest.get("seed"),
        "requested_instances": denom,
        "recorded_rows": len(rows),
        "strict_successes": strict,
        "strict_success_rate": strict / denom,
        "artifact_delivery_rate": delivered / denom,
        "patch_applies_rate": patch_applies / denom,
        "official_success_rate": official / denom,
        "failure_reasons": dict(sorted(failures.items())),
        "tokens_total": sum(int(row.get("tokens_total", 0) or 0) for row in rows),
        "llm_calls_total": llm_calls_total,
        "repair_cycles_total": repair_cycles_total,
        "avg_repair_cycles": round(repair_cycles_total / denom, 4),
        "avg_branch_count": round(sum(branch_counts) / denom, 4) if branch_counts else 0.0,
        "avg_dynamic_agents": round(
            sum(dynamic_agent_avgs) / len(dynamic_agent_avgs),
            4,
        )
        if dynamic_agent_avgs
        else 0.0,
        "cost_total_usd": round(sum(float(row.get("cost_total_usd", 0.0) or 0.0) for row in rows), 6),
        "runtime_total_seconds": round(sum(float(row.get("runtime_seconds", 0.0) or 0.0) for row in rows), 4),
        "avg_coordination_overhead": round(
            sum(float(row.get("coordination_overhead", 0.0) or 0.0) for row in rows) / denom,
            4,
        ),
        "runs_json": str((out_dir / "runs.json").resolve()),
        "official_eval_json": str((out_dir / "official_eval.json").resolve()),
        "manifest_json": str((out_dir / "campaign_manifest.json").resolve()),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = args.out_dir.resolve()
    results_dir = out_dir / "instances"
    logs_dir = out_dir / "logs"
    results_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    instances = [inst.model_dump() for inst in load_instances(args.subset)]
    config = load_campaign_config(args.config)
    if args.query_timeout_seconds is None:
        configured_timeout = config.get("migrationbench", {}).get("query_timeout_seconds")
        if configured_timeout is not None:
            args.query_timeout_seconds = float(configured_timeout)
    manifest = build_manifest(args, instances, config)
    (out_dir / "campaign_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "framework": args.framework,
                "provider": manifest["provider"],
                "model": manifest["model"],
                "seed": args.seed,
                "instances": len(instances),
                "official_eval_enabled": not args.skip_official_eval,
                "query_timeout_seconds": args.query_timeout_seconds,
            },
            sort_keys=True,
        )
    )

    rows: list[dict[str, Any]] = []
    for instance in instances:
        result_path = results_dir / f"{instance['instance_id']}.json"
        if result_path.exists() and not args.force:
            rows.append(json.loads(result_path.read_text(encoding="utf-8")))
            continue
        payload = run_one(
            args=args,
            instance=instance,
            result_path=result_path,
            log_path=logs_dir / f"{instance['instance_id']}.log",
        )
        if not payload.get("provider"):
            payload["provider"] = manifest.get("provider", "")
        if not payload.get("model"):
            payload["model"] = manifest.get("model", "")
        result_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        rows.append(payload)

    full_rows = synthesize_missing(manifest, rows)
    (out_dir / "runs.json").write_text(
        json.dumps({"runs": full_rows}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "official_eval.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "instance_id": row.get("instance_id"),
                        "official_success": row.get("official_success", False),
                        "strict_success": row.get("strict_success", False),
                        "failure_reason": row.get("failure_reason", ""),
                        "official_eval": row.get("official_eval", {}),
                    }
                    for row in full_rows
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    summary = summarize(manifest, rows, out_dir)
    (out_dir / "benchmark_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
