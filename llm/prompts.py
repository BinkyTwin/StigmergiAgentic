"""Prompt templates used by generic stigmergic tools."""

from __future__ import annotations

from typing import Any


SYSTEM_STIGMERGIC_AGENT_PROMPT = (
    "You are a domain-agnostic stigmergic worker. "
    "Read marker context, perform the requested action, and return concrete outputs. "
    "Do not describe hypothetical plans when action execution context is available."
)

SYSTEM_PROMPT_V3 = (
    "You are a domain-agnostic stigmergic worker operating in a real workspace.\n"
    "Use only concrete evidence from the workspace context and available tools.\n"
    "When you suggest an action, keep it executable and bounded.\n\n"
    "Workspace context:\n{workspace_context}\n\n"
    "Available tools: {available_tools}\n"
)


def build_system_prompt(workspace_context: str, available_tools: list[str]) -> str:
    """Build V3 system prompt with workspace context and tool surface."""
    tools = ", ".join(sorted({tool for tool in available_tools if tool})) or "none"
    context = workspace_context.strip() or "(no workspace context provided)"
    return SYSTEM_PROMPT_V3.format(
        workspace_context=context,
        available_tools=tools,
    )


def build_action_prompt(
    *,
    action_type: str,
    target: str,
    objective: str,
    marker_payload: dict[str, Any],
    available_tools: list[str] | None = None,
    workspace_context: str | None = None,
) -> str:
    """Build a compact action prompt from marker context."""
    tool_fields = _build_tool_fields(available_tools or [])
    prompt = (
        f"Action: {action_type}\n"
        f"Target: {target}\n"
        f"Objective: {objective}\n"
        f"Marker payload: {marker_payload}\n"
        f'Return strict JSON: {{"analysis":"..."{tool_fields}}}. '
        "Include optional fields only when relevant."
    )
    if workspace_context:
        prompt = f"{prompt}\nWorkspace context:\n{workspace_context}"
    return prompt


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
