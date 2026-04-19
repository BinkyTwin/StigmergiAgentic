"""LangGraph supervisor baseline for TravelPlanner benchmarking."""

from __future__ import annotations

import json
import re
import time
from typing import Any, Literal, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field, ValidationError

from core.schemas import TravelItineraryOutput
from llm.client import LLMClient, LLMResponse

from .evaluator import PlanEvaluation, TravelPlannerEvaluator
from .tools import PlanDayTool
from .workspace import TravelPlannerWorkspace


class RoutePlanOutput(BaseModel):
    """Supervisor routing decision."""

    outbound_transportation: str = "-"
    return_transportation: str = "-"


class AccommodationPlanOutput(BaseModel):
    """Supervisor accommodation selection."""

    accommodation: str = "-"


class RestaurantDayOutput(BaseModel):
    """Meal allocation for one day."""

    day: int
    breakfast: str = "-"
    lunch: str = "-"
    dinner: str = "-"


class RestaurantPlanOutput(BaseModel):
    """Supervisor restaurant allocation."""

    days: list[RestaurantDayOutput] = Field(default_factory=list)


class AttractionDayOutput(BaseModel):
    """Attraction allocation for one day."""

    day: int
    attraction: str = "-"


class AttractionPlanOutput(BaseModel):
    """Supervisor attraction allocation."""

    days: list[AttractionDayOutput] = Field(default_factory=list)


class SupervisorState(TypedDict, total=False):
    """LangGraph state for one TravelPlanner query."""

    objective: str
    objective_id: str
    query_idx: int
    query_data: dict[str, Any]
    search_payload: dict[str, list[dict[str, Any]]]
    routing_context: list[dict[str, Any]]
    route_plan: dict[str, Any]
    transport_plan: dict[str, Any]
    accommodation_plan: dict[str, Any]
    restaurant_plan: dict[str, Any]
    attraction_plan: dict[str, Any]
    itinerary: list[dict[str, Any]]
    final_plan: list[dict[str, Any]]
    assistant_response: str
    evaluation: dict[str, Any]
    final_pass: bool
    retry_count: int
    max_validation_retries: int
    validation_feedback: list[str]
    validation_failures: list[str]
    step_trace: list[dict[str, Any]]
    should_retry: bool


def render_assistant_response(plan: list[dict[str, Any]]) -> str:
    """Render the final TravelPlanner itinerary in the existing text format."""
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


class LangGraphTravelPlannerRunner:
    """Deterministic supervisor baseline backed by LangGraph."""

    def __init__(
        self,
        *,
        config: dict[str, Any],
        workspace: TravelPlannerWorkspace,
        llm_client: LLMClient,
        max_validation_retries: int = 2,
    ) -> None:
        self.config = config
        self.workspace = workspace
        self.llm_client = llm_client
        self.max_validation_retries = max(0, int(max_validation_retries))
        self.schema_parse_retries = 2
        self.planner = PlanDayTool(config=config, max_planning_attempts=1)
        self.evaluator = TravelPlannerEvaluator(workspace=workspace)
        self._graph = self._build_graph()

    def run_query(
        self,
        *,
        objective: str,
        objective_id: str,
        query_idx: int,
        query_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute the supervisor graph and return the benchmark payload."""
        started_at = time.perf_counter()
        initial_state: SupervisorState = {
            "objective": objective,
            "objective_id": objective_id,
            "query_idx": int(query_idx),
            "query_data": dict(query_data),
            "retry_count": 0,
            "max_validation_retries": self.max_validation_retries,
            "validation_feedback": [],
            "validation_failures": [],
            "step_trace": [],
            "should_retry": False,
        }
        final_state = self._graph.invoke(
            initial_state,
            config={"configurable": {"thread_id": f"langgraph-travelplanner-{query_idx}"}},
        )
        runtime_seconds = round(time.perf_counter() - started_at, 4)

        final_plan = list(final_state.get("final_plan", []))
        assistant_response = str(
            final_state.get("assistant_response") or render_assistant_response(final_plan)
        )
        evaluation = dict(final_state.get("evaluation", {}))
        return {
            "status": "ok",
            "query_idx": int(final_state.get("query_idx", query_idx)),
            "objective": objective,
            "objective_id": objective_id,
            "assistant_response": assistant_response,
            "evaluation": evaluation,
            "final_pass": bool(final_state.get("final_pass", False)),
            "final_plan": final_plan,
            "plan": final_plan,
            "summary": {
                "framework": "langgraph_supervisor",
                "adapter": "travelplanner_langgraph_supervisor",
                "llm_provider": str(self.config.get("llm", {}).get("provider", "")),
                "llm_model": str(self.config.get("llm", {}).get("model", "")),
                "tokens_used": int(getattr(self.llm_client, "total_tokens_used", 0)),
                "cost_used": float(getattr(self.llm_client, "total_cost_usd", 0.0)),
                "runtime_seconds": runtime_seconds,
                "step_trace": list(final_state.get("step_trace", [])),
                "retry_count": int(final_state.get("retry_count", 0)),
                "validation_failures": list(final_state.get("validation_failures", [])),
                "coordination_overhead": len(final_state.get("step_trace", [])),
                "search_payload_keys": sorted(final_state.get("search_payload", {}).keys()),
            },
        }

    def _build_graph(self):
        workflow = StateGraph(SupervisorState)
        workflow.add_node("load_query_context", self._load_query_context)
        workflow.add_node("route_planner", self._route_planner)
        workflow.add_node("transport_planner", self._transport_planner)
        workflow.add_node("accommodation_planner", self._accommodation_planner)
        workflow.add_node("restaurant_planner", self._restaurant_planner)
        workflow.add_node("attraction_planner", self._attraction_planner)
        workflow.add_node("final_integrator", self._final_integrator)
        workflow.add_node("official_validator", self._official_validator)
        workflow.add_node("retry_or_finish", self._retry_or_finish)

        workflow.add_edge(START, "load_query_context")
        workflow.add_edge("load_query_context", "route_planner")
        workflow.add_edge("route_planner", "transport_planner")
        workflow.add_edge("transport_planner", "accommodation_planner")
        workflow.add_edge("accommodation_planner", "restaurant_planner")
        workflow.add_edge("restaurant_planner", "attraction_planner")
        workflow.add_edge("attraction_planner", "final_integrator")
        workflow.add_edge("final_integrator", "official_validator")
        workflow.add_edge("official_validator", "retry_or_finish")
        workflow.add_conditional_edges(
            "retry_or_finish",
            self._route_after_retry,
            ["route_planner", END],
        )
        return workflow.compile(checkpointer=MemorySaver())

    def _load_query_context(self, state: SupervisorState) -> dict[str, Any]:
        started_at = time.perf_counter()
        query_data = dict(state.get("query_data", {}))
        raw_payload: dict[str, Any] = {}
        self.planner._inject_default_search_payloads(  # noqa: SLF001 - deliberate reuse
            results=raw_payload,
            query_data=query_data,
            workspace=self.workspace,
        )
        search_payload = self.planner._compact_search_payload(  # noqa: SLF001 - deliberate reuse
            raw_payload,
            query_data=query_data,
        )
        routing_context = self.planner._build_routing_context(  # noqa: SLF001 - deliberate reuse
            query_data=self.planner._compact_query_data(query_data),  # noqa: SLF001 - deliberate reuse
            search_payload=search_payload,
        )
        return {
            "search_payload": search_payload,
            "routing_context": routing_context,
            "step_trace": self._append_trace(
                state,
                node_name="load_query_context",
                started_at=started_at,
                search_payload_keys=sorted(search_payload.keys()),
                routing_options=len(routing_context),
            ),
        }

    def _route_planner(self, state: SupervisorState) -> dict[str, Any]:
        started_at = time.perf_counter()
        query_data = dict(state.get("query_data", {}))
        feedback = list(state.get("validation_feedback", []))
        prompt = (
            "You are the central route planner for a TravelPlanner supervisor graph.\n"
            "Return compact valid JSON only with these keys: "
            '{"outbound_transportation":"...","return_transportation":"..."}\n'
            "Choose exact transportation strings from RoutingData when possible.\n"
            "If no valid route exists, return '-'.\n"
            f"Query: {json.dumps(self.planner._compact_query_data(query_data), ensure_ascii=True)}\n"  # noqa: SLF001 - deliberate reuse
            f"ValidationFeedback: {json.dumps(feedback, ensure_ascii=True)}\n"
            f"RoutingData: {json.dumps(state.get('routing_context', []), ensure_ascii=True)}"
        )
        route_plan, trace = self._call_schema(
            state=state,
            node_name="route_planner",
            prompt=prompt,
            response_schema=RoutePlanOutput,
            fallback_fn=self._fallback_route_plan,
        )
        return {
            "route_plan": route_plan.model_dump(),
            "step_trace": trace,
        }

    def _transport_planner(self, state: SupervisorState) -> dict[str, Any]:
        started_at = time.perf_counter()
        query_data = dict(state.get("query_data", {}))
        route_plan = dict(state.get("route_plan", {}))
        search_payload = dict(state.get("search_payload", {}))
        route_options = self.planner._build_route_option_catalog(search_payload)  # noqa: SLF001 - deliberate reuse

        origin = str(query_data.get("org", "")).strip()
        destination = str(query_data.get("dest", "")).strip()
        outbound_city = f"from {origin} to {destination}"
        return_city = f"from {destination} to {origin}"
        outbound = self.planner._normalize_transportation_field(  # noqa: SLF001 - deliberate reuse
            raw_value=route_plan.get("outbound_transportation"),
            current_city=outbound_city,
            route_options=route_options,
        )
        inbound = self.planner._normalize_transportation_field(  # noqa: SLF001 - deliberate reuse
            raw_value=route_plan.get("return_transportation"),
            current_city=return_city,
            route_options=route_options,
        )
        transport_plan = {
            "outbound_transportation": outbound,
            "return_transportation": inbound,
        }
        return {
            "transport_plan": transport_plan,
            "step_trace": self._append_trace(
                state,
                node_name="transport_planner",
                started_at=started_at,
                outbound_transportation=outbound,
                return_transportation=inbound,
            ),
        }

    def _accommodation_planner(self, state: SupervisorState) -> dict[str, Any]:
        started_at = time.perf_counter()
        query_data = dict(state.get("query_data", {}))
        search_payload = dict(state.get("search_payload", {}))
        hotels = search_payload.get("search_hotels", [])
        prompt = (
            "You are the accommodation planner for a TravelPlanner supervisor graph.\n"
            "Return compact valid JSON only with key "
            '{"accommodation":"<name>, <city> or -"}\n'
            "Use only hotels from SearchData and respect occupancy, minimum nights, room type, and house rules.\n"
            f"Query: {json.dumps(self.planner._compact_query_data(query_data), ensure_ascii=True)}\n"  # noqa: SLF001 - deliberate reuse
            f"ValidationFeedback: {json.dumps(state.get('validation_feedback', []), ensure_ascii=True)}\n"
            f"SearchData: {json.dumps({'search_hotels': hotels}, ensure_ascii=True)}"
        )
        accommodation_plan, trace = self._call_schema(
            state=state,
            node_name="accommodation_planner",
            prompt=prompt,
            response_schema=AccommodationPlanOutput,
            fallback_fn=self._fallback_accommodation_plan,
        )
        normalized = self.planner._normalize_named_field(  # noqa: SLF001 - deliberate reuse
            raw_value=accommodation_plan.accommodation,
            candidates=self.planner._build_named_candidates(  # noqa: SLF001 - deliberate reuse
                search_payload=search_payload,
                keys=("search_hotels",),
                name_field="NAME",
                city_field="city",
            ),
        )
        payload = accommodation_plan.model_dump()
        payload["accommodation"] = normalized
        return {
            "accommodation_plan": payload,
            "step_trace": trace,
        }

    def _restaurant_planner(self, state: SupervisorState) -> dict[str, Any]:
        started_at = time.perf_counter()
        query_data = dict(state.get("query_data", {}))
        days = max(1, int(query_data.get("days", 1)))
        search_payload = dict(state.get("search_payload", {}))
        prompt = (
            "You are the restaurant planner for a TravelPlanner supervisor graph.\n"
            "Return compact valid JSON only with key "
            '{"days":[{"day":1,"breakfast":"...","lunch":"...","dinner":"..."}]}\n'
            "Provide exactly one object per trip day. Use canonical '<name>, <city>' strings or '-'.\n"
            "Avoid reusing the same restaurant across meals when possible.\n"
            f"TripDays: {days}\n"
            f"Query: {json.dumps(self.planner._compact_query_data(query_data), ensure_ascii=True)}\n"  # noqa: SLF001 - deliberate reuse
            f"ValidationFeedback: {json.dumps(state.get('validation_feedback', []), ensure_ascii=True)}\n"
            f"SearchData: {json.dumps({'search_restaurants': search_payload.get('search_restaurants', [])}, ensure_ascii=True)}"
        )
        restaurant_plan, trace = self._call_schema(
            state=state,
            node_name="restaurant_planner",
            prompt=prompt,
            response_schema=RestaurantPlanOutput,
            fallback_fn=self._fallback_restaurant_plan,
        )
        candidates = self.planner._build_named_candidates(  # noqa: SLF001 - deliberate reuse
            search_payload=search_payload,
            keys=("search_restaurants",),
            name_field="Name",
            city_field="City",
        )
        normalized_days = self._normalize_restaurant_days(
            days=restaurant_plan.days,
            candidates=candidates,
            total_days=days,
        )
        return {
            "restaurant_plan": {
                "days": normalized_days,
            },
            "step_trace": trace,
        }

    def _attraction_planner(self, state: SupervisorState) -> dict[str, Any]:
        started_at = time.perf_counter()
        query_data = dict(state.get("query_data", {}))
        days = max(1, int(query_data.get("days", 1)))
        search_payload = dict(state.get("search_payload", {}))
        prompt = (
            "You are the attraction planner for a TravelPlanner supervisor graph.\n"
            "Return compact valid JSON only with key "
            '{"days":[{"day":1,"attraction":"..."}]}\n'
            "Provide exactly one object per trip day. Use canonical '<name>, <city>' strings or '-'.\n"
            "Avoid repeating the same attraction across days.\n"
            f"TripDays: {days}\n"
            f"Query: {json.dumps(self.planner._compact_query_data(query_data), ensure_ascii=True)}\n"  # noqa: SLF001 - deliberate reuse
            f"ValidationFeedback: {json.dumps(state.get('validation_feedback', []), ensure_ascii=True)}\n"
            f"SearchData: {json.dumps({'search_attractions': search_payload.get('search_attractions', [])}, ensure_ascii=True)}"
        )
        attraction_plan, trace = self._call_schema(
            state=state,
            node_name="attraction_planner",
            prompt=prompt,
            response_schema=AttractionPlanOutput,
            fallback_fn=self._fallback_attraction_plan,
        )
        candidates = self.planner._build_named_candidates(  # noqa: SLF001 - deliberate reuse
            search_payload=search_payload,
            keys=("search_attractions",),
            name_field="Name",
            city_field="City",
        )
        normalized_days = self._normalize_attraction_days(
            days=attraction_plan.days,
            candidates=candidates,
            total_days=days,
        )
        return {
            "attraction_plan": {
                "days": normalized_days,
            },
            "step_trace": trace,
        }

    def _final_integrator(self, state: SupervisorState) -> dict[str, Any]:
        started_at = time.perf_counter()
        query_data = dict(state.get("query_data", {}))
        search_payload = dict(state.get("search_payload", {}))
        supervisor_guidance = {
            "route_plan": state.get("transport_plan", {}),
            "accommodation_plan": state.get("accommodation_plan", {}),
            "restaurant_plan": state.get("restaurant_plan", {}),
            "attraction_plan": state.get("attraction_plan", {}),
        }
        base_prompt = self.planner._build_prompt(  # noqa: SLF001 - deliberate reuse
            query_data=query_data,
            search_payload=search_payload,
            validation_feedback=list(state.get("validation_feedback", [])),
        )
        prompt = (
            f"{base_prompt}\n\n"
            "SupervisorGuidance:\n"
            f"{json.dumps(supervisor_guidance, ensure_ascii=True)}\n"
            "Follow SupervisorGuidance when it is compatible with the hard requirements."
            " If there is a conflict, repair the minimal number of fields needed to satisfy the constraints."
        )
        itinerary_output, trace = self._call_schema(
            state=state,
            node_name="final_integrator",
            prompt=prompt,
            response_schema=TravelItineraryOutput,
            fallback_fn=self._fallback_itinerary_output,
        )
        itinerary = self.planner._normalize_itinerary(  # noqa: SLF001 - deliberate reuse
            itinerary=[day.model_dump() for day in itinerary_output.plan],
            query_data=query_data,
            search_payload=search_payload,
        )
        return {
            "itinerary": itinerary,
            "final_plan": itinerary,
            "assistant_response": render_assistant_response(itinerary),
            "step_trace": trace,
        }

    def _official_validator(self, state: SupervisorState) -> dict[str, Any]:
        started_at = time.perf_counter()
        query_data = dict(state.get("query_data", {}))
        itinerary = list(state.get("itinerary", []))
        plan_eval = self.evaluator.evaluate_plan(query_data=query_data, plan=itinerary)
        evaluation = self.evaluator.aggregate([plan_eval])
        evaluation["estimated_cost"] = float(plan_eval.estimated_cost)
        failed_feedback = self.evaluator.failure_feedback(plan_eval)
        failed_constraints = self.evaluator.failed_constraints(plan_eval)
        retry_count = int(state.get("retry_count", 0))
        if not plan_eval.final_pass:
            retry_count += 1
        return {
            "evaluation": evaluation,
            "final_pass": bool(plan_eval.final_pass),
            "validation_feedback": failed_feedback,
            "validation_failures": failed_constraints,
            "retry_count": retry_count,
            "step_trace": self._append_trace(
                state,
                node_name="official_validator",
                started_at=started_at,
                final_pass=bool(plan_eval.final_pass),
                validation_failures=failed_constraints,
            ),
        }

    def _retry_or_finish(self, state: SupervisorState) -> dict[str, Any]:
        started_at = time.perf_counter()
        retry_count = int(state.get("retry_count", 0))
        max_retries = int(state.get("max_validation_retries", self.max_validation_retries))
        should_retry = (
            not bool(state.get("final_pass", False))
            and retry_count <= max_retries
            and bool(state.get("validation_feedback", []))
        )
        return {
            "should_retry": should_retry,
            "step_trace": self._append_trace(
                state,
                node_name="retry_or_finish",
                started_at=started_at,
                should_retry=should_retry,
                retry_count=retry_count,
                max_validation_retries=max_retries,
            ),
        }

    def _route_after_retry(self, state: SupervisorState) -> Literal["route_planner", END]:
        if bool(state.get("should_retry", False)):
            return "route_planner"
        return END

    def _call_schema(
        self,
        *,
        state: SupervisorState,
        node_name: str,
        prompt: str,
        response_schema: type[BaseModel],
        fallback_fn: Any | None = None,
    ) -> tuple[BaseModel, list[dict[str, Any]]]:
        started_at = time.perf_counter()
        before_tokens = int(getattr(self.llm_client, "total_tokens_used", 0))
        before_cost = float(getattr(self.llm_client, "total_cost_usd", 0.0))
        parse_errors: list[str] = []
        response: LLMResponse | None = None
        model: BaseModel | None = None
        retry_prompt = prompt
        fallback_used = False

        for attempt in range(self.schema_parse_retries + 1):
            response = self.llm_client.call(
                prompt=retry_prompt,
                response_schema=response_schema,
            )
            try:
                model = self._parse_schema_response(
                    response=response,
                    response_schema=response_schema,
                )
                break
            except (ValidationError, json.JSONDecodeError, ValueError) as exc:
                parse_errors.append(f"attempt_{attempt + 1}: {exc}")
                retry_prompt = (
                    f"{prompt}\n\n"
                    "Your previous answer was malformed, truncated, or not valid JSON. "
                    "Return compact valid JSON only. No markdown. No explanation."
                )

        if model is None:
            if fallback_fn is None:
                error_text = "; ".join(parse_errors) if parse_errors else "unknown schema parse failure"
                raise RuntimeError(f"{node_name} failed to produce valid structured output: {error_text}")
            model = fallback_fn(state)
            fallback_used = True

        assert response is not None
        trace = self._append_trace(
            state,
            node_name=node_name,
            started_at=started_at,
            llm_model=str(getattr(response, "model", "")),
            tokens_used=int(getattr(self.llm_client, "total_tokens_used", 0)) - before_tokens,
            cost_used=round(float(getattr(self.llm_client, "total_cost_usd", 0.0)) - before_cost, 8),
            latency_ms=int(getattr(response, "latency_ms", 0)),
            parse_attempts=len(parse_errors) + 1,
            fallback_used=fallback_used,
            parse_errors=parse_errors,
        )
        return model, trace

    def _parse_schema_response(
        self,
        *,
        response: LLMResponse,
        response_schema: type[BaseModel],
    ) -> BaseModel:
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, response_schema):
            return parsed

        raw_content = str(getattr(response, "content", "")).strip()
        if not raw_content:
            raise ValueError("empty response content")

        json_candidate = self._extract_json_candidate(raw_content)
        if json_candidate:
            try:
                return response_schema.model_validate_json(json_candidate)
            except ValidationError:
                pass

        extracted_fields = self._extract_simple_fields(raw_content)
        if extracted_fields:
            return response_schema.model_validate(extracted_fields)

        return response_schema.model_validate_json(raw_content)

    def _extract_json_candidate(self, raw_content: str) -> str:
        start = raw_content.find("{")
        if start < 0:
            return ""

        in_string = False
        escaped = False
        depth = 0
        for index in range(start, len(raw_content)):
            char = raw_content[index]
            if in_string:
                if escaped:
                    escaped = False
                    continue
                if char == "\\":
                    escaped = True
                    continue
                if char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return raw_content[start : index + 1]
        return ""

    def _extract_simple_fields(self, raw_content: str) -> dict[str, Any]:
        extracted: dict[str, Any] = {}
        simple_patterns = {
            "accommodation": r'"accommodation"\s*:\s*"(?P<value>[^"\n\r]*)"',
            "outbound_transportation": r'"outbound_transportation"\s*:\s*"(?P<value>[^"\n\r]*)"',
            "return_transportation": r'"return_transportation"\s*:\s*"(?P<value>[^"\n\r]*)"',
        }
        for field, pattern in simple_patterns.items():
            match = re.search(pattern, raw_content)
            if match:
                extracted[field] = match.group("value")
        return extracted

    def _append_trace(
        self,
        state: SupervisorState,
        *,
        node_name: str,
        started_at: float,
        **extra: Any,
    ) -> list[dict[str, Any]]:
        trace = [dict(item) for item in state.get("step_trace", [])]
        entry = {
            "node": node_name,
            "duration_seconds": round(time.perf_counter() - started_at, 4),
        }
        entry.update(extra)
        trace.append(entry)
        return trace

    def _fallback_route_plan(self, state: SupervisorState) -> RoutePlanOutput:
        outbound = "-"
        inbound = "-"
        for item in state.get("routing_context", []):
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "")).strip().lower()
            options = item.get("transportation_options", [])
            if not isinstance(options, list) or not options:
                continue
            if label == "outbound" and outbound == "-":
                outbound = str(options[0]).strip() or "-"
            if label == "return" and inbound == "-":
                inbound = str(options[0]).strip() or "-"
        return RoutePlanOutput(
            outbound_transportation=outbound,
            return_transportation=inbound,
        )

    def _fallback_accommodation_plan(
        self,
        state: SupervisorState,
    ) -> AccommodationPlanOutput:
        search_payload = dict(state.get("search_payload", {}))
        candidates = self.planner._build_named_candidates(  # noqa: SLF001 - deliberate reuse
            search_payload=search_payload,
            keys=("search_hotels",),
            name_field="NAME",
            city_field="city",
        )
        accommodation = candidates[0]["canonical"] if candidates else "-"
        return AccommodationPlanOutput(accommodation=accommodation)

    def _fallback_restaurant_plan(
        self,
        state: SupervisorState,
    ) -> RestaurantPlanOutput:
        total_days = max(1, int(dict(state.get("query_data", {})).get("days", 1)))
        return RestaurantPlanOutput(
            days=[
                RestaurantDayOutput(day=day_index, breakfast="-", lunch="-", dinner="-")
                for day_index in range(1, total_days + 1)
            ]
        )

    def _fallback_attraction_plan(
        self,
        state: SupervisorState,
    ) -> AttractionPlanOutput:
        total_days = max(1, int(dict(state.get("query_data", {})).get("days", 1)))
        return AttractionPlanOutput(
            days=[
                AttractionDayOutput(day=day_index, attraction="-")
                for day_index in range(1, total_days + 1)
            ]
        )

    def _fallback_itinerary_output(
        self,
        state: SupervisorState,
    ) -> TravelItineraryOutput:
        query_data = dict(state.get("query_data", {}))
        total_days = max(1, int(query_data.get("days", 1)))
        destination = str(query_data.get("dest", "")).strip()
        origin = str(query_data.get("org", "")).strip()

        restaurant_days = {
            int(item.get("day", 0)): item
            for item in dict(state.get("restaurant_plan", {})).get("days", [])
            if isinstance(item, dict)
        }
        attraction_days = {
            int(item.get("day", 0)): item
            for item in dict(state.get("attraction_plan", {})).get("days", [])
            if isinstance(item, dict)
        }
        accommodation = str(
            dict(state.get("accommodation_plan", {})).get("accommodation", "-")
        ).strip() or "-"
        transport_plan = dict(state.get("transport_plan", {}))
        outbound_transport = str(
            transport_plan.get("outbound_transportation", "-")
        ).strip() or "-"
        return_transport = str(
            transport_plan.get("return_transportation", "-")
        ).strip() or "-"

        plan: list[dict[str, Any]] = []
        for day_index in range(1, total_days + 1):
            day_restaurants = restaurant_days.get(day_index, {})
            day_attraction = attraction_days.get(day_index, {})
            if day_index == 1:
                current_city = f"from {origin} to {destination}" if origin and destination else destination
                transportation = outbound_transport
            elif day_index == total_days and return_transport != "-":
                current_city = f"from {destination} to {origin}" if origin and destination else destination
                transportation = return_transport
            else:
                current_city = destination or "-"
                transportation = "-"

            plan.append(
                {
                    "current_city": current_city,
                    "transportation": transportation,
                    "breakfast": str(day_restaurants.get("breakfast", "-") or "-"),
                    "attraction": str(day_attraction.get("attraction", "-") or "-"),
                    "lunch": str(day_restaurants.get("lunch", "-") or "-"),
                    "dinner": str(day_restaurants.get("dinner", "-") or "-"),
                    "accommodation": accommodation if day_index < total_days else "-",
                }
            )

        normalized = self.planner._normalize_itinerary(  # noqa: SLF001 - deliberate reuse
            itinerary=plan,
            query_data=query_data,
            search_payload=dict(state.get("search_payload", {})),
        )
        return TravelItineraryOutput.model_validate({"plan": normalized})

    def _normalize_restaurant_days(
        self,
        *,
        days: list[RestaurantDayOutput],
        candidates: list[dict[str, str]],
        total_days: int,
    ) -> list[dict[str, Any]]:
        by_day = {
            max(1, int(day.day)): {
                "day": max(1, int(day.day)),
                "breakfast": self.planner._normalize_named_field(raw_value=day.breakfast, candidates=candidates),  # noqa: SLF001 - deliberate reuse
                "lunch": self.planner._normalize_named_field(raw_value=day.lunch, candidates=candidates),  # noqa: SLF001 - deliberate reuse
                "dinner": self.planner._normalize_named_field(raw_value=day.dinner, candidates=candidates),  # noqa: SLF001 - deliberate reuse
            }
            for day in days
        }
        normalized: list[dict[str, Any]] = []
        for day_index in range(1, total_days + 1):
            normalized.append(
                by_day.get(
                    day_index,
                    {
                        "day": day_index,
                        "breakfast": "-",
                        "lunch": "-",
                        "dinner": "-",
                    },
                )
            )
        return normalized

    def _normalize_attraction_days(
        self,
        *,
        days: list[AttractionDayOutput],
        candidates: list[dict[str, str]],
        total_days: int,
    ) -> list[dict[str, Any]]:
        by_day = {
            max(1, int(day.day)): {
                "day": max(1, int(day.day)),
                "attraction": self.planner._normalize_attraction_field(raw_value=day.attraction, candidates=candidates),  # noqa: SLF001 - deliberate reuse
            }
            for day in days
        }
        normalized: list[dict[str, Any]] = []
        for day_index in range(1, total_days + 1):
            normalized.append(
                by_day.get(
                    day_index,
                    {
                        "day": day_index,
                        "attraction": "-",
                    },
                )
            )
        return normalized
