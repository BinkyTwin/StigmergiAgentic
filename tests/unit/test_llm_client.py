"""Unit tests for provider-aware LLM client."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from llm.client import LLMClient, ModelPricing


class FakeRetryableError(Exception):
    """Custom exception used to exercise retry path."""


class FakeCompletions:
    """Fake completions endpoint with scripted outcomes."""

    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def create(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        current = self.outcomes.pop(0)
        if isinstance(current, Exception):
            raise current
        return current


class FakeChat:
    def __init__(self, completions: FakeCompletions) -> None:
        self.completions = completions


class FakeOpenAIClient:
    def __init__(self, completions: FakeCompletions) -> None:
        self.chat = FakeChat(completions)


def _build_config() -> dict:
    return {
        "llm": {
            "provider": "openrouter",
            "model": "qwen/qwen3-235b-a22b-2507",
            "temperature": 0.2,
            "max_tokens_total": 10000,
            "max_budget_usd": 0.0,
            "retry_attempts": 2,
            "retry_backoff": [1],
            "retry_jitter_seconds": 0.0,
        }
    }


def _make_response(
    content: str,
    prompt_tokens: int = 10,
    completion_tokens: int = 20,
    cost: float | str | None = None,
):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost,
        ),
    )


def test_llm_client_rejects_unsupported_provider() -> None:
    config = _build_config()
    config["llm"]["provider"] = "unknown"

    with pytest.raises(ValueError, match="Unsupported llm.provider"):
        LLMClient(config)


def test_llm_client_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        LLMClient(_build_config())


def test_llm_client_retries_on_retryable_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

    client = LLMClient(_build_config())
    client.client = FakeOpenAIClient(
        FakeCompletions([FakeRetryableError("retry"), _make_response("ok")])
    )
    monkeypatch.setattr(client, "_is_retryable", lambda error: isinstance(error, FakeRetryableError))
    monkeypatch.setattr("time.sleep", lambda seconds: None)

    result = client.call(prompt="hello")
    assert result.content == "ok"


def test_llm_client_blocks_token_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    config = _build_config()
    config["llm"]["max_tokens_total"] = 5

    client = LLMClient(config)
    with pytest.raises(RuntimeError, match="Token budget exceeded before call"):
        client.call(prompt="x" * 200)


def test_llm_client_blocks_cost_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(
        LLMClient,
        "_fetch_model_pricing",
        lambda self: ModelPricing(
            prompt_cost_per_token_usd=0.001,
            completion_cost_per_token_usd=0.001,
            request_cost_usd=0.0,
        ),
    )

    config = _build_config()
    config["llm"]["max_budget_usd"] = 0.001
    client = LLMClient(config)

    with pytest.raises(RuntimeError, match="Cost budget exceeded before call"):
        client.call(prompt="x" * 200)


def test_extract_code_block_handles_markdown_fences(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    client = LLMClient(_build_config())

    extracted = client.extract_code_block("```python\nprint('ok')\n```")
    cleaned = client.extract_code_block("```python\nprint('ok')")

    assert extracted == "print('ok')"
    assert cleaned == "print('ok')"
