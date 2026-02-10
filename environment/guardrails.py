"""Environment guardrails enforcing deep norms for the stigmergic medium."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, MutableMapping


class GuardrailError(RuntimeError):
    """Base exception for guardrail violations."""


class TokenBudgetExceededError(GuardrailError):
    """Raised when token usage exceeds configured budget."""


class ScopeLockError(GuardrailError):
    """Raised when a file-level lock is held by another agent."""


class Guardrails:
    """Enforce budget, anti-loop, lock, TTL, and traceability rules."""

    def __init__(self, config: Mapping[str, Any]) -> None:
        thresholds = config.get("thresholds", {})
        llm = config.get("llm", {})

        self.max_tokens_total = int(llm.get("max_tokens_total", 100_000))
        self.max_retry_count = int(thresholds.get("max_retry_count", 3))
        self.scope_lock_ttl = int(thresholds.get("scope_lock_ttl", 3))

    def enforce_token_budget(self, total_tokens_used: int) -> None:
        """Raise when the token budget ceiling is exceeded."""
        if total_tokens_used > self.max_tokens_total:
            raise TokenBudgetExceededError(
                f"Token budget exceeded: {total_tokens_used} > {self.max_tokens_total}"
            )

    def enforce_retry_limit(self, retry_count: int) -> bool:
        """Return True when a file should be marked as skipped."""
        return retry_count > self.max_retry_count

    def enforce_scope_lock(
        self,
        file_key: str,
        agent_id: str,
        status_entry: Mapping[str, Any] | None,
    ) -> None:
        """Ensure only one agent can mutate a file while it is in progress."""
        if not status_entry:
            return

        lock_owner = status_entry.get("lock_owner")
        status_value = status_entry.get("status")

        if status_value == "in_progress" and lock_owner and lock_owner != agent_id:
            raise ScopeLockError(
                f"Scope lock violation for {file_key}: held by {lock_owner}, not {agent_id}"
            )

    def acquire_scope_lock(
        self,
        status_entry: MutableMapping[str, Any],
        agent_id: str,
        current_tick: int = 0,
    ) -> MutableMapping[str, Any]:
        """Attach lock ownership metadata to a status entry."""
        status_entry["lock_owner"] = agent_id
        status_entry["lock_acquired_tick"] = int(current_tick)
        return status_entry

    def release_scope_lock(
        self,
        status_entry: MutableMapping[str, Any],
        agent_id: str,
    ) -> MutableMapping[str, Any]:
        """Release lock metadata when the current owner completes or fails."""
        lock_owner = status_entry.get("lock_owner")
        if lock_owner is None or lock_owner == agent_id:
            status_entry.pop("lock_owner", None)
            status_entry.pop("lock_acquired_tick", None)
        return status_entry

    def enforce_scope_lock_ttl(
        self,
        status_data: MutableMapping[str, MutableMapping[str, Any]],
        current_tick: int,
    ) -> list[str]:
        """Release zombie in-progress locks past TTL and requeue files."""
        released_files: list[str] = []

        for file_key, entry in status_data.items():
            if entry.get("status") != "in_progress":
                continue

            lock_owner = entry.get("lock_owner")
            lock_tick = entry.get("lock_acquired_tick")
            if lock_owner is None or lock_tick is None:
                continue

            if current_tick - int(lock_tick) > self.scope_lock_ttl:
                entry["previous_status"] = entry.get("status")
                entry["status"] = "pending"
                entry["retry_count"] = int(entry.get("retry_count", 0)) + 1
                entry["timestamp"] = utc_timestamp()
                entry["updated_by"] = "system_ttl"
                entry.pop("lock_owner", None)
                entry.pop("lock_acquired_tick", None)
                released_files.append(file_key)

        return released_files

    def stamp_trace(
        self,
        payload: MutableMapping[str, Any],
        agent_id: str,
        action: str,
    ) -> MutableMapping[str, Any]:
        """Attach traceability metadata to write/update payloads."""
        if action not in {"write", "update"}:
            raise ValueError(f"Unsupported trace action: {action}")

        payload["timestamp"] = utc_timestamp()
        if action == "write":
            payload.setdefault("created_by", agent_id)
        else:
            payload["updated_by"] = agent_id

        return payload


def utc_timestamp() -> str:
    """Return UTC timestamp in ISO-8601 format with Z suffix."""
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return now.isoformat().replace("+00:00", "Z")
