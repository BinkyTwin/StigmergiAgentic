"""OpenRouter LLM client with retry, budget enforcement, and token tracking."""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Any

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


@dataclass
class LLMResponse:
    """Standard response envelope for all LLM calls."""

    content: str
    tokens_used: int
    model: str
    latency_ms: int


class LLMClient:
    """OpenRouter-backed LLM client for migration agents."""

    def __init__(self, config: dict[str, Any]):
        llm_config = config.get("llm", {})

        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is required")

        self.model = str(llm_config.get("model", "qwen/qwen3-235b-a22b-2507"))
        self.temperature = float(llm_config.get("temperature", 0.2))
        self.max_response_tokens = int(llm_config.get("max_response_tokens", 4096))
        self.retry_attempts = int(llm_config.get("retry_attempts", 3))
        self.retry_backoff = list(llm_config.get("retry_backoff", [1, 2, 4]))
        self.budget = int(llm_config.get("max_tokens_total", 100_000))

        self.total_tokens_used = 0
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://openrouter.ai/api/v1",
        )

    def check_budget(self, estimated_tokens: int) -> bool:
        """Return whether the requested call fits in remaining token budget."""
        return (self.total_tokens_used + int(estimated_tokens)) <= self.budget

    def call(self, prompt: str, system: str | None = None) -> LLMResponse:
        """Call the LLM with retry for transient failures and token accounting."""
        estimated_tokens = self._estimate_tokens(prompt=prompt, system=system)
        if not self.check_budget(estimated_tokens=estimated_tokens):
            raise RuntimeError(
                "Token budget exceeded before call: "
                f"used={self.total_tokens_used}, estimated={estimated_tokens}, budget={self.budget}"
            )

        last_error: Exception | None = None

        for attempt in range(self.retry_attempts):
            try:
                start = time.monotonic()
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self._build_messages(prompt=prompt, system=system),
                    temperature=self.temperature,
                    max_tokens=self.max_response_tokens,
                )

                content = self._extract_content(response)
                usage = getattr(response, "usage", None)
                prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
                completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
                tokens_used = prompt_tokens + completion_tokens

                self.total_tokens_used += tokens_used
                latency_ms = int((time.monotonic() - start) * 1000)

                return LLMResponse(
                    content=content,
                    tokens_used=tokens_used,
                    model=self.model,
                    latency_ms=latency_ms,
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
        """Extract code from markdown fenced block, fallback to raw text."""
        match = CODE_BLOCK_RE.search(text)
        if match:
            return match.group("code").strip()
        return text.strip()

    def _build_messages(self, prompt: str, system: str | None) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _estimate_tokens(self, prompt: str, system: str | None) -> int:
        payload_chars = len(prompt) + len(system or "")
        estimated_prompt_tokens = max(1, payload_chars // 4)
        return estimated_prompt_tokens + self.max_response_tokens

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
