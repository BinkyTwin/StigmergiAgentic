"""Run a refactored TravelPlanner C3 adapt/eval campaign.

The runner is intentionally stricter than the legacy bash loops: it preflights
effective configs, isolates cross-run DBs under the output directory, stores
stdout/stderr logs per query, and reports strict delivered-pass metrics.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from main import _build_config, _build_protocol_namespace  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--adapt-config",
        type=Path,
        default=Path("config/travelplanner_c3_full_adapt_gemma.yaml"),
    )
    parser.add_argument(
        "--eval-config",
        type=Path,
        default=Path("config/travelplanner_c3_full_eval_gemma.yaml"),
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--adapt-start", type=int, default=0)
    parser.add_argument("--adapt-queries", type=int, default=45)
    parser.add_argument("--eval-start", type=int, default=0)
    parser.add_argument("--eval-queries", type=int, default=180)
    parser.add_argument("--expected-provider", type=str, default="openrouter")
    parser.add_argument("--expected-model", type=str, default="google/gemma-4-31b-it")
    parser.add_argument(
        "--arm",
        choices=["full_c3", "protocol_only", "skills_only", "compiler_only"],
        default="full_c3",
    )
    parser.add_argument(
        "--expected-namespace",
        type=str,
        default="coordination_protocol::travelplanner::travelplanner_c3_gemma_seed42_v1",
    )
    parser.add_argument(
        "--expect-compiler",
        choices=["enabled", "disabled", "any"],
        default="any",
    )
    parser.add_argument("--skip-adapt", action="store_true", default=False)
    parser.add_argument("--clean", action="store_true", default=False)
    parser.add_argument("--adapt-phase-name", type=str, default="adapt")
    parser.add_argument("--eval-phase-name", type=str, default="c3")
    return parser.parse_args(argv)


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return data


def write_generated_config(
    source: Path,
    target: Path,
    pheromones_dir: Path,
    *,
    arm: str,
) -> Path:
    config = load_yaml(source)
    apply_arm_overrides(config, arm=arm)
    skill_cfg = dict(config.get("skill_library", {}))
    if skill_cfg:
        skill_cfg["db_path"] = str((pheromones_dir / "skills.db").resolve())
        config["skill_library"] = skill_cfg
    proto_cfg = dict(config.get("protocol", {}))
    if proto_cfg:
        proto_cfg["db_path"] = str((pheromones_dir / "protocols.db").resolve())
        config["protocol"] = proto_cfg

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return target


def apply_arm_overrides(config: dict[str, Any], *, arm: str) -> None:
    config.setdefault("skill_library", {})
    config.setdefault("protocol", {})
    config.setdefault("emergence", {}).setdefault("cross_run", {})
    config.setdefault("agents", {}).setdefault("protocol_compiler", {})

    if arm == "full_c3":
        config["skill_library"]["enabled"] = True
        config["protocol"]["enabled"] = True
        config["emergence"]["cross_run"]["enabled"] = True
        config["agents"]["protocol_compiler"]["enabled"] = True
    elif arm == "protocol_only":
        config["skill_library"]["enabled"] = False
        config["protocol"]["enabled"] = True
        config["emergence"]["cross_run"]["enabled"] = True
        config["agents"]["protocol_compiler"]["enabled"] = False
    elif arm == "skills_only":
        config["skill_library"]["enabled"] = True
        config["protocol"]["enabled"] = False
        config["emergence"]["cross_run"]["enabled"] = False
        config["agents"]["protocol_compiler"]["enabled"] = False
    elif arm == "compiler_only":
        config["skill_library"]["enabled"] = False
        config["protocol"]["enabled"] = False
        config["emergence"]["cross_run"]["enabled"] = False
        config["agents"]["protocol_compiler"]["enabled"] = True


def effective_config(config_path: Path) -> dict[str, Any]:
    args = argparse.Namespace(
        adapter="travelplanner",
        objective="Query 0",
        workspace=".",
        data_dir=None,
        query_idx=0,
        config=str(config_path),
        max_ticks=None,
        agents=None,
        seed=42,
        keep_session=False,
    )
    return _build_config(args)


def required_api_key(provider: str) -> str:
    if provider == "deepseek":
        return "DEEPSEEK_API_KEY"
    return "OPENROUTER_API_KEY"


def preflight(args: argparse.Namespace, adapt_config: Path, eval_config: Path) -> dict[str, Any]:
    adapt_effective = effective_config(adapt_config)
    eval_effective = effective_config(eval_config)
    eval_llm = dict(eval_effective.get("llm", {}))
    provider = str(eval_llm.get("provider", "")).strip()
    model = str(eval_llm.get("model", "")).strip()
    namespace_adapt = _build_protocol_namespace(adapt_effective, "travelplanner")
    namespace_eval = _build_protocol_namespace(eval_effective, "travelplanner")
    compiler_enabled = bool(
        dict(eval_effective.get("agents", {}))
        .get("protocol_compiler", {})
        .get("enabled", False)
    )

    if args.expected_provider != "any" and provider != args.expected_provider:
        raise RuntimeError(f"provider mismatch: expected {args.expected_provider}, got {provider}")
    if args.expected_model != "any" and model != args.expected_model:
        raise RuntimeError(f"model mismatch: expected {args.expected_model}, got {model}")
    if args.expected_namespace != "any" and namespace_eval != args.expected_namespace:
        raise RuntimeError(
            f"namespace mismatch: expected {args.expected_namespace}, got {namespace_eval}"
        )
    if (
        bool(adapt_effective.get("protocol", {}).get("enabled", False))
        and bool(eval_effective.get("protocol", {}).get("enabled", False))
        and namespace_adapt != namespace_eval
    ):
        raise RuntimeError(
            f"adapt/eval namespace mismatch: {namespace_adapt} != {namespace_eval}"
        )
    if args.expect_compiler == "enabled" and not compiler_enabled:
        raise RuntimeError("protocol compiler expected enabled but effective config disables it")
    if args.expect_compiler == "disabled" and compiler_enabled:
        raise RuntimeError("protocol compiler expected disabled but effective config enables it")

    key_name = required_api_key(provider)
    if not os.environ.get(key_name):
        raise RuntimeError(f"missing API key environment variable: {key_name}")

    return {
        "provider": provider,
        "model": model,
        "api_key_env": key_name,
        "namespace_adapt": namespace_adapt,
        "namespace_eval": namespace_eval,
        "compiler_enabled": compiler_enabled,
        "adapt_config_effective": adapt_effective,
        "eval_config_effective": eval_effective,
    }


def extract_last_json(stdout: str) -> dict[str, Any]:
    lines = stdout.splitlines()
    for index in range(len(lines) - 1, -1, -1):
        if not lines[index].lstrip().startswith("{"):
            continue
        candidate = "\n".join(lines[index:]).strip()
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ValueError("unable to locate final JSON object")


def run_query(
    *,
    phase: str,
    query_idx: int,
    config_path: Path,
    seed: int,
    output_dir: Path,
) -> dict[str, Any]:
    query_dir = output_dir / phase
    logs_dir = output_dir / "logs" / phase
    query_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"query_{query_idx:03d}.log"
    started = time.perf_counter()
    command = [
        sys.executable,
        "main.py",
        "--adapter",
        "travelplanner",
        "--objective",
        f"Query {query_idx}",
        "--query-idx",
        str(query_idx),
        "--config",
        str(config_path),
        "--seed",
        str(seed),
    ]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    runtime = time.perf_counter() - started
    log_path.write_text(
        (completed.stdout or "")
        + ("\n" if completed.stdout and not completed.stdout.endswith("\n") else "")
        + (completed.stderr or ""),
        encoding="utf-8",
    )

    if completed.returncode != 0:
        payload = failed_payload(
            query_idx=query_idx,
            runtime_seconds=runtime,
            reason="returncode_nonzero",
            stderr_tail="\n".join((completed.stderr or "").splitlines()[-20:]),
        )
    else:
        try:
            payload = extract_last_json(completed.stdout or "")
            payload["runtime_seconds"] = round(runtime, 4)
        except ValueError as exc:
            payload = failed_payload(
                query_idx=query_idx,
                runtime_seconds=runtime,
                reason="json_extract_failed",
                stderr_tail=str(exc),
            )

    # The runtime summary may omit query_idx when a compiled protocol fails before
    # any TravelPlanner marker carries query_data. The campaign artifact still
    # belongs to this requested query and must remain official-scorer addressable.
    payload["query_idx"] = query_idx
    plan = payload.get("final_plan") if isinstance(payload.get("final_plan"), list) else []
    raw_final_pass = bool(payload.get("raw_final_pass", payload.get("final_pass", False)))
    strict_final_pass = bool(plan and raw_final_pass)
    payload["artifact_delivered"] = bool(plan)
    payload["raw_final_pass"] = raw_final_pass
    payload["strict_final_pass"] = strict_final_pass
    payload["final_pass"] = strict_final_pass
    if not strict_final_pass and str(payload.get("failure_reason", "ok")) == "ok":
        payload["failure_reason"] = "empty_plan_from_llm"

    (query_dir / f"query_{query_idx:03d}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return payload


def failed_payload(
    *,
    query_idx: int,
    runtime_seconds: float,
    reason: str,
    stderr_tail: str,
) -> dict[str, Any]:
    return {
        "status": "failed",
        "query_idx": query_idx,
        "final_plan": [],
        "plan": [],
        "artifact_delivered": False,
        "raw_final_pass": False,
        "strict_final_pass": False,
        "final_pass": False,
        "failure_reason": reason,
        "stderr_tail": stderr_tail,
        "runtime_seconds": round(runtime_seconds, 4),
    }


def checkpoint_sqlite(pheromones_dir: Path) -> None:
    for db_path in (pheromones_dir / "skills.db", pheromones_dir / "protocols.db"):
        if not db_path.exists():
            continue
        con = sqlite3.connect(db_path)
        try:
            con.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            con.execute("PRAGMA journal_mode=DELETE;")
        finally:
            con.close()
        for suffix in ("-wal", "-shm"):
            db_path.with_name(db_path.name + suffix).unlink(missing_ok=True)


def write_runs_json(path: Path, runs: list[dict[str, Any]]) -> None:
    path.write_text(
        json.dumps({"runs": runs}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def run_official_eval(
    *,
    runs_json: Path,
    out_path: Path,
    start: int,
    count: int,
) -> None:
    command = [
        sys.executable,
        "scripts/eval_travelplanner_official.py",
        "--runs-json",
        str(runs_json),
        "--split",
        "validation",
        "--out",
        str(out_path),
        "--start-index",
        str(start),
        "--end-index",
        str(start + count),
    ]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    (out_path.parent / "official_eval.log").write_text(
        (completed.stdout or "") + (completed.stderr or ""),
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(f"official eval failed: {completed.stderr}")


def build_summary(
    *,
    runs: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    total = len(runs)
    denom = total or 1
    failures: dict[str, int] = {}
    for run in runs:
        reason = str(run.get("failure_reason", "ok")).strip() or "ok"
        failures[reason] = failures.get(reason, 0) + 1
    return {
        "manifest": {
            key: value
            for key, value in manifest.items()
            if key not in {"adapt_config_effective", "eval_config_effective"}
        },
        "queries": total,
        "artifact_delivery_rate": sum(bool(r.get("artifact_delivered", False)) for r in runs) / denom,
        "raw_final_pass_rate": sum(bool(r.get("raw_final_pass", False)) for r in runs) / denom,
        "strict_final_pass_rate": sum(bool(r.get("strict_final_pass", False)) for r in runs) / denom,
        "final_pass_rate": sum(bool(r.get("strict_final_pass", False)) for r in runs) / denom,
        "tokens_total": sum(int(r.get("tokens_used", 0) or 0) for r in runs),
        "cost_total_usd": round(sum(float(r.get("cost_used", 0.0) or 0.0) for r in runs), 6),
        "failure_reasons": dict(sorted(failures.items())),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = args.out_dir.expanduser().resolve()
    if args.clean and out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pheromones_dir = out_dir / "pheromones"
    generated_dir = out_dir / "generated_configs"
    pheromones_dir.mkdir(parents=True, exist_ok=True)

    adapt_config = write_generated_config(
        args.adapt_config,
        generated_dir / "adapt.yaml",
        pheromones_dir,
        arm=args.arm,
    )
    eval_config = write_generated_config(
        args.eval_config,
        generated_dir / "eval.yaml",
        pheromones_dir,
        arm=args.arm,
    )
    manifest = preflight(args, adapt_config, eval_config)
    manifest.update(
        {
            "seed": args.seed,
            "arm": args.arm,
            "adapt_start": args.adapt_start,
            "adapt_queries": args.adapt_queries,
            "eval_start": args.eval_start,
            "eval_queries": args.eval_queries,
            "adapt_config": str(args.adapt_config),
            "eval_config": str(args.eval_config),
            "generated_adapt_config": str(adapt_config),
            "generated_eval_config": str(eval_config),
        }
    )
    (out_dir / "campaign_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )

    if not args.skip_adapt:
        for query_idx in range(args.adapt_start, args.adapt_start + args.adapt_queries):
            run_query(
                phase=args.adapt_phase_name,
                query_idx=query_idx,
                config_path=adapt_config,
                seed=args.seed,
                output_dir=out_dir,
            )
        checkpoint_sqlite(pheromones_dir)

    eval_runs = [
        run_query(
            phase=args.eval_phase_name,
            query_idx=query_idx,
            config_path=eval_config,
            seed=args.seed,
            output_dir=out_dir,
        )
        for query_idx in range(args.eval_start, args.eval_start + args.eval_queries)
    ]

    runs_json = out_dir / "runs.json"
    write_runs_json(runs_json, eval_runs)
    run_official_eval(
        runs_json=runs_json,
        out_path=out_dir / "official_eval.json",
        start=args.eval_start,
        count=args.eval_queries,
    )
    summary = build_summary(runs=eval_runs, manifest=manifest)
    (out_dir / "benchmark_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
