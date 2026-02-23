"""Unit tests for the Scout agent."""

from __future__ import annotations

import json
from pathlib import Path

from agents.scout import Scout
from environment.pheromone_store import PheromoneStore


class FakeLLMClient:
    """Deterministic fake LLM client for scout tests."""

    def __init__(self, content: str) -> None:
        self.content = content
        self.last_system = ""
        self.last_prompt = ""
        self.calls = 0

    def call(self, prompt: str, system: str | None = None):  # type: ignore[no-untyped-def]
        self.last_prompt = prompt
        self.last_system = system or ""
        self.calls += 1

        class Response:
            tokens_used = 50
            latency_ms = 30

            def __init__(self, content: str) -> None:
                self.content = content

        return Response(self.content)

    def extract_code_block(self, text: str) -> str:
        marker = "```json"
        if marker in text:
            return text.split(marker, 1)[1].split("```", 1)[0].strip()
        marker2 = "```"
        if marker2 in text:
            return text.split(marker2, 1)[1].split("```", 1)[0].strip()
        return text


class FailingLLMClient:
    """LLM client that always raises an exception."""

    def call(self, prompt: str, system: str | None = None):  # type: ignore[no-untyped-def]
        raise RuntimeError("LLM unavailable")

    def extract_code_block(self, text: str) -> str:
        return text


def _build_config() -> dict:
    return {
        "pheromones": {
            "task_intensity_clamp": [0.1, 1.0],
            "decay_type": "exponential",
            "decay_rate": 0.05,
            "inhibition_decay_rate": 0.08,
        },
        "thresholds": {
            "max_retry_count": 3,
            "scope_lock_ttl": 3,
            "transformer_intensity_min": 0.2,
        },
        "llm": {
            "max_tokens_total": 100000,
        },
    }


def test_scout_deposits_tasks_and_pending_status(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)

    (repo_path / "main.py").write_text(
        'print "hello"\nname = raw_input("x")\nfor i in xrange(2):\n    print i\n',
        encoding="utf-8",
    )
    (repo_path / "utils.py").write_text(
        "def x(d):\n    return d.iteritems()\n",
        encoding="utf-8",
    )

    store = PheromoneStore(_build_config(), base_path=tmp_path)
    scout = Scout(
        name="scout",
        config=_build_config(),
        pheromone_store=store,
        target_repo_path=repo_path,
    )

    acted = scout.run()

    assert acted is True

    tasks = store.read_all("tasks")
    status = store.read_all("status")

    assert sorted(tasks.keys()) == ["main.py", "utils.py"]
    assert sorted(status.keys()) == ["main.py", "utils.py"]

    main_task = tasks["main.py"]
    assert main_task["intensity"] >= 0.1
    assert "raw_input" in main_task["patterns_found"]
    assert any(detail["source"] == "regex" for detail in main_task["pattern_details"])

    assert status["main.py"]["status"] == "pending"
    assert status["main.py"]["retry_count"] == 0
    assert status["main.py"]["inhibition"] == 0.0


def test_scout_min_max_normalization_degenerate_case(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)

    content = "def run(d):\n    return d.iteritems()\n"
    (repo_path / "a.py").write_text(content, encoding="utf-8")
    (repo_path / "b.py").write_text(content, encoding="utf-8")

    store = PheromoneStore(_build_config(), base_path=tmp_path)
    scout = Scout(
        name="scout",
        config=_build_config(),
        pheromone_store=store,
        target_repo_path=repo_path,
    )

    scout.run()

    tasks = store.read_all("tasks")
    assert tasks["a.py"]["intensity"] == 0.5
    assert tasks["b.py"]["intensity"] == 0.5


# ---------------------------------------------------------------------------
# Phase 2 tests: LLM-driven Scout
# ---------------------------------------------------------------------------


def test_scout_llm_analysis_structured_pheromones(tmp_path: Path) -> None:
    """Mock LLM returns valid JSON with a novel pattern; verify merge is correct."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)

    (repo_path / "target.py").write_text(
        'print "hello"\nimport foo\n',
        encoding="utf-8",
    )

    llm_response = json.dumps(
        {
            "patterns": [
                {
                    "name": "print_statement",
                    "line": 1,
                    "severity": "high",
                    "description": "print statement needs parentheses",
                },
                {
                    "name": "implicit_relative_import",
                    "line": 2,
                    "severity": "medium",
                    "description": "Uses implicit relative import",
                },
            ],
            "complexity_score": 3.5,
            "summary": "Simple file with print and import issues",
        }
    )

    fake_llm = FakeLLMClient(llm_response)
    config = _build_config()
    config["scout"] = {
        "llm_analysis": {
            "enabled": True,
            "severity_weights": {"high": 1.5, "medium": 1.0, "low": 0.5},
            "intensity_weights": {
                "weighted_patterns": 0.5,
                "dependencies": 0.2,
                "llm_complexity": 0.3,
            },
        }
    }
    store = PheromoneStore(config, base_path=tmp_path)
    scout = Scout(
        name="scout",
        config=config,
        pheromone_store=store,
        target_repo_path=repo_path,
        llm_client=fake_llm,
    )

    acted = scout.run()
    assert acted is True

    tasks = store.read_all("tasks")
    task = tasks["target.py"]

    assert "implicit_relative_import" in task["patterns_found"]
    assert "print_statement" in task["patterns_found"]
    assert task["analysis_source"] == "hybrid"
    assert task["llm_complexity_score"] == 3.5

    # Verify source attribution in pattern_details
    sources = {d["pattern"]: d["source"] for d in task["pattern_details"]}
    assert sources.get("implicit_relative_import") == "llm"
    # print_statement should be llm+regex since both detect it
    assert sources.get("print_statement") in ("llm+regex", "regex")


def test_scout_llm_fallback_on_parse_failure(tmp_path: Path) -> None:
    """Mock LLM returns invalid text; Scout falls back to regex-only."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    (repo_path / "target.py").write_text(
        'print "hello"\n',
        encoding="utf-8",
    )

    fake_llm = FakeLLMClient("This is not valid JSON at all!")
    config = _build_config()
    config["scout"] = {"llm_analysis": {"enabled": True}}
    store = PheromoneStore(config, base_path=tmp_path)
    scout = Scout(
        name="scout",
        config=config,
        pheromone_store=store,
        target_repo_path=repo_path,
        llm_client=fake_llm,
    )

    acted = scout.run()
    assert acted is True

    tasks = store.read_all("tasks")
    task = tasks["target.py"]
    assert task["analysis_source"] == "regex"
    assert "print_statement" in task["patterns_found"]


def test_scout_llm_fallback_on_exception(tmp_path: Path) -> None:
    """Mock LLM raises exception; Scout falls back to regex-only."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    (repo_path / "target.py").write_text(
        'print "hello"\n',
        encoding="utf-8",
    )

    config = _build_config()
    config["scout"] = {"llm_analysis": {"enabled": True}}
    store = PheromoneStore(config, base_path=tmp_path)
    scout = Scout(
        name="scout",
        config=config,
        pheromone_store=store,
        target_repo_path=repo_path,
        llm_client=FailingLLMClient(),
    )

    acted = scout.run()
    assert acted is True

    tasks = store.read_all("tasks")
    task = tasks["target.py"]
    assert task["analysis_source"] == "regex"
    assert "print_statement" in task["patterns_found"]


def test_scout_llm_analysis_handles_null_line_field(tmp_path: Path) -> None:
    """LLM payloads with null line numbers should not crash Scout."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    (repo_path / "target.py").write_text(
        'print "hello"\n',
        encoding="utf-8",
    )

    llm_response = json.dumps(
        {
            "patterns": [
                {
                    "name": "implicit_relative_import",
                    "line": None,
                    "severity": "medium",
                },
            ],
            "complexity_score": 2.0,
        }
    )

    fake_llm = FakeLLMClient(llm_response)
    config = _build_config()
    config["scout"] = {"llm_analysis": {"enabled": True}}
    store = PheromoneStore(config, base_path=tmp_path)
    scout = Scout(
        name="scout",
        config=config,
        pheromone_store=store,
        target_repo_path=repo_path,
        llm_client=fake_llm,
    )

    acted = scout.run()
    assert acted is True

    task = store.read_all("tasks")["target.py"]
    assert "implicit_relative_import" in task["patterns_found"]
    implicit_detail = next(
        entry
        for entry in task["pattern_details"]
        if entry["pattern"] == "implicit_relative_import"
    )
    assert implicit_detail["line"] == 1


def test_scout_skips_missing_candidate_file(tmp_path: Path) -> None:
    """Unreadable or missing files should be skipped without crashing Scout."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    config = _build_config()
    store = PheromoneStore(config, base_path=tmp_path)

    class InjectedScout(Scout):
        def perceive(self) -> dict[str, list[str]]:
            return {"candidate_files": ["ghost.py"], "all_file_keys": ["ghost.py"]}

    scout = InjectedScout(
        name="scout",
        config=config,
        pheromone_store=store,
        target_repo_path=repo_path,
    )

    acted = scout.run()
    assert acted is True
    assert store.read_all("tasks") == {}
    assert store.read_all("status") == {}


def test_scout_hybrid_scoring_severity(tmp_path: Path) -> None:
    """high-severity patterns produce a higher raw_score than low-severity."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)

    (repo_path / "high.py").write_text('print "hello"\n', encoding="utf-8")
    (repo_path / "low.py").write_text('print "hello"\n', encoding="utf-8")

    config = _build_config()
    config["scout"] = {
        "llm_analysis": {
            "enabled": True,
            "severity_weights": {"high": 1.5, "medium": 1.0, "low": 0.5},
            "intensity_weights": {
                "weighted_patterns": 0.5,
                "dependencies": 0.2,
                "llm_complexity": 0.3,
            },
        }
    }

    high_response = json.dumps(
        {
            "patterns": [
                {"name": "print_statement", "line": 1, "severity": "high"},
            ],
            "complexity_score": 8.0,
            "summary": "Complex",
        }
    )
    low_response = json.dumps(
        {
            "patterns": [
                {"name": "print_statement", "line": 1, "severity": "low"},
            ],
            "complexity_score": 2.0,
            "summary": "Simple",
        }
    )

    # Test high-severity file
    store_high = PheromoneStore(config, base_path=tmp_path / "high_store")
    fake_llm_high = FakeLLMClient(high_response)
    scout_high = Scout(
        name="scout",
        config=config,
        pheromone_store=store_high,
        target_repo_path=repo_path,
        llm_client=fake_llm_high,
    )
    perception_high = scout_high.perceive()
    # Only process high.py
    perception_high["candidate_files"] = ["high.py"]
    action_high = scout_high.decide(perception_high)
    raw_high = action_high["analyses"][0]["raw_score"]

    # Test low-severity file
    store_low = PheromoneStore(config, base_path=tmp_path / "low_store")
    fake_llm_low = FakeLLMClient(low_response)
    scout_low = Scout(
        name="scout",
        config=config,
        pheromone_store=store_low,
        target_repo_path=repo_path,
        llm_client=fake_llm_low,
    )
    perception_low = scout_low.perceive()
    perception_low["candidate_files"] = ["low.py"]
    action_low = scout_low.decide(perception_low)
    raw_low = action_low["analyses"][0]["raw_score"]

    assert raw_high > raw_low


def test_scout_novel_patterns_in_output(tmp_path: Path) -> None:
    """A novel LLM-detected pattern appears in patterns_found."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    (repo_path / "target.py").write_text("x = 1\n", encoding="utf-8")

    llm_response = json.dumps(
        {
            "patterns": [
                {
                    "name": "implicit_string_concat",
                    "line": 1,
                    "severity": "low",
                    "description": "Implicit string concatenation across lines",
                },
            ],
            "complexity_score": 1.0,
            "summary": "Minimal",
        }
    )

    fake_llm = FakeLLMClient(llm_response)
    config = _build_config()
    config["scout"] = {"llm_analysis": {"enabled": True}}
    store = PheromoneStore(config, base_path=tmp_path)
    scout = Scout(
        name="scout",
        config=config,
        pheromone_store=store,
        target_repo_path=repo_path,
        llm_client=fake_llm,
    )

    acted = scout.run()
    assert acted is True

    tasks = store.read_all("tasks")
    task = tasks["target.py"]
    assert "implicit_string_concat" in task["patterns_found"]


def test_scout_system_prompt_stigmergic(tmp_path: Path) -> None:
    """The system prompt sent to the LLM contains 'stigmergic'."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    (repo_path / "target.py").write_text('print "hello"\n', encoding="utf-8")

    llm_response = json.dumps(
        {
            "patterns": [],
            "complexity_score": 1.0,
            "summary": "Empty",
        }
    )

    fake_llm = FakeLLMClient(llm_response)
    config = _build_config()
    config["scout"] = {"llm_analysis": {"enabled": True}}
    store = PheromoneStore(config, base_path=tmp_path)
    scout = Scout(
        name="scout",
        config=config,
        pheromone_store=store,
        target_repo_path=repo_path,
        llm_client=fake_llm,
    )

    scout.run()

    assert fake_llm.calls >= 1
    assert "stigmergic" in fake_llm.last_system.lower()


def test_scout_regex_only_without_llm(tmp_path: Path) -> None:
    """Scout without llm_client uses regex-only path (existing behavior)."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)
    (repo_path / "target.py").write_text(
        'print "hello"\nname = raw_input("x")\n',
        encoding="utf-8",
    )

    store = PheromoneStore(_build_config(), base_path=tmp_path)
    scout = Scout(
        name="scout",
        config=_build_config(),
        pheromone_store=store,
        target_repo_path=repo_path,
    )

    acted = scout.run()
    assert acted is True

    tasks = store.read_all("tasks")
    task = tasks["target.py"]
    assert task["analysis_source"] == "regex"
    assert "print_statement" in task["patterns_found"]
    assert "raw_input" in task["patterns_found"]
