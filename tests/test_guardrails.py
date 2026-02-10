"""Unit tests for environment guardrails."""

from __future__ import annotations

import pytest

from environment.guardrails import Guardrails, ScopeLockError, TokenBudgetExceededError


def _build_config() -> dict:
    return {
        "thresholds": {
            "max_retry_count": 3,
            "scope_lock_ttl": 3,
        },
        "llm": {
            "max_tokens_total": 100,
        },
    }


def test_enforce_token_budget_accepts_under_limit() -> None:
    guardrails = Guardrails(_build_config())
    guardrails.enforce_token_budget(99)


def test_enforce_token_budget_raises_over_limit() -> None:
    guardrails = Guardrails(_build_config())
    with pytest.raises(TokenBudgetExceededError):
        guardrails.enforce_token_budget(101)


def test_enforce_retry_limit() -> None:
    guardrails = Guardrails(_build_config())
    assert guardrails.enforce_retry_limit(4) is True
    assert guardrails.enforce_retry_limit(3) is False


def test_enforce_scope_lock_rejects_other_owner() -> None:
    guardrails = Guardrails(_build_config())
    status_entry = {
        "status": "in_progress",
        "lock_owner": "transformer",
    }

    with pytest.raises(ScopeLockError):
        guardrails.enforce_scope_lock(
            file_key="utils.py",
            agent_id="tester",
            status_entry=status_entry,
        )


def test_scope_lock_ttl_releases_zombie_lock() -> None:
    guardrails = Guardrails(_build_config())
    status_data = {
        "utils.py": {
            "status": "in_progress",
            "retry_count": 0,
            "lock_owner": "transformer",
            "lock_acquired_tick": 1,
        }
    }

    released = guardrails.enforce_scope_lock_ttl(status_data, current_tick=5)

    assert released == ["utils.py"]
    updated_entry = status_data["utils.py"]
    assert updated_entry["status"] == "pending"
    assert updated_entry["retry_count"] == 1
    assert "lock_owner" not in updated_entry
    assert "lock_acquired_tick" not in updated_entry


def test_stamp_trace_adds_metadata() -> None:
    guardrails = Guardrails(_build_config())

    write_payload = guardrails.stamp_trace(
        payload={"status": "pending"},
        agent_id="scout",
        action="write",
    )
    assert write_payload["created_by"] == "scout"
    assert "timestamp" in write_payload

    update_payload = guardrails.stamp_trace(
        payload={"status": "transformed"},
        agent_id="transformer",
        action="update",
    )
    assert update_payload["updated_by"] == "transformer"
    assert "timestamp" in update_payload
