"""Guardrails (deep norms) for the generic stigmergic environment."""

from __future__ import annotations


class GuardrailError(RuntimeError):
    """Base exception for guardrail failures."""


class BudgetExceededError(GuardrailError):
    """Raised when token or cost budgets are exceeded."""


class TraceabilityError(GuardrailError):
    """Raised when traceability metadata is missing."""


class ScopeLockError(GuardrailError):
    """Raised when a scope lock operation is invalid."""


class GuardrailEngine:
    """Collection of stateless guardrail checks."""

    def enforce_budget(
        self,
        tokens_used: int,
        max_tokens: int,
        cost_used: float,
        max_budget_usd: float,
    ) -> None:
        """Validate token and cost budget ceilings."""
        if tokens_used > max_tokens:
            raise BudgetExceededError(
                f"Token budget exceeded: {tokens_used} > {max_tokens}"
            )

        if max_budget_usd > 0.0 and cost_used > max_budget_usd:
            raise BudgetExceededError(
                f"Cost budget exceeded: {cost_used:.6f} > {max_budget_usd:.6f}"
            )

    def enforce_retry_limit(self, retry_count: int, max_retry_count: int) -> bool:
        """Return True when an item should be skipped due to retry overflow."""
        return int(retry_count) > int(max_retry_count)

    def enforce_lock_ttl(self, lock_tick: int, current_tick: int, ttl: int) -> bool:
        """Return True when a lock has expired based on TTL."""
        return int(current_tick) - int(lock_tick) > int(ttl)

    def validate_traceability(
        self,
        agent_id: str,
        timestamp: str,
        enabled: bool = True,
    ) -> None:
        """Ensure mandatory traceability fields are present when enabled."""
        if not enabled:
            return
        if not agent_id:
            raise TraceabilityError("agent_id is required for traceability")
        if not timestamp:
            raise TraceabilityError("timestamp is required for traceability")
