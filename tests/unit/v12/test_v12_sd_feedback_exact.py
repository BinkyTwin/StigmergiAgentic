"""Official SD-Feedback protocol compatibility tests."""

from __future__ import annotations

from types import SimpleNamespace

from core_v10.contracts import ValidationResult, ValidationStatus
from core_v12.sd_feedback_exact import (
    OFFICIAL_MAVEN_PROJECT_TEMPLATE_PROMPT,
    apply_official_jdk17_seed,
    apply_official_sd_groups,
    build_data_from_validation,
    parse_official_sd_response,
    prepare_official_sd_prompt,
    signature_from_validation,
)
from core_v12.tools.executor import build_sd_feedback_readonly_tool_registry
from core_v12.tools.native_schema import registry_to_native_tools


def test_official_sd_feedback_parser_extracts_grouped_find_replace(tmp_path) -> None:
    target = tmp_path / "repo" / "src" / "main" / "java" / "App.java"
    target.parent.mkdir(parents=True)
    target.write_text("class App { int x = 1; }\n", encoding="utf-8")
    response = f"""
Explanation:
- small fix

[Change Start {target}]
[Find Start]
int x = 1;
[Find End]
[Replace Start]
int x = 2;
[Replace End]
[Change End {target}]
"""

    parsed = parse_official_sd_response(response)

    assert parsed.ok
    assert parsed.groups[0].path == str(target)
    assert parsed.groups[0].pairs[0].find == "int x = 1;"
    assert "Change Start" in parsed.parsed_content


def test_official_sd_feedback_writer_uses_fuzzy_find_blocks(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "App.java"
    target.write_text("class App {\n    int x = 1;\n}\n", encoding="utf-8")
    parsed = parse_official_sd_response(
        f"""
[Change Start {target}]
[Find Start]
int x = 1;
[Find End]
[Replace Start]
int x = 2;
[Replace End]
[Change End {target}]
"""
    )

    result = apply_official_sd_groups(parsed.groups, repo)

    assert result.any_patched
    assert target.read_text(encoding="utf-8") == "class App {\n    int x = 2;\n}\n"


def test_official_sd_feedback_writer_remaps_parent_branch_absolute_paths(
    tmp_path,
) -> None:
    parent_repo = tmp_path / "parent" / "repo"
    candidate_repo = tmp_path / "candidate" / "repo"
    parent_target = parent_repo / "src" / "main" / "java" / "App.java"
    candidate_target = candidate_repo / "src" / "main" / "java" / "App.java"
    parent_target.parent.mkdir(parents=True)
    candidate_target.parent.mkdir(parents=True)
    parent_target.write_text("class App { int x = 1; }\n", encoding="utf-8")
    candidate_target.write_text("class App { int x = 1; }\n", encoding="utf-8")
    parsed = parse_official_sd_response(
        f"""
[Change Start {parent_target}]
[Find Start]
int x = 1;
[Find End]
[Replace Start]
int x = 2;
[Replace End]
[Change End {parent_target}]
"""
    )

    result = apply_official_sd_groups(parsed.groups, candidate_repo)

    assert result.any_patched
    assert candidate_target.read_text(encoding="utf-8") == "class App { int x = 2; }\n"
    assert parent_target.read_text(encoding="utf-8") == "class App { int x = 1; }\n"


def test_official_sd_feedback_writer_reports_missing_find_block(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "App.java"
    target.write_text("class App {}\n", encoding="utf-8")
    parsed = parse_official_sd_response(
        f"""
[Change Start {target}]
[Find Start]
missing();
[Find End]
[Replace Start]
present();
[Replace End]
[Change End {target}]
"""
    )

    result = apply_official_sd_groups(parsed.groups, repo)

    assert not result.any_patched
    assert "Find blocks are not found" in result.feedback[0]


def test_official_jdk17_seed_rewrites_maven_pom(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pom.xml").write_text(
        """<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>x</groupId>
  <artifactId>x</artifactId>
  <version>1</version>
  <properties><maven.compiler.source>1.8</maven.compiler.source></properties>
</project>
""",
        encoding="utf-8",
    )

    modified = apply_official_jdk17_seed(repo)
    text = (repo / "pom.xml").read_text(encoding="utf-8")

    assert modified == ("pom.xml",)
    assert "maven.compiler.source" in text
    assert "17" in text
    assert "maven-compiler-plugin" in text


def test_build_data_extracts_first_maven_compile_error(tmp_path) -> None:
    repo = tmp_path / "repo"
    java = repo / "src" / "main" / "java" / "App.java"
    java.parent.mkdir(parents=True)
    java.write_text("class App {\n  void f() { missing(); }\n}\n", encoding="utf-8")
    (repo / "pom.xml").write_text("<project />", encoding="utf-8")
    validation = ValidationResult(
        candidate_id="c1",
        status=ValidationStatus.FAILED,
        validator_name="test",
        summary="compile_error",
        raw_output=f"[ERROR] {java}:[2,14] cannot find symbol",
    )

    build_data = build_data_from_validation(validation, repo_dir=repo)
    signature = signature_from_validation(validation, repo_dir=repo)

    assert build_data.filename == str(java)
    assert build_data.line_number == 2
    assert build_data.column_number == 14
    assert "Compilation error is at this line" in (build_data.code_snippet or "")
    assert signature.first_error_file == str(java)


def test_official_retry_prompt_uses_feedback_messages() -> None:
    request = prepare_official_sd_prompt(
        repo_dir=SimpleNamespace(),
        project_path=None,
        build_data=SimpleNamespace(project="", filename=None),
        last_prompt_messages=[{"role": "user", "content": "old prompt"}],
        last_llm_response="bad response",
        feedback=["Find blocks are not found"],
    )

    assert request.prompt_kind == "official_sd_feedback_retry"
    assert "The response is incorrect" in request.prompt
    assert "[Feedback Start]Find blocks are not found[Feedback End]" in request.prompt
    assert request.messages[-1]["role"] == "assistant"


def test_project_prompt_is_official_java17_template() -> None:
    assert "Java 17" in OFFICIAL_MAVEN_PROJECT_TEMPLATE_PROMPT
    assert "[Change Start $full_filepath]" in OFFICIAL_MAVEN_PROJECT_TEMPLATE_PROMPT
    assert "[Find Start]" in OFFICIAL_MAVEN_PROJECT_TEMPLATE_PROMPT


def test_readonly_registry_has_native_tool_schemas_for_v12_4() -> None:
    registry = build_sd_feedback_readonly_tool_registry()
    tools = registry_to_native_tools(registry)
    names = {tool["function"]["name"] for tool in tools}

    assert set(registry.names()) == names
    assert "read_build_log" in names
    assert "parse_maven_errors" in names
