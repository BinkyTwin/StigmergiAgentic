"""Run one TravelPlanner query and export a structured JSON payload."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.environment import Environment
from core.marker import Marker
from core.marker_store import MarkerStore
from core.orchestrator import Orchestrator
from core.tool_registry import ToolRegistry
from main import (
    DEFAULT_DB_PATH,
    _build_adapter,
    _build_agents,
    _build_config,
    _build_run_summary,
    _build_travelplanner_response,
    _cleanup_session,
    _dag_info,
    _maybe_create_llm_client,
    _workspace_context,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one TravelPlanner query and export final_plan JSON."
    )
    parser.add_argument("--objective", type=str, required=True)
    parser.add_argument("--query-idx", type=int, required=True)
    parser.add_argument("--workspace", type=str, default=".")
    parser.add_argument("--data-dir", type=str, default=None)
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--max-ticks", type=int, default=None)
    parser.add_argument("--agents", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--keep-session", action="store_true", default=False)
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()
    session_id = str(uuid4())

    cfg_args = argparse.Namespace(
        adapter="travelplanner",
        objective=args.objective,
        workspace=args.workspace,
        data_dir=args.data_dir,
        query_idx=args.query_idx,
        config=args.config,
        max_ticks=args.max_ticks,
        agents=args.agents,
        seed=args.seed,
        keep_session=args.keep_session,
    )

    config = _build_config(cfg_args)
    adapter = _build_adapter(name="travelplanner", config=config)
    workspace = adapter.create_workspace(config)
    objective = adapter.create_objective(
        {"objective": args.objective, "query_idx": args.query_idx},
        config,
    )
    workspace_context = _workspace_context(workspace)
    markers_cfg = dict(config.get("markers", {}))
    session_isolation = bool(markers_cfg.get("session_isolation", False))

    store = MarkerStore(
        db_path=DEFAULT_DB_PATH,
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

    evaluation = adapter.evaluate_run(
        {
            "markers": result.final_snapshot.markers,
            "stop_reason": result.stop_reason,
        }
    )
    dag_info = _dag_info(result.final_snapshot.markers)
    assistant_response = _build_travelplanner_response(result.final_snapshot.markers)
    summary = _build_run_summary(
        adapter_name="travelplanner",
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
    )

    final_plan = summary.get("final_plan", [])
    if not isinstance(final_plan, list):
        final_plan = []
    raw_final_pass = bool(summary.get("raw_final_pass", False))
    strict_final_pass = bool(summary.get("strict_final_pass", False))
    failure_reason = str(summary.get("failure_reason", "ok"))

    output = {
        "status": "ok",
        "query_idx": int(objective.payload.get("query_idx", args.query_idx)),
        "objective": objective.description,
        "objective_id": objective.objective_id,
        "summary": summary,
        "assistant_response": assistant_response,
        "evaluation": evaluation,
        "failure_reason": failure_reason,
        "raw_final_pass": raw_final_pass,
        "strict_final_pass": strict_final_pass,
        "final_pass": strict_final_pass,
        "artifact_delivered": bool(final_plan),
        "final_plan": final_plan,
        "plan": final_plan,
    }
    print(json.dumps(output, indent=2, sort_keys=True))

    if not args.keep_session and session_isolation:
        _cleanup_session(Path(store.db_path).parent)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
