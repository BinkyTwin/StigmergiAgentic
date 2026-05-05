"""V10 MigrationBench adapter package.

This package re-implements the MigrationBench surface on top of
``core_v10``. It must not import anything from the legacy ``core`` or
``adapters`` packages — see ``tests/unit/v10/test_import_boundaries``.
"""

from __future__ import annotations

from adapters_v10.migrationbench.schemas import (
    JAVA_MAJOR_VERSION,
    MigrationBenchInstance,
    PatchStats,
    TypedEdit,
    TypedEditSet,
    stable_instance_id,
)
from adapters_v10.migrationbench.adapter import MigrationBenchAdapterV10
from adapters_v10.migrationbench.maven import (
    classify_maven_failure,
    feedback_digest,
    parse_class_major_versions,
)
from adapters_v10.migrationbench.verifier import (
    LocalVerificationResult,
    MigrationBenchVerifier,
    OfficialEvaluator,
    OfficialVerificationResult,
    PatchApplyResult,
    SIGNAL_KEYS,
)
from adapters_v10.migrationbench.workspace import (
    EditApplicationResult,
    MigrationBenchWorkspaceV10,
    WorkspaceError,
)

__all__ = [
    "EditApplicationResult",
    "JAVA_MAJOR_VERSION",
    "LocalVerificationResult",
    "MigrationBenchAdapterV10",
    "MigrationBenchInstance",
    "MigrationBenchVerifier",
    "MigrationBenchWorkspaceV10",
    "OfficialEvaluator",
    "OfficialVerificationResult",
    "PatchApplyResult",
    "PatchStats",
    "SIGNAL_KEYS",
    "TypedEdit",
    "TypedEditSet",
    "WorkspaceError",
    "classify_maven_failure",
    "feedback_digest",
    "parse_class_major_versions",
    "stable_instance_id",
]
