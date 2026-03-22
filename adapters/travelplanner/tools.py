"""Domain tools for TravelPlanner adapter."""

from __future__ import annotations

import json
import re
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
    prompt_query_fields = (
        "query_idx",
        "query",
        "org",
        "dest",
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
                    parsed = getattr(response, "parsed", None)
                    if isinstance(parsed, TravelItineraryOutput):
                        itinerary = [day.model_dump() for day in parsed.plan]
                    else:
                        itinerary = self._parse_itinerary(
                            raw_content=str(getattr(response, "content", "")),
                            llm_client=llm_client,
                        )
                    itinerary = self._normalize_itinerary(
                        itinerary=itinerary,
                        query_data=query_data,
                        search_payload=search_payload,
                    )
                    consumed_tokens = int(getattr(response, "tokens_used", 0))
                    cost_usd = float(getattr(response, "cost_usd", 0.0))
                    planner_model = str(getattr(response, "model", "unknown"))
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
            updated.payload = payload
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
            updated.payload = payload
            # Keep state as planning to allow retry, but signal failure
            updated.state = "planning"
            updated.intensity = max(
                self.intensity_floor,
                float(updated.intensity) - self.intensity_step,
            )
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
        feedback_block = ""
        if validation_feedback:
            feedback_block = (
                "Previous validation failures to fix exactly:\n"
                f"{json.dumps(validation_feedback, ensure_ascii=True)}\n"
            )

        routing_block = ""
        if routing_context:
            routing_block = (
                "RoutingData:\n"
                f"{json.dumps(routing_context, ensure_ascii=True)}\n"
            )

        return (
            "You are a travel planning assistant. Build a day-by-day itinerary in strict JSON.\n"
            "Return only JSON matching this schema:\n"
            '{"plan":[{"current_city":"...","transportation":"...","breakfast":"...",'
            '"attraction":"...","lunch":"...","dinner":"...","accommodation":"..."}]}\n'
            "Hard requirements:\n"
            f"- Return exactly {int(query_data.get('days', 0) or 0)} day objects in the plan.\n"
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
        city = str(query_data.get("dest", "")).strip()
        origin = str(query_data.get("org", "")).strip()
        dates = query_data.get("date", [])
        outbound_date = str(dates[0]) if isinstance(dates, list) and dates else ""
        return_date = str(dates[-1]) if isinstance(dates, list) and dates else outbound_date

        fallback_specs = (
            ("search_restaurants", "search_restaurants", {"city": city}),
            ("search_hotels", "search_hotels", {"city": city}),
            ("search_attractions", "search_attractions", {"city": city}),
            (
                "search_flights_outbound",
                "search_flights",
                {"origin": origin, "dest": city, "date": outbound_date},
            ),
            (
                "search_flights_return",
                "search_flights",
                {"origin": city, "dest": origin, "date": return_date},
            ),
            (
                "search_ground_transport_outbound",
                "search_ground_transport",
                {"origin": origin, "dest": city},
            ),
            (
                "search_ground_transport_return",
                "search_ground_transport",
                {"origin": city, "dest": origin},
            ),
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
                default_city=str(query_data.get("dest", "")).strip(),
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
            fields = self.prompt_search_fields.get(search_type)
            if fields is None:
                continue
            limit = int(self.prompt_search_limits.get(search_type, 8))
            compact_records: list[dict[str, Any]] = []
            source_records = raw_records
            if search_type == "search_hotels":
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
        try:
            people_number = int(query_data.get("people_number", 1))
        except Exception:  # noqa: BLE001
            people_number = 1

        stay_nights = max(trip_days - 1, 1)
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
        origin = str(query_data.get("org", "")).strip()
        destination = str(query_data.get("dest", "")).strip()
        dates = query_data.get("date", [])
        outbound_date = str(dates[0]) if isinstance(dates, list) and dates else ""
        return_date = str(dates[-1]) if isinstance(dates, list) and dates else outbound_date

        route_specs = [
            (
                "outbound",
                origin,
                destination,
                outbound_date,
                search_payload.get("search_flights_outbound", search_payload.get("search_flights", [])),
                search_payload.get("search_ground_transport_outbound", search_payload.get("search_ground_transport", [])),
            ),
            (
                "return",
                destination,
                origin,
                return_date,
                search_payload.get("search_flights_return", []),
                search_payload.get("search_ground_transport_return", []),
            ),
        ]

        routing_context: list[dict[str, Any]] = []
        for label, route_origin, route_dest, date_value, flights, ground in route_specs:
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
                    "label": label,
                    "current_city": f"from {route_origin} to {route_dest}",
                    "date": date_value,
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

        flight_keys = (
            "search_flights",
            "search_flights_outbound",
            "search_flights_return",
        )
        for key in flight_keys:
            for record in search_payload.get(key, []):
                if not isinstance(record, dict):
                    continue
                flight_number = str(record.get("Flight Number", "")).strip()
                if not flight_number:
                    continue
                catalog["flight_numbers"][flight_number.casefold()] = self._canonical_flight_option(record)

        ground_keys = (
            "search_ground_transport",
            "search_ground_transport_outbound",
            "search_ground_transport_return",
        )
        for key in ground_keys:
            for record in search_payload.get(key, []):
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
        for key in keys:
            for record in search_payload.get(key, []):
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
            replanning_payload["validation_feedback"] = failed_feedback or failed_constraints
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
        updated.payload = payload
        updated.state = "terminal"
        updated.intensity = max(
            self.intensity_floor,
            float(updated.intensity) - self.intensity_step,
        )

        return ActionResult(action_type=self.action_type, marker_updates=[updated])
