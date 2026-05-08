"""V12 MigrationBench LLM tool chooser using native OpenAI-compatible calls.

This module is intentionally separate from ``providers_llm.py``. V10/V11 ask
the model for edit sets; V12.2 asks the model for one native function tool call
and lets the local ToolExecutor perform the guarded action.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from core_v10.contracts import Observation, RunInstance, to_jsonable
from core_v12.agent_loop import AgentStep, ToolChoiceError, redact_secrets
from core_v12.medium.local_view import AgentLocalView
from core_v12.tools.native_schema import (
    NativeToolCallParseError,
    parse_native_tool_call_message,
    registry_to_native_tools,
    tool_schema_hash,
)
from core_v12.tools.schema import ToolCall, ToolSpec


LOGGER = logging.getLogger("scripts.bench.providers_v12_llm")

TRACE_SCHEMA_VERSION = "v12.llm_native_tool_trace.v1"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
SYSTEM_PROMPT_V12_NATIVE_TOOLS = """You are an autonomous Java migration agent.

You operate under the V12 scientific contract:
- the medium guides but never patches;
- you choose exactly one tool and all of its parameters;
- you may call any non-forbidden tool from the registry;
- medium annotations are guidance, not hard constraints;
- if you choose an inhibited tool, explain why in rationale;
- if you ignore a strongly supported tool, explain why in rationale;
- only edit_file_guarded or apply_patch may create a patch;
- suggest_* tools return proposals only and never mutate the workspace;
- inspect before editing when the local view recommends it;
- never output a free-form patch in assistant text.

Return exactly one native function tool call. Do not answer in prose.
"""


@dataclass(frozen=True)
class V12LLMConfig:
    """Resolved OpenAI-compatible native tool-call configuration."""

    provider: str
    model: str
    base_url: str
    api_key: str
    timeout_seconds: float = 120.0
    max_tokens: int = 1500
    temperature: float = 0.0
    strict_tools: bool = True
    max_schema_retries: int = 1
    extra_headers: dict[str, str] = field(default_factory=dict)
    trace_dir: Path | None = None

    @classmethod
    def from_extras(cls, extras: dict[str, Any]) -> "V12LLMConfig | None":
        """Build config from bench extras without deterministic fallback."""

        llm = dict(extras.get("v12_llm") or extras.get("llm") or {})
        if not _coerce_bool(extras.get("use_v12_llm_provider"), default=True):
            return None
        provider = (
            str(llm.get("provider", extras.get("provider", "deepseek")))
            .strip()
            .lower()
        )
        strict_tools = _coerce_bool(
            llm.get("strict_tools", extras.get("v12_strict_tools")),
            default=True,
        )
        model = _resolve_model(provider=provider, llm=llm)
        env_var_map = {
            "deepseek": "DEEPSEEK_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "openai": "OPENAI_API_KEY",
        }
        env_var = str(
            llm.get("api_key_env") or env_var_map.get(provider, "DEEPSEEK_API_KEY")
        )
        api_key = str(llm.get("api_key") or os.environ.get(env_var, "")).strip()
        if not api_key:
            api_key = _load_env_key(Path(".env"), env_var)
        if not api_key:
            LOGGER.warning(
                "providers_v12_llm: %s not set; V12 provider unavailable", env_var
            )
            return None

        explicit_base_url = llm.get("base_url") or extras.get("v12_llm_base_url")
        if explicit_base_url:
            base_url = str(explicit_base_url)
        elif provider == "deepseek" and strict_tools:
            base_url = "https://api.deepseek.com/beta"
        else:
            base_url = {
                "deepseek": "https://api.deepseek.com",
                "openrouter": "https://openrouter.ai/api/v1",
                "openai": "https://api.openai.com/v1",
            }.get(provider, "https://api.deepseek.com")

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
            timeout_seconds=float(llm.get("timeout_seconds", 120.0)),
            max_tokens=int(llm.get("max_tokens", 1500)),
            temperature=float(llm.get("temperature", 0.0)),
            strict_tools=strict_tools,
            max_schema_retries=max(0, int(llm.get("max_schema_retries", 1))),
            extra_headers=dict(llm.get("extra_headers") or {}),
            trace_dir=trace_dir,
        )


@dataclass(frozen=True)
class _NativeCompletion:
    message: Any | None
    raw_message: dict[str, Any] | None
    usage: Any | None
    finish_reason: str | None
    duration_seconds: float | None
    provider_param_fallback: bool = False
    call_error: str | None = None


class V12ToolTraceWriter:
    """Persist complete redacted native tool-call traces."""

    def __init__(self, trace_dir: Path | None) -> None:
        self.trace_dir = trace_dir

    def write(self, record: dict[str, Any]) -> None:
        if self.trace_dir is None:
            return
        payload = redact_secrets(
            {
                "schema_version": TRACE_SCHEMA_VERSION,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                **record,
            }
        )
        instance_id = _safe_trace_name(str(payload.get("instance_id") or "unknown"))
        line = json.dumps(_jsonable(payload), ensure_ascii=False, sort_keys=True) + "\n"
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        for path in (
            self.trace_dir / "calls.jsonl",
            self.trace_dir / f"{instance_id}.jsonl",
        ):
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line)


class V12NativeToolClient:
    """OpenAI-compatible Chat Completions client that returns V12 ToolCall."""

    def __init__(self, config: V12LLMConfig, *, sdk_client: Any | None = None) -> None:
        self.config = config
        self._sdk_client = sdk_client
        self.trace_writer = V12ToolTraceWriter(config.trace_dir)

    def choose_tool(
        self,
        local_view: AgentLocalView,
        registry_or_specs: Sequence[ToolSpec],
        history: Sequence[AgentStep],
        *,
        instance: RunInstance | None = None,
        observation: Observation | None = None,
        prompt_kind: str = "migrationbench_v12_tool_step",
    ) -> ToolCall:
        """Ask the model for exactly one native tool call and parse it."""

        offered_specs = _non_forbidden_specs(local_view, registry_or_specs)
        tools = registry_to_native_tools(offered_specs, strict=self.config.strict_tools)
        schema_hash = tool_schema_hash(offered_specs, strict=self.config.strict_tools)
        system_prompt = SYSTEM_PROMPT_V12_NATIVE_TOOLS
        parse_errors: list[str] = []
        for retry_index in range(self.config.max_schema_retries + 1):
            user_prompt = _build_user_prompt(
                local_view=local_view,
                tool_specs=offered_specs,
                history=history,
                observation=observation,
                parse_errors=parse_errors,
            )
            completion = self._call_native_tools(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                tools=tools,
            )
            if completion.call_error:
                self._trace(
                    instance=instance,
                    local_view=local_view,
                    history=history,
                    prompt_kind=prompt_kind,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    tools=tools,
                    schema_hash=schema_hash,
                    completion=completion,
                    parsed_tool_call=None,
                    parse_status="api_error",
                    parse_errors=[completion.call_error],
                    retry_index=retry_index,
                )
                raise ToolChoiceError(
                    "V12 native tool API call failed",
                    parse_errors=[completion.call_error],
                    raw_payload=completion.raw_message,
                )
            try:
                parsed = parse_native_tool_call_message(completion.message, offered_specs)
            except NativeToolCallParseError as exc:
                parse_errors = list(exc.errors)
                self._trace(
                    instance=instance,
                    local_view=local_view,
                    history=history,
                    prompt_kind=prompt_kind,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    tools=tools,
                    schema_hash=schema_hash,
                    completion=completion,
                    parsed_tool_call=None,
                    parse_status="parse_failed",
                    parse_errors=parse_errors,
                    retry_index=retry_index,
                )
                continue
            self._trace(
                instance=instance,
                local_view=local_view,
                history=history,
                prompt_kind=prompt_kind,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                tools=tools,
                schema_hash=schema_hash,
                completion=completion,
                parsed_tool_call=parsed,
                parse_status="ok",
                parse_errors=[],
                retry_index=retry_index,
            )
            return parsed
        raise ToolChoiceError(
            "V12 native tool call parsing failed",
            parse_errors=parse_errors or ["unknown_parse_failure"],
        )

    def _call_native_tools(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]],
        include_parallel_tool_calls: bool = True,
    ) -> _NativeCompletion:
        started = time.time()
        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "tools": tools,
            "tool_choice": "required",
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if self.config.provider == "deepseek":
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        if include_parallel_tool_calls:
            kwargs["parallel_tool_calls"] = False
        if self.config.provider == "deepseek" and self._sdk_client is None:
            completion = self._call_deepseek_http(kwargs=kwargs, started=started)
            if (
                include_parallel_tool_calls
                and completion.call_error
                and _looks_like_parallel_tool_param_error_text(completion.call_error)
            ):
                fallback = self._call_native_tools(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    tools=tools,
                    include_parallel_tool_calls=False,
                )
                return _NativeCompletion(
                    message=fallback.message,
                    raw_message=fallback.raw_message,
                    usage=fallback.usage,
                    finish_reason=fallback.finish_reason,
                    duration_seconds=fallback.duration_seconds,
                    provider_param_fallback=True,
                    call_error=fallback.call_error,
                )
            return completion
        client = self._client()
        try:
            completion = client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            if include_parallel_tool_calls and _looks_like_parallel_tool_param_error(exc):
                fallback = self._call_native_tools(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    tools=tools,
                    include_parallel_tool_calls=False,
                )
                return _NativeCompletion(
                    message=fallback.message,
                    raw_message=fallback.raw_message,
                    usage=fallback.usage,
                    finish_reason=fallback.finish_reason,
                    duration_seconds=fallback.duration_seconds,
                    provider_param_fallback=True,
                    call_error=fallback.call_error,
                )
            return _NativeCompletion(
                message=None,
                raw_message=None,
                usage=None,
                finish_reason=None,
                duration_seconds=time.time() - started,
                call_error=f"api_call_failed:{type(exc).__name__}:{exc}",
            )
        choice = completion.choices[0] if getattr(completion, "choices", None) else None
        message = getattr(choice, "message", None) if choice is not None else None
        return _NativeCompletion(
            message=message,
            raw_message=_message_to_dict(message),
            usage=getattr(completion, "usage", None),
            finish_reason=getattr(choice, "finish_reason", None) if choice is not None else None,
            duration_seconds=time.time() - started,
        )

    def _call_deepseek_http(
        self,
        *,
        kwargs: dict[str, Any],
        started: float,
    ) -> _NativeCompletion:
        payload = dict(kwargs)
        extra_body = payload.pop("extra_body", None)
        if isinstance(extra_body, dict):
            payload.update(extra_body)
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.config.timeout_seconds,
            ) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[-2000:]
            return _NativeCompletion(
                message=None,
                raw_message=None,
                usage=None,
                finish_reason=None,
                duration_seconds=time.time() - started,
                call_error=f"api_call_failed:HTTPError:{exc.code}:{body}",
            )
        except Exception as exc:  # noqa: BLE001
            return _NativeCompletion(
                message=None,
                raw_message=None,
                usage=None,
                finish_reason=None,
                duration_seconds=time.time() - started,
                call_error=f"api_call_failed:{type(exc).__name__}:{exc}",
            )
        choices = data.get("choices") or []
        choice = choices[0] if choices else {}
        message = choice.get("message") or {}
        return _NativeCompletion(
            message=message,
            raw_message=_jsonable(message),
            usage=data.get("usage"),
            finish_reason=choice.get("finish_reason"),
            duration_seconds=time.time() - started,
        )

    def _client(self) -> Any:
        if self._sdk_client is not None:
            return self._sdk_client
        try:
            from openai import OpenAI
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"openai SDK not importable: {exc}") from exc
        self._sdk_client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout_seconds,
            default_headers=self.config.extra_headers or None,
        )
        return self._sdk_client

    def _trace(
        self,
        *,
        instance: RunInstance | None,
        local_view: AgentLocalView,
        history: Sequence[AgentStep],
        prompt_kind: str,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]],
        schema_hash: str,
        completion: _NativeCompletion,
        parsed_tool_call: ToolCall | None,
        parse_status: str,
        parse_errors: Sequence[str],
        retry_index: int,
    ) -> None:
        self.trace_writer.write(
            {
                "provider": self.config.provider,
                "model": self.config.model,
                "base_url": self.config.base_url,
                "instance_id": instance.instance_id if instance is not None else "unknown",
                "step_index": len(history),
                "prompt_kind": prompt_kind,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "local_view": local_view.to_dict(),
                "tool_schemas": tools,
                "tool_schema_hash": schema_hash,
                "raw_message": completion.raw_message,
                "raw_tool_calls": (
                    completion.raw_message.get("tool_calls")
                    if isinstance(completion.raw_message, dict)
                    else None
                ),
                "parsed_tool_call": (
                    parsed_tool_call.model_dump(mode="json")
                    if parsed_tool_call is not None
                    else None
                ),
                "parse_status": parse_status,
                "parse_errors": list(parse_errors),
                "retry_index": int(retry_index),
                "provider_param_fallback": bool(completion.provider_param_fallback),
                "duration_seconds": completion.duration_seconds,
                "finish_reason": completion.finish_reason,
                "usage": _jsonable(completion.usage),
            }
        )


def make_migrationbench_v12_tool_chooser(adapter: Any, extras: dict[str, Any]):
    """Return a ToolChooser for MigrationBench V12.2 native tool calls."""

    from adapters_v10.migrationbench.adapter import MigrationBenchAdapterV10

    if not isinstance(adapter, MigrationBenchAdapterV10):
        raise TypeError(
            "V12 LLM tool chooser requires MigrationBenchAdapterV10, got "
            f"{type(adapter).__name__}"
        )
    config = V12LLMConfig.from_extras(extras)
    if config is None:
        raise RuntimeError("V12 LLM tool chooser unavailable; no API key/config")
    client = V12NativeToolClient(config)

    def choose(
        local_view: AgentLocalView,
        tools: tuple[ToolSpec, ...],
        history: tuple[AgentStep, ...],
    ) -> ToolCall:
        return client.choose_tool(
            local_view,
            tools,
            history,
            instance=None,
            observation=None,
        )

    return choose


def _build_user_prompt(
    *,
    local_view: AgentLocalView,
    tool_specs: Sequence[ToolSpec],
    history: Sequence[AgentStep],
    observation: Observation | None,
    parse_errors: Sequence[str],
) -> str:
    payload = {
        "objective": local_view.objective,
        "migration_context": local_view.migration_context,
        "current_best": local_view.current_best,
        "recent_failures": local_view.recent_failures,
        "hot_files": local_view.hot_files,
        "tool_registry": local_view.tool_registry,
        "tool_annotations": local_view.tool_annotations,
        "forbidden_tools": local_view.forbidden_tools,
        "supported_tools": local_view.supported_tools,
        "inhibited_tools": local_view.inhibited_tools,
        "supported_actions": local_view.supported_actions,
        "anti_actions": local_view.anti_actions,
        "relevant_pheromones": local_view.relevant_pheromones,
        "candidate_history": local_view.candidate_history,
        "available_tools": [spec.name for spec in tool_specs],
        "tool_history": [step.to_dict() for step in history[-8:]],
        "observation_summary": observation.summary if observation is not None else None,
    }
    text = (
        "Choose the next V12 tool call from this JSON context. "
        "You may call any non-forbidden tool in available_tools. "
        "Medium tool_annotations are guidance only; they do not hide tools. "
        "If you choose an inhibited tool or ignore a strongly supported tool, "
        "put the justification in the tool rationale. "
        "Do not ask for file contents in prose; call read_file, search_repo, or inspect_pom.\n\n"
        + json.dumps(to_jsonable(payload), ensure_ascii=False, sort_keys=True)
    )
    if parse_errors:
        text += (
            "\n\nPrevious provider output was invalid for these reasons: "
            + json.dumps(list(parse_errors), ensure_ascii=False)
            + "\nReturn exactly one valid native function tool call now."
        )
    return text


def _message_to_dict(message: Any) -> dict[str, Any] | None:
    if message is None:
        return None
    if hasattr(message, "model_dump"):
        try:
            return _jsonable(message.model_dump())
        except Exception:  # noqa: BLE001
            pass
    if isinstance(message, dict):
        return _jsonable(message)
    tool_calls = getattr(message, "tool_calls", None)
    return _jsonable(
        {
            "content": getattr(message, "content", None),
            "tool_calls": list(tool_calls or []),
        }
    )


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "model_dump"):
        try:
            return _jsonable(value.model_dump())
        except Exception:  # noqa: BLE001
            pass
    if hasattr(value, "dict"):
        try:
            return _jsonable(value.dict())
        except Exception:  # noqa: BLE001
            pass
    return str(value)


def _looks_like_parallel_tool_param_error(exc: Exception) -> bool:
    return _looks_like_parallel_tool_param_error_text(str(exc))


def _looks_like_parallel_tool_param_error_text(text: str) -> bool:
    text = text.lower()
    return "parallel_tool_calls" in text or "parallel tool" in text


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


def _non_forbidden_specs(
    local_view: AgentLocalView,
    specs: Sequence[ToolSpec],
) -> tuple[ToolSpec, ...]:
    forbidden = set(local_view.forbidden_tools)
    visible = set(local_view.tool_registry or ())
    if not visible:
        visible = {spec.name for spec in specs}
    return tuple(
        spec
        for spec in specs
        if spec.name in visible and spec.name not in forbidden
    )


def _resolve_model(*, provider: str, llm: dict[str, Any]) -> str:
    configured = str(llm.get("model") or "").strip()
    if configured:
        return configured
    if provider == "deepseek":
        return DEFAULT_DEEPSEEK_MODEL
    raise ValueError(
        "V12 LLM model must be configured explicitly for "
        f"provider={provider!r}; only DeepSeek has a repo default"
    )


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"cannot coerce boolean value: {value!r}")


def _safe_trace_name(value: str) -> str:
    import re

    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned[:180] or "unknown"


__all__ = [
    "DEFAULT_DEEPSEEK_MODEL",
    "SYSTEM_PROMPT_V12_NATIVE_TOOLS",
    "TRACE_SCHEMA_VERSION",
    "V12LLMConfig",
    "V12NativeToolClient",
    "V12ToolTraceWriter",
    "make_migrationbench_v12_tool_chooser",
]
