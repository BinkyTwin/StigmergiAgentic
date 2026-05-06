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


def _plugin_blocks_for_artifact(text: str, artifact_marker: str) -> tuple[str, ...]:
    blocks: list[str] = []
    for match in re.finditer(r"<plugin\b[^>]*>.*?</plugin>", text, flags=re.DOTALL):
        block = match.group(0)
        if artifact_marker in block:
            blocks.append(block)
    return tuple(blocks)


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
    "JAVA17_POM_REPLACEMENTS",
    "maven_add_jaxb_dependency_edits",
    "maven_compiler_release_edits",
    "maven_upgrade_compiler_plugin_edits",
    "maven_upgrade_surefire_plugin_edits",
    "migrationbench_operator_candidates",
]
