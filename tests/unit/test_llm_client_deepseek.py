"""Tests for the DeepSeek provider path in LLMClient."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from llm.client import LLMClient, STATIC_PRICING


@pytest.fixture(autouse=True)
def _deepseek_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")


def _build_client() -> LLMClient:
    config = {
        "llm": {
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "max_tokens_total": 100_000,
        }
    }
    return LLMClient(config)


def test_deepseek_provider_uses_static_pricing() -> None:
    client = _build_client()
    assert client.model_pricing is not None
    assert client.base_url == "https://api.deepseek.com"
    expected = STATIC_PRICING["deepseek"]["deepseek-v4-flash"]
    assert client.model_pricing.prompt_cost_per_token_usd == pytest.approx(
        expected["prompt_cache_miss"]
    )
    assert client.model_pricing.completion_cost_per_token_usd == pytest.approx(
        expected["completion"]
    )
    assert client.model_pricing.prompt_cache_hit_cost_per_token_usd == pytest.approx(
        expected["prompt_cache_hit"]
    )


def test_deepseek_cost_uses_cache_hit_rate_when_available() -> None:
    client = _build_client()
    cost = client._estimate_cost_usd(
        prompt_tokens=100,
        completion_tokens=50,
        cache_hit_tokens=80,
        cache_miss_tokens=20,
    )
    pricing = STATIC_PRICING["deepseek"]["deepseek-chat"]
    expected = (
        80 * pricing["prompt_cache_hit"]
        + 20 * pricing["prompt_cache_miss"]
        + 50 * pricing["completion"]
    )
    assert cost == pytest.approx(expected)


def test_extract_cache_tokens_reads_deepseek_usage() -> None:
    client = _build_client()
    usage = SimpleNamespace(
        prompt_tokens=100,
        completion_tokens=50,
        prompt_cache_hit_tokens=80,
        prompt_cache_miss_tokens=20,
    )
    hit, miss = client._extract_cache_tokens(usage=usage)
    assert hit == 80
    assert miss == 20


def test_extract_cache_tokens_returns_none_when_absent() -> None:
    client = _build_client()
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5)
    hit, miss = client._extract_cache_tokens(usage=usage)
    assert hit is None
    assert miss is None


def test_deepseek_chat_alias_uses_v4_flash_pricing() -> None:
    config = {
        "llm": {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "max_tokens_total": 100_000,
        }
    }
    client = LLMClient(config)
    flash = STATIC_PRICING["deepseek"]["deepseek-v4-flash"]
    assert client.model_pricing is not None
    assert client.model_pricing.prompt_cost_per_token_usd == pytest.approx(
        flash["prompt_cache_miss"]
    )


def test_deepseek_non_thinking_mode_uses_extra_body_disabled() -> None:
    config = {
        "llm": {
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "max_tokens_total": 100_000,
            "reasoning": {"mode": "non-thinking"},
        }
    }
    client = LLMClient(config)
    payload = {"temperature": 0.2}

    client._apply_provider_request_options(payload)

    assert payload["temperature"] == 0.2
    assert payload["extra_body"] == {"thinking": {"type": "disabled"}}


def test_deepseek_thinking_effort_removes_temperature() -> None:
    config = {
        "llm": {
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "max_tokens_total": 100_000,
            "reasoning": {"mode": "thinking", "effort": "high"},
        }
    }
    client = LLMClient(config)
    payload = {"temperature": 0.2}

    client._apply_provider_request_options(payload)

    assert "temperature" not in payload
    assert payload["reasoning_effort"] == "high"
    assert payload["extra_body"] == {"thinking": {"type": "enabled"}}
