"""Batch benchmark runner for TravelPlanner framework baselines."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FAILURE_TOLERANCE_RATIO = 0.30
LOG_TAIL_LINES = 20


FRAMEWORK_SPECS: dict[str, dict[str, str]] = {
    "solo": {
        "script": "scripts/run_travelplanner_solo_query_export.py",
        "label": "solo_direct",
    },
    "solo_direct": {
        "script": "scripts/run_travelplanner_solo_query_export.py",
        "label": "solo_direct",
    },
    "solo_cot": {
        "script": "scripts/run_travelplanner_cot_query_export.py",
        "label": "solo_cot",
    },
    "solo_self_refine": {
        "script": "scripts/run_travelplanner_self_refine_query_export.py",
        "label": "solo_self_refine",
    },
    "planner_executor": {
        "script": "scripts/run_travelplanner_planner_executor_query_export.py",
        "label": "planner_executor",
    },
    "langgraph_supervisor": {
        "script": "scripts/run_travelplanner_langgraph_query_export.py",
        "label": "langgraph_supervisor",
    },
    "stigmergiagentic": {
        "script": "scripts/run_travelplanner_query_export.py",
        "label": "stigmergiagentic",
    },
    "stigmergic": {
        "script": "scripts/run_travelplanner_query_export.py",
        "label": "stigmergic",
    },
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a batch TravelPlanner benchmark for one framework"
    )
    parser.add_argument(
        "--framework",
        choices=sorted(FRAMEWORK_SPECS),
        required=True,
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--database-root", type=str, default="data/travelplanner/database")
    parser.add_argument("--split", type=str, default="validation")
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--end-index", type=int, default=None)
    parser.add_argument("--start", type=int, default=None)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--max-queries", type=int, default=180)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-ticks", type=int, default=None)
    parser.add_argument("--agents", type=int, default=None)
    parser.add_argument("--max-validation-retries", type=int, default=2)
    parser.add_argument("--query-timeout-seconds", type=float, default=None)
    parser.add_argument("--force", action="store_true", default=False)
    return parser.parse_args(argv)


def extract_last_json(stdout: str) -> dict[str, Any]:
    lines = stdout.splitlines()
    for index in range(len(lines) - 1, -1, -1):
        if not lines[index].lstrip().startswith("{"):
            continue
        candidate = "\n".join(lines[index:]).strip()
        if not candidate:
            continue
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ValueError("Unable to locate a JSON object in command output")


def tail_text(text: str | None, *, max_lines: int = LOG_TAIL_LINES) -> str:
    if not text:
        return ""
    lines = str(text).splitlines()
    return "\n".join(lines[-max_lines:])


def build_query_indices(args: argparse.Namespace) -> list[int]:
    if args.start is not None or args.end is not None:
        start_index = max(0, int(args.start or 0))
        if args.end is not None:
            end_index = max(start_index, int(args.end)) + 1
        else:
            end_index = start_index + max(0, int(args.max_queries))
    else:
        start_index = max(0, int(args.start_index))
        if args.end_index is not None:
            end_index = max(start_index, int(args.end_index))
        else:
            end_index = start_index + max(0, int(args.max_queries))
    return list(range(start_index, end_index))


def build_exporter_command(
    *,
    framework: str,
    args: argparse.Namespace,
    query_idx: int,
) -> list[str]:
    spec = FRAMEWORK_SPECS[framework]
    command = [
        sys.executable,
        spec["script"],
        "--objective",
        f"Query {query_idx}",
        "--query-idx",
        str(query_idx),
        "--seed",
        str(args.seed),
    ]
    if args.config:
        command.extend(["--config", str(args.config)])
    if framework in {"stigmergiagentic", "stigmergic"}:
        if args.max_ticks is not None:
            command.extend(["--max-ticks", str(args.max_ticks)])
        if args.agents is not None:
            command.extend(["--agents", str(args.agents)])
    if framework == "langgraph_supervisor":
        command.extend(["--max-validation-retries", str(args.max_validation_retries)])
    return command


def coordination_overhead_for(framework: str, payload: dict[str, Any]) -> int:
    summary = payload.get("summary", {})
    if not isinstance(summary, dict):
        return 0
    existing = summary.get("coordination_overhead")
    if existing is not None:
        try:
            return int(existing)
        except Exception:  # noqa: BLE001
            pass
    if framework in {"solo", "solo_direct", "solo_cot"}:
        return 1
    if framework == "solo_self_refine":
        trace = summary.get("step_trace", [])
        if isinstance(trace, list):
            return sum(
                1
                for item in trace
                if isinstance(item, dict)
                and str(item.get("node", "")).startswith(
                    ("self_refine_draft", "self_refine_critic", "self_refine_reviser")
                )
            )
        return 2
    if framework == "planner_executor":
        trace = summary.get("step_trace", [])
        if isinstance(trace, list):
            return sum(
                1
                for item in trace
                if isinstance(item, dict)
                and str(item.get("node", "")).startswith(("central_planner", "central_executor"))
            )
        return 2
    if framework == "langgraph_supervisor":
        trace = summary.get("step_trace", [])
        return len(trace) if isinstance(trace, list) else int(summary.get("coordination_overhead", 0))
    if framework in {"stigmergiagentic", "stigmergic"}:
        return int(summary.get("total_ticks", 0) or 0)
    return 0


def infer_failure_reason(payload: dict[str, Any]) -> str:
    explicit = str(payload.get("failure_reason", "")).strip()
    if explicit:
        return explicit

    evaluation = payload.get("evaluation", {})
    if isinstance(evaluation, dict):
        nested = str(evaluation.get("failure_reason", "")).strip()
        if nested:
            return nested
        query_results = evaluation.get("query_results", [])
        if isinstance(query_results, list) and query_results:
            first = query_results[0]
            if isinstance(first, dict):
                nested = str(first.get("failure_reason", "")).strip()
                if nested:
                    return nested

    summary = payload.get("summary", {})
    if isinstance(summary, dict):
        stop_reason = str(summary.get("stop_reason", "")).strip()
        if stop_reason in {"budget_exhausted", "idle_cycles", "max_ticks"}:
            return stop_reason

    return "ok"


def augment_payload(
    *,
    framework: str,
    payload: dict[str, Any],
    runtime_seconds: float,
    seed: int | None,
) -> dict[str, Any]:
    updated = dict(payload)
    summary = dict(updated.get("summary", {}))
    summary.setdefault("framework", framework)
    summary.setdefault("seed", seed)
    summary.setdefault("step_trace", [])
    summary.setdefault("validation_failures", [])
    summary.setdefault("retry_count", 0)
    summary.setdefault("search_payload_keys", [])
    summary.setdefault("run_status", "success")
    summary["runtime_seconds"] = round(runtime_seconds, 4)
    summary["coordination_overhead"] = coordination_overhead_for(framework, updated)
    failure_reason = infer_failure_reason(updated)
    updated["failure_reason"] = failure_reason
    summary.setdefault("failure_reason", failure_reason)
    updated["summary"] = summary
    return updated


def failed_query_payload(
    *,
    framework: str,
    query_idx: int,
    runtime_seconds: float,
    seed: int | None,
    failure_reason: str,
    stderr_tail: str,
    stdout_tail: str = "",
    returncode: int | None = None,
    error_message: str = "",
    error_type: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "query_idx": query_idx,
        "status": "failed",
        "final_pass": False,
        "final_plan": [],
        "plan": [],
        "failure_reason": failure_reason,
        "stderr_tail": stderr_tail,
        "stdout_tail": stdout_tail,
        "summary": {
            "run_status": "failed",
            "failure_reason": failure_reason,
        },
    }
    if returncode is not None:
        payload["returncode"] = returncode
    if error_message:
        payload["error_message"] = error_message
    if error_type:
        payload["error_type"] = error_type
    return augment_payload(
        framework=framework,
        payload=payload,
        runtime_seconds=runtime_seconds,
        seed=seed,
    )


def execute_query_export(
    *,
    framework: str,
    args: argparse.Namespace,
    query_idx: int,
    command: list[str],
    log_path: Path,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=args.query_timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        runtime_seconds = time.perf_counter() - started_at
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        log_path.write_text(
            stdout
            + ("\n" if stdout and not stdout.endswith("\n") else "")
            + stderr
            + (
                "" if stderr.endswith("\n") or not stderr else "\n"
            )
            + f"[benchmark] query timed out after {args.query_timeout_seconds} seconds\n",
            encoding="utf-8",
        )
        return failed_query_payload(
            framework=framework,
            query_idx=query_idx,
            runtime_seconds=runtime_seconds,
            seed=args.seed,
            failure_reason="timeout",
            stderr_tail=tail_text(stderr) or tail_text(log_path.read_text(encoding="utf-8")),
            stdout_tail=tail_text(stdout),
            error_message=str(exc),
            error_type=type(exc).__name__,
        )
    except Exception as exc:  # noqa: BLE001
        runtime_seconds = time.perf_counter() - started_at
        message = f"[benchmark] exporter crashed before completion: {exc}\n"
        log_path.write_text(message, encoding="utf-8")
        return failed_query_payload(
            framework=framework,
            query_idx=query_idx,
            runtime_seconds=runtime_seconds,
            seed=args.seed,
            failure_reason="exporter_crash",
            stderr_tail=tail_text(message),
            error_message=str(exc),
            error_type=type(exc).__name__,
        )

    runtime_seconds = time.perf_counter() - started_at
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    log_path.write_text(
        stdout + ("\n" if stdout and not stdout.endswith("\n") else "") + stderr,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        return failed_query_payload(
            framework=framework,
            query_idx=query_idx,
            runtime_seconds=runtime_seconds,
            seed=args.seed,
            failure_reason="returncode_nonzero",
            stderr_tail=tail_text(stderr) or tail_text(log_path.read_text(encoding="utf-8")),
            stdout_tail=tail_text(stdout),
            returncode=completed.returncode,
        )

    try:
        payload = extract_last_json(stdout)
    except ValueError as exc:
        return failed_query_payload(
            framework=framework,
            query_idx=query_idx,
            runtime_seconds=runtime_seconds,
            seed=args.seed,
            failure_reason="exporter_crash",
            stderr_tail=tail_text(stderr),
            stdout_tail=tail_text(stdout),
            returncode=completed.returncode,
            error_message=str(exc),
            error_type=type(exc).__name__,
        )

    return augment_payload(
        framework=framework,
        payload=payload,
        runtime_seconds=runtime_seconds,
        seed=args.seed,
    )


def write_runs_json(path: Path, runs: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"runs": runs}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def build_benchmark_summary(
    *,
    framework: str,
    run_tag_dir: Path,
    runs: list[dict[str, Any]],
    queries_requested: int,
    runs_json: Path,
    official_eval_json: Path,
    total_runtime_seconds: float,
) -> dict[str, Any]:
    total_queries = len(runs)
    tokens = 0
    cost = 0.0
    runtime = 0.0
    overhead = 0
    final_passes = 0
    succeeded_queries = 0
    failure_reasons: dict[str, int] = {}
    for run in runs:
        summary = run.get("summary", {})
        if not isinstance(summary, dict):
            continue
        tokens += int(summary.get("tokens_used", 0) or 0)
        cost += float(summary.get("cost_used", 0.0) or 0.0)
        runtime += float(summary.get("runtime_seconds", 0.0) or 0.0)
        overhead += int(summary.get("coordination_overhead", 0) or 0)
        if bool(run.get("final_pass", False)):
            final_passes += 1
        failure_reason = infer_failure_reason(run)
        if failure_reason == "ok":
            succeeded_queries += 1
        failure_reasons[failure_reason] = failure_reasons.get(failure_reason, 0) + 1

    denom = queries_requested if queries_requested > 0 else 1
    failed_queries = queries_requested - succeeded_queries
    return {
        "framework": framework,
        "output_root": str(run_tag_dir.resolve()),
        "queries": total_queries,
        "queries_requested": queries_requested,
        "queries_recorded": total_queries,
        "queries_succeeded": succeeded_queries,
        "final_passes": final_passes,
        "failed_queries": failed_queries,
        "failure_reasons": dict(sorted(failure_reasons.items())),
        "final_pass_rate_raw": final_passes / denom if total_queries else 0.0,
        "success_rate": succeeded_queries / denom if queries_requested else 0.0,
        "tokens_total": tokens,
        "cost_total_usd": round(cost, 6),
        "runtime_total_seconds": round(runtime, 4),
        "runtime_wall_seconds": round(total_runtime_seconds, 4),
        "avg_tokens_per_query": round(tokens / denom, 2),
        "avg_cost_per_query_usd": round(cost / denom, 6),
        "avg_runtime_per_query_seconds": round(runtime / denom, 4),
        "avg_coordination_overhead": round(overhead / denom, 2),
        "failure_tolerance_ratio": FAILURE_TOLERANCE_RATIO,
        "failure_tolerance_exceeded": (failed_queries / denom) > FAILURE_TOLERANCE_RATIO,
        "official_eval_semantics": {
            "evaluates_requested_range": True,
            "missing_query_prediction": "treated_as_empty_plan",
            "missing_query_plan_value": [],
            "denominator_note": "Campaign robustness improves resumability and failure traceability without changing the official evaluation denominator.",
        },
        "runs_json": str(runs_json.resolve()),
        "official_eval_json": str(official_eval_json.resolve()),
    }


def run_official_eval(
    *,
    runs_json: Path,
    database_root: str,
    split: str,
    official_eval_json: Path,
    official_eval_log: Path,
    start_index: int | None = None,
    end_index: int | None = None,
) -> None:
    command = [
        sys.executable,
        "scripts/eval_travelplanner_official.py",
        "--runs-json",
        str(runs_json),
        "--database-root",
        str(database_root),
        "--split",
        split,
        "--out",
        str(official_eval_json),
    ]
    if start_index is not None:
        command.extend(["--start-index", str(start_index)])
    if end_index is not None:
        command.extend(["--end-index", str(end_index)])
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    official_eval_log.parent.mkdir(parents=True, exist_ok=True)
    official_eval_log.write_text(
        completed.stdout + ("\n" if completed.stdout and not completed.stdout.endswith("\n") else "") + completed.stderr,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Official scorer failed (exit={completed.returncode}): {' '.join(command)}"
        )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    framework = args.framework
    out_dir = args.out_dir.expanduser().resolve()
    query_dir = out_dir / "queries"
    logs_dir = out_dir / "logs"
    runs_json = out_dir / "runs.json"
    official_eval_json = out_dir / "official_eval.json"
    benchmark_summary_json = out_dir / "benchmark_summary.json"
    query_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    query_indices = build_query_indices(args)
    runs: list[dict[str, Any]] = []
    all_started_at = time.perf_counter()
    for query_idx in query_indices:
        result_path = query_dir / f"query_{query_idx:03d}.json"
        if result_path.exists() and not args.force:
            runs.append(json.loads(result_path.read_text(encoding="utf-8")))
            continue

        command = build_exporter_command(framework=framework, args=args, query_idx=query_idx)
        log_path = logs_dir / f"query_{query_idx:03d}.log"
        payload = execute_query_export(
            framework=framework,
            args=args,
            query_idx=query_idx,
            command=command,
            log_path=log_path,
        )
        result_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        runs.append(payload)

    write_runs_json(runs_json, runs)
    subset_start_index = query_indices[0] if query_indices else None
    subset_end_index = query_indices[-1] + 1 if query_indices else None
    run_official_eval(
        runs_json=runs_json,
        database_root=args.database_root,
        split=args.split,
        official_eval_json=official_eval_json,
        official_eval_log=logs_dir / "official_eval.log",
        start_index=subset_start_index,
        end_index=subset_end_index,
    )
    benchmark_summary = build_benchmark_summary(
        framework=framework,
        run_tag_dir=out_dir,
        runs=runs,
        queries_requested=len(query_indices),
        runs_json=runs_json,
        official_eval_json=official_eval_json,
        total_runtime_seconds=time.perf_counter() - all_started_at,
    )
    benchmark_summary_json.write_text(
        json.dumps(benchmark_summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if benchmark_summary["failure_tolerance_exceeded"]:
        print(
            (
                "[benchmark] warning: failed query ratio exceeded tolerance "
                f"({benchmark_summary['failed_queries']}/{benchmark_summary['queries_requested']} > "
                f"{benchmark_summary['failure_tolerance_ratio']:.0%})"
            ),
            file=sys.stderr,
        )
    print(json.dumps(benchmark_summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
