"""Runtime environment wrapper around marker store and guardrails."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .guardrails import GuardrailEngine
from .marker import Marker, StateMachine, utc_now_iso
from .marker_store import MarkerStore
from .tool_registry import ActionResult


@dataclass(slots=True)
class EnvironmentSnapshot:
    """Read-only snapshot consumed by agents at one tick."""

    tick: int
    markers: list[Marker]
    by_type: dict[str, list[Marker]]


class Environment:
    """Composition root for store, guardrails, workspace, and state machine."""

    def __init__(
        self,
        *,
        store: MarkerStore,
        config: dict[str, Any],
        workspace: Any | None = None,
        guardrails: GuardrailEngine | None = None,
        state_machine: StateMachine | None = None,
    ) -> None:
        self.store = store
        self.config = config
        self.workspace = workspace
        self.guardrails = guardrails or store.guardrails
        self.state_machine = state_machine or StateMachine()

        self.tokens_used = 0
        self.cost_used = 0.0

    def snapshot(self, tick: int) -> EnvironmentSnapshot:
        """Build one immutable-like snapshot from current store state."""
        grouped = self.store.snapshot()
        copied_grouped: dict[str, list[Marker]] = {
            marker_type: [Marker.from_dict(marker.to_dict()) for marker in markers]
            for marker_type, markers in grouped.items()
        }
        flat_markers = [
            marker
            for markers in copied_grouped.values()
            for marker in markers
        ]
        flat_markers.sort(key=lambda marker: marker.id)
        return EnvironmentSnapshot(tick=tick, markers=flat_markers, by_type=copied_grouped)

    def acquire_lock(self, marker_id: str, agent_id: str, tick: int) -> bool:
        """Attempt to lock one marker for an agent."""
        return self.store.acquire_lock(marker_id=marker_id, agent_id=agent_id, tick=tick)

    def release_lock(self, marker_id: str, agent_id: str) -> bool:
        """Release one marker lock."""
        return self.store.release_lock(marker_id=marker_id, agent_id=agent_id)

    def apply_action_result(self, agent_id: str, result: ActionResult) -> list[Marker]:
        """Apply tool result to marker store and enforce guardrails."""
        persisted: list[Marker] = []
        for marker_update in result.marker_updates:
            marker_to_save = Marker.from_dict(marker_update.to_dict())
            existing = self.store.get_marker(marker_to_save.id)

            if existing is not None:
                if existing.state != marker_to_save.state:
                    self.state_machine.validate_transition(existing.state, marker_to_save.state)
                    transition = f"{existing.state}->{marker_to_save.state}"
                    history = list(existing.history)
                    history.append(transition)
                    marker_to_save.history = history
                else:
                    marker_to_save.history = list(existing.history)
                marker_to_save.created_by = existing.created_by
                marker_to_save.created_at = existing.created_at
            else:
                if not marker_to_save.created_by:
                    marker_to_save.created_by = agent_id
                if not marker_to_save.created_at:
                    marker_to_save.created_at = utc_now_iso()

            saved = self.store.upsert_marker(marker=marker_to_save, agent_id=agent_id)
            persisted.append(saved)

        self.tokens_used += int(result.consumed_tokens)
        self.cost_used += float(result.cost_usd)
        self.enforce_budget()
        return persisted

    def maintain(self, current_tick: int) -> dict[str, Any]:
        """Apply lock maintenance and marker decay for one tick."""
        ttl = int(self.config.get("guardrails", {}).get("scope_lock_ttl", 3))
        released_locks = self.store.maintain_locks(current_tick=current_tick, ttl=ttl)
        decayed_markers = self.store.apply_decay(current_tick=current_tick, config=self.config)
        return {
            "released_locks": released_locks,
            "decayed_markers": decayed_markers,
        }

    def enforce_budget(
        self,
        tokens_used: int | None = None,
        cost_used: float | None = None,
    ) -> None:
        """Validate token and cost budgets against configuration."""
        actual_tokens = self.tokens_used if tokens_used is None else int(tokens_used)
        actual_cost = self.cost_used if cost_used is None else float(cost_used)

        llm_cfg = self.config.get("llm", {})
        max_tokens_total = int(llm_cfg.get("max_tokens_total", 0))
        max_budget_usd = float(llm_cfg.get("max_budget_usd", 0.0))

        self.guardrails.enforce_budget(
            tokens_used=actual_tokens,
            max_tokens=max_tokens_total,
            cost_used=actual_cost,
            max_budget_usd=max_budget_usd,
        )
