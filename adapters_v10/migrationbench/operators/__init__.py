"""MigrationBench V11 typed operators."""

from adapters_v10.migrationbench.operators.maven import (
    migrationbench_operator_candidates,
    maven_add_jaxb_dependency_edits,
    maven_add_javafx_dependencies_edits,
    maven_add_or_upgrade_surefire_for_target_java_edits,
    maven_compiler_release_edits,
    maven_upgrade_bundle_plugin_edits,
    maven_upgrade_compiler_plugin_edits,
    maven_upgrade_lombok_for_target_java_edits,
    maven_upgrade_lombok_edits,
    maven_upgrade_surefire_plugin_edits,
    replace_sun_misc_base64_edits,
    target_java_replacements,
)

__all__ = [
    "maven_add_jaxb_dependency_edits",
    "maven_add_javafx_dependencies_edits",
    "maven_add_or_upgrade_surefire_for_target_java_edits",
    "maven_compiler_release_edits",
    "maven_upgrade_bundle_plugin_edits",
    "maven_upgrade_compiler_plugin_edits",
    "maven_upgrade_lombok_for_target_java_edits",
    "maven_upgrade_lombok_edits",
    "maven_upgrade_surefire_plugin_edits",
    "migrationbench_operator_candidates",
    "replace_sun_misc_base64_edits",
    "target_java_replacements",
]
