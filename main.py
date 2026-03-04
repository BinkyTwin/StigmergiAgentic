"""CLI entrypoint for the V2 generic assistant runtime."""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

import yaml

from adapters.assistant import AssistantAdapter
from core.agent import StigmergicAgent
from core.config import load_config, merge_config, validate_config
from core.environment import Environment
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run one assistant session and print run summary as JSON."""
    args = parse_args(argv)

    config = _build_config(args)
    adapter = AssistantAdapter(config=config)
    workspace = adapter.create_workspace(config)

    objective = adapter.create_objective({"objective": args.objective}, config)

    store = MarkerStore(
        db_path=DEFAULT_DB_PATH,
        max_retry_count=int(config.get("guardrails", {}).get("max_retry_count", 3)),
        traceability=bool(config.get("guardrails", {}).get("traceability", True)),
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
        store.upsert_marker(marker=marker, agent_id="system_seed")

    llm_client = _maybe_create_llm_client(config=config)
    agents = _build_agents(config=config, registry=registry, seed=args.seed)

    orchestrator = Orchestrator(
        environment=environment,
        agents=agents,
        config=config,
        llm_client=llm_client,
    )
    result = orchestrator.run_sync()

    evaluation = adapter.evaluate_run({"markers": result.final_snapshot.markers})
    assistant_response = _build_assistant_response(
        objective_id=objective.objective_id,
        markers=result.final_snapshot.markers,
    )

    print("Assistant response:")
    print(assistant_response)
    print()

    summary = {
        "adapter": args.adapter,
        "objective_id": objective.objective_id,
        "stop_reason": result.stop_reason,
        "total_ticks": result.total_ticks,
        "agents": len(agents),
        "markers": len(result.final_snapshot.markers),
        "tokens_used": int(environment.tokens_used),
        "cost_used": float(environment.cost_used),
        "evaluation": evaluation,
        "assistant_response": assistant_response,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


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
    subtasks = [marker for marker in markers if str(getattr(marker, "id", "")).startswith(prefix)]
    subtasks = sorted(subtasks, key=_subtask_sort_key)

    if not subtasks:
        root = next(
            (marker for marker in markers if str(getattr(marker, "id", "")) == objective_id),
            None,
        )
        if root is None:
            return "No assistant response generated."
        analysis = _normalize_analysis(root.payload.get("last_thought"))
        return analysis or "No assistant response generated."

    lines: list[str] = []
    for index, marker in enumerate(subtasks, start=1):
        payload = dict(getattr(marker, "payload", {}))
        task = str(payload.get("task", "")).strip()
        analysis = _normalize_analysis(payload.get("last_thought"))

        if task and analysis:
            lines.append(f"{index}. {task} -> {analysis}")
            continue
        if task:
            lines.append(f"{index}. {task}")
            continue
        if analysis:
            lines.append(f"{index}. {analysis}")

    if not lines:
        return "No assistant response generated."
    return "\n".join(lines)


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
            normalized_steps = [str(step).strip() for step in steps if str(step).strip()]
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


if __name__ == "__main__":
    raise SystemExit(main())
