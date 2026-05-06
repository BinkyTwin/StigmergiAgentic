"""V11 typed operator guard tests."""

from __future__ import annotations

import adapters_v10.migrationbench.operators as operators
from adapters_v10.migrationbench.context import MigrationContext
from adapters_v10.migrationbench.operators import (
    maven_add_jaxb_dependency_edits,
    maven_add_javafx_dependencies_edits,
    maven_add_or_upgrade_surefire_for_target_java_edits,
    maven_compiler_release_edits,
    maven_upgrade_bundle_plugin_edits,
    maven_upgrade_compiler_plugin_edits,
    maven_upgrade_lombok_for_target_java_edits,
    maven_upgrade_lombok_edits,
    migrationbench_operator_candidates,
    replace_sun_misc_base64_edits,
    target_java_replacements,
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


def _context(target_java: int = 17) -> MigrationContext:
    return MigrationContext(
        source_language="java",
        source_version=8,
        target_language="java",
        target_version=target_java,
        target_class_major={8: 52, 11: 55, 17: 61, 21: 65}[target_java],
        build_system="maven",
        migration_mode="minimal",
        dependency_policy="minimal",
    )


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
    edits = maven_compiler_release_edits({"pom.xml": pom}, _context())

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


def test_target_java_11_replacements() -> None:
    pom = "<project><properties><java.version>1.8</java.version></properties></project>"
    edits = maven_compiler_release_edits({"pom.xml": pom}, _context(11))

    assert edits[0]["new"] == "<java.version>11</java.version>"
    assert ("<java.version>1.8</java.version>", "<java.version>11</java.version>") in (
        target_java_replacements(_context(11))
    )


def test_target_java_17_replacements() -> None:
    pom = "<project><properties><release>8</release></properties></project>"
    edits = maven_compiler_release_edits({"pom.xml": pom}, _context(17))

    assert edits[0]["new"] == "<release>17</release>"


def test_target_java_21_replacements() -> None:
    pom = "<project><properties><maven.compiler.target>1.8</maven.compiler.target></properties></project>"
    edits = maven_compiler_release_edits({"pom.xml": pom}, _context(21))

    assert edits[0]["new"] == "<maven.compiler.target>21</maven.compiler.target>"


def test_maven_add_jaxb_dependency_requires_dependencies_anchor() -> None:
    assert maven_add_jaxb_dependency_edits({"pom.xml": "<project/>"}, _context()) == []

    edits = maven_add_jaxb_dependency_edits(
        {"pom.xml": "<project><dependencies>\n  </dependencies></project>"},
        _context(),
    )

    assert len(edits) == 1
    assert edits[0]["old"] == "  </dependencies>"
    assert "javax.xml.bind" in edits[0]["new"]


def test_maven_add_jaxb_dependency_can_preserve_javax_namespace() -> None:
    edits = maven_add_jaxb_dependency_edits(
        {"pom.xml": "<project><dependencies>\n</dependencies></project>"},
        _context(),
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

    edits = maven_upgrade_compiler_plugin_edits({"pom.xml": pom}, _context())

    assert len(edits) == 1
    assert edits[0]["old"].lstrip().startswith("<plugin>")
    assert "<artifactId>maven-compiler-plugin</artifactId>" in edits[0]["old"]
    assert "<version>3.11.0</version>" in edits[0]["new"]
    assert "<artifactId>not-a-plugin</artifactId>" not in edits[0]["old"]


def test_maven_ensure_compiler_release_inserts_property_without_marker() -> None:
    pom = "<project><modelVersion>4.0.0</modelVersion></project>"

    edits = maven_compiler_release_edits({"pom.xml": pom}, _context(21))

    joined_new = "\n".join(str(edit["new"]) for edit in edits)
    assert "<maven.compiler.release>21</maven.compiler.release>" in joined_new
    assert "17" not in joined_new


def test_maven_ensure_compiler_release_updates_scoped_plugin_config() -> None:
    pom = """<project>
  <build>
    <plugins>
      <plugin>
        <artifactId>maven-compiler-plugin</artifactId>
        <version>3.1</version>
        <configuration>
          <source>1.8</source>
        </configuration>
      </plugin>
    </plugins>
  </build>
</project>"""

    edits = maven_compiler_release_edits({"pom.xml": pom}, _context(11))

    plugin_edits = [edit for edit in edits if "maven-compiler-plugin" in edit["old"]]
    assert len(plugin_edits) == 1
    assert "<version>3.8.1</version>" in plugin_edits[0]["new"]
    assert "<release>11</release>" in plugin_edits[0]["new"]


def test_surefire_target_operator_adds_plugin_when_absent() -> None:
    pom = "<project><build></build></project>"

    edits = maven_add_or_upgrade_surefire_for_target_java_edits(
        {"pom.xml": pom},
        _context(21),
    )

    assert len(edits) == 1
    assert "<artifactId>maven-surefire-plugin</artifactId>" in edits[0]["new"]
    assert "<version>3.2.5</version>" in edits[0]["new"]


def test_surefire_target_operator_creates_build_plugins_when_absent() -> None:
    pom = "<project><modelVersion>4.0.0</modelVersion></project>"

    edits = maven_add_or_upgrade_surefire_for_target_java_edits(
        {"pom.xml": pom},
        _context(17),
    )

    assert len(edits) == 1
    assert "<build>" in edits[0]["new"]
    assert "<plugins>" in edits[0]["new"]
    assert "<artifactId>maven-surefire-plugin</artifactId>" in edits[0]["new"]


def test_lombok_target_operator_upgrades_properties_and_plugin_block() -> None:
    pom = """<project>
  <properties>
    <lombok.version>1.18.8</lombok.version>
    <lombok.plugin.version>1.18.6.0</lombok.plugin.version>
  </properties>
  <dependencies>
    <dependency>
      <groupId>org.projectlombok</groupId>
      <artifactId>lombok</artifactId>
      <version>1.18.8</version>
    </dependency>
  </dependencies>
  <build>
    <plugins>
      <plugin>
        <groupId>org.projectlombok</groupId>
        <artifactId>lombok-maven-plugin</artifactId>
        <version>1.18.6.0</version>
      </plugin>
    </plugins>
  </build>
</project>"""

    edits = maven_upgrade_lombok_for_target_java_edits({"pom.xml": pom}, _context())

    joined_new = "\n".join(str(edit["new"]) for edit in edits)
    assert "<lombok.version>1.18.30</lombok.version>" in joined_new
    assert "<lombok.plugin.version>1.18.20.0</lombok.plugin.version>" in joined_new
    assert "<artifactId>lombok</artifactId>" in joined_new
    assert "<version>1.18.30</version>" in joined_new


def test_lombok_target_operator_uses_target_profile_versions() -> None:
    pom = """<project>
  <properties>
    <lombok.version>1.18.8</lombok.version>
  </properties>
</project>"""

    edits_11 = maven_upgrade_lombok_edits({"pom.xml": pom}, _context(11))
    edits_17 = maven_upgrade_lombok_edits({"pom.xml": pom}, _context(17))
    edits_21 = maven_upgrade_lombok_edits({"pom.xml": pom}, _context(21))

    assert "<lombok.version>1.18.20</lombok.version>" in edits_11[0]["new"]
    assert "<lombok.version>1.18.30</lombok.version>" in edits_17[0]["new"]
    assert "<lombok.version>1.18.32</lombok.version>" in edits_21[0]["new"]


def test_lombok_target_operator_returns_empty_when_lombok_absent() -> None:
    pom = "<project><properties><java.version>1.8</java.version></properties></project>"

    assert maven_upgrade_lombok_edits({"pom.xml": pom}, _context()) == []


def test_bytecode_reader_incompatibility_does_not_emit_compiler_release_patch() -> None:
    pom = """<project>
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>2.1.5.RELEASE</version>
  </parent>
</project>"""

    candidates = migrationbench_operator_candidates(
        feedback=FeedbackDigest(
            candidate_id="c1",
            failure_type="class_version_error",
            severity="warning",
            summary="class_version_error",
            evidence=[
                "Unsupported class file major version 61 in Spring ASM ClassReader"
            ],
        ),
        original=Candidate(
            candidate_id="c1",
            kind=CandidateKind.PATCH,
            payload={"branch_id": "c1_branch"},
            origin="seed",
        ),
        observation=Observation(
            summary="pom",
            data={"pom_texts": {"pom.xml": pom}, "target_java": 17},
        ),
        instance=RunInstance(
            instance_id="spring__case",
            adapter_name="migrationbench",
            objective="migrate",
        ),
        affordance=Affordance(
            affordance_id="aff-spring",
            action_type="diagnose_bytecode_reader_incompatibility",
            target="maven_build",
            reason="class_version_error",
            priority=1.0,
            expected_worker_kind="operator_selector",
        ),
    )

    assert candidates == ()


def test_no_operator_name_contains_17() -> None:
    assert all("17" not in name for name in operators.__all__)


def test_bundle_plugin_operator_scopes_felix_upgrade() -> None:
    pom = """<project>
  <dependencies>
    <dependency>
      <groupId>demo</groupId>
      <artifactId>bundle-like-dependency</artifactId>
      <version>2.5.3</version>
    </dependency>
  </dependencies>
  <build>
    <plugins>
      <plugin>
        <groupId>org.apache.felix</groupId>
        <artifactId>maven-bundle-plugin</artifactId>
        <version>2.5.3</version>
      </plugin>
    </plugins>
  </build>
</project>"""

    edits = maven_upgrade_bundle_plugin_edits({"pom.xml": pom}, _context())

    assert len(edits) == 1
    assert "<artifactId>maven-bundle-plugin</artifactId>" in edits[0]["old"]
    assert "<version>5.1.9</version>" in edits[0]["new"]
    assert "<artifactId>bundle-like-dependency</artifactId>" not in edits[0]["old"]


def test_bundle_plugin_operator_returns_empty_when_plugin_absent() -> None:
    pom = "<project><dependencies><dependency><artifactId>bndlib</artifactId></dependency></dependencies></project>"

    assert maven_upgrade_bundle_plugin_edits({"pom.xml": pom}, _context()) == []


def test_javafx_operator_uses_target_profile_and_target_gate() -> None:
    pom = "<project><dependencies>\n  </dependencies></project>"

    assert maven_add_javafx_dependencies_edits({"pom.xml": pom}, _context(8)) == []

    edits_11 = maven_add_javafx_dependencies_edits(
        {"pom.xml": pom},
        _context(11),
        feedback_text="javafx.application.Application javafx.fxml.FXMLLoader",
    )
    edits_17 = maven_add_javafx_dependencies_edits(
        {"pom.xml": pom},
        _context(17),
        feedback_text="javafx.scene.control.TextField",
    )
    edits_21 = maven_add_javafx_dependencies_edits(
        {"pom.xml": pom},
        _context(21),
        feedback_text="javafx.stage.Stage",
    )

    assert "<artifactId>javafx-controls</artifactId>" in edits_11[0]["new"]
    assert "<artifactId>javafx-fxml</artifactId>" in edits_11[0]["new"]
    assert "<version>11.0.2</version>" in edits_11[0]["new"]
    assert "<version>17.0.2</version>" in edits_17[0]["new"]
    assert "<version>21.0.2</version>" in edits_21[0]["new"]


def test_javafx_operator_adds_dependencies_block_when_absent() -> None:
    pom = "<project><modelVersion>4.0.0</modelVersion></project>"

    edits = maven_add_javafx_dependencies_edits(
        {"pom.xml": pom},
        _context(17),
        feedback_text="javafx.scene.layout.Pane",
    )

    assert len(edits) == 1
    assert "<dependencies>" in edits[0]["new"]
    assert "<artifactId>javafx-controls</artifactId>" in edits[0]["new"]


def test_replace_sun_misc_base64_exact_patterns_only() -> None:
    java = """package demo;

import sun.misc.BASE64Encoder;
import sun.misc.BASE64Decoder;

class Demo {
  String e(byte[] data) {
    return new BASE64Encoder().encode(data);
  }
  byte[] d(String text) throws Exception {
    return new BASE64Decoder().decodeBuffer(text);
  }
}
"""

    edits = replace_sun_misc_base64_edits({"src/main/java/Demo.java": java}, _context(17))

    assert len(edits) == 1
    assert "import java.util.Base64;" in edits[0]["new"]
    assert "Base64.getEncoder().encodeToString(data)" in edits[0]["new"]
    assert "Base64.getDecoder().decode(text)" in edits[0]["new"]
    assert "BASE64Encoder" not in edits[0]["new"]


def test_replace_sun_misc_base64_noops_for_complex_or_old_target() -> None:
    complex_java = """import sun.misc.BASE64Encoder;
class Demo {
  String e(byte[] data) {
    BASE64Encoder encoder = new BASE64Encoder();
    return encoder.encode(data);
  }
}
"""

    assert replace_sun_misc_base64_edits({"Demo.java": complex_java}, _context(17)) == []
    assert replace_sun_misc_base64_edits({"Demo.java": complex_java}, _context(8)) == []


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
            "target_java": 17,
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
        action_type="ensure_maven_compiler_release",
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
        data={"pom_files": ["pom.xml"], "java_files_sample": [], "target_java": 17},
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


def test_operator_provider_reads_migrationbench_repo_dir_workspace(tmp_path) -> None:
    branch_root = tmp_path / "branch"
    repo = branch_root / "repo"
    repo.mkdir(parents=True)
    (repo / "pom.xml").write_text(
        "<project><dependencies>\n</dependencies></project>",
        encoding="utf-8",
    )
    observation = Observation(
        summary="pom",
        data={"pom_files": ["pom.xml"], "java_files_sample": [], "target_java": 17},
    )
    workspace = WorkspaceHandle(
        root=branch_root,
        instance_id="repo__case",
        metadata={"repo_dir": str(repo)},
    )

    live_observation = _attach_live_files(observation, workspace)

    assert live_observation.data["__live_files__"]["pom.xml"].startswith(
        "<project>"
    )
