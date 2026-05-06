"""V11 typed operator guard tests."""

from __future__ import annotations

from adapters_v10.migrationbench.operators import (
    maven_add_jaxb_dependency_edits,
    maven_compiler_release_edits,
)
from core_v10.operators import ExactReplaceText


def test_exact_replace_rejects_absent_old_span() -> None:
    result = ExactReplaceText().apply(
        current_text="alpha beta",
        old="gamma",
        new="delta",
    )

    assert result.applied is False
    assert result.reason == "old_not_present"
    assert result.text == "alpha beta"


def test_maven_compiler_operator_emits_only_proven_spans() -> None:
    pom = "<project><properties><maven.compiler.source>1.8</maven.compiler.source></properties></project>"
    edits = maven_compiler_release_edits({"pom.xml": pom})

    assert edits == [
        {
            "type": "replace_text",
            "path": "pom.xml",
            "old": "<maven.compiler.source>1.8</maven.compiler.source>",
            "new": "<maven.compiler.source>17</maven.compiler.source>",
            "expected_replacements": 1,
            "allow_multiple": True,
        }
    ]


def test_maven_add_jaxb_dependency_requires_dependencies_anchor() -> None:
    assert maven_add_jaxb_dependency_edits({"pom.xml": "<project/>"}) == []

    edits = maven_add_jaxb_dependency_edits(
        {"pom.xml": "<project><dependencies>\n  </dependencies></project>"}
    )

    assert len(edits) == 1
    assert edits[0]["old"] == "  </dependencies>"
    assert "jakarta.xml.bind-api" in edits[0]["new"]
