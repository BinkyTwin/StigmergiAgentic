"""Core primitives for the V3 generic stigmergic framework."""

from .agent import StigmergicAgent
from .audit import AuditEvent, AuditLog, utc_timestamp
from .config import ConfigError, load_config, merge_config, validate_config
from .decay import decay_inhibition, decay_intensity
from .dependency import (
    build_dependency_graph,
    depends_on_ids,
    topological_sort,
    unblocked_markers,
    validate_dag,
)
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
from .reinforcement import (
    penalize_on_failure,
    propagate_backward,
    reinforce_on_success,
)
from .schemas import (
    DecomposeOutput,
    LLMParsedResponse,
    SubtaskSpec,
    ThinkOutput,
    ToolResult,
)
from .tool_registry import ActionResult, Decision, Tool, ToolRegistry

__all__ = [
    "ActionResult",
    "AuditEvent",
    "AuditLog",
    "BudgetExceededError",
    "ConfigError",
    "DecomposeOutput",
    "Decision",
    "Environment",
    "EnvironmentSnapshot",
    "GuardrailEngine",
    "GuardrailError",
    "LLMParsedResponse",
    "InvalidMarkerError",
    "InvalidTransitionError",
    "Marker",
    "MarkerStore",
    "MarkerStoreError",
    "MarkerType",
    "SubtaskSpec",
    "Orchestrator",
    "OrchestratorResult",
    "ToolResult",
    "ScopeLockError",
    "StateMachine",
    "StigmergicAgent",
    "ThinkOutput",
    "TickRow",
    "Tool",
    "ToolRegistry",
    "TraceabilityError",
    "build_dependency_graph",
    "compute_pressures",
    "depends_on_ids",
    "decay_inhibition",
    "decay_intensity",
    "load_config",
    "merge_config",
    "penalize_on_failure",
    "propagate_backward",
    "reinforce_on_success",
    "select_action",
    "topological_sort",
    "unblocked_markers",
    "utc_timestamp",
    "validate_dag",
    "validate_config",
]
