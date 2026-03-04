"""Parallel tick-based orchestrator for stigmergic agents."""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from .agent import StigmergicAgent
from .environment import Environment, EnvironmentSnapshot
from .guardrails import BudgetExceededError
from .tool_registry import ActionResult, Decision


TERMINAL_STATES = {"terminal", "skipped", "escalated"}


@dataclass(slots=True)
class TickRow:
    """Execution telemetry for one orchestrator tick."""

    tick: int
    decisions: dict[str, str | None]
    executed_actions: int
    lock_conflicts: int
    active_agents: int
    pressures: dict[str, float]
    actions_by_type: dict[str, int]
    terminal_progress: float
    maintenance: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OrchestratorResult:
    """Final in-memory execution result for one run."""

    stop_reason: str
    total_ticks: int
    tick_rows: list[TickRow]
    final_snapshot: EnvironmentSnapshot
    session_id: str | None = None


class Orchestrator:
    """Coordinate perceive/decide/execute/deposit over multiple agents."""

    def __init__(
        self,
        *,
        environment: Environment,
        agents: list[StigmergicAgent],
        config: dict[str, Any],
        llm_client: Any | None = None,
        session_id: str | None = None,
    ) -> None:
        self.environment = environment
        self.agents = agents
        self.config = config
        self.llm_client = llm_client
        self.session_id = session_id

    async def run(self) -> OrchestratorResult:
        """Run orchestrator until one stop condition is met."""
        orchestrator_cfg = self.config.get("orchestrator", {})
        max_ticks = int(orchestrator_cfg.get("max_ticks", 50))
        idle_cycles_to_stop = int(orchestrator_cfg.get("idle_cycles_to_stop", 2))
        parallel = bool(orchestrator_cfg.get("parallel", True))

        idle_cycles = 0
        stop_reason = "max_ticks"
        tick_rows: list[TickRow] = []
        final_snapshot = self.environment.snapshot(tick=0)

        for tick in range(max_ticks):
            maintenance = self.environment.maintain(current_tick=tick)
            pre_snapshot = self.environment.snapshot(tick=tick)

            decisions_by_agent = await self._collect_decisions(
                snapshot=pre_snapshot,
                parallel=parallel,
            )

            lock_conflicts = 0
            winners: list[tuple[StigmergicAgent, Decision]] = []
            for agent, decision in decisions_by_agent:
                if decision is None:
                    continue
                acquired = self.environment.acquire_lock(
                    marker_id=decision.marker_id,
                    agent_id=agent.agent_id,
                    tick=tick,
                )
                if acquired:
                    winners.append((agent, decision))
                else:
                    lock_conflicts += 1

            try:
                execution_results = await self._execute_winners(
                    winners=winners,
                    parallel=parallel,
                )
            except BudgetExceededError:
                stop_reason = "budget_exhausted"
                execution_results = []

            executed_actions = sum(
                1
                for result in execution_results
                if result is not None and not bool(result.metadata.get("failed", False))
            )

            if executed_actions == 0:
                idle_cycles += 1
            else:
                idle_cycles = 0

            post_snapshot = self.environment.snapshot(tick=tick)
            final_snapshot = post_snapshot

            actions_by_type = dict(Counter(decision.action_type for _, decision in winners))
            pressures = self._aggregate_pressures(decisions_by_agent)
            decisions_payload = {
                agent.agent_id: (
                    None if decision is None else decision.action_type
                )
                for agent, decision in decisions_by_agent
            }
            tick_rows.append(
                TickRow(
                    tick=tick,
                    decisions=decisions_payload,
                    executed_actions=executed_actions,
                    lock_conflicts=lock_conflicts,
                    active_agents=len(winners),
                    pressures=pressures,
                    actions_by_type=actions_by_type,
                    terminal_progress=self._terminal_progress(post_snapshot),
                    maintenance=maintenance,
                )
            )

            if stop_reason == "budget_exhausted":
                break

            try:
                self.environment.enforce_budget()
            except BudgetExceededError:
                stop_reason = "budget_exhausted"
                break

            if self._all_terminal(post_snapshot):
                stop_reason = "all_terminal"
                break

            if idle_cycles >= idle_cycles_to_stop:
                stop_reason = "idle_cycles"
                break

        return OrchestratorResult(
            stop_reason=stop_reason,
            total_ticks=len(tick_rows),
            tick_rows=tick_rows,
            final_snapshot=final_snapshot,
            session_id=self.session_id,
        )

    def run_sync(self) -> OrchestratorResult:
        """Sync wrapper used by unit tests and non-async callers."""
        return asyncio.run(self.run())

    async def _collect_decisions(
        self,
        *,
        snapshot: EnvironmentSnapshot,
        parallel: bool,
    ) -> list[tuple[StigmergicAgent, Decision | None]]:
        if not self.agents:
            return []

        if parallel:
            resolved = await asyncio.gather(
                *(agent.perceive_and_decide(snapshot) for agent in self.agents)
            )
        else:
            resolved = []
            for agent in self.agents:
                resolved.append(await agent.perceive_and_decide(snapshot))

        return list(zip(self.agents, resolved))

    async def _execute_winners(
        self,
        *,
        winners: list[tuple[StigmergicAgent, Decision]],
        parallel: bool,
    ) -> list[ActionResult]:
        if not winners:
            return []

        if parallel:
            results = await asyncio.gather(
                *(self._execute_one(agent=agent, decision=decision) for agent, decision in winners)
            )
            return list(results)

        results: list[ActionResult] = []
        for agent, decision in winners:
            results.append(await self._execute_one(agent=agent, decision=decision))
        return results

    async def _execute_one(
        self,
        *,
        agent: StigmergicAgent,
        decision: Decision,
    ) -> ActionResult:
        try:
            return await agent.execute(
                decision=decision,
                environment=self.environment,
                llm_client=self.llm_client,
            )
        finally:
            self.environment.release_lock(
                marker_id=decision.marker_id,
                agent_id=agent.agent_id,
            )

    def _aggregate_pressures(
        self,
        decisions_by_agent: list[tuple[StigmergicAgent, Decision | None]],
    ) -> dict[str, float]:
        pressure_accumulator: dict[str, float] = {}
        decision_count = 0

        for _, decision in decisions_by_agent:
            if decision is None:
                continue
            decision_count += 1
            for action_type, value in decision.pressures.items():
                pressure_accumulator[action_type] = (
                    pressure_accumulator.get(action_type, 0.0) + float(value)
                )

        if decision_count == 0:
            return {}

        return {
            action_type: value / float(decision_count)
            for action_type, value in pressure_accumulator.items()
        }

    def _all_terminal(self, snapshot: EnvironmentSnapshot) -> bool:
        if not snapshot.markers:
            return False
        return all(marker.state in TERMINAL_STATES for marker in snapshot.markers)

    def _terminal_progress(self, snapshot: EnvironmentSnapshot) -> float:
        if not snapshot.markers:
            return 0.0
        terminal_count = sum(1 for marker in snapshot.markers if marker.state in TERMINAL_STATES)
        return float(terminal_count) / float(len(snapshot.markers))
