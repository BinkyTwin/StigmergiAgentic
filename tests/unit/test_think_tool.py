"""Unit tests for think tool gating behavior."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from core.marker import Marker
from tools.think import ThinkTool


def _make_marker(*, marker_id: str, state: str, payload: dict) -> Marker:
    return Marker(
        id=marker_id,
        marker_type="task",
        target=marker_id,
        intensity=1.0,
        state=state,
        payload=payload,
        created_by="seed",
        created_at="2026-03-04T12:00:00+00:00",
        updated_by="seed",
        updated_at="2026-03-04T12:00:00+00:00",
        history=["created"],
    )


def test_think_not_eligible_on_active_without_explicit_allowlist() -> None:
    tool = ThinkTool(config={})
    marker = _make_marker(marker_id="m-active", state="active", payload={})
    assert tool.is_eligible(marker) is False


def test_think_eligible_on_active_root_marker_after_decompose() -> None:
    tool = ThinkTool(config={})
    marker = _make_marker(
        marker_id="m-root-active",
        state="active",
        payload={"decomposed": True},
    )
    assert tool.is_eligible(marker) is True


def test_think_progresses_pending_to_active_and_completed_to_verified() -> None:
    tool = ThinkTool(config={})

    pending_marker = _make_marker(marker_id="m-pending", state="pending", payload={})
    result_pending = asyncio.run(
        tool.execute(
            agent_id="agent-1",
            marker=pending_marker,
            environment=object(),
            llm_client=None,
        )
    )
    assert result_pending.marker_updates[0].state == "active"

    completed_marker = _make_marker(
        marker_id="m-completed", state="completed", payload={}
    )
    result_completed = asyncio.run(
        tool.execute(
            agent_id="agent-1",
            marker=completed_marker,
            environment=object(),
            llm_client=None,
        )
    )
    assert result_completed.marker_updates[0].state == "verified"


def test_think_keeps_payload_without_hints_when_llm_returns_plain_text() -> None:
    class PlainTextLLM:
        def call(self, prompt: str, system: str | None = None) -> SimpleNamespace:
            return SimpleNamespace(
                content="I will analyze the transport options.",
                tokens_used=1,
                cost_usd=0.0,
                model="fake",
            )

        def extract_code_block(self, text: str) -> str:
            return text

    tool = ThinkTool(config={})
    marker = _make_marker(
        marker_id="m-hint",
        state="pending",
        payload={"task": "Compare Paris to London transport options"},
    )
    result = asyncio.run(
        tool.execute(
            agent_id="agent-1",
            marker=marker,
            environment=object(),
            llm_client=PlainTextLLM(),
        )
    )

    updated_payload = result.marker_updates[0].payload
    assert "query" not in updated_payload
    assert "path" not in updated_payload
    assert "command" not in updated_payload
