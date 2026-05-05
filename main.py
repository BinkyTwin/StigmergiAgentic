"""CLI entrypoint for V3 adapters (assistant and travelplanner)."""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from dotenv import load_dotenv

from adapters.base import DomainAdapter
from adapters.assistant import AssistantAdapter
from adapters.migrationbench import MigrationBenchAdapter
from adapters.travelplanner import TravelPlannerAdapter
from core.agent import StigmergicAgent
from core.config import load_config, merge_config, validate_config
from core.dependency import validate_dag
from core.emergence import (
    clamp_cross_run_adaptations,
    compute_adaptations,
    compute_protocol_score,
)
from core.environment import Environment
from core.marker import Marker
from core.marker_store import MarkerStore
from core.orchestrator import Orchestrator
from core.tool_registry import ToolRegistry
from llm.client import LLMClient


ASSISTANT_CONFIG_PATH = Path("config/assistant.yaml")
TRAVELPLANNER_CONFIG_PATH = Path("config/travelplanner.yaml")
MIGRATIONBENCH_CONFIG_PATH = Path("config/migrationbench_v6_static_deepseek.yaml")
DEFAULT_DB_PATH = Path("pheromones/markers.db")
SKILLS_DB_PATH = Path("pheromones/skills.db")
PROTOCOLS_DB_PATH = Path("pheromones/protocols.db")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for assistant execution."""
    parser = argparse.ArgumentParser(description="Stigmergic V3 runtime")
    parser.add_argument(
        "--adapter",
        choices=["assistant", "travelplanner", "migrationbench"],
        default="assistant",
    )
    parser.add_argument("--objective", type=str, required=True)
    parser.add_argument("--workspace", type=str, default=".")
    parser.add_argument("--data-dir", type=str, default=None)
    parser.add_argument("--query-idx", type=int, default=None)
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--max-ticks", type=int, default=None)
    parser.add_argument("--agents", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--keep-session",
        action="store_true",
        default=False,
        help="Keep session DB and audit files after run (default: auto-cleanup)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run one assistant session and print run summary as JSON."""
    load_dotenv()
    args = parse_args(argv)
    session_id = str(uuid4())

    config = _build_config(args)
    adapter = _build_adapter(name=args.adapter, config=config)
    workspace = adapter.create_workspace(config)
    user_input: dict[str, Any] = {"objective": args.objective}
    if args.query_idx is not None:
        user_input["query_idx"] = int(args.query_idx)
    objective = adapter.create_objective(user_input, config)
    workspace_context = _workspace_context(workspace)
    markers_cfg = dict(config.get("markers", {}))
    session_isolation = bool(markers_cfg.get("session_isolation", False))
    db_path = DEFAULT_DB_PATH

    store = MarkerStore(
        db_path=db_path,
        max_retry_count=int(config.get("guardrails", {}).get("max_retry_count", 3)),
        traceability=bool(config.get("guardrails", {}).get("traceability", True)),
        session_id=session_id,
        session_isolation=session_isolation,
    )
    skills_store = _maybe_build_skills_store(config)
    protocol_store = _maybe_build_protocol_store(config)
    protocol_namespace = _build_protocol_namespace(config, args.adapter)
    protocol_status = _apply_cross_run_protocol(
        config=config,
        protocol_store=protocol_store,
        namespace=protocol_namespace,
    )
    environment = Environment(
        store=store,
        config=config,
        workspace=workspace,
        state_machine=adapter.define_state_machine(),
        skills_store=skills_store,
        adapter_name=str(args.adapter),
    )

    registry = ToolRegistry()
    adapter.register_tools(registry)
    llm_client = _maybe_create_llm_client(config=config)

    for marker in _select_initial_markers(
        adapter=adapter,
        objective=objective,
        config=config,
        llm_client=llm_client,
    ):
        seeded = Marker.from_dict(marker.to_dict())
        payload = dict(seeded.payload)
        if workspace_context:
            payload.setdefault("workspace_context", workspace_context)
        seeded.payload = payload
        store.upsert_marker(marker=seeded, agent_id="system_seed")

    agents = _build_agents(config=config, registry=registry, seed=args.seed)

    orchestrator = Orchestrator(
        environment=environment,
        agents=agents,
        config=config,
        llm_client=llm_client,
        session_id=session_id,
    )
    result = orchestrator.run_sync()

    evaluation = adapter.evaluate_run(
        {
            "markers": result.final_snapshot.markers,
            "stop_reason": result.stop_reason,
        }
    )
    _persist_protocol(
        result=result,
        evaluation=evaluation,
        config=config,
        protocol_store=protocol_store,
        namespace=protocol_namespace,
        session_id=session_id,
    )
    dag_info = _dag_info(result.final_snapshot.markers)
    if args.adapter == "assistant":
        assistant_response = _build_assistant_response(
            objective_id=objective.objective_id,
            markers=result.final_snapshot.markers,
        )
    elif args.adapter == "travelplanner":
        assistant_response = _build_travelplanner_response(
            result.final_snapshot.markers
        )
    else:
        assistant_response = _build_migrationbench_response(
            result.final_snapshot.markers
        )

    print(f"Session ID: {session_id}")
    print("Assistant response:")
    print(assistant_response)
    print()
    _print_emergence_dashboard(result.emergence_summary)
    print()

    summary = _build_run_summary(
        adapter_name=args.adapter,
        objective_id=objective.objective_id,
        session_id=session_id,
        store=store,
        result=result,
        environment=environment,
        agents=agents,
        evaluation=evaluation,
        dag_info=dag_info,
        assistant_response=assistant_response,
        config=config,
        protocol_namespace=protocol_namespace,
        cross_run_loaded=bool(protocol_status.get("loaded", False)),
        cross_run_applied=bool(protocol_status.get("applied", False)),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))

    if not args.keep_session and session_isolation:
        _cleanup_session(store.db_path.parent)

    return 0


def _cleanup_session(session_dir: Path) -> None:
    """Remove ephemeral session directory (DB + audit) after run completes."""
    try:
        if session_dir.is_dir():
            shutil.rmtree(session_dir)
    except OSError:
        pass  # cleanup must never crash the run


def _build_config(args: argparse.Namespace) -> dict[str, Any]:
    config = load_config()

    if args.adapter == "assistant":
        assistant_overrides = _load_yaml(ASSISTANT_CONFIG_PATH)
        if assistant_overrides:
            config = merge_config(config, assistant_overrides)
    elif args.adapter == "travelplanner":
        travelplanner_overrides = _load_yaml(TRAVELPLANNER_CONFIG_PATH)
        if travelplanner_overrides:
            config = merge_config(config, travelplanner_overrides)
    elif args.adapter == "migrationbench":
        migrationbench_overrides = _load_yaml(MIGRATIONBENCH_CONFIG_PATH)
        if migrationbench_overrides:
            config = merge_config(config, migrationbench_overrides)

    if args.config:
        user_overrides = _load_yaml(Path(args.config))
        config = merge_config(config, user_overrides)

    config.setdefault("tools", {})
    config["tools"]["sandbox_root"] = str(Path(args.workspace).expanduser().resolve())
    if args.data_dir:
        config.setdefault("travelplanner", {})
        config["travelplanner"]["database_path"] = str(
            Path(args.data_dir).expanduser().resolve()
        )

    if args.max_ticks is not None:
        config.setdefault("orchestrator", {})
        config["orchestrator"]["max_ticks"] = int(args.max_ticks)

    if args.agents is not None:
        config.setdefault("agents", {})
        config["agents"]["num_agents"] = int(args.agents)

    validate_config(config)
    return config


def _build_adapter(*, name: str, config: dict[str, Any]) -> DomainAdapter:
    if name == "assistant":
        return AssistantAdapter(config=config)
    if name == "travelplanner":
        return TravelPlannerAdapter(config=config)
    if name == "migrationbench":
        return MigrationBenchAdapter(config=config)
    raise ValueError(f"Unsupported adapter: {name}")


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"YAML config must be a mapping: {path}")
    return loaded


def _maybe_create_llm_client(config: dict[str, Any]) -> LLMClient | None:
    try:
        return LLMClient(config)
    except Exception as exc:  # noqa: BLE001
        print(
            f"LLM client disabled: {exc}",
            file=sys.stderr,
        )
        return None


def _select_initial_markers(
    *,
    adapter: DomainAdapter,
    objective: Any,
    config: dict[str, Any],
    llm_client: LLMClient | None,
) -> list[Marker]:
    compiler_cfg = dict(config.get("agents", {}).get("protocol_compiler", {}))
    compiler_enabled = bool(compiler_cfg.get("enabled", False))
    runtime = config.setdefault("_runtime", {})
    if not compiler_enabled:
        runtime["protocol_compiler_used"] = False
        runtime["protocol_compiler_reason"] = "disabled"
        return adapter.initial_markers(objective=objective, agent_id="system_seed")

    compiled = adapter.compile_protocol(
        objective=objective,
        config=config,
        llm_client=llm_client,
    )
    if compiled and validate_dag(compiled):
        runtime["protocol_compiler_used"] = True
        runtime["protocol_compiler_reason"] = "compiled"
        return compiled
    runtime["protocol_compiler_used"] = False
    runtime["protocol_compiler_reason"] = "fallback_initial_markers"
    return adapter.initial_markers(objective=objective, agent_id="system_seed")


def _build_agents(
    *,
    config: dict[str, Any],
    registry: ToolRegistry,
    seed: int | None,
) -> list[StigmergicAgent]:
    num_agents = int(config.get("agents", {}).get("num_agents", 1))
    agents: list[StigmergicAgent] = []
    for index in range(num_agents):
        rng = None
        if seed is not None:
            rng = random.Random(seed + index)
        agents.append(
            StigmergicAgent(
                agent_id=f"agent-{index + 1}",
                tool_registry=registry,
                config=config,
                rng=rng,
            )
        )
    return agents


def _build_run_summary(
    *,
    adapter_name: str,
    objective_id: str,
    session_id: str,
    store: MarkerStore,
    result: Any,
    environment: Environment,
    agents: list[StigmergicAgent],
    evaluation: dict[str, Any],
    dag_info: dict[str, Any],
    assistant_response: str,
    config: dict[str, Any],
    protocol_namespace: str = "",
    cross_run_loaded: bool = False,
    cross_run_applied: bool = False,
) -> dict[str, Any]:
    llm_config = dict(config.get("llm", {}))
    protocol_cfg = dict(config.get("protocol", {}))
    if adapter_name == "travelplanner":
        artifact = _extract_travelplanner_artifact(result.final_snapshot.markers)
    elif adapter_name == "migrationbench":
        artifact = _extract_migrationbench_artifact(result.final_snapshot.markers)
    else:
        artifact = {
            "final_plan": [],
            "artifact_delivered": False,
            "raw_final_pass": False,
            "strict_final_pass": False,
            "failure_reason": "",
            "query_idx": None,
        }
    runtime = dict(config.get("_runtime", {}))
    return {
        "adapter": adapter_name,
        "objective_id": objective_id,
        "session_id": session_id,
        "session_db_path": str(store.db_path),
        "stop_reason": result.stop_reason,
        "total_ticks": result.total_ticks,
        "agents": len(agents),
        "markers": len(result.final_snapshot.markers),
        "tokens_used": int(environment.tokens_used),
        "cost_used": float(environment.cost_used),
        "llm_provider": str(llm_config.get("provider", "")),
        "llm_model": str(llm_config.get("model", "")),
        "reinforcement": {
            "events": int(environment.reinforcement_events),
            "propagation_events": int(environment.propagation_events),
        },
        "maintenance": {
            "pruned_markers": int(environment.pruned_markers),
        },
        "skill_library": {
            "enabled": bool(
                dict(config.get("skill_library", {})).get("enabled", False)
            ),
            "skills_promoted": int(getattr(environment, "skills_promoted", 0)),
            "skills_loaded_count": int(
                getattr(environment, "skills_loaded_count", 0)
            ),
            "skills_injected_count": int(
                getattr(environment, "skills_injected_count", 0)
            ),
        },
        "protocol": {
            "enabled": bool(protocol_cfg.get("enabled", False)),
            "namespace": protocol_namespace,
            "coordination_protocol_loaded": bool(cross_run_loaded),
            "coordination_protocol_applied": bool(cross_run_applied),
        },
        "protocol_compiler": {
            "enabled": bool(
                dict(config.get("agents", {}))
                .get("protocol_compiler", {})
                .get("enabled", False)
            ),
            "used": bool(runtime.get("protocol_compiler_used", False)),
            "reason": str(runtime.get("protocol_compiler_reason", "")),
        },
        "protocol_namespace": protocol_namespace,
        "coordination_protocol_loaded": bool(cross_run_loaded),
        "coordination_protocol_applied": bool(cross_run_applied),
        "final_plan": artifact["final_plan"],
        "artifact_delivered": artifact["artifact_delivered"],
        "raw_final_pass": artifact["raw_final_pass"],
        "strict_final_pass": artifact["strict_final_pass"],
        "final_pass": artifact["strict_final_pass"],
        "failure_reason": artifact["failure_reason"],
        "query_idx": artifact["query_idx"],
        "emergence": dict(result.emergence_summary),
        "dag": dag_info,
        "evaluation": evaluation,
        "assistant_response": assistant_response,
    }


def _extract_travelplanner_artifact(markers: list[Any]) -> dict[str, Any]:
    final_plan: list[dict[str, Any]] = []
    raw_final_pass = False
    strict_final_pass = False
    failure_reason = ""
    query_idx = None
    fallback_plan: list[dict[str, Any]] = []
    fallback_raw_final_pass = False
    fallback_strict_final_pass = False
    fallback_failure_reason = ""
    fallback_query_idx = None

    for marker in markers:
        marker_id = str(getattr(marker, "id", ""))
        payload = dict(getattr(marker, "payload", {}))
        query_data = payload.get("query_data")
        marker_query_idx = None
        if isinstance(query_data, dict) and query_data.get("query_idx") is not None:
            try:
                marker_query_idx = int(query_data.get("query_idx"))
            except Exception:  # noqa: BLE001
                marker_query_idx = None
        elif payload.get("query_idx") is not None:
            try:
                marker_query_idx = int(payload.get("query_idx"))
            except Exception:  # noqa: BLE001
                marker_query_idx = None

        candidate_plan = payload.get("final_plan", payload.get("plan", []))
        if isinstance(candidate_plan, list) and candidate_plan and not fallback_plan:
            fallback_plan = candidate_plan
            fallback_query_idx = marker_query_idx
            evaluation = payload.get("evaluation", {})
            if isinstance(evaluation, dict):
                fallback_raw_final_pass = bool(
                    evaluation.get("raw_final_pass", evaluation.get("final_pass", False))
                )
                fallback_strict_final_pass = bool(
                    evaluation.get(
                        "strict_final_pass",
                        fallback_raw_final_pass and bool(fallback_plan),
                    )
                )
            else:
                fallback_raw_final_pass = bool(payload.get("final_pass", False))
                fallback_strict_final_pass = bool(
                    payload.get(
                        "strict_final_pass",
                        fallback_raw_final_pass and bool(fallback_plan),
                    )
                )
            fallback_failure_reason = str(
                payload.get("failure_reason", "")
            ).strip()

        if marker_id.endswith("::finalize"):
            plan = payload.get("final_plan", [])
            if isinstance(plan, list):
                final_plan = plan
            raw_final_pass = bool(
                payload.get("raw_final_pass", payload.get("final_pass", False))
            )
            strict_final_pass = bool(
                payload.get("strict_final_pass", raw_final_pass and bool(final_plan))
            )
            failure_reason = str(payload.get("failure_reason", "")).strip()
            query_idx = marker_query_idx
            if final_plan:
                break

    if not final_plan and fallback_plan:
        final_plan = fallback_plan
        raw_final_pass = fallback_raw_final_pass
        strict_final_pass = fallback_strict_final_pass
        failure_reason = fallback_failure_reason
        query_idx = fallback_query_idx

    if not final_plan and (not failure_reason or failure_reason == "ok"):
        failure_reason = "empty_plan_from_llm"

    return {
        "final_plan": final_plan,
        "artifact_delivered": bool(final_plan),
        "raw_final_pass": raw_final_pass,
        "strict_final_pass": bool(final_plan and raw_final_pass and strict_final_pass),
        "failure_reason": failure_reason or "ok",
        "query_idx": query_idx,
    }


def _extract_migrationbench_artifact(markers: list[Any]) -> dict[str, Any]:
    """Extract patch-centric contract from the MigrationBench finalize marker."""
    for marker in markers:
        marker_id = str(getattr(marker, "id", ""))
        if not (
            marker_id.endswith("::finalize_patch")
            or marker_id.endswith("::finalize_evaluated_patch")
        ):
            continue
        payload = dict(getattr(marker, "payload", {}))
        return {
            "final_plan": [],
            "artifact_delivered": bool(payload.get("artifact_delivered", False)),
            "raw_final_pass": bool(payload.get("official_success", False)),
            "strict_final_pass": bool(payload.get("strict_success", False)),
            "failure_reason": str(payload.get("failure_reason", "ok")),
            "query_idx": None,
            "migrationbench_contract": payload,
        }
    return {
        "final_plan": [],
        "artifact_delivered": False,
        "raw_final_pass": False,
        "strict_final_pass": False,
        "failure_reason": "missing_final_patch",
        "query_idx": None,
    }


def _build_assistant_response(objective_id: str, markers: list[Any]) -> str:
    """Build one human-readable assistant response from terminal marker payloads."""
    prefix = f"{objective_id}::subtask::"
    subtasks = [
        marker
        for marker in markers
        if str(getattr(marker, "id", "")).startswith(prefix)
    ]
    subtasks = sorted(subtasks, key=_subtask_sort_key)

    if not subtasks:
        root = next(
            (
                marker
                for marker in markers
                if str(getattr(marker, "id", "")) == objective_id
            ),
            None,
        )
        if root is None:
            return "No assistant response generated."
        payload = dict(getattr(root, "payload", {}))
        return (
            _render_marker_output(task="", payload=payload)
            or "No assistant response generated."
        )

    lines: list[str] = []
    for index, marker in enumerate(subtasks, start=1):
        payload = dict(getattr(marker, "payload", {}))
        task = str(payload.get("task", "")).strip()
        rendered = _render_marker_output(task=task, payload=payload)
        if rendered:
            lines.append(f"{index}. {rendered}")

    if not lines:
        return "No assistant response generated."
    return "\n".join(lines)


def _build_travelplanner_response(markers: list[Any]) -> str:
    """Render final travel plan from finalize marker payload when available."""
    final_markers = [
        marker
        for marker in markers
        if str(getattr(marker, "id", "")).endswith("::finalize")
    ]
    if not final_markers:
        return "No travel plan generated."

    final_marker = sorted(
        final_markers, key=lambda marker: str(getattr(marker, "id", ""))
    )[0]
    payload = dict(getattr(final_marker, "payload", {}))
    plan = payload.get("final_plan", [])
    if not isinstance(plan, list) or not plan:
        return "No travel plan generated."

    lines: list[str] = []
    for index, day in enumerate(plan, start=1):
        if not isinstance(day, dict):
            continue
        city = str(day.get("current_city", "")).strip()
        transport = str(day.get("transportation", "")).strip()
        breakfast = str(day.get("breakfast", "")).strip()
        lunch = str(day.get("lunch", "")).strip()
        dinner = str(day.get("dinner", "")).strip()
        attraction = str(day.get("attraction", "")).strip()
        accommodation = str(day.get("accommodation", "")).strip()
        lines.append(
            f"Day {index}: {city} | transport={transport} | breakfast={breakfast} "
            f"| attraction={attraction} | lunch={lunch} | dinner={dinner} "
            f"| accommodation={accommodation}"
        )

    return "\n".join(lines) if lines else "No travel plan generated."


def _build_migrationbench_response(markers: list[Any]) -> str:
    """Render a concise patch outcome for MigrationBench runs."""
    artifact = _extract_migrationbench_artifact(markers)
    contract = artifact.get("migrationbench_contract", {})
    if not isinstance(contract, dict) or not contract:
        return "No MigrationBench patch generated."
    return (
        f"patch={contract.get('patch_path', '')} "
        f"applies={contract.get('patch_applies', False)} "
        f"official_success={contract.get('official_success', False)} "
        f"strict_success={contract.get('strict_success', False)} "
        f"reason={contract.get('failure_reason', '')}"
    )


def _render_marker_output(*, task: str, payload: dict[str, Any]) -> str:
    segments: list[str] = []
    if task:
        segments.append(task)

    thought = _normalize_analysis(payload.get("last_thought"))
    if thought:
        segments.append(thought)

    read_summary = _summarize_read(payload.get("last_read"))
    if read_summary:
        segments.append(read_summary)

    bash_summary = _summarize_bash(payload.get("last_bash"))
    if bash_summary:
        segments.append(bash_summary)

    write_summary = _summarize_write(payload.get("last_write"))
    if write_summary:
        segments.append(write_summary)

    search_summary = _summarize_search(payload.get("last_search"))
    if search_summary:
        segments.append(search_summary)

    if not segments:
        return ""
    if len(segments) == 1:
        return segments[0]
    return f"{segments[0]} -> {' | '.join(segments[1:])}"


def _summarize_read(last_read: Any) -> str:
    if not isinstance(last_read, dict):
        return ""
    path = str(last_read.get("path", "")).strip()
    content = str(last_read.get("content", "")).strip()
    if not path and not content:
        return ""

    excerpt = " ".join(content.split())
    if len(excerpt) > 120:
        excerpt = f"{excerpt[:117]}..."
    if path and excerpt:
        return f"read `{path}`: {excerpt}"
    if path:
        return f"read `{path}`"
    return f"read result: {excerpt}"


def _summarize_bash(last_bash: Any) -> str:
    if not isinstance(last_bash, dict):
        return ""
    command = last_bash.get("command", [])
    if isinstance(command, list):
        command_text = " ".join(str(part) for part in command if str(part).strip())
    else:
        command_text = str(command).strip()
    returncode = last_bash.get("returncode")
    stdout = str(last_bash.get("stdout", "")).strip()
    stderr = str(last_bash.get("stderr", "")).strip()
    output = stdout or stderr
    output = " ".join(output.split())
    if len(output) > 120:
        output = f"{output[:117]}..."

    parts: list[str] = []
    if command_text:
        parts.append(f"bash `{command_text}`")
    if returncode is not None:
        parts.append(f"exit={returncode}")
    if output:
        parts.append(output)
    return ": ".join([parts[0], " | ".join(parts[1:])]) if parts else ""


def _summarize_write(last_write: Any) -> str:
    if not isinstance(last_write, dict):
        return ""
    mode = str(last_write.get("mode", "")).strip()
    path = str(last_write.get("path", "")).strip()
    bytes_written = last_write.get("bytes_written")
    replacements = last_write.get("replacements")

    details: list[str] = []
    if bytes_written is not None:
        details.append(f"bytes={bytes_written}")
    if replacements is not None and int(replacements) > 0:
        details.append(f"replacements={replacements}")

    base = "write"
    if mode:
        base = f"write ({mode})"
    if path:
        base = f"{base} `{path}`"
    if details:
        return f"{base}: {' | '.join(details)}"
    return base if path or mode else ""


def _summarize_search(last_search: Any) -> str:
    if not isinstance(last_search, dict):
        return ""
    query = str(last_search.get("query", "")).strip()
    results = last_search.get("results", [])
    if not isinstance(results, list):
        results = []
    count = len(results)
    if not query and count == 0:
        return ""

    top_title = ""
    if results:
        first = results[0]
        if isinstance(first, dict):
            top_title = str(first.get("title", "")).strip()
    if query and top_title:
        return f"search '{query}': {count} results (top: {top_title})"
    if query:
        return f"search '{query}': {count} results"
    return f"search: {count} results"


def _subtask_sort_key(marker: Any) -> tuple[int, str]:
    marker_id = str(getattr(marker, "id", ""))
    suffix = marker_id.rsplit("::subtask::", maxsplit=1)[-1]
    try:
        return int(suffix), marker_id
    except ValueError:
        return 10_000, marker_id


def _normalize_analysis(last_thought: Any) -> str:
    if not isinstance(last_thought, dict):
        return ""
    raw = str(last_thought.get("analysis", "")).strip()
    if not raw:
        return ""

    parsed = _try_parse_json(raw)
    if isinstance(parsed, dict):
        steps = parsed.get("steps")
        if isinstance(steps, list):
            normalized_steps = [
                str(step).strip() for step in steps if str(step).strip()
            ]
            if normalized_steps:
                return "; ".join(normalized_steps)

        next_actions = parsed.get("next_actions")
        if isinstance(next_actions, list):
            normalized_actions: list[str] = []
            for action in next_actions:
                if isinstance(action, dict):
                    description = str(action.get("description", "")).strip()
                    label = str(action.get("action", "")).strip()
                    if description and label:
                        normalized_actions.append(f"{label}: {description}")
                    elif description:
                        normalized_actions.append(description)
                    elif label:
                        normalized_actions.append(label)
                else:
                    text = str(action).strip()
                    if text:
                        normalized_actions.append(text)
            if normalized_actions:
                return "; ".join(normalized_actions)

        task = str(parsed.get("task", "")).strip()
        if task:
            return task

    if isinstance(parsed, list):
        normalized_items = [str(item).strip() for item in parsed if str(item).strip()]
        if normalized_items:
            return "; ".join(normalized_items)

    return raw


def _try_parse_json(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _workspace_context(workspace: Any) -> str:
    if workspace is None or not hasattr(workspace, "get_context_summary"):
        return ""
    try:
        return str(workspace.get_context_summary()).strip()
    except Exception:  # noqa: BLE001
        return ""


def _print_emergence_dashboard(emergence: dict[str, Any]) -> None:
    print("Emergence dashboard:")
    if not emergence:
        print("- disabled")
        return

    ordered_metrics = [
        "specialization_entropy",
        "colony_specialization",
        "collaboration_density",
        "action_switching_rate",
        "convergence_tick",
        "lock_contention_rate",
        "parallel_utilization",
        "pressure_entropy",
    ]
    for metric in ordered_metrics:
        if metric not in emergence:
            continue
        value = emergence[metric]
        if isinstance(value, float):
            print(f"- {metric}: {value:.4f}")
        else:
            print(f"- {metric}: {value}")


def _dag_info(markers: list[Any]) -> dict[str, Any]:
    cast_markers = [marker for marker in markers if isinstance(marker, Marker)]
    dependency_edges = 0
    for marker in cast_markers:
        depends_on = marker.payload.get("depends_on")
        if isinstance(depends_on, list):
            dependency_edges += len(depends_on)
    return {
        "is_valid": validate_dag(cast_markers),
        "nodes": len(cast_markers),
        "edges": dependency_edges,
    }


def _maybe_build_skills_store(config: dict[str, Any]) -> MarkerStore | None:
    """Build cross-run skills marker store when the skill library is enabled."""
    skill_cfg = dict(config.get("skill_library", {}))
    if not bool(skill_cfg.get("enabled", False)):
        return None
    db_path = Path(str(skill_cfg.get("db_path", SKILLS_DB_PATH)))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return MarkerStore(
        db_path=db_path,
        traceability=False,
        session_isolation=False,
    )


def _maybe_build_protocol_store(config: dict[str, Any]) -> MarkerStore | None:
    """Build cross-run protocol marker store when the protocol artifact is enabled."""
    proto_cfg = dict(config.get("protocol", {}))
    if not bool(proto_cfg.get("enabled", False)):
        return None
    db_path = Path(str(proto_cfg.get("db_path", PROTOCOLS_DB_PATH)))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return MarkerStore(
        db_path=db_path,
        traceability=False,
        session_isolation=False,
    )


def _build_protocol_namespace(config: dict[str, Any], adapter_name: str) -> str:
    """Return a stable namespace key for this (adapter, config) combination."""
    import hashlib

    proto_cfg = dict(config.get("protocol", {}))
    explicit = str(proto_cfg.get("namespace", "")).strip()
    if explicit:
        if explicit.startswith("coordination_protocol::"):
            return explicit
        return f"coordination_protocol::{adapter_name}::{explicit}"

    llm_cfg = dict(config.get("llm", {}))
    pressures_cfg = dict(config.get("pressures", {}))
    skill_cfg = dict(config.get("skill_library", {}))
    emergence_cfg = dict(config.get("emergence", {}))
    feedback_cfg = dict(emergence_cfg.get("feedback_loop", {}))
    key = {
        "adapter": str(adapter_name).strip(),
        "model": str(llm_cfg.get("model", "")).strip(),
        "alpha": float(pressures_cfg.get("alpha", 1.0)),
        "beta": float(pressures_cfg.get("beta", 1.0)),
        "skill_library": bool(skill_cfg.get("enabled", False)),
        "protocol": bool(proto_cfg.get("enabled", False)),
        "feedback_loop": bool(feedback_cfg.get("enabled", False)),
    }
    digest = hashlib.md5(json.dumps(key, sort_keys=True).encode("utf-8")).hexdigest()[
        :8
    ]
    return f"coordination_protocol::{adapter_name}::{digest}"


def _set_config_path(config: dict[str, Any], path: str, value: Any) -> None:
    """Apply a dotted-path assignment to an existing nested dict."""
    keys = [key for key in str(path).split(".") if key]
    if not keys:
        return
    cursor: Any = config
    for key in keys[:-1]:
        if not isinstance(cursor, dict) or key not in cursor:
            return
        cursor = cursor[key]
    if isinstance(cursor, dict):
        cursor[keys[-1]] = value


def _maybe_apply_cross_run_protocol(
    *,
    config: dict[str, Any],
    protocol_store: MarkerStore | None,
    namespace: str,
) -> bool:
    """Apply clamped best-protocol adaptations to config before the run starts."""
    return bool(
        _apply_cross_run_protocol(
            config=config,
            protocol_store=protocol_store,
            namespace=namespace,
        ).get("applied", False)
    )


def _apply_cross_run_protocol(
    *,
    config: dict[str, Any],
    protocol_store: MarkerStore | None,
    namespace: str,
) -> dict[str, Any]:
    """Apply best-protocol adaptations and return load/apply diagnostics."""
    cross_run_cfg = dict(config.get("emergence", {}).get("cross_run", {}))
    if not bool(cross_run_cfg.get("enabled", False)):
        return {"namespace": namespace, "loaded": False, "applied": False, "reason": "disabled"}
    if protocol_store is None:
        return {"namespace": namespace, "loaded": False, "applied": False, "reason": "store_missing"}

    baseline = protocol_store.load_protocol_marker(slot="baseline", namespace=namespace)
    best = protocol_store.load_protocol_marker(slot="best", namespace=namespace)
    if not baseline or not best:
        return {"namespace": namespace, "loaded": False, "applied": False, "reason": "missing_baseline_or_best"}

    adaptations = dict(best.get("adaptations", {}) or {})
    if not adaptations:
        return {"namespace": namespace, "loaded": True, "applied": False, "reason": "no_adaptations"}

    max_delta = float(cross_run_cfg.get("max_total_delta", 0.15))
    baseline_config = dict(baseline.get("config", {}) or {})
    clamped = clamp_cross_run_adaptations(
        adaptations,
        baseline_config,
        max_total_delta=max_delta,
    )
    for path, value in clamped.items():
        _set_config_path(config, str(path), value)
    return {
        "namespace": namespace,
        "loaded": True,
        "applied": bool(clamped),
        "reason": "applied" if clamped else "clamped_empty",
        "adaptations": clamped,
    }


def _persist_protocol(
    *,
    result: Any,
    evaluation: dict[str, Any],
    config: dict[str, Any],
    protocol_store: MarkerStore | None,
    namespace: str,
    session_id: str,
) -> None:
    """Persist coordination protocol artifacts after one run completes."""
    cross_run_cfg = dict(config.get("emergence", {}).get("cross_run", {}))
    if not bool(cross_run_cfg.get("enabled", False)):
        return
    if protocol_store is None:
        return
    if bool(cross_run_cfg.get("read_only", False)):
        return

    metrics = dict(result.emergence_summary or {})
    adaptations = dict(compute_adaptations(metrics, config))
    score = float(compute_protocol_score(evaluation or {}))

    payload_latest: dict[str, Any] = {
        "metrics": metrics,
        "adaptations": adaptations,
        "score": score,
        "session_id": session_id,
    }
    protocol_store.save_protocol_marker(
        slot="latest",
        namespace=namespace,
        payload=payload_latest,
    )

    if (
        protocol_store.load_protocol_marker(slot="baseline", namespace=namespace)
        is None
    ):
        protocol_store.save_protocol_marker(
            slot="baseline",
            namespace=namespace,
            payload={
                "config": dict(config),
                "session_id": session_id,
            },
        )

    current_best = protocol_store.load_protocol_marker(slot="best", namespace=namespace)
    if current_best is None or score > float(current_best.get("score", -1e9)):
        protocol_store.save_protocol_marker(
            slot="best",
            namespace=namespace,
            payload=payload_latest,
        )


if __name__ == "__main__":
    raise SystemExit(main())
