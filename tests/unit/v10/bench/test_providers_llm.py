"""Unit tests for the LLM-driven providers in scripts.bench.providers_llm.

The OpenAI client is patched out so these tests run offline. Each test
exercises one observable behavior (config resolution, JSON parsing,
candidate dedup, fallback semantics, repair feedback usage).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from adapters_v10.migrationbench.context import MigrationContext
from core_v10.contracts import (
    Candidate,
    CandidateKind,
    FeedbackDigest,
    Observation,
    RunInstance,
)

from scripts.bench import providers_llm
from scripts.bench.providers_llm import (
    LLMConfig,
    _collect_dependency_context,
    _extract_dependencies,
    _extract_spring_boot_parent,
    _format_project_context,
    _normalize_edits,
    _safe_json_parse,
    _signature,
    make_migrationbench_llm_initial_provider,
    make_migrationbench_llm_repair_provider,
)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_safe_json_parse_handles_plain_object() -> None:
    parsed = _safe_json_parse('{"edits": [{"type": "replace_text"}]}')
    assert parsed == {"edits": [{"type": "replace_text"}]}


def test_safe_json_parse_handles_fenced_block() -> None:
    text = (
        "Here is the answer:\n"
        "```json\n"
        '{"edits": [{"type": "replace_text"}]}\n'
        "```\n"
    )
    assert _safe_json_parse(text) == {"edits": [{"type": "replace_text"}]}


def test_safe_json_parse_returns_none_on_garbage() -> None:
    assert _safe_json_parse("nope") is None
    assert _safe_json_parse("") is None


def test_normalize_edits_filters_invalid_paths_and_kinds() -> None:
    raw = {
        "edits": [
            {"type": "replace_text", "path": "/abs", "old": "a", "new": "b"},
            {"type": "replace_text", "path": "../etc", "old": "a", "new": "b"},
            {"type": "replace_text", "path": "pom.xml", "old": "", "new": "x"},
            {"type": "replace_text", "path": "pom.xml", "old": "1.8", "new": "17"},
            {"type": "write_file", "path": "Foo.java", "content": "class Foo {}"},
            {"type": "rename_file", "path": "x", "from": "a", "to": "b"},
            "not-an-object",
        ]
    }
    cleaned = _normalize_edits(raw)
    paths = [e["path"] for e in cleaned]
    kinds = [e["type"] for e in cleaned]
    assert paths == ["pom.xml", "Foo.java"]
    assert kinds == ["replace_text", "write_file"]
    assert cleaned[0]["expected_replacements"] == 1
    assert cleaned[0]["allow_multiple"] is True


def test_normalize_edits_returns_empty_for_non_dict_input() -> None:
    assert _normalize_edits([]) == []
    assert _normalize_edits(None) == []


def test_normalize_edits_drops_hallucinated_old_when_files_provided() -> None:
    files = {"pom.xml": "<project><foo>1</foo></project>"}
    raw = {
        "edits": [
            # Verbatim, must survive
            {"type": "replace_text", "path": "pom.xml", "old": "<foo>1</foo>", "new": "<foo>2</foo>"},
            # Hallucinated, must be dropped
            {"type": "replace_text", "path": "pom.xml", "old": "<bar>nope</bar>", "new": "x"},
        ]
    }
    cleaned = _normalize_edits(raw, files=files)
    assert len(cleaned) == 1
    assert cleaned[0]["old"] == "<foo>1</foo>"


def test_normalize_edits_keeps_unknown_paths_when_files_provided() -> None:
    """Edits to files we did NOT show the LLM should pass through unchecked.

    This preserves the LLM's ability to write fresh files (e.g. a
    `web.xml` it sees only as a name in `pom_files`).
    """
    files = {"pom.xml": "<a/>"}
    raw = {
        "edits": [
            # Path not in files dict — guard does nothing, edit goes through.
            {"type": "replace_text", "path": "src/main/resources/foo.xml", "old": "x", "new": "y"},
        ]
    }
    cleaned = _normalize_edits(raw, files=files)
    assert len(cleaned) == 1
    assert cleaned[0]["path"] == "src/main/resources/foo.xml"


def test_signature_is_stable_for_same_payload() -> None:
    a = [{"type": "replace_text", "path": "p", "old": "x", "new": "y"}]
    b = [{"type": "replace_text", "path": "p", "old": "x", "new": "y"}]
    assert _signature(a) == _signature(b)


def test_signature_distinguishes_payloads() -> None:
    a = [{"type": "replace_text", "path": "p", "old": "x", "new": "y"}]
    b = [{"type": "replace_text", "path": "p", "old": "x", "new": "Z"}]
    assert _signature(a) != _signature(b)


# ---------------------------------------------------------------------------
# LLMConfig
# ---------------------------------------------------------------------------


def test_llm_config_returns_none_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    assert LLMConfig.from_extras({"use_llm_providers": False}) is None


def test_llm_config_returns_none_when_api_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert LLMConfig.from_extras({"use_llm_providers": True}) is None


def test_llm_config_resolves_deepseek_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-key")
    config = LLMConfig.from_extras({"use_llm_providers": True})
    assert config is not None
    assert config.provider == "deepseek"
    assert config.base_url.startswith("https://api.deepseek.com")
    assert config.model == "deepseek-chat"
    assert config.api_key == "sk-key"
    assert config.trace_dir is None


def test_llm_config_defaults_trace_dir_to_out_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-key")
    config = LLMConfig.from_extras(
        {"use_llm_providers": True, "out_dir": str(tmp_path)}
    )
    assert config is not None
    assert config.trace_dir == tmp_path / "llm_traces"


# ---------------------------------------------------------------------------
# Initial provider
# ---------------------------------------------------------------------------


def _make_observation() -> Observation:
    return Observation(
        summary="migrate",
        data={
            "instance_id": "demo__repo",
            "repo_url": "https://github.com/demo/repo",
            "base_commit": "abcdef",
            "target_java": 17,
            "target_class_major": 61,
            "migration_mode": "minimal",
            "pom_files": ["pom.xml"],
            "java_files_sample": [],
        },
    )


def _make_instance() -> RunInstance:
    return RunInstance(
        instance_id="demo__repo",
        adapter_name="migrationbench_v10",
        objective="migrate to target java",
        metadata={"instance": {"target_java": 17}},
    )


def _migration_context(target_java: int = 17) -> MigrationContext:
    return MigrationContext(
        source_language="java",
        source_version=8,
        target_language="java",
        target_version=target_java,
        target_class_major={11: 55, 17: 61, 21: 65}[target_java],
        build_system="maven",
        migration_mode="minimal",
        dependency_policy="minimal",
    )


class _FakeWorkspace:
    def __init__(self, files: dict[str, str]):
        self._files = files

    def list_targets(self) -> list[str]:
        return list(self._files)

    def read_file(self, rel: str, max_bytes: int = 0) -> str:
        return self._files[rel]


class _FakeAdapter:
    """Adapter stub for the LLM provider tests."""

    def __init__(self, files: dict[str, str]):
        self._workspace = _FakeWorkspace(files)

    # Mirror MigrationBenchAdapterV10's private hook used by the providers.
    def _require_base_workspace(self) -> _FakeWorkspace:
        return self._workspace


@pytest.fixture
def adapter_factory(monkeypatch: pytest.MonkeyPatch):
    """Patch isinstance so the LLM providers accept the fake adapter."""

    def _factory(files: dict[str, str]):
        adapter = _FakeAdapter(files)
        monkeypatch.setattr(
            "adapters_v10.migrationbench.adapter.MigrationBenchAdapterV10",
            _FakeAdapter,
        )
        return adapter

    return _factory


def test_initial_provider_falls_back_to_deterministic_when_disabled(
    adapter_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-key")
    pom = (
        "<project>\n"
        "  <maven.compiler.source>1.8</maven.compiler.source>\n"
        "  <maven.compiler.target>1.8</maven.compiler.target>\n"
        "</project>\n"
    )
    adapter = adapter_factory({"pom.xml": pom})
    extras = {"use_llm_providers": False}
    provide = make_migrationbench_llm_initial_provider(adapter, extras)
    candidates = list(provide(_make_observation(), _make_instance()))
    assert len(candidates) == 1
    assert candidates[0].origin == "builtin_deterministic_maven_target_java"


def test_initial_provider_emits_distinct_llm_candidates(
    adapter_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-key")
    pom = (
        "<project>\n"
        "  <maven.compiler.source>1.8</maven.compiler.source>\n"
        "</project>\n"
    )
    adapter = adapter_factory({"pom.xml": pom})

    responses = iter(
        [
            {
                "edits": [
                    {
                        "type": "replace_text",
                        "path": "pom.xml",
                        "old": "<maven.compiler.source>1.8</maven.compiler.source>",
                        "new": "<maven.compiler.source>17</maven.compiler.source>",
                    }
                ],
                "rationale": "minimal",
                "expected_build_command": "mvn clean verify",
            },
            {
                "edits": [
                    {
                        "type": "replace_text",
                        "path": "pom.xml",
                        "old": "<maven.compiler.source>1.8</maven.compiler.source>",
                        "new": "<maven.compiler.release>17</maven.compiler.release>",
                    }
                ],
                "rationale": "use release flag",
                "expected_build_command": "mvn clean verify",
            },
            None,  # third LLM call falls into invalid response branch
            None,  # fourth too
        ]
    )

    def fake_call(*args, **kwargs):
        return next(responses)

    monkeypatch.setattr(providers_llm, "_call_llm_json", fake_call)

    extras = {"use_llm_providers": True, "llm_initial_candidates": 4}
    provide = make_migrationbench_llm_initial_provider(adapter, extras)
    candidates = list(provide(_make_observation(), _make_instance()))
    origins = [c.origin for c in candidates]
    assert all(o.startswith("llm_") for o in origins)
    assert len(candidates) == 2
    seen = {_signature(c.payload["edit_set"]["edits"]) for c in candidates}
    assert len(seen) == len(candidates)


def test_initial_provider_writes_full_llm_trace_for_each_call(
    adapter_factory,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-key")
    pom = (
        "<project>\n"
        "  <maven.compiler.source>1.8</maven.compiler.source>\n"
        "</project>\n"
    )
    adapter = adapter_factory({"pom.xml": pom})
    valid_response = providers_llm.LLMJsonResponse(
        {
            "edits": [
                {
                    "type": "replace_text",
                    "path": "pom.xml",
                    "old": "<maven.compiler.source>1.8</maven.compiler.source>",
                    "new": "<maven.compiler.source>17</maven.compiler.source>",
                }
            ],
            "rationale": "trace me",
        },
        raw_response='{"edits":[{"type":"replace_text"}],"rationale":"trace me"}',
        duration_seconds=0.2,
        finish_reason="stop",
        usage={"prompt_tokens": 10, "completion_tokens": 5},
    )
    responses = iter([valid_response, valid_response, None])
    monkeypatch.setattr(providers_llm, "_call_llm_json", lambda *a, **k: next(responses))

    provide = make_migrationbench_llm_initial_provider(
        adapter,
        {
            "use_llm_providers": True,
            "llm_initial_candidates": 3,
            "out_dir": str(tmp_path),
        },
    )
    candidates = list(provide(_make_observation(), _make_instance()))

    assert len(candidates) == 1
    trace_path = tmp_path / "llm_traces" / "calls.jsonl"
    rows = [
        json.loads(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [row["candidate_emitted"] for row in rows] == [True, False, False]
    assert rows[1]["dropped_reason"] == "duplicate_signature"
    assert rows[2]["dropped_reason"] == "empty_or_invalid_edits"
    first = rows[0]
    assert first["call_kind"] == "initial"
    assert first["instance_id"] == "demo__repo"
    assert "You are a senior Java/Maven build engineer" in first["system_prompt"]
    assert "Target Java: 17" in first["user_prompt"]
    assert first["raw_response"].startswith('{"edits"')
    assert first["parsed_response"]["rationale"] == "trace me"
    assert first["normalized_edits"][0]["path"] == "pom.xml"
    assert first["usage"] == {"prompt_tokens": 10, "completion_tokens": 5}


def test_initial_provider_falls_back_to_deterministic_when_llm_silent(
    adapter_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-key")
    pom = (
        "<project>\n"
        "  <maven.compiler.source>1.8</maven.compiler.source>\n"
        "</project>\n"
    )
    adapter = adapter_factory({"pom.xml": pom})
    monkeypatch.setattr(providers_llm, "_call_llm_json", lambda *a, **k: None)
    extras = {"use_llm_providers": True, "llm_initial_candidates": 2}
    provide = make_migrationbench_llm_initial_provider(adapter, extras)
    candidates = list(provide(_make_observation(), _make_instance()))
    assert len(candidates) == 1
    assert candidates[0].origin == "builtin_deterministic_maven_target_java"
    assert candidates[0].metadata.get("source") == "deterministic_fallback"


def test_deterministic_fallback_uses_target_java(
    adapter_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-key")
    pom = (
        "<project>\n"
        "  <maven.compiler.release>8</maven.compiler.release>\n"
        "</project>\n"
    )
    adapter = adapter_factory({"pom.xml": pom})
    monkeypatch.setattr(providers_llm, "_call_llm_json", lambda *a, **k: None)
    obs = Observation(
        summary="migrate",
        data={
            "instance_id": "demo__repo",
            "repo_url": "https://github.com/demo/repo",
            "base_commit": "abcdef",
            "target_java": 21,
            "target_class_major": 65,
            "migration_mode": "minimal",
            "pom_files": ["pom.xml"],
            "java_files_sample": [],
        },
    )

    provide = make_migrationbench_llm_initial_provider(
        adapter,
        {"use_llm_providers": True, "llm_initial_candidates": 1},
    )
    candidates = list(provide(obs, _make_instance()))

    edit = candidates[0].payload["edit_set"]["edits"][0]
    assert edit["new"] == "<maven.compiler.release>21</maven.compiler.release>"
    assert candidates[0].metadata["migration_context"]["target_java"] == 21


def test_initial_provider_dedups_identical_llm_outputs(
    adapter_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-key")
    pom = "<project></project>"  # no java8 markers — deterministic baseline empty
    adapter = adapter_factory({"pom.xml": pom})

    duplicate = {
        "edits": [
            {
                "type": "replace_text",
                "path": "pom.xml",
                "old": "<project>",
                "new": "<project><foo/>",
            }
        ]
    }
    responses = iter([duplicate, duplicate, duplicate, duplicate])
    monkeypatch.setattr(providers_llm, "_call_llm_json", lambda *a, **k: next(responses))

    extras = {"use_llm_providers": True, "llm_initial_candidates": 4}
    provide = make_migrationbench_llm_initial_provider(adapter, extras)
    candidates = list(provide(_make_observation(), _make_instance()))
    # All four LLM calls produced the same payload, so dedup leaves us with
    # exactly one LLM-origin candidate.
    assert len(candidates) == 1
    assert candidates[0].origin.startswith("llm_")


# ---------------------------------------------------------------------------
# Repair provider
# ---------------------------------------------------------------------------


def _feedback_with_compile_failure() -> FeedbackDigest:
    return FeedbackDigest(
        candidate_id="demo__repo-c0-baseline",
        failure_type="compile_error",
        severity="blocking",
        summary="compile_error",
        evidence=["mvn output tail showing compile error"],
        candidate_causes=[],
        recommended_next_actions=[
            {"action": "fix_compile_error", "rationale": "compile_error"}
        ],
        anti_actions=["do not repeat the same edit signature on the same files"],
        metadata={"signals": {"compile_success": False, "patch_applies": True}},
    )


def test_repair_provider_returns_empty_when_disabled(
    adapter_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-key")
    adapter = adapter_factory({"pom.xml": "<p/>"})
    extras = {"use_llm_providers": False}
    provide = make_migrationbench_llm_repair_provider(adapter, extras)
    candidates = list(
        provide(
            _feedback_with_compile_failure(),
            Candidate(
                candidate_id="demo__repo-c0-baseline",
                kind=CandidateKind.PATCH,
                payload={"branch_id": "c0", "edit_set": {"edits": []}},
                origin="builtin_deterministic_maven_target_java",
            ),
            _make_observation(),
            _make_instance(),
        )
    )
    assert candidates == []


def test_repair_provider_uses_feedback_and_emits_candidate(
    adapter_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-key")
    adapter = adapter_factory({"pom.xml": "<project/>"})

    captured: dict[str, Any] = {}

    def fake_call(config, *, system, user, temperature):
        captured["system"] = system
        captured["user"] = user
        captured["temperature"] = temperature
        return {
            "edits": [
                {
                    "type": "replace_text",
                    "path": "pom.xml",
                    "old": "<project/>",
                    "new": "<project><release>17</release></project>",
                }
            ]
        }

    monkeypatch.setattr(providers_llm, "_call_llm_json", fake_call)

    extras = {"use_llm_providers": True, "llm_repair_candidates": 1}
    provide = make_migrationbench_llm_repair_provider(adapter, extras)
    feedback = _feedback_with_compile_failure()
    candidates = list(
        provide(
            feedback,
            Candidate(
                candidate_id="demo__repo-c0-baseline",
                kind=CandidateKind.PATCH,
                payload={
                    "branch_id": "c0",
                    "edit_set": {
                        "edits": [
                            {
                                "type": "replace_text",
                                "path": "pom.xml",
                                "old": "1.8",
                                "new": "17",
                            }
                        ]
                    },
                },
                origin="builtin_deterministic_maven_target_java",
            ),
            _make_observation(),
            _make_instance(),
        )
    )
    assert len(candidates) == 1
    rep = candidates[0]
    assert rep.parent_id == "demo__repo-c0-baseline"
    assert rep.origin.startswith("llm_repair_")
    assert "compile_error" in captured["user"]
    assert "Recommended next actions" in captured["user"]
    assert captured["temperature"] == 0.0


# ---------------------------------------------------------------------------
# Project context enrichment (piste 1, ADR 2026-05-04)
# ---------------------------------------------------------------------------


def test_extract_dependencies_parses_top_level_pom() -> None:
    pom = """
    <project>
      <dependencies>
        <dependency>
          <groupId>org.springframework.boot</groupId>
          <artifactId>spring-boot-starter-web</artifactId>
          <version>2.5.0</version>
        </dependency>
        <dependency>
          <groupId>org.junit.jupiter</groupId>
          <artifactId>junit-jupiter</artifactId>
        </dependency>
      </dependencies>
    </project>
    """
    deps = _extract_dependencies(pom)
    assert {"groupId": "org.springframework.boot", "artifactId": "spring-boot-starter-web", "version": "2.5.0"} in deps
    assert any(d["artifactId"] == "junit-jupiter" for d in deps)


def test_extract_spring_boot_parent_detects_version() -> None:
    pom = """
    <project>
      <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>2.7.5</version>
      </parent>
    </project>
    """
    assert _extract_spring_boot_parent(pom) == "2.7.5"


def test_extract_spring_boot_parent_returns_none_for_other_parents() -> None:
    pom = "<project><parent><artifactId>random</artifactId><version>1</version></parent></project>"
    assert _extract_spring_boot_parent(pom) is None


def test_collect_dependency_context_finds_javax_imports() -> None:
    files = {
        "pom.xml": """
            <project>
              <parent>
                <artifactId>spring-boot-starter-parent</artifactId>
                <version>2.7.0</version>
              </parent>
              <dependencies>
                <dependency>
                  <groupId>org.springframework.boot</groupId>
                  <artifactId>spring-boot-starter-web</artifactId>
                </dependency>
              </dependencies>
            </project>
        """,
        "src/main/java/Foo.java": (
            "package demo;\n"
            "import javax.servlet.http.HttpServletRequest;\n"
            "import javax.persistence.Entity;\n"
            "import java.util.List;\n"  # not javax, must be ignored
            "class Foo {}\n"
        ),
    }
    ctx = _collect_dependency_context(files)
    assert "2.7.0" in ctx["spring_boot_parent_versions"]
    assert any(d["artifactId"] == "spring-boot-starter-web" for d in ctx["top_dependencies"])
    assert "javax.servlet.http.HttpServletRequest" in ctx["javax_imports"]
    assert "javax.persistence.Entity" in ctx["javax_imports"]
    assert all("java.util" not in s for s in ctx["javax_imports"])


def test_format_project_context_returns_empty_when_no_signal() -> None:
    assert (
        _format_project_context(
            {
                "top_dependencies": [],
                "javax_imports": [],
                "spring_boot_parent_versions": [],
            }
        )
        == ""
    )


def test_format_project_context_emits_blocks() -> None:
    ctx = {
        "spring_boot_parent_versions": ["2.7.5"],
        "top_dependencies": [
            {"groupId": "g", "artifactId": "a", "version": "1.0"}
        ],
        "javax_imports": ["javax.servlet.http.HttpServletRequest"],
    }
    text = _format_project_context(ctx, _migration_context(21))
    assert "spring_boot_parent_versions" in text
    assert "g:a:1.0" in text
    assert "javax.servlet.http.HttpServletRequest" in text
    assert "jakarta" in text  # hint mentioning jakarta migration


def test_initial_user_prompt_includes_project_context_and_test_rule(
    adapter_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-key")
    pom_xml = """
        <project>
          <parent>
            <artifactId>spring-boot-starter-parent</artifactId>
            <version>2.7.0</version>
          </parent>
          <dependencies>
            <dependency>
              <groupId>org.springframework.boot</groupId>
              <artifactId>spring-boot-starter-web</artifactId>
            </dependency>
          </dependencies>
          <maven.compiler.source>1.8</maven.compiler.source>
        </project>
    """
    java_src = "import javax.servlet.http.HttpServletRequest;\nclass A {}\n"
    adapter = adapter_factory({"pom.xml": pom_xml, "src/main/java/A.java": java_src})

    captured: dict[str, Any] = {}

    def fake_call(config, *, system, user, temperature):
        captured.setdefault("user", user)
        captured.setdefault("system", system)
        return {
            "edits": [
                {
                    "type": "replace_text",
                    "path": "pom.xml",
                    "old": "<maven.compiler.source>1.8</maven.compiler.source>",
                    "new": "<maven.compiler.source>17</maven.compiler.source>",
                }
            ]
        }

    monkeypatch.setattr(providers_llm, "_call_llm_json", fake_call)

    obs = Observation(
        summary="x",
        data={
            "instance_id": "demo__repo",
            "repo_url": "https://github.com/demo/repo",
            "base_commit": "abc",
            "target_java": 17,
            "target_class_major": 61,
            "migration_mode": "minimal",
            "pom_files": ["pom.xml"],
            "java_files_sample": ["src/main/java/A.java"],
        },
    )
    extras = {"use_llm_providers": True, "llm_initial_candidates": 1}
    provide = make_migrationbench_llm_initial_provider(adapter, extras)
    list(provide(obs, _make_instance()))
    assert "Project context" in captured["user"]
    assert "javax.servlet.http.HttpServletRequest" in captured["user"]
    # System prompt carries the test preservation rule.
    assert "preserve" in captured["system"].lower() or "do not delete" in captured["system"].lower()
    assert "MigrationBench" in captured["system"] or "official" in captured["system"].lower()


def test_prompt_mentions_target_java_not_hardcoded_17(
    adapter_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-key")
    pom_xml = "<project><maven.compiler.source>1.8</maven.compiler.source></project>"
    adapter = adapter_factory({"pom.xml": pom_xml})

    captured: dict[str, str] = {}

    def fake_call(config, *, system, user, temperature):
        captured["system"] = system
        captured["user"] = user
        return {
            "edits": [
                {
                    "type": "replace_text",
                    "path": "pom.xml",
                    "old": "<maven.compiler.source>1.8</maven.compiler.source>",
                    "new": "<maven.compiler.source>21</maven.compiler.source>",
                }
            ]
        }

    monkeypatch.setattr(providers_llm, "_call_llm_json", fake_call)
    obs = Observation(
        summary="x",
        data={
            "instance_id": "demo__repo",
            "repo_url": "https://github.com/demo/repo",
            "base_commit": "abc",
            "target_java": 21,
            "target_class_major": 65,
            "migration_mode": "minimal",
            "pom_files": ["pom.xml"],
            "java_files_sample": [],
        },
    )

    provide = make_migrationbench_llm_initial_provider(
        adapter,
        {"use_llm_providers": True, "llm_initial_candidates": 1},
    )
    list(provide(obs, _make_instance()))

    combined_prompt = f"{captured['system']}\n{captured['user']}"
    assert "Target Java: 21" in combined_prompt
    assert "Java 17" not in combined_prompt


def test_repair_provider_skips_invalid_llm_response(
    adapter_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-key")
    adapter = adapter_factory({"pom.xml": "<p/>"})

    monkeypatch.setattr(providers_llm, "_call_llm_json", lambda *a, **k: None)
    extras = {"use_llm_providers": True, "llm_repair_candidates": 2}
    provide = make_migrationbench_llm_repair_provider(adapter, extras)
    out = list(
        provide(
            _feedback_with_compile_failure(),
            Candidate(
                candidate_id="demo__repo-c0-baseline",
                kind=CandidateKind.PATCH,
                payload={"branch_id": "c0", "edit_set": {"edits": []}},
                origin="builtin_deterministic_maven_target_java",
            ),
            _make_observation(),
            _make_instance(),
        )
    )
    assert out == []
