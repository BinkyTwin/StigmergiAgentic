"""V12.4 SD-Feedback text LLM provider.

Unlike V12.2 native tool calls, the official SD-Feedback baseline asks the
model for prose plus grouped ``[Find]/[Replace]`` blocks. This provider keeps
that raw text contract and writes full redacted traces for audit.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from core_v12.agent_loop import redact_secrets


LOGGER = logging.getLogger("scripts.bench.providers_v12_sd_feedback")

TRACE_SCHEMA_VERSION = "v12_4.sd_feedback_llm_trace.v1"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"


@dataclass(frozen=True)
class SDFeedbackLLMConfig:
    """Resolved OpenAI-compatible text completion config for SD-Feedback."""

    provider: str
    model: str
    base_url: str
    api_key: str
    timeout_seconds: float = 180.0
    max_tokens: int = 4000
    temperature: float = 0.0
    extra_headers: dict[str, str] = field(default_factory=dict)
    trace_dir: Path | None = None

    @classmethod
    def from_extras(cls, extras: dict[str, Any]) -> "SDFeedbackLLMConfig | None":
        """Build config from campaign extras; no deterministic fallback here."""

        if extras.get("use_llm_providers") is False:
            return None
        llm = dict(extras.get("v12_4_llm") or extras.get("llm") or {})
        provider = str(llm.get("provider", extras.get("provider", "deepseek"))).lower()
        model = str(llm.get("model") or DEFAULT_DEEPSEEK_MODEL)
        env_var = str(
            llm.get("api_key_env")
            or {
                "deepseek": "DEEPSEEK_API_KEY",
                "openrouter": "OPENROUTER_API_KEY",
                "openai": "OPENAI_API_KEY",
            }.get(provider, "DEEPSEEK_API_KEY")
        )
        api_key = str(llm.get("api_key") or os.environ.get(env_var) or "").strip()
        if not api_key:
            api_key = _load_env_key(Path(".env"), env_var)
        if not api_key:
            LOGGER.warning("%s not set; SD-Feedback LLM provider unavailable", env_var)
            return None
        base_url = str(
            llm.get("base_url")
            or extras.get("v12_4_llm_base_url")
            or {
                "deepseek": "https://api.deepseek.com",
                "openrouter": "https://openrouter.ai/api/v1",
                "openai": "https://api.openai.com/v1",
            }.get(provider, "https://api.deepseek.com")
        )
        trace_enabled = _coerce_bool(
            llm.get("trace_enabled", extras.get("llm_trace_enabled")),
            default=True,
        )
        trace_dir_raw = llm.get("trace_dir") or extras.get("llm_trace_dir")
        if trace_dir_raw is None and extras.get("out_dir"):
            trace_dir_raw = Path(str(extras["out_dir"])) / "llm_traces"
        trace_dir = Path(str(trace_dir_raw)) if trace_enabled and trace_dir_raw else None
        return cls(
            provider=provider,
            model=model,
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=float(llm.get("timeout_seconds", extras.get("llm_timeout_seconds", 180.0))),
            max_tokens=int(llm.get("max_tokens", extras.get("llm_max_tokens", 4000))),
            temperature=float(llm.get("temperature", extras.get("temperature", 0.0))),
            extra_headers=dict(llm.get("extra_headers") or {}),
            trace_dir=trace_dir,
        )


@dataclass(frozen=True)
class SDFeedbackLLMResponse:
    """Raw SD-Feedback model text plus call metadata."""

    content: str
    raw_response: dict[str, Any] | None = None
    error: str | None = None
    duration_seconds: float | None = None
    finish_reason: str | None = None
    usage: dict[str, Any] | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class SDFeedbackTraceWriter:
    """Persist redacted SD-Feedback LLM call traces."""

    def __init__(self, trace_dir: Path | None) -> None:
        self.trace_dir = trace_dir

    def write(self, record: dict[str, Any]) -> None:
        if self.trace_dir is None:
            return
        payload = redact_secrets(
            {
                "schema_version": TRACE_SCHEMA_VERSION,
                "timestamp_utc": datetime.now(UTC).isoformat(),
                **record,
            }
        )
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        instance_id = _safe_trace_name(str(payload.get("instance_id") or "unknown"))
        line = json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
        for path in (
            self.trace_dir / "calls.jsonl",
            self.trace_dir / f"{instance_id}.jsonl",
        ):
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line)


class SDFeedbackTextClient:
    """OpenAI-compatible text client for official SD-Feedback prompts."""

    def __init__(self, config: SDFeedbackLLMConfig) -> None:
        self.config = config
        self.trace_writer = SDFeedbackTraceWriter(config.trace_dir)

    def complete(
        self,
        *,
        prompt: str,
        messages: Sequence[dict[str, str]] = (),
        instance_id: str,
        arm_id: str,
        iteration: int,
        prompt_kind: str,
        metadata: dict[str, Any] | None = None,
    ) -> SDFeedbackLLMResponse:
        """Call chat completion and trace the full redacted prompt/response."""

        started = time.time()
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                *list(messages),
                {"role": "user", "content": prompt},
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if self.config.provider == "deepseek":
            payload["thinking"] = {"type": "disabled"}
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            **dict(self.config.extra_headers or {}),
        }
        try:
            request = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(
                request,
                timeout=self.config.timeout_seconds,
            ) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[-4000:]
            result = SDFeedbackLLMResponse(
                content="",
                raw_response=None,
                error=f"api_call_failed:HTTPError:{exc.code}:{body}",
                duration_seconds=time.time() - started,
            )
            self._trace(prompt, messages, instance_id, arm_id, iteration, prompt_kind, result, metadata)
            return result
        except Exception as exc:  # noqa: BLE001
            result = SDFeedbackLLMResponse(
                content="",
                raw_response=None,
                error=f"api_call_failed:{type(exc).__name__}:{exc}",
                duration_seconds=time.time() - started,
            )
            self._trace(prompt, messages, instance_id, arm_id, iteration, prompt_kind, result, metadata)
            return result
        choices = data.get("choices") or []
        choice = choices[0] if choices else {}
        message = choice.get("message") or {}
        result = SDFeedbackLLMResponse(
            content=str(message.get("content") or ""),
            raw_response=data,
            duration_seconds=time.time() - started,
            finish_reason=choice.get("finish_reason"),
            usage=data.get("usage") or {},
        )
        self._trace(prompt, messages, instance_id, arm_id, iteration, prompt_kind, result, metadata)
        return result

    def _trace(
        self,
        prompt: str,
        messages: Sequence[dict[str, str]],
        instance_id: str,
        arm_id: str,
        iteration: int,
        prompt_kind: str,
        response: SDFeedbackLLMResponse,
        metadata: dict[str, Any] | None,
    ) -> None:
        self.trace_writer.write(
            {
                "provider": self.config.provider,
                "model": self.config.model,
                "base_url": self.config.base_url,
                "instance_id": instance_id,
                "arm_id": arm_id,
                "iteration": int(iteration),
                "prompt_kind": prompt_kind,
                "messages": list(messages),
                "prompt": prompt,
                "raw_response": response.raw_response,
                "raw_text": response.content,
                "call_error": response.error,
                "duration_seconds": response.duration_seconds,
                "finish_reason": response.finish_reason,
                "usage": response.usage or {},
                "metadata": metadata or {},
            }
        )


def _load_env_key(path: Path, key: str) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    prefix = f"{key}="
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or not line.startswith(prefix):
            continue
        return line[len(prefix) :].strip().strip("'\"")
    return ""


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _safe_trace_name(value: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value))[:160] or "unknown"


__all__ = [
    "SDFeedbackLLMConfig",
    "SDFeedbackLLMResponse",
    "SDFeedbackTextClient",
    "SDFeedbackTraceWriter",
]
