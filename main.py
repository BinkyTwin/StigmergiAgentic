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


if __name__ == "__main__":
    raise SystemExit(main())
