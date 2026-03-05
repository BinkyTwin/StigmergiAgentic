"""CLI entrypoint for the V2 generic assistant runtime."""

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

from adapters.assistant import AssistantAdapter
from core.agent import StigmergicAgent
from core.config import load_config, merge_config, validate_config
from core.dependency import validate_dag
from core.environment import Environment
from core.marker import Marker
from core.marker_store import MarkerStore
from core.orchestrator import Orchestrator
from core.tool_registry import ToolRegistry
from llm.client import LLMClient


ASSISTANT_CONFIG_PATH = Path("config/assistant.yaml")
DEFAULT_DB_PATH = Path("pheromones/markers.db")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for assistant execution."""
    parser = argparse.ArgumentParser(description="Stigmergic V2 assistant runtime")
    parser.add_argument("--adapter", choices=["assistant"], default="assistant")
    parser.add_argument("--objective", type=str, required=True)
    parser.add_argument("--workspace", type=str, default=".")
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
    adapter = AssistantAdapter(config=config)
    workspace = adapter.create_workspace(config)
    workspace_context = _workspace_context(workspace)

    objective = adapter.create_objective({"objective": args.objective}, config)
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
    environment = Environment(
        store=store,
        config=config,
        workspace=workspace,
        state_machine=adapter.define_state_machine(),
    )

    registry = ToolRegistry()
    adapter.register_tools(registry)

    for marker in adapter.initial_markers(objective=objective, agent_id="system_seed"):
        seeded = Marker.from_dict(marker.to_dict())
        payload = dict(seeded.payload)
        if workspace_context:
            payload.setdefault("workspace_context", workspace_context)
        seeded.payload = payload
        store.upsert_marker(marker=seeded, agent_id="system_seed")

    llm_client = _maybe_create_llm_client(config=config)
    agents = _build_agents(config=config, registry=registry, seed=args.seed)

    orchestrator = Orchestrator(
        environment=environment,
        agents=agents,
        config=config,
        llm_client=llm_client,
        session_id=session_id,
    )
    result = orchestrator.run_sync()

    evaluation = adapter.evaluate_run({"markers": result.final_snapshot.markers})
    dag_info = _dag_info(result.final_snapshot.markers)
    assistant_response = _build_assistant_response(
        objective_id=objective.objective_id,
        markers=result.final_snapshot.markers,
    )

    print(f"Session ID: {session_id}")
    print("Assistant response:")
    print(assistant_response)
    print()
    _print_emergence_dashboard(result.emergence_summary)
    print()

    summary = {
        "adapter": args.adapter,
        "objective_id": objective.objective_id,
        "session_id": session_id,
        "session_db_path": str(store.db_path),
        "stop_reason": result.stop_reason,
        "total_ticks": result.total_ticks,
        "agents": len(agents),
        "markers": len(result.final_snapshot.markers),
        "tokens_used": int(environment.tokens_used),
        "cost_used": float(environment.cost_used),
        "reinforcement": {
            "events": int(environment.reinforcement_events),
            "propagation_events": int(environment.propagation_events),
        },
        "maintenance": {
            "pruned_markers": int(environment.pruned_markers),
        },
        "emergence": dict(result.emergence_summary),
        "dag": dag_info,
        "evaluation": evaluation,
        "assistant_response": assistant_response,
    }
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

    assistant_overrides = _load_yaml(ASSISTANT_CONFIG_PATH)
    if assistant_overrides:
        config = merge_config(config, assistant_overrides)

    if args.config:
        user_overrides = _load_yaml(Path(args.config))
        config = merge_config(config, user_overrides)

    config.setdefault("tools", {})
    config["tools"]["sandbox_root"] = str(Path(args.workspace).expanduser().resolve())

    if args.max_ticks is not None:
        config.setdefault("orchestrator", {})
        config["orchestrator"]["max_ticks"] = int(args.max_ticks)

    if args.agents is not None:
        config.setdefault("agents", {})
        config["agents"]["num_agents"] = int(args.agents)

    validate_config(config)
    return config


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


if __name__ == "__main__":
    raise SystemExit(main())
