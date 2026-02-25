"""OpenRouter LLM client with retry, budget enforcement, and token tracking."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)


RETRYABLE_STATUS_CODES = {429, 500, 502, 503}
CODE_BLOCK_RE = re.compile(
    r"```(?:python)?\n(?P<code>.*?)```", re.DOTALL | re.IGNORECASE
)
FENCE_LINE_RE = re.compile(r"^\s*```(?:python|py)?\s*$", re.IGNORECASE)
LOGGER = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Standard response envelope for all LLM calls."""

    content: str
    tokens_used: int
    model: str
    latency_ms: int
    cost_usd: float = 0.0


@dataclass
class ModelPricing:
    """Per-token/per-request pricing for one OpenRouter model."""

    prompt_cost_per_token_usd: float
    completion_cost_per_token_usd: float
    request_cost_usd: float = 0.0


class LLMClient:
    """OpenRouter-backed LLM client for migration agents."""

    def __init__(self, config: dict[str, Any]):
        llm_config = config.get("llm", {})

        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is required")

        self.model = str(llm_config.get("model", "qwen/qwen3-235b-a22b-2507"))
        self.temperature = float(llm_config.get("temperature", 0.2))
        raw_max_response_tokens = llm_config.get("max_response_tokens", 0)
        max_response_tokens = int(raw_max_response_tokens)
        # Hard-disable explicit max_tokens: thinking-heavy migrations should never
        # be truncated by a client-side completion cap.
        self.max_response_tokens: int | None = None
        if max_response_tokens > 0:
            LOGGER.warning(
                "llm.max_response_tokens=%s is ignored: client never sends max_tokens",
                max_response_tokens,
            )
        self.estimated_completion_tokens = int(
            llm_config.get("estimated_completion_tokens", 4096)
        )
        self.retry_attempts = int(llm_config.get("retry_attempts", 3))
        self.retry_backoff = list(llm_config.get("retry_backoff", [1, 2, 4]))
        self.budget = int(llm_config.get("max_tokens_total", 100_000))
        self.max_budget_usd = float(llm_config.get("max_budget_usd", 0.0))
        self.pricing_api_timeout_seconds = float(
            llm_config.get("pricing_api_timeout_seconds", 8.0)
        )
        self.request_timeout_seconds = float(
            llm_config.get("request_timeout_seconds", 300.0)
        )
        self.pricing_endpoint = str(
            llm_config.get(
                "pricing_endpoint",
                "https://openrouter.ai/api/v1/models/user",
            )
        )
        self.pricing_strict = bool(llm_config.get("pricing_strict", False))

        self.total_tokens_used = 0
        self.total_cost_usd = 0.0
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://openrouter.ai/api/v1",
            timeout=self.request_timeout_seconds,
        )
        self.model_pricing = (
            self._fetch_model_pricing() if self.max_budget_usd > 0.0 else None
        )
        if (
            self.max_budget_usd > 0.0
            and self.model_pricing is None
            and self.pricing_strict
        ):
            raise RuntimeError(
                "Cost budget configured but OpenRouter pricing unavailable "
                f"for model={self.model}"
            )

    def check_budget(self, estimated_tokens: int) -> bool:
        """Return whether the requested call fits in remaining token budget."""
        return (self.total_tokens_used + int(estimated_tokens)) <= self.budget

    def check_cost_budget(self, estimated_cost_usd: float) -> bool:
        """Return whether the estimated call cost fits in remaining USD budget."""
        if self.max_budget_usd <= 0.0:
            return True
        return (self.total_cost_usd + float(estimated_cost_usd)) <= self.max_budget_usd

    def call(self, prompt: str, system: str | None = None) -> LLMResponse:
        """Call the LLM with retry for transient failures and token accounting."""
        estimated_prompt_tokens, estimated_completion_tokens = self._estimate_usage(
            prompt=prompt,
            system=system,
        )
        estimated_tokens = estimated_prompt_tokens + estimated_completion_tokens
        if not self.check_budget(estimated_tokens=estimated_tokens):
            raise RuntimeError(
                "Token budget exceeded before call: "
                f"used={self.total_tokens_used}, estimated={estimated_tokens}, budget={self.budget}"
            )
        estimated_cost_usd = self._estimate_cost_usd(
            prompt_tokens=estimated_prompt_tokens,
            completion_tokens=estimated_completion_tokens,
        )
        if estimated_cost_usd is not None and not self.check_cost_budget(
            estimated_cost_usd=estimated_cost_usd
        ):
            raise RuntimeError(
                "Cost budget exceeded before call: "
                f"used=${self.total_cost_usd:.6f}, estimated=${estimated_cost_usd:.6f}, "
                f"budget=${self.max_budget_usd:.6f}"
            )

        last_error: Exception | None = None

        for attempt in range(self.retry_attempts):
            try:
                start = time.monotonic()
                request_payload: dict[str, Any] = {
                    "model": self.model,
                    "messages": self._build_messages(prompt=prompt, system=system),
                    "temperature": self.temperature,
                }

                response = self.client.chat.completions.create(
                    **request_payload,
                )

                content = self._extract_content(response)
                usage = getattr(response, "usage", None)
                prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
                completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
                tokens_used = prompt_tokens + completion_tokens
                call_cost_usd = self._extract_usage_cost_usd(usage=usage)
                if call_cost_usd is None:
                    call_cost_usd = self._estimate_cost_usd(
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                    )

                self.total_tokens_used += tokens_used
                if call_cost_usd is not None:
                    self.total_cost_usd += call_cost_usd
                latency_ms = int((time.monotonic() - start) * 1000)

                return LLMResponse(
                    content=content,
                    tokens_used=tokens_used,
                    model=self.model,
                    latency_ms=latency_ms,
                    cost_usd=float(call_cost_usd or 0.0),
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if not self._is_retryable(exc):
                    raise

                has_next_attempt = attempt < self.retry_attempts - 1
                if not has_next_attempt:
                    break

                backoff_seconds = self._backoff_for_attempt(attempt)
                time.sleep(backoff_seconds)

        assert last_error is not None
        raise last_error

    def extract_code_block(self, text: str) -> str:
        """Extract code from markdown fences and sanitize stray markdown wrappers."""
        matches = list(CODE_BLOCK_RE.finditer(text))
        if matches:
            longest = max(matches, key=lambda match: len(match.group("code")))
            return longest.group("code").strip()

        raw = text.strip()
        if not raw:
            return raw

        lines = raw.splitlines()
        cleaned_lines: list[str] = []
        for index, line in enumerate(lines):
            if FENCE_LINE_RE.match(line):
                # Strip isolated markdown fences such as ```python / ``` wrappers.
                continue
            if index == 0 and line.strip().startswith("```"):
                continue
            cleaned_lines.append(line)

        return "\n".join(cleaned_lines).strip()

    def _build_messages(self, prompt: str, system: str | None) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _estimate_usage(self, prompt: str, system: str | None) -> tuple[int, int]:
        payload_chars = len(prompt) + len(system or "")
        estimated_prompt_tokens = max(1, payload_chars // 4)
        completion_allowance = (
            self.max_response_tokens
            if self.max_response_tokens is not None
            else self.estimated_completion_tokens
        )
        return estimated_prompt_tokens, int(completion_allowance)

    def _estimate_tokens(self, prompt: str, system: str | None) -> int:
        prompt_tokens, completion_tokens = self._estimate_usage(
            prompt=prompt,
            system=system,
        )
        return prompt_tokens + completion_tokens

    def _estimate_cost_usd(
        self,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float | None:
        if self.model_pricing is None:
            return None
        estimated = (
            float(prompt_tokens) * self.model_pricing.prompt_cost_per_token_usd
            + float(completion_tokens)
            * self.model_pricing.completion_cost_per_token_usd
            + self.model_pricing.request_cost_usd
        )
        return max(0.0, float(estimated))

    def _extract_usage_cost_usd(self, usage: Any) -> float | None:
        if usage is None:
            return None

        raw_cost = getattr(usage, "cost", None)
        if raw_cost is None and isinstance(usage, dict):
            raw_cost = usage.get("cost")
        if raw_cost is None:
            return None
        return self._safe_float(raw_cost)

    def _fetch_model_pricing(self) -> ModelPricing | None:
        request = Request(
            self.pricing_endpoint,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.pricing_api_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, json.JSONDecodeError) as exc:
            LOGGER.warning(
                "Failed to fetch OpenRouter pricing endpoint=%s model=%s error=%s",
                self.pricing_endpoint,
                self.model,
                exc,
            )
            return None

        model_entry = self._match_model_entry(payload=payload)
        if model_entry is None:
            LOGGER.warning(
                "No pricing entry found for model=%s from endpoint=%s",
                self.model,
                self.pricing_endpoint,
            )
            return None

        raw_pricing = model_entry.get("pricing", {})
        if not isinstance(raw_pricing, dict):
            return None

        prompt_cost = self._safe_float(raw_pricing.get("prompt"))
        completion_cost = self._safe_float(raw_pricing.get("completion"))
        request_cost = self._safe_float(raw_pricing.get("request"))
        if prompt_cost is None or completion_cost is None:
            return None

        return ModelPricing(
            prompt_cost_per_token_usd=prompt_cost,
            completion_cost_per_token_usd=completion_cost,
            request_cost_usd=float(request_cost or 0.0),
        )

    def _match_model_entry(self, payload: Any) -> dict[str, Any] | None:
        entries = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(entries, list):
            return None

        expected = self.model.strip().lower()
        fallback_entry: dict[str, Any] | None = None

        for entry in entries:
            if not isinstance(entry, dict):
                continue

            model_id = str(entry.get("id", "")).strip().lower()
            canonical_slug = str(entry.get("canonical_slug", "")).strip().lower()
            if model_id == expected or canonical_slug == expected:
                return entry

            if fallback_entry is None:
                if model_id.startswith(f"{expected}:") or canonical_slug.startswith(
                    f"{expected}:"
                ):
                    fallback_entry = entry

        return fallback_entry

    def _safe_float(self, raw_value: Any) -> float | None:
        if raw_value in (None, ""):
            return None
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return None
        if value < 0.0:
            return 0.0
        return value

    def _is_retryable(self, error: Exception) -> bool:
        if isinstance(
            error,
            (RateLimitError, InternalServerError, APIConnectionError, APITimeoutError),
        ):
            return True
        if isinstance(error, APIStatusError):
            return error.status_code in RETRYABLE_STATUS_CODES
        return False

    def _backoff_for_attempt(self, attempt: int) -> float:
        if attempt < len(self.retry_backoff):
            return float(self.retry_backoff[attempt])
        return float(self.retry_backoff[-1])

    def _extract_content(self, response: Any) -> str:
        choices = getattr(response, "choices", None)
        if not choices:
            return ""

        message = getattr(choices[0], "message", None)
        if message is None:
            return ""

        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "\n".join(parts)

        return str(content)
