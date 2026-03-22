"""Unit tests for provider-aware LLM client."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from core.schemas import ThinkOutput
from llm.client import LLMClient, ModelPricing


class FakeRetryableError(Exception):
    """Custom exception used to exercise retry path."""


class FakeCompletions:
    """Fake completions endpoint with scripted outcomes."""

    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0
        self.last_kwargs: dict | None = None

    def create(self, **kwargs):  # type: ignore[no-untyped-def]
        self.last_kwargs = kwargs
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


class AsyncFakeCompletions:
    """Async fake completions endpoint with optional delay and concurrency tracking."""

    def __init__(self, outcomes: list[object], delay_seconds: float = 0.0) -> None:
        self.outcomes = list(outcomes)
        self.delay_seconds = delay_seconds
        self.calls = 0
        self.active = 0
        self.max_active = 0
        self.last_kwargs: dict | None = None

    async def create(self, **kwargs):  # type: ignore[no-untyped-def]
        self.last_kwargs = kwargs
        self.calls += 1
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            if self.delay_seconds > 0.0:
                await asyncio.sleep(self.delay_seconds)
            current = self.outcomes.pop(0)
            if isinstance(current, Exception):
                raise current
            return current
        finally:
            self.active -= 1


class AsyncFakeChat:
    def __init__(self, completions: AsyncFakeCompletions) -> None:
        self.completions = completions


class AsyncFakeOpenAIClient:
    def __init__(self, completions: AsyncFakeCompletions) -> None:
        self.chat = AsyncFakeChat(completions)


def _build_config() -> dict:
    return {
        "llm": {
            "provider": "openrouter",
            "model": "qwen/qwen3.5-9b",
            "temperature": 0.2,
            "max_tokens_total": 10000,
            "max_budget_usd": 0.0,
            "retry_attempts": 2,
            "retry_backoff": [1],
            "retry_jitter_seconds": 0.0,
        },
        "async": {
            "max_concurrent_llm_calls": 4,
            "subprocess_timeout": 120,
        },
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


def test_llm_client_call_can_parse_structured_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    client = LLMClient(_build_config())
    client.client = FakeOpenAIClient(
        FakeCompletions([_make_response('{"analysis":"ok","path":"README.md"}')])
    )

    result = client.call(prompt="hello", response_schema=ThinkOutput)
    assert isinstance(result.parsed, ThinkOutput)
    assert result.parsed is not None
    assert result.parsed.path == "README.md"


def test_llm_client_forwards_max_tokens_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    config = _build_config()
    config["llm"]["max_response_tokens"] = 128

    completions = FakeCompletions([_make_response("ok")])
    client = LLMClient(config)
    client.client = FakeOpenAIClient(completions)

    client.call(prompt="hello")

    assert completions.last_kwargs is not None
    assert completions.last_kwargs["max_tokens"] == 128


def test_llm_client_forwards_reasoning_config_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    config = _build_config()
    config["llm"]["reasoning"] = {"effort": "none", "exclude": True}

    completions = FakeCompletions([_make_response("ok")])
    client = LLMClient(config)
    client.client = FakeOpenAIClient(completions)

    client.call(prompt="hello")

    assert completions.last_kwargs is not None
    assert completions.last_kwargs["extra_body"] == {
        "reasoning": {"effort": "none", "exclude": True}
    }


def test_llm_client_acall_parses_structured_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    client = LLMClient(_build_config())
    client.async_client = AsyncFakeOpenAIClient(
        AsyncFakeCompletions(
            [_make_response('{"analysis":"Use file_read first","path":"README.md"}')]
        )
    )

    result = asyncio.run(
        client.acall(prompt="hello", response_schema=ThinkOutput)
    )
    assert isinstance(result.parsed, ThinkOutput)
    assert result.parsed is not None
    assert result.parsed.path == "README.md"


def test_llm_client_acall_forwards_max_tokens_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    config = _build_config()
    config["llm"]["max_response_tokens"] = 128

    completions = AsyncFakeCompletions([_make_response("ok")])
    client = LLMClient(config)
    client.async_client = AsyncFakeOpenAIClient(completions)

    asyncio.run(client.acall(prompt="hello"))

    assert completions.last_kwargs is not None
    assert completions.last_kwargs["max_tokens"] == 128


def test_llm_client_acall_keeps_raw_when_schema_validation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    client = LLMClient(_build_config())
    client.async_client = AsyncFakeOpenAIClient(
        AsyncFakeCompletions([_make_response('{"path":"README.md"}')])
    )

    result = asyncio.run(client.acall(prompt="hello", response_schema=ThinkOutput))
    assert result.parsed is None
    assert result.parsed_response is not None
    assert result.parsed_response.is_valid is False
    assert "analysis" in str(result.parsed_response.validation_error)


def test_llm_client_acall_limits_concurrency_with_semaphore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    config = _build_config()
    config["async"]["max_concurrent_llm_calls"] = 1
    client = LLMClient(config)
    fake = AsyncFakeCompletions(
        [_make_response("ok-1"), _make_response("ok-2")],
        delay_seconds=0.05,
    )
    client.async_client = AsyncFakeOpenAIClient(fake)

    async def _run_two_calls() -> None:
        await asyncio.gather(
            client.acall(prompt="first"),
            client.acall(prompt="second"),
        )

    asyncio.run(_run_two_calls())
    assert fake.max_active == 1


def test_llm_client_acall_enforces_budget_precheck(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    config = _build_config()
    config["llm"]["max_tokens_total"] = 5
    client = LLMClient(config)

    with pytest.raises(RuntimeError, match="Token budget exceeded before call"):
        asyncio.run(client.acall(prompt="x" * 200))
