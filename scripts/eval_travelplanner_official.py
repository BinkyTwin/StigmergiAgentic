"""Run official TravelPlanner evaluation on generated predictions."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any

from datasets import load_dataset

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.travelplanner.official_eval import OfficialTravelPlannerEvaluator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate TravelPlanner predictions with official OSU code")
    parser.add_argument(
        "--runs-json",
        type=Path,
        required=True,
        help="Path to a JSON file containing a top-level `runs` array",
    )
    parser.add_argument(
        "--database-root",
        type=Path,
        default=Path("data/travelplanner/database"),
        help="TravelPlanner database root used for official constraint checks",
    )
    parser.add_argument(
        "--split",
        type=str,
        default="validation",
        help="Dataset split (default: validation)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional output JSON path",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=None,
        help="Optional inclusive subset start index for pilot/subset evaluation",
    )
    parser.add_argument(
        "--end-index",
        type=int,
        default=None,
        help="Optional exclusive subset end index for pilot/subset evaluation",
    )
    return parser.parse_args()


def build_predictions(payload: dict[str, Any]) -> dict[int, list[dict[str, Any]]]:
    runs = payload.get("runs", [])
    if not isinstance(runs, list):
        raise ValueError("runs-json must contain a list under key `runs`")

    predictions: dict[int, list[dict[str, Any]]] = {}
    for run in runs:
        if not isinstance(run, dict):
            continue
        try:
            query_idx = int(run.get("query_idx", -1))
        except Exception:  # noqa: BLE001
            continue
        if query_idx < 0:
            continue

        plan = run.get("final_plan")
        if not isinstance(plan, list):
            plan = run.get("plan")
        if not isinstance(plan, list):
            plan = []

        predictions[query_idx] = plan
    return predictions


def normalize_local_constraint(query_data: dict[str, Any]) -> dict[str, Any]:
    local_constraint = query_data.get("local_constraint")
    if isinstance(local_constraint, str):
        try:
            local_constraint = ast.literal_eval(local_constraint)
        except Exception:  # noqa: BLE001
            local_constraint = {}
    if not isinstance(local_constraint, dict):
        local_constraint = {}
    return local_constraint


def applicable_hard_constraints(query_data: dict[str, Any]) -> set[str]:
    level = str(query_data.get("level", "")).strip().lower()
    local_constraint = normalize_local_constraint(query_data)
    applicable = {"valid_cost"}
    if level in {"medium", "hard"}:
        if local_constraint.get("house rule") is not None:
            applicable.add("valid_room_rule")
        if local_constraint.get("cuisine") is not None:
            applicable.add("valid_cuisine")
        if local_constraint.get("room type") is not None:
            applicable.add("valid_room_type")
    if level == "hard" and local_constraint.get("transportation") is not None:
        applicable.add("valid_transportation")
    return applicable


def evaluate_subset(
    *,
    evaluator: OfficialTravelPlannerEvaluator,
    predictions: dict[int, list[dict[str, Any]]],
    split: str,
    start_index: int,
    end_index: int,
) -> dict[str, Any]:
    dataset = load_dataset("osunlp/TravelPlanner", split)[split]
    total = len(dataset)
    start = max(0, start_index)
    end = total if end_index is None else min(total, max(start, end_index))
    query_indices = list(range(start, end))
    if not query_indices:
        return {
            "delivery_rate": 0.0,
            "commonsense_micro": 0.0,
            "commonsense_macro": 0.0,
            "hard_constraint_micro": 0.0,
            "hard_constraint_macro": 0.0,
            "final_pass_rate": 0.0,
            "evaluated_queries": 0,
            "official_detailed": {
                "mode": "subset",
                "query_indices": [],
                "hard_constraint_total": 0,
            },
        }

    delivery_count = 0
    commonsense_micro_pass = 0
    commonsense_macro_count = 0
    hard_micro_pass = 0
    hard_micro_total = 0
    hard_macro_count = 0
    final_pass_count = 0

    for query_idx in query_indices:
        query_data = dict(dataset[query_idx])
        plan = predictions.get(query_idx, [])
        evaluation = evaluator.evaluate_plan(query_data=query_data, plan=plan)

        if evaluation.delivered:
            delivery_count += 1
        commonsense_micro_pass += sum(1 for value in evaluation.commonsense.values() if value is True)
        if evaluation.commonsense_macro_pass:
            commonsense_macro_count += 1

        applicable = applicable_hard_constraints(query_data)
        hard_micro_total += len(applicable)
        for name in applicable:
            if evaluation.hard.get(name) is True:
                hard_micro_pass += 1

        if evaluation.hard_macro_pass:
            hard_macro_count += 1
        if evaluation.final_pass:
            final_pass_count += 1

    count = len(query_indices)
    return {
        "delivery_rate": delivery_count / count,
        "commonsense_micro": commonsense_micro_pass / (8 * count),
        "commonsense_macro": commonsense_macro_count / count,
        "hard_constraint_micro": (hard_micro_pass / hard_micro_total) if hard_micro_total else 0.0,
        "hard_constraint_macro": hard_macro_count / count,
        "final_pass_rate": final_pass_count / count,
        "evaluated_queries": count,
        "official_detailed": {
            "mode": "subset",
            "query_indices": query_indices,
            "hard_constraint_total": hard_micro_total,
        },
    }


def main() -> int:
    args = parse_args()
    runs_json = args.runs_json.expanduser().resolve()
    database_root = args.database_root.expanduser().resolve()

    payload = json.loads(runs_json.read_text(encoding="utf-8"))
    predictions = build_predictions(payload)

    evaluator = OfficialTravelPlannerEvaluator(
        database_root=database_root,
        dataset_split=args.split,
    )
    if args.start_index is not None or args.end_index is not None:
        start_index = args.start_index or 0
        end_index = args.end_index
        scores = evaluate_subset(
            evaluator=evaluator,
            predictions=predictions,
            split=args.split,
            start_index=start_index,
            end_index=end_index,
        )
        score_mode = "subset"
        evaluated_indices = scores.get("official_detailed", {}).get("query_indices", [])
    else:
        scores = evaluator.evaluate_predictions_by_query_idx(predictions=predictions)
        score_mode = "full_split"
        evaluated_indices = scores.get("official_detailed", {}).get("query_indices", [])

    output = {
        "runs_json": str(runs_json),
        "database_root": str(database_root),
        "split": args.split,
        "predicted_queries": sorted(predictions.keys()),
        "score_mode": score_mode,
        "start_index": args.start_index,
        "end_index": args.end_index,
        "evaluated_query_indices": evaluated_indices,
        "scores": scores,
    }

    rendered = json.dumps(output, indent=2, ensure_ascii=True)
    print(rendered)

    if args.out is not None:
        out_path = args.out.expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
        print(f"wrote {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
