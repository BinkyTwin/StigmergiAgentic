"""Core primitives for the V2 generic stigmergic framework."""

from .agent import StigmergicAgent
from .audit import AuditEvent, AuditLog, utc_timestamp
from .config import ConfigError, load_config, merge_config, validate_config
from .decay import decay_inhibition, decay_intensity
from .environment import Environment, EnvironmentSnapshot
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
from .orchestrator import Orchestrator, OrchestratorResult, TickRow
from .pressure import compute_pressures, select_action
from .tool_registry import ActionResult, Decision, Tool, ToolRegistry

__all__ = [
    "ActionResult",
    "AuditEvent",
    "AuditLog",
    "BudgetExceededError",
    "ConfigError",
    "Decision",
    "Environment",
    "EnvironmentSnapshot",
    "GuardrailEngine",
    "GuardrailError",
    "InvalidMarkerError",
    "InvalidTransitionError",
    "Marker",
    "MarkerStore",
    "MarkerStoreError",
    "MarkerType",
    "Orchestrator",
    "OrchestratorResult",
    "ScopeLockError",
    "StateMachine",
    "StigmergicAgent",
    "TickRow",
    "Tool",
    "ToolRegistry",
    "TraceabilityError",
    "compute_pressures",
    "decay_inhibition",
    "decay_intensity",
    "load_config",
    "merge_config",
    "select_action",
    "utc_timestamp",
    "validate_config",
]
