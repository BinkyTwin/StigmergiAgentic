"""Unit tests for the provider-aware LLM client wrapper."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
)

from stigmergy.llm_client import LLMClient, ModelPricing


class RetryableStubError(Exception):
    """Custom error used to force retry paths in tests."""


class FakeCompletions:
    """Configurable fake OpenAI completions endpoint."""

    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0
        self.last_kwargs: dict[str, object] = {}

    def create(self, **kwargs: object) -> object:
        self.calls += 1
        self.last_kwargs = kwargs
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
            "max_response_tokens": 256,
            "estimated_completion_tokens": 256,
            "max_tokens_total": 10000,
            "retry_attempts": 3,
            "retry_backoff": [1, 2, 4],
        }
    }


def _build_zai_config() -> dict:
    return {
        "llm": {
            "provider": "zai",
            "model": "glm-5",
            "temperature": 0.2,
            "max_response_tokens": 256,
            "estimated_completion_tokens": 256,
            "max_tokens_total": 10000,
            "retry_attempts": 3,
            "retry_backoff": [1, 2, 4],
        }
    }


def _make_response(
    content: str,
    prompt_tokens: int = 10,
    completion_tokens: int = 20,
    cost: float | str | None = None,
) -> object:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost,
        ),
    )


def test_llm_client_retry_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

    client = LLMClient(_build_config())

    outcomes = [RetryableStubError("retry me"), _make_response("ok")]
    fake_completions = FakeCompletions(outcomes)
    client.client = FakeOpenAIClient(fake_completions)

    sleep_calls: list[float] = []

    monkeypatch.setattr(
        client, "_is_retryable", lambda error: isinstance(error, RetryableStubError)
    )
    monkeypatch.setattr("time.sleep", lambda seconds: sleep_calls.append(seconds))

    result = client.call(prompt="hello")

    assert result.content == "ok"
    assert fake_completions.calls == 2
    assert sleep_calls == [1.0]


def test_llm_client_sets_openai_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    config = _build_config()
    config["llm"]["request_timeout_seconds"] = 42

    captured_kwargs: dict[str, object] = {}

    def fake_openai(**kwargs: object) -> FakeOpenAIClient:
        captured_kwargs.update(kwargs)
        return FakeOpenAIClient(FakeCompletions([_make_response("ok")]))

    monkeypatch.setattr("stigmergy.llm_client.OpenAI", fake_openai)

    LLMClient(config)

    assert captured_kwargs["timeout"] == 42.0


def test_llm_client_uses_zai_provider_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ZAI_API_KEY", "zai-test")
    config = _build_zai_config()

    captured_kwargs: dict[str, object] = {}

    def fake_openai(**kwargs: object) -> FakeOpenAIClient:
        captured_kwargs.update(kwargs)
        return FakeOpenAIClient(FakeCompletions([_make_response("ok")]))

    monkeypatch.setattr("stigmergy.llm_client.OpenAI", fake_openai)

    LLMClient(config)

    assert captured_kwargs["api_key"] == "zai-test"
    assert captured_kwargs["base_url"] == "https://api.z.ai/api/coding/paas/v4"


def test_llm_client_raises_on_unsupported_provider() -> None:
    config = _build_config()
    config["llm"]["provider"] = "unknown"

    with pytest.raises(ValueError, match="Unsupported llm.provider"):
        LLMClient(config)


def test_llm_client_budget_check_blocks_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    config = _build_config()
    config["llm"]["max_tokens_total"] = 32

    client = LLMClient(config)

    with pytest.raises(RuntimeError, match="Token budget exceeded before call"):
        client.call(prompt="x" * 500)


def test_llm_client_omits_max_tokens_when_uncapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    config = _build_config()
    config["llm"]["max_response_tokens"] = 0
    config["llm"]["max_tokens_total"] = 10_000

    client = LLMClient(config)
    fake_completions = FakeCompletions([_make_response("ok")])
    client.client = FakeOpenAIClient(fake_completions)

    result = client.call(prompt="hello")
    assert result.content == "ok"
    assert "max_tokens" not in fake_completions.last_kwargs


def test_llm_client_ignores_max_tokens_even_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    config = _build_config()
    config["llm"]["max_response_tokens"] = 512

    client = LLMClient(config)
    fake_completions = FakeCompletions([_make_response("ok")])
    client.client = FakeOpenAIClient(fake_completions)

    result = client.call(prompt="hello")
    assert result.content == "ok"
    assert "max_tokens" not in fake_completions.last_kwargs


def test_llm_client_cost_budget_check_blocks_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(
        LLMClient,
        "_fetch_model_pricing",
        lambda self: ModelPricing(
            prompt_cost_per_token_usd=0.001,
            completion_cost_per_token_usd=0.001,
        ),
    )

    config = _build_config()
    config["llm"]["max_budget_usd"] = 0.001
    client = LLMClient(config)

    with pytest.raises(RuntimeError, match="Cost budget exceeded before call"):
        client.call(prompt="x" * 200)


def test_llm_client_uses_usage_cost_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    config = _build_config()
    config["llm"]["max_budget_usd"] = 100

    client = LLMClient(config)
    fake_completions = FakeCompletions([_make_response("ok", cost="0.0125")])
    client.client = FakeOpenAIClient(fake_completions)

    response = client.call(prompt="hello")

    assert response.cost_usd == pytest.approx(0.0125)
    assert client.total_cost_usd == pytest.approx(0.0125)


def test_llm_client_estimates_cost_when_usage_cost_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(
        LLMClient,
        "_fetch_model_pricing",
        lambda self: ModelPricing(
            prompt_cost_per_token_usd=0.0001,
            completion_cost_per_token_usd=0.0002,
            request_cost_usd=0.0003,
        ),
    )
    config = _build_config()
    config["llm"]["max_budget_usd"] = 10

    client = LLMClient(config)
    fake_completions = FakeCompletions(
        [_make_response("ok", prompt_tokens=10, completion_tokens=20, cost=None)]
    )
    client.client = FakeOpenAIClient(fake_completions)

    response = client.call(prompt="hello")

    expected = 10 * 0.0001 + 20 * 0.0002 + 0.0003
    assert response.cost_usd == pytest.approx(expected)
    assert client.total_cost_usd == pytest.approx(expected)


def test_extract_code_block() -> None:
    os.environ["OPENROUTER_API_KEY"] = "sk-test"
    client = LLMClient(_build_config())

    text = "prefix\n```python\nprint('ok')\n```\nsuffix"
    assert client.extract_code_block(text) == "print('ok')"


def test_extract_code_block_strips_unclosed_fence() -> None:
    os.environ["OPENROUTER_API_KEY"] = "sk-test"
    client = LLMClient(_build_config())

    text = "```python\nprint('ok')\n"
    assert client.extract_code_block(text) == "print('ok')"


def test_extract_code_block_strips_fence_lines_only() -> None:
    os.environ["OPENROUTER_API_KEY"] = "sk-test"
    client = LLMClient(_build_config())

    text = "```python\nx = 1\n```\n"
    assert client.extract_code_block(text) == "x = 1"


@pytest.mark.live_api
def test_live_api_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    if os.environ.get("RUN_LIVE_API") != "1":
        pytest.skip("Set RUN_LIVE_API=1 to enable live API smoke test")

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        pytest.skip("OPENROUTER_API_KEY not set")

    monkeypatch.setenv("OPENROUTER_API_KEY", api_key)
    config = _build_config()
    config["llm"]["max_response_tokens"] = 64

    client = LLMClient(config)
    try:
        response = client.call(
            prompt="Reply with exactly: pong", system="You are concise."
        )
    except AuthenticationError:
        pytest.skip("OPENROUTER_API_KEY is set but rejected by OpenRouter")
    except (APIStatusError, APIConnectionError, APITimeoutError) as exc:
        pytest.skip(f"OpenRouter transient/provider error during smoke test: {exc}")

    assert isinstance(response.content, str)
    assert response.tokens_used >= 0
