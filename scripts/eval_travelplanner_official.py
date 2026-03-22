"""Run official TravelPlanner evaluation on generated predictions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

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
    scores = evaluator.evaluate_predictions_by_query_idx(predictions=predictions)

    output = {
        "runs_json": str(runs_json),
        "database_root": str(database_root),
        "split": args.split,
        "predicted_queries": sorted(predictions.keys()),
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
