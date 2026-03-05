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
                "days": query_data.get("days"),
                "people_number": query_data.get("people_number"),
                "budget": query_data.get("budget"),
                "local_constraint": query_data.get("local_constraint"),
            },
        )

    def register_tools(self, registry: ToolRegistry) -> None:
        registry.register(SearchFlightsTool(config=self.config))
        registry.register(SearchHotelsTool(config=self.config))
        registry.register(SearchRestaurantsTool(config=self.config))
        registry.register(SearchAttractionsTool(config=self.config))
        registry.register(PlanDayTool(config=self.config))
        registry.register(ValidateConstraintsTool(config=self.config, max_retries=2))

        hintable = [
            "search_flights",
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
        dates = query.get("date", [])
        outbound_date = str(dates[0]) if isinstance(dates, list) and dates else ""

        objective_id = objective.objective_id
        flights_id = f"{objective_id}::search_flights"
        hotels_id = f"{objective_id}::search_hotels"
        attractions_id = f"{objective_id}::search_attractions"
        plan_id = f"{objective_id}::plan_itinerary"
        validate_id = f"{objective_id}::validate_constraints"
        finalize_id = f"{objective_id}::finalize"

        base = {
            "objective": objective.description,
            "query_data": query,
            "query_idx": int(objective.payload.get("query_idx", 0)),
        }

        return [
            Marker(
                id=flights_id,
                marker_type="task",
                target=flights_id,
                intensity=0.95,
                state="pending",
                payload={
                    **base,
                    "origin": str(query.get("org", "")),
                    "dest": str(query.get("dest", "")),
                    "date": outbound_date,
                    "eligible_actions": ["search_flights"],
                    "stage": "search_flights",
                },
                created_by=agent_id,
                created_at=now,
                updated_by=agent_id,
                updated_at=now,
                history=["created"],
            ),
            Marker(
                id=hotels_id,
                marker_type="task",
                target=hotels_id,
                intensity=0.92,
                state="pending",
                payload={
                    **base,
                    "city": str(query.get("dest", "")),
                    "eligible_actions": ["search_hotels"],
                    "stage": "search_hotels",
                },
                created_by=agent_id,
                created_at=now,
                updated_by=agent_id,
                updated_at=now,
                history=["created"],
            ),
            Marker(
                id=attractions_id,
                marker_type="task",
                target=attractions_id,
                intensity=0.92,
                state="pending",
                payload={
                    **base,
                    "city": str(query.get("dest", "")),
                    "eligible_actions": ["search_attractions"],
                    "stage": "search_attractions",
                },
                created_by=agent_id,
                created_at=now,
                updated_by=agent_id,
                updated_at=now,
                history=["created"],
            ),
            Marker(
                id=plan_id,
                marker_type="task",
                target=plan_id,
                intensity=1.0,
                state="pending",
                payload={
                    **base,
                    "depends_on": [flights_id, hotels_id, attractions_id],
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

    def evaluate_run(self, env_snapshot: dict[str, Any]) -> dict[str, Any]:
        if self._workspace is None:
            raise ValueError("workspace must be created before evaluation")
        evaluator = TravelPlannerEvaluator(workspace=self._workspace)
        markers = env_snapshot.get("markers", [])
        return evaluator.evaluate_snapshot(markers)

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
