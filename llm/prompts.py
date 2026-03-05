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
    "Episodic memory:\n{memory_context}\n\n"
    "Reusable lessons:\n{lesson_context}\n\n"
    "Workspace context:\n{workspace_context}\n\n"
    "Available tools: {available_tools}\n"
)


def build_system_prompt(
    workspace_context: str,
    available_tools: list[str],
    memory_context: str | None = None,
    lesson_context: str | None = None,
) -> str:
    """Build V3 system prompt with workspace context and tool surface."""
    tools = ", ".join(sorted({tool for tool in available_tools if tool})) or "none"
    context = workspace_context.strip() or "(no workspace context provided)"
    memory = (memory_context or "").strip() or "(no episodic memories)"
    lessons = (lesson_context or "").strip() or "(no reusable lessons)"
    return SYSTEM_PROMPT_V3.format(
        memory_context=memory,
        lesson_context=lessons,
        workspace_context=context,
        available_tools=tools,
    )


def build_memory_context(memories: list[dict[str, Any]]) -> str:
    """Format episodic memories into a compact prompt block."""
    if not memories:
        return "(no episodic memories)"

    rows: list[str] = []
    for index, memory in enumerate(memories[:5], start=1):
        context = str(memory.get("context", "")).strip()
        action = str(memory.get("action", "")).strip()
        result = str(memory.get("result", "")).strip()
        relevance = memory.get("relevance")
        age = memory.get("age")
        chunks = [part for part in [action, result] if part]
        suffix = " | ".join(chunks) if chunks else "signal"

        details: list[str] = []
        if relevance is not None:
            details.append(f"relevance={relevance}")
        if age is not None:
            details.append(f"age={age}")
        details_text = f" ({', '.join(details)})" if details else ""
        rows.append(f"{index}. {context or '(no context)'} -> {suffix}{details_text}")

    return "\n".join(rows)


def build_lesson_context(lessons: list[dict[str, Any]]) -> str:
    """Format lesson markers into a compact prompt block."""
    if not lessons:
        return "(no reusable lessons)"

    rows: list[str] = []
    for index, lesson in enumerate(lessons[:5], start=1):
        text = str(lesson.get("lesson", "")).strip() or "(empty lesson)"
        source = str(lesson.get("source_marker", "")).strip()
        agent = str(lesson.get("source_agent", "")).strip()
        details = [part for part in [source, agent] if part]
        details_text = f" [{' | '.join(details)}]" if details else ""
        rows.append(f"{index}. {text}{details_text}")
    return "\n".join(rows)


def build_action_prompt(
    *,
    action_type: str,
    target: str,
    objective: str,
    marker_payload: dict[str, Any],
    available_tools: list[str] | None = None,
    workspace_context: str | None = None,
    memory_context: str | None = None,
    lesson_context: str | None = None,
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
    if memory_context:
        prompt = f"{prompt}\nEpisodic memory:\n{memory_context}"
    if lesson_context:
        prompt = f"{prompt}\nReusable lessons:\n{lesson_context}"
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
