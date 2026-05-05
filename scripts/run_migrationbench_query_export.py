"""Run one MigrationBench instance and print the common JSON contract."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.migrationbench import MigrationBenchAdapter, MigrationBenchInstance
from adapters.migrationbench.agentless_baseline import run_agentless_self_debug
from adapters.migrationbench.evaluator import MigrationBenchEvaluator
from adapters.migrationbench.scientific_baselines import (
    run_dependency_only_script,
    run_llm_patch_baseline,
    run_no_change,
    run_sd_feedback_wrapper,
)
from adapters.migrationbench.schemas import empty_output_contract
from core.agent import StigmergicAgent
from core.config import load_config, merge_config, validate_config
from core.environment import Environment
from core.marker import Marker
from core.marker_store import MarkerStore
from core.orchestrator import Orchestrator
from core.tool_registry import ToolRegistry
from llm.client import LLMClient
from scripts.migrationbench_cleanup import clean_stigmergic_artifacts


LLM_FRAMEWORKS = {
    "solo_direct",
    "solo_cot",
    "solo_self_refine",
    "planner_executor",
    "agentless_self_debug",
    "stigmergic_v6_static",
    "stigmergic_v7_repair_colony",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--framework", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--subset", type=Path, default=None)
    parser.add_argument("--instance-id", type=str, default=None)
    parser.add_argument("--index", type=int, default=None)
    parser.add_argument("--instance-json", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=Path("config/migrationbench_v6_static_deepseek.yaml"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workspace-root", type=Path, default=Path("workspaces/migrationbench"))
    parser.add_argument("--migrationbench-root", type=Path, default=Path("external/MigrationBench"))
    parser.add_argument("--force", action="store_true", default=False)
    parser.add_argument("--skip-official-eval", action="store_true", default=False)
    parser.add_argument("--sd-feedback-command", type=str, default="")
    parser.add_argument("--agentless-iterations", type=int, default=3)
    return parser.parse_args(argv)


def load_instances(path: Path) -> list[MigrationBenchInstance]:
    rows: list[MigrationBenchInstance] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(MigrationBenchInstance.model_validate(json.loads(line)))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Invalid instance at {path}:{line_no}: {exc}") from exc
    return rows


def select_instance(args: argparse.Namespace) -> MigrationBenchInstance:
    if args.instance_json:
        return MigrationBenchInstance.model_validate(
            json.loads(args.instance_json.read_text(encoding="utf-8"))
        )
    if args.subset is None:
        raise ValueError("--subset is required unless --instance-json is provided")
    instances = load_instances(args.subset)
    if args.instance_id:
        for instance in instances:
            if instance.instance_id == args.instance_id:
                return instance
        raise ValueError(f"Unknown instance_id={args.instance_id!r} in {args.subset}")
    if args.index is None:
        raise ValueError("Either --instance-id or --index is required")
    return instances[int(args.index)]


def load_campaign_config(config_path: Path | None) -> dict[str, Any]:
    config = load_config()
    if config_path and config_path.exists():
        overrides = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if not isinstance(overrides, dict):
            raise ValueError(f"Config must be a mapping: {config_path}")
        config = merge_config(config, overrides)
    validate_config(config)
    return config


def maybe_llm_client(config: dict[str, Any], *, required: bool) -> LLMClient | None:
    if not required:
        return None
    try:
        return LLMClient(config)
    except Exception as exc:  # noqa: BLE001
        print(f"[migrationbench] LLM disabled: {exc}", file=sys.stderr)
        return None


def run_stigmergic_runtime(
    *,
    instance: MigrationBenchInstance,
    args: argparse.Namespace,
    config: dict[str, Any],
    llm_client: LLMClient | None,
    framework: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    workspace_root = args.workspace_root / framework / instance.instance_id / f"seed{args.seed}"
    output_dir = args.out_dir / "artifacts"
    run_config = merge_config(config, {})
    run_config.setdefault("migrationbench", {})
    run_config["migrationbench"].update(
        {
            "instance": instance.model_dump(),
            "workspace_dir": str(workspace_root),
            "artifact_dir": str(output_dir),
            "official_root": str(args.migrationbench_root),
            "run_official_eval": not args.skip_official_eval,
            "framework": framework,
            "seed": int(args.seed),
            "force_workspace": bool(args.force),
        }
    )
    run_config.setdefault("tools", {})
    run_config["tools"]["sandbox_root"] = str(workspace_root)

    session_id = str(uuid4())
    adapter = MigrationBenchAdapter(config=run_config)
    workspace = adapter.create_workspace(run_config)
    objective = adapter.create_objective({"objective": instance.instance_id}, run_config)
    if args.force:
        clean_stigmergic_artifacts(args.out_dir)
    store = MarkerStore(
        db_path=args.out_dir / "markers.db",
        max_retry_count=int(run_config.get("guardrails", {}).get("max_retry_count", 3)),
        traceability=bool(run_config.get("guardrails", {}).get("traceability", True)),
        session_id=session_id,
        session_isolation=False,
    )
    environment = Environment(
        store=store,
        config=run_config,
        workspace=workspace,
        state_machine=adapter.define_state_machine(),
        adapter_name="migrationbench",
    )
    registry = ToolRegistry()
    adapter.register_tools(registry)
    for marker in adapter.initial_markers(objective=objective, agent_id="system_seed"):
        store.upsert_marker(marker=Marker.from_dict(marker.to_dict()), agent_id="system_seed")

    agents = [
        StigmergicAgent(
            agent_id=f"agent-{idx + 1}",
            tool_registry=registry,
            config=run_config,
        )
        for idx in range(int(run_config.get("agents", {}).get("num_agents", 1)))
    ]
    orchestrator = Orchestrator(
        environment=environment,
        agents=agents,
        config=run_config,
        llm_client=llm_client,
        session_id=session_id,
    )
    result = orchestrator.run_sync()
    evaluation = adapter.evaluate_run(
        {"markers": result.final_snapshot.markers, "stop_reason": result.stop_reason}
    )
    contract = dict(evaluation.get("final_contract") or {})
    if not contract:
        provider = str(config.get("llm", {}).get("provider", ""))
        model = str(config.get("llm", {}).get("model", ""))
        contract = empty_output_contract(
            instance=instance,
            framework=framework,
            provider=provider,
            model=model,
            seed=args.seed,
            failure_reason="missing_final_patch",
        )
    contract.setdefault("instance_id", instance.instance_id)
    if not str(contract.get("instance_id", "")).strip():
        contract["instance_id"] = instance.instance_id
    contract.setdefault("framework", framework)
    contract.setdefault("seed", int(args.seed))
    contract.setdefault("provider", str(config.get("llm", {}).get("provider", "")))
    contract.setdefault("model", str(config.get("llm", {}).get("model", "")))
    contract["runtime_seconds"] = round(time.perf_counter() - started, 4)
    contract["tokens_total"] = int(environment.tokens_used)
    contract["cost_total_usd"] = round(float(environment.cost_used), 6)
    contract["llm_calls"] = int(getattr(environment, "llm_calls_used", contract.get("llm_calls", 0)))
    contract["markers_created"] = len(result.final_snapshot.markers)
    contract["coordination_overhead"] = int(result.total_ticks)
    markers_by_type = Counter(
        str(getattr(marker, "marker_type", ""))
        for marker in result.final_snapshot.markers
    )
    agent_pool = dict(result.emergence_summary.get("agent_pool", {}))
    if agent_pool:
        contract["dynamic_agents_min"] = agent_pool.get("dynamic_agents_min")
        contract["dynamic_agents_max"] = agent_pool.get("dynamic_agents_max")
        contract["dynamic_agents_avg"] = agent_pool.get("dynamic_agents_avg")
    if framework == "stigmergic_v7_repair_colony":
        patch_markers = [
            marker
            for marker in result.final_snapshot.markers
            if str(getattr(marker, "marker_type", "")) == "patch_hypothesis"
        ]
        contract["branch_count"] = len({
            str(getattr(marker, "payload", {}).get("branch_id", "")).strip()
            for marker in patch_markers
            if str(getattr(marker, "payload", {}).get("branch_id", "")).strip()
        })
        contract["repair_cycles"] = max(
            [
                int(getattr(marker, "payload", {}).get("attempt", 0) or 0)
                for marker in patch_markers
            ]
            or [0]
        )
        latest = _latest_patch_payload(patch_markers)
        contract["failure_taxonomy"] = str(latest.get("failure_taxonomy", ""))
        contract["caps_hit"] = contract.get("caps_hit") or {}
    contract["summary"] = {
        "session_id": session_id,
        "stop_reason": result.stop_reason,
        "total_ticks": result.total_ticks,
        "emergence": result.emergence_summary,
        "markers_by_type": dict(markers_by_type),
    }
    return contract


def _latest_patch_payload(markers: list[Marker]) -> dict[str, Any]:
    if not markers:
        return {}
    return dict(
        max(
            markers,
            key=lambda marker: int(getattr(marker, "payload", {}).get("attempt", 0) or 0),
        ).payload
    )


def run_framework(
    *,
    instance: MigrationBenchInstance,
    args: argparse.Namespace,
    config: dict[str, Any],
) -> dict[str, Any]:
    framework = str(args.framework)
    evaluator = MigrationBenchEvaluator(
        migrationbench_root=args.migrationbench_root,
        run_official=not args.skip_official_eval,
    )
    llm_client = maybe_llm_client(config, required=framework in LLM_FRAMEWORKS)
    provider = str(config.get("llm", {}).get("provider", ""))
    model = str(config.get("llm", {}).get("model", ""))
    workspace_root = args.workspace_root / framework / instance.instance_id / f"seed{args.seed}"
    artifacts_dir = args.out_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    if framework == "no_change":
        return run_no_change(
            instance=instance,
            workspace_root=workspace_root,
            output_dir=artifacts_dir,
            evaluator=evaluator,
            provider=provider,
            model=model,
            seed=args.seed,
            force=args.force,
        )
    if framework == "dependency_only_script":
        return run_dependency_only_script(
            instance=instance,
            workspace_root=workspace_root,
            output_dir=artifacts_dir,
            evaluator=evaluator,
            provider=provider,
            model=model,
            seed=args.seed,
            force=args.force,
        )
    if framework == "solo_direct":
        return run_llm_patch_baseline(
            instance=instance,
            workspace_root=workspace_root,
            output_dir=artifacts_dir,
            evaluator=evaluator,
            llm_client=llm_client,
            framework=framework,
            strategy="solo direct migration patch",
            seed=args.seed,
            force=args.force,
            repair_cycles=0,
        )
    if framework == "solo_cot":
        return run_llm_patch_baseline(
            instance=instance,
            workspace_root=workspace_root,
            output_dir=artifacts_dir,
            evaluator=evaluator,
            llm_client=llm_client,
            framework=framework,
            strategy="solo chain-of-thought style structured analysis then typed edits",
            seed=args.seed,
            force=args.force,
            repair_cycles=0,
        )
    if framework == "solo_self_refine":
        return run_llm_patch_baseline(
            instance=instance,
            workspace_root=workspace_root,
            output_dir=artifacts_dir,
            evaluator=evaluator,
            llm_client=llm_client,
            framework=framework,
            strategy="solo self-refine with build feedback repair",
            seed=args.seed,
            force=args.force,
            repair_cycles=1,
        )
    if framework == "planner_executor":
        return run_llm_patch_baseline(
            instance=instance,
            workspace_root=workspace_root,
            output_dir=artifacts_dir,
            evaluator=evaluator,
            llm_client=llm_client,
            framework=framework,
            strategy="central planner identifies migration steps, central executor emits typed edits",
            seed=args.seed,
            force=args.force,
            repair_cycles=1,
        )
    if framework == "agentless_self_debug":
        return run_agentless_self_debug(
            instance=instance,
            workspace_root=workspace_root,
            output_dir=artifacts_dir,
            evaluator=evaluator,
            llm_client=llm_client,
            seed=args.seed,
            force=args.force,
            max_iterations=args.agentless_iterations,
        )
    if framework == "sd_feedback":
        return run_sd_feedback_wrapper(
            instance=instance,
            workspace_root=workspace_root,
            output_dir=artifacts_dir,
            command_template=args.sd_feedback_command or None,
            provider=provider,
            model=model,
            seed=args.seed,
        )
    if framework in {"stigmergic_v6_static", "stigmergic_v7_repair_colony"}:
        return run_stigmergic_runtime(
            instance=instance,
            args=args,
            config=config,
            llm_client=llm_client,
            framework=framework,
        )
    raise ValueError(f"Unsupported framework: {framework}")


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    instance = select_instance(args)
    config = load_campaign_config(args.config)
    output = run_framework(instance=instance, args=args, config=config)
    output.setdefault("instance", instance.model_dump())
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
