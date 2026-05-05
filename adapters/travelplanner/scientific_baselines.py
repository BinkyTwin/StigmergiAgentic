"""Scientific TravelPlanner baselines for organization-philosophy benchmarking."""

from __future__ import annotations

import json
import time
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from core.schemas import TravelItineraryOutput
from llm.client import LLMClient, LLMResponse

from .evaluator import PlanEvaluation, TravelPlannerEvaluator
from .tools import PlanDayTool
from .workspace import TravelPlannerWorkspace


class SelfRefineCritiqueOutput(BaseModel):
    """Self-refine critique payload."""

    issues: list[str] = Field(default_factory=list)
    repair_instructions: list[str] = Field(default_factory=list)


class PlannerExecutorDayOutput(BaseModel):
    """Planner-executor day blueprint."""

    day: int
    breakfast: str = "-"
    lunch: str = "-"
    dinner: str = "-"
    attraction: str = "-"


class PlannerExecutorBlueprintOutput(BaseModel):
    """Planner-executor blueprint payload."""

    outbound_transportation: str = "-"
    return_transportation: str = "-"
    accommodation: str = "-"
    days: list[PlannerExecutorDayOutput] = Field(default_factory=list)


class MetaGPTRequirementsOutput(BaseModel):
    """ProductManager role output — extracted hard + commonsense requirements."""

    hard_constraints: list[str] = Field(default_factory=list)
    commonsense_constraints: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)


class MetaGPTArchitectureDayOutput(BaseModel):
    """Architect role per-day skeleton."""

    day: int
    current_city: str = "-"
    transportation: str = "-"


class MetaGPTArchitectureOutput(BaseModel):
    """Architect role output — macro plan and per-day city/transport skeleton."""

    accommodation_strategy: str = "-"
    city_sequence: list[str] = Field(default_factory=list)
    days: list[MetaGPTArchitectureDayOutput] = Field(default_factory=list)


def render_assistant_response(plan: list[dict[str, Any]]) -> str:
    """Render the final TravelPlanner itinerary in the repository text format."""
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


class TravelPlannerScientificBaselineRunner:
    """Shared implementation for controlled TravelPlanner baselines."""

    def __init__(
        self,
        *,
        mode: Literal[
            "direct",
            "cot",
            "self_refine",
            "planner_executor",
            "metagpt_sequential",
        ],
        config: dict[str, Any],
        workspace: TravelPlannerWorkspace,
        llm_client: LLMClient,
        seed: int | None = None,
    ) -> None:
        self.mode = mode
        self.config = config
        self.workspace = workspace
        self.llm_client = llm_client
        self.seed = seed
        self.planner = PlanDayTool(config=config, max_planning_attempts=1)
        self.evaluator = TravelPlannerEvaluator(workspace=workspace)
        self.node_retry_attempts = 2
        self.node_retry_backoff_seconds = 2.0

    def run_query(
        self,
        *,
        objective: str,
        objective_id: str,
        query_idx: int,
        query_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute one query with the configured baseline mode."""
        started_at = time.perf_counter()
        search_payload = self._build_search_payload(query_data=query_data)
        base_prompt = self.planner._build_prompt(  # noqa: SLF001 - deliberate reuse
            query_data=query_data,
            search_payload=search_payload,
            validation_feedback=[],
        )
        step_trace: list[dict[str, Any]] = []
        retry_count = 0

        if self.mode == "direct":
            itinerary = self._run_direct(
                base_prompt=base_prompt,
                query_data=query_data,
                search_payload=search_payload,
                step_trace=step_trace,
            )
        elif self.mode == "cot":
            itinerary = self._run_cot(
                base_prompt=base_prompt,
                query_data=query_data,
                search_payload=search_payload,
                step_trace=step_trace,
            )
        elif self.mode == "self_refine":
            itinerary, retry_count = self._run_self_refine(
                base_prompt=base_prompt,
                query_data=query_data,
                search_payload=search_payload,
                step_trace=step_trace,
            )
        elif self.mode == "planner_executor":
            itinerary = self._run_planner_executor(
                base_prompt=base_prompt,
                query_data=query_data,
                search_payload=search_payload,
                step_trace=step_trace,
            )
        elif self.mode == "metagpt_sequential":
            itinerary = self._run_metagpt_sequential(
                base_prompt=base_prompt,
                query_data=query_data,
                search_payload=search_payload,
                step_trace=step_trace,
            )
        else:
            raise ValueError(f"Unsupported scientific baseline mode: {self.mode}")

        plan_eval = self.evaluator.evaluate_plan(query_data=query_data, plan=itinerary)
        evaluation = self.evaluator.aggregate([plan_eval])
        evaluation["estimated_cost"] = float(plan_eval.estimated_cost)
        validation_failures = self.evaluator.failed_constraints(plan_eval)
        validation_feedback = self.evaluator.failure_feedback(plan_eval)
        step_trace.append(
            {
                "node": "official_validator",
                "final_pass": bool(plan_eval.final_pass),
                "validation_failures": validation_failures,
                "validation_feedback_count": len(validation_feedback),
                "estimated_cost": float(plan_eval.estimated_cost),
            }
        )
        runtime_seconds = round(time.perf_counter() - started_at, 4)
        assistant_response = render_assistant_response(itinerary)
        framework_name = {
            "direct": "solo_direct",
            "cot": "solo_cot",
            "self_refine": "solo_self_refine",
            "planner_executor": "planner_executor",
            "metagpt_sequential": "metagpt_sequential",
        }[self.mode]

        return {
            "status": "ok",
            "query_idx": int(query_idx),
            "objective": objective,
            "objective_id": objective_id,
            "assistant_response": assistant_response,
            "evaluation": evaluation,
            "final_pass": bool(plan_eval.final_pass),
            "final_plan": itinerary,
            "plan": itinerary,
            "summary": {
                "framework": framework_name,
                "adapter": f"travelplanner_{framework_name}",
                "llm_provider": str(self.config.get("llm", {}).get("provider", "")),
                "llm_model": str(self.config.get("llm", {}).get("model", "")),
                "seed": self.seed,
                "tokens_used": int(getattr(self.llm_client, "total_tokens_used", 0)),
                "cost_used": float(getattr(self.llm_client, "total_cost_usd", 0.0)),
                "runtime_seconds": runtime_seconds,
                "step_trace": step_trace,
                "retry_count": retry_count,
                "validation_failures": validation_failures,
                "coordination_overhead": self._coordination_overhead(
                    mode=self.mode,
                    step_trace=step_trace,
                ),
                "search_payload_keys": sorted(search_payload.keys()),
                "run_status": "success",
            },
        }

    def _run_direct(
        self,
        *,
        base_prompt: str,
        query_data: dict[str, Any],
        search_payload: dict[str, Any],
        step_trace: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        itinerary = self._call_itinerary(
            node_name="direct_planner",
            prompt=base_prompt,
            query_data=query_data,
            search_payload=search_payload,
            step_trace=step_trace,
        )
        return itinerary

    def _run_cot(
        self,
        *,
        base_prompt: str,
        query_data: dict[str, Any],
        search_payload: dict[str, Any],
        step_trace: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        prompt = (
            "Reason carefully about transportation, room constraints, city transitions, "
            "restaurant uniqueness, and attraction uniqueness before answering. "
            "Return only the final strict JSON.\n\n"
            f"{base_prompt}"
        )
        itinerary = self._call_itinerary(
            node_name="cot_planner",
            prompt=prompt,
            query_data=query_data,
            search_payload=search_payload,
            step_trace=step_trace,
        )
        return itinerary

    def _run_self_refine(
        self,
        *,
        base_prompt: str,
        query_data: dict[str, Any],
        search_payload: dict[str, Any],
        step_trace: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], int]:
        try:
            draft_itinerary = self._call_itinerary(
                node_name="self_refine_draft",
                prompt=(
                    "Produce a strong first draft of the itinerary. "
                    "Return only strict JSON.\n\n"
                    f"{base_prompt}"
                ),
                query_data=query_data,
                search_payload=search_payload,
                step_trace=step_trace,
            )
        except Exception as exc:  # noqa: BLE001
            step_trace.append(
                {
                    "node": "self_refine_draft_fallback",
                    "reason": "llm_call_failed",
                    "error_type": type(exc).__name__,
                }
            )
            return [], 0
        draft_eval = self.evaluator.evaluate_plan(query_data=query_data, plan=draft_itinerary)
        draft_failures = self.evaluator.failed_constraints(draft_eval)
        draft_feedback = self.evaluator.failure_feedback(draft_eval)
        step_trace.append(
            {
                "node": "self_refine_draft_validator",
                "final_pass": bool(draft_eval.final_pass),
                "validation_failures": draft_failures,
                "validation_feedback_count": len(draft_feedback),
                "estimated_cost": float(draft_eval.estimated_cost),
            }
        )
        if draft_eval.final_pass or not draft_feedback:
            step_trace.append(
                {
                    "node": "self_refine_skip_revision",
                    "reason": "draft_passed" if draft_eval.final_pass else "no_feedback",
                }
            )
            return draft_itinerary, 0

        compact_feedback = self._compact_feedback_items(draft_feedback, limit=6)
        critique_prompt = (
            "You are a strict TravelPlanner reviewer.\n"
            "Return compact valid JSON only with keys "
            '{"issues":["..."],"repair_instructions":["..."]}\n'
            "Return at most 4 issues and 4 repair_instructions. Keep each item under 18 words.\n"
            "Prioritize hard constraints and day-count consistency.\n"
            f"Query: {json.dumps(self.planner._compact_query_data(query_data), ensure_ascii=True)}\n"  # noqa: SLF001
            f"DraftPlan: {json.dumps(draft_itinerary, ensure_ascii=True)}\n"
            f"ValidationFeedback: {json.dumps(compact_feedback, ensure_ascii=True)}"
        )
        try:
            critique = self._call_schema(
                node_name="self_refine_critic",
                prompt=critique_prompt,
                response_schema=SelfRefineCritiqueOutput,
                step_trace=step_trace,
            )
        except Exception as exc:  # noqa: BLE001
            critique = self._fallback_self_refine_critique(compact_feedback)
            step_trace.append(
                {
                    "node": "self_refine_critic_fallback",
                    "reason": self._failure_reason_from_exception(exc),
                    "error_type": type(exc).__name__,
                    "issue_count": len(critique.issues),
                }
            )
        revise_prompt = (
            f"{base_prompt}\n\n"
            "CurrentDraft:\n"
            f"{json.dumps(draft_itinerary, ensure_ascii=True)}\n"
            "RepairInstructions:\n"
            f"{json.dumps(critique.repair_instructions or critique.issues, ensure_ascii=True)}\n"
            "Revise the draft minimally so that it satisfies the constraints."
        )
        try:
            final_itinerary = self._call_itinerary(
                node_name="self_refine_reviser",
                prompt=revise_prompt,
                query_data=query_data,
                search_payload=search_payload,
                step_trace=step_trace,
            )
        except Exception as exc:  # noqa: BLE001
            step_trace.append(
                {
                    "node": "self_refine_reviser_fallback",
                    "reason": "llm_call_failed",
                    "error_type": type(exc).__name__,
                    "fallback": "draft_itinerary",
                }
            )
            final_itinerary = draft_itinerary
        return final_itinerary, 1

    def _run_planner_executor(
        self,
        *,
        base_prompt: str,
        query_data: dict[str, Any],
        search_payload: dict[str, Any],
        step_trace: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        trip_days = max(1, int(query_data.get("days", 1) or 1))
        local_constraint = query_data.get("local_constraint") or {}
        if not isinstance(local_constraint, dict):
            local_constraint = {}
        budget = query_data.get("budget", "-")
        people_number = query_data.get("people_number", 1)
        planning_prompt = (
            "You are the central planner in a planner-executor architecture.\n"
            "Return compact valid JSON only with keys "
            '{"outbound_transportation":"...","return_transportation":"...",'
            '"accommodation":"...","days":[{"day":1,"breakfast":"...","lunch":"...","dinner":"...","attraction":"..."}]}\n'
            f"Return EXACTLY {trip_days} day entries, ordered day=1..{trip_days}. Every day must have a non-'-' breakfast, lunch, dinner, and attraction.\n"
            "Use canonical '<name>, <city>' strings. Never reuse the same restaurant across meals and days (each of the "
            f"{trip_days * 3} meal slots must be a distinct restaurant) and never reuse the same attraction across days.\n"
            "Choose transportation from the routing/search data when possible.\n"
            f"Hard constraints to respect: total budget ${budget} for {people_number} traveller(s); "
            f"cuisine={local_constraint.get('cuisine', 'any')}; "
            f"room_type={local_constraint.get('room type', 'any')}; "
            f"house_rule={local_constraint.get('house rule', 'any')}; "
            f"transportation={local_constraint.get('transportation', 'any')}.\n"
            "Commonsense constraints: stay within the sandbox of provided search data, respect minimum-nights stays, "
            "ensure restaurant/attraction diversity, and keep current_city consistent with transportation segments.\n"
            f"Query: {json.dumps(self.planner._compact_query_data(query_data), ensure_ascii=True)}\n"  # noqa: SLF001
            f"RoutingData: {json.dumps(self.planner._build_routing_context(query_data=self.planner._compact_query_data(query_data), search_payload=search_payload), ensure_ascii=True)}\n"  # noqa: SLF001
            f"SearchData: {json.dumps(search_payload, ensure_ascii=True)}"
        )
        try:
            blueprint = self._call_schema(
                node_name="central_planner",
                prompt=planning_prompt,
                response_schema=PlannerExecutorBlueprintOutput,
                step_trace=step_trace,
            )
        except (ValidationError, json.JSONDecodeError, ValueError) as exc:
            fallback_itinerary = self._call_itinerary(
                node_name="central_planner_fallback_itinerary",
                prompt=(
                    "Produce the shortest valid itinerary JSON possible. "
                    "Use '-' whenever a field can stay empty. Return only strict JSON.\n\n"
                    f"{base_prompt}"
                ),
                query_data=query_data,
                search_payload=search_payload,
                step_trace=step_trace,
            )
            blueprint = self._blueprint_from_itinerary(fallback_itinerary)
            step_trace.append(
                {
                    "node": "central_planner_fallback_blueprint",
                    "reason": "schema_parse_failed",
                    "error_type": type(exc).__name__,
                    "days_in_blueprint": len(blueprint.days),
                }
            )
        normalized_blueprint = self._normalize_planner_blueprint(
            blueprint=blueprint,
            query_data=query_data,
            search_payload=search_payload,
        )
        executor_prompt = (
            f"{base_prompt}\n\n"
            "CentralPlanBlueprint:\n"
            f"{json.dumps(normalized_blueprint, ensure_ascii=True)}\n"
            "The blueprint is a strong starting point produced by the central planner. "
            "Follow its high-level choices (transportation, accommodation, attractions/meals per day) when they satisfy the constraints, "
            "but you MUST fix any violation: fill every day with breakfast, lunch, dinner and attraction; keep all restaurants and attractions distinct; "
            "respect budget, cuisine, room and house-rule constraints; align current_city with transportation segments."
        )
        itinerary = self._call_itinerary(
            node_name="central_executor",
            prompt=executor_prompt,
            query_data=query_data,
            search_payload=search_payload,
            step_trace=step_trace,
        )
        return itinerary

    def _run_metagpt_sequential(
        self,
        *,
        base_prompt: str,
        query_data: dict[str, Any],
        search_payload: dict[str, Any],
        step_trace: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """MetaGPT-style pipeline: ProductManager → Architect → Engineer → Reviewer."""
        trip_days = max(1, int(query_data.get("days", 1) or 1))
        compact_query = self.planner._compact_query_data(query_data)  # noqa: SLF001
        local_constraint = query_data.get("local_constraint") or {}
        if not isinstance(local_constraint, dict):
            local_constraint = {}

        # Role 1 — ProductManager: extract requirements from the raw query.
        pm_prompt = (
            "ROLE: ProductManager. Read the travel request and enumerate the "
            "explicit and implicit constraints the final itinerary must satisfy.\n"
            "Return compact JSON only with keys "
            '{"hard_constraints":["..."],"commonsense_constraints":["..."],"success_criteria":["..."]}\n'
            "Each list must contain at most 6 short, imperative items (under 18 words).\n"
            f"Query: {json.dumps(compact_query, ensure_ascii=True)}\n"
            f"BudgetAndPeople: budget=${query_data.get('budget', '-')}, people={query_data.get('people_number', 1)}\n"
            f"LocalConstraints: {json.dumps(local_constraint, ensure_ascii=True)}"
        )
        try:
            requirements = self._call_schema(
                node_name="metagpt_product_manager",
                prompt=pm_prompt,
                response_schema=MetaGPTRequirementsOutput,
                step_trace=step_trace,
            )
        except Exception as exc:  # noqa: BLE001
            step_trace.append(
                {
                    "node": "metagpt_product_manager_fallback",
                    "reason": self._failure_reason_from_exception(exc),
                    "error_type": type(exc).__name__,
                }
            )
            requirements = MetaGPTRequirementsOutput(
                hard_constraints=[
                    f"Respect budget ${query_data.get('budget', '-')}",
                    f"Serve {query_data.get('people_number', 1)} traveller(s)",
                ],
                commonsense_constraints=[
                    "Diverse restaurants and attractions per day",
                    "Consistent current_city per transportation",
                ],
            )

        # Role 2 — Architect: produce macro plan (city sequence + per-day skeleton).
        architect_prompt = (
            "ROLE: Architect. Using the requirements, design the macro structure "
            f"of a {trip_days}-day itinerary.\n"
            "Return compact JSON only with keys "
            '{"accommodation_strategy":"...","city_sequence":["..."],'
            '"days":[{"day":1,"current_city":"...","transportation":"..."}]}\n'
            f"The days array MUST contain EXACTLY {trip_days} entries ordered day=1..{trip_days}.\n"
            "Use canonical '<name>, <city>' strings or '-'. Pick transportation from RoutingData when possible.\n"
            f"Query: {json.dumps(compact_query, ensure_ascii=True)}\n"
            f"Requirements: {json.dumps(requirements.model_dump(), ensure_ascii=True)}\n"
            f"RoutingData: {json.dumps(self.planner._build_routing_context(query_data=compact_query, search_payload=search_payload), ensure_ascii=True)}"  # noqa: SLF001
        )
        try:
            architecture = self._call_schema(
                node_name="metagpt_architect",
                prompt=architect_prompt,
                response_schema=MetaGPTArchitectureOutput,
                step_trace=step_trace,
            )
        except Exception as exc:  # noqa: BLE001
            step_trace.append(
                {
                    "node": "metagpt_architect_fallback",
                    "reason": self._failure_reason_from_exception(exc),
                    "error_type": type(exc).__name__,
                }
            )
            architecture = MetaGPTArchitectureOutput(
                accommodation_strategy="Single accommodation covering all nights",
                city_sequence=[str(query_data.get("dest", "-"))],
                days=[
                    MetaGPTArchitectureDayOutput(day=i + 1)
                    for i in range(trip_days)
                ],
            )

        # Role 3 — Engineer: produce the detailed itinerary.
        engineer_prompt = (
            "ROLE: Engineer. Produce the final detailed itinerary that satisfies "
            "the requirements and follows the architecture skeleton.\n"
            f"{base_prompt}\n\n"
            "Requirements:\n"
            f"{json.dumps(requirements.model_dump(), ensure_ascii=True)}\n"
            "ArchitecturePlan:\n"
            f"{json.dumps(architecture.model_dump(), ensure_ascii=True)}\n"
            f"You MUST return EXACTLY {trip_days} day entries, all fields populated (no '-' placeholders "
            "for breakfast/lunch/dinner/attraction)."
        )
        draft_itinerary = self._call_itinerary(
            node_name="metagpt_engineer",
            prompt=engineer_prompt,
            query_data=query_data,
            search_payload=search_payload,
            step_trace=step_trace,
        )

        # Role 4 — Reviewer: validate against official constraints and repair if needed.
        draft_eval = self.evaluator.evaluate_plan(
            query_data=query_data, plan=draft_itinerary
        )
        draft_failures = self.evaluator.failed_constraints(draft_eval)
        draft_feedback = self.evaluator.failure_feedback(draft_eval)
        step_trace.append(
            {
                "node": "metagpt_reviewer_validator",
                "final_pass": bool(draft_eval.final_pass),
                "validation_failures": draft_failures,
                "validation_feedback_count": len(draft_feedback),
                "estimated_cost": float(draft_eval.estimated_cost),
            }
        )
        if draft_eval.final_pass or not draft_feedback:
            step_trace.append(
                {
                    "node": "metagpt_reviewer_skip_revision",
                    "reason": "draft_passed" if draft_eval.final_pass else "no_feedback",
                }
            )
            return draft_itinerary

        compact_feedback = self._compact_feedback_items(draft_feedback, limit=6)
        reviewer_prompt = (
            "ROLE: Reviewer. The draft itinerary violates constraints. Repair it MINIMALLY "
            "while preserving the architecture's macro decisions.\n"
            f"{base_prompt}\n\n"
            "Requirements:\n"
            f"{json.dumps(requirements.model_dump(), ensure_ascii=True)}\n"
            "ArchitecturePlan:\n"
            f"{json.dumps(architecture.model_dump(), ensure_ascii=True)}\n"
            "DraftItinerary:\n"
            f"{json.dumps(draft_itinerary, ensure_ascii=True)}\n"
            "ValidationFailures:\n"
            f"{json.dumps(compact_feedback, ensure_ascii=True)}\n"
            f"Return EXACTLY {trip_days} day entries with all fields populated."
        )
        final_itinerary = self._call_itinerary(
            node_name="metagpt_reviewer",
            prompt=reviewer_prompt,
            query_data=query_data,
            search_payload=search_payload,
            step_trace=step_trace,
        )
        return final_itinerary

    def _build_search_payload(self, *, query_data: dict[str, Any]) -> dict[str, Any]:
        raw_payload: dict[str, Any] = {}
        self.planner._inject_default_search_payloads(  # noqa: SLF001 - deliberate reuse
            results=raw_payload,
            query_data=query_data,
            workspace=self.workspace,
        )
        return self.planner._compact_search_payload(  # noqa: SLF001 - deliberate reuse
            raw_payload,
            query_data=query_data,
        )

    def _call_itinerary(
        self,
        *,
        node_name: str,
        prompt: str,
        query_data: dict[str, Any],
        search_payload: dict[str, Any],
        step_trace: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        dynamic_max_tokens = self.planner._dynamic_max_response_tokens(  # noqa: SLF001
            query_data=query_data
        )
        response = self._call_llm(
            node_name=node_name,
            prompt=prompt,
            response_schema=TravelItineraryOutput,
            step_trace=step_trace,
            max_response_tokens=dynamic_max_tokens,
        )
        itinerary = self._parse_itinerary_response(response=response)
        parse_failure_reason = ""
        if not itinerary:
            raw_content = str(getattr(response, "content", "") or "").strip()
            parse_failure_reason = (
                "schema_parse_failed" if raw_content else "empty_llm_content"
            )
            recovery_response = self._call_llm(
                node_name=f"{node_name}_recovery",
                prompt=(
                    "Your previous response could not be parsed as a valid itinerary JSON. "
                    "Return ONLY strict JSON matching the schema, no preamble, no markdown fence.\n\n"
                    f"{prompt}"
                ),
                response_schema=TravelItineraryOutput,
                step_trace=step_trace,
                max_response_tokens=dynamic_max_tokens,
            )
            recovery_itinerary = self._parse_itinerary_response(
                response=recovery_response
            )
            if recovery_itinerary:
                itinerary = recovery_itinerary
                parse_failure_reason = "recovered_on_retry"
            if step_trace:
                step_trace[-1]["parse_failure_reason"] = parse_failure_reason
        elif step_trace:
            step_trace[-1]["parse_failure_reason"] = "none"
        itinerary = self.planner._normalize_itinerary(  # noqa: SLF001 - deliberate reuse
            itinerary=itinerary,
            query_data=query_data,
            search_payload=search_payload,
        )
        if step_trace:
            step_trace[-1]["days_returned"] = len(itinerary)
        return itinerary

    def _call_schema(
        self,
        *,
        node_name: str,
        prompt: str,
        response_schema: type[BaseModel],
        step_trace: list[dict[str, Any]],
    ) -> BaseModel:
        response = self._call_llm(
            node_name=node_name,
            prompt=prompt,
            response_schema=response_schema,
            step_trace=step_trace,
        )
        return self._parse_schema_response(
            response=response,
            response_schema=response_schema,
        )

    def _call_llm(
        self,
        *,
        node_name: str,
        prompt: str,
        response_schema: type[BaseModel],
        step_trace: list[dict[str, Any]],
        max_response_tokens: int | None = None,
    ) -> LLMResponse:
        last_error: Exception | None = None
        for attempt in range(self.node_retry_attempts):
            started_at = time.perf_counter()
            before_tokens = int(getattr(self.llm_client, "total_tokens_used", 0))
            before_cost = float(getattr(self.llm_client, "total_cost_usd", 0.0))
            try:
                call_kwargs: dict[str, Any] = {
                    "prompt": prompt,
                    "response_schema": response_schema,
                }
                if max_response_tokens is not None:
                    try:
                        response = self.llm_client.call(
                            **call_kwargs,
                            max_response_tokens=max_response_tokens,
                        )
                    except TypeError:
                        response = self.llm_client.call(**call_kwargs)
                else:
                    response = self.llm_client.call(**call_kwargs)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < self.node_retry_attempts - 1:
                    time.sleep(self.node_retry_backoff_seconds * (attempt + 1))
                    continue
                raise
            step_trace.append(
                {
                    "node": node_name,
                    "latency_ms": int((time.perf_counter() - started_at) * 1000),
                    "llm_model": str(getattr(response, "model", "")),
                    "tokens_used": int(getattr(self.llm_client, "total_tokens_used", 0)) - before_tokens,
                    "cost_used": round(float(getattr(self.llm_client, "total_cost_usd", 0.0)) - before_cost, 8),
                    "response_schema": response_schema.__name__,
                    "attempt": attempt + 1,
                }
            )
            return response
        assert last_error is not None
        raise last_error

    def _parse_itinerary_response(
        self,
        *,
        response: LLMResponse,
    ) -> list[dict[str, Any]]:
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, TravelItineraryOutput):
            return [day.model_dump() for day in parsed.plan]

        parsed_response = getattr(response, "parsed_response", None)
        if parsed_response is not None and isinstance(parsed_response.parsed, dict):
            try:
                output = TravelItineraryOutput.model_validate(parsed_response.parsed)
                return [day.model_dump() for day in output.plan]
            except ValidationError:
                pass

        raw_content = str(getattr(response, "content", "")).strip()
        if raw_content:
            try:
                return [
                    day.model_dump()
                    for day in TravelItineraryOutput.model_validate_json(
                        self._extract_json_candidate(raw_content) or raw_content
                    ).plan
                ]
            except (ValidationError, json.JSONDecodeError, ValueError):
                pass
        return self.planner._parse_itinerary(raw_content=raw_content, llm_client=self.llm_client)  # noqa: SLF001

    def _parse_schema_response(
        self,
        *,
        response: LLMResponse,
        response_schema: type[BaseModel],
    ) -> BaseModel:
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, response_schema):
            return parsed

        parsed_response = getattr(response, "parsed_response", None)
        if parsed_response is not None and isinstance(parsed_response.parsed, dict):
            return response_schema.model_validate(parsed_response.parsed)

        raw_content = str(getattr(response, "content", "")).strip()
        if not raw_content:
            raise ValueError(f"Empty response for {response_schema.__name__}")
        candidate = self._extract_json_candidate(raw_content) or raw_content
        return response_schema.model_validate_json(candidate)

    def _compact_feedback_items(self, feedback: list[str], *, limit: int) -> list[str]:
        compact: list[str] = []
        for item in feedback:
            text = " ".join(str(item).split())
            if not text:
                continue
            compact.append(text[:220])
            if len(compact) >= limit:
                break
        return compact

    def _failure_reason_from_exception(self, exc: Exception) -> str:
        if isinstance(exc, (ValidationError, json.JSONDecodeError, ValueError)):
            return "schema_parse_failed"
        return "llm_call_failed"

    def _fallback_self_refine_critique(
        self,
        feedback: list[str],
    ) -> SelfRefineCritiqueOutput:
        compact = self._compact_feedback_items(feedback, limit=4)
        repairs = [f"Fix: {item}"[:220] for item in compact]
        if not compact:
            compact = ["Repair the itinerary to satisfy the TravelPlanner constraints."]
            repairs = ["Revise the itinerary minimally so all constraints pass."]
        return SelfRefineCritiqueOutput(
            issues=compact,
            repair_instructions=repairs,
        )

    def _compact_planner_search_payload(
        self,
        search_payload: dict[str, Any],
    ) -> dict[str, Any]:
        limits = {
            "search_flights": 4,
            "search_flights_outbound": 4,
            "search_flights_return": 4,
            "search_ground_transport": 2,
            "search_ground_transport_outbound": 2,
            "search_ground_transport_return": 2,
            "search_hotels": 4,
            "search_restaurants": 6,
            "search_attractions": 6,
        }
        compact: dict[str, Any] = {}
        for key, value in search_payload.items():
            if isinstance(value, list):
                compact[key] = value[: limits.get(key, 4)]
            else:
                compact[key] = value
        return compact

    def _blueprint_from_itinerary(
        self,
        itinerary: list[dict[str, Any]],
    ) -> PlannerExecutorBlueprintOutput:
        if not itinerary:
            return PlannerExecutorBlueprintOutput()

        outbound = str(itinerary[0].get("transportation", "-") or "-")
        inbound = str(itinerary[-1].get("transportation", "-") or "-")
        accommodation = "-"
        days: list[PlannerExecutorDayOutput] = []

        for index, day in enumerate(itinerary, start=1):
            if accommodation == "-":
                candidate = str(day.get("accommodation", "-") or "-")
                if candidate != "-":
                    accommodation = candidate
            breakfast = str(day.get("breakfast", "-") or "-")
            lunch = str(day.get("lunch", "-") or "-")
            dinner = str(day.get("dinner", "-") or "-")
            attraction = str(day.get("attraction", "-") or "-")
            if all(value == "-" for value in (breakfast, lunch, dinner, attraction)):
                continue
            days.append(
                PlannerExecutorDayOutput(
                    day=index,
                    breakfast=breakfast,
                    lunch=lunch,
                    dinner=dinner,
                    attraction=attraction,
                )
            )

        return PlannerExecutorBlueprintOutput(
            outbound_transportation=outbound,
            return_transportation=inbound,
            accommodation=accommodation,
            days=days,
        )

    def _normalize_planner_blueprint(
        self,
        *,
        blueprint: PlannerExecutorBlueprintOutput,
        query_data: dict[str, Any],
        search_payload: dict[str, Any],
    ) -> dict[str, Any]:
        route_options = self.planner._build_route_option_catalog(search_payload)  # noqa: SLF001
        restaurant_candidates = self.planner._build_named_candidates(  # noqa: SLF001
            search_payload=search_payload,
            keys=("search_restaurants",),
            name_field="Name",
            city_field="City",
        )
        attraction_candidates = self.planner._build_named_candidates(  # noqa: SLF001
            search_payload=search_payload,
            keys=("search_attractions",),
            name_field="Name",
            city_field="City",
        )
        hotel_candidates = self.planner._build_named_candidates(  # noqa: SLF001
            search_payload=search_payload,
            keys=("search_hotels",),
            name_field="NAME",
            city_field="city",
        )
        origin = str(query_data.get("org", "")).strip()
        destination = str(query_data.get("dest", "")).strip()
        outbound_city = f"from {origin} to {destination}"
        return_city = f"from {destination} to {origin}"
        days = max(1, int(query_data.get("days", 1)))
        meals_by_day: dict[int, dict[str, str]] = {}
        for item in blueprint.days:
            meals_by_day[int(item.day)] = {
                "breakfast": self.planner._normalize_named_field(  # noqa: SLF001
                    raw_value=item.breakfast,
                    candidates=restaurant_candidates,
                ),
                "lunch": self.planner._normalize_named_field(  # noqa: SLF001
                    raw_value=item.lunch,
                    candidates=restaurant_candidates,
                ),
                "dinner": self.planner._normalize_named_field(  # noqa: SLF001
                    raw_value=item.dinner,
                    candidates=restaurant_candidates,
                ),
                "attraction": self.planner._normalize_attraction_field(  # noqa: SLF001
                    raw_value=item.attraction,
                    candidates=attraction_candidates,
                ),
            }
        normalized_days: list[dict[str, Any]] = []
        for day in range(1, days + 1):
            normalized_days.append(
                {
                    "day": day,
                    **meals_by_day.get(
                        day,
                        {
                            "breakfast": "-",
                            "lunch": "-",
                            "dinner": "-",
                            "attraction": "-",
                        },
                    ),
                }
            )
        return {
            "outbound_transportation": self.planner._normalize_transportation_field(  # noqa: SLF001
                raw_value=blueprint.outbound_transportation,
                current_city=outbound_city,
                route_options=route_options,
            ),
            "return_transportation": self.planner._normalize_transportation_field(  # noqa: SLF001
                raw_value=blueprint.return_transportation,
                current_city=return_city,
                route_options=route_options,
            ),
            "accommodation": self.planner._normalize_named_field(  # noqa: SLF001
                raw_value=blueprint.accommodation,
                candidates=hotel_candidates,
            ),
            "days": normalized_days,
        }

    def _coordination_overhead(
        self,
        *,
        mode: str,
        step_trace: list[dict[str, Any]],
    ) -> int:
        if mode in {"direct", "cot"}:
            return 1
        llm_steps = [
            item
            for item in step_trace
            if isinstance(item, dict) and str(item.get("node", "")).startswith(("self_refine_", "central_", "direct_", "cot_"))
        ]
        if mode == "self_refine":
            return sum(
                1
                for item in llm_steps
                if str(item.get("node", "")).startswith(("self_refine_draft", "self_refine_critic", "self_refine_reviser"))
            )
        if mode == "planner_executor":
            return sum(
                1
                for item in llm_steps
                if str(item.get("node", "")).startswith(("central_planner", "central_executor"))
            )
        if mode == "metagpt_sequential":
            return sum(
                1
                for item in step_trace
                if isinstance(item, dict)
                and str(item.get("node", "")).startswith("metagpt_")
                and "response_schema" in item
            )
        return len(step_trace)

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
                continue
            if char == "}":
                depth -= 1
                if depth == 0:
                    return raw_content[start : index + 1]
        return ""
