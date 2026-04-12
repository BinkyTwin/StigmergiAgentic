"""TravelPlanner domain adapter for Sprint 6 V3."""

from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from adapters.base import DomainAdapter, Objective, Workspace
from core.marker import Marker, StateMachine, utc_now_iso
from core.tool_registry import ToolRegistry
from tools.decompose import DecomposeTool
from tools.think import ThinkTool

from .evaluator import TravelPlannerEvaluator
from .tools import (
    PlanDayTool,
    SearchAttractionsTool,
    SearchFlightsTool,
    SearchGroundTransportTool,
    SearchHotelsTool,
    SearchRestaurantsTool,
    ValidateConstraintsTool,
)
from .workspace import TravelPlannerWorkspace


class TravelPlannerAdapter(DomainAdapter):
    """Domain adapter implementing TravelPlanner workflow on top of V3 runtime."""

    def __init__(self, *, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self._workspace: TravelPlannerWorkspace | None = None

    def create_workspace(self, config: dict[str, Any]) -> Workspace:
        domain_cfg = dict(config.get("travelplanner", {}))
        data_dir = domain_cfg.get("database_path", "data/travelplanner/database")
        split = str(domain_cfg.get("dataset_split", "validation"))
        query_rows = domain_cfg.get("query_rows")
        if not isinstance(query_rows, list):
            query_rows = None
        self._workspace = TravelPlannerWorkspace(
            database_root=data_dir,
            dataset_split=split,
            query_rows=query_rows,
        )
        return self._workspace

    def create_objective(
        self,
        user_input: dict[str, Any],
        config: dict[str, Any],
    ) -> Objective:
        if self._workspace is None:
            self.create_workspace(config)
        assert self._workspace is not None

        requested_idx = self._resolve_query_idx(user_input)
        query_data = self._workspace.get_query(requested_idx)

        description = str(query_data.get("query", "")).strip()
        if not description:
            raise ValueError("TravelPlanner query cannot be empty")

        return Objective(
            objective_id=f"travelplanner::{uuid4()}",
            description=description,
            payload={
                "query_idx": int(query_data["query_idx"]),
                "query_data": query_data,
                "org": query_data.get("org"),
                "dest": query_data.get("dest"),
                "city_sequence": query_data.get("city_sequence", []),
                "days": query_data.get("days"),
                "people_number": query_data.get("people_number"),
                "budget": query_data.get("budget"),
                "local_constraint": query_data.get("local_constraint"),
            },
        )

    def register_tools(self, registry: ToolRegistry) -> None:
        registry.register(SearchFlightsTool(config=self.config))
        registry.register(SearchGroundTransportTool(config=self.config))
        registry.register(SearchHotelsTool(config=self.config))
        registry.register(SearchRestaurantsTool(config=self.config))
        registry.register(SearchAttractionsTool(config=self.config))
        registry.register(PlanDayTool(config=self.config))
        registry.register(ValidateConstraintsTool(config=self.config, max_retries=2))

        hintable = [
            "search_flights",
            "search_ground_transport",
            "search_hotels",
            "search_restaurants",
            "search_attractions",
            "plan_itinerary",
            "validate_constraints",
        ]
        registry.register(ThinkTool(config=self.config, available_hint_tools=hintable))
        registry.register(DecomposeTool(config=self.config))

    def define_state_machine(self) -> StateMachine:
        transitions = {
            "pending": {
                "searching",
                "planning",
                "validating",
                "terminal",
                "skipped",
                "escalated",
            },
            "searching": {
                "searching",
                "planning",
                "terminal",
                "skipped",
                "escalated",
            },
            "planning": {
                "searching",
                "planning",
                "validating",
                "terminal",
                "skipped",
                "escalated",
            },
            "validating": {
                "searching",
                "planning",
                "validating",
                "terminal",
                "skipped",
                "escalated",
            },
            "terminal": {
                "terminal",
                "planning",
                "searching",
                "validating",
                "skipped",
                "escalated",
            },
            "skipped": {"skipped"},
            "escalated": {"escalated"},
        }
        return StateMachine(transitions=transitions)

    def initial_markers(self, objective: Objective, agent_id: str) -> list[Marker]:
        now = utc_now_iso()
        query = dict(objective.payload.get("query_data", {}))
        city_sequence = self._resolve_city_sequence(query)
        query["city_sequence"] = city_sequence
        leg_dates = self._resolve_leg_dates(query=query, city_sequence=city_sequence)
        query["leg_dates"] = leg_dates

        objective_id = objective.objective_id
        plan_id = f"{objective_id}::plan_itinerary"
        validate_id = f"{objective_id}::validate_constraints"
        finalize_id = f"{objective_id}::finalize"

        base = {
            "objective": objective.description,
            "query_data": query,
            "query_idx": int(objective.payload.get("query_idx", 0)),
        }
        city_specs = self._build_city_search_specs(
            objective_id=objective_id,
            city_sequence=city_sequence,
        )
        route_specs = self._build_route_specs(
            objective_id=objective_id,
            origin=str(query.get("org", "")).strip(),
            city_sequence=city_sequence,
            leg_dates=leg_dates,
            city_specs=city_specs,
        )

        markers: list[Marker] = []
        for route_spec in route_specs:
            markers.extend(
                [
                    Marker(
                        id=route_spec["flight_id"],
                        marker_type="task",
                        target=route_spec["flight_id"],
                        intensity=float(route_spec["flight_intensity"]),
                        state="pending",
                        payload={
                            **base,
                            "origin": route_spec["origin"],
                            "dest": route_spec["dest"],
                            "date": route_spec["date"],
                            "result_key": route_spec["flight_result_key"],
                            "depends_on": route_spec["depends_on"],
                            "eligible_actions": ["search_flights"],
                            "stage": route_spec["flight_result_key"],
                            "leg_label": route_spec["label"],
                        },
                        created_by=agent_id,
                        created_at=now,
                        updated_by=agent_id,
                        updated_at=now,
                        history=["created"],
                    ),
                    Marker(
                        id=route_spec["ground_id"],
                        marker_type="task",
                        target=route_spec["ground_id"],
                        intensity=float(route_spec["ground_intensity"]),
                        state="pending",
                        payload={
                            **base,
                            "origin": route_spec["origin"],
                            "dest": route_spec["dest"],
                            "result_key": route_spec["ground_result_key"],
                            "depends_on": route_spec["depends_on"],
                            "eligible_actions": ["search_ground_transport"],
                            "stage": route_spec["ground_result_key"],
                            "leg_label": route_spec["label"],
                        },
                        created_by=agent_id,
                        created_at=now,
                        updated_by=agent_id,
                        updated_at=now,
                        history=["created"],
                    ),
                ]
            )

        multi_city = len(city_sequence) > 1
        for index, city_spec in enumerate(city_specs):
            city_depends_on = []
            if multi_city and index < len(route_specs):
                city_depends_on = [
                    route_specs[index]["flight_id"],
                    route_specs[index]["ground_id"],
                ]
            for task in city_spec["tasks"]:
                markers.append(
                    Marker(
                        id=task["id"],
                        marker_type="task",
                        target=task["id"],
                        intensity=0.92,
                        state="pending",
                        payload={
                            **base,
                            "city": city_spec["city"],
                            "city_index": index,
                            "result_key": task["result_key"],
                            "depends_on": city_depends_on,
                            "eligible_actions": [task["action"]],
                            "stage": task["result_key"],
                        },
                        created_by=agent_id,
                        created_at=now,
                        updated_by=agent_id,
                        updated_at=now,
                        history=["created"],
                    )
                )

        all_dependency_ids = [
            marker.id
            for marker in markers
        ]
        markers.extend(
            [
                Marker(
                    id=plan_id,
                    marker_type="task",
                    target=plan_id,
                    intensity=1.0,
                    state="pending",
                    payload={
                        **base,
                        "depends_on": all_dependency_ids,
                        "eligible_actions": ["plan_itinerary"],
                        "stage": "planning",
                    },
                    created_by=agent_id,
                    created_at=now,
                    updated_by=agent_id,
                    updated_at=now,
                    history=["created"],
                ),
                Marker(
                    id=validate_id,
                    marker_type="task",
                    target=validate_id,
                    intensity=0.9,
                    state="pending",
                    payload={
                        **base,
                        "depends_on": [plan_id],
                        "eligible_actions": ["validate_constraints"],
                        "stage": "validating",
                    },
                    created_by=agent_id,
                    created_at=now,
                    updated_by=agent_id,
                    updated_at=now,
                    history=["created"],
                ),
                Marker(
                    id=finalize_id,
                    marker_type="task",
                    target=finalize_id,
                    intensity=0.8,
                    state="pending",
                    payload={
                        **base,
                        "depends_on": [validate_id],
                        "eligible_actions": ["validate_constraints"],
                        "stage": "finalize",
                    },
                    created_by=agent_id,
                    created_at=now,
                    updated_by=agent_id,
                    updated_at=now,
                    history=["created"],
                ),
            ]
        )
        return markers

    def evaluate_run(self, env_snapshot: dict[str, Any]) -> dict[str, Any]:
        if self._workspace is None:
            raise ValueError("workspace must be created before evaluation")
        evaluator = TravelPlannerEvaluator(workspace=self._workspace)
        markers = env_snapshot.get("markers", [])
        result = evaluator.evaluate_snapshot(markers)

        domain_cfg = dict(self.config.get("travelplanner", {}))
        include_full_split = bool(domain_cfg.get("official_full_split_eval", False))
        if include_full_split:
            predictions = self._collect_predictions_by_query_idx(markers)
            result["official_full_split"] = evaluator.evaluate_predictions_by_query_idx(
                predictions=predictions,
            )

        return result

    def _collect_predictions_by_query_idx(
        self,
        markers: list[Any],
    ) -> dict[int, list[dict[str, Any]]]:
        predictions: dict[int, list[dict[str, Any]]] = {}
        for marker in markers:
            marker_id = str(getattr(marker, "id", ""))
            if not marker_id.endswith("::finalize"):
                continue
            payload = dict(getattr(marker, "payload", {}))
            query_data = payload.get("query_data")
            plan = payload.get("final_plan")
            if not isinstance(query_data, dict):
                continue
            if not isinstance(plan, list):
                continue
            try:
                query_idx = int(query_data.get("query_idx", -1))
            except Exception:  # noqa: BLE001
                continue
            if query_idx < 0:
                continue
            predictions[query_idx] = plan
        return predictions

    def _resolve_query_idx(self, user_input: dict[str, Any]) -> int:
        if "query_idx" in user_input:
            return max(0, int(user_input["query_idx"]))
        if "query_index" in user_input:
            return max(0, int(user_input["query_index"]))

        objective = str(user_input.get("objective", "")).strip()
        if objective:
            if objective.isdigit():
                return max(0, int(objective))

            match = re.search(r"query\s*(\d+)", objective, flags=re.IGNORECASE)
            if match is not None:
                return max(0, int(match.group(1)))

            if self._workspace is not None:
                rows = self._workspace._load_queries(split=self._workspace.dataset_split)
                for idx, row in enumerate(rows):
                    if str(row.get("query", "")).strip() == objective:
                        return idx

        default_idx = int(self.config.get("travelplanner", {}).get("default_query_idx", 0))
        return max(0, default_idx)

    def _resolve_city_sequence(self, query: dict[str, Any]) -> list[str]:
        raw = query.get("city_sequence")
        if isinstance(raw, list):
            sequence = [str(city).strip() for city in raw if str(city).strip()]
            if sequence:
                return sequence
        if self._workspace is not None:
            sequence = self._workspace.build_city_sequence(query)
            if sequence:
                return sequence
        destination = str(query.get("dest", "")).strip()
        return [destination] if destination else []

    def _resolve_leg_dates(
        self,
        *,
        query: dict[str, Any],
        city_sequence: list[str],
    ) -> list[str]:
        raw = query.get("leg_dates")
        if isinstance(raw, list) and raw:
            dates = [str(value).strip() for value in raw if str(value).strip()]
            if len(dates) >= max(len(city_sequence) + 1, 2):
                return dates

        dates_raw = query.get("date", [])
        dates = [str(value).strip() for value in dates_raw] if isinstance(dates_raw, list) else []
        leg_count = max(len(city_sequence) + 1, 2)
        if not dates:
            return [""] * leg_count
        return [
            dates[min(index * 2, len(dates) - 1)]
            for index in range(leg_count)
        ]

    def _build_city_search_specs(
        self,
        *,
        objective_id: str,
        city_sequence: list[str],
    ) -> list[dict[str, Any]]:
        multi_city = len(city_sequence) > 1
        specs: list[dict[str, Any]] = []
        for city in city_sequence:
            slug = self._slugify_city(city)
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
                    "slug": slug,
                    "tasks": [
                        {
                            "id": f"{objective_id}::{hotel_key}",
                            "result_key": hotel_key,
                            "action": "search_hotels",
                        },
                        {
                            "id": f"{objective_id}::{restaurant_key}",
                            "result_key": restaurant_key,
                            "action": "search_restaurants",
                        },
                        {
                            "id": f"{objective_id}::{attraction_key}",
                            "result_key": attraction_key,
                            "action": "search_attractions",
                        },
                    ],
                }
            )
        return specs

    def _build_route_specs(
        self,
        *,
        objective_id: str,
        origin: str,
        city_sequence: list[str],
        leg_dates: list[str],
        city_specs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        route_cities = [origin, *city_sequence, origin]
        specs: list[dict[str, Any]] = []
        for leg_index in range(len(route_cities) - 1):
            if leg_index == 0:
                label = "outbound"
                flight_key = "search_flights_outbound"
                ground_key = "search_ground_transport_outbound"
                flight_intensity = 0.95
                ground_intensity = 0.93
            elif leg_index == len(route_cities) - 2:
                label = "return"
                flight_key = "search_flights_return"
                ground_key = "search_ground_transport_return"
                flight_intensity = 0.94
                ground_intensity = 0.92
            else:
                label = f"leg_{leg_index}"
                flight_key = f"search_flights_leg_{leg_index}"
                ground_key = f"search_ground_transport_leg_{leg_index}"
                flight_intensity = max(0.84, 0.93 - (leg_index * 0.01))
                ground_intensity = max(0.83, 0.91 - (leg_index * 0.01))

            depends_on: list[str] = []
            if leg_index > 0 and leg_index - 1 < len(city_specs):
                depends_on = [
                    task["id"]
                    for task in city_specs[leg_index - 1]["tasks"]
                ]

            specs.append(
                {
                    "label": label,
                    "origin": route_cities[leg_index],
                    "dest": route_cities[leg_index + 1],
                    "date": leg_dates[min(leg_index, len(leg_dates) - 1)] if leg_dates else "",
                    "flight_id": f"{objective_id}::{flight_key}",
                    "ground_id": f"{objective_id}::{ground_key}",
                    "flight_result_key": flight_key,
                    "ground_result_key": ground_key,
                    "flight_intensity": flight_intensity,
                    "ground_intensity": ground_intensity,
                    "depends_on": depends_on,
                }
            )
        return specs

    def _slugify_city(self, city: str) -> str:
        text = str(city).strip().lower()
        text = re.sub(r"[^a-z0-9]+", "_", text)
        return text.strip("_") or "city"
