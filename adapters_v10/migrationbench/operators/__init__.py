"""MigrationBench V11 typed operators."""

from adapters_v10.migrationbench.operators.maven import (
    JAVA17_POM_REPLACEMENTS,
    migrationbench_operator_candidates,
    maven_add_jaxb_dependency_edits,
    maven_compiler_release_edits,
    maven_upgrade_compiler_plugin_edits,
    maven_upgrade_surefire_plugin_edits,
)

__all__ = [
    "JAVA17_POM_REPLACEMENTS",
    "maven_add_jaxb_dependency_edits",
    "maven_compiler_release_edits",
    "maven_upgrade_compiler_plugin_edits",
    "maven_upgrade_surefire_plugin_edits",
    "migrationbench_operator_candidates",
]
