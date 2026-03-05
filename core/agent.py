"""Generic stigmergic agent implementation."""

from __future__ import annotations

from dataclasses import dataclass
import random
import re
from uuid import uuid4
from typing import Any

from .dependency import unblocked_markers
from .environment import Environment, EnvironmentSnapshot
from .guardrails import BudgetExceededError
from .marker import Marker
from .pressure import compute_pressures, select_action
from .tool_registry import ActionResult, Decision, ToolRegistry


TERMINAL_STATES = {"terminal", "skipped", "escalated"}


@dataclass(slots=True)
class MemoryEntry:
    """One episodic memory entry kept by an agent."""

    context: str
    action: str
    result: str
    relevance: float
    tick: int
    entry_id: str


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
    ) -> None:
        self.agent_id = agent_id
        self.tool_registry = tool_registry
        self.config = config
        self.rng = rng or random.Random()
        agents_cfg = dict(config.get("agents", {}))
        self.memory = AgentMemory(
            capacity=int(agents_cfg.get("memory_capacity", 20)),
            decay_rate=float(agents_cfg.get("memory_decay_rate", 0.1)),
        )

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
        pressures = compute_pressures(
            markers=candidates,
            action_types=action_types,
            weights=pressure_weights,
            inhibition_threshold=inhibition_threshold,
            formula=pressure_formula,
            alpha=pressure_alpha,
            beta=pressure_beta,
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

        return Decision(
            agent_id=self.agent_id,
            action_type=action_type,
            marker_id=target.id,
            target=target.target,
            pressures=pressures,
            selected_pressure=float(pressures.get(action_type, 0.0)),
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

        return unblocked_markers(markers=candidates, terminal_ids=terminal_ids)

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
