"""Prompt templates used by generic stigmergic tools."""

from __future__ import annotations

from typing import Any


SYSTEM_STIGMERGIC_AGENT_PROMPT = (
    "You are a domain-agnostic stigmergic worker. "
    "Read marker context, perform the requested action, and return concrete outputs. "
    "Do not describe hypothetical plans when action execution context is available."
)


def build_action_prompt(
    *,
    action_type: str,
    target: str,
    objective: str,
    marker_payload: dict[str, Any],
    available_tools: list[str] | None = None,
) -> str:
    """Build a compact action prompt from marker context."""
    tool_fields = _build_tool_fields(available_tools or [])
    return (
        f"Action: {action_type}\n"
        f"Target: {target}\n"
        f"Objective: {objective}\n"
        f"Marker payload: {marker_payload}\n"
        f'Return strict JSON: {{"analysis":"..."{tool_fields}}}. '
        "Include optional fields only when relevant."
    )


def _build_tool_fields(tools: list[str]) -> str:
    field_map = {
        "file_read": '"path":"optional"',
        "file_write": '"write":{"mode":"...","path":"...","content":"..."}',
        "bash_exec": '"command":"optional"',
        "web_search": '"query":"optional"',
    }
    fields = [field_map[tool] for tool in tools if tool in field_map]
    if not fields:
        return ""
    return "," + ",".join(fields)
