"""MigrationBench V11 typed operators."""

from adapters_v10.migrationbench.operators.maven import (
    BUNDLE_PLUGIN_VERSION_TARGET,
    JAVA17_POM_REPLACEMENTS,
    LOMBOK_MAVEN_PLUGIN_VERSION_TARGET,
    LOMBOK_VERSION_TARGET,
    SPRING_BOOT_JAVA17_PARENT_TARGET,
    migrationbench_operator_candidates,
    maven_add_jaxb_dependency_edits,
    maven_compiler_release_edits,
    maven_upgrade_bundle_plugin_edits,
    maven_upgrade_compiler_plugin_edits,
    maven_upgrade_lombok_java17_edits,
    maven_upgrade_spring_boot_java17_edits,
    maven_upgrade_surefire_plugin_edits,
)

__all__ = [
    "BUNDLE_PLUGIN_VERSION_TARGET",
    "JAVA17_POM_REPLACEMENTS",
    "LOMBOK_MAVEN_PLUGIN_VERSION_TARGET",
    "LOMBOK_VERSION_TARGET",
    "SPRING_BOOT_JAVA17_PARENT_TARGET",
    "maven_add_jaxb_dependency_edits",
    "maven_compiler_release_edits",
    "maven_upgrade_bundle_plugin_edits",
    "maven_upgrade_compiler_plugin_edits",
    "maven_upgrade_lombok_java17_edits",
    "maven_upgrade_spring_boot_java17_edits",
    "maven_upgrade_surefire_plugin_edits",
    "migrationbench_operator_candidates",
]
