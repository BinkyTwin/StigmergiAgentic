"""Parallel tick-based orchestrator for stigmergic agents."""

from __future__ import annotations

import asyncio
from collections import Counter, defaultdict
from dataclasses import dataclass, field
import random
from typing import Any

from .audit import AuditEvent, utc_timestamp
from .agent import StigmergicAgent
from .emergence import compute_adaptations, compute_emergence_metrics
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
    emergence: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OrchestratorResult:
    """Final in-memory execution result for one run."""

    stop_reason: str
    total_ticks: int
    tick_rows: list[TickRow]
    final_snapshot: EnvironmentSnapshot
    session_id: str | None = None
    emergence_summary: dict[str, Any] = field(default_factory=dict)


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
        self._rng = random.Random(0)
        self._bind_agent_callbacks()

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
        emergence_summary: dict[str, Any] = {}

        for tick in range(max_ticks):
            maintenance = self.environment.maintain(current_tick=tick)
            pre_snapshot = self.environment.snapshot(tick=tick)

            decisions_by_agent = await self._collect_decisions(
                snapshot=pre_snapshot,
                parallel=parallel,
            )
            winners, lock_conflicts = self._resolve_winners(
                decisions_by_agent=decisions_by_agent,
                tick=tick,
            )

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
            for agent in self.agents:
                if hasattr(agent, "memory") and hasattr(agent.memory, "decay_all"):
                    agent.memory.decay_all()

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
            tick_emergence = self._tick_emergence_payload(
                decisions=decisions_payload,
                active_agents=len(winners),
                lock_conflicts=lock_conflicts,
            )
            row = TickRow(
                tick=tick,
                decisions=decisions_payload,
                executed_actions=executed_actions,
                lock_conflicts=lock_conflicts,
                active_agents=len(winners),
                pressures=pressures,
                actions_by_type=actions_by_type,
                terminal_progress=self._terminal_progress(post_snapshot),
                maintenance=maintenance,
                emergence=tick_emergence,
            )
            tick_rows.append(row)
            adaptations = self._maybe_apply_feedback(
                tick=tick,
                tick_rows=tick_rows,
            )
            if adaptations:
                row.maintenance["adaptations"] = dict(adaptations)

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

        emergence_cfg = dict(self.config.get("emergence", {}))
        if bool(emergence_cfg.get("enabled", False)):
            selected_metrics = emergence_cfg.get("metrics", [])
            computed = compute_emergence_metrics(
                tick_rows=tick_rows,
                total_agents=len(self.agents),
                audit_log_path=getattr(self.environment.store.audit_log, "path", None),
            )
            if isinstance(selected_metrics, list) and selected_metrics:
                emergence_summary = {
                    metric: computed[metric]
                    for metric in selected_metrics
                    if metric in computed
                }
            else:
                emergence_summary = computed

        return OrchestratorResult(
            stop_reason=stop_reason,
            total_ticks=len(tick_rows),
            tick_rows=tick_rows,
            final_snapshot=final_snapshot,
            session_id=self.session_id,
            emergence_summary=emergence_summary,
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

    def _bind_agent_callbacks(self) -> None:
        for agent in self.agents:
            if hasattr(agent, "bind_on_perceive"):
                agent.bind_on_perceive(self._record_agent_reads)

    def _record_agent_reads(
        self,
        agent_id: str,
        markers: list[Any],
        tick: int,
    ) -> None:
        marker_ids = {
            str(getattr(marker, "id", "")).strip()
            for marker in markers
            if str(getattr(marker, "id", "")).strip()
        }
        for marker_id in marker_ids:
            self.environment.store.record_read(
                marker_id=marker_id,
                agent_id=agent_id,
                tick=int(tick),
            )

    def _resolve_winners(
        self,
        *,
        decisions_by_agent: list[tuple[StigmergicAgent, Decision | None]],
        tick: int,
    ) -> tuple[list[tuple[StigmergicAgent, Decision]], int]:
        emergent_cfg = dict(
            self.config.get("orchestrator", {}).get("emergent_resolution", {})
        )
        if not bool(emergent_cfg.get("enabled", False)):
            return self._resolve_winners_sequential(
                decisions_by_agent=decisions_by_agent,
                tick=tick,
            )
        return self._resolve_winners_emergent(
            decisions_by_agent=decisions_by_agent,
            tick=tick,
            base_probability=float(emergent_cfg.get("base_probability", 0.1)),
        )

    def _resolve_winners_sequential(
        self,
        *,
        decisions_by_agent: list[tuple[StigmergicAgent, Decision | None]],
        tick: int,
    ) -> tuple[list[tuple[StigmergicAgent, Decision]], int]:
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
        return winners, lock_conflicts

    def _resolve_winners_emergent(
        self,
        *,
        decisions_by_agent: list[tuple[StigmergicAgent, Decision | None]],
        tick: int,
        base_probability: float,
    ) -> tuple[list[tuple[StigmergicAgent, Decision]], int]:
        groups: dict[str, list[tuple[StigmergicAgent, Decision]]] = defaultdict(list)
        marker_order: list[str] = []
        for agent, decision in decisions_by_agent:
            if decision is None:
                continue
            if decision.marker_id not in groups:
                marker_order.append(decision.marker_id)
            groups[decision.marker_id].append((agent, decision))

        winners: list[tuple[StigmergicAgent, Decision]] = []
        lock_conflicts = 0
        for marker_id in marker_order:
            contenders = groups.get(marker_id, [])
            if not contenders:
                continue
            if len(contenders) == 1:
                agent, decision = contenders[0]
                if self.environment.acquire_lock(
                    marker_id=decision.marker_id,
                    agent_id=agent.agent_id,
                    tick=tick,
                ):
                    winners.append((agent, decision))
                else:
                    lock_conflicts += 1
                continue

            lock_conflicts += len(contenders) - 1
            winner = self._weighted_contender_choice(
                contenders=contenders,
                base_probability=base_probability,
            )
            if winner is not None:
                winner_agent, winner_decision = winner
                if self.environment.acquire_lock(
                    marker_id=winner_decision.marker_id,
                    agent_id=winner_agent.agent_id,
                    tick=tick,
                ):
                    winners.append((winner_agent, winner_decision))
                    continue

            for agent, decision in contenders:
                if winner is not None and agent.agent_id == winner[0].agent_id:
                    continue
                if self.environment.acquire_lock(
                    marker_id=decision.marker_id,
                    agent_id=agent.agent_id,
                    tick=tick,
                ):
                    winners.append((agent, decision))
                    break
        return winners, lock_conflicts

    def _weighted_contender_choice(
        self,
        *,
        contenders: list[tuple[StigmergicAgent, Decision]],
        base_probability: float,
    ) -> tuple[StigmergicAgent, Decision] | None:
        if not contenders:
            return None

        weights = [
            max(0.0, float(getattr(decision, "selection_affinity", 0.0)))
            + max(0.0, float(base_probability))
            for _, decision in contenders
        ]
        total = sum(weights)
        if total <= 0.0:
            return contenders[0]

        draw = self._rng.random() * total
        cumulative = 0.0
        for contender, weight in zip(contenders, weights):
            cumulative += weight
            if draw <= cumulative:
                return contender
        return contenders[-1]

    def _maybe_apply_feedback(
        self,
        *,
        tick: int,
        tick_rows: list[TickRow],
    ) -> dict[str, float]:
        feedback_cfg = dict(self.config.get("emergence", {}).get("feedback_loop", {}))
        if not bool(feedback_cfg.get("enabled", False)):
            return {}

        interval_ticks = max(1, int(feedback_cfg.get("interval_ticks", 5)))
        if (int(tick) + 1) % interval_ticks != 0:
            return {}

        metrics = compute_emergence_metrics(
            tick_rows=tick_rows,
            total_agents=len(self.agents),
            audit_log_path=getattr(self.environment.store.audit_log, "path", None),
        )
        adaptations = compute_adaptations(metrics, self.config)
        if not adaptations:
            return {}

        before = {path: self._get_config_value(path) for path in adaptations}
        self._apply_adaptations(adaptations)
        after = {path: self._get_config_value(path) for path in adaptations}
        self._audit_adaptations(
            tick=tick,
            before=before,
            after=after,
            metrics=metrics,
        )
        return after

    def _apply_adaptations(self, adaptations: dict[str, float]) -> None:
        for path, value in adaptations.items():
            self._set_config_value(path, value)

    def _set_config_value(self, path: str, value: float) -> None:
        keys = [part for part in str(path).split(".") if part]
        if not keys:
            return
        cursor: Any = self.config
        for key in keys[:-1]:
            next_value = cursor.get(key)
            if not isinstance(next_value, dict):
                next_value = {}
                cursor[key] = next_value
            cursor = next_value
        cursor[keys[-1]] = value

    def _get_config_value(self, path: str) -> Any:
        cursor: Any = self.config
        for key in [part for part in str(path).split(".") if part]:
            if not isinstance(cursor, dict) or key not in cursor:
                return None
            cursor = cursor[key]
        return cursor

    def _audit_adaptations(
        self,
        *,
        tick: int,
        before: dict[str, Any],
        after: dict[str, Any],
        metrics: dict[str, Any],
    ) -> None:
        self.environment.store.audit_log.append(
            AuditEvent(
                timestamp=utc_timestamp(),
                agent_id="system_emergence",
                action="adaptation",
                marker_id="runtime_config",
                marker_type="system",
                target="feedback_loop",
                before={"config": before, "metrics": metrics},
                after={"config": after, "metrics": metrics},
                tick=int(tick),
            )
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

    def _tick_emergence_payload(
        self,
        *,
        decisions: dict[str, str | None],
        active_agents: int,
        lock_conflicts: int,
    ) -> dict[str, Any]:
        lock_attempts = sum(1 for action in decisions.values() if action is not None)
        lock_contention_rate = (
            0.0
            if lock_attempts == 0
            else float(lock_conflicts) / float(lock_attempts)
        )
        total_agents = len(self.agents)
        parallel_utilization = (
            0.0
            if total_agents <= 0
            else float(active_agents) / float(total_agents)
        )
        return {
            "lock_contention_rate": lock_contention_rate,
            "parallel_utilization": parallel_utilization,
        }
