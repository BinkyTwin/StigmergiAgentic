"""Sprint 6 capability-level tests (Python parity + non-Python strict flow)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agents.capabilities.discover import discover_files
from agents.capabilities.test import test_file as capability_test_file
from agents.capabilities.transform import transform_file
from agents.capabilities.validate import validate_file
from environment.pheromone_store import PheromoneStore


class FakeLLMClient:
    """Deterministic fake LLM client for capability tests."""

    def __init__(self, content: str) -> None:
        self.content = content

    def call(self, prompt: str, system: str | None = None):  # type: ignore[no-untyped-def]
        class Response:
            tokens_used = 42
            latency_ms = 7

            def __init__(self, content: str) -> None:
                self.content = content

        return Response(self.content)

    def extract_code_block(self, text: str) -> str:
        return text


def _build_config(*, non_python_enabled: bool = False) -> dict[str, Any]:
    return {
        "pheromones": {
            "task_intensity_clamp": [0.1, 1.0],
            "decay_type": "exponential",
            "decay_rate": 0.05,
            "inhibition_decay_rate": 0.08,
            "inhibition_threshold": 0.1,
        },
        "thresholds": {
            "transformer_intensity_min": 0.2,
            "validator_confidence_high": 0.8,
            "validator_confidence_low": 0.5,
            "max_retry_count": 3,
            "scope_lock_ttl": 3,
        },
        "llm": {
            "max_tokens_total": 100000,
        },
        "runtime": {
            "tick": 0,
        },
        "transformer": {
            "syntax_gate": {"enabled": True, "repair_attempts_max": 2},
        },
        "capabilities": {
            "non_python": {
                "enabled": non_python_enabled,
                "include_extensions": [".md", ".txt", ".json", ".yaml", ".toml", ".sh"],
                "strict_guardrails": True,
                "max_text_file_bytes": 200000,
                "pass_confidence": 0.85,
                "fail_confidence": 0.4,
                "legacy_tokens": ["python2", "xrange", "iteritems", "urllib2"],
            }
        },
    }


def test_discover_capability_python_detects_patterns(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    (repo_path / "module.py").write_text(
        'print "hello"\\nname = raw_input("x")\\n',
        encoding="utf-8",
    )
    config = _build_config(non_python_enabled=False)
    store = PheromoneStore(config, base_path=tmp_path)

    analyses = discover_files(
        store=store,
        repo_path=repo_path,
        llm_client=None,
        config=config,
        agent_name="scout",
        candidate_files=["module.py"],
        all_file_keys=["module.py"],
        build_system_prompt=lambda role: role,
    )

    assert len(analyses) == 1
    entry = analyses[0]
    assert entry["file_kind"] == "python"
    assert entry["analysis_source"] == "regex"
    assert "print_statement" in entry["patterns_found"]
    assert "raw_input" in entry["patterns_found"]


def test_discover_capability_non_python_detects_legacy_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    (repo_path / "README.md").write_text(
        "Run this project with python2 and inspect script.py for details.\\n",
        encoding="utf-8",
    )
    (repo_path / "script.py").write_text("print('ok')\\n", encoding="utf-8")
    config = _build_config(non_python_enabled=True)
    store = PheromoneStore(config, base_path=tmp_path)

    analyses = discover_files(
        store=store,
        repo_path=repo_path,
        llm_client=None,
        config=config,
        agent_name="scout",
        candidate_files=["README.md"],
        all_file_keys=["README.md", "script.py"],
    )

    assert len(analyses) == 1
    entry = analyses[0]
    assert entry["file_kind"] == "text"
    assert entry["analysis_source"] == "text_scan"
    assert entry["dep_count"] >= 1
    assert len(entry["patterns_found"]) >= 1


def test_transform_capability_python_flow(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    (repo_path / "module.py").write_text('print "hello"\\n', encoding="utf-8")
    config = _build_config(non_python_enabled=False)
    store = PheromoneStore(config, base_path=tmp_path)
    store.write(
        "tasks",
        "module.py",
        {
            "intensity": 0.9,
            "patterns_found": ["print_statement"],
            "file_kind": "python",
        },
        agent_id="scout",
    )
    store.write(
        "status",
        "module.py",
        {"status": "pending", "retry_count": 0, "inhibition": 0.0},
        agent_id="scout",
    )

    result = transform_file(
        store=store,
        repo_path=repo_path,
        llm_client=FakeLLMClient("print('hello')\n"),
        file_key="module.py",
        config=config,
        agent_name="transformer",
    )

    assert result["success"] is True
    assert result["file_kind"] == "python"
    assert result["transform_mode"] == "python_syntax_gate"
    assert "print('hello')" in (repo_path / "module.py").read_text(encoding="utf-8")


def test_transform_capability_non_python_full_file(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    (repo_path / "README.md").write_text(
        "Use python2 to run module.py\\n",
        encoding="utf-8",
    )
    config = _build_config(non_python_enabled=True)
    store = PheromoneStore(config, base_path=tmp_path)
    store.write(
        "tasks",
        "README.md",
        {
            "intensity": 0.9,
            "patterns_found": ["legacy_token_python2", "python_file_reference"],
            "file_kind": "text",
        },
        agent_id="scout",
    )
    store.write(
        "status",
        "README.md",
        {"status": "pending", "retry_count": 0, "inhibition": 0.0},
        agent_id="scout",
    )

    result = transform_file(
        store=store,
        repo_path=repo_path,
        llm_client=FakeLLMClient("Use python3 to run module.py\\n"),
        file_key="README.md",
        config=config,
        agent_name="transformer",
    )

    assert result["success"] is True
    assert result["file_kind"] == "text"
    assert result["transform_mode"] == "text_full_file"
    assert "python3" in (repo_path / "README.md").read_text(encoding="utf-8")


def test_test_capability_python_with_callbacks(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    (repo_path / "module.py").write_text(
        "def value():\\n    return 1\\n", encoding="utf-8"
    )
    config = _build_config(non_python_enabled=False)
    store = PheromoneStore(config, base_path=tmp_path)
    store.write(
        "tasks",
        "module.py",
        {"intensity": 0.8, "patterns_found": [], "file_kind": "python"},
        agent_id="scout",
    )
    store.write(
        "status",
        "module.py",
        {"status": "transformed", "retry_count": 0, "inhibition": 0.0},
        agent_id="transformer",
    )

    result = capability_test_file(
        store=store,
        repo_path=repo_path,
        file_key="module.py",
        config=config,
        agent_name="tester",
        run_adaptive_fallback=lambda file_key, file_path: {  # noqa: ARG005
            "tests_total": 1,
            "tests_passed": 1,
            "tests_failed": 0,
            "coverage": 0.0,
            "issues": [],
            "confidence": 0.8,
            "test_mode": "fallback_global_pass",
        },
    )

    assert result["file_kind"] == "python"
    assert result["tests_failed"] == 0
    assert result["confidence"] == 0.8
    assert result["test_mode"] == "fallback_global_pass"


def test_test_capability_non_python_strict_pass(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    (repo_path / "module.py").write_text("print('ok')\\n", encoding="utf-8")
    (repo_path / "README.md").write_text(
        "Run with python3 and inspect module.py for details.\\n",
        encoding="utf-8",
    )
    config = _build_config(non_python_enabled=True)
    store = PheromoneStore(config, base_path=tmp_path)
    store.write(
        "tasks",
        "README.md",
        {"intensity": 0.7, "patterns_found": [], "file_kind": "text"},
        agent_id="scout",
    )
    store.write(
        "status",
        "README.md",
        {"status": "transformed", "retry_count": 0, "inhibition": 0.0},
        agent_id="transformer",
    )

    result = capability_test_file(
        store=store,
        repo_path=repo_path,
        file_key="README.md",
        config=config,
        agent_name="tester",
    )

    assert result["file_kind"] == "text"
    assert result["tests_failed"] == 0
    assert result["confidence"] == 0.85
    assert result["test_mode"] == "non_python_strict"


def test_test_capability_non_python_strict_fail(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    (repo_path / "README.md").write_text(
        "Run with python2 and inspect missing_module.py\\n",
        encoding="utf-8",
    )
    config = _build_config(non_python_enabled=True)
    store = PheromoneStore(config, base_path=tmp_path)
    store.write(
        "tasks",
        "README.md",
        {"intensity": 0.7, "patterns_found": [], "file_kind": "text"},
        agent_id="scout",
    )
    store.write(
        "status",
        "README.md",
        {"status": "transformed", "retry_count": 0, "inhibition": 0.0},
        agent_id="transformer",
    )

    result = capability_test_file(
        store=store,
        repo_path=repo_path,
        file_key="README.md",
        config=config,
        agent_name="tester",
    )

    assert result["file_kind"] == "text"
    assert result["tests_failed"] == 1
    assert result["confidence"] == 0.4
    assert any(issue.startswith("legacy_reference:") for issue in result["issues"])
    assert any(
        issue.startswith("missing_python_reference:") for issue in result["issues"]
    )


def test_validate_capability_dry_run_high_confidence() -> None:
    config = _build_config(non_python_enabled=True)
    result = validate_file(
        store=None,
        repo_path=Path.cwd(),
        file_key="README.md",
        config=config,
        dry_run=True,
        agent_name="validator",
        quality_entry={"confidence": 0.9},
        status_entry={"retry_count": 0, "inhibition": 0.0},
    )

    assert result["success"] is True
    assert result["status"] == "validated"
    assert result["updated_confidence"] == 1.0
    assert result["decision_metadata"]["dry_run"] is True
