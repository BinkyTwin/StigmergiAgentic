"""V12 tool recommendation metrics.

These metrics test whether stigmergic annotations guide the agent without
removing autonomy. They are computed from EventLog payloads rather than from
provider internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from core_v10.event_log import EventRecord
from core_v12.agent_loop import (
    AGENT_TOOL_CALL_REQUESTED_EVENT,
    TOOL_EXECUTED_EVENT,
)


@dataclass(frozen=True)
class ToolRecommendationMetrics:
    tool_recommendation_follow_rate: float
    tool_recommendation_override_rate: float
    inhibited_tool_usage_rate: float
    successful_override_rate: float
    harmful_override_rate: float
    forbidden_tool_attempt_count: int
    strongly_supported_tool_ignored_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_recommendation_follow_rate": self.tool_recommendation_follow_rate,
            "tool_recommendation_override_rate": self.tool_recommendation_override_rate,
            "inhibited_tool_usage_rate": self.inhibited_tool_usage_rate,
            "successful_override_rate": self.successful_override_rate,
            "harmful_override_rate": self.harmful_override_rate,
            "forbidden_tool_attempt_count": self.forbidden_tool_attempt_count,
            "strongly_supported_tool_ignored_count": (
                self.strongly_supported_tool_ignored_count
            ),
        }


def summarize_tool_recommendation_metrics(
    events: Iterable[EventRecord | dict[str, Any]],
) -> ToolRecommendationMetrics:
    """Summarize whether agent tool choices followed medium annotations."""

    rows = _requested_tool_rows(events)
    total = len(rows)
    recommended_total = sum(1 for row in rows if row["has_strong"])
    followed = sum(1 for row in rows if row["followed"])
    overrides = [row for row in rows if row["override"]]
    inhibited = sum(1 for row in rows if row["inhibited"])
    forbidden = sum(1 for row in rows if row["forbidden"])
    ignored = sum(len(row["ignored"]) for row in rows)
    successful_overrides = sum(1 for row in overrides if row["outcome"] == "success")
    harmful_overrides = sum(
        1 for row in overrides if row["outcome"] in {"failed", "rejected"}
    )
    return ToolRecommendationMetrics(
        tool_recommendation_follow_rate=_rate(followed, recommended_total),
        tool_recommendation_override_rate=_rate(len(overrides), recommended_total),
        inhibited_tool_usage_rate=_rate(inhibited, total),
        successful_override_rate=_rate(successful_overrides, len(overrides)),
        harmful_override_rate=_rate(harmful_overrides, len(overrides)),
        forbidden_tool_attempt_count=forbidden,
        strongly_supported_tool_ignored_count=ignored,
    )


def _requested_tool_rows(events: Iterable[EventRecord | dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    pending_index: int | None = None
    for event in events:
        event_type = _event_type(event)
        payload = _payload(event)
        if event_type == AGENT_TOOL_CALL_REQUESTED_EVENT:
            context = dict(payload.get("tool_recommendation_context") or {})
            strong = tuple(context.get("strongly_supported_tools") or ())
            selected = str((payload.get("tool_call") or {}).get("tool_name") or "")
            row = {
                "selected": selected,
                "has_strong": bool(strong),
                "followed": bool(strong and selected in strong),
                "override": bool(strong and selected not in strong),
                "inhibited": bool(context.get("selected_is_inhibited")),
                "forbidden": bool(context.get("selected_is_forbidden")),
                "ignored": tuple(context.get("ignored_strongly_supported_tools") or ()),
                "outcome": None,
            }
            rows.append(row)
            pending_index = len(rows) - 1
        elif event_type == TOOL_EXECUTED_EVENT and pending_index is not None:
            result = payload.get("result") or {}
            rows[pending_index]["outcome"] = result.get("status")
            pending_index = None
    return rows


def _event_type(event: EventRecord | dict[str, Any]) -> str:
    if isinstance(event, dict):
        return str(event.get("event_type") or "")
    return event.event_type


def _payload(event: EventRecord | dict[str, Any]) -> dict[str, Any]:
    if isinstance(event, dict):
        return dict(event.get("payload") or {})
    return dict(event.payload or {})


def _rate(numerator: int, denominator: int) -> float:
    return float(numerator / denominator) if denominator else 0.0


__all__ = [
    "ToolRecommendationMetrics",
    "summarize_tool_recommendation_metrics",
]
