"""Runtime environment wrapper around marker store and guardrails."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .decay import effective_intensity
from .dependency import validate_dag
from .guardrails import GuardrailEngine
from .marker import Marker, StateMachine, utc_now_iso
from .marker_store import MarkerStore
from .reinforcement import propagate_backward, reinforce_on_success
from .tool_registry import (
    ActionResult,
    ValidationResult,
    build_repair_marker_id,
)


@dataclass(slots=True)
class EnvironmentSnapshot:
    """Read-only snapshot consumed by agents at one tick."""

    tick: int
    markers: list[Marker]
    by_type: dict[str, list[Marker]]
    control: dict[str, Any] = field(default_factory=dict)
    skills: list[Marker] = field(default_factory=list)


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
        skills_store: MarkerStore | None = None,
        adapter_name: str = "generic",
    ) -> None:
        self.store = store
        self.config = config
        self.workspace = workspace
        self.guardrails = guardrails or store.guardrails
        self.state_machine = state_machine or StateMachine()
        self.skills_store = skills_store
        self.adapter_name = str(adapter_name).strip() or "generic"

        self.tokens_used = 0
        self.cost_used = 0.0
        self.reinforcement_events = 0
        self.propagation_events = 0
        self.pruned_markers = 0
        self.skills_promoted = 0

    def snapshot(
        self,
        tick: int,
        control: dict[str, Any] | None = None,
    ) -> EnvironmentSnapshot:
        """Build one immutable-like snapshot from current store state."""
        runtime_control = dict(control or {})
        grouped = self.store.snapshot()
        lock_stats_by_marker = self.store.lock_stats_snapshot()
        copied_grouped: dict[str, list[Marker]] = {
            marker_type: [Marker.from_dict(marker.to_dict()) for marker in markers]
            for marker_type, markers in grouped.items()
        }
        markers_cfg = dict(self.config.get("markers", {}))
        time_decay_cfg = dict(markers_cfg.get("time_decay", {}))
        if bool(time_decay_cfg.get("enabled", False)):
            decay_type = str(markers_cfg.get("decay_type", "exponential"))
            default_decay_rate = float(
                markers_cfg.get("default_decay_rate", markers_cfg.get("decay_rate", 0.05))
            )
            decay_rates_by_type = dict(markers_cfg.get("decay_rates_by_type", {}))
            clamp_raw = markers_cfg.get("intensity_clamp", [0.1, 1.0])
            clamp = (float(clamp_raw[0]), float(clamp_raw[1]))
            decay_period_seconds = float(
                time_decay_cfg.get("decay_period_seconds", 60.0)
            )
            now = utc_now_iso()

            for markers in copied_grouped.values():
                for marker in markers:
                    marker_decay_rate = float(
                        decay_rates_by_type.get(marker.marker_type, default_decay_rate)
                    )
                    marker.intensity = effective_intensity(
                        stored_intensity=marker.intensity,
                        last_active_at=marker.last_active_at or marker.updated_at,
                        now=now,
                        decay_type=decay_type,
                        decay_rate=marker_decay_rate,
                        decay_period_seconds=decay_period_seconds,
                        clamp=clamp,
                    )
        recovery_cfg = dict(runtime_control.get("recovery", {}))
        recovery_active = bool(recovery_cfg.get("active", False))
        inhibition_relief = (
            max(0.0, float(recovery_cfg.get("inhibition_relief", 0.0)))
            if recovery_active
            else 0.0
        )
        flat_markers = [
            marker
            for markers in copied_grouped.values()
            for marker in markers
        ]
        for marker in flat_markers:
            payload = dict(marker.payload)
            stats = dict(lock_stats_by_marker.get(marker.id, {}))
            last_conflict_tick = stats.get("last_conflict_tick")
            ticks_since_last_conflict = None
            if isinstance(last_conflict_tick, int):
                ticks_since_last_conflict = max(0, int(tick) - last_conflict_tick)
            stats["ticks_since_last_conflict"] = ticks_since_last_conflict
            payload["runtime_lock_stats"] = stats
            marker.payload = payload
            if inhibition_relief > 0.0:
                marker.inhibition = max(0.0, float(marker.inhibition) - inhibition_relief)
        flat_markers.sort(key=lambda marker: marker.id)
        skill_markers = self._load_skill_markers()
        return EnvironmentSnapshot(
            tick=tick,
            markers=flat_markers,
            by_type=copied_grouped,
            control=runtime_control,
            skills=skill_markers,
        )

    def _load_skill_markers(self) -> list[Marker]:
        """Load persistent skill markers from the cross-run store when enabled."""
        if self.skills_store is None:
            return []
        skill_cfg = dict(self.config.get("skill_library", {}))
        if not bool(skill_cfg.get("enabled", False)):
            return []
        try:
            rows = self.skills_store.query_markers(marker_type="skill")
        except Exception:  # noqa: BLE001
            return []
        return [Marker.from_dict(marker.to_dict()) for marker in rows]

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
            marker_to_save.last_active_at = utc_now_iso()

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

        persisted.extend(
            self._apply_validation_result(
                agent_id=agent_id,
                validation=result.validation,
            )
        )

        self._maybe_promote_to_skill(
            agent_id=agent_id,
            result=result,
            quality_score=quality_score,
        )

        self.tokens_used += int(result.consumed_tokens)
        self.cost_used += float(result.cost_usd)
        self.enforce_budget()
        return persisted

    def maintain(self, current_tick: int) -> dict[str, Any]:
        """Apply lock maintenance and marker decay for one tick."""
        ttl = int(self.config.get("guardrails", {}).get("scope_lock_ttl", 3))
        released_locks = self.store.maintain_locks(current_tick=current_tick, ttl=ttl)
        decayed_markers = self.store.apply_decay(current_tick=current_tick, config=self.config)
        frequentation_boosted_markers = self.store.apply_frequentation(
            current_tick=current_tick,
            config=self.config,
        )
        pruned = int(getattr(self.store, "last_decay_pruned_count", 0))
        self.pruned_markers += pruned
        return {
            "released_locks": released_locks,
            "decayed_markers": decayed_markers,
            "frequentation_boosted_markers": frequentation_boosted_markers,
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
        updated.last_active_at = utc_now_iso()
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
            updated.last_active_at = utc_now_iso()
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
        lesson_id = f"lesson::{source_marker.id}"
        existing = self.store.get_marker(lesson_id)
        prior_usage = (
            int(existing.payload.get("usage_count", 0)) if existing is not None else 0
        )
        return Marker(
            id=lesson_id,
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
                "usage_count": prior_usage,
            },
            created_by=source_agent,
            created_at=timestamp,
            updated_by=source_agent,
            updated_at=timestamp,
            last_active_at=timestamp,
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

    def _apply_validation_result(
        self,
        *,
        agent_id: str,
        validation: ValidationResult | None,
    ) -> list[Marker]:
        if validation is None:
            return []

        repair_cfg = dict(self.config.get("orchestrator", {}).get("targeted_repair", {}))
        if not bool(repair_cfg.get("enabled", False)):
            return []

        repair = validation.repair
        if repair is None or str(validation.status).strip().lower() != "failed":
            return []

        allowed_attempts = min(
            max(1, int(repair.max_attempts)),
            max(1, int(repair_cfg.get("max_cycles", 1))),
        )
        if int(repair.attempt) > allowed_attempts:
            return []

        target_marker = self.store.get_marker(repair.target_marker_id)
        if target_marker is None:
            return []

        timestamp = utc_now_iso()
        repair_id = build_repair_marker_id(
            source_marker_id=validation.source_marker_id,
            target_marker_id=repair.target_marker_id,
            attempt=repair.attempt,
        )
        feedback = [
            str(item).strip()
            for item in (repair.feedback or validation.feedback)
            if str(item).strip()
        ]
        payload = dict(target_marker.payload)
        payload.update(dict(repair.payload_updates))
        payload["repair_target_id"] = target_marker.id
        payload["repair_source_id"] = str(validation.source_marker_id).strip()
        payload["repair_attempt"] = int(repair.attempt)
        payload["repair_targets"] = [
            str(item).strip() for item in validation.targets if str(item).strip()
        ]
        payload["validation_feedback"] = feedback
        payload["repair_feedback"] = feedback
        if repair.eligible_actions:
            payload["eligible_actions"] = list(repair.eligible_actions)

        repair_marker = Marker(
            id=repair_id,
            marker_type=str(repair.marker_type or "repair"),
            target=target_marker.target,
            intensity=min(
                1.0,
                max(
                    0.0,
                    float(
                        repair.intensity
                        if repair.intensity is not None
                        else repair_cfg.get("repair_marker_intensity", 0.95)
                    ),
                ),
            ),
            state="pending",
            payload=payload,
            created_by=agent_id,
            created_at=timestamp,
            updated_by=agent_id,
            updated_at=timestamp,
            last_active_at=timestamp,
            history=["created", "repair_requested"],
        )
        return [self.store.upsert_marker(marker=repair_marker, agent_id=agent_id)]

    def _maybe_promote_to_skill(
        self,
        *,
        agent_id: str,
        result: ActionResult,
        quality_score: float,
    ) -> None:
        """Promote credited lesson markers to persistent skill markers."""
        if self.skills_store is None:
            return
        skill_cfg = dict(self.config.get("skill_library", {}))
        if not bool(skill_cfg.get("enabled", False)):
            return
        if bool(skill_cfg.get("read_only", False)):
            return

        credited_raw = result.metadata.get("credited_lesson_ids", [])
        if not isinstance(credited_raw, (list, tuple, set)):
            return
        credited_ids = [str(item).strip() for item in credited_raw if str(item).strip()]
        if not credited_ids:
            return

        reinforcement_cfg = dict(self.config.get("reinforcement", {}))
        lesson_threshold = float(reinforcement_cfg.get("lesson_threshold", 0.7))
        if float(quality_score) < lesson_threshold:
            return

        promotion_min_uses = max(1, int(reinforcement_cfg.get("promotion_min_uses", 2)))
        timestamp = utc_now_iso()

        for lesson_id in credited_ids:
            lesson = self.store.get_marker(lesson_id)
            if lesson is None:
                continue

            lesson_payload = dict(lesson.payload)
            prior_uses = int(lesson_payload.get("usage_count", 0))
            usage_count = prior_uses + 1
            lesson_payload["usage_count"] = usage_count

            updated_lesson = Marker.from_dict(lesson.to_dict())
            updated_lesson.payload = lesson_payload
            updated_lesson.last_active_at = timestamp
            self.store.upsert_marker(marker=updated_lesson, agent_id=agent_id)

            if usage_count < promotion_min_uses:
                continue

            skill_id = f"skill::{self.adapter_name}::{lesson_id}"
            skill_intensity = max(0.0, min(1.0, float(quality_score)))
            skill_text = str(lesson_payload.get("lesson", "")).strip()
            context_fingerprint = self._build_skill_context_fingerprint(lesson)

            existing_skill = self.skills_store.get_marker(skill_id)
            if existing_skill is not None:
                new_payload = dict(existing_skill.payload)
                new_payload["skill_text"] = skill_text or str(
                    new_payload.get("skill_text", "")
                )
                new_payload["context_fingerprint"] = context_fingerprint
                new_payload["quality_score"] = max(
                    float(new_payload.get("quality_score", 0.0)),
                    float(quality_score),
                )
                new_payload["usage_count"] = int(new_payload.get("usage_count", 0)) + 1
                new_payload["source_lesson_id"] = lesson_id
                new_payload["domain"] = self.adapter_name

                updated_skill = Marker.from_dict(existing_skill.to_dict())
                updated_skill.payload = new_payload
                updated_skill.intensity = max(
                    existing_skill.intensity,
                    skill_intensity,
                )
                updated_skill.last_active_at = timestamp
                self.skills_store.upsert_marker(marker=updated_skill, agent_id=agent_id)
            else:
                skill_marker = Marker(
                    id=skill_id,
                    marker_type="skill",
                    target=str(lesson.target),
                    intensity=skill_intensity,
                    state="terminal",
                    payload={
                        "skill_text": skill_text,
                        "context_fingerprint": context_fingerprint,
                        "quality_score": float(quality_score),
                        "usage_count": usage_count,
                        "source_lesson_id": lesson_id,
                        "domain": self.adapter_name,
                    },
                    created_by=agent_id,
                    created_at=timestamp,
                    updated_by=agent_id,
                    updated_at=timestamp,
                    last_active_at=timestamp,
                    history=["promoted"],
                )
                self.skills_store.upsert_marker(marker=skill_marker, agent_id=agent_id)
            self.skills_promoted += 1

    def _build_skill_context_fingerprint(self, lesson: Marker) -> str:
        target = str(lesson.target).strip()
        source_marker = str(lesson.payload.get("source_marker", "")).strip()
        return f"{self.adapter_name}::{target}::{source_marker}"
