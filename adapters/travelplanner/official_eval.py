"""Wrapper around official TravelPlanner evaluation code (OSU-NLP-Group)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


OFFICIAL_ROOT = Path(__file__).resolve().parents[2] / "third_party" / "travelplanner_official"
OFFICIAL_RUNNER = OFFICIAL_ROOT / "runner.py"


@dataclass(slots=True)
class OfficialPlanEvaluation:
    delivered: bool
    commonsense: dict[str, bool | None]
    hard: dict[str, bool | None]
    commonsense_messages: dict[str, str | None]
    hard_messages: dict[str, str | None]
    commonsense_macro_pass: bool
    hard_macro_pass: bool
    final_pass: bool
    estimated_cost: float


class OfficialTravelPlannerEvaluator:
    """Bridge that executes upstream TravelPlanner evaluation logic in a subprocess."""

    def __init__(self, *, database_root: str | Path, dataset_split: str = "validation") -> None:
        self.database_root = Path(database_root).expanduser().resolve()
        self.dataset_split = str(dataset_split).strip() or "validation"

    def evaluate_plan(self, *, query_data: dict[str, Any], plan: list[dict[str, Any]]) -> OfficialPlanEvaluation:
        if not plan:
            return self._empty_plan_evaluation()

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as query_file:
            query_path = Path(query_file.name)
            query_file.write(json.dumps(query_data, ensure_ascii=True))

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as plan_file:
            plan_path = Path(plan_file.name)
            plan_file.write(json.dumps(plan, ensure_ascii=True))

        try:
            payload = self._run_runner(
                [
                    "query",
                    "--database-root",
                    str(self.database_root),
                    "--query-path",
                    str(query_path),
                    "--plan-path",
                    str(plan_path),
                ]
            )
        finally:
            query_path.unlink(missing_ok=True)
            plan_path.unlink(missing_ok=True)

        delivered = bool(plan) and bool(payload.get("delivered", False))
        final_pass = delivered and bool(payload.get("final_pass", False))
        return OfficialPlanEvaluation(
            delivered=delivered,
            commonsense=dict(payload.get("commonsense", {})),
            hard=dict(payload.get("hard", {})),
            commonsense_messages=dict(payload.get("commonsense_messages", {})),
            hard_messages=dict(payload.get("hard_messages", {})),
            commonsense_macro_pass=bool(payload.get("commonsense_macro_pass", False)),
            hard_macro_pass=bool(payload.get("hard_macro_pass", False)),
            final_pass=final_pass,
            estimated_cost=float(payload.get("estimated_cost", 0.0)),
        )

    def _empty_plan_evaluation(self) -> OfficialPlanEvaluation:
        commonsense = {
            "is_valid_information_in_current_city": False,
            "is_valid_information_in_sandbox": False,
            "is_reasonable_visiting_city": False,
            "is_valid_restaurants": False,
            "is_valid_transportation": False,
            "is_valid_attractions": False,
            "is_valid_accommodation": False,
            "is_not_absent": False,
        }
        hard = {
            "valid_cost": False,
            "valid_room_rule": False,
            "valid_cuisine": False,
            "valid_room_type": False,
            "valid_transportation": False,
        }
        messages = {key: "empty plan is not a delivered itinerary" for key in commonsense}
        hard_messages = {key: "empty plan is not a delivered itinerary" for key in hard}
        return OfficialPlanEvaluation(
            delivered=False,
            commonsense=commonsense,
            hard=hard,
            commonsense_messages=messages,
            hard_messages=hard_messages,
            commonsense_macro_pass=False,
            hard_macro_pass=False,
            final_pass=False,
            estimated_cost=0.0,
        )

    def evaluate_predictions_by_query_idx(
        self,
        *,
        predictions: dict[int, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as predictions_file:
            predictions_path = Path(predictions_file.name)
            serialized = {str(int(key)): value for key, value in predictions.items()}
            predictions_file.write(json.dumps(serialized, ensure_ascii=True))

        try:
            payload = self._run_runner(
                [
                    "full",
                    "--database-root",
                    str(self.database_root),
                    "--split",
                    self.dataset_split,
                    "--predictions-path",
                    str(predictions_path),
                ]
            )
        finally:
            predictions_path.unlink(missing_ok=True)

        return {
            "delivery_rate": float(payload.get("delivery_rate", 0.0)),
            "commonsense_micro": float(payload.get("commonsense_micro", 0.0)),
            "commonsense_macro": float(payload.get("commonsense_macro", 0.0)),
            "hard_constraint_micro": float(payload.get("hard_constraint_micro", 0.0)),
            "hard_constraint_macro": float(payload.get("hard_constraint_macro", 0.0)),
            "final_pass_rate": float(payload.get("final_pass_rate", 0.0)),
            "evaluated_queries": int(payload.get("evaluated_queries", 0)),
            "official_detailed": payload.get("official_detailed", {}),
        }

    def failed_constraints(self, evaluation: OfficialPlanEvaluation) -> list[str]:
        failed: list[str] = []
        for name, value in evaluation.commonsense.items():
            if value is False:
                failed.append(f"commonsense:{name}")
        for name, value in evaluation.hard.items():
            if value is False:
                failed.append(f"hard:{name}")
        return failed

    def _run_runner(self, args: list[str]) -> dict[str, Any]:
        if not OFFICIAL_RUNNER.exists():
            raise FileNotFoundError(f"Official runner not found: {OFFICIAL_RUNNER}")

        cmd = [
            sys.executable,
            str(OFFICIAL_RUNNER),
            *args,
        ]
        proc = subprocess.run(
            cmd,
            cwd=OFFICIAL_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                "Official TravelPlanner evaluator failed: "
                f"exit={proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr}"
            )

        text = proc.stdout.strip()
        if not text:
            return {}
        return json.loads(text.splitlines()[-1])
