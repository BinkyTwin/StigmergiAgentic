"""Unit tests for the Transformer agent."""

from __future__ import annotations

from pathlib import Path

from agents.transformer import Transformer
from environment.pheromone_store import PheromoneStore


class FakeLLMClient:
    """Deterministic fake LLM client for transformer tests."""

    def __init__(self, content: str) -> None:
        self.content = content
        self.last_prompt = ""
        self.last_system = ""

    def call(self, prompt: str, system: str | None = None):  # type: ignore[no-untyped-def]
        self.last_prompt = prompt
        self.last_system = system or ""

        class Response:
            tokens_used = 123
            latency_ms = 50

            def __init__(self, response_content: str) -> None:
                self.content = response_content

        return Response(self.content)

    def extract_code_block(self, text: str) -> str:
        marker = "```python"
        if marker in text:
            return text.split(marker, 1)[1].split("```", 1)[0].strip()
        return text


def _build_config() -> dict:
    return {
        "pheromones": {
            "inhibition_threshold": 0.1,
            "decay_type": "exponential",
            "decay_rate": 0.05,
            "inhibition_decay_rate": 0.08,
        },
        "thresholds": {
            "transformer_intensity_min": 0.2,
            "max_retry_count": 3,
            "scope_lock_ttl": 3,
        },
        "llm": {
            "max_tokens_total": 100000,
        },
    }


def test_transformer_selects_highest_intensity_and_transforms(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True)

    (repo_path / "target.py").write_text('print "hello"\n', encoding="utf-8")
    (repo_path / "other.py").write_text('print "other"\n', encoding="utf-8")
    (repo_path / "example_validated.py").write_text("print('ok')\n", encoding="utf-8")

    store = PheromoneStore(_build_config(), base_path=tmp_path)

    store.write(
        "tasks",
        "target.py",
        {"intensity": 0.9, "patterns_found": ["print_statement"]},
        agent_id="scout",
    )
    store.write(
        "tasks",
        "other.py",
        {"intensity": 0.3, "patterns_found": ["print_statement"]},
        agent_id="scout",
    )
    store.write(
        "tasks",
        "example_validated.py",
        {"intensity": 0.2, "patterns_found": ["print_statement"]},
        agent_id="scout",
    )

    store.write(
        "status",
        "target.py",
        {"status": "retry", "retry_count": 1, "inhibition": 0.0},
        agent_id="scout",
    )
    store.write(
        "status",
        "other.py",
        {"status": "pending", "retry_count": 0, "inhibition": 0.0},
        agent_id="scout",
    )
    store.write(
        "status",
        "example_validated.py",
        {"status": "validated", "retry_count": 0, "inhibition": 0.0},
        agent_id="validator",
    )

    store.write(
        "quality",
        "target.py",
        {
            "confidence": 0.4,
            "tests_total": 1,
            "tests_passed": 0,
            "tests_failed": 1,
            "coverage": 0.0,
            "issues": ["missing print parentheses"],
        },
        agent_id="tester",
    )
    store.write(
        "quality",
        "example_validated.py",
        {
            "confidence": 0.95,
            "tests_total": 1,
            "tests_passed": 1,
            "tests_failed": 0,
            "coverage": 1.0,
            "issues": [],
        },
        agent_id="tester",
    )

    fake_llm = FakeLLMClient("""```python\nprint('hello')\n```""")
    transformer = Transformer(
        name="transformer",
        config=_build_config(),
        pheromone_store=store,
        target_repo_path=repo_path,
        llm_client=fake_llm,
    )

    acted = transformer.run()

    assert acted is True
    assert "Few-shot examples from validated traces" in fake_llm.last_prompt
    assert "Retry context from previous failures" in fake_llm.last_prompt

    transformed_text = (repo_path / "target.py").read_text(encoding="utf-8")
    assert "print('hello')" in transformed_text

    status_entry = store.read_one("status", "target.py")
    assert status_entry is not None
    assert status_entry["status"] == "transformed"
    assert status_entry["metadata"]["tokens_used"] == 123
