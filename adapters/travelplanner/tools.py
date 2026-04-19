"""Domain tools for TravelPlanner adapter."""

from __future__ import annotations

import ast
import json
import logging
import re
from typing import Any

import pandas as pd
from pydantic import ValidationError

from core.marker import Marker
from core.schemas import TravelItineraryOutput
from core.tool_registry import (
    ActionResult,
    RepairRequest,
    Tool,
    ValidationResult,
    build_repair_marker_id,
)

from .evaluator import TravelPlannerEvaluator
from .workspace import QUERY_DATASET_ID


logger = logging.getLogger(__name__)


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
        return all(
            str(marker.payload.get(field, "")).strip() for field in self.required_fields
        )

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
        payload["result_key"] = str(payload.get("result_key", self.action_type)).strip() or self.action_type
        payload["results"] = records
        payload["result_count"] = len(records)
        payload["search_params"] = call_kwargs
        updated.payload = payload
        updated.state = "searching" if updated.state == "pending" else "terminal"
        if records:
            updated.intensity = max(
                self.intensity_floor,
                float(updated.intensity) - self.intensity_step,
            )

        return ActionResult(action_type=self.action_type, marker_updates=[updated])


class SearchFlightsTool(_BaseTravelSearchTool):
    action_type = "search_flights"
    workspace_method = "search_flights"
    required_fields = ("origin", "dest", "date")


class SearchGroundTransportTool(_BaseTravelSearchTool):
    action_type = "search_ground_transport"
    workspace_method = "search_ground_transport"
    required_fields = ("origin", "dest")


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
    _few_shot_examples_cache: list[dict[str, Any]] | None = None
    _few_shot_examples_loaded = False
    prompt_query_fields = (
        "query_idx",
        "query",
        "org",
        "dest",
        "city_sequence",
        "days",
        "visiting_city_number",
        "date",
        "people_number",
        "budget",
        "level",
        "local_constraint",
    )
    prompt_search_limits = {
        "search_flights": 6,
        "search_flights_outbound": 6,
        "search_flights_return": 6,
        "search_ground_transport": 4,
        "search_ground_transport_outbound": 4,
        "search_ground_transport_return": 4,
        "search_hotels": 8,
        "search_restaurants": 10,
        "search_attractions": 10,
    }
    prompt_search_fields = {
        "search_flights": (
            "Flight Number",
            "Price",
            "DepTime",
            "ArrTime",
            "ActualElapsedTime",
            "FlightDate",
            "OriginCityName",
            "DestCityName",
        ),
        "search_flights_outbound": (
            "Flight Number",
            "Price",
            "DepTime",
            "ArrTime",
            "ActualElapsedTime",
            "FlightDate",
            "OriginCityName",
            "DestCityName",
        ),
        "search_flights_return": (
            "Flight Number",
            "Price",
            "DepTime",
            "ArrTime",
            "ActualElapsedTime",
            "FlightDate",
            "OriginCityName",
            "DestCityName",
        ),
        "search_ground_transport": (
            "mode",
            "origin",
            "destination",
            "duration",
            "distance",
            "cost",
            "transportation",
        ),
        "search_ground_transport_outbound": (
            "mode",
            "origin",
            "destination",
            "duration",
            "distance",
            "cost",
            "transportation",
        ),
        "search_ground_transport_return": (
            "mode",
            "origin",
            "destination",
            "duration",
            "distance",
            "cost",
            "transportation",
        ),
        "search_hotels": (
            "NAME",
            "price",
            "room type",
            "house_rules",
            "minimum nights",
            "maximum occupancy",
            "review rate number",
            "city",
        ),
        "search_restaurants": (
            "Name",
            "Average Cost",
            "Cuisines",
            "Aggregate Rating",
            "City",
        ),
        "search_attractions": (
            "Name",
            "Address",
            "Phone",
            "Website",
            "City",
        ),
    }

    def __init__(
        self, *, config: dict[str, Any], max_planning_attempts: int = 3
    ) -> None:
        self.config = config
        self.max_planning_attempts = int(max_planning_attempts)
        markers_cfg = dict(config.get("markers", {}))
        self.intensity_step = float(markers_cfg.get("intensity_step_tool", 0.05))
        self.intensity_floor = float(markers_cfg.get("intensity_floor", 0.1))
        self.few_shot_examples = self._load_few_shot_examples()

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

        search_payload = self._collect_search_payloads(
            marker=marker, environment=environment
        )
        feedback_raw = marker.payload.get("validation_feedback", [])
        validation_feedback = (
            [str(item) for item in feedback_raw]
            if isinstance(feedback_raw, list)
            else []
        )

        consumed_tokens = 0
        cost_usd = 0.0
        planner_model = "none"
        planning_failure_reason = ""

        itinerary: list[dict[str, Any]] = []

        if llm_client is not None and (
            hasattr(llm_client, "acall") or hasattr(llm_client, "call")
        ):
            prompt = self._build_prompt(
                query_data=query_data,
                search_payload=search_payload,
                validation_feedback=validation_feedback,
            )
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
                    planner_model = str(getattr(response, "model", "unknown"))
                    consumed_tokens = int(getattr(response, "tokens_used", 0))
                    cost_usd = float(getattr(response, "cost_usd", 0.0))
                    parsed = getattr(response, "parsed", None)
                    if isinstance(parsed, TravelItineraryOutput):
                        itinerary = [day.model_dump() for day in parsed.plan]
                    else:
                        raw_content = str(getattr(response, "content", ""))
                        itinerary = self._parse_itinerary(
                            raw_content=raw_content,
                            llm_client=llm_client,
                        )
                        if raw_content.strip() and not itinerary:
                            planning_failure_reason = "schema_parse_failed"
                    itinerary = self._normalize_itinerary(
                        itinerary=itinerary,
                        query_data=query_data,
                        search_payload=search_payload,
                    )
            except Exception:  # noqa: BLE001
                itinerary = []

        planning_attempts = int(marker.payload.get("planning_attempts", 0)) + 1

        # Guard: if plan is empty and we've exhausted attempts, mark as failed
        if not itinerary and planning_attempts >= self.max_planning_attempts:
            updated = Marker.from_dict(marker.to_dict())
            payload = dict(updated.payload)
            payload["plan"] = []
            payload["planning_attempts"] = planning_attempts
            payload["needs_replan"] = False
            payload["planner_model"] = planner_model
            self._record_failure_reason(
                payload=payload,
                reason="empty_plan_after_max_attempts",
                previous_reason=planning_failure_reason,
            )
            updated.payload = payload
            updated.state = "terminal"
            updated.intensity = 0.8
            return ActionResult(
                action_type=self.action_type,
                marker_updates=[updated],
                consumed_tokens=consumed_tokens,
                cost_usd=cost_usd,
                metadata={"failed": True, "reason": "empty_plan_after_max_attempts"},
            )

        # Guard: if plan is empty, mark action as failed so idle_cycles increments
        if not itinerary:
            updated = Marker.from_dict(marker.to_dict())
            payload = dict(updated.payload)
            payload["plan"] = []
            payload["planning_attempts"] = planning_attempts
            payload["needs_replan"] = True
            payload["planner_model"] = planner_model
            payload["validation_feedback"] = validation_feedback
            self._record_failure_reason(
                payload=payload,
                reason="empty_plan_from_llm",
                previous_reason=planning_failure_reason,
            )
            updated.payload = payload
            # Keep state as planning to allow retry, but signal failure
            updated.state = "planning"
            updated.intensity = 0.8
            return ActionResult(
                action_type=self.action_type,
                marker_updates=[updated],
                consumed_tokens=consumed_tokens,
                cost_usd=cost_usd,
                metadata={"failed": True, "reason": "empty_plan_from_llm"},
            )

        updated = Marker.from_dict(marker.to_dict())
        payload = dict(updated.payload)
        payload["plan"] = itinerary
        payload["search_payload"] = search_payload
        payload["planner_model"] = planner_model
        payload["planning_attempts"] = planning_attempts
        payload["needs_replan"] = False
        payload["validation_feedback"] = validation_feedback
        payload["failure_reason"] = "ok"
        payload["last_failure_reason"] = "ok"
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

    def _record_failure_reason(
        self,
        *,
        payload: dict[str, Any],
        reason: str,
        previous_reason: str = "",
    ) -> None:
        history_raw = payload.get("failure_history", [])
        history = (
            [str(item).strip() for item in history_raw if str(item).strip()]
            if isinstance(history_raw, list)
            else []
        )
        if previous_reason and previous_reason not in history:
            history.append(previous_reason)
        if reason and reason not in history:
            history.append(reason)
        payload["failure_history"] = history[-5:]
        payload["last_failure_reason"] = previous_reason or reason
        payload["failure_reason"] = reason

    @classmethod
    def _load_few_shot_examples(cls) -> list[dict[str, Any]]:
        if cls._few_shot_examples_loaded:
            return list(cls._few_shot_examples_cache or [])

        cls._few_shot_examples_loaded = True
        cls._few_shot_examples_cache = []

        try:
            from datasets import load_dataset

            dataset = load_dataset(QUERY_DATASET_ID, "train")
            cls._few_shot_examples_cache = cls._select_few_shot_examples(
                dataset["train"]
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Unable to load TravelPlanner train few-shot examples: %s",
                exc,
            )
            cls._few_shot_examples_cache = []

        return list(cls._few_shot_examples_cache)

    @classmethod
    def _select_few_shot_examples(cls, rows: Any) -> list[dict[str, Any]]:
        examples: list[dict[str, Any]] = []
        predicates = (
            lambda visiting_count: visiting_count == 1,
            lambda visiting_count: visiting_count >= 2,
        )

        for predicate in predicates:
            selected: dict[str, Any] | None = None
            for raw_row in rows:
                example = cls._extract_few_shot_example(raw_row)
                if example is None:
                    continue
                visiting_count = int(
                    example["query"].get("visiting_city_number", 0) or 0
                )
                if predicate(visiting_count):
                    selected = example
                    break
            if selected is not None:
                examples.append(selected)

        return examples

    @classmethod
    def _extract_few_shot_example(
        cls, raw_row: Any
    ) -> dict[str, Any] | None:
        if not isinstance(raw_row, dict):
            return None

        annotated_plan = cls._safe_literal_value(
            raw_row.get("annotated_plan"),
            default=[],
        )
        if (
            not isinstance(annotated_plan, list)
            or len(annotated_plan) < 2
            or not isinstance(annotated_plan[1], list)
        ):
            return None

        query_payload = cls._compact_few_shot_query(raw_row)
        plan_rows = cls._compact_few_shot_plan_rows(annotated_plan[1])
        if not plan_rows:
            return None

        try:
            parsed = TravelItineraryOutput.model_validate({"plan": plan_rows})
        except ValidationError:
            return None

        return {
            "query": query_payload,
            "plan": [day.model_dump() for day in parsed.plan],
        }

    @classmethod
    def _compact_few_shot_query(cls, raw_row: dict[str, Any]) -> dict[str, Any]:
        compact: dict[str, Any] = {}
        for field in cls.prompt_query_fields:
            if field not in raw_row:
                continue
            value = raw_row[field]
            if field == "date":
                compact[field] = cls._safe_literal_value(value, default=[])
                continue
            if field == "local_constraint":
                compact[field] = cls._safe_literal_value(value, default={})
                continue
            compact[field] = value
        return compact

    @classmethod
    def _compact_few_shot_plan_rows(
        cls, raw_plan_rows: list[Any]
    ) -> list[dict[str, Any]]:
        fields = (
            "current_city",
            "transportation",
            "breakfast",
            "attraction",
            "lunch",
            "dinner",
            "accommodation",
        )
        compact_rows: list[dict[str, Any]] = []
        for raw_row in raw_plan_rows:
            if not isinstance(raw_row, dict):
                continue
            if not any(str(raw_row.get(field, "")).strip() for field in fields):
                continue
            compact_rows.append(
                {
                    field: cls._stringify_few_shot_value(raw_row.get(field))
                    for field in fields
                }
            )
        return compact_rows

    @staticmethod
    def _safe_literal_value(value: Any, *, default: Any) -> Any:
        if isinstance(value, (dict, list, tuple, int, float, bool)):
            return value
        if value is None:
            return default
        text = str(value).strip()
        if not text:
            return default
        try:
            return ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return default

    @staticmethod
    def _stringify_few_shot_value(value: Any) -> str:
        text = str(value).strip() if value is not None else ""
        return text or "-"

    def _build_prompt(
        self,
        *,
        query_data: dict[str, Any],
        search_payload: dict[str, Any],
        validation_feedback: list[str],
    ) -> str:
        compact_query = self._compact_query_data(query_data)
        compact_search_payload = self._compact_search_payload(
            search_payload,
            query_data=query_data,
        )
        routing_context = self._build_routing_context(
            query_data=compact_query,
            search_payload=compact_search_payload,
        )
        city_sequence = self._resolve_city_sequence(query_data)
        feedback_block = ""
        if validation_feedback:
            feedback_block = (
                "Previous validation failures to fix exactly:\n"
                f"{json.dumps(validation_feedback, ensure_ascii=True)}\n"
            )
        city_sequence_block = ""
        if city_sequence:
            city_sequence_block = (
                "- Visit these cities in order: "
                + " -> ".join(city_sequence)
                + ".\n"
            )
        multi_city_block = ""
        if len(city_sequence) > 1:
            multi_city_block = (
                "IMPORTANT for multi-city trips: You MUST include one day per city transition "
                "(transportation day)\n"
                "and at least one stay day per intermediate city.\n"
            )

        routing_block = ""
        if routing_context:
            routing_block = (
                "RoutingData:\n"
                f"{json.dumps(routing_context, ensure_ascii=True)}\n"
            )
        # Few-shot examples loaded from osunlp/TravelPlanner split="train" ONLY.
        # Never use split="validation" here — would contaminate the benchmark.
        few_shot_block = ""
        if self.few_shot_examples:
            rendered_examples = []
            for index, example in enumerate(self.few_shot_examples, start=1):
                rendered_examples.append(
                    f"Example {index}: "
                    f"{json.dumps(example['query'], ensure_ascii=True)}"
                    " -> "
                    f"{json.dumps({'plan': example['plan']}, ensure_ascii=True)}"
                )
            few_shot_block = (
                "Examples (from training split only):\n"
                + "\n".join(rendered_examples)
                + "\n"
            )

        return (
            "You are a travel planning assistant. Build a day-by-day itinerary in strict JSON.\n"
            "Return only JSON matching this schema:\n"
            '{"plan":[{"current_city":"...","transportation":"...","breakfast":"...",'
            '"attraction":"...","lunch":"...","dinner":"...","accommodation":"..."}]}\n'
            "Hard requirements:\n"
            f"- Return exactly {int(query_data.get('days', 0) or 0)} day objects in the plan.\n"
            f"{city_sequence_block}"
            f"{multi_city_block}"
            "- Keep city consistency with current_city and transportation.\n"
            "- Use '<name>, <city>' format for meals, attractions, and accommodation.\n"
            "- Never repeat the same restaurant across breakfast/lunch/dinner.\n"
            "- Never repeat the same attraction across days.\n"
            "- Put accommodation for each non-final night.\n"
            "- For transport, use either consistent flights or consistent non-flight mode.\n"
            "- Accommodation must satisfy minimum nights, maximum occupancy, and local room constraints.\n"
            "- The itinerary should form a closed circle within the allotted day count when origin and destination differ.\n"
            "Canonical formatting rules:\n"
            "- A transfer day must use current_city exactly 'from <origin> to <destination>'.\n"
            "- A stay day must use current_city as a single city name and transportation '-'.\n"
            "- If you choose a flight, copy transportation exactly as 'Flight Number: <id>, from <origin> to <destination>'.\n"
            "- If you choose self-driving or taxi, copy the full transportation string from RoutingData.\n"
            "- Attractions may be '-' or one or more '<name>, <city>' values separated by '; '.\n"
            "- Meals or attractions that are not scheduled should be '-'.\n"
            f"{feedback_block}"
            f"{few_shot_block}"
            "Use only plausible values from provided search data.\n"
            f"Query: {json.dumps(compact_query, ensure_ascii=True)}\n"
            f"{routing_block}"
            f"SearchData: {json.dumps(compact_search_payload, ensure_ascii=True)}"
        )

    def _parse_itinerary(
        self, *, raw_content: str, llm_client: Any | None
    ) -> list[dict[str, Any]]:
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

    def _collect_search_payloads(
        self, *, marker: Marker, environment: Any
    ) -> dict[str, Any]:
        results: dict[str, Any] = {}
        depends_on = marker.payload.get("depends_on", [])
        if not isinstance(depends_on, list):
            return results

        for dep_id in depends_on:
            dependency = environment.store.get_marker(str(dep_id))
            if dependency is None:
                continue
            dep_payload = dict(dependency.payload)
            search_type = str(
                dep_payload.get("result_key")
                or dep_payload.get("search_type")
                or dependency.id
            ).strip()
            records = dep_payload.get("results", [])
            if isinstance(records, list):
                results[search_type] = records

        workspace = getattr(environment, "workspace", None)
        query_data = marker.payload.get("query_data")
        if isinstance(query_data, dict) and workspace is not None:
            self._inject_default_search_payloads(
                results=results,
                query_data=query_data,
                workspace=workspace,
            )

        return self._compact_search_payload(results, query_data=query_data if isinstance(query_data, dict) else None)

    def _inject_default_search_payloads(
        self,
        *,
        results: dict[str, Any],
        query_data: dict[str, Any],
        workspace: Any,
    ) -> None:
        fallback_specs: list[tuple[str, str, dict[str, str]]] = []
        for city_spec in self._build_city_search_specs(query_data):
            city = city_spec["city"]
            fallback_specs.extend(
                [
                    (
                        city_spec["restaurant_key"],
                        "search_restaurants",
                        {"city": city},
                    ),
                    (
                        city_spec["hotel_key"],
                        "search_hotels",
                        {"city": city},
                    ),
                    (
                        city_spec["attraction_key"],
                        "search_attractions",
                        {"city": city},
                    ),
                ]
            )

        for route_spec in self._build_route_specs(query_data):
            fallback_specs.extend(
                [
                    (
                        route_spec["flight_key"],
                        "search_flights",
                        {
                            "origin": route_spec["origin"],
                            "dest": route_spec["dest"],
                            "date": route_spec["date"],
                        },
                    ),
                    (
                        route_spec["ground_key"],
                        "search_ground_transport",
                        {
                            "origin": route_spec["origin"],
                            "dest": route_spec["dest"],
                        },
                    ),
                ]
            )

        for result_key, workspace_method, kwargs in fallback_specs:
            if result_key in results:
                continue
            if not all(str(value).strip() for value in kwargs.values()):
                continue
            if not hasattr(workspace, workspace_method):
                continue
            try:
                frame = getattr(workspace, workspace_method)(**kwargs)
            except Exception:  # noqa: BLE001
                continue
            if isinstance(frame, pd.DataFrame):
                results[result_key] = frame.to_dict(orient="records")

    def _normalize_itinerary(
        self,
        *,
        itinerary: list[dict[str, Any]],
        query_data: dict[str, Any],
        search_payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if not itinerary:
            return []

        route_options = self._build_route_option_catalog(search_payload)
        restaurant_candidates = self._build_named_candidates(
            search_payload=search_payload,
            keys=("search_restaurants",),
            name_field="Name",
            city_field="City",
        )
        attraction_candidates = self._build_named_candidates(
            search_payload=search_payload,
            keys=("search_attractions",),
            name_field="Name",
            city_field="City",
        )
        hotel_candidates = self._build_named_candidates(
            search_payload=search_payload,
            keys=("search_hotels",),
            name_field="NAME",
            city_field="city",
        )
        city_sequence = self._resolve_city_sequence(query_data)
        default_city = (
            city_sequence[0]
            if city_sequence
            else str(query_data.get("dest", "")).strip()
        )

        normalized_days: list[dict[str, Any]] = []
        for raw_day in itinerary:
            if not isinstance(raw_day, dict):
                continue

            day = {
                "current_city": self._string_or_dash(raw_day.get("current_city")),
                "transportation": self._string_or_dash(raw_day.get("transportation")),
                "breakfast": self._normalize_named_field(
                    raw_value=raw_day.get("breakfast"),
                    candidates=restaurant_candidates,
                ),
                "attraction": self._normalize_attraction_field(
                    raw_value=raw_day.get("attraction"),
                    candidates=attraction_candidates,
                ),
                "lunch": self._normalize_named_field(
                    raw_value=raw_day.get("lunch"),
                    candidates=restaurant_candidates,
                ),
                "dinner": self._normalize_named_field(
                    raw_value=raw_day.get("dinner"),
                    candidates=restaurant_candidates,
                ),
                "accommodation": self._normalize_named_field(
                    raw_value=raw_day.get("accommodation"),
                    candidates=hotel_candidates,
                ),
            }

            day["transportation"] = self._normalize_transportation_field(
                raw_value=day["transportation"],
                current_city=day["current_city"],
                route_options=route_options,
            )
            day["current_city"] = self._normalize_current_city_field(
                raw_value=day["current_city"],
                transportation=day["transportation"],
                default_city=default_city,
            )
            normalized_days.append(day)

        return normalized_days

    def _compact_query_data(self, query_data: dict[str, Any]) -> dict[str, Any]:
        compact: dict[str, Any] = {}
        for field in self.prompt_query_fields:
            if field in query_data:
                compact[field] = query_data[field]
        return compact

    def _compact_search_payload(
        self,
        search_payload: dict[str, Any],
        *,
        query_data: dict[str, Any] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        compact: dict[str, list[dict[str, Any]]] = {}
        for search_type, raw_records in search_payload.items():
            if not isinstance(raw_records, list):
                continue
            base_key = self._extract_base_search_key(search_type)
            if base_key is None:
                continue
            fields = self.prompt_search_fields.get(base_key)
            if fields is None:
                continue
            limit = int(self.prompt_search_limits.get(base_key, 8))
            compact_records: list[dict[str, Any]] = []
            source_records = raw_records
            if base_key == "search_hotels":
                source_records = self._filter_hotel_candidates(
                    raw_records=raw_records,
                    query_data=query_data,
                )
            for raw_record in source_records[:limit]:
                if not isinstance(raw_record, dict):
                    continue
                compact_record = {
                    field: raw_record.get(field)
                    for field in fields
                    if field in raw_record
                }
                if compact_record:
                    compact_records.append(compact_record)
            if compact_records:
                compact[search_type] = compact_records
        return compact

    def _filter_hotel_candidates(
        self,
        *,
        raw_records: list[dict[str, Any]],
        query_data: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        if not isinstance(query_data, dict):
            return raw_records

        try:
            trip_days = int(query_data.get("days", 0))
        except Exception:  # noqa: BLE001
            trip_days = 0
        city_count = max(len(self._resolve_city_sequence(query_data)), 1)
        try:
            people_number = int(query_data.get("people_number", 1))
        except Exception:  # noqa: BLE001
            people_number = 1

        stay_nights = max(1, (max(trip_days - 1, 1) + city_count - 1) // city_count)
        local_constraint = query_data.get("local_constraint")
        constraints = local_constraint if isinstance(local_constraint, dict) else {}
        room_constraint = str(constraints.get("room type") or "").strip().casefold()
        house_rule = str(constraints.get("house rule") or "").strip().casefold()

        filtered: list[dict[str, Any]] = []
        for record in raw_records:
            if not isinstance(record, dict):
                continue
            minimum_nights = self._coerce_int(record.get("minimum nights"))
            maximum_occupancy = self._coerce_int(record.get("maximum occupancy"))
            room_type = str(record.get("room type", "")).strip().casefold()
            house_rules = str(record.get("house_rules", "")).strip()

            if minimum_nights is not None and minimum_nights > stay_nights:
                continue
            if maximum_occupancy is not None and maximum_occupancy < people_number:
                continue
            if room_constraint:
                if room_constraint == "not shared room" and room_type == "shared room":
                    continue
                room_map = {
                    "shared room": "shared room",
                    "private room": "private room",
                    "entire room": "entire home/apt",
                }
                required_room = room_map.get(room_constraint)
                if required_room and room_type != required_room:
                    continue
            if house_rule and self._violates_house_rule(
                house_rule=house_rule,
                house_rules=house_rules,
            ):
                continue
            filtered.append(record)

        return filtered or raw_records

    def _build_routing_context(
        self,
        *,
        query_data: dict[str, Any],
        search_payload: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        routing_context: list[dict[str, Any]] = []
        for route_spec in self._build_route_specs(query_data):
            flights = search_payload.get(
                route_spec["flight_key"],
                search_payload.get("search_flights", []),
            )
            ground = search_payload.get(
                route_spec["ground_key"],
                search_payload.get("search_ground_transport", []),
            )
            transport_options = [
                self._canonical_flight_option(record)
                for record in flights
                if isinstance(record, dict)
            ]
            transport_options.extend(
                str(record.get("transportation", "")).strip()
                for record in ground
                if isinstance(record, dict) and str(record.get("transportation", "")).strip()
            )
            if not transport_options:
                continue
            routing_context.append(
                {
                    "label": route_spec["label"],
                    "current_city": f"from {route_spec['origin']} to {route_spec['dest']}",
                    "date": route_spec["date"],
                    "transportation_options": transport_options,
                    "stay_day_transportation": "-",
                }
            )

        return routing_context

    def _build_route_option_catalog(
        self,
        search_payload: dict[str, Any],
    ) -> dict[str, dict[Any, str]]:
        catalog: dict[str, dict[Any, str]] = {
            "flight_numbers": {},
            "ground_routes": {},
        }

        for key, records in search_payload.items():
            if not self._search_key_matches(key, "search_flights"):
                continue
            for record in records:
                if not isinstance(record, dict):
                    continue
                flight_number = str(record.get("Flight Number", "")).strip()
                if not flight_number:
                    continue
                catalog["flight_numbers"][flight_number.casefold()] = self._canonical_flight_option(record)

        for key, records in search_payload.items():
            if not self._search_key_matches(key, "search_ground_transport"):
                continue
            for record in records:
                if not isinstance(record, dict):
                    continue
                mode = str(record.get("mode", "")).strip().casefold()
                origin = str(record.get("origin", "")).strip()
                destination = str(record.get("destination", "")).strip()
                transportation = str(record.get("transportation", "")).strip()
                if not mode or not origin or not destination or not transportation:
                    continue
                catalog["ground_routes"][
                    (mode, origin.casefold(), destination.casefold())
                ] = transportation

        return catalog

    def _build_named_candidates(
        self,
        *,
        search_payload: dict[str, Any],
        keys: tuple[str, ...],
        name_field: str,
        city_field: str,
    ) -> list[dict[str, str]]:
        candidates: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for key, records in search_payload.items():
            if not any(self._search_key_matches(key, prefix) for prefix in keys):
                continue
            for record in records:
                if not isinstance(record, dict):
                    continue
                name = str(record.get(name_field, "")).strip()
                city = str(record.get(city_field, "")).strip()
                if not name or not city:
                    continue
                dedupe_key = (name.casefold(), city.casefold())
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                candidates.append(
                    {
                        "name": name,
                        "city": city,
                        "canonical": f"{name}, {city}",
                    }
                )
        return candidates

    def _normalize_named_field(
        self,
        *,
        raw_value: Any,
        candidates: list[dict[str, str]],
    ) -> str:
        text = self._string_or_dash(raw_value)
        if text == "-":
            return "-"

        parsed_name, parsed_city = self._split_name_city(text)
        for candidate in candidates:
            name_match = parsed_name and parsed_name.casefold() == candidate["name"].casefold()
            text_match = candidate["name"].casefold() in text.casefold()
            if not name_match and not text_match:
                continue
            if parsed_city and parsed_city.casefold() != candidate["city"].casefold():
                continue
            return candidate["canonical"]

        return text

    def _normalize_attraction_field(
        self,
        *,
        raw_value: Any,
        candidates: list[dict[str, str]],
    ) -> str:
        text = self._string_or_dash(raw_value)
        if text == "-":
            return "-"

        parts = [part.strip() for part in text.split(";") if part.strip()]
        if not parts:
            parts = [text]
        normalized_parts = [
            self._normalize_named_field(raw_value=part, candidates=candidates)
            for part in parts
        ]
        normalized_parts = [part for part in normalized_parts if part]
        if not normalized_parts:
            return "-"
        if len(normalized_parts) == 1:
            return normalized_parts[0]
        return "; ".join(normalized_parts)

    def _normalize_transportation_field(
        self,
        *,
        raw_value: Any,
        current_city: str,
        route_options: dict[str, dict[Any, str]],
    ) -> str:
        text = self._string_or_dash(raw_value)
        if text == "-":
            return "-"

        lowered = text.casefold()
        if lowered in {
            "local transport",
            "local transportation",
            "public transport",
            "none",
            "n/a",
        }:
            return "-"

        flight_number = self._extract_flight_number(text)
        if flight_number is not None:
            canonical = route_options["flight_numbers"].get(flight_number.casefold())
            if canonical:
                return canonical

        route = self._extract_route(text) or self._extract_route(current_city)
        if route is not None:
            route_key = (route[0].casefold(), route[1].casefold())
            if "self-driving" in lowered:
                canonical = route_options["ground_routes"].get(
                    ("self-driving", route_key[0], route_key[1])
                )
                if canonical:
                    return canonical
            if "taxi" in lowered:
                canonical = route_options["ground_routes"].get(
                    ("taxi", route_key[0], route_key[1])
                )
                if canonical:
                    return canonical

        return text

    def _normalize_current_city_field(
        self,
        *,
        raw_value: Any,
        transportation: str,
        default_city: str,
    ) -> str:
        route = self._extract_route(transportation)
        if route is not None:
            return f"from {route[0]} to {route[1]}"

        text = self._string_or_dash(raw_value)
        if text == "-" and default_city:
            return default_city
        return text

    def _canonical_flight_option(self, record: dict[str, Any]) -> str:
        flight_number = str(record.get("Flight Number", "")).strip()
        origin = str(record.get("OriginCityName", "")).strip()
        destination = str(record.get("DestCityName", "")).strip()
        return f"Flight Number: {flight_number}, from {origin} to {destination}"

    def _extract_flight_number(self, text: str) -> str | None:
        match = re.search(r"\b([A-Z]\d{4,})\b", str(text).upper())
        if match is None:
            return None
        return match.group(1)

    def _extract_route(self, text: str) -> tuple[str, str] | None:
        match = re.search(r"from\s+(.+?)\s+to\s+([^,]+)(?=[,\s]|$)", str(text), flags=re.IGNORECASE)
        if match is None:
            return None
        return match.group(1).strip(), match.group(2).strip()

    def _split_name_city(self, text: str) -> tuple[str, str]:
        parts = [part.strip() for part in str(text).rsplit(",", 1)]
        if len(parts) == 2:
            return parts[0], parts[1]
        return str(text).strip(), ""

    def _string_or_dash(self, value: Any) -> str:
        text = str(value).strip() if value is not None else ""
        if not text:
            return "-"
        return text

    def _coerce_int(self, value: Any) -> int | None:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def _violates_house_rule(self, *, house_rule: str, house_rules: str) -> bool:
        blocked_rules = {
            "smoking": "No smoking",
            "parties": "No parties",
            "children under 10": "No children under 10",
            "visitors": "No visitors",
            "pets": "No pets",
        }
        blocked_text = blocked_rules.get(house_rule)
        if not blocked_text:
            return False
        return blocked_text in house_rules

    def _resolve_city_sequence(self, query_data: dict[str, Any]) -> list[str]:
        raw = query_data.get("city_sequence")
        if isinstance(raw, list):
            sequence = [str(city).strip() for city in raw if str(city).strip()]
            if sequence:
                return sequence
        destination = str(query_data.get("dest", "")).strip()
        return [destination] if destination else []

    def _resolve_leg_dates(self, query_data: dict[str, Any]) -> list[str]:
        raw = query_data.get("leg_dates")
        if isinstance(raw, list):
            normalized = [str(value).strip() for value in raw if str(value).strip()]
            if normalized:
                return normalized

        dates_raw = query_data.get("date", [])
        dates = [str(value).strip() for value in dates_raw] if isinstance(dates_raw, list) else []
        city_count = len(self._resolve_city_sequence(query_data))
        leg_count = max(city_count + 1, 2)
        if not dates:
            return [""] * leg_count
        return [
            dates[min(index * 2, len(dates) - 1)]
            for index in range(leg_count)
        ]

    def _build_city_search_specs(self, query_data: dict[str, Any]) -> list[dict[str, str]]:
        city_sequence = self._resolve_city_sequence(query_data)
        multi_city = len(city_sequence) > 1
        specs: list[dict[str, str]] = []
        for city in city_sequence:
            slug = self._slugify_key(city)
            if multi_city:
                hotel_key = f"search_hotels_{slug}"
                restaurant_key = f"search_restaurants_{slug}"
                attraction_key = f"search_attractions_{slug}"
            else:
                hotel_key = "search_hotels"
                restaurant_key = "search_restaurants"
                attraction_key = "search_attractions"
            specs.append(
                {
                    "city": city,
                    "hotel_key": hotel_key,
                    "restaurant_key": restaurant_key,
                    "attraction_key": attraction_key,
                }
            )
        return specs

    def _build_route_specs(self, query_data: dict[str, Any]) -> list[dict[str, str]]:
        origin = str(query_data.get("org", "")).strip()
        city_sequence = self._resolve_city_sequence(query_data)
        leg_dates = self._resolve_leg_dates(query_data)
        route_cities = [origin, *city_sequence, origin]
        specs: list[dict[str, str]] = []
        for leg_index in range(len(route_cities) - 1):
            if leg_index == 0:
                label = "outbound"
                flight_key = "search_flights_outbound"
                ground_key = "search_ground_transport_outbound"
            elif leg_index == len(route_cities) - 2:
                label = "return"
                flight_key = "search_flights_return"
                ground_key = "search_ground_transport_return"
            else:
                label = f"leg_{leg_index}"
                flight_key = f"search_flights_leg_{leg_index}"
                ground_key = f"search_ground_transport_leg_{leg_index}"
            specs.append(
                {
                    "label": label,
                    "origin": route_cities[leg_index],
                    "dest": route_cities[leg_index + 1],
                    "date": leg_dates[min(leg_index, len(leg_dates) - 1)] if leg_dates else "",
                    "flight_key": flight_key,
                    "ground_key": ground_key,
                }
            )
        return specs

    def _extract_base_search_key(self, search_type: str) -> str | None:
        for base_key in self.prompt_search_fields:
            if self._search_key_matches(search_type, base_key):
                return base_key
        return None

    def _search_key_matches(self, search_type: str, prefix: str) -> bool:
        return search_type == prefix or search_type.startswith(f"{prefix}_")

    def _slugify_key(self, value: str) -> str:
        text = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower())
        return text.strip("_") or "city"


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
        failed_feedback = evaluator.failure_feedback(evaluation)

        updated = Marker.from_dict(marker.to_dict())
        payload = dict(updated.payload)
        payload["query_data"] = query_data
        payload["plan"] = plan
        payload["evaluation"] = {
            "delivery_rate": 1.0 if evaluation.delivered else 0.0,
            "commonsense": evaluation.commonsense,
            "commonsense_messages": evaluation.commonsense_messages,
            "hard": evaluation.hard,
            "hard_messages": evaluation.hard_messages,
            "commonsense_macro_pass": evaluation.commonsense_macro_pass,
            "hard_macro_pass": evaluation.hard_macro_pass,
            "final_pass": evaluation.final_pass,
            "estimated_cost": evaluation.estimated_cost,
            "failed_constraints": failed_constraints,
            "failed_feedback": failed_feedback,
        }
        updated.payload = payload
        updated.intensity = max(
            self.intensity_floor,
            float(updated.intensity) - self.intensity_step,
        )

        if evaluation.final_pass:
            payload["failure_reason"] = "ok"
            updated.state = "terminal"
            return ActionResult(
                action_type=self.action_type,
                marker_updates=[updated],
                metadata={"final_pass": True},
            )

        if failed_constraints:
            updated.intensity = 0.9
            updated.inhibition = 0.0

        shaped_plan: Marker | None = None
        if not evaluation.commonsense_macro_pass:
            shaped_plan = Marker.from_dict(plan_marker.to_dict())
            shaped_plan.inhibition = min(1.0, float(shaped_plan.inhibition) + 0.3)

        updated.retry_count = int(updated.retry_count) + 1
        if updated.retry_count <= self.max_retries:
            payload["failure_reason"] = "validation_failed"
            updated.state = "planning"
            repair_feedback = failed_feedback or failed_constraints
            if self._targeted_repair_enabled():
                repair_marker_id = build_repair_marker_id(
                    source_marker_id=marker.id,
                    target_marker_id=plan_marker.id,
                    attempt=updated.retry_count,
                )
                payload["depends_on"] = [repair_marker_id, plan_marker.id]
                payload["repair_marker_id"] = repair_marker_id
                payload["repair_feedback"] = list(repair_feedback)
                updated.payload = payload
                marker_updates = [updated]
                if shaped_plan is not None:
                    marker_updates.append(shaped_plan)
                return ActionResult(
                    action_type=self.action_type,
                    marker_updates=marker_updates,
                    metadata={"final_pass": False, "replan": True},
                    validation=ValidationResult(
                        status="failed",
                        source_marker_id=marker.id,
                        targets=[plan_marker.id],
                        feedback=list(repair_feedback),
                        repair=RepairRequest(
                            target_marker_id=plan_marker.id,
                            attempt=updated.retry_count,
                            max_attempts=self.max_retries,
                            eligible_actions=list(
                                plan_marker.payload.get("eligible_actions", [])
                            ),
                        ),
                    ),
                )

            replanning_marker = (
                shaped_plan
                if shaped_plan is not None
                else Marker.from_dict(plan_marker.to_dict())
            )
            replanning_payload = dict(replanning_marker.payload)
            replanning_payload["needs_replan"] = True
            replanning_payload["validation_feedback"] = repair_feedback
            replanning_marker.payload = replanning_payload
            replanning_marker.state = "planning"
            updated.payload = payload
            return ActionResult(
                action_type=self.action_type,
                marker_updates=[updated, replanning_marker],
                metadata={"final_pass": False, "replan": True},
            )

        payload["failure_reason"] = "validator_replan_exhausted"
        updated.state = "terminal"
        marker_updates = [updated]
        if shaped_plan is not None:
            marker_updates.append(shaped_plan)
        return ActionResult(
            action_type=self.action_type,
            marker_updates=marker_updates,
            metadata={"final_pass": False, "replan": False},
        )

    def _resolve_plan_marker(
        self, *, marker: Marker, environment: Any
    ) -> Marker | None:
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
        payload["failure_reason"] = str(validate_marker.payload.get("failure_reason", "ok"))
        updated.payload = payload
        updated.state = "terminal"
        updated.intensity = max(
            self.intensity_floor,
            float(updated.intensity) - self.intensity_step,
        )

        return ActionResult(action_type=self.action_type, marker_updates=[updated])

    def _targeted_repair_enabled(self) -> bool:
        orchestrator_cfg = dict(self.config.get("orchestrator", {}))
        targeted_repair_cfg = dict(orchestrator_cfg.get("targeted_repair", {}))
        return bool(targeted_repair_cfg.get("enabled", False))
