"""TravelPlanner evaluator backed by official OSU-NLP-Group constraints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.marker import Marker

from .official_eval import OfficialTravelPlannerEvaluator
from .workspace import TravelPlannerWorkspace


@dataclass(slots=True)
class PlanEvaluation:
    """Per-query evaluation payload."""

    delivered: bool
    commonsense: dict[str, bool | None]
    commonsense_messages: dict[str, str | None]
    hard: dict[str, bool | None]
    hard_messages: dict[str, str | None]
    estimated_cost: float

    @property
    def commonsense_macro_pass(self) -> bool:
        return all(value is True for value in self.commonsense.values() if value is not None)

    @property
    def hard_macro_pass(self) -> bool:
        return all(value is True for value in self.hard.values() if value is not None)

    @property
    def final_pass(self) -> bool:
        return self.delivered and self.commonsense_macro_pass and self.hard_macro_pass


class TravelPlannerEvaluator:
    """Evaluate plans with official TravelPlanner constraints."""

    def __init__(self, *, workspace: TravelPlannerWorkspace) -> None:
        self.workspace = workspace
        self._official = OfficialTravelPlannerEvaluator(
            database_root=self.workspace.database_root,
            dataset_split=self.workspace.dataset_split,
        )

    def evaluate_snapshot(self, markers: list[Marker] | list[dict[str, Any]]) -> dict[str, Any]:
        typed_markers = [
            marker if isinstance(marker, Marker) else Marker.from_dict(marker)
            for marker in markers
            if isinstance(marker, (Marker, dict))
        ]

        finalize_candidates = [
            marker
            for marker in typed_markers
            if marker.id.endswith("::finalize")
        ]
        source_markers = finalize_candidates if finalize_candidates else typed_markers

        query_plan_pairs: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
        seen_keys: set[str] = set()

        for marker in source_markers:
            payload = dict(marker.payload)
            query_data = payload.get("query_data")
            plan = payload.get("final_plan")
            if not isinstance(plan, list):
                plan = payload.get("plan")
            if not isinstance(query_data, dict):
                continue
            if isinstance(plan, list):
                key = str(query_data.get("query_idx", marker.id))
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                query_plan_pairs.append((query_data, plan))

        if not query_plan_pairs:
            return {
                "delivery_rate": 0.0,
                "commonsense_micro": 0.0,
                "commonsense_macro": 0.0,
                "hard_constraint_micro": 0.0,
                "hard_constraint_macro": 0.0,
                "final_pass_rate": 0.0,
                "evaluated_queries": 0,
            }

        evaluations = [
            self.evaluate_plan(query_data=query, plan=plan)
            for query, plan in query_plan_pairs
        ]
        return self.aggregate(evaluations)

    def evaluate_plan(self, *, query_data: dict[str, Any], plan: list[dict[str, Any]]) -> PlanEvaluation:
        official = self._official.evaluate_plan(query_data=query_data, plan=plan)
        commonsense = {
            "valid_info_current_city": official.commonsense.get("is_valid_information_in_current_city"),
            "valid_info_sandbox": official.commonsense.get("is_valid_information_in_sandbox"),
            "reasonable_city_route": official.commonsense.get("is_reasonable_visiting_city"),
            "valid_restaurants": official.commonsense.get("is_valid_restaurants"),
            "valid_transportation": official.commonsense.get("is_valid_transportation"),
            "valid_attractions": official.commonsense.get("is_valid_attractions"),
            "valid_accommodation": official.commonsense.get("is_valid_accommodation"),
            "not_absent": official.commonsense.get("is_not_absent"),
        }
        commonsense_messages = {
            "valid_info_current_city": official.commonsense_messages.get("is_valid_information_in_current_city"),
            "valid_info_sandbox": official.commonsense_messages.get("is_valid_information_in_sandbox"),
            "reasonable_city_route": official.commonsense_messages.get("is_reasonable_visiting_city"),
            "valid_restaurants": official.commonsense_messages.get("is_valid_restaurants"),
            "valid_transportation": official.commonsense_messages.get("is_valid_transportation"),
            "valid_attractions": official.commonsense_messages.get("is_valid_attractions"),
            "valid_accommodation": official.commonsense_messages.get("is_valid_accommodation"),
            "not_absent": official.commonsense_messages.get("is_not_absent"),
        }
        hard = {
            "valid_cost": official.hard.get("valid_cost"),
            "valid_room_rule": official.hard.get("valid_room_rule"),
            "valid_cuisine": official.hard.get("valid_cuisine"),
            "valid_room_type": official.hard.get("valid_room_type"),
            "valid_transportation": official.hard.get("valid_transportation"),
        }
        hard_messages = {
            "valid_cost": official.hard_messages.get("valid_cost"),
            "valid_room_rule": official.hard_messages.get("valid_room_rule"),
            "valid_cuisine": official.hard_messages.get("valid_cuisine"),
            "valid_room_type": official.hard_messages.get("valid_room_type"),
            "valid_transportation": official.hard_messages.get("valid_transportation"),
        }
        return PlanEvaluation(
            delivered=official.delivered,
            commonsense=commonsense,
            commonsense_messages=commonsense_messages,
            hard=hard,
            hard_messages=hard_messages,
            estimated_cost=float(official.estimated_cost),
        )

    def aggregate(self, evaluations: list[PlanEvaluation]) -> dict[str, Any]:
        total = len(evaluations)
        if total <= 0:
            return {
                "delivery_rate": 0.0,
                "commonsense_micro": 0.0,
                "commonsense_macro": 0.0,
                "hard_constraint_micro": 0.0,
                "hard_constraint_macro": 0.0,
                "final_pass_rate": 0.0,
                "evaluated_queries": 0,
            }

        delivery_count = sum(1 for eval_ in evaluations if eval_.delivered)
        commonsense_macro = sum(1 for eval_ in evaluations if eval_.commonsense_macro_pass)
        hard_macro = sum(1 for eval_ in evaluations if eval_.hard_macro_pass)
        final_macro = sum(1 for eval_ in evaluations if eval_.final_pass)

        commonsense_true = 0
        commonsense_total = 0
        hard_true = 0
        hard_total = 0

        for eval_ in evaluations:
            for value in eval_.commonsense.values():
                if value is None:
                    continue
                commonsense_total += 1
                if value:
                    commonsense_true += 1
            for value in eval_.hard.values():
                if value is None:
                    continue
                hard_total += 1
                if value:
                    hard_true += 1

        commonsense_micro = 0.0 if commonsense_total == 0 else commonsense_true / commonsense_total
        hard_micro = 0.0 if hard_total == 0 else hard_true / hard_total

        return {
            "delivery_rate": delivery_count / total,
            "commonsense_micro": commonsense_micro,
            "commonsense_macro": commonsense_macro / total,
            "hard_constraint_micro": hard_micro,
            "hard_constraint_macro": hard_macro / total,
            "final_pass_rate": final_macro / total,
            "evaluated_queries": total,
        }

    def failed_constraints(self, evaluation: PlanEvaluation) -> list[str]:
        failed: list[str] = []
        for name, value in evaluation.commonsense.items():
            if value is False:
                failed.append(f"commonsense:{name}")
        for name, value in evaluation.hard.items():
            if value is False:
                failed.append(f"hard:{name}")
        return failed

    def failure_feedback(self, evaluation: PlanEvaluation) -> list[str]:
        feedback: list[str] = []
        for name, value in evaluation.commonsense.items():
            if value is not False:
                continue
            message = evaluation.commonsense_messages.get(name)
            if message:
                feedback.append(f"commonsense:{name} - {message}")
            else:
                feedback.append(f"commonsense:{name}")
        for name, value in evaluation.hard.items():
            if value is not False:
                continue
            message = evaluation.hard_messages.get(name)
            if message:
                feedback.append(f"hard:{name} - {message}")
            else:
                feedback.append(f"hard:{name}")
        return feedback

    def evaluate_predictions_by_query_idx(
        self,
        *,
        predictions: dict[int, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        return self._official.evaluate_predictions_by_query_idx(predictions=predictions)
