"""Migration context carried across MigrationBench prompts and operators."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from core_v10.contracts import Observation, RunInstance

from adapters_v10.migrationbench.compatibility import (
    JavaCompatibilityProfile,
    java_profile_for,
)
from adapters_v10.migrationbench.schemas import MigrationBenchInstance


@dataclass(frozen=True)
class MigrationContext:
    """Target-aware context for one migration task."""

    source_language: str
    source_version: int
    target_language: str
    target_version: int
    target_class_major: int
    build_system: str
    migration_mode: str
    dependency_policy: str
    framework_hints: tuple[str, ...] = field(default_factory=tuple)
    expected_build_command: str = "mvn clean verify"

    @property
    def target_java(self) -> int:
        """Alias used by Java-specific call sites."""

        return int(self.target_version)

    @property
    def source_java(self) -> int:
        """Alias used by Java-specific call sites."""

        return int(self.source_version)

    @property
    def compatibility(self) -> JavaCompatibilityProfile:
        """Return the compatibility profile for this target."""

        return java_profile_for(self.target_java)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        payload = asdict(self)
        payload["target_java"] = self.target_java
        payload["source_java"] = self.source_java
        return payload


def migration_context_from_instance(
    instance: MigrationBenchInstance | RunInstance | Mapping[str, Any],
) -> MigrationContext:
    """Build a :class:`MigrationContext` from a MigrationBench instance."""

    if isinstance(instance, MigrationBenchInstance):
        data = {
            "source_language": "java",
            "source_version": getattr(instance, "source_java", 8),
            "target_language": "java",
            "target_java": instance.target_java,
            "build_system": "maven",
            "migration_mode": instance.migration_mode,
            "dependency_policy": "maximal"
            if instance.is_maximal_migration
            else "minimal",
            "framework_hints": _framework_hints_from_mapping(
                {"stratum": instance.stratum, "stats": instance.stats}
            ),
        }
        return _context_from_mapping(data)

    if isinstance(instance, RunInstance):
        payload = instance.metadata.get("instance", instance.metadata)
        if isinstance(payload, MigrationBenchInstance):
            return migration_context_from_instance(payload)
        if not isinstance(payload, Mapping):
            payload = instance.metadata
        return _context_from_mapping(payload)

    return _context_from_mapping(instance)


def migration_context_from_observation(
    observation: Observation,
    instance: RunInstance | MigrationBenchInstance | Mapping[str, Any] | None = None,
) -> MigrationContext:
    """Build context from an observation, optionally completed by instance data."""

    data: dict[str, Any] = {}
    if instance is not None:
        try:
            data.update(migration_context_from_instance(instance).to_dict())
        except ValueError:
            # Observation may carry the target during synthetic tests.
            data.update(_instance_payload(instance))

    embedded = observation.data.get("migration_context")
    if isinstance(embedded, Mapping):
        data.update(dict(embedded))
    data.update(observation.data)
    return _context_from_mapping(data)


def _context_from_mapping(raw: Mapping[str, Any]) -> MigrationContext:
    target = _required_int(raw, "target_java", "target_version")
    profile = java_profile_for(target)
    source = _optional_int(raw, "source_java", "source_version") or 8
    target_class_major = _optional_int(raw, "target_class_major")
    if target_class_major is not None and target_class_major != profile.class_major:
        raise ValueError(
            "target_class_major does not match target_java profile: "
            f"{target_class_major} != {profile.class_major}"
        )
    migration_mode = str(raw.get("migration_mode") or "minimal")
    dependency_policy = str(raw.get("dependency_policy") or migration_mode)
    return MigrationContext(
        source_language=str(raw.get("source_language") or "java"),
        source_version=source,
        target_language=str(raw.get("target_language") or "java"),
        target_version=target,
        target_class_major=profile.class_major,
        build_system=str(raw.get("build_system") or "maven"),
        migration_mode=migration_mode,
        dependency_policy=dependency_policy,
        framework_hints=_framework_hints_from_mapping(raw),
        expected_build_command=str(raw.get("expected_build_command") or "mvn clean verify"),
    )


def _required_int(raw: Mapping[str, Any], *keys: str) -> int:
    for key in keys:
        value = raw.get(key)
        if value is not None and str(value).strip() != "":
            return int(value)
    raise ValueError(f"MigrationContext requires one of: {', '.join(keys)}")


def _optional_int(raw: Mapping[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = raw.get(key)
        if value is not None and str(value).strip() != "":
            return int(value)
    return None


def _framework_hints_from_mapping(raw: Mapping[str, Any]) -> tuple[str, ...]:
    hints = raw.get("framework_hints")
    if isinstance(hints, str):
        return (hints,)
    if isinstance(hints, (list, tuple, set)):
        return tuple(str(item) for item in hints if str(item).strip())

    collected: list[str] = []
    stratum = raw.get("stratum")
    if isinstance(stratum, Mapping):
        collected.extend(f"{key}:{value}" for key, value in sorted(stratum.items()))
    stats = raw.get("stats")
    if isinstance(stats, Mapping):
        for key in ("num_pom_xml", "num_java_files", "num_test_cases"):
            if key in stats:
                collected.append(f"{key}:{stats[key]}")
    return tuple(collected)


def _instance_payload(instance: Any) -> dict[str, Any]:
    if isinstance(instance, RunInstance):
        payload = instance.metadata.get("instance", instance.metadata)
        return dict(payload) if isinstance(payload, Mapping) else {}
    if isinstance(instance, MigrationBenchInstance):
        return instance.model_dump()
    if isinstance(instance, Mapping):
        return dict(instance)
    return {}


__all__ = [
    "MigrationContext",
    "migration_context_from_instance",
    "migration_context_from_observation",
]
