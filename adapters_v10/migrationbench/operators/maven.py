"""Guarded Maven operators for V11 MigrationBench candidates."""

from __future__ import annotations

import re
from typing import Any, Iterable, Sequence

from core_v10.contracts import (
    Candidate,
    CandidateKind,
    FeedbackDigest,
    Observation,
    RunInstance,
)
from core_v10.operators import ExactReplaceText
from core_v10.stigmergy.records import Affordance, OperatorInvocation

from adapters_v10.migrationbench.context import (
    MigrationContext,
    migration_context_from_observation,
)

JAXB_DEPENDENCY_XML = """    <dependency>
      <groupId>jakarta.xml.bind</groupId>
      <artifactId>jakarta.xml.bind-api</artifactId>
      <version>4.0.2</version>
    </dependency>
"""


JAVAX_JAXB_DEPENDENCY_XML = """    <dependency>
      <groupId>javax.xml.bind</groupId>
      <artifactId>jaxb-api</artifactId>
      <version>2.3.1</version>
    </dependency>
"""


def migrationbench_operator_candidates(
    *,
    feedback: FeedbackDigest,
    original: Candidate,
    observation: Observation,
    instance: RunInstance,
    affordance: Affordance | None,
) -> Sequence[Candidate]:
    """Return guarded operator candidates for one V11 affordance."""

    context = migration_context_from_observation(observation, instance)
    pom_texts = _pom_texts(observation)
    java_texts = _java_texts(observation)
    if not pom_texts and not java_texts:
        return ()
    edits: list[dict[str, Any]] = []
    operator_ids: list[str] = []
    action = affordance.action_type if affordance is not None else ""
    full_text = _feedback_text(feedback)

    if _looks_like_sun_misc_base64_failure(
        full_text=full_text,
        java_texts=java_texts,
        context=context,
    ):
        base64_edits = replace_sun_misc_base64_edits(java_texts, context)
        if base64_edits:
            edits.extend(base64_edits)
            operator_ids.append("ReplaceSunMiscBase64WithJavaUtilBase64")

    if pom_texts and _looks_like_lombok_target_failure(
        feedback=feedback,
        action=action,
        full_text=full_text,
        pom_texts=pom_texts,
    ):
        lombok_edits = maven_upgrade_lombok_edits(pom_texts, context)
        if lombok_edits:
            edits.extend(lombok_edits)
            operator_ids.append("MavenUpgradeLombokForTargetJava")

    if pom_texts and _looks_like_maven_bundle_felix_failure(
        action=action,
        full_text=full_text,
        pom_texts=pom_texts,
    ):
        bundle_edits = maven_upgrade_bundle_plugin_edits(pom_texts, context)
        if bundle_edits:
            edits.extend(bundle_edits)
            operator_ids.append("MavenUpgradeBundlePlugin")

    if pom_texts and _looks_like_compiler_release_failure(
        action=action,
        full_text=full_text,
    ):
        new_edits = maven_compiler_release_edits(pom_texts, context)
        if new_edits:
            edits.extend(new_edits)
            operator_ids.append("MavenEnsureCompilerRelease")

    if pom_texts and (
        action in {
            "fix_official_test_summary",
            "interpret_official_eval",
            "preserve_test_count",
            "preserve_test_count_and_maven_test_summary",
        }
        or any(
        token in full_text for token in ("official", "#tests=-2", "surefire", "test summary")
        )
    ):
        surefire_edits = maven_upgrade_surefire_plugin_edits(pom_texts, context)
        if surefire_edits:
            edits.extend(surefire_edits)
            operator_ids.append("MavenAddOrUpgradeSurefireForTargetJava")

    if pom_texts and _looks_like_javafx_failure(
        action=action,
        full_text=full_text,
        context=context,
    ):
        javafx_edits = maven_add_javafx_dependencies_edits(
            pom_texts,
            context,
            feedback_text=full_text,
        )
        if javafx_edits:
            edits.extend(javafx_edits)
            operator_ids.append("MavenAddJavaFxDependencies")

    if pom_texts and (action == "add_missing_dependency" or any(
        token in full_text for token in ("javax.xml.bind", "jaxb", "dependency_resolution")
    )):
        dependency_edits = maven_add_jaxb_dependency_edits(
            pom_texts,
            context,
            binding_namespace=(
                "javax"
                if "javax.xml.bind" in full_text and "jakarta.xml.bind" not in full_text
                else ("jakarta" if "jakarta.xml.bind" in full_text else None)
            ),
        )
        if dependency_edits:
            edits.extend(dependency_edits)
            operator_ids.append("MavenAddJaxbDependency")

    # Last conservative fallback for MigrationBench: if an affordance exists
    # but no specialized pattern matched, try target-Java POM declarations only.
    if (
        not edits
        and pom_texts
        and affordance is not None
        and action in {"ensure_maven_compiler_release", "select_compile_operator"}
    ):
        new_edits = maven_compiler_release_edits(pom_texts, context)
        if new_edits:
            edits.extend(new_edits)
            operator_ids.append("MavenEnsureCompilerRelease")

    if not edits:
        return ()

    source_affordance_id = affordance.affordance_id if affordance is not None else None
    invocation = OperatorInvocation(
        operator_id="+".join(operator_ids) if operator_ids else "MigrationBenchOperator",
        params={
            "failure_type": feedback.failure_type,
            "action_type": action,
            "edit_count": len(edits),
            "source_java": context.source_java,
            "target_java": context.target_java,
            "target_class_major": context.target_class_major,
            "build_system": context.build_system,
        },
        target_files=tuple(sorted({str(edit["path"]) for edit in edits})),
        rationale=(
            f"V11 operator candidate from {feedback.failure_type or 'feedback'}"
        ),
        source_affordance_id=source_affordance_id,
    )
    parent_branch = str(original.payload.get("branch_id") or original.candidate_id)
    candidate_id = (
        f"{original.candidate_id}-op-"
        f"{(source_affordance_id or invocation.operator_id).replace(':', '_')[:16]}"
    )
    return (
        Candidate(
            candidate_id=candidate_id,
            kind=CandidateKind.PATCH,
            payload={
                "branch_id": candidate_id,
                "parent_branch_id": parent_branch,
                "edit_set": {
                    "edits": edits,
                    "rationale": invocation.rationale,
                    "expected_build_command": context.expected_build_command,
                },
            },
            origin="v11_operator_search",
            parent_id=original.candidate_id,
            metadata={
                "operator_invocation": invocation.to_dict(),
                "source_affordance_id": source_affordance_id,
                "worker_id": (
                    affordance.expected_worker_kind
                    if affordance is not None
                    else "operator_selector"
                ),
            },
        ),
    )


def target_java_replacements(context: MigrationContext) -> tuple[tuple[str, str], ...]:
    """Return exact POM replacements for the migration target in ``context``."""

    old_tokens = _java_version_tokens(context.source_java)
    new_token = str(context.target_java)
    tags = (
        "maven.compiler.source",
        "maven.compiler.target",
        "maven.compiler.release",
        "source",
        "target",
        "release",
        "java.version",
    )
    replacements: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for tag in tags:
        for old_token in old_tokens:
            old = f"<{tag}>{old_token}</{tag}>"
            new = f"<{tag}>{new_token}</{tag}>"
            if old == new or (old, new) in seen:
                continue
            seen.add((old, new))
            replacements.append((old, new))
    return tuple(replacements)


def maven_compiler_release_edits(
    pom_texts: dict[str, str],
    context: MigrationContext,
) -> list[dict[str, Any]]:
    """Generate exact target-Java compiler edits only when old spans exist."""

    edits: list[dict[str, Any]] = []
    for path, text in pom_texts.items():
        path_edits: list[dict[str, Any]] = []
        for old, new in target_java_replacements(context):
            result = ExactReplaceText().apply(
                current_text=text,
                old=old,
                new=new,
                expected_replacements=1,
                allow_multiple=True,
            )
            if not result.applied:
                continue
            path_edits.append(
                {
                    "type": "replace_text",
                    "path": path,
                    "old": old,
                    "new": new,
                    "expected_replacements": result.replacements,
                    "allow_multiple": True,
                }
            )
        path_edits.extend(_compiler_release_property_insert_edits(path, text, context))
        path_edits.extend(
            _compiler_plugin_target_edits(
                path,
                text,
                context,
                add_if_absent=not path_edits,
            )
        )
        edits.extend(path_edits)
    return _dedupe_edits(edits)


def maven_upgrade_compiler_plugin_edits(
    pom_texts: dict[str, str],
    context: MigrationContext,
) -> list[dict[str, Any]]:
    """Generate guarded maven-compiler-plugin upgrades."""

    edits: list[dict[str, Any]] = []
    for path, text in pom_texts.items():
        edits.extend(_compiler_plugin_target_edits(path, text, context))
    return _dedupe_edits(edits)


def maven_upgrade_surefire_plugin_edits(
    pom_texts: dict[str, str],
    context: MigrationContext,
) -> list[dict[str, Any]]:
    """Generate guarded maven-surefire-plugin add-or-upgrade edits."""

    edits = _plugin_version_to_target_edits(
        pom_texts,
        plugin_artifact="maven-surefire-plugin",
        target_version=context.compatibility.surefire_min,
    )
    if edits:
        return _dedupe_edits(edits)
    return _add_plugin_if_absent_edits(
        pom_texts,
        plugin_artifact="maven-surefire-plugin",
        plugin_xml=_surefire_plugin_xml(context),
    )


def maven_add_or_upgrade_surefire_for_target_java_edits(
    pom_texts: dict[str, str],
    context: MigrationContext,
) -> list[dict[str, Any]]:
    """Alias with the operator's explicit target-aware semantics."""

    return maven_upgrade_surefire_plugin_edits(pom_texts, context)


def maven_upgrade_lombok_edits(
    pom_texts: dict[str, str],
    context: MigrationContext,
) -> list[dict[str, Any]]:
    """Upgrade Lombok coordinates known to fail against target javac internals."""

    edits = _property_version_edits(
        pom_texts,
        property_names=("lombok.version",),
        target_version=context.compatibility.lombok_min,
    )
    edits.extend(
        _property_version_edits(
            pom_texts,
            property_names=("lombok.plugin.version",),
            target_version=context.compatibility.lombok_maven_plugin_min,
        )
    )
    edits.extend(
        _dependency_version_to_target_edits(
            pom_texts,
            dependency_artifact="lombok",
            target_version=context.compatibility.lombok_min,
            group_marker="<groupId>org.projectlombok</groupId>",
        )
    )
    edits.extend(
        _plugin_version_to_target_edits(
            pom_texts,
            plugin_artifact="lombok-maven-plugin",
            target_version=context.compatibility.lombok_maven_plugin_min,
        )
    )
    return _dedupe_edits(edits)


def maven_upgrade_lombok_for_target_java_edits(
    pom_texts: dict[str, str],
    context: MigrationContext,
) -> list[dict[str, Any]]:
    """Alias with the operator's explicit target-aware semantics."""

    return maven_upgrade_lombok_edits(pom_texts, context)


def maven_upgrade_bundle_plugin_edits(
    pom_texts: dict[str, str],
    context: MigrationContext,
) -> list[dict[str, Any]]:
    """Upgrade Felix maven-bundle-plugin for target-Java bnd failures."""

    return _plugin_version_to_target_edits(
        pom_texts,
        plugin_artifact="maven-bundle-plugin",
        target_version=context.compatibility.bundle_plugin_min,
    )


def maven_add_javafx_dependencies_edits(
    pom_texts: dict[str, str],
    context: MigrationContext,
    *,
    feedback_text: str = "",
) -> list[dict[str, Any]]:
    """Add JavaFX dependencies when JavaFX was removed from the target JDK."""

    if context.target_language.lower() != "java" or context.target_java < 11:
        return []
    wants_fxml = "fxml" in feedback_text.lower()
    dependency_xml = _javafx_dependencies_xml(context, include_fxml=wants_fxml)
    edits: list[dict[str, Any]] = []
    for path, text in pom_texts.items():
        missing_controls = "javafx-controls" not in text
        missing_fxml = wants_fxml and "javafx-fxml" not in text
        if not missing_controls and not missing_fxml:
            continue
        xml = dependency_xml
        if not missing_controls:
            xml = _javafx_dependency_xml("javafx-fxml", context.compatibility.javafx_version)
        elif not missing_fxml:
            xml = _javafx_dependency_xml("javafx-controls", context.compatibility.javafx_version)
        edit = _insert_dependencies_xml_edit(path=path, text=text, dependency_xml=xml)
        if edit is not None:
            edits.append(edit)
            break
    return edits


def replace_sun_misc_base64_edits(
    java_texts: dict[str, str],
    context: MigrationContext,
) -> list[dict[str, Any]]:
    """Replace simple sun.misc Base64 usages with java.util.Base64."""

    if context.target_language.lower() != "java" or context.target_java < 9:
        return []
    edits: list[dict[str, Any]] = []
    for path, text in java_texts.items():
        if "sun.misc.BASE64Encoder" not in text and "sun.misc.BASE64Decoder" not in text:
            continue
        updated = _replace_simple_sun_misc_base64_text(text)
        if updated is None or updated == text:
            continue
        edits.append(
            {
                "type": "replace_text",
                "path": path,
                "old": text,
                "new": updated,
                "expected_replacements": 1,
                "allow_multiple": False,
                "rationale": (
                    "Simple sun.misc BASE64Encoder/BASE64Decoder migration to "
                    "java.util.Base64 for the target Java runtime."
                ),
            }
        )
    return edits


def maven_add_jaxb_dependency_edits(
    pom_texts: dict[str, str],
    context: MigrationContext,
    *,
    binding_namespace: str | None = None,
) -> list[dict[str, Any]]:
    """Insert JAXB API dependency when an existing dependencies block exists."""

    edits: list[dict[str, Any]] = []
    namespace = binding_namespace or context.compatibility.jaxb_namespace_default
    dependency_xml = (
        JAVAX_JAXB_DEPENDENCY_XML
        if namespace == "javax"
        else JAXB_DEPENDENCY_XML
    )
    dependency_marker = (
        "jaxb-api" if namespace == "javax" else "jakarta.xml.bind-api"
    )
    for path, text in pom_texts.items():
        if dependency_marker in text:
            continue
        old = "  </dependencies>"
        if old not in text:
            old = "</dependencies>"
        result = ExactReplaceText().apply(
            current_text=text,
            old=old,
            new=f"{dependency_xml}{old}",
            expected_replacements=1,
            allow_multiple=False,
        )
        if not result.applied:
            continue
        edits.append(
            {
                "type": "replace_text",
                "path": path,
                "old": old,
                "new": f"{dependency_xml}{old}",
                "expected_replacements": 1,
                "allow_multiple": False,
            }
        )
        break
    return edits


def _compiler_release_property_insert_edits(
    path: str,
    text: str,
    context: MigrationContext,
) -> list[dict[str, Any]]:
    """Insert maven.compiler.release when no compiler property exists."""

    property_names = (
        "maven.compiler.release",
        "maven.compiler.source",
        "maven.compiler.target",
        "java.version",
    )
    if any(f"<{name}>" in text for name in property_names):
        return []
    property_xml = (
        f"    <maven.compiler.release>{context.target_java}</maven.compiler.release>\n"
    )
    if "</properties>" in text:
        old = "  </properties>" if "  </properties>" in text else "</properties>"
        return [
            {
                "type": "replace_text",
                "path": path,
                "old": old,
                "new": f"{property_xml}{old}",
                "expected_replacements": 1,
                "allow_multiple": False,
            }
        ]
    opening = _project_opening_tag(text)
    if opening is None:
        return []
    properties_block = (
        "\n  <properties>\n"
        f"{property_xml}"
        "  </properties>"
    )
    return [
        {
            "type": "replace_text",
            "path": path,
            "old": opening,
            "new": f"{opening}{properties_block}",
            "expected_replacements": 1,
            "allow_multiple": False,
        }
    ]


def _compiler_plugin_target_edits(
    path: str,
    text: str,
    context: MigrationContext,
    *,
    add_if_absent: bool = True,
) -> list[dict[str, Any]]:
    artifact_marker = "<artifactId>maven-compiler-plugin</artifactId>"
    blocks = _plugin_blocks_for_artifact(text, artifact_marker)
    edits: list[dict[str, Any]] = []
    if not blocks:
        if not add_if_absent:
            return []
        return _add_plugin_if_absent_edits(
            {path: text},
            plugin_artifact="maven-compiler-plugin",
            plugin_xml=_compiler_plugin_xml(context),
        )
    for block in blocks:
        updated = _plugin_block_with_target_version(
            block,
            target_version=context.compatibility.compiler_plugin_min,
        )
        updated = _compiler_plugin_block_with_release(updated, context)
        if updated == block:
            continue
        edits.append(
            {
                "type": "replace_text",
                "path": path,
                "old": block,
                "new": updated,
                "expected_replacements": 1,
                "allow_multiple": False,
            }
        )
        break
    return edits


def _compiler_plugin_block_with_release(
    block: str,
    context: MigrationContext,
) -> str:
    target = str(context.target_java)
    release_match = re.search(r"<release>([^<]+)</release>", block)
    if release_match is not None:
        current = release_match.group(1).strip()
        if current == target:
            return block
        return block.replace(
            release_match.group(0),
            f"<release>{target}</release>",
            1,
        )
    release_line = f"          <release>{target}</release>\n"
    if "</configuration>" in block:
        closing = "        </configuration>" if "        </configuration>" in block else "</configuration>"
        return block.replace(closing, f"{release_line}{closing}", 1)
    return block.replace(
        "      </plugin>" if "      </plugin>" in block else "</plugin>",
        "        <configuration>\n"
        f"{release_line}"
        "        </configuration>\n"
        + ("      </plugin>" if "      </plugin>" in block else "</plugin>"),
        1,
    )


def _plugin_block_with_target_version(block: str, *, target_version: str) -> str:
    match = re.search(r"<version>([^<]+)</version>", block)
    if match is None:
        artifact_match = re.search(r"(<artifactId>[^<]+</artifactId>)", block)
        if artifact_match is None:
            return block
        return block.replace(
            artifact_match.group(1),
            f"{artifact_match.group(1)}\n        <version>{target_version}</version>",
            1,
        )
    current_version = match.group(1).strip()
    if current_version.startswith("${"):
        return block
    if current_version == target_version or not _version_less_than(
        current_version,
        target_version,
    ):
        return block
    return block.replace(match.group(0), f"<version>{target_version}</version>", 1)


def _add_plugin_if_absent_edits(
    pom_texts: dict[str, str],
    *,
    plugin_artifact: str,
    plugin_xml: str,
) -> list[dict[str, Any]]:
    artifact_marker = f"<artifactId>{plugin_artifact}</artifactId>"
    edits: list[dict[str, Any]] = []
    for path, text in pom_texts.items():
        if artifact_marker in text:
            continue
        edit = _insert_plugin_xml_edit(path=path, text=text, plugin_xml=plugin_xml)
        if edit is not None:
            edits.append(edit)
            break
    return edits


def _insert_plugin_xml_edit(
    *,
    path: str,
    text: str,
    plugin_xml: str,
) -> dict[str, Any] | None:
    if "</plugins>" in text:
        old = "    </plugins>" if "    </plugins>" in text else "</plugins>"
        return {
            "type": "replace_text",
            "path": path,
            "old": old,
            "new": f"{plugin_xml}{old}",
            "expected_replacements": 1,
            "allow_multiple": False,
        }
    if "</build>" in text:
        old = "  </build>" if "  </build>" in text else "</build>"
        plugins_xml = f"    <plugins>\n{plugin_xml}    </plugins>\n"
        return {
            "type": "replace_text",
            "path": path,
            "old": old,
            "new": f"{plugins_xml}{old}",
            "expected_replacements": 1,
            "allow_multiple": False,
        }
    opening = _project_opening_tag(text)
    if opening is None:
        return None
    build_xml = f"\n  <build>\n    <plugins>\n{plugin_xml}    </plugins>\n  </build>"
    return {
        "type": "replace_text",
        "path": path,
        "old": opening,
        "new": f"{opening}{build_xml}",
        "expected_replacements": 1,
        "allow_multiple": False,
    }


def _insert_dependencies_xml_edit(
    *,
    path: str,
    text: str,
    dependency_xml: str,
) -> dict[str, Any] | None:
    if "</dependencies>" in text:
        old = "  </dependencies>" if "  </dependencies>" in text else "</dependencies>"
        return {
            "type": "replace_text",
            "path": path,
            "old": old,
            "new": f"{dependency_xml}{old}",
            "expected_replacements": 1,
            "allow_multiple": False,
        }
    opening = _project_opening_tag(text)
    if opening is None:
        return None
    dependencies_xml = f"\n  <dependencies>\n{dependency_xml}  </dependencies>"
    return {
        "type": "replace_text",
        "path": path,
        "old": opening,
        "new": f"{opening}{dependencies_xml}",
        "expected_replacements": 1,
        "allow_multiple": False,
    }


def _project_opening_tag(text: str) -> str | None:
    match = re.search(r"<project\b[^>]*>", text)
    return match.group(0) if match else None


def _compiler_plugin_xml(context: MigrationContext) -> str:
    return (
        "      <plugin>\n"
        "        <groupId>org.apache.maven.plugins</groupId>\n"
        "        <artifactId>maven-compiler-plugin</artifactId>\n"
        f"        <version>{context.compatibility.compiler_plugin_min}</version>\n"
        "        <configuration>\n"
        f"          <release>{context.target_java}</release>\n"
        "        </configuration>\n"
        "      </plugin>\n"
    )


def _surefire_plugin_xml(context: MigrationContext) -> str:
    return (
        "      <plugin>\n"
        "        <groupId>org.apache.maven.plugins</groupId>\n"
        "        <artifactId>maven-surefire-plugin</artifactId>\n"
        f"        <version>{context.compatibility.surefire_min}</version>\n"
        "      </plugin>\n"
    )


def _javafx_dependency_xml(artifact_id: str, version: str) -> str:
    return (
        "    <dependency>\n"
        "      <groupId>org.openjfx</groupId>\n"
        f"      <artifactId>{artifact_id}</artifactId>\n"
        f"      <version>{version}</version>\n"
        "    </dependency>\n"
    )


def _javafx_dependencies_xml(
    context: MigrationContext,
    *,
    include_fxml: bool,
) -> str:
    xml = _javafx_dependency_xml("javafx-controls", context.compatibility.javafx_version)
    if include_fxml:
        xml += _javafx_dependency_xml("javafx-fxml", context.compatibility.javafx_version)
    return xml


def _replace_simple_sun_misc_base64_text(text: str) -> str | None:
    updated = text
    encoder_import = "import sun.misc.BASE64Encoder;\n"
    decoder_import = "import sun.misc.BASE64Decoder;\n"
    if encoder_import not in updated and decoder_import not in updated:
        return None
    updated = updated.replace(encoder_import, "")
    updated = updated.replace(decoder_import, "")
    encoder_re = re.compile(r"new\s+BASE64Encoder\(\)\.encode\(([^()\n;]+)\)")
    decoder_re = re.compile(r"new\s+BASE64Decoder\(\)\.decodeBuffer\(([^()\n;]+)\)")
    updated = encoder_re.sub(r"Base64.getEncoder().encodeToString(\1)", updated)
    updated = decoder_re.sub(r"Base64.getDecoder().decode(\1)", updated)
    if "BASE64Encoder" in updated or "BASE64Decoder" in updated:
        return None
    if "java.util.Base64" not in updated:
        import_match = re.search(r"(^import\s+[^;]+;\n)", updated, flags=re.MULTILINE)
        if import_match:
            updated = updated.replace(
                import_match.group(1),
                f"{import_match.group(1)}import java.util.Base64;\n",
                1,
            )
        else:
            package_match = re.search(r"(^package\s+[^;]+;\n)", updated, flags=re.MULTILINE)
            if package_match:
                updated = updated.replace(
                    package_match.group(1),
                    f"{package_match.group(1)}\nimport java.util.Base64;\n",
                    1,
                )
            else:
                updated = f"import java.util.Base64;\n{updated}"
    return updated


def _plugin_version_edits(
    pom_texts: dict[str, str],
    *,
    plugin_artifact: str,
    replacements: Iterable[tuple[str, str]],
) -> list[dict[str, Any]]:
    edits: list[dict[str, Any]] = []
    artifact_marker = f"<artifactId>{plugin_artifact}</artifactId>"
    for path, text in pom_texts.items():
        for block in _plugin_blocks_for_artifact(text, artifact_marker):
            for old, new in replacements:
                result = ExactReplaceText().apply(
                    current_text=block,
                    old=old,
                    new=new,
                    expected_replacements=1,
                    allow_multiple=False,
                )
                if not result.applied:
                    continue
                upgraded_block = result.text
                text_result = ExactReplaceText().apply(
                    current_text=text,
                    old=block,
                    new=upgraded_block,
                    expected_replacements=1,
                    allow_multiple=False,
                )
                if not text_result.applied:
                    continue
                edits.append(
                    {
                        "type": "replace_text",
                        "path": path,
                        "old": block,
                        "new": upgraded_block,
                        "expected_replacements": 1,
                        "allow_multiple": False,
                    }
                )
                break
            if edits and edits[-1]["path"] == path:
                break
    return edits


def _plugin_version_to_target_edits(
    pom_texts: dict[str, str],
    *,
    plugin_artifact: str,
    target_version: str,
) -> list[dict[str, Any]]:
    edits: list[dict[str, Any]] = []
    artifact_marker = f"<artifactId>{plugin_artifact}</artifactId>"
    for path, text in pom_texts.items():
        for block in _plugin_blocks_for_artifact(text, artifact_marker):
            edit = _block_version_to_target_edit(
                path=path,
                text=text,
                block=block,
                target_version=target_version,
            )
            if edit is not None:
                edits.append(edit)
                break
    return edits


def _dependency_version_to_target_edits(
    pom_texts: dict[str, str],
    *,
    dependency_artifact: str,
    target_version: str,
    group_marker: str | None = None,
) -> list[dict[str, Any]]:
    edits: list[dict[str, Any]] = []
    artifact_marker = f"<artifactId>{dependency_artifact}</artifactId>"
    for path, text in pom_texts.items():
        for block in _dependency_blocks_for_artifact(
            text,
            artifact_marker=artifact_marker,
            group_marker=group_marker,
        ):
            edit = _block_version_to_target_edit(
                path=path,
                text=text,
                block=block,
                target_version=target_version,
            )
            if edit is not None:
                edits.append(edit)
                break
    return edits


def _parent_version_to_target_edits(
    pom_texts: dict[str, str],
    *,
    parent_artifact: str,
    target_version: str,
    group_marker: str | None = None,
) -> list[dict[str, Any]]:
    edits: list[dict[str, Any]] = []
    artifact_marker = f"<artifactId>{parent_artifact}</artifactId>"
    for path, text in pom_texts.items():
        for block in _parent_blocks_for_artifact(
            text,
            artifact_marker=artifact_marker,
            group_marker=group_marker,
        ):
            edit = _block_version_to_target_edit(
                path=path,
                text=text,
                block=block,
                target_version=target_version,
            )
            if edit is not None:
                edits.append(edit)
                break
    return edits


def _property_version_edits(
    pom_texts: dict[str, str],
    *,
    property_names: Iterable[str],
    target_version: str,
) -> list[dict[str, Any]]:
    edits: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for path, text in pom_texts.items():
        for property_name in property_names:
            pattern = (
                rf"<{re.escape(property_name)}>([^<]+)</{re.escape(property_name)}>"
            )
            for match in re.finditer(pattern, text):
                current_version = match.group(1).strip()
                if current_version == target_version:
                    continue
                if current_version.startswith("${") or not _version_less_than(
                    current_version, target_version
                ):
                    continue
                old = match.group(0)
                if (path, old) in seen:
                    continue
                seen.add((path, old))
                new = (
                    f"<{property_name}>{target_version}</{property_name}>"
                )
                result = ExactReplaceText().apply(
                    current_text=text,
                    old=old,
                    new=new,
                    expected_replacements=1,
                    allow_multiple=True,
                )
                if not result.applied:
                    continue
                edits.append(
                    {
                        "type": "replace_text",
                        "path": path,
                        "old": old,
                        "new": new,
                        "expected_replacements": result.replacements,
                        "allow_multiple": True,
                    }
                )
    return edits


def _block_version_to_target_edit(
    *,
    path: str,
    text: str,
    block: str,
    target_version: str,
) -> dict[str, Any] | None:
    match = re.search(r"<version>([^<]+)</version>", block)
    if match is None:
        return None
    current_version = match.group(1).strip()
    if current_version == target_version or current_version.startswith("${"):
        return None
    if not _version_less_than(current_version, target_version):
        return None
    old_version_tag = match.group(0)
    new_version_tag = f"<version>{target_version}</version>"
    block_result = ExactReplaceText().apply(
        current_text=block,
        old=old_version_tag,
        new=new_version_tag,
        expected_replacements=1,
        allow_multiple=False,
    )
    if not block_result.applied:
        return None
    text_result = ExactReplaceText().apply(
        current_text=text,
        old=block,
        new=block_result.text,
        expected_replacements=1,
        allow_multiple=False,
    )
    if not text_result.applied:
        return None
    return {
        "type": "replace_text",
        "path": path,
        "old": block,
        "new": block_result.text,
        "expected_replacements": 1,
        "allow_multiple": False,
    }


def _version_less_than(current: str, target: str) -> bool:
    current_parts = _version_key(current)
    target_parts = _version_key(target)
    if current_parts is None or target_parts is None:
        return False
    return current_parts < target_parts


def _version_key(value: str) -> tuple[int, ...] | None:
    numbers = re.findall(r"\d+", value)
    if not numbers:
        return None
    return tuple(int(part) for part in numbers)


def _java_version_tokens(version: int) -> tuple[str, ...]:
    if int(version) == 8:
        return ("1.8", "8")
    return (str(int(version)),)


def _dedupe_edits(edits: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for edit in edits:
        key = (str(edit.get("path", "")), str(edit.get("old", "")))
        if key in seen:
            continue
        seen.add(key)
        unique.append(edit)
    return unique


def _plugin_blocks_for_artifact(text: str, artifact_marker: str) -> tuple[str, ...]:
    blocks: list[str] = []
    for match in re.finditer(r"<plugin\b[^>]*>.*?</plugin>", text, flags=re.DOTALL):
        block = match.group(0)
        if artifact_marker in block:
            blocks.append(block)
    return tuple(blocks)


def _dependency_blocks_for_artifact(
    text: str,
    *,
    artifact_marker: str,
    group_marker: str | None = None,
) -> tuple[str, ...]:
    blocks: list[str] = []
    for match in re.finditer(r"<dependency\b[^>]*>.*?</dependency>", text, flags=re.DOTALL):
        block = match.group(0)
        if artifact_marker in block and (group_marker is None or group_marker in block):
            blocks.append(block)
    return tuple(blocks)


def _parent_blocks_for_artifact(
    text: str,
    *,
    artifact_marker: str,
    group_marker: str | None = None,
) -> tuple[str, ...]:
    blocks: list[str] = []
    for match in re.finditer(r"<parent\b[^>]*>.*?</parent>", text, flags=re.DOTALL):
        block = match.group(0)
        if artifact_marker in block and (group_marker is None or group_marker in block):
            blocks.append(block)
    return tuple(blocks)


def _looks_like_lombok_target_failure(
    *,
    feedback: FeedbackDigest,
    action: str,
    full_text: str,
    pom_texts: dict[str, str],
) -> bool:
    if not _pom_contains(pom_texts, "org.projectlombok") and "lombok" not in full_text:
        return False
    if any(
        token in full_text
        for token in (
            "lombok",
            "delombok",
            "javacprocessingenvironment",
            "com.sun.tools.javac",
            "jdk.compiler",
            "illegalaccesserror",
        )
    ):
        return True
    return (
        action in {"fix_compile_error", "select_compile_operator"}
        and str(feedback.failure_type or "") in {"compile_error", "build_failure"}
    )


def _looks_like_compiler_release_failure(
    *,
    action: str,
    full_text: str,
) -> bool:
    if "unsupported class file major version" in full_text and any(
        token in full_text for token in ("spring", "asm", "cglib", "bytecode")
    ):
        return False
    if action in {"ensure_maven_compiler_release", "select_compile_operator"}:
        return True
    return any(
        token in full_text
        for token in ("source option", "target option", "release", "class_version")
    )


def _looks_like_maven_bundle_felix_failure(
    *,
    action: str,
    full_text: str,
    pom_texts: dict[str, str],
) -> bool:
    if not _pom_contains(pom_texts, "maven-bundle-plugin"):
        return False
    if action == "upgrade_bundle_plugin":
        return True
    return any(
        token in full_text
        for token in (
            "maven-bundle-plugin",
            "bundleplugin",
            "org.apache.felix",
            "aQute.bnd".lower(),
            "concurrentmodificationexception",
        )
    )


def _looks_like_javafx_failure(
    *,
    action: str,
    full_text: str,
    context: MigrationContext,
) -> bool:
    if context.target_language.lower() != "java" or context.target_java < 11:
        return False
    if action == "add_javafx_dependencies":
        return True
    return any(
        token in full_text
        for token in (
            "javafx.application.application",
            "javafx.stage.stage",
            "javafx.scene",
            "stagestyle",
            "observablevalue",
            "observablevaluebase",
            "invalidationlistener",
            "changelistener",
            "listchangelistener",
            "mapchangelistener",
            "loadexception",
            "textfield",
            "pane",
            "javafx_missing",
        )
    )


def _looks_like_sun_misc_base64_failure(
    *,
    full_text: str,
    java_texts: dict[str, str],
    context: MigrationContext,
) -> bool:
    if context.target_language.lower() != "java" or context.target_java < 9:
        return False
    if "sun.misc.base64" in full_text or "base64encoder" in full_text:
        return True
    return any(
        "sun.misc.BASE64Encoder" in text or "sun.misc.BASE64Decoder" in text
        for text in java_texts.values()
    )


def _pom_contains(pom_texts: dict[str, str], needle: str) -> bool:
    return any(needle in text for text in pom_texts.values())


def _pom_texts(observation: Observation) -> dict[str, str]:
    live = observation.data.get("__live_files__")
    pom_texts: dict[str, str] = {}
    if isinstance(live, dict):
        for path, text in live.items():
            if str(path).endswith("pom.xml"):
                pom_texts[str(path)] = str(text)
    # Unit tests and synthetic runs may pass pom_texts directly.
    raw = observation.data.get("pom_texts")
    if isinstance(raw, dict):
        for path, text in raw.items():
            if str(path).endswith("pom.xml"):
                pom_texts.setdefault(str(path), str(text))
    return pom_texts


def _java_texts(observation: Observation) -> dict[str, str]:
    live = observation.data.get("__live_files__")
    java_texts: dict[str, str] = {}
    if isinstance(live, dict):
        for path, text in live.items():
            if str(path).endswith(".java"):
                java_texts[str(path)] = str(text)
    raw = observation.data.get("java_texts")
    if isinstance(raw, dict):
        for path, text in raw.items():
            if str(path).endswith(".java"):
                java_texts.setdefault(str(path), str(text))
    return java_texts


def _feedback_text(feedback: FeedbackDigest) -> str:
    return "\n".join(
        [
            str(feedback.failure_type or ""),
            str(feedback.summary or ""),
            "\n".join(str(x) for x in feedback.evidence),
        ]
    ).lower()


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
