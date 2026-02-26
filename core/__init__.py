"""Core primitives for the V2 generic stigmergic framework."""

from .audit import AuditEvent, AuditLog, utc_timestamp
from .config import ConfigError, load_config, merge_config, validate_config
from .decay import decay_inhibition, decay_intensity
from .guardrails import (
    BudgetExceededError,
    GuardrailEngine,
    GuardrailError,
    ScopeLockError,
    TraceabilityError,
)
from .marker import (
    InvalidMarkerError,
    InvalidTransitionError,
    Marker,
    MarkerType,
    StateMachine,
)
from .marker_store import MarkerStore, MarkerStoreError

__all__ = [
    "AuditEvent",
    "AuditLog",
    "BudgetExceededError",
    "ConfigError",
    "GuardrailEngine",
    "GuardrailError",
    "InvalidMarkerError",
    "InvalidTransitionError",
    "Marker",
    "MarkerStore",
    "MarkerStoreError",
    "MarkerType",
    "ScopeLockError",
    "StateMachine",
    "TraceabilityError",
    "decay_inhibition",
    "decay_intensity",
    "load_config",
    "merge_config",
    "utc_timestamp",
    "validate_config",
]
