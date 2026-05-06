"""Target-aware Java compatibility profiles for MigrationBench."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JavaCompatibilityProfile:
    """Compatibility thresholds for one target Java runtime."""

    target_java: int
    class_major: int
    compiler_plugin_min: str
    surefire_min: str
    lombok_min: str
    javafx_version: str
    jaxb_namespace_default: str
    lombok_maven_plugin_min: str = "1.18.20.0"
    spring_boot_parent_min: str | None = None
    bundle_plugin_min: str = "5.1.9"


JAVA_PROFILES: dict[int, JavaCompatibilityProfile] = {
    8: JavaCompatibilityProfile(
        target_java=8,
        class_major=52,
        compiler_plugin_min="3.8.1",
        surefire_min="2.22.2",
        lombok_min="1.18.20",
        javafx_version="8.0.202",
        jaxb_namespace_default="javax",
        spring_boot_parent_min="2.5.15",
    ),
    11: JavaCompatibilityProfile(
        target_java=11,
        class_major=55,
        compiler_plugin_min="3.8.1",
        surefire_min="2.22.2",
        lombok_min="1.18.20",
        javafx_version="11.0.2",
        jaxb_namespace_default="javax",
        spring_boot_parent_min="2.5.15",
    ),
    17: JavaCompatibilityProfile(
        target_java=17,
        class_major=61,
        compiler_plugin_min="3.11.0",
        surefire_min="3.2.5",
        lombok_min="1.18.30",
        javafx_version="17.0.2",
        jaxb_namespace_default="javax",
        spring_boot_parent_min="2.7.18",
    ),
    21: JavaCompatibilityProfile(
        target_java=21,
        class_major=65,
        compiler_plugin_min="3.11.0",
        surefire_min="3.2.5",
        lombok_min="1.18.32",
        javafx_version="21.0.2",
        jaxb_namespace_default="javax",
        spring_boot_parent_min="3.2.5",
    ),
}


JAVA_MAJOR_VERSION: dict[int, int] = {
    version: profile.class_major for version, profile in JAVA_PROFILES.items()
}
"""Mapping from Java SE version to JVM class file ``major_version`` byte."""


def java_profile_for(target_java: int) -> JavaCompatibilityProfile:
    """Return the compatibility profile for ``target_java`` or fail explicitly."""

    target = int(target_java)
    try:
        return JAVA_PROFILES[target]
    except KeyError as exc:
        raise ValueError(
            f"target_java {target} is not in supported set {sorted(JAVA_PROFILES)}"
        ) from exc


__all__ = [
    "JAVA_MAJOR_VERSION",
    "JAVA_PROFILES",
    "JavaCompatibilityProfile",
    "java_profile_for",
]
