"""Domain tools for TravelPlanner adapter."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from pydantic import ValidationError

from core.marker import Marker
from core.schemas import TravelItineraryOutput
from core.tool_registry import ActionResult, Tool

from .evaluator import TravelPlannerEvaluator


class _BaseTravelSearchTool(Tool):
    """Shared implementation for deterministic CSV-backed search tools."""

    action_type = ""
    workspace_method = ""
    required_fields: tuple[str, ...] = ()

    def __init__(self, *, config: dict[str, Any]) -> None:
        markers_cfg = dict(config.get("markers", {}))
        self.intensity_step = float(markers_cfg.get("intensity_step_tool", 0.05))
        self.intensity_floor = float(markers_cfg.get("intensity_floor", 0.1))

    def is_eligible(self, marker: Marker) -> bool:
        raw = marker.payload.get("eligible_actions")
        if isinstance(raw, (list, tuple, set)) and len(raw) > 0:
            return self.action_type in {str(item) for item in raw}
        if marker.state not in {"pending", "searching"}:
            return False
        return all(str(marker.payload.get(field, "")).strip() for field in self.required_fields)

    async def execute(
        self,
        *,
        agent_id: str,
        marker: Marker,
        environment: Any,
        llm_client: Any | None = None,
    ) -> ActionResult:
        workspace = getattr(environment, "workspace", None)
        if workspace is None or not hasattr(workspace, self.workspace_method):
            return ActionResult(
                action_type=self.action_type,
                metadata={"failed": True, "reason": "workspace_missing"},
            )

        call_kwargs: dict[str, str] = {}
        for field in self.required_fields:
            value = str(marker.payload.get(field, "")).strip()
            if not value:
                return ActionResult(
                    action_type=self.action_type,
                    metadata={"failed": True, "reason": f"missing_{field}"},
                )
            call_kwargs[field] = value

        search_fn = getattr(workspace, self.workspace_method)
        try:
            frame = search_fn(**call_kwargs)
        except Exception as exc:  # noqa: BLE001
            return ActionResult(
                action_type=self.action_type,
                metadata={"failed": True, "reason": str(exc)},
            )

        if isinstance(frame, pd.DataFrame):
            records = frame.to_dict(orient="records")
        else:
            records = []

        updated = Marker.from_dict(marker.to_dict())
        payload = dict(updated.payload)
        payload["search_type"] = self.action_type
        payload["results"] = records
        payload["result_count"] = len(records)
        payload["search_params"] = call_kwargs
        updated.payload = payload
        updated.state = "searching" if updated.state == "pending" else "terminal"
        updated.intensity = max(
            self.intensity_floor,
            float(updated.intensity) - self.intensity_step,
        )

        return ActionResult(action_type=self.action_type, marker_updates=[updated])


class SearchFlightsTool(_BaseTravelSearchTool):
    action_type = "search_flights"
    workspace_method = "search_flights"
    required_fields = ("origin", "dest", "date")


class SearchHotelsTool(_BaseTravelSearchTool):
    action_type = "search_hotels"
    workspace_method = "search_hotels"
    required_fields = ("city",)


class SearchRestaurantsTool(_BaseTravelSearchTool):
    action_type = "search_restaurants"
    workspace_method = "search_restaurants"
    required_fields = ("city",)


class SearchAttractionsTool(_BaseTravelSearchTool):
    action_type = "search_attractions"
    workspace_method = "search_attractions"
    required_fields = ("city",)


class PlanDayTool(Tool):
    """LLM-backed itinerary construction with JSON schema validation."""

    action_type = "plan_itinerary"

    def __init__(self, *, config: dict[str, Any]) -> None:
        self.config = config
        markers_cfg = dict(config.get("markers", {}))
        self.intensity_step = float(markers_cfg.get("intensity_step_tool", 0.05))
        self.intensity_floor = float(markers_cfg.get("intensity_floor", 0.1))

    def is_eligible(self, marker: Marker) -> bool:
        raw = marker.payload.get("eligible_actions")
        if isinstance(raw, (list, tuple, set)) and len(raw) > 0:
            return self.action_type in {str(item) for item in raw}
        return marker.state in {"pending", "planning", "terminal"}

    async def execute(
        self,
        *,
        agent_id: str,
        marker: Marker,
        environment: Any,
        llm_client: Any | None = None,
    ) -> ActionResult:
        query_data = marker.payload.get("query_data")
        if not isinstance(query_data, dict):
            return ActionResult(
                action_type=self.action_type,
                metadata={"failed": True, "reason": "missing_query_data"},
            )

        workspace = getattr(environment, "workspace", None)
        if workspace is None:
            return ActionResult(
                action_type=self.action_type,
                metadata={"failed": True, "reason": "workspace_missing"},
            )

        search_payload = self._collect_search_payloads(marker=marker, environment=environment)

        consumed_tokens = 0
        cost_usd = 0.0
        planner_model = "fallback"

        itinerary = self._fallback_plan(query_data=query_data, workspace=workspace)

        if llm_client is not None and (
            hasattr(llm_client, "acall") or hasattr(llm_client, "call")
        ):
            prompt = self._build_prompt(query_data=query_data, search_payload=search_payload)
            try:
                response = None
                if hasattr(llm_client, "acall"):
                    response = await llm_client.acall(
                        prompt=prompt,
                        response_schema=TravelItineraryOutput,
                    )
                elif hasattr(llm_client, "call"):
                    response = llm_client.call(
                        prompt=prompt,
                    )

                if response is not None:
                    parsed = getattr(response, "parsed", None)
                    if isinstance(parsed, TravelItineraryOutput):
                        itinerary = [day.model_dump() for day in parsed.plan]
                    else:
                        itinerary = self._parse_itinerary(
                            raw_content=str(getattr(response, "content", "")),
                            llm_client=llm_client,
                        )
                    consumed_tokens = int(getattr(response, "tokens_used", 0))
                    cost_usd = float(getattr(response, "cost_usd", 0.0))
                    planner_model = str(getattr(response, "model", "unknown"))
            except Exception:  # noqa: BLE001
                itinerary = self._fallback_plan(query_data=query_data, workspace=workspace)

        updated = Marker.from_dict(marker.to_dict())
        payload = dict(updated.payload)
        payload["plan"] = itinerary
        payload["search_payload"] = search_payload
        payload["planner_model"] = planner_model
        payload["planning_attempts"] = int(payload.get("planning_attempts", 0)) + 1
        payload["needs_replan"] = False
        updated.payload = payload

        if marker.state == "pending":
            updated.state = "planning"
        else:
            updated.state = "terminal"

        updated.intensity = max(
            self.intensity_floor,
            float(updated.intensity) - self.intensity_step,
        )

        return ActionResult(
            action_type=self.action_type,
            marker_updates=[updated],
            consumed_tokens=consumed_tokens,
            cost_usd=cost_usd,
        )

    def _build_prompt(
        self,
        *,
        query_data: dict[str, Any],
        search_payload: dict[str, Any],
    ) -> str:
        return (
            "You are a travel planning assistant. Build a day-by-day itinerary in strict JSON.\n"
            "Return only JSON matching this schema:\n"
            '{"plan":[{"current_city":"...","transportation":"...","breakfast":"...",'
            '"attraction":"...","lunch":"...","dinner":"...","accommodation":"..."}]}\n'
            "Use only plausible values from provided search data.\n"
            f"Query: {json.dumps(query_data, ensure_ascii=True)}\n"
            f"SearchData: {json.dumps(search_payload, ensure_ascii=True)}"
        )

    def _parse_itinerary(self, *, raw_content: str, llm_client: Any | None) -> list[dict[str, Any]]:
        candidates = [raw_content]
        if llm_client is not None and hasattr(llm_client, "extract_code_block"):
            try:
                candidates.insert(0, str(llm_client.extract_code_block(raw_content)))
            except Exception:  # noqa: BLE001
                pass

        for candidate in candidates:
            text = str(candidate).strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
                parsed = TravelItineraryOutput.model_validate(payload)
                return [day.model_dump() for day in parsed.plan]
            except (json.JSONDecodeError, ValidationError):
                continue
        return []

    def _collect_search_payloads(self, *, marker: Marker, environment: Any) -> dict[str, Any]:
        results: dict[str, Any] = {}
        depends_on = marker.payload.get("depends_on", [])
        if not isinstance(depends_on, list):
            return results

        for dep_id in depends_on:
            dependency = environment.store.get_marker(str(dep_id))
            if dependency is None:
                continue
            dep_payload = dict(dependency.payload)
            search_type = str(dep_payload.get("search_type", dependency.id)).strip()
            records = dep_payload.get("results", [])
            if isinstance(records, list):
                results[search_type] = records[:20]
        return results

    def _fallback_plan(self, *, query_data: dict[str, Any], workspace: Any) -> list[dict[str, str]]:
        days = max(1, int(query_data.get("days", 1)))
        origin = str(query_data.get("org", "")).strip()
        destination = str(query_data.get("dest", "")).strip()
        dates = query_data.get("date", [])
        people = int(query_data.get("people_number", 1))

        hotels = workspace.search_hotels(destination)
        restaurants = workspace.search_restaurants(destination)
        attractions = workspace.search_attractions(destination)
        outbound_date = str(dates[0]) if isinstance(dates, list) and dates else ""
        flights = workspace.search_flights(origin, destination, outbound_date)

        hotel_label = "-"
        if not hotels.empty:
            row = hotels.iloc[0]
            hotel_label = f"{row.get('NAME', '-')}, {row.get('city', destination)}"

        meal_label = "-"
        if not restaurants.empty:
            row = restaurants.iloc[0]
            meal_label = f"{row.get('Name', '-')}, {row.get('City', destination)}"

        attraction_label = "-"
        if not attractions.empty:
            row = attractions.iloc[0]
            attraction_label = f"{row.get('Name', '-')}, {row.get('City', destination)}"

        transport_out = f"Self-driving, from {origin} to {destination}, cost: TBD"
        if not flights.empty:
            flight = flights.iloc[0]
            transport_out = (
                f"Flight Number: {flight.get('Flight Number')}, "
                f"from {origin} to {destination}"
            )

        transport_back = f"Self-driving, from {destination} to {origin}, cost: TBD"

        plan: list[dict[str, str]] = []
        for day_idx in range(days):
            if day_idx == 0:
                current_city = f"from {origin} to {destination}"
                transportation = transport_out
            elif day_idx == days - 1:
                current_city = f"from {destination} to {origin}"
                transportation = transport_back
            else:
                current_city = destination
                transportation = "-"

            plan.append(
                {
                    "current_city": current_city,
                    "transportation": transportation,
                    "breakfast": meal_label,
                    "attraction": attraction_label,
                    "lunch": meal_label,
                    "dinner": meal_label,
                    "accommodation": "-" if day_idx == days - 1 else hotel_label,
                }
            )

        if days == 1:
            # one-day trips still need at least one concrete transport placeholder
            plan[0]["transportation"] = transport_out
        return plan


class ValidateConstraintsTool(Tool):
    """Programmatic validation against commonsense and hard constraints."""

    action_type = "validate_constraints"

    def __init__(self, *, config: dict[str, Any], max_retries: int = 2) -> None:
        self.config = config
        self.max_retries = int(max_retries)
        markers_cfg = dict(config.get("markers", {}))
        self.intensity_step = float(markers_cfg.get("intensity_step_tool", 0.05))
        self.intensity_floor = float(markers_cfg.get("intensity_floor", 0.1))

    def is_eligible(self, marker: Marker) -> bool:
        raw = marker.payload.get("eligible_actions")
        if isinstance(raw, (list, tuple, set)) and len(raw) > 0:
            return self.action_type in {str(item) for item in raw}
        return marker.state in {"pending", "planning", "validating"}

    async def execute(
        self,
        *,
        agent_id: str,
        marker: Marker,
        environment: Any,
        llm_client: Any | None = None,
    ) -> ActionResult:
        stage = str(marker.payload.get("stage", "")).strip().lower()
        if stage == "finalize" or marker.id.endswith("::finalize"):
            return self._finalize(marker=marker, environment=environment)

        workspace = getattr(environment, "workspace", None)
        if workspace is None:
            return ActionResult(
                action_type=self.action_type,
                metadata={"failed": True, "reason": "workspace_missing"},
            )

        evaluator = TravelPlannerEvaluator(workspace=workspace)
        plan_marker = self._resolve_plan_marker(marker=marker, environment=environment)
        if plan_marker is None:
            return ActionResult(
                action_type=self.action_type,
                metadata={"failed": True, "reason": "plan_marker_missing"},
            )

        query_data = plan_marker.payload.get("query_data")
        plan = plan_marker.payload.get("plan")
        if not isinstance(query_data, dict):
            return ActionResult(
                action_type=self.action_type,
                metadata={"failed": True, "reason": "missing_query_data"},
            )
        if not isinstance(plan, list):
            return ActionResult(
                action_type=self.action_type,
                metadata={"failed": True, "reason": "missing_plan"},
            )

        evaluation = evaluator.evaluate_plan(query_data=query_data, plan=plan)
        failed_constraints = evaluator.failed_constraints(evaluation)

        updated = Marker.from_dict(marker.to_dict())
        payload = dict(updated.payload)
        payload["query_data"] = query_data
        payload["plan"] = plan
        payload["evaluation"] = {
            "delivery_rate": 1.0 if evaluation.delivered else 0.0,
            "commonsense": evaluation.commonsense,
            "hard": evaluation.hard,
            "commonsense_macro_pass": evaluation.commonsense_macro_pass,
            "hard_macro_pass": evaluation.hard_macro_pass,
            "final_pass": evaluation.final_pass,
            "estimated_cost": evaluation.estimated_cost,
            "failed_constraints": failed_constraints,
        }
        updated.payload = payload
        updated.intensity = max(
            self.intensity_floor,
            float(updated.intensity) - self.intensity_step,
        )

        if evaluation.final_pass:
            updated.state = "terminal"
            return ActionResult(
                action_type=self.action_type,
                marker_updates=[updated],
                metadata={"final_pass": True},
            )

        updated.retry_count = int(updated.retry_count) + 1
        if updated.retry_count <= self.max_retries:
            updated.state = "planning"
            replanning_marker = Marker.from_dict(plan_marker.to_dict())
            replanning_payload = dict(replanning_marker.payload)
            replanning_payload["needs_replan"] = True
            replanning_payload["validation_feedback"] = failed_constraints
            replanning_marker.payload = replanning_payload
            replanning_marker.state = "planning"
            return ActionResult(
                action_type=self.action_type,
                marker_updates=[updated, replanning_marker],
                metadata={"final_pass": False, "replan": True},
            )

        updated.state = "terminal"
        return ActionResult(
            action_type=self.action_type,
            marker_updates=[updated],
            metadata={"final_pass": False, "replan": False},
        )

    def _resolve_plan_marker(self, *, marker: Marker, environment: Any) -> Marker | None:
        depends_on = marker.payload.get("depends_on", [])
        if not isinstance(depends_on, list):
            return None
        for dependency_id in depends_on:
            candidate = environment.store.get_marker(str(dependency_id))
            if candidate is None:
                continue
            if candidate.payload.get("plan") is not None:
                return candidate
        return None

    def _finalize(self, *, marker: Marker, environment: Any) -> ActionResult:
        depends_on = marker.payload.get("depends_on", [])
        if not isinstance(depends_on, list) or not depends_on:
            return ActionResult(
                action_type=self.action_type,
                metadata={"failed": True, "reason": "missing_finalize_dependency"},
            )

        validate_marker = environment.store.get_marker(str(depends_on[0]))
        if validate_marker is None:
            return ActionResult(
                action_type=self.action_type,
                metadata={"failed": True, "reason": "validate_marker_missing"},
            )

        eval_payload = dict(validate_marker.payload.get("evaluation", {}))

        updated = Marker.from_dict(marker.to_dict())
        payload = dict(updated.payload)
        payload["query_data"] = validate_marker.payload.get("query_data")
        payload["final_plan"] = validate_marker.payload.get("plan", [])
        payload["evaluation"] = eval_payload
        payload["final_pass"] = bool(eval_payload.get("final_pass", False))
        updated.payload = payload
        updated.state = "terminal"
        updated.intensity = max(
            self.intensity_floor,
            float(updated.intensity) - self.intensity_step,
        )

        return ActionResult(action_type=self.action_type, marker_updates=[updated])
