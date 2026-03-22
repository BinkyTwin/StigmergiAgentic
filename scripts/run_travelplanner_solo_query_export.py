"""Run one TravelPlanner query with a single direct planning call and export JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.travelplanner.adapter import TravelPlannerAdapter
from adapters.travelplanner.evaluator import TravelPlannerEvaluator
from adapters.travelplanner.tools import PlanDayTool
from core.schemas import TravelItineraryOutput
from main import _build_config, _maybe_create_llm_client


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one TravelPlanner query with a solo single-call planner"
    )
    parser.add_argument("--objective", type=str, required=True)
    parser.add_argument("--query-idx", type=int, required=True)
    parser.add_argument("--workspace", type=str, default=".")
    parser.add_argument("--data-dir", type=str, default=None)
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--seed", type=int, default=None)
    return parser.parse_args()


def _build_runtime_config(args: argparse.Namespace) -> dict[str, Any]:
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
    return _build_config(cfg_args)


def _render_assistant_response(plan: list[dict[str, Any]]) -> str:
    if not plan:
        return "No travel plan generated."

    lines: list[str] = []
    for index, day in enumerate(plan, start=1):
        lines.append(
            f"Day {index}: {day.get('current_city', '-')} | "
            f"transport={day.get('transportation', '-')} | "
            f"breakfast={day.get('breakfast', '-')} | "
            f"attraction={day.get('attraction', '-')} | "
            f"lunch={day.get('lunch', '-')} | "
            f"dinner={day.get('dinner', '-')} | "
            f"accommodation={day.get('accommodation', '-')}"
        )
    return "\n".join(lines)


def main() -> int:
    load_dotenv()
    args = parse_args()
    config = _build_runtime_config(args)
    adapter = TravelPlannerAdapter(config=config)
    workspace = adapter.create_workspace(config)
    objective = adapter.create_objective(
        {"objective": args.objective, "query_idx": args.query_idx},
        config,
    )
    query_data = dict(objective.payload.get("query_data", {}))

    planner = PlanDayTool(config=config, max_planning_attempts=1)
    raw_search_payload: dict[str, Any] = {}
    planner._inject_default_search_payloads(  # noqa: SLF001 - deliberate notebook-facing reuse
        results=raw_search_payload,
        query_data=query_data,
        workspace=workspace,
    )
    search_payload = planner._compact_search_payload(  # noqa: SLF001 - deliberate notebook-facing reuse
        raw_search_payload,
        query_data=query_data,
    )
    prompt = planner._build_prompt(  # noqa: SLF001 - deliberate notebook-facing reuse
        query_data=query_data,
        search_payload=search_payload,
        validation_feedback=[],
    )

    llm_client = _maybe_create_llm_client(config=config)
    if llm_client is None:
        raise RuntimeError("LLM client is unavailable; check provider configuration and API key.")

    response = llm_client.call(prompt=prompt, response_schema=TravelItineraryOutput)
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, TravelItineraryOutput):
        itinerary = [day.model_dump() for day in parsed.plan]
    else:
        itinerary = planner._parse_itinerary(  # noqa: SLF001 - deliberate notebook-facing reuse
            raw_content=str(getattr(response, "content", "")),
            llm_client=llm_client,
        )
    itinerary = planner._normalize_itinerary(  # noqa: SLF001 - deliberate notebook-facing reuse
        itinerary=itinerary,
        query_data=query_data,
        search_payload=search_payload,
    )

    evaluator = TravelPlannerEvaluator(workspace=workspace)
    plan_evaluation = evaluator.evaluate_plan(query_data=query_data, plan=itinerary)
    evaluation = evaluator.aggregate([plan_evaluation])
    assistant_response = _render_assistant_response(itinerary)

    output = {
        "status": "ok",
        "query_idx": int(query_data.get("query_idx", args.query_idx)),
        "objective": objective.description,
        "objective_id": objective.objective_id,
        "assistant_response": assistant_response,
        "evaluation": evaluation,
        "final_pass": bool(plan_evaluation.final_pass),
        "final_plan": itinerary,
        "plan": itinerary,
        "summary": {
            "adapter": "travelplanner_solo",
            "llm_provider": str(config.get("llm", {}).get("provider", "")),
            "llm_model": str(config.get("llm", {}).get("model", "")),
            "tokens_used": int(getattr(response, "tokens_used", 0)),
            "cost_used": float(getattr(response, "cost_usd", 0.0)),
            "search_payload_keys": sorted(search_payload.keys()),
        },
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
