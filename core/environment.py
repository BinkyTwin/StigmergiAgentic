"""Runtime environment wrapper around marker store and guardrails."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .dependency import validate_dag
from .guardrails import GuardrailEngine
from .marker import Marker, StateMachine, utc_now_iso
from .marker_store import MarkerStore
from .reinforcement import propagate_backward, reinforce_on_success
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
        self.reinforcement_events = 0
        self.propagation_events = 0
        self.pruned_markers = 0

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
        reinforcement_cfg = dict(self.config.get("reinforcement", {}))
        reinforcement_enabled = bool(reinforcement_cfg.get("enabled", False))
        propagation_factor = float(reinforcement_cfg.get("propagation_factor", 0.0))
        lesson_threshold = float(reinforcement_cfg.get("lesson_threshold", 0.7))
        quality_score = self._extract_quality_score(result)

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

            if (
                reinforcement_enabled
                and saved.state in {"completed", "verified"}
                and (existing is None or existing.state != saved.state)
            ):
                reinforced = self.apply_reinforcement(
                    marker_id=saved.id,
                    quality_score=quality_score,
                    actor_id=agent_id,
                )
                if reinforced is not None:
                    persisted[-1] = reinforced

            if (
                saved.marker_type != "lesson"
                and saved.state in {"completed", "verified"}
                and (existing is None or existing.state != saved.state)
                and quality_score > lesson_threshold
            ):
                lesson_marker = self._build_lesson_marker(
                    source_marker=saved,
                    source_agent=agent_id,
                    quality_score=quality_score,
                )
                persisted.append(
                    self.store.upsert_marker(marker=lesson_marker, agent_id=agent_id)
                )

            if (
                reinforcement_enabled
                and propagation_factor > 0.0
                and saved.state in {"terminal", "verified", "completed"}
                and isinstance(saved.payload.get("depends_on"), list)
            ):
                updates = self._propagate_reinforcement(
                    completed_marker_id=saved.id,
                    propagation_factor=propagation_factor,
                    actor_id=agent_id,
                )
                self.propagation_events += len(updates)

        self.tokens_used += int(result.consumed_tokens)
        self.cost_used += float(result.cost_usd)
        self.enforce_budget()
        return persisted

    def maintain(self, current_tick: int) -> dict[str, Any]:
        """Apply lock maintenance and marker decay for one tick."""
        ttl = int(self.config.get("guardrails", {}).get("scope_lock_ttl", 3))
        released_locks = self.store.maintain_locks(current_tick=current_tick, ttl=ttl)
        decayed_markers = self.store.apply_decay(current_tick=current_tick, config=self.config)
        pruned = int(getattr(self.store, "last_decay_pruned_count", 0))
        self.pruned_markers += pruned
        return {
            "released_locks": released_locks,
            "decayed_markers": decayed_markers,
            "pruned_markers": pruned,
        }

    def apply_reinforcement(
        self,
        marker_id: str,
        quality_score: float,
        actor_id: str = "system_reinforcement",
    ) -> Marker | None:
        """Apply positive reinforcement to one marker intensity."""
        marker = self.store.get_marker(marker_id)
        if marker is None:
            return None

        reinforcement_cfg = dict(self.config.get("reinforcement", {}))
        rate = float(reinforcement_cfg.get("rate", 0.1))
        max_intensity = float(reinforcement_cfg.get("max_intensity", 1.0))

        updated = Marker.from_dict(marker.to_dict())
        updated.intensity = reinforce_on_success(
            marker=marker,
            reinforcement_rate=rate,
            quality_score=quality_score,
            max_intensity=max_intensity,
        )
        saved = self.store.upsert_marker(marker=updated, agent_id=actor_id)
        self.reinforcement_events += 1
        return saved

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

    def _extract_quality_score(self, result: ActionResult) -> float:
        raw = result.metadata.get("quality_score", 1.0)
        if isinstance(raw, dict):
            first = next(iter(raw.values()), 1.0)
            try:
                return float(first)
            except (TypeError, ValueError):
                return 1.0
        try:
            return float(raw)
        except (TypeError, ValueError):
            return 1.0

    def _propagate_reinforcement(
        self,
        *,
        completed_marker_id: str,
        propagation_factor: float,
        actor_id: str,
    ) -> list[Marker]:
        all_markers = self.store.query_markers()
        if not validate_dag(all_markers):
            return []

        reinforcement_cfg = dict(self.config.get("reinforcement", {}))
        rate = float(reinforcement_cfg.get("rate", 0.1))
        max_intensity = float(reinforcement_cfg.get("max_intensity", 1.0))

        updates: list[Marker] = []
        for marker_id, delta in propagate_backward(
            completed_marker_id=completed_marker_id,
            all_markers=all_markers,
            propagation_factor=propagation_factor,
        ):
            marker = self.store.get_marker(marker_id)
            if marker is None:
                continue
            updated = Marker.from_dict(marker.to_dict())
            updated.intensity = min(
                max_intensity,
                max(0.0, float(marker.intensity) + float(delta) * rate),
            )
            updates.append(self.store.upsert_marker(marker=updated, agent_id=actor_id))
        return updates

    def _build_lesson_marker(
        self,
        *,
        source_marker: Marker,
        source_agent: str,
        quality_score: float,
    ) -> Marker:
        timestamp = utc_now_iso()
        lesson_text = self._extract_lesson_text(source_marker)
        return Marker(
            id=f"lesson::{source_marker.id}",
            marker_type="lesson",
            target=source_marker.target,
            intensity=0.8,
            state="terminal",
            payload={
                "lesson": lesson_text,
                "source_marker": source_marker.id,
                "source_agent": source_agent,
                "source_state": source_marker.state,
                "quality_score": float(quality_score),
            },
            created_by=source_agent,
            created_at=timestamp,
            updated_by=source_agent,
            updated_at=timestamp,
            history=["created"],
        )

    def _extract_lesson_text(self, marker: Marker) -> str:
        thought = marker.payload.get("last_thought")
        if isinstance(thought, dict):
            analysis = str(thought.get("analysis", "")).strip()
            if analysis:
                return analysis

        task = str(marker.payload.get("task", "")).strip()
        if task:
            return f"Successful pattern: {task}"

        objective = str(marker.payload.get("objective", "")).strip()
        if objective:
            return f"Successful objective fragment: {objective}"

        return f"Transitioned successfully to {marker.state} on {marker.target}"
