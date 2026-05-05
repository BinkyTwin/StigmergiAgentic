"""V10 verified-resolution runtime core.

This package intentionally coexists with the legacy ``core`` package while the
new plug-and-play architecture is built and validated phase by phase.
"""

from core_v10.contracts import (
    ApplyResult,
    ArtifactContract,
    ArtifactResult,
    ArtifactStatus,
    Candidate,
    CandidateKind,
    Capability,
    DomainAdapterV10,
    FeedbackDigest,
    Observation,
    RunInstance,
    ScoreResult,
    ValidationResult,
    ValidationStatus,
    WorkspaceHandle,
)
from core_v10.blackboard import BlackboardSnapshot, build_blackboard, graph_from_events
from core_v10.event_log import EventRecord, JsonlEventLog, ReplaySnapshot, replay_events
from core_v10.hypothesis_graph import (
    HypothesisGraph,
    HypothesisNode,
    HypothesisScore,
    HypothesisStatus,
)
from core_v10.replay import replay_jsonl
from core_v10.signals import CoordinationSignal, SignalKind
from core_v10.strategy_runner import (
    CandidateProvider,
    RepairProvider,
    StopReason,
    StrategyConfig,
    StrategyResult,
    StrategyRunner,
)
from core_v10.verifier import FinalizationReport, VerifierLoop, VerifierReport

__all__ = [
    "ApplyResult",
    "ArtifactContract",
    "ArtifactResult",
    "ArtifactStatus",
    "Candidate",
    "CandidateKind",
    "Capability",
    "DomainAdapterV10",
    "FeedbackDigest",
    "Observation",
    "RunInstance",
    "ScoreResult",
    "ValidationResult",
    "ValidationStatus",
    "WorkspaceHandle",
    "BlackboardSnapshot",
    "build_blackboard",
    "graph_from_events",
    "EventRecord",
    "JsonlEventLog",
    "ReplaySnapshot",
    "replay_events",
    "replay_jsonl",
    "CoordinationSignal",
    "SignalKind",
    "HypothesisGraph",
    "HypothesisNode",
    "HypothesisScore",
    "HypothesisStatus",
    "FinalizationReport",
    "VerifierLoop",
    "VerifierReport",
    "CandidateProvider",
    "RepairProvider",
    "StopReason",
    "StrategyConfig",
    "StrategyResult",
    "StrategyRunner",
]
