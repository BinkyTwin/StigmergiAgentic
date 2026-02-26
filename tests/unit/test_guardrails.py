"""Unit tests for guardrail engine."""

from __future__ import annotations

import pytest

from core.guardrails import BudgetExceededError, GuardrailEngine, TraceabilityError


def test_enforce_budget_accepts_within_limits() -> None:
    guardrails = GuardrailEngine()
    guardrails.enforce_budget(
        tokens_used=100,
        max_tokens=200,
        cost_used=1.2,
        max_budget_usd=2.0,
    )


def test_enforce_budget_raises_on_token_overflow() -> None:
    guardrails = GuardrailEngine()
    with pytest.raises(BudgetExceededError):
        guardrails.enforce_budget(
            tokens_used=201,
            max_tokens=200,
            cost_used=1.0,
            max_budget_usd=2.0,
        )


def test_enforce_budget_raises_on_cost_overflow() -> None:
    guardrails = GuardrailEngine()
    with pytest.raises(BudgetExceededError):
        guardrails.enforce_budget(
            tokens_used=100,
            max_tokens=200,
            cost_used=2.1,
            max_budget_usd=2.0,
        )


def test_enforce_retry_limit() -> None:
    guardrails = GuardrailEngine()
    assert guardrails.enforce_retry_limit(retry_count=4, max_retry_count=3) is True
    assert guardrails.enforce_retry_limit(retry_count=3, max_retry_count=3) is False


def test_enforce_lock_ttl() -> None:
    guardrails = GuardrailEngine()
    assert guardrails.enforce_lock_ttl(lock_tick=1, current_tick=5, ttl=3) is True
    assert guardrails.enforce_lock_ttl(lock_tick=2, current_tick=5, ttl=3) is False


def test_validate_traceability_requires_fields_when_enabled() -> None:
    guardrails = GuardrailEngine()
    with pytest.raises(TraceabilityError):
        guardrails.validate_traceability(agent_id="", timestamp="2026-02-26T12:00:00+00:00")

    guardrails.validate_traceability(agent_id="agent-1", timestamp="", enabled=False)
