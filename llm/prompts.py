"""Prompt templates used by generic stigmergic tools."""

from __future__ import annotations

from typing import Any


SYSTEM_STIGMERGIC_AGENT_PROMPT = (
    "You are a domain-agnostic stigmergic worker. "
    "Read marker context, perform the requested action, and return structured outputs."
)


def build_action_prompt(
    *,
    action_type: str,
    target: str,
    objective: str,
    marker_payload: dict[str, Any],
) -> str:
    """Build a compact action prompt from marker context."""
    return (
        f"Action: {action_type}\n"
        f"Target: {target}\n"
        f"Objective: {objective}\n"
        f"Marker payload: {marker_payload}\n"
        "Respond with concise actionable output."
    )
