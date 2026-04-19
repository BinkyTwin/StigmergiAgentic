"""Run SwarmAgentic TravelPlanner benchmarks with benchmark-mode status artifacts."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shlex
import shutil
import signal
import select
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PREPARE_SCRIPT = REPO_ROOT / "scripts" / "prepare_swarmagentic_openrouter.py"
EXPORT_STATE_SCRIPT = REPO_ROOT / "scripts" / "export_swarmagentic_save_jsonl.py"
CONVERT_RESULTS_SCRIPT = REPO_ROOT / "scripts" / "convert_swarmagentic_travelplanner_results.py"
OFFICIAL_EVAL_SCRIPT = REPO_ROOT / "scripts" / "eval_travelplanner_official.py"
PATCH_REVISION = "swarm-openrouter-20260407-monitoring-v1"

VALID_MODES = {"preflight", "pilot", "full"}
PROVIDER_FAILURE_PATTERNS = (
    "The operation was aborted",
    "Provider returned error",
    "'code': 504",
    '"code": 504',
    "code': 504",
    "code: 504",
)
WATCHDOG_FAILURE_PATTERNS = (
    "[WATCHDOG]",
    "idle timeout exceeded",
)
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 30
DEFAULT_IDLE_TIMEOUT_SECONDS = 600
DEFAULT_LOG_TAIL_LINES = 12

PAPER_CONTEXT = {
    "sources": {
        "swarmagentic_paper": "https://aclanthology.org/2025.emnlp-main.93.pdf",
        "travelplanner_paper": "https://openreview.net/pdf/e9fe4b4f56f555d4eb81bfd90c1b9a501e7a57dd.pdf",
        "swarmagentic_repo": "https://github.com/YaoZ720/SwarmAgenticCode",
    },
    "paper_protocol": {
        "train_queries": 9,
        "validation_queries": 180,
        "particles": 5,
        "iterations": 10,
        "optimizer_model": "GPT-4o-mini-0718",
        "executor_models": ["GPT-3.5-turbo-0125", "GPT-4o-0806"],
    },
    "repo_protocol_inference": {
        "train_file": "train_45.jsonl",
        "sample_step": 5,
        "effective_train_queries": 9,
        "note": "Public README documents train_45.jsonl; pso.py default sample_step=5 loads 9 effective examples.",
    },
    "paper_scores": {
        "gpt_3_5": {
            "delivery_rate": 1.0,
            "commonsense_micro": 0.709,
            "commonsense_macro": 0.128,
            "hard_constraint_micro": 0.21,
            "hard_constraint_macro": 0.094,
            "final_pass_rate": 0.033,
        },
        "gpt_4o": {
            "delivery_rate": 1.0,
            "commonsense_micro": 0.929,
            "commonsense_macro": 0.561,
            "hard_constraint_micro": 0.667,
            "hard_constraint_macro": 0.528,
            "final_pass_rate": 0.322,
        },
    },
}


@dataclass(slots=True)
class CommandResult:
    returncode: int
    output: str
    command: list[str]


class BenchmarkFailure(RuntimeError):
    """Expected benchmark failure classified into infra/framework buckets."""

    def __init__(self, *, status: str, phase: str, output: str, command: list[str]) -> None:
        super().__init__(f"{status} during {phase}: {shlex.join(command)}")
        self.status = status
        self.phase = phase
        self.output = output
        self.command = command


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run SwarmAgentic TravelPlanner benchmarks with preflight/pilot/full modes"
    )
    parser.add_argument("--swarm-root", type=Path, required=True, help="Output root for SwarmAgentic benchmark artifacts")
    parser.add_argument("--mode", type=str, default="full", choices=sorted(VALID_MODES))
    parser.add_argument("--model", type=str, required=True)
    parser.add_argument("--base-url", type=str, default="https://openrouter.ai/api/v1")
    parser.add_argument("--extract-model", type=str, default=None)
    parser.add_argument("--split", type=str, default="validation")
    parser.add_argument("--database-root", type=Path, default=Path("data/travelplanner/database"))
    parser.add_argument("--sample-step", type=int, default=5)
    parser.add_argument("--max-queries", type=int, default=180)
    parser.add_argument("--max-iteration", type=int, default=10)
    parser.add_argument("--preflight-iteration", type=int, default=1)
    parser.add_argument("--pilot-iteration", type=int, default=2)
    parser.add_argument("--pilot-queries", type=int, default=20)
    parser.add_argument("--eval-shard-size", type=int, default=20)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--heartbeat-interval-seconds", type=int, default=DEFAULT_HEARTBEAT_INTERVAL_SECONDS)
    parser.add_argument("--idle-timeout-seconds", type=int, default=DEFAULT_IDLE_TIMEOUT_SECONDS)
    parser.add_argument("--disable-idle-watchdog", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--skip-train", action="store_true")
    parser.add_argument("--clone-swarm", action="store_true")
    parser.add_argument("--install-swarm-deps", action="store_true")
    return parser.parse_args()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def format_duration(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    minutes, sec = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{sec:02d}s"
    return f"{minutes}m{sec:02d}s"


def compact_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except Exception:
        return str(path)


def tail_text(path: Path, max_lines: int = DEFAULT_LOG_TAIL_LINES) -> list[str]:
    if not path.exists() or not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-max_lines:]


def terminate_process_group(proc: subprocess.Popen[str], *, grace_seconds: float = 5.0) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except Exception:
        proc.terminate()
    deadline = time.monotonic() + grace_seconds
    while proc.poll() is None and time.monotonic() < deadline:
        time.sleep(0.2)
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        except Exception:
            proc.kill()


def process_snapshot(pid: int | None) -> dict[str, Any]:
    if not pid:
        return {"pid": None, "ps": ""}
    proc = subprocess.run(
        ["ps", "-o", "pid,ppid,stat,%cpu,%mem,etime,rss,command", "-p", str(pid)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "pid": pid,
        "ps": proc.stdout.strip(),
        "returncode": proc.returncode,
    }


def snapshot_path(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": str(path),
            "label": compact_path(path),
            "exists": False,
        }

    stat = path.stat()
    if path.is_file():
        return {
            "path": str(path),
            "label": compact_path(path),
            "exists": True,
            "kind": "file",
            "size_bytes": stat.st_size,
            "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        }

    latest_file: Path | None = None
    latest_mtime = 0.0
    file_count = 0
    total_size = 0
    for item in path.rglob("*"):
        if not item.is_file():
            continue
        file_count += 1
        item_stat = item.stat()
        total_size += item_stat.st_size
        if item_stat.st_mtime >= latest_mtime:
            latest_mtime = item_stat.st_mtime
            latest_file = item

    payload: dict[str, Any] = {
        "path": str(path),
        "label": compact_path(path),
        "exists": True,
        "kind": "dir",
        "file_count": file_count,
        "total_size_bytes": total_size,
        "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }
    if latest_file is not None:
        payload["latest_file"] = compact_path(latest_file)
        payload["latest_mtime_utc"] = datetime.fromtimestamp(latest_mtime, timezone.utc).isoformat()
    return payload


def snapshot_watched_paths(paths: list[Path]) -> dict[str, dict[str, Any]]:
    return {str(path): snapshot_path(path) for path in paths}


def snapshot_signature(summary: dict[str, Any]) -> tuple[Any, ...]:
    return (
        summary.get("exists"),
        summary.get("kind"),
        summary.get("size_bytes"),
        summary.get("mtime_utc"),
        summary.get("file_count"),
        summary.get("total_size_bytes"),
        summary.get("latest_file"),
        summary.get("latest_mtime_utc"),
    )


def watched_snapshot_changed(previous: dict[str, dict[str, Any]], current: dict[str, dict[str, Any]]) -> bool:
    keys = set(previous) | set(current)
    for key in keys:
        if snapshot_signature(previous.get(key, {})) != snapshot_signature(current.get(key, {})):
            return True
    return False


def compact_watch_summary(snapshot: dict[str, dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in snapshot.values():
        label = item.get("label", item.get("path", "unknown"))
        if not item.get("exists"):
            parts.append(f"{label}=missing")
        elif item.get("kind") == "file":
            parts.append(f"{label}=file:{item.get('size_bytes', 0)}B")
        else:
            latest_file = item.get("latest_file", "-")
            parts.append(
                f"{label}=dir:{item.get('file_count', 0)} files latest={Path(str(latest_file)).name if latest_file != '-' else '-'}"
            )
    return "; ".join(parts)


def merge_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    if extra:
        env.update({key: str(value) for key, value in extra.items()})
    return env


def stream_command(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    log_path: Path | None = None,
) -> CommandResult:
    print("$", shlex.join(cmd), flush=True)
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd is not None else None,
        env=merge_env(env),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    lines: list[str] = []
    assert proc.stdout is not None
    for raw in proc.stdout:
        lines.append(raw)
        print(raw.rstrip("\n"), flush=True)
    proc.wait()
    output = "".join(lines)
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(output, encoding="utf-8")
    return CommandResult(returncode=proc.returncode, output=output, command=cmd)


def stream_command_monitored(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    log_path: Path,
    phase: str,
    status: dict[str, Any],
    mode_root: Path,
    watched_paths: list[Path] | None = None,
    heartbeat_interval_seconds: int = DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    idle_timeout_seconds: int | None = DEFAULT_IDLE_TIMEOUT_SECONDS,
) -> CommandResult:
    watched_paths = watched_paths or []
    monitor_path = mode_root / "live_monitor.json"
    heartbeat_log = mode_root / "logs" / "heartbeat.log"
    heartbeat_log.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    print("$", shlex.join(cmd), flush=True)
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=merge_env(env),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        start_new_session=True,
    )

    started_at = time.monotonic()
    last_output_at = started_at
    last_progress_at = started_at
    last_heartbeat_at = started_at
    heartbeat_count = 0
    watchdog_triggered = False
    initial_snapshot = snapshot_watched_paths(watched_paths)
    last_snapshot = initial_snapshot
    lines: list[str] = []

    status.setdefault("monitoring", {})
    status["monitoring"].update(
        {
            "current_phase": phase,
            "last_child_output_utc": None,
            "last_progress_utc": None,
            "last_heartbeat_utc": None,
            "heartbeat_count": heartbeat_count,
            "watchdog_triggered": False,
            "watched_paths": [str(path.resolve()) for path in watched_paths],
            "last_watch_summary": initial_snapshot,
            "current_process": process_snapshot(proc.pid),
        }
    )
    update_status_artifacts(mode_root, status)

    def flush_monitor(current_snapshot: dict[str, dict[str, Any]], *, note: str | None = None) -> None:
        nonlocal heartbeat_count
        process_info = process_snapshot(proc.pid)
        monitor_payload = {
            "timestamp_utc": utc_now_iso(),
            "phase": phase,
            "command": cmd,
            "cwd": str(cwd),
            "pid": proc.pid,
            "returncode": proc.poll(),
            "elapsed_seconds": round(time.monotonic() - started_at, 3),
            "last_child_output_seconds_ago": round(time.monotonic() - last_output_at, 3),
            "last_progress_seconds_ago": round(time.monotonic() - last_progress_at, 3),
            "watchdog_triggered": watchdog_triggered,
            "heartbeat_count": heartbeat_count,
            "watched_paths": current_snapshot,
            "process": process_info,
        }
        if note:
            monitor_payload["note"] = note
        serialize_json(monitor_path, monitor_payload)
        status["monitoring"].update(
            {
                "current_phase": phase,
                "last_heartbeat_utc": monitor_payload["timestamp_utc"],
                "heartbeat_count": heartbeat_count,
                "watchdog_triggered": watchdog_triggered,
                "last_watch_summary": current_snapshot,
                "current_process": process_info,
            }
        )
        update_status_artifacts(mode_root, status)

    normalized_idle_timeout = None if idle_timeout_seconds is None else max(1, idle_timeout_seconds)
    heartbeat_interval_seconds = max(1, heartbeat_interval_seconds)

    with log_path.open("w", encoding="utf-8") as log_file, heartbeat_log.open("a", encoding="utf-8") as heartbeat_file:
        while True:
            current_snapshot = snapshot_watched_paths(watched_paths)
            if watched_snapshot_changed(last_snapshot, current_snapshot):
                last_progress_at = time.monotonic()
                last_snapshot = current_snapshot
                watch_line = (
                    f"[WATCH] phase={phase} elapsed={format_duration(time.monotonic() - started_at)} "
                    f"activity={compact_watch_summary(current_snapshot)}"
                )
                print(watch_line, flush=True)
                heartbeat_file.write(watch_line + "\n")
                heartbeat_file.flush()
                flush_monitor(current_snapshot, note="watched-path activity")

            if proc.stdout is not None:
                ready, _, _ = select.select([proc.stdout], [], [], 1.0)
                if ready:
                    raw = proc.stdout.readline()
                    if raw:
                        lines.append(raw)
                        log_file.write(raw)
                        log_file.flush()
                        print(raw.rstrip("\n"), flush=True)
                        last_output_at = time.monotonic()
                        last_progress_at = last_output_at
                        status["monitoring"]["last_child_output_utc"] = utc_now_iso()
                        status["monitoring"]["last_progress_utc"] = status["monitoring"]["last_child_output_utc"]
                    elif proc.poll() is not None:
                        break
            if proc.poll() is not None and proc.stdout is not None:
                remaining = proc.stdout.read()
                if remaining:
                    lines.append(remaining)
                    log_file.write(remaining)
                    log_file.flush()
                    print(remaining.rstrip("\n"), flush=True)
                break

            now = time.monotonic()
            if now - last_heartbeat_at >= heartbeat_interval_seconds:
                heartbeat_count += 1
                heartbeat_line = (
                    f"[HEARTBEAT] phase={phase} elapsed={format_duration(now - started_at)} "
                    f"since_output={format_duration(now - last_output_at)} "
                    f"since_progress={format_duration(now - last_progress_at)} "
                    f"watch={compact_watch_summary(current_snapshot)}"
                )
                print(heartbeat_line, flush=True)
                heartbeat_file.write(heartbeat_line + "\n")
                heartbeat_file.flush()
                flush_monitor(current_snapshot, note="heartbeat")
                last_heartbeat_at = now

            if normalized_idle_timeout is not None and (now - last_progress_at) >= normalized_idle_timeout and proc.poll() is None:
                watchdog_triggered = True
                timeout_line = (
                    f"[WATCHDOG] phase={phase} idle timeout exceeded after {format_duration(now - last_progress_at)} "
                    f"without child output or watched-path changes."
                )
                print(timeout_line, flush=True)
                lines.append(timeout_line + "\n")
                log_file.write(timeout_line + "\n")
                log_file.flush()
                heartbeat_file.write(timeout_line + "\n")
                heartbeat_file.flush()
                terminate_process_group(proc)
                flush_monitor(current_snapshot, note="watchdog timeout")
                break

        proc.wait()

    output = "".join(lines)
    return CommandResult(returncode=proc.returncode, output=output, command=cmd)


def is_provider_failure(output: str) -> bool:
    return any(pattern in output for pattern in PROVIDER_FAILURE_PATTERNS)


def is_watchdog_failure(output: str) -> bool:
    return any(pattern in output for pattern in WATCHDOG_FAILURE_PATTERNS)


def count_provider_failures(output: str) -> int:
    count = 0
    for pattern in PROVIDER_FAILURE_PATTERNS:
        count += output.count(pattern)
    return count


def serialize_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def render_context_markdown(*, mode: str, model: str) -> str:
    def pct(value: float) -> str:
        return f"{value * 100:.1f}"

    gpt35 = PAPER_CONTEXT["paper_scores"]["gpt_3_5"]
    gpt4o = PAPER_CONTEXT["paper_scores"]["gpt_4o"]
    protocol = PAPER_CONTEXT["paper_protocol"]
    repo_protocol = PAPER_CONTEXT["repo_protocol_inference"]
    sources = PAPER_CONTEXT["sources"]
    lines = [
        "## SwarmAgentic Context",
        "",
        f"This notebook benchmark uses `{model}` in `{mode}` mode. The paper numbers below are context only and are **not directly comparable** to the Qwen/OpenRouter benchmark.",
        "",
        "| Source | Optimizer | Executor | Train | Eval | Delivery | Commonsense Micro | Commonsense Macro | Hard Constraint Micro | Hard Constraint Macro | Final |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        f"| SwarmAgentic paper (GPT-3.5 column) | {protocol['optimizer_model']} | {protocol['executor_models'][0]} | {protocol['train_queries']} representative queries | validation {protocol['validation_queries']} | {pct(gpt35['delivery_rate'])} | {pct(gpt35['commonsense_micro'])} | {pct(gpt35['commonsense_macro'])} | {pct(gpt35['hard_constraint_micro'])} | {pct(gpt35['hard_constraint_macro'])} | {pct(gpt35['final_pass_rate'])} |",
        f"| SwarmAgentic paper (GPT-4o column) | {protocol['optimizer_model']} | {protocol['executor_models'][1]} | {protocol['train_queries']} representative queries | validation {protocol['validation_queries']} | {pct(gpt4o['delivery_rate'])} | {pct(gpt4o['commonsense_micro'])} | {pct(gpt4o['commonsense_macro'])} | {pct(gpt4o['hard_constraint_micro'])} | {pct(gpt4o['hard_constraint_macro'])} | {pct(gpt4o['final_pass_rate'])} |",
        "",
        "Methodology note:",
        f"The public repo documents `{repo_protocol['train_file']}`, but its default `sample_step={repo_protocol['sample_step']}` loads {repo_protocol['effective_train_queries']} effective examples. This is a reasonable implementation-level match to the paper's 9-query training protocol.",
        "",
        "Sources:",
        f"- [SwarmAgentic EMNLP 2025]({sources['swarmagentic_paper']})",
        f"- [TravelPlanner ICML 2024]({sources['travelplanner_paper']})",
        f"- [SwarmAgentic official repository]({sources['swarmagentic_repo']})",
    ]
    return "\n".join(lines) + "\n"


def render_reproducibility_markdown(status: dict[str, Any]) -> str:
    artifacts = status.get("artifacts", {})
    monitoring = status.get("monitoring", {})
    lines = [
        "## SwarmAgentic Reproducibility",
        "",
        f"- Mode: `{status.get('mode', 'unknown')}`",
        f"- Status: `{status.get('status', 'unknown')}`",
        f"- Failed phase: `{status.get('failed_phase', 'none')}`",
        f"- Provider-like 504 count: `{status.get('provider_failure_count', 0)}`",
        f"- Full benchmark possible: `{bool(status.get('full_benchmark_possible', False))}`",
        f"- Queries attempted: `{status.get('query_range', {}).get('start', 0)}:{status.get('query_range', {}).get('end', 0)}`",
        f"- Shards completed: `{status.get('completed_shards', 0)}/{status.get('planned_shards', 0)}`",
        f"- Checkpoint available: `{bool(status.get('checkpoint_available', False))}`",
        f"- Official eval available: `{bool(status.get('official_eval_available', False))}`",
        f"- Monitoring phase: `{monitoring.get('current_phase', 'none')}`",
        f"- Heartbeats emitted: `{monitoring.get('heartbeat_count', 0)}`",
        f"- Last child output UTC: `{monitoring.get('last_child_output_utc', 'n/a')}`",
        f"- Last progress UTC: `{monitoring.get('last_progress_utc', 'n/a')}`",
        f"- Last heartbeat UTC: `{monitoring.get('last_heartbeat_utc', 'n/a')}`",
        f"- Watchdog triggered: `{bool(monitoring.get('watchdog_triggered', False))}`",
    ]
    if artifacts:
        lines.extend(
            [
                "",
                "Artifacts:",
                f"- Status JSON: `{artifacts.get('status_json', '')}`",
                f"- Reproducibility MD: `{artifacts.get('reproducibility_md', '')}`",
                f"- Context MD: `{artifacts.get('context_md', '')}`",
                f"- Runs JSON: `{artifacts.get('runs_json', '')}`",
                f"- Official Eval JSON: `{artifacts.get('official_eval_json', '')}`",
                f"- Live Monitor JSON: `{artifacts.get('live_monitor_json', '')}`",
                f"- Heartbeat Log: `{artifacts.get('heartbeat_log', '')}`",
            ]
        )
    notes = status.get("notes", [])
    if notes:
        lines.extend(["", "Notes:"])
        for note in notes:
            lines.append(f"- {note}")
    return "\n".join(lines) + "\n"


def mode_config(args: argparse.Namespace) -> dict[str, Any]:
    if args.mode == "preflight":
        return {
            "iterations": max(1, args.preflight_iteration),
            "settings": [0.2],
            "eval_queries": 0,
            "run_eval": False,
        }
    if args.mode == "pilot":
        return {
            "iterations": max(1, args.pilot_iteration),
            "settings": None,
            "eval_queries": max(1, min(args.max_queries, args.pilot_queries)),
            "run_eval": True,
        }
    return {
        "iterations": max(1, args.max_iteration),
        "settings": None,
        "eval_queries": max(1, args.max_queries),
        "run_eval": True,
    }


def shard_ranges(total_queries: int, shard_size: int) -> list[tuple[int, int]]:
    if total_queries <= 0:
        return []
    size = max(1, shard_size)
    return [(start, min(total_queries, start + size)) for start in range(0, total_queries, size)]


def clone_or_refresh_swarmagentic(*, swarm_root: Path, swarm_clone: Path, clone_swarm: bool) -> None:
    revision_file = swarm_clone / ".stig_patch_revision"
    clone_is_current = revision_file.exists() and revision_file.read_text(encoding="utf-8").strip() == PATCH_REVISION

    if swarm_clone.exists() and not clone_swarm and clone_is_current:
        print(f"[INFO] Reusing existing clone: {swarm_clone}", flush=True)
    else:
        if swarm_clone.exists():
            reason = "user requested fresh clone" if clone_swarm else "local patch revision changed"
            print(f"[INFO] Refreshing SwarmAgentic clone because {reason}.", flush=True)
        shutil.rmtree(swarm_clone)
        result = stream_command(
            ["git", "clone", "--depth", "1", "https://github.com/YaoZ720/SwarmAgenticCode.git", str(swarm_clone)],
            cwd=REPO_ROOT,
            log_path=swarm_root / "git_clone.log",
        )
        if result.returncode != 0:
            raise RuntimeError(f"git clone failed: {result.returncode}")
    patch_result = stream_command(
        [sys.executable, str(PREPARE_SCRIPT), "--repo-root", str(swarm_clone)],
        cwd=REPO_ROOT,
        log_path=swarm_root / "patch_openrouter.log",
    )
    if patch_result.returncode != 0:
        raise RuntimeError(f"prepare_swarmagentic_openrouter.py failed: {patch_result.returncode}")


def install_swarmagentic_deps(*, swarm_root: Path, swarm_clone: Path, install: bool) -> Path:
    venv_python = swarm_clone / ".venv_compare" / "bin" / "python"
    if install or not venv_python.exists():
        venv_result = stream_command(
            ["uv", "venv", ".venv_compare"],
            cwd=swarm_clone,
            log_path=swarm_root / "venv.log",
        )
        if venv_result.returncode != 0:
            raise RuntimeError(f"uv venv failed: {venv_result.returncode}")
        pip_result = stream_command(
            ["uv", "pip", "install", "--python", str(venv_python), "-r", "requirements.txt"],
            cwd=swarm_clone,
            log_path=swarm_root / "pip_install.log",
        )
        if pip_result.returncode != 0:
            raise RuntimeError(f"uv pip install failed: {pip_result.returncode}")
    return venv_python


def sync_if_exists(source: Path, destination: Path) -> bool:
    if not source.exists():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return True


def build_status_payload(
    *,
    args: argparse.Namespace,
    mode_details: dict[str, Any],
    mode_root: Path,
    query_end: int,
    planned_shards: int,
) -> dict[str, Any]:
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "status": "running",
        "failed_phase": None,
        "provider_failure_count": 0,
        "provider_failure_detected": False,
        "model": args.model,
        "extract_model": args.extract_model or args.model,
        "split": args.split,
        "query_range": {"start": 0, "end": query_end},
        "protocol": {
            "sample_step": args.sample_step,
            "max_workers": args.max_workers,
            "configured_max_iteration": args.max_iteration,
            "effective_iterations": mode_details["iterations"],
            "eval_shard_size": args.eval_shard_size,
            "pilot_queries": args.pilot_queries,
            "preflight_iteration": args.preflight_iteration,
            "native_particle_count": 5 if mode_details["settings"] is None else len(mode_details["settings"]),
            "settings": mode_details["settings"],
            "same_backbone": args.model,
            "fairness_axis": "same backbone, native per-framework configuration",
        },
        "checkpoint_available": False,
        "official_eval_available": False,
        "completed_shards": 0,
        "planned_shards": planned_shards,
        "full_benchmark_possible": False,
        "monitoring": {
            "heartbeat_interval_seconds": args.heartbeat_interval_seconds,
            "idle_timeout_seconds": None if args.disable_idle_watchdog else args.idle_timeout_seconds,
            "current_phase": None,
            "last_child_output_utc": None,
            "last_progress_utc": None,
            "last_heartbeat_utc": None,
            "heartbeat_count": 0,
            "watchdog_triggered": False,
            "watched_paths": [],
            "last_watch_summary": {},
            "current_process": {},
        },
        "notes": [],
        "artifacts": {
            "status_json": str((mode_root / "benchmark_status.json").resolve()),
            "reproducibility_md": str((mode_root / "reproducibility.md").resolve()),
            "context_md": str((mode_root / "context.md").resolve()),
            "context_json": str((mode_root / "context.json").resolve()),
            "runs_json": str((mode_root / "runs.json").resolve()),
            "official_eval_json": str((mode_root / "official_eval.json").resolve()),
        },
    }


def update_status_artifacts(mode_root: Path, status: dict[str, Any]) -> None:
    serialize_json(mode_root / "benchmark_status.json", status)
    serialize_json(
        mode_root / "context.json",
        {
            "backbone_model": status.get("model"),
            "mode": status.get("mode"),
            **PAPER_CONTEXT,
        },
    )
    (mode_root / "context.md").write_text(
        render_context_markdown(mode=status.get("mode", "unknown"), model=status.get("model", "unknown")),
        encoding="utf-8",
    )
    (mode_root / "reproducibility.md").write_text(render_reproducibility_markdown(status), encoding="utf-8")


def classify_failure(phase: str, result: CommandResult) -> BenchmarkFailure:
    status = "infra_failure" if (is_provider_failure(result.output) or is_watchdog_failure(result.output)) else "framework_failure"
    return BenchmarkFailure(status=status, phase=phase, output=result.output, command=result.command)


def run_or_fail(phase: str, *, cmd: list[str], cwd: Path, env: dict[str, str], log_path: Path) -> CommandResult:
    result = stream_command(cmd, cwd=cwd, env=env, log_path=log_path)
    if result.returncode != 0:
        raise classify_failure(phase, result)
    return result


def run_monitored_or_fail(
    phase: str,
    *,
    cmd: list[str],
    cwd: Path,
    env: dict[str, str],
    log_path: Path,
    status: dict[str, Any],
    mode_root: Path,
    watched_paths: list[Path],
    heartbeat_interval_seconds: int,
    idle_timeout_seconds: int | None,
) -> CommandResult:
    result = stream_command_monitored(
        cmd,
        cwd=cwd,
        env=env,
        log_path=log_path,
        phase=phase,
        status=status,
        mode_root=mode_root,
        watched_paths=watched_paths,
        heartbeat_interval_seconds=heartbeat_interval_seconds,
        idle_timeout_seconds=idle_timeout_seconds,
    )
    if result.returncode != 0:
        raise classify_failure(phase, result)
    return result


def main() -> int:
    args = parse_args()
    if args.mode not in VALID_MODES:
        raise ValueError(f"Unsupported mode: {args.mode}")
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise EnvironmentError("OPENROUTER_API_KEY is required in the environment")

    swarm_root = args.swarm_root.expanduser().resolve()
    swarm_clone = swarm_root / "repo"
    mode_root = swarm_root / "benchmark" / args.mode
    swarm_cwd = swarm_clone / "travelplanner" / "swarm"
    mode_root.mkdir(parents=True, exist_ok=True)

    mode_details = mode_config(args)
    query_end = mode_details["eval_queries"]
    planned_ranges = shard_ranges(query_end, args.eval_shard_size if args.mode == "full" else max(1, query_end or 1))
    status = build_status_payload(
        args=args,
        mode_details=mode_details,
        mode_root=mode_root,
        query_end=query_end,
        planned_shards=len(planned_ranges),
    )
    update_status_artifacts(mode_root, status)

    swarm_env = {
        "OPENAI_API_KEY": os.environ["OPENROUTER_API_KEY"],
        "OPENAI_BASE_URL": args.base_url,
        "PYTHONUNBUFFERED": "1",
    }

    logs_root = mode_root / "logs"
    checkpoint_cwd = swarm_cwd / "save_state.jsonl"
    checkpoint_mode = mode_root / "save_state.jsonl"
    save_json_cwd = swarm_cwd / "save.jsonl"
    save_json_mode = mode_root / "save.jsonl"
    evaluation_root = mode_root / "evaluation"
    shard_root = evaluation_root / "shards"
    aggregate_root = evaluation_root / "aggregate"
    aggregate_results_jsonl = aggregate_root / "results.jsonl"
    runs_json = mode_root / "runs.json"
    official_json = mode_root / "official_eval.json"
    status["artifacts"]["live_monitor_json"] = str((mode_root / "live_monitor.json").resolve())
    status["artifacts"]["heartbeat_log"] = str((logs_root / "heartbeat.log").resolve())
    status["artifacts"]["train_log"] = str((logs_root / "pso_train.log").resolve())
    update_status_artifacts(mode_root, status)
    idle_timeout_seconds = None if args.disable_idle_watchdog else args.idle_timeout_seconds

    try:
        print(f"[INFO] Mode: {args.mode}", flush=True)
        print(f"[INFO] Model: {args.model}", flush=True)
        clone_or_refresh_swarmagentic(swarm_root=swarm_root, swarm_clone=swarm_clone, clone_swarm=args.clone_swarm)
        swarm_python = install_swarmagentic_deps(swarm_root=swarm_root, swarm_clone=swarm_clone, install=args.install_swarm_deps)

        if args.resume and checkpoint_mode.exists():
            sync_if_exists(checkpoint_mode, checkpoint_cwd)
            status["notes"].append("Resumed from mode-specific checkpoint snapshot.")

        if not args.skip_train:
            status["failed_phase"] = "train"
            update_status_artifacts(mode_root, status)

            train_cmd = [
                str(swarm_python),
                "pso.py",
                "--max_iteration",
                str(mode_details["iterations"]),
                "--model",
                args.model,
                "--max_workers",
                str(args.max_workers),
                "--sample_step",
                str(args.sample_step),
                "--dataset",
                "data/train_45.jsonl",
                "--ref_info",
                "data/train_ref_info.jsonl",
                "--save_dir",
                str((mode_root / "training").resolve()),
            ]
            if mode_details["settings"]:
                train_cmd.extend(["--settings", *[str(value) for value in mode_details["settings"]]])
            if args.resume and checkpoint_cwd.exists():
                train_cmd.extend(["--resume", "--state_idx", "-1"])

            try:
                train_result = run_monitored_or_fail(
                    "train",
                    cmd=train_cmd,
                    cwd=swarm_cwd,
                    env=swarm_env,
                    log_path=logs_root / "pso_train.log",
                    status=status,
                    mode_root=mode_root,
                    watched_paths=[checkpoint_cwd, swarm_cwd / "logs", mode_root / "training"],
                    heartbeat_interval_seconds=args.heartbeat_interval_seconds,
                    idle_timeout_seconds=idle_timeout_seconds,
                )
                status["provider_failure_count"] += count_provider_failures(train_result.output)
            except BenchmarkFailure as failure:
                status["provider_failure_count"] += count_provider_failures(failure.output)
                status["provider_failure_detected"] = status["provider_failure_count"] > 0
                sync_if_exists(checkpoint_cwd, checkpoint_mode)
                status["checkpoint_available"] = checkpoint_mode.exists()
                if checkpoint_mode.exists():
                    status["notes"].append("Training failed but a checkpoint snapshot exists; continuing from the latest saved state.")
                else:
                    raise
            else:
                sync_if_exists(checkpoint_cwd, checkpoint_mode)
                status["checkpoint_available"] = checkpoint_mode.exists()
        else:
            status["notes"].append("Training skipped by configuration.")

        if not checkpoint_mode.exists():
            raise BenchmarkFailure(
                status="framework_failure",
                phase="train",
                output="No checkpoint available after training.",
                command=[str(swarm_cwd / "pso.py")],
            )

        if args.mode == "preflight":
            status["status"] = "success"
            status["failed_phase"] = None
            status["full_benchmark_possible"] = True
            update_status_artifacts(mode_root, status)
            print("[INFO] Preflight completed successfully.", flush=True)
            return 0

        status["failed_phase"] = "export"
        update_status_artifacts(mode_root, status)
        export_result = stream_command(
            [
                sys.executable,
                str(EXPORT_STATE_SCRIPT),
                "--state-jsonl",
                str(checkpoint_mode),
                "--out",
                str(save_json_mode),
            ],
            cwd=REPO_ROOT,
            log_path=logs_root / "export_save_jsonl.log",
        )
        if export_result.returncode != 0:
            raise classify_failure("export", export_result)
        sync_if_exists(save_json_mode, save_json_cwd)

        shard_root.mkdir(parents=True, exist_ok=True)
        aggregate_root.mkdir(parents=True, exist_ok=True)
        for existing in aggregate_root.glob("results-*.jsonl"):
            existing.unlink()
        aggregate_results_jsonl.unlink(missing_ok=True)

        status["failed_phase"] = "eval"
        update_status_artifacts(mode_root, status)
        for start, end in planned_ranges:
            shard_dir = shard_root / f"{start:03d}_{end:03d}"
            shard_dir.mkdir(parents=True, exist_ok=True)
            shard_log = logs_root / f"eval_{start:03d}_{end:03d}.log"
            print(f"[INFO] Evaluating shard {start}:{end}", flush=True)
            status["artifacts"][f"eval_log_{start:03d}_{end:03d}"] = str(shard_log.resolve())
            update_status_artifacts(mode_root, status)
            eval_result = run_monitored_or_fail(
                "eval",
                cmd=[
                    str(swarm_python),
                    "test.py",
                    "--particle_idx",
                    "-1",
                    "--model",
                    args.model,
                    "--extract_model",
                    args.extract_model or args.model,
                    "--save_dir",
                    str(shard_dir.resolve()),
                    "--start_index",
                    str(start),
                    "--end_index",
                    str(end),
                    "--max_workers",
                    str(args.max_workers),
                    "--dataset",
                    "data/validation.jsonl",
                    "--ref_info",
                    "data/validation_ref_info.jsonl",
                ],
                cwd=swarm_cwd,
                env=swarm_env,
                log_path=shard_log,
                status=status,
                mode_root=mode_root,
                watched_paths=[shard_dir, aggregate_root, swarm_cwd / "logs"],
                heartbeat_interval_seconds=args.heartbeat_interval_seconds,
                idle_timeout_seconds=idle_timeout_seconds,
            )
            status["provider_failure_count"] += count_provider_failures(eval_result.output)
            source_results = shard_dir / "results.jsonl"
            if not source_results.exists():
                raise BenchmarkFailure(
                    status="framework_failure",
                    phase="eval",
                    output=f"Missing shard results: {source_results}",
                    command=[str(swarm_cwd / "test.py")],
                )
            shutil.copy2(source_results, aggregate_root / f"results-{start:03d}-{end:03d}.jsonl")
            status["completed_shards"] += 1
            update_status_artifacts(mode_root, status)

        status["failed_phase"] = "aggregate"
        update_status_artifacts(mode_root, status)
        aggregate_result = stream_command_monitored(
            [
                str(swarm_python),
                "test.py",
                "--particle_idx",
                "-1",
                "--aggregate_folder",
                str(aggregate_root.resolve()),
                "--dataset",
                "data/validation.jsonl",
                "--ref_info",
                "data/validation_ref_info.jsonl",
            ],
            cwd=swarm_cwd,
            env=swarm_env,
            log_path=logs_root / "aggregate_eval.log",
            phase="aggregate",
            status=status,
            mode_root=mode_root,
            watched_paths=[aggregate_root],
            heartbeat_interval_seconds=args.heartbeat_interval_seconds,
            idle_timeout_seconds=idle_timeout_seconds,
        )
        if aggregate_result.returncode != 0:
            raise classify_failure("aggregate", aggregate_result)
        status["provider_failure_count"] += count_provider_failures(aggregate_result.output)
        if not aggregate_results_jsonl.exists():
            raise BenchmarkFailure(
                status="framework_failure",
                phase="aggregate",
                output=f"Aggregate results missing: {aggregate_results_jsonl}",
                command=[str(swarm_cwd / "test.py"), "--aggregate_folder", str(aggregate_root)],
            )

        status["failed_phase"] = "convert"
        update_status_artifacts(mode_root, status)
        convert_cmd = [
            sys.executable,
            str(CONVERT_RESULTS_SCRIPT),
            "--results-jsonl",
            str(aggregate_results_jsonl),
            "--out",
            str(runs_json),
            "--method-name",
            "SwarmAgentic",
        ]
        if query_end > 0:
            convert_cmd.extend(["--expected-count", str(query_end)])
        convert_result = stream_command(convert_cmd, cwd=REPO_ROOT, log_path=logs_root / "convert_runs.log")
        if convert_result.returncode != 0:
            raise classify_failure("convert", convert_result)

        status["failed_phase"] = "official_eval"
        update_status_artifacts(mode_root, status)
        official_cmd = [
            "uv",
            "run",
            "python",
            str(OFFICIAL_EVAL_SCRIPT),
            "--runs-json",
            str(runs_json),
            "--database-root",
            str(args.database_root),
            "--split",
            args.split,
            "--out",
            str(official_json),
        ]
        if args.mode == "pilot":
            official_cmd.extend(["--start-index", "0", "--end-index", str(query_end)])
        official_result = stream_command(official_cmd, cwd=REPO_ROOT, log_path=logs_root / "official_eval.log")
        if official_result.returncode != 0:
            raise classify_failure("official_eval", official_result)

        status["provider_failure_count"] += count_provider_failures(official_result.output)
        status["provider_failure_detected"] = status["provider_failure_count"] > 0
        status["official_eval_available"] = official_json.exists()
        status["status"] = "success"
        status["failed_phase"] = None
        status["full_benchmark_possible"] = True
        if args.mode == "pilot":
            status["notes"].append("Pilot scores are subset-only smoke-test metrics over the evaluated shard, not thesis-table metrics.")
        update_status_artifacts(mode_root, status)
        print("[INFO] SwarmAgentic benchmark completed successfully.", flush=True)
        return 0

    except BenchmarkFailure as failure:
        status["status"] = failure.status
        status["failed_phase"] = failure.phase
        status["provider_failure_count"] += count_provider_failures(failure.output)
        status["provider_failure_detected"] = status["provider_failure_count"] > 0
        status["checkpoint_available"] = checkpoint_mode.exists() or checkpoint_cwd.exists()
        if checkpoint_cwd.exists():
            sync_if_exists(checkpoint_cwd, checkpoint_mode)
        status["official_eval_available"] = official_json.exists()
        status["full_benchmark_possible"] = False
        status["notes"].append(failure.output.strip().splitlines()[-1] if failure.output.strip() else str(failure))
        heartbeat_tail = tail_text(logs_root / "heartbeat.log", max_lines=2)
        if heartbeat_tail:
            status["notes"].append("Heartbeat tail: " + " | ".join(heartbeat_tail))
        update_status_artifacts(mode_root, status)
        print(f"[WARN] Benchmark ended with status={failure.status} phase={failure.phase}", flush=True)
        return 0
    except Exception as exc:  # noqa: BLE001
        status["status"] = "framework_failure"
        status["failed_phase"] = status.get("failed_phase") or "setup"
        status["provider_failure_detected"] = status["provider_failure_count"] > 0
        status["checkpoint_available"] = checkpoint_mode.exists() or checkpoint_cwd.exists()
        if checkpoint_cwd.exists():
            sync_if_exists(checkpoint_cwd, checkpoint_mode)
        status["official_eval_available"] = official_json.exists()
        status["full_benchmark_possible"] = False
        status["notes"].append(str(exc))
        heartbeat_tail = tail_text(logs_root / "heartbeat.log", max_lines=2)
        if heartbeat_tail:
            status["notes"].append("Heartbeat tail: " + " | ".join(heartbeat_tail))
        update_status_artifacts(mode_root, status)
        print(f"[WARN] Benchmark ended with unexpected failure: {exc}", flush=True)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
