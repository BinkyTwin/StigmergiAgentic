"""V10 MigrationBench adapter package.

The package intentionally keeps its top-level import light. Several V12 unit
tests import small MigrationBench helpers such as ``context`` or ``schemas``;
loading the full adapter/verifier/workspace stack in ``__init__`` makes those
tests slow and brittle. Public symbols remain available through lazy
``__getattr__`` resolution.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS: dict[str, tuple[str, str]] = {
    "EditApplicationResult": ("adapters_v10.migrationbench.workspace", "EditApplicationResult"),
    "JAVA_MAJOR_VERSION": ("adapters_v10.migrationbench.schemas", "JAVA_MAJOR_VERSION"),
    "JAVA_PROFILES": ("adapters_v10.migrationbench.compatibility", "JAVA_PROFILES"),
    "JavaCompatibilityProfile": ("adapters_v10.migrationbench.compatibility", "JavaCompatibilityProfile"),
    "LocalVerificationResult": ("adapters_v10.migrationbench.verifier", "LocalVerificationResult"),
    "MigrationContext": ("adapters_v10.migrationbench.context", "MigrationContext"),
    "MigrationBenchAdapterV10": ("adapters_v10.migrationbench.adapter", "MigrationBenchAdapterV10"),
    "MigrationBenchInstance": ("adapters_v10.migrationbench.schemas", "MigrationBenchInstance"),
    "MigrationBenchVerifier": ("adapters_v10.migrationbench.verifier", "MigrationBenchVerifier"),
    "MigrationBenchWorkspaceV10": ("adapters_v10.migrationbench.workspace", "MigrationBenchWorkspaceV10"),
    "OfficialEvaluator": ("adapters_v10.migrationbench.verifier", "OfficialEvaluator"),
    "OfficialVerificationResult": ("adapters_v10.migrationbench.verifier", "OfficialVerificationResult"),
    "PatchApplyResult": ("adapters_v10.migrationbench.verifier", "PatchApplyResult"),
    "PatchStats": ("adapters_v10.migrationbench.schemas", "PatchStats"),
    "SIGNAL_KEYS": ("adapters_v10.migrationbench.verifier", "SIGNAL_KEYS"),
    "TypedEdit": ("adapters_v10.migrationbench.schemas", "TypedEdit"),
    "TypedEditSet": ("adapters_v10.migrationbench.schemas", "TypedEditSet"),
    "WorkspaceError": ("adapters_v10.migrationbench.workspace", "WorkspaceError"),
    "classify_maven_failure": ("adapters_v10.migrationbench.maven", "classify_maven_failure"),
    "feedback_digest": ("adapters_v10.migrationbench.maven", "feedback_digest"),
    "java_profile_for": ("adapters_v10.migrationbench.compatibility", "java_profile_for"),
    "migration_context_from_instance": ("adapters_v10.migrationbench.context", "migration_context_from_instance"),
    "migration_context_from_observation": ("adapters_v10.migrationbench.context", "migration_context_from_observation"),
    "parse_class_major_versions": ("adapters_v10.migrationbench.maven", "parse_class_major_versions"),
    "stable_instance_id": ("adapters_v10.migrationbench.schemas", "stable_instance_id"),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


__all__ = sorted(_EXPORTS)
