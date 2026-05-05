"""Run one TravelPlanner query with the MetaGPT-sequential baseline and export JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.travelplanner.adapter import TravelPlannerAdapter
from adapters.travelplanner.scientific_baselines import (
    TravelPlannerScientificBaselineRunner,
)
from main import _build_config, _maybe_create_llm_client


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one TravelPlanner query with the MetaGPT-sequential baseline"
    )
    parser.add_argument("--objective", type=str, required=True)
    parser.add_argument("--query-idx", type=int, required=True)
    parser.add_argument("--workspace", type=str, default=".")
    parser.add_argument("--data-dir", type=str, default=None)
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--seed", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()
    cfg_args = argparse.Namespace(
        adapter="travelplanner",
        objective=args.objective,
        workspace=args.workspace,
        data_dir=args.data_dir,
        query_idx=args.query_idx,
        config=args.config,
        max_ticks=None,
        agents=None,
        seed=args.seed,
        keep_session=False,
    )
    config = _build_config(cfg_args)
    adapter = TravelPlannerAdapter(config=config)
    workspace = adapter.create_workspace(config)
    objective = adapter.create_objective(
        {"objective": args.objective, "query_idx": args.query_idx},
        config,
    )
    query_data = dict(objective.payload.get("query_data", {}))

    llm_client = _maybe_create_llm_client(config=config)
    if llm_client is None:
        raise RuntimeError("LLM client is unavailable; check provider configuration and API key.")

    runner = TravelPlannerScientificBaselineRunner(
        mode="metagpt_sequential",
        config=config,
        workspace=workspace,
        llm_client=llm_client,
        seed=args.seed,
    )
    output = runner.run_query(
        objective=objective.description,
        objective_id=objective.objective_id,
        query_idx=int(query_data.get("query_idx", args.query_idx)),
        query_data=query_data,
    )
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
