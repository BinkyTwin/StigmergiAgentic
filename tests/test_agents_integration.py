"""Integration tests for Sprint 2 agent handoffs through pheromones."""

from __future__ import annotations

from pathlib import Path

from git import Repo

from agents.scout import Scout
from agents.tester import Tester
from agents.transformer import Transformer
from agents.validator import Validator
from environment.pheromone_store import PheromoneStore


class FakeLLMClient:
    """Simple deterministic LLM stub for integration flows."""

    def __init__(self, transformed_content: str) -> None:
        self.transformed_content = transformed_content

    def call(self, prompt: str, system: str | None = None):  # type: ignore[no-untyped-def]
        class Response:
            tokens_used = 80
            latency_ms = 10

            def __init__(self, content: str) -> None:
                self.content = content

        return Response(self.transformed_content)

    def extract_code_block(self, text: str) -> str:
        return text


def _build_config() -> dict:
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
    }


def _init_repo(repo_path: Path, files: dict[str, str]) -> Repo:
    repo_path.mkdir(parents=True)
    for relative_path, content in files.items():
        target = repo_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    repo = Repo.init(repo_path)
    repo.git.add(".")
    repo.index.commit("initial")
    return repo


def test_scout_to_transformer_handoff(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    _init_repo(
        repo_path,
        {
            "module.py": 'print "hello"\n',
        },
    )

    store = PheromoneStore(_build_config(), base_path=tmp_path)

    scout = Scout("scout", _build_config(), store, repo_path)
    transformer = Transformer(
        "transformer",
        _build_config(),
        store,
        repo_path,
        llm_client=FakeLLMClient("print('hello')\n"),
    )

    assert scout.run() is True
    assert transformer.run() is True

    status = store.read_one("status", "module.py")
    assert status is not None
    assert status["status"] == "transformed"


def test_transformer_to_tester_handoff(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    _init_repo(
        repo_path,
        {
            "sample.py": 'print "legacy"\n',
            "tests/test_sample.py": "from sample import value\n\n\ndef test_value():\n    assert value() == 1\n",
        },
    )

    store = PheromoneStore(_build_config(), base_path=tmp_path)
    store.write(
        "tasks",
        "sample.py",
        {"intensity": 0.9, "patterns_found": ["print_statement"]},
        agent_id="scout",
    )
    store.write(
        "status",
        "sample.py",
        {"status": "pending", "retry_count": 0, "inhibition": 0.0},
        agent_id="scout",
    )

    transformer = Transformer(
        "transformer",
        _build_config(),
        store,
        repo_path,
        llm_client=FakeLLMClient("def value():\n    return 1\n"),
    )
    tester = Tester("tester", _build_config(), store, repo_path)

    assert transformer.run() is True
    assert tester.run() is True

    quality = store.read_one("quality", "sample.py")
    status = store.read_one("status", "sample.py")

    assert quality is not None
    assert quality["confidence"] == 1.0
    assert status is not None
    assert status["status"] == "tested"


def test_tester_to_validator_handoff(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    _init_repo(
        repo_path,
        {
            "module.py": "def value():\n    return 1\n",
        },
    )

    (repo_path / "module.py").write_text(
        "def value():\n    return 2\n", encoding="utf-8"
    )

    store = PheromoneStore(_build_config(), base_path=tmp_path)
    store.write(
        "status",
        "module.py",
        {"status": "tested", "retry_count": 0, "inhibition": 0.0},
        agent_id="tester",
    )
    store.write(
        "quality",
        "module.py",
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

    validator = Validator("validator", _build_config(), store, repo_path)
    assert validator.run() is True

    status = store.read_one("status", "module.py")
    assert status is not None
    assert status["status"] == "validated"


def test_full_single_file_cycle(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    _init_repo(
        repo_path,
        {
            "module.py": "def add(a, b):\n    print a + b\n    return a + b\n",
            "tests/test_module.py": "from module import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n",
        },
    )

    store = PheromoneStore(_build_config(), base_path=tmp_path)

    scout = Scout("scout", _build_config(), store, repo_path)
    transformer = Transformer(
        "transformer",
        _build_config(),
        store,
        repo_path,
        llm_client=FakeLLMClient(
            "def add(a, b):\n    print(a + b)\n    return a + b\n"
        ),
    )
    tester = Tester("tester", _build_config(), store, repo_path)
    validator = Validator("validator", _build_config(), store, repo_path)

    assert scout.run() is True
    assert transformer.run() is True
    assert tester.run() is True
    assert validator.run() is True

    status = store.read_one("status", "module.py")
    quality = store.read_one("quality", "module.py")

    assert status is not None
    assert status["status"] == "validated"
    assert quality is not None
    assert quality["confidence"] >= 0.9
