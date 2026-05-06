"""V11 typed operator guard tests."""

from __future__ import annotations

from adapters_v10.migrationbench.operators import (
    maven_add_jaxb_dependency_edits,
    maven_compiler_release_edits,
    maven_upgrade_compiler_plugin_edits,
    migrationbench_operator_candidates,
)
from core_v10.contracts import (
    Candidate,
    CandidateKind,
    FeedbackDigest,
    Observation,
    RunInstance,
    WorkspaceHandle,
)
from core_v10.strategy_runner import _attach_live_files
from core_v10.operators import ExactReplaceText
from core_v10.stigmergy.records import Affordance


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


def test_maven_add_jaxb_dependency_can_preserve_javax_namespace() -> None:
    edits = maven_add_jaxb_dependency_edits(
        {"pom.xml": "<project><dependencies>\n</dependencies></project>"},
        binding_namespace="javax",
    )

    assert len(edits) == 1
    assert "<groupId>javax.xml.bind</groupId>" in edits[0]["new"]
    assert "<artifactId>jaxb-api</artifactId>" in edits[0]["new"]
    assert "jakarta.xml.bind-api" not in edits[0]["new"]


def test_maven_plugin_upgrade_is_scoped_to_matching_plugin_block() -> None:
    pom = """<project>
  <dependencies>
    <dependency>
      <groupId>demo</groupId>
      <artifactId>not-a-plugin</artifactId>
      <version>3.1</version>
    </dependency>
  </dependencies>
  <build>
    <plugins>
      <plugin>
        <artifactId>maven-compiler-plugin</artifactId>
        <version>3.1</version>
      </plugin>
    </plugins>
  </build>
</project>"""

    edits = maven_upgrade_compiler_plugin_edits({"pom.xml": pom})

    assert len(edits) == 1
    assert edits[0]["old"].lstrip().startswith("<plugin>")
    assert "<artifactId>maven-compiler-plugin</artifactId>" in edits[0]["old"]
    assert "<version>3.11.0</version>" in edits[0]["new"]
    assert "<artifactId>not-a-plugin</artifactId>" not in edits[0]["old"]


def test_migrationbench_operator_candidate_is_child_of_original_candidate() -> None:
    original = Candidate(
        candidate_id="root-c0",
        kind=CandidateKind.PATCH,
        payload={"branch_id": "root-branch"},
        origin="seed",
        parent_id="older-parent",
    )
    feedback = FeedbackDigest(
        candidate_id="root-c0",
        failure_type="compile_error",
        severity="blocking",
        summary="source option 5 is no longer supported",
    )
    observation = Observation(
        summary="pom",
        data={
            "pom_texts": {
                "pom.xml": (
                    "<project><properties>"
                    "<maven.compiler.source>1.8</maven.compiler.source>"
                    "</properties></project>"
                )
            }
        },
    )
    affordance = Affordance(
        affordance_id="aff-compile",
        action_type="set_maven_compiler_release",
        target="pom.xml",
        reason="compile_error",
        priority=1.0,
        expected_worker_kind="maven_compiler_operator",
    )

    candidates = migrationbench_operator_candidates(
        feedback=feedback,
        original=original,
        observation=observation,
        instance=RunInstance(
            instance_id="repo__case",
            adapter_name="migrationbench",
            objective="migrate",
        ),
        affordance=affordance,
    )

    assert len(candidates) == 1
    assert candidates[0].parent_id == original.candidate_id
    assert candidates[0].payload["parent_branch_id"] == "root-branch"


def test_operator_provider_can_read_live_poms_from_workspace_handle(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pom.xml").write_text(
        "<project><dependencies>\n</dependencies></project>",
        encoding="utf-8",
    )
    observation = Observation(
        summary="pom",
        data={"pom_files": ["pom.xml"], "java_files_sample": []},
    )
    workspace = WorkspaceHandle(root=repo, instance_id="repo__case")

    live_observation = _attach_live_files(observation, workspace)

    feedback = FeedbackDigest(
        candidate_id="root-c0",
        failure_type="dependency_resolution_error",
        severity="blocking",
        summary="Could not resolve javax.xml.bind",
        evidence=["javax.xml.bind missing"],
    )
    original = Candidate(
        candidate_id="root-c0",
        kind=CandidateKind.PATCH,
        payload={"branch_id": "root-branch"},
        origin="seed",
    )
    affordance = Affordance(
        affordance_id="aff-dependency",
        action_type="add_missing_dependency",
        target="pom.xml",
        reason="dependency_resolution_error",
        priority=1.0,
        expected_worker_kind="dependency_operator",
    )

    candidates = migrationbench_operator_candidates(
        feedback=feedback,
        original=original,
        observation=live_observation,
        instance=RunInstance(
            instance_id="repo__case",
            adapter_name="migrationbench",
            objective="migrate",
        ),
        affordance=affordance,
    )

    assert len(candidates) == 1
    assert candidates[0].origin == "v11_operator_search"
    assert (
        candidates[0].metadata["operator_invocation"]["operator_id"]
        == "MavenAddJaxbDependency"
    )
