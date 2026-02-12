"""Unit tests for the OpenRouter LLM client wrapper."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError, AuthenticationError

from stigmergy.llm_client import LLMClient


class RetryableStubError(Exception):
    """Custom error used to force retry paths in tests."""


class FakeCompletions:
    """Configurable fake OpenAI completions endpoint."""

    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def create(self, **_: object) -> object:
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
            "model": "qwen/qwen3-235b-a22b-2507",
            "temperature": 0.2,
            "max_response_tokens": 256,
            "max_tokens_total": 2000,
            "retry_attempts": 3,
            "retry_backoff": [1, 2, 4],
        }
    }


def _make_response(
    content: str, prompt_tokens: int = 10, completion_tokens: int = 20
) -> object:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
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


def test_llm_client_budget_check_blocks_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    config = _build_config()
    config["llm"]["max_tokens_total"] = 32

    client = LLMClient(config)

    with pytest.raises(RuntimeError, match="Token budget exceeded before call"):
        client.call(prompt="x" * 500)


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
