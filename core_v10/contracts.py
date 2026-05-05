"""Core V10 adapter and artifact contracts.

The contracts in this module are deliberately domain-neutral. Benchmark and
language-specific scoring rules belong in adapters, not in this package.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


JsonDict = dict[str, Any]


class CandidateKind(str, Enum):
    """Supported high-level candidate categories."""

    PATCH = "patch"
    PLAN = "plan"
    TOOL_ACTION = "tool_action"
    TEXT = "text"
    OTHER = "other"


class ValidationStatus(str, Enum):
    """Validation lifecycle states shared by all adapters."""

    NOT_RUN = "not_run"
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    ERROR = "error"


class ArtifactStatus(str, Enum):
    """Final artifact delivery status."""

    DELIVERED = "delivered"
    MISSING = "missing"
    INVALID = "invalid"


@dataclass(frozen=True)
class RunInstance:
    """A benchmark or local task instance exposed to the V10 runtime."""

    instance_id: str
    adapter_name: str
    objective: str
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class WorkspaceHandle:
    """Adapter-owned workspace handle.

    The core treats this as an opaque root plus metadata. Workspace preparation,
    isolation, cleanup, and official evaluator setup remain adapter concerns.
    """

    root: Path
    instance_id: str
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class Capability:
    """Tool, validator, analyzer, or finalizer exposed by an adapter."""

    name: str
    kind: str
    description: str = ""
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class Observation:
    """Initial or refreshed adapter observation."""

    summary: str
    data: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class Candidate:
    """A proposed solution hypothesis."""

    candidate_id: str
    kind: CandidateKind
    payload: JsonDict
    origin: str
    parent_id: str | None = None
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class ApplyResult:
    """Result of applying a candidate to an adapter workspace."""

    candidate_id: str
    applied: bool
    workspace: WorkspaceHandle
    summary: str = ""
    artifacts: JsonDict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationResult:
    """Adapter validation result for a candidate."""

    candidate_id: str
    status: ValidationStatus
    validator_name: str
    signals: JsonDict = field(default_factory=dict)
    summary: str = ""
    raw_output: str = ""
    errors: list[str] = field(default_factory=list)
    metadata: JsonDict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Return whether the validation fully passed."""

        return self.status == ValidationStatus.PASSED


@dataclass(frozen=True)
class FeedbackDigest:
    """Structured feedback extracted from validation, logs, or evaluator output."""

    candidate_id: str
    failure_type: str
    severity: str
    summary: str
    locations: list[JsonDict] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    candidate_causes: list[str] = field(default_factory=list)
    recommended_next_actions: list[JsonDict] = field(default_factory=list)
    anti_actions: list[str] = field(default_factory=list)
    metadata: JsonDict = field(default_factory=dict)

    @property
    def is_blocking(self) -> bool:
        """Return whether this feedback should block final success."""

        return self.severity in {"blocking", "fatal"}


@dataclass(frozen=True)
class ArtifactResult:
    """Final artifact produced by an adapter."""

    candidate_id: str
    status: ArtifactStatus
    artifacts: JsonDict = field(default_factory=dict)
    summary: str = ""
    metadata: JsonDict = field(default_factory=dict)

    @property
    def delivered(self) -> bool:
        """Return whether the adapter delivered a final artifact."""

        return self.status == ArtifactStatus.DELIVERED


@dataclass(frozen=True)
class ScoreResult:
    """Adapter scoring output mapped into common V10 metrics."""

    candidate_id: str
    strict_success: bool
    metrics: JsonDict = field(default_factory=dict)
    summary: str = ""
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class ArtifactContract:
    """Common final-output contract for adapter artifacts."""

    required_artifacts: tuple[str, ...] = ()
    required_metrics: tuple[str, ...] = ("strict_success",)

    def validate_artifact(self, artifact: ArtifactResult) -> list[str]:
        """Return missing or invalid artifact fields."""

        errors: list[str] = []
        if artifact.status != ArtifactStatus.DELIVERED:
            errors.append(f"artifact status is {artifact.status.value}")
        for key in self.required_artifacts:
            if key not in artifact.artifacts:
                errors.append(f"missing artifact: {key}")
                continue
            value = artifact.artifacts[key]
            if value is None:
                errors.append(f"empty artifact: {key}")
            elif isinstance(value, str):
                if not value.strip():
                    errors.append(f"empty artifact: {key}")
            elif isinstance(value, bytes):
                if not value:
                    errors.append(f"empty artifact: {key}")
            elif isinstance(value, Path):
                if not value.exists():
                    errors.append(f"artifact path does not exist: {key}")
                elif not value.is_file():
                    errors.append(f"artifact path is not a file: {key}")
                elif value.stat().st_size == 0:
                    errors.append(f"empty artifact file: {key}")
            else:
                errors.append(f"unsupported artifact type: {key}")
        return errors

    def validate_score(self, score: ScoreResult) -> list[str]:
        """Return missing score metrics required by this contract."""

        errors: list[str] = []
        for key in self.required_metrics:
            if key == "strict_success":
                continue
            if key not in score.metrics:
                errors.append(f"missing metric: {key}")
        return errors


class DomainAdapterV10(ABC):
    """Minimal adapter surface for V10 strategies."""

    name: str
    artifact_contract: ArtifactContract = ArtifactContract()

    @abstractmethod
    def setup(self, instance: RunInstance) -> WorkspaceHandle:
        """Prepare and return an adapter-owned workspace."""

    @abstractmethod
    def observe(self, workspace: WorkspaceHandle) -> Observation:
        """Return the current task/workspace observation."""

    @abstractmethod
    def capabilities(self) -> list[Capability]:
        """Return adapter-provided tools, analyzers, validators, and finalizers."""

    @abstractmethod
    def apply(self, candidate: Candidate, workspace: WorkspaceHandle) -> ApplyResult:
        """Apply a candidate to the workspace or isolated branch."""

    @abstractmethod
    def validate(
        self, candidate: Candidate, workspace: WorkspaceHandle
    ) -> ValidationResult:
        """Validate a candidate in the adapter domain."""

    @abstractmethod
    def diagnose(
        self, validation: ValidationResult, workspace: WorkspaceHandle
    ) -> FeedbackDigest:
        """Convert validation output into structured feedback."""

    @abstractmethod
    def finalize(
        self, candidate: Candidate, workspace: WorkspaceHandle
    ) -> ArtifactResult:
        """Export the final artifact using the adapter output contract."""

    @abstractmethod
    def score(self, artifact: ArtifactResult) -> ScoreResult:
        """Score a finalized artifact using common V10 metrics."""


def to_jsonable(value: Any) -> Any:
    """Convert V10 contract values into JSON-serializable structures."""

    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return to_jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    return value
