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


JAVA17_POM_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("<maven.compiler.source>1.8</maven.compiler.source>", "<maven.compiler.source>17</maven.compiler.source>"),
    ("<maven.compiler.target>1.8</maven.compiler.target>", "<maven.compiler.target>17</maven.compiler.target>"),
    ("<maven.compiler.release>8</maven.compiler.release>", "<maven.compiler.release>17</maven.compiler.release>"),
    ("<source>1.8</source>", "<source>17</source>"),
    ("<target>1.8</target>", "<target>17</target>"),
    ("<release>8</release>", "<release>17</release>"),
    ("<java.version>1.8</java.version>", "<java.version>17</java.version>"),
    ("<java.version>8</java.version>", "<java.version>17</java.version>"),
)


COMPILER_PLUGIN_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("<version>2.3.2</version>", "<version>3.11.0</version>"),
    ("<version>3.1</version>", "<version>3.11.0</version>"),
    ("<version>3.5.1</version>", "<version>3.11.0</version>"),
    ("<version>3.6.0</version>", "<version>3.11.0</version>"),
    ("<version>3.8.0</version>", "<version>3.11.0</version>"),
)


SUREFIRE_PLUGIN_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("<version>2.12.4</version>", "<version>3.2.5</version>"),
    ("<version>2.19.1</version>", "<version>3.2.5</version>"),
    ("<version>2.20.1</version>", "<version>3.2.5</version>"),
    ("<version>2.22.2</version>", "<version>3.2.5</version>"),
)


LOMBOK_VERSION_TARGET = "1.18.30"
LOMBOK_MAVEN_PLUGIN_VERSION_TARGET = "1.18.20.0"
SPRING_BOOT_JAVA17_PARENT_TARGET = "2.7.18"
BUNDLE_PLUGIN_VERSION_TARGET = "5.1.9"


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

    pom_texts = _pom_texts(observation)
    if not pom_texts:
        return ()
    edits: list[dict[str, Any]] = []
    operator_ids: list[str] = []
    action = affordance.action_type if affordance is not None else ""
    full_text = _feedback_text(feedback)

    if _looks_like_lombok_java17_failure(
        feedback=feedback,
        action=action,
        full_text=full_text,
        pom_texts=pom_texts,
    ):
        lombok_edits = maven_upgrade_lombok_java17_edits(pom_texts)
        if lombok_edits:
            edits.extend(lombok_edits)
            operator_ids.append("MavenUpgradeLombokJava17")

    if _looks_like_spring_boot_asm_java17_failure(
        feedback=feedback,
        action=action,
        full_text=full_text,
        pom_texts=pom_texts,
    ):
        spring_edits = maven_upgrade_spring_boot_java17_edits(pom_texts)
        if spring_edits:
            edits.extend(spring_edits)
            operator_ids.append("MavenUpgradeSpringBootJava17")

    if _looks_like_maven_bundle_felix_failure(
        full_text=full_text,
        pom_texts=pom_texts,
    ):
        bundle_edits = maven_upgrade_bundle_plugin_edits(pom_texts)
        if bundle_edits:
            edits.extend(bundle_edits)
            operator_ids.append("MavenUpgradeBundlePlugin")

    if action in {"set_maven_compiler_release", "select_compile_operator"} or any(
        token in full_text for token in ("compile", "source", "target", "release", "class_version")
    ):
        new_edits = maven_compiler_release_edits(pom_texts)
        if new_edits:
            edits.extend(new_edits)
            operator_ids.append("MavenSetCompilerRelease")
        plugin_edits = maven_upgrade_compiler_plugin_edits(pom_texts)
        if plugin_edits:
            edits.extend(plugin_edits)
            operator_ids.append("MavenUpgradeCompilerPlugin")

    if action in {"interpret_official_eval", "preserve_test_count"} or any(
        token in full_text for token in ("official", "#tests=-2", "surefire", "test summary")
    ):
        surefire_edits = maven_upgrade_surefire_plugin_edits(pom_texts)
        if surefire_edits:
            edits.extend(surefire_edits)
            operator_ids.append("MavenUpgradeSurefirePlugin")

    if action == "add_missing_dependency" or any(
        token in full_text for token in ("javax.xml.bind", "jaxb", "dependency_resolution")
    ):
        dependency_edits = maven_add_jaxb_dependency_edits(
            pom_texts,
            binding_namespace=(
                "javax"
                if "javax.xml.bind" in full_text and "jakarta.xml.bind" not in full_text
                else "jakarta"
            ),
        )
        if dependency_edits:
            edits.extend(dependency_edits)
            operator_ids.append("MavenAddJaxbDependency")

    # Last conservative fallback for MigrationBench: if an affordance exists
    # but no specialized pattern matched, try Java 17 POM declarations only.
    if not edits and affordance is not None:
        new_edits = maven_compiler_release_edits(pom_texts)
        if new_edits:
            edits.extend(new_edits)
            operator_ids.append("MavenSetCompilerRelease")

    if not edits:
        return ()

    source_affordance_id = affordance.affordance_id if affordance is not None else None
    invocation = OperatorInvocation(
        operator_id="+".join(operator_ids) if operator_ids else "MigrationBenchOperator",
        params={
            "failure_type": feedback.failure_type,
            "action_type": action,
            "edit_count": len(edits),
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
                    "expected_build_command": "mvn clean verify",
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


def maven_compiler_release_edits(pom_texts: dict[str, str]) -> list[dict[str, Any]]:
    """Generate exact Java 17 compiler edits only when old spans are present."""

    edits: list[dict[str, Any]] = []
    for path, text in pom_texts.items():
        for old, new in JAVA17_POM_REPLACEMENTS:
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


def maven_upgrade_compiler_plugin_edits(
    pom_texts: dict[str, str],
) -> list[dict[str, Any]]:
    """Generate guarded maven-compiler-plugin upgrades."""

    return _plugin_version_edits(
        pom_texts,
        plugin_artifact="maven-compiler-plugin",
        replacements=COMPILER_PLUGIN_REPLACEMENTS,
    )


def maven_upgrade_surefire_plugin_edits(
    pom_texts: dict[str, str],
) -> list[dict[str, Any]]:
    """Generate guarded maven-surefire-plugin upgrades."""

    return _plugin_version_edits(
        pom_texts,
        plugin_artifact="maven-surefire-plugin",
        replacements=SUREFIRE_PLUGIN_REPLACEMENTS,
    )


def maven_upgrade_lombok_java17_edits(
    pom_texts: dict[str, str],
) -> list[dict[str, Any]]:
    """Upgrade Lombok coordinates known to fail against Java 17 javac internals."""

    edits = _property_version_edits(
        pom_texts,
        property_names=("lombok.version",),
        target_version=LOMBOK_VERSION_TARGET,
    )
    edits.extend(
        _property_version_edits(
            pom_texts,
            property_names=("lombok.plugin.version",),
            target_version=LOMBOK_MAVEN_PLUGIN_VERSION_TARGET,
        )
    )
    edits.extend(
        _dependency_version_to_target_edits(
            pom_texts,
            dependency_artifact="lombok",
            target_version=LOMBOK_VERSION_TARGET,
            group_marker="<groupId>org.projectlombok</groupId>",
        )
    )
    edits.extend(
        _plugin_version_to_target_edits(
            pom_texts,
            plugin_artifact="lombok-maven-plugin",
            target_version=LOMBOK_MAVEN_PLUGIN_VERSION_TARGET,
        )
    )
    return _dedupe_edits(edits)


def maven_upgrade_spring_boot_java17_edits(
    pom_texts: dict[str, str],
) -> list[dict[str, Any]]:
    """Upgrade old Spring Boot 2.x parents that cannot read Java 17 class files."""

    edits = _property_version_edits(
        pom_texts,
        property_names=("spring.boot.version", "spring-boot.version"),
        target_version=SPRING_BOOT_JAVA17_PARENT_TARGET,
    )
    edits.extend(
        _parent_version_to_target_edits(
            pom_texts,
            parent_artifact="spring-boot-starter-parent",
            target_version=SPRING_BOOT_JAVA17_PARENT_TARGET,
            group_marker="<groupId>org.springframework.boot</groupId>",
        )
    )
    return _dedupe_edits(edits)


def maven_upgrade_bundle_plugin_edits(
    pom_texts: dict[str, str],
) -> list[dict[str, Any]]:
    """Upgrade Felix maven-bundle-plugin for Java 17/bnd test-time failures."""

    return _plugin_version_to_target_edits(
        pom_texts,
        plugin_artifact="maven-bundle-plugin",
        target_version=BUNDLE_PLUGIN_VERSION_TARGET,
    )


def maven_add_jaxb_dependency_edits(
    pom_texts: dict[str, str],
    *,
    binding_namespace: str = "jakarta",
) -> list[dict[str, Any]]:
    """Insert JAXB API dependency when an existing dependencies block exists."""

    edits: list[dict[str, Any]] = []
    dependency_xml = (
        JAVAX_JAXB_DEPENDENCY_XML
        if binding_namespace == "javax"
        else JAXB_DEPENDENCY_XML
    )
    dependency_marker = (
        "jaxb-api" if binding_namespace == "javax" else "jakarta.xml.bind-api"
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


def _looks_like_lombok_java17_failure(
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


def _looks_like_spring_boot_asm_java17_failure(
    *,
    feedback: FeedbackDigest,
    action: str,
    full_text: str,
    pom_texts: dict[str, str],
) -> bool:
    if not _pom_contains(pom_texts, "spring-boot-starter-parent"):
        return False
    if "unsupported class file major version 61" in full_text:
        return True
    if "asm classreader" in full_text:
        return True
    return (
        action == "set_maven_compiler_release"
        and str(feedback.failure_type or "") == "class_version_error"
    )


def _looks_like_maven_bundle_felix_failure(
    *,
    full_text: str,
    pom_texts: dict[str, str],
) -> bool:
    if not _pom_contains(pom_texts, "maven-bundle-plugin"):
        return False
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


def _feedback_text(feedback: FeedbackDigest) -> str:
    return "\n".join(
        [
            str(feedback.failure_type or ""),
            str(feedback.summary or ""),
            "\n".join(str(x) for x in feedback.evidence),
        ]
    ).lower()


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
