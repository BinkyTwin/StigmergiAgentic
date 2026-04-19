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
    control: dict[str, Any] = field(default_factory=dict)


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
        self._recovery_state: dict[str, Any] = {
            "active_until_tick": -1,
            "last_activation_tick": None,
            "activation_count": 0,
        }
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
            base_snapshot = self.environment.snapshot(tick=tick)
            control_state = self._build_control_state(
                tick=tick,
                tick_rows=tick_rows,
                snapshot=base_snapshot,
                idle_cycles=idle_cycles,
            )
            pre_snapshot = (
                self.environment.snapshot(tick=tick, control=control_state)
                if self._snapshot_requires_control_refresh(control_state)
                else base_snapshot
            )

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
                control=self._control_row_payload(control_state, decisions_by_agent),
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

            effective_idle_limit = int(
                control_state.get("dynamic_idle_limit", idle_cycles_to_stop)
            )
            if idle_cycles >= effective_idle_limit:
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

    def _build_control_state(
        self,
        *,
        tick: int,
        tick_rows: list[TickRow],
        snapshot: EnvironmentSnapshot,
        idle_cycles: int,
    ) -> dict[str, Any]:
        recovery_cfg = self._recovery_controller_config()
        recovery_active = int(self._recovery_state.get("active_until_tick", -1)) >= int(tick)
        activation_signal: dict[str, Any] = {}

        if bool(recovery_cfg.get("enabled", False)) and not recovery_active:
            activation_signal = self._maybe_activate_recovery(
                tick=tick,
                tick_rows=tick_rows,
                snapshot=snapshot,
            )
            recovery_active = int(self._recovery_state.get("active_until_tick", -1)) >= int(tick)

        recovery_payload = {
            "active": recovery_active,
            "activated_this_tick": bool(activation_signal),
            "temperature_boost": (
                float(recovery_cfg.get("temperature_boost", 0.0))
                if recovery_active
                else 0.0
            ),
            "inhibition_relief": (
                float(recovery_cfg.get("inhibition_relief", 0.0))
                if recovery_active
                else 0.0
            ),
            "last_activation_tick": self._recovery_state.get("last_activation_tick"),
            "activation_count": int(self._recovery_state.get("activation_count", 0)),
            "signal": activation_signal,
        }
        selection_temperature_override = None
        if recovery_active:
            base_temperature = float(
                self.config.get("agents", {}).get("selection_temperature", 0.1)
            )
            selection_temperature_override = max(
                0.0,
                base_temperature + float(recovery_cfg.get("temperature_boost", 0.0)),
            )

        return {
            "recovery": recovery_payload,
            "selection_temperature_override": selection_temperature_override,
            "dynamic_idle_limit": self._dynamic_idle_limit(snapshot),
            "idle_cycles": int(idle_cycles),
        }

    def _snapshot_requires_control_refresh(self, control_state: dict[str, Any]) -> bool:
        recovery_cfg = dict(control_state.get("recovery", {}))
        return bool(recovery_cfg.get("active", False))

    def _control_row_payload(
        self,
        control_state: dict[str, Any],
        decisions_by_agent: list[tuple[StigmergicAgent, Decision | None]],
    ) -> dict[str, Any]:
        recovery_cfg = dict(control_state.get("recovery", {}))
        return {
            "recovery": recovery_cfg,
            "dynamic_idle_limit": int(control_state.get("dynamic_idle_limit", 0)),
            "stickiness_activations": sum(
                1
                for _, decision in decisions_by_agent
                if decision is not None and bool(getattr(decision, "stickiness_applied", False))
            ),
            "recovery_target_preferences": sum(
                1
                for _, decision in decisions_by_agent
                if decision is not None
                and bool(getattr(decision, "recovery_preference_applied", False))
            ),
        }

    def _recovery_controller_config(self) -> dict[str, Any]:
        orchestrator_cfg = dict(self.config.get("orchestrator", {}))
        return dict(orchestrator_cfg.get("recovery_controller", {}))

    def _dynamic_idle_limit(self, snapshot: EnvironmentSnapshot) -> int:
        orchestrator_cfg = dict(self.config.get("orchestrator", {}))
        base_limit = int(orchestrator_cfg.get("idle_cycles_to_stop", 0))
        recovery_cfg = self._recovery_controller_config()
        dynamic_idle = dict(recovery_cfg.get("dynamic_idle", {}))
        if not bool(recovery_cfg.get("enabled", False)) or not bool(
            dynamic_idle.get("enabled", False)
        ):
            return base_limit

        pending_count = sum(
            1 for marker in snapshot.markers if marker.state not in TERMINAL_STATES
        )
        if pending_count <= 0:
            return base_limit

        node_per_idle_cycle = max(1, int(dynamic_idle.get("node_per_idle_cycle", 6)))
        max_extra = max(0, int(dynamic_idle.get("max_extra_idle_cycles", 0)))
        extra_idle = min(max_extra, pending_count // node_per_idle_cycle)
        return base_limit + extra_idle

    def _maybe_activate_recovery(
        self,
        *,
        tick: int,
        tick_rows: list[TickRow],
        snapshot: EnvironmentSnapshot,
    ) -> dict[str, Any]:
        recovery_cfg = self._recovery_controller_config()
        stagnation_ticks = max(1, int(recovery_cfg.get("stagnation_ticks", 5)))
        if len(tick_rows) < stagnation_ticks:
            return {}

        last_activation_tick = self._recovery_state.get("last_activation_tick")
        cooldown_ticks = max(0, int(recovery_cfg.get("recovery_cooldown_ticks", 0)))
        if isinstance(last_activation_tick, int) and int(tick) - last_activation_tick < cooldown_ticks:
            return {}

        if not self._pending_work_remaining(snapshot):
            return {}
        if not self._no_recent_terminal_progress(tick_rows=tick_rows, window=stagnation_ticks):
            return {}

        recent_contention = self._recent_contention_rate(
            tick=tick,
            window=stagnation_ticks,
        )
        threshold = float(recovery_cfg.get("contention_threshold", 0.6))
        if recent_contention < threshold:
            return {}

        duration = max(1, int(recovery_cfg.get("temperature_boost_duration", 1)))
        self._recovery_state["active_until_tick"] = int(tick) + duration - 1
        self._recovery_state["last_activation_tick"] = int(tick)
        self._recovery_state["activation_count"] = (
            int(self._recovery_state.get("activation_count", 0)) + 1
        )
        signal = {
            "recent_contention_rate": recent_contention,
            "contention_threshold": threshold,
            "stagnation_ticks": stagnation_ticks,
            "pending_markers": sum(
                1 for marker in snapshot.markers if marker.state not in TERMINAL_STATES
            ),
        }
        self._audit_recovery_activation(tick=tick, signal=signal)
        return signal

    def _recent_contention_rate(self, *, tick: int, window: int) -> float:
        since_tick = max(0, int(tick) - max(1, int(window)))
        stats = self.environment.store.lock_stats_snapshot(since_tick=since_tick)
        attempts = sum(int(row.get("attempts", 0)) for row in stats.values())
        conflicts = sum(int(row.get("conflicts", 0)) for row in stats.values())
        if attempts <= 0:
            return 0.0
        return float(conflicts) / float(attempts)

    def _no_recent_terminal_progress(
        self,
        *,
        tick_rows: list[TickRow],
        window: int,
    ) -> bool:
        if not tick_rows:
            return False
        recent_rows = tick_rows[-max(1, int(window)) :]
        start_progress = float(recent_rows[0].terminal_progress)
        end_progress = float(recent_rows[-1].terminal_progress)
        return end_progress <= start_progress

    def _pending_work_remaining(self, snapshot: EnvironmentSnapshot) -> bool:
        return any(marker.state not in TERMINAL_STATES for marker in snapshot.markers)

    def _audit_recovery_activation(
        self,
        *,
        tick: int,
        signal: dict[str, Any],
    ) -> None:
        recovery_cfg = self._recovery_controller_config()
        self.environment.store.audit_log.append(
            AuditEvent(
                timestamp=utc_timestamp(),
                agent_id="system_recovery",
                action="recovery_activation",
                marker_id="runtime_config",
                marker_type="system",
                target="recovery_controller",
                before={"signal": signal},
                after={
                    "selection_temperature_override": (
                        float(self.config.get("agents", {}).get("selection_temperature", 0.1))
                        + float(recovery_cfg.get("temperature_boost", 0.0))
                    ),
                    "inhibition_relief": float(recovery_cfg.get("inhibition_relief", 0.0)),
                    "duration_ticks": int(recovery_cfg.get("temperature_boost_duration", 1)),
                },
                tick=int(tick),
            )
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
            ordered_attempts: list[tuple[StigmergicAgent, Decision]] = []
            if winner is not None:
                ordered_attempts.append(winner)
            ordered_attempts.extend(
                contender
                for contender in contenders
                if winner is None or contender[0].agent_id != winner[0].agent_id
            )

            attempted_agent_ids: set[str] = set()
            actual_winner_id: str | None = None
            for agent, decision in ordered_attempts:
                attempted_agent_ids.add(agent.agent_id)
                if self.environment.acquire_lock(
                    marker_id=decision.marker_id,
                    agent_id=agent.agent_id,
                    tick=tick,
                ):
                    winners.append((agent, decision))
                    actual_winner_id = agent.agent_id
                    break

            if actual_winner_id is not None:
                for agent, decision in contenders:
                    if agent.agent_id == actual_winner_id or agent.agent_id in attempted_agent_ids:
                        continue
                    self.environment.store.record_lock_attempt(
                        marker_id=decision.marker_id,
                        agent_id=agent.agent_id,
                        tick=tick,
                        acquired=False,
                    )
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
