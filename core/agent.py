"""Generic stigmergic agent implementation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import random
import re
from uuid import uuid4
from typing import Any, Callable

from .dependency import unblocked_markers
from .environment import Environment, EnvironmentSnapshot
from .guardrails import BudgetExceededError
from .marker import Marker
from .pressure import compute_pressures, select_action
from .tool_registry import ActionResult, Decision, ToolRegistry


TERMINAL_STATES = {"terminal", "skipped", "escalated"}
OnPerceiveCallback = Callable[[str, list[Marker], int], None]


@dataclass(slots=True)
class MemoryEntry:
    """One episodic memory entry kept by an agent."""

    context: str
    action: str
    result: str
    relevance: float
    tick: int
    entry_id: str


@dataclass(slots=True)
class AgentAffinityProfile:
    """Lightweight local affinity profile built from successful actions."""

    type_counts: dict[str, int]
    target_keywords: dict[str, int]
    total_actions: int = 0

    def record_action(self, marker_type: str, target: str) -> None:
        """Update local specialization traces after one successful action."""
        normalized_type = str(marker_type).strip()
        if normalized_type:
            self.type_counts[normalized_type] = self.type_counts.get(normalized_type, 0) + 1

        for keyword in self._tokenize(target):
            self.target_keywords[keyword] = self.target_keywords.get(keyword, 0) + 1

        self.total_actions += 1

    def type_affinity(self, marker_type: str) -> float:
        """Return relative affinity for one marker type."""
        if self.total_actions <= 0:
            return 0.5
        count = self.type_counts.get(str(marker_type).strip(), 0)
        return self._clamp(float(count) / float(self.total_actions))

    def semantic_affinity(self, target: str) -> float:
        """Return keyword-overlap affinity for one target."""
        if self.total_actions <= 0:
            return 0.5
        keywords = self._tokenize(target)
        if not keywords:
            return 0.5
        overlap = sum(1 for keyword in keywords if keyword in self.target_keywords)
        return self._clamp(float(overlap) / float(len(keywords)))

    def combined_affinity(
        self,
        marker_type: str,
        target: str,
        *,
        type_weight: float = 0.5,
        semantic_weight: float = 0.5,
    ) -> float:
        """Return weighted affinity across type and target semantics."""
        if self.total_actions <= 0:
            return 0.5

        type_score = self.type_affinity(marker_type)
        semantic_score = self.semantic_affinity(target)
        type_value = max(0.0, float(type_weight))
        semantic_value = max(0.0, float(semantic_weight))
        weight_sum = type_value + semantic_value
        if weight_sum <= 0.0:
            return self._clamp((type_score + semantic_score) / 2.0)
        return self._clamp(
            ((type_score * type_value) + (semantic_score * semantic_value)) / weight_sum
        )

    def _tokenize(self, text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-zA-Z0-9_]+", str(text).lower())
            if token
        }

    def _clamp(self, value: float) -> float:
        return max(0.0, min(1.0, float(value)))


class AgentMemory:
    """Bounded in-memory episodic store used by one agent."""

    def __init__(self, *, capacity: int = 20, decay_rate: float = 0.1) -> None:
        self.capacity = max(1, int(capacity))
        self.decay_rate = min(1.0, max(0.0, float(decay_rate)))
        self._entries: list[MemoryEntry] = []

    def remember(
        self,
        *,
        context: str,
        action: str,
        result: str,
        tick: int,
        relevance: float = 1.0,
    ) -> MemoryEntry:
        """Persist one episodic memory entry."""
        entry = MemoryEntry(
            context=str(context).strip(),
            action=str(action).strip(),
            result=str(result).strip(),
            relevance=self._clamp(float(relevance), 0.0, 1.0),
            tick=max(0, int(tick)),
            entry_id=str(uuid4()),
        )

        if len(self._entries) >= self.capacity:
            self._evict_weakest()
        self._entries.append(entry)
        return entry

    def recall(
        self,
        *,
        current_context: str,
        current_tick: int,
        top_k: int = 3,
    ) -> list[MemoryEntry]:
        """Return top-k memories by overlap * relevance * recency."""
        if not self._entries:
            return []

        now_tick = max(0, int(current_tick))
        limit = max(1, int(top_k))
        scored: list[tuple[float, MemoryEntry]] = []

        for entry in self._entries:
            overlap = self._keyword_overlap(current_context, entry.context)
            age = max(0, now_tick - entry.tick)
            score = overlap * float(entry.relevance) * (1.0 / (1.0 + float(age)))
            scored.append((score, entry))

        scored.sort(
            key=lambda item: (
                -item[0],
                -float(item[1].relevance),
                -int(item[1].tick),
                item[1].entry_id,
            )
        )
        return [entry for _, entry in scored[:limit]]

    def reinforce(self, *, entry_id: str, reward: float = 0.1) -> None:
        """Increase relevance of one memory entry after successful usage."""
        delta = max(0.0, float(reward))
        if delta <= 0.0:
            return
        for entry in self._entries:
            if entry.entry_id != entry_id:
                continue
            entry.relevance = self._clamp(entry.relevance + delta, 0.0, 1.0)
            return

    def decay_all(self) -> None:
        """Apply global relevance decay to all entries."""
        if not self._entries:
            return
        decay_multiplier = 1.0 - self.decay_rate
        for entry in self._entries:
            entry.relevance = self._clamp(
                float(entry.relevance) * decay_multiplier, 0.0, 1.0
            )

    def _evict_weakest(self) -> None:
        if not self._entries:
            return
        weakest_idx = min(
            range(len(self._entries)),
            key=lambda idx: (
                float(self._entries[idx].relevance),
                int(self._entries[idx].tick),
                self._entries[idx].entry_id,
            ),
        )
        self._entries.pop(weakest_idx)

    def _keyword_overlap(self, current_context: str, memory_context: str) -> float:
        current_tokens = self._tokenize(current_context)
        memory_tokens = self._tokenize(memory_context)
        if not current_tokens or not memory_tokens:
            return 0.0
        common = current_tokens.intersection(memory_tokens)
        return float(len(common)) / float(len(current_tokens))

    def _tokenize(self, text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-zA-Z0-9_]+", str(text).lower())
            if token
        }

    def _clamp(self, value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, float(value)))


class StigmergicAgent:
    """Homogeneous role-free agent guided by environmental pressure."""

    def __init__(
        self,
        *,
        agent_id: str,
        tool_registry: ToolRegistry,
        config: dict[str, Any],
        rng: random.Random | None = None,
        on_perceive: OnPerceiveCallback | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.tool_registry = tool_registry
        self.config = config
        self.rng = rng or random.Random()
        self.on_perceive = on_perceive
        agents_cfg = dict(config.get("agents", {}))
        self.memory = AgentMemory(
            capacity=int(agents_cfg.get("memory_capacity", 20)),
            decay_rate=float(agents_cfg.get("memory_decay_rate", 0.1)),
        )
        self.affinity = AgentAffinityProfile(type_counts={}, target_keywords={})

    def bind_on_perceive(self, callback: OnPerceiveCallback | None) -> None:
        """Attach or replace the optional perception callback."""
        self.on_perceive = callback

    async def perceive_and_decide(
        self,
        snapshot: EnvironmentSnapshot,
    ) -> Decision | None:
        """Build one decision from current snapshot."""
        action_types = self.tool_registry.action_types()
        if not action_types:
            return None

        candidates = self._candidate_markers(snapshot=snapshot)
        if not candidates:
            return None

        pressure_weights = self.config.get("pressures", {}).get("default_weights", {})
        pressure_formula = str(
            self.config.get("pressures", {}).get("formula", "simple")
        )
        pressure_alpha = float(self.config.get("pressures", {}).get("alpha", 1.0))
        pressure_beta = float(self.config.get("pressures", {}).get("beta", 1.0))
        inhibition_threshold = float(
            self.config.get("markers", {}).get("inhibition_threshold", 1.0)
        )
        heuristic_fn = None
        if bool(self._local_sensing_config().get("enabled", False)):
            heuristic_fn = lambda marker, action: self._affinity_heuristic(
                marker=marker,
                action=action,
                pressure_weights=pressure_weights,
            )
        pressures = compute_pressures(
            markers=candidates,
            action_types=action_types,
            weights=pressure_weights,
            inhibition_threshold=inhibition_threshold,
            formula=pressure_formula,
            alpha=pressure_alpha,
            beta=pressure_beta,
            heuristic_fn=heuristic_fn,
        )

        temperature = float(
            self.config.get("agents", {}).get("selection_temperature", 0.1)
        )
        action_type = select_action(
            pressures=pressures, temperature=temperature, rng=self.rng
        )
        if action_type is None:
            return None

        eligible = [
            marker
            for marker in candidates
            if action_type in marker.payload.get("eligible_actions", [])
        ]
        if not eligible:
            return None

        target = sorted(
            eligible,
            key=lambda marker: (-marker.intensity, marker.inhibition, marker.id),
        )[0]
        decision_context = self._build_decision_context(
            action_type=action_type,
            marker=target,
        )
        memory_top_k = int(self.config.get("agents", {}).get("memory_top_k", 3))
        recalled = self.memory.recall(
            current_context=decision_context,
            current_tick=int(snapshot.tick),
            top_k=memory_top_k,
        )
        recalled_memories = [
            self._memory_entry_payload(entry=entry, now_tick=int(snapshot.tick))
            for entry in recalled
        ]
        lesson_markers = self._recall_lessons(
            snapshot=snapshot,
            top_k=int(self.config.get("agents", {}).get("lesson_top_k", 3)),
        )
        selection_affinity = self._marker_affinity(target)

        return Decision(
            agent_id=self.agent_id,
            action_type=action_type,
            marker_id=target.id,
            marker_type=target.marker_type,
            target=target.target,
            pressures=pressures,
            selected_pressure=float(pressures.get(action_type, 0.0)),
            selection_affinity=selection_affinity,
            tick=int(snapshot.tick),
            context=decision_context,
            recalled_memories=recalled_memories,
            lesson_markers=lesson_markers,
        )

    async def execute(
        self,
        decision: Decision,
        environment: Environment,
        llm_client: Any | None = None,
    ) -> ActionResult:
        """Execute selected tool and persist updates through environment."""
        action_type = str(getattr(decision, "action_type", ""))
        marker_id = str(getattr(decision, "marker_id", ""))

        tool = self.tool_registry.get(action_type)
        marker = environment.store.get_marker(marker_id)
        if marker is None:
            return ActionResult(
                action_type=action_type,
                metadata={"failed": True, "reason": "marker_not_found"},
            )

        if marker.lock_owner not in {None, self.agent_id}:
            return ActionResult(
                action_type=action_type,
                metadata={"failed": True, "reason": "lock_conflict"},
            )

        try:
            runtime_marker = Marker.from_dict(marker.to_dict())
            runtime_payload = dict(runtime_marker.payload)
            recalled = getattr(decision, "recalled_memories", [])
            lessons = getattr(decision, "lesson_markers", [])
            if isinstance(recalled, list) and recalled:
                runtime_payload["recalled_memories"] = list(recalled)
            if isinstance(lessons, list) and lessons:
                runtime_payload["lesson_markers"] = list(lessons)
            runtime_marker.payload = runtime_payload

            result = await tool.execute(
                agent_id=self.agent_id,
                marker=runtime_marker,
                environment=environment,
                llm_client=llm_client,
            )
            environment.apply_action_result(agent_id=self.agent_id, result=result)
            if not bool(result.metadata.get("failed", False)):
                self.affinity.record_action(
                    marker_type=runtime_marker.marker_type,
                    target=runtime_marker.target,
                )

            remembered = self.memory.remember(
                context=str(getattr(decision, "context", runtime_marker.target)),
                action=action_type,
                result=self._result_summary(result),
                tick=int(getattr(decision, "tick", 0)),
                relevance=self._memory_relevance(result),
            )
            self.memory.reinforce(
                entry_id=remembered.entry_id,
                reward=max(0.0, self._extract_quality_score(result) - 0.5),
            )
            return result
        except BudgetExceededError:
            raise
        except Exception as exc:  # noqa: BLE001
            return ActionResult(
                action_type=action_type,
                metadata={"failed": True, "error": str(exc)},
            )

    def _candidate_markers(self, snapshot: EnvironmentSnapshot) -> list[Marker]:
        inhibition_threshold = float(
            self.config.get("markers", {}).get("inhibition_threshold", 1.0)
        )
        candidates: list[Marker] = []
        terminal_ids = {
            marker.id
            for marker in snapshot.markers
            if marker.state in TERMINAL_STATES
        }

        for marker in snapshot.markers:
            if marker.state in TERMINAL_STATES:
                continue
            if marker.lock_owner not in {None, self.agent_id}:
                continue
            if marker.inhibition >= inhibition_threshold:
                continue

            eligible_actions = self.tool_registry.eligible_actions_for(marker)
            raw_allowed_actions = marker.payload.get("eligible_actions")
            if (
                isinstance(raw_allowed_actions, (list, tuple, set))
                and len(raw_allowed_actions) > 0
            ):
                allowed_set = {str(action) for action in raw_allowed_actions}
                eligible_actions = [
                    action for action in eligible_actions if action in allowed_set
                ]
            if not eligible_actions:
                continue

            candidate = Marker.from_dict(marker.to_dict())
            candidate.payload = dict(candidate.payload)
            candidate.payload["eligible_actions"] = list(eligible_actions)
            candidates.append(candidate)

        visible = self._apply_local_sensing(
            unblocked_markers(markers=candidates, terminal_ids=terminal_ids)
        )
        if callable(self.on_perceive) and visible:
            try:
                self.on_perceive(self.agent_id, visible, int(snapshot.tick))
            except Exception:  # noqa: BLE001
                pass
        return visible

    def _build_decision_context(self, *, action_type: str, marker: Marker) -> str:
        payload = dict(marker.payload)
        parts = [
            str(action_type).strip(),
            str(marker.marker_type).strip(),
            str(marker.target).strip(),
            str(payload.get("objective", "")).strip(),
            str(payload.get("task", "")).strip(),
            str(payload.get("description", "")).strip(),
        ]
        return " | ".join(part for part in parts if part)

    def _memory_entry_payload(
        self,
        *,
        entry: MemoryEntry,
        now_tick: int,
    ) -> dict[str, Any]:
        age = max(0, int(now_tick) - int(entry.tick))
        return {
            "entry_id": entry.entry_id,
            "context": entry.context,
            "action": entry.action,
            "result": entry.result,
            "relevance": float(entry.relevance),
            "tick": int(entry.tick),
            "age": int(age),
        }

    def _recall_lessons(
        self,
        *,
        snapshot: EnvironmentSnapshot,
        top_k: int,
    ) -> list[dict[str, Any]]:
        lessons = [
            marker
            for marker in snapshot.by_type.get("lesson", [])
            if marker.state == "terminal"
        ]
        lessons.sort(
            key=lambda marker: (
                marker.updated_at,
                marker.id,
            ),
            reverse=True,
        )

        selected = lessons[: max(1, int(top_k))]
        return [
            {
                "id": marker.id,
                "target": marker.target,
                "lesson": str(marker.payload.get("lesson", "")).strip(),
                "source_marker": str(marker.payload.get("source_marker", "")).strip(),
                "source_agent": str(marker.payload.get("source_agent", "")).strip(),
                "updated_at": marker.updated_at,
            }
            for marker in selected
        ]

    def _result_summary(self, result: ActionResult) -> str:
        if result.metadata.get("failed"):
            reason = str(result.metadata.get("reason", result.metadata.get("error", "failed")))
            return f"failed:{reason}"

        states = sorted(
            {
                str(marker.state).strip()
                for marker in result.marker_updates
                if str(marker.state).strip()
            }
        )
        if not states:
            return "success"
        return f"states:{','.join(states)}"

    def _memory_relevance(self, result: ActionResult) -> float:
        if bool(result.metadata.get("failed", False)):
            return 0.2
        quality = self._extract_quality_score(result)
        return max(0.3, min(1.0, quality))

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

    def _apply_local_sensing(self, markers: list[Marker]) -> list[Marker]:
        cfg = self._local_sensing_config()
        if not bool(cfg.get("enabled", False)):
            return markers

        intensity_threshold = float(cfg.get("intensity_threshold", 0.0))
        filtered = [
            marker for marker in markers if float(marker.intensity) >= intensity_threshold
        ]
        if not filtered:
            return []

        exploration_rate = max(
            0.0,
            min(1.0, float(cfg.get("affinity_exploration_rate", 0.2))),
        )
        if exploration_rate >= 1.0 or self.rng.random() < exploration_rate:
            return filtered

        type_weight = float(cfg.get("type_affinity_weight", 0.4))
        semantic_weight = float(cfg.get("semantic_affinity_weight", 0.3))
        recency_weight = float(cfg.get("recency_weight", 0.3))
        recency_scores = self._recency_scores(filtered)

        scored: list[tuple[float, Marker]] = []
        for marker in filtered:
            score = (
                (self.affinity.type_affinity(marker.marker_type) * type_weight)
                + (self.affinity.semantic_affinity(marker.target) * semantic_weight)
                + (recency_scores.get(marker.id, 0.5) * recency_weight)
            )
            scored.append((score, marker))

        scored.sort(
            key=lambda item: (
                -item[0],
                -item[1].intensity,
                item[1].inhibition,
                item[1].id,
            )
        )
        limit = int(cfg.get("max_candidates", 0))
        ordered = [marker for _, marker in scored]
        if limit > 0:
            return ordered[:limit]
        return ordered

    def _local_sensing_config(self) -> dict[str, Any]:
        agents_cfg = dict(self.config.get("agents", {}))
        return dict(agents_cfg.get("local_sensing", {}))

    def _affinity_heuristic(
        self,
        *,
        marker: Marker,
        action: str,
        pressure_weights: dict[str, float] | Any,
    ) -> float:
        base_weight = max(float(dict(pressure_weights).get(action, 1.0)), 0.0)
        return base_weight * (1.0 + self._marker_affinity(marker))

    def _marker_affinity(self, marker: Marker) -> float:
        cfg = self._local_sensing_config()
        return self.affinity.combined_affinity(
            marker.marker_type,
            marker.target,
            type_weight=float(cfg.get("type_affinity_weight", 0.4)),
            semantic_weight=float(cfg.get("semantic_affinity_weight", 0.3)),
        )

    def _recency_scores(self, markers: list[Marker]) -> dict[str, float]:
        parsed: list[tuple[Marker, float]] = []
        for marker in markers:
            raw = str(marker.last_active_at or marker.updated_at).strip()
            try:
                parsed_dt = datetime.fromisoformat(raw)
            except ValueError:
                continue
            parsed.append((marker, parsed_dt.timestamp()))

        if not parsed:
            return {marker.id: 0.5 for marker in markers}

        timestamps = [value for _, value in parsed]
        oldest = min(timestamps)
        newest = max(timestamps)
        if newest <= oldest:
            return {marker.id: 0.5 for marker in markers}

        scores = {
            marker.id: (timestamp - oldest) / (newest - oldest)
            for marker, timestamp in parsed
        }
        for marker in markers:
            scores.setdefault(marker.id, 0.5)
        return scores
