"""LLM-driven candidate / repair providers for the V10 bench harness.

Replaces the placeholder providers in :mod:`scripts.bench.providers` so that
the A1/A2/A3 ablation actually exercises the strategy ladder:

- Initial provider: prompts a chat LLM to produce a :class:`TypedEditSet` for
  the migration. Called ``max_candidates`` times with progressively higher
  temperature so the strategy receives genuinely distinct candidates.
- Repair provider: rebuilds a prompt that includes the failure signals,
  truncated build/test log, and the previous edit set, then asks the LLM
  for a corrected :class:`TypedEditSet`.

Both providers fall back to the deterministic target-Java Maven edits from
:mod:`scripts.bench.providers` whenever the LLM is unavailable or returns
unparseable JSON. That guarantees we never regress below the current
deterministic baseline because of API hiccups — and the fallback path is
recorded in ``Candidate.metadata`` so post-hoc audits can tell which
candidates were LLM-driven.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from core_v10.contracts import (
    Candidate,
    CandidateKind,
    FeedbackDigest,
    Observation,
    RunInstance,
)

from adapters_v10.migrationbench.context import (
    MigrationContext,
    migration_context_from_observation,
)
from scripts.bench.providers import (
    deterministic_maven_target_java_edits,
)


LOGGER = logging.getLogger("scripts.bench.providers_llm")


_MAX_POM_BYTES = 16_000
_MAX_JAVA_FILES_IN_PROMPT = 6
_MAX_JAVA_BYTES = 4_000
_DEFAULT_TIMEOUT_SECONDS = 120.0
_DEFAULT_MAX_TOKENS = 3_000


# ---------------------------------------------------------------------------
# LLM config + thin client
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LLMConfig:
    """Resolved configuration for the OpenAI-compatible provider."""

    provider: str
    model: str
    base_url: str
    api_key: str
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS
    max_tokens: int = _DEFAULT_MAX_TOKENS
    extra_headers: dict[str, str] = field(default_factory=dict)
    trace_dir: Path | None = None

    @classmethod
    def from_extras(cls, extras: dict[str, Any]) -> "LLMConfig | None":
        """Build a config from harness extras; returns ``None`` if disabled."""

        llm = extras.get("llm") or {}
        if extras.get("use_llm_providers") is False:
            return None
        provider = str(llm.get("provider", "deepseek")).strip().lower()
        env_var_map = {
            "deepseek": "DEEPSEEK_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
        }
        env_var = env_var_map.get(provider, "DEEPSEEK_API_KEY")
        api_key = os.environ.get(env_var, "").strip()
        if not api_key:
            LOGGER.warning(
                "providers_llm: %s not set; falling back to deterministic provider",
                env_var,
            )
            return None
        defaults_url = {
            "deepseek": "https://api.deepseek.com/v1",
            "openrouter": "https://openrouter.ai/api/v1",
        }
        trace_enabled = bool(
            llm.get("trace_enabled", extras.get("llm_trace_enabled", True))
        )
        trace_dir_raw = llm.get("trace_dir") or extras.get("llm_trace_dir")
        if trace_dir_raw is None and extras.get("out_dir"):
            trace_dir_raw = Path(str(extras["out_dir"])) / "llm_traces"
        trace_dir = Path(str(trace_dir_raw)) if trace_enabled and trace_dir_raw else None
        return cls(
            provider=provider,
            model=str(llm.get("model", "deepseek-chat")),
            base_url=str(llm.get("base_url", defaults_url.get(provider, ""))),
            api_key=api_key,
            timeout_seconds=float(llm.get("timeout_seconds", _DEFAULT_TIMEOUT_SECONDS)),
            max_tokens=int(llm.get("max_tokens", _DEFAULT_MAX_TOKENS)),
            extra_headers=dict(llm.get("extra_headers") or {}),
            trace_dir=trace_dir,
        )


class LLMJsonResponse(dict):
    """Parsed LLM JSON plus raw call metadata for audit traces."""

    def __init__(
        self,
        parsed: dict[str, Any] | None,
        *,
        raw_response: str | None = None,
        error: str | None = None,
        duration_seconds: float | None = None,
        finish_reason: str | None = None,
        usage: Any | None = None,
    ) -> None:
        super().__init__(parsed or {})
        self.raw_response = raw_response
        self.error = error
        self.duration_seconds = duration_seconds
        self.finish_reason = finish_reason
        self.usage = usage


def _call_llm_json(
    config: LLMConfig,
    *,
    system: str,
    user: str,
    temperature: float,
) -> dict[str, Any] | None:
    """Call chat completion and return parsed JSON with raw trace metadata."""

    try:
        from openai import OpenAI  # local import keeps unit tests light
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("openai SDK not importable: %s", exc)
        return LLMJsonResponse(None, error=f"openai_sdk_not_importable: {exc}")

    client = OpenAI(
        api_key=config.api_key,
        base_url=config.base_url,
        timeout=config.timeout_seconds,
        default_headers=config.extra_headers or None,
    )
    started = time.time()
    try:
        completion = client.chat.completions.create(
            model=config.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=float(temperature),
            max_tokens=config.max_tokens,
            response_format={"type": "json_object"},
        )
    except Exception as exc:  # noqa: BLE001
        elapsed = time.time() - started
        LOGGER.warning(
            "providers_llm: API call failed in %.1fs (temperature=%.2f): %s",
            elapsed,
            temperature,
            exc,
        )
        return LLMJsonResponse(
            None,
            error=f"api_call_failed: {exc}",
            duration_seconds=elapsed,
        )

    if not completion.choices:
        LOGGER.warning("providers_llm: empty choices")
        return LLMJsonResponse(
            None,
            error="empty_choices",
            duration_seconds=time.time() - started,
            usage=getattr(completion, "usage", None),
        )

    choice = completion.choices[0]
    raw = choice.message.content or ""
    parsed = _safe_json_parse(raw)
    return LLMJsonResponse(
        parsed,
        raw_response=raw,
        error=None if parsed is not None else "json_parse_failed",
        duration_seconds=time.time() - started,
        finish_reason=getattr(choice, "finish_reason", None),
        usage=getattr(completion, "usage", None),
    )


def _jsonable(value: Any) -> Any:
    """Convert SDK/Pydantic objects to JSON-safe values without secrets."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
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


def _safe_trace_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned[:180] or "unknown"


def _response_trace_metadata(response: dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(response, LLMJsonResponse):
        return {
            "raw_response": response.raw_response,
            "call_error": response.error,
            "duration_seconds": response.duration_seconds,
            "finish_reason": response.finish_reason,
            "usage": _jsonable(response.usage),
        }
    return {
        "raw_response": None,
        "call_error": "no_response" if response is None else None,
        "duration_seconds": None,
        "finish_reason": None,
        "usage": None,
    }


def _write_llm_trace(config: LLMConfig, record: dict[str, Any]) -> None:
    """Persist one audit record per LLM call under ``<out_dir>/llm_traces``."""

    if config.trace_dir is None:
        return
    trace_dir = config.trace_dir
    instance_id = str(record.get("instance_id") or "unknown")
    payload = {
        "schema_version": "v11.llm_trace.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        **record,
    }
    try:
        trace_dir.mkdir(parents=True, exist_ok=True)
        paths = [
            trace_dir / "calls.jsonl",
            trace_dir / f"{_safe_trace_name(instance_id)}.jsonl",
        ]
        line = json.dumps(_jsonable(payload), ensure_ascii=False, sort_keys=True) + "\n"
        for path in paths:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("providers_llm: could not write LLM trace: %s", exc)


def _trace_llm_call(
    config: LLMConfig,
    *,
    call_kind: str,
    instance: RunInstance,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    slot_index: int,
    response: dict[str, Any] | None,
    normalized_edits: list[dict[str, Any]],
    candidate_id: str,
    candidate_emitted: bool,
    dropped_reason: str | None,
    files: dict[str, str],
    parent_candidate_id: str | None = None,
    feedback_failure_type: str | None = None,
) -> None:
    parsed_response = dict(response) if isinstance(response, dict) else None
    meta = _response_trace_metadata(response)
    _write_llm_trace(
        config,
        {
            "call_kind": call_kind,
            "instance_id": instance.instance_id,
            "provider": config.provider,
            "model": config.model,
            "base_url": config.base_url,
            "temperature": temperature,
            "max_tokens": config.max_tokens,
            "timeout_seconds": config.timeout_seconds,
            "slot_index": slot_index,
            "candidate_id": candidate_id,
            "parent_candidate_id": parent_candidate_id,
            "feedback_failure_type": feedback_failure_type,
            "candidate_emitted": candidate_emitted,
            "dropped_reason": dropped_reason,
            "parse_ok": parsed_response is not None and meta.get("call_error") is None,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "system_prompt_chars": len(system_prompt),
            "user_prompt_chars": len(user_prompt),
            "files_shown": sorted(files),
            "files_shown_chars": {
                path: len(text) for path, text in sorted(files.items())
            },
            "parsed_response": parsed_response,
            "raw_response": meta["raw_response"],
            "raw_response_chars": len(meta["raw_response"] or ""),
            "normalized_edits": normalized_edits,
            "normalized_edit_count": len(normalized_edits),
            "call_error": meta["call_error"],
            "duration_seconds": meta["duration_seconds"],
            "finish_reason": meta["finish_reason"],
            "usage": meta["usage"],
        },
    )



_FENCE_RE = re.compile(r"```(?:json)?\s*(.+?)```", re.DOTALL)


def _safe_json_parse(content: str) -> dict[str, Any] | None:
    """Tolerate fenced or trailing-garbage JSON outputs."""

    if not content:
        return None
    text = content.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = _FENCE_RE.search(text)
    if m:
        candidate = m.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    # Last resort: locate first { and last } and attempt slice.
    start = text.find("{")
    end = text.rfind("}")
    if 0 <= start < end:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


_TEST_PRESERVATION_RULE = (
    "Hard rule: do NOT delete, rename, comment out, or add @Disabled / @Ignore "
    "to any existing test class or test method. The official MigrationBench "
    "evaluator counts test cases and rejects the patch when the count drops or "
    "when `mvn test -f .` does not emit the standard Maven/Surefire test "
    "summary it can parse (often reported as Success=False with #tests=-2). "
    "Touch test files only to fix compile errors that come directly from the "
    "migration; prefer Maven/Surefire/JUnit configuration fixes when the "
    "official failure is only about test counting or test-summary parsing."
)


_VERBATIM_RULE = (
    "Hard rule for `replace_text` edits: the `old` field MUST be a verbatim "
    "substring of the file shown to you under '--- BEGIN FILE: <path> ---'. "
    "Do NOT paraphrase, re-indent, collapse whitespace, or invent fragments. "
    "If a snippet you want to change is not present verbatim in the files "
    "below, OMIT that edit rather than guessing — an edit whose `old` cannot "
    "be located will reject the entire candidate."
)


_SYSTEM_PROMPT_INITIAL = (
    "You are a senior Java/Maven build engineer. Given a project that builds "
    "with Java 8, propose the smallest set of edits that will let the project "
    "build, test, and produce class files at the requested target Java "
    "version. Your answer must be a single JSON object with a 'edits' array. "
    "Each edit is one of:\n"
    "- {'type':'replace_text','path':'pom.xml','old':'…','new':'…','expected_replacements':1}\n"
    "- {'type':'write_file','path':'…','content':'…'}\n"
    "Paths must be repository-relative POSIX. Edits are applied in order. "
    "Do NOT include explanatory prose outside JSON. Prefer the smallest "
    "possible diff: usually only `<maven.compiler.*>`, `<source>`, "
    "`<target>`, `<release>`, or `<java.version>` need to change. The "
    "Project context block below is informational — it does NOT mean you "
    "must migrate javax→jakarta or bump Spring Boot. Touch only what the "
    "build needs to clear the requested target Java.\n"
    + _VERBATIM_RULE + "\n"
    + _TEST_PRESERVATION_RULE
)


_SYSTEM_PROMPT_REPAIR = (
    "You are repairing a previous target-Java migration patch that failed in a "
    "Maven build. You will receive the previous edits, the validation "
    "signals, the failure classification, and a tail of the build/test log. "
    "Produce a corrected JSON edit set in the same schema. Address the "
    "specific failure that the signals point to (compile error → fix POM "
    "release/source/target or add missing dependency; test error → revisit "
    "the offending file; class_version_ok=false → align maven.compiler.* "
    "and <release> with the target; dependency_resolution_error → bump "
    "the offending plugin/dependency to a target-compatible version, "
    "but ONLY if the exact text you want to replace is present verbatim "
    "in the files shown; official_eval_failed/#tests=-2 → keep every test "
    "intact and adjust Maven/Surefire/JUnit configuration so `mvn test -f .` "
    "runs the existing tests and prints the standard `[INFO] Results` summary). "
    "Output JSON only.\n"
    + _VERBATIM_RULE + "\n"
    + _TEST_PRESERVATION_RULE
)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head = limit // 2
    tail = limit - head - 32
    return f"{text[:head]}\n...[truncated {len(text) - limit} chars]...\n{text[-tail:]}"


def _read_target_files(adapter, observation: Observation) -> dict[str, str]:
    """Collect a small set of files to ground the prompt.

    When ``observation.data["__live_files__"]`` is populated (typically by the
    strategy runner before invoking the repair_provider), those files are
    used verbatim. This is critical for repair: the LLM must see the *current*
    state of the parent branch (e.g. after the initial edit was applied),
    not the pristine base workspace. When the override is missing, we fall
    back to reading the adapter's base workspace — used for initial provider
    calls.
    """

    live_files = observation.data.get("__live_files__")
    if isinstance(live_files, dict) and live_files:
        # Already truncated by the runner; trust the payload.
        return {str(k): str(v) for k, v in live_files.items()}

    workspace = adapter._require_base_workspace()  # type: ignore[attr-defined]
    files: dict[str, str] = {}
    for rel in observation.data.get("pom_files", []) or []:
        try:
            files[rel] = _truncate(
                workspace.read_file(rel, max_bytes=_MAX_POM_BYTES),
                _MAX_POM_BYTES,
            )
        except Exception:  # noqa: BLE001
            continue
    java_sample = list(observation.data.get("java_files_sample") or [])[
        :_MAX_JAVA_FILES_IN_PROMPT
    ]
    for rel in java_sample:
        try:
            files[rel] = _truncate(
                workspace.read_file(rel, max_bytes=_MAX_JAVA_BYTES),
                _MAX_JAVA_BYTES,
            )
        except Exception:  # noqa: BLE001
            continue
    return files


def _format_files_block(files: dict[str, str]) -> str:
    parts: list[str] = []
    for path, body in files.items():
        parts.append(f"--- BEGIN FILE: {path} ---\n{body}\n--- END FILE: {path} ---")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Project context enrichment (piste 1, ADR 2026-05-04)
# ---------------------------------------------------------------------------


_DEPENDENCY_RE = re.compile(
    r"<dependency>(?P<body>.*?)</dependency>", re.DOTALL | re.IGNORECASE
)
_DEP_FIELD_RES = {
    "groupId": re.compile(r"<groupId>\s*(?P<v>[^<]+?)\s*</groupId>", re.IGNORECASE),
    "artifactId": re.compile(
        r"<artifactId>\s*(?P<v>[^<]+?)\s*</artifactId>", re.IGNORECASE
    ),
    "version": re.compile(r"<version>\s*(?P<v>[^<]+?)\s*</version>", re.IGNORECASE),
}
_PARENT_RE = re.compile(r"<parent>(?P<body>.*?)</parent>", re.DOTALL | re.IGNORECASE)
_JAVAX_IMPORT_RE = re.compile(r"^\s*import\s+(javax\.[A-Za-z0-9_.]+)\s*;", re.MULTILINE)


def _extract_dependencies(pom_text: str) -> list[dict[str, str]]:
    """Best-effort regex parse of top-level <dependency> blocks."""

    deps: list[dict[str, str]] = []
    for match in _DEPENDENCY_RE.finditer(pom_text or ""):
        body = match.group("body")
        entry: dict[str, str] = {}
        for key, regex in _DEP_FIELD_RES.items():
            m = regex.search(body)
            if m:
                entry[key] = m.group("v")
        if entry.get("artifactId"):
            deps.append(entry)
    return deps


def _extract_spring_boot_parent(pom_text: str) -> str | None:
    """Return the Spring Boot parent version if the POM declares it."""

    parent_match = _PARENT_RE.search(pom_text or "")
    if not parent_match:
        return None
    body = parent_match.group("body")
    artifact = _DEP_FIELD_RES["artifactId"].search(body)
    if not artifact:
        return None
    if "spring-boot-starter-parent" not in artifact.group("v"):
        return None
    version = _DEP_FIELD_RES["version"].search(body)
    return version.group("v") if version else "unspecified"


def _collect_dependency_context(
    files: dict[str, str],
    *,
    max_deps: int = 30,
    max_javax: int = 30,
) -> dict[str, Any]:
    """Build a ``project_context`` dict for the prompt.

    Strictly passive: parses the in-memory POM/Java strings already loaded
    by :func:`_read_target_files`; never executes Maven and never touches
    the disk. This keeps the enrichment cheap and reproducible.
    """

    deps: list[dict[str, str]] = []
    spring_boot_versions: list[str] = []
    for path, text in files.items():
        if not path.endswith("pom.xml"):
            continue
        deps.extend(_extract_dependencies(text))
        sb = _extract_spring_boot_parent(text)
        if sb:
            spring_boot_versions.append(sb)

    seen: set[tuple[str, str]] = set()
    unique_deps: list[dict[str, str]] = []
    for d in deps:
        key = (d.get("groupId", ""), d.get("artifactId", ""))
        if key in seen:
            continue
        seen.add(key)
        unique_deps.append(d)
        if len(unique_deps) >= max_deps:
            break

    javax_imports: list[str] = []
    seen_imports: set[str] = set()
    for path, text in files.items():
        if not path.endswith(".java"):
            continue
        for match in _JAVAX_IMPORT_RE.finditer(text or ""):
            symbol = match.group(1)
            if symbol in seen_imports:
                continue
            seen_imports.add(symbol)
            javax_imports.append(symbol)
            if len(javax_imports) >= max_javax:
                break
        if len(javax_imports) >= max_javax:
            break

    return {
        "spring_boot_parent_versions": sorted(set(spring_boot_versions)),
        "top_dependencies": unique_deps,
        "javax_imports": javax_imports,
    }


def _format_project_context(
    context: dict[str, Any],
    migration_context: MigrationContext | None = None,
) -> str:
    """Render the project context block for the user prompt."""

    parts = ["Project context (parsed passively from poms/java files):"]
    sb = context.get("spring_boot_parent_versions") or []
    if sb:
        parts.append(f"  spring_boot_parent_versions: {sb}")
    deps = context.get("top_dependencies") or []
    if deps:
        rendered = []
        for d in deps:
            rendered.append(
                f"{d.get('groupId','?')}:{d.get('artifactId','?')}"
                f":{d.get('version','?')}"
            )
        parts.append(
            f"  top_dependencies ({len(rendered)}): {', '.join(rendered)}"
        )
    javax = context.get("javax_imports") or []
    if javax:
        parts.append(
            f"  javax_imports_used ({len(javax)}): {', '.join(javax)}"
        )
        target_text = (
            f"target Java {migration_context.target_java}"
            if migration_context is not None
            else "the requested target Java"
        )
        parts.append(
            f"  hint: with {target_text} and Spring Boot 3.x these javax.* "
            "must migrate to jakarta.* (servlet, persistence, validation, ws.rs)."
        )
    if len(parts) == 1:
        return ""
    return "\n".join(parts)


def _build_initial_user_prompt(
    instance: RunInstance,
    observation: Observation,
    files: dict[str, str],
    *,
    variation_hint: str,
) -> str:
    migration_context = migration_context_from_observation(observation, instance)
    project_context = _format_project_context(
        _collect_dependency_context(files),
        migration_context,
    )
    context_block = (project_context + "\n\n") if project_context else ""
    return (
        f"Repository: {observation.data.get('repo_url')}\n"
        f"Base commit: {observation.data.get('base_commit')}\n"
        f"Migration mode: {migration_context.migration_mode}\n"
        f"Target Java: {migration_context.target_java} "
        f"(class file major version {migration_context.target_class_major})\n"
        f"Variation hint: {variation_hint}\n\n"
        f"{context_block}"
        "Files (truncated for context):\n\n"
        f"{_format_files_block(files)}\n\n"
        "Output a single JSON object: "
        '{"edits":[…],"rationale":"…","expected_build_command":"mvn clean verify"}'
    )


def _build_repair_user_prompt(
    instance: RunInstance,
    observation: Observation,
    files: dict[str, str],
    feedback: FeedbackDigest,
    original: Candidate,
) -> str:
    edit_set = original.payload.get("edit_set") or {}
    prior_edits_json = json.dumps(edit_set, indent=2, sort_keys=True)
    if len(prior_edits_json) > 6000:
        prior_edits_json = prior_edits_json[:6000] + "\n…[prior_edits truncated]"
    signals = (feedback.metadata or {}).get("signals") or {}
    log_tail = "\n".join(feedback.evidence)[-3500:] if feedback.evidence else ""
    migration_context = migration_context_from_observation(observation, instance)
    project_context = _format_project_context(
        _collect_dependency_context(files),
        migration_context,
    )
    context_block = (project_context + "\n\n") if project_context else ""
    signal_digest = _format_stigmergic_digest(
        observation.data.get("stigmergic_digest")
    )
    signal_block = (
        f"Stigmergic policy digest from prior candidates:\n{signal_digest}\n\n"
        if signal_digest
        else ""
    )
    return (
        f"Repository: {observation.data.get('repo_url')}\n"
        f"Target Java: {migration_context.target_java} "
        f"(class major {migration_context.target_class_major})\n"
        f"Failure type: {feedback.failure_type}\n"
        f"Severity: {feedback.severity}\n"
        f"Signals: {json.dumps(signals)}\n"
        f"Recommended next actions: "
        f"{json.dumps(feedback.recommended_next_actions)}\n"
        f"Anti-actions: {json.dumps(feedback.anti_actions)}\n\n"
        f"{signal_block}"
        f"{context_block}"
        f"Previous edit set:\n{prior_edits_json}\n\n"
        f"Build/test log tail (last 3.5KB):\n{log_tail}\n\n"
        "Files (current contents, truncated):\n\n"
        f"{_format_files_block(files)}\n\n"
        "Return one JSON object: "
        '{"edits":[…],"rationale":"…","expected_build_command":"mvn clean verify"}'
    )


def _format_stigmergic_digest(raw: Any) -> str:
    if not isinstance(raw, dict):
        return ""
    compact: dict[str, list[dict[str, Any]]] = {}
    for key in ("top_inhibitions", "top_supports", "top_novelties"):
        rows = raw.get(key)
        if not isinstance(rows, list):
            continue
        cleaned = []
        for row in rows[:3]:
            if not isinstance(row, dict):
                continue
            cleaned.append(
                {
                    "kind": row.get("kind"),
                    "target": row.get("target"),
                    "intensity": row.get("intensity"),
                    "evidence": list(row.get("evidence") or [])[:2],
                }
            )
        if cleaned:
            compact[key] = cleaned
    if not compact:
        return ""
    text = json.dumps(compact, sort_keys=True)
    return _truncate(text, 1200)


# ---------------------------------------------------------------------------
# Edit-set normalization & validation
# ---------------------------------------------------------------------------


def _normalize_edits(
    raw: Any,
    files: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Coerce LLM output into the TypedEdit dict schema.

    When ``files`` is provided, every ``replace_text`` edit is checked
    against the visible file content: if ``old`` is not a verbatim
    substring of ``files[path]``, the edit is dropped silently. This
    deterministic guard prevents hallucinated edits from reaching the
    apply layer and triggering ``replacement_count_too_low`` rejections.
    """

    if not isinstance(raw, dict):
        return []
    edits = raw.get("edits")
    if not isinstance(edits, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for item in edits:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type", "")).strip()
        path = str(item.get("path", "")).strip().replace("\\", "/")
        if not path or path.startswith("/") or ".." in path.split("/"):
            continue
        if kind == "replace_text":
            old = item.get("old")
            new = item.get("new")
            if not isinstance(old, str) or not old:
                continue
            if not isinstance(new, str):
                continue
            # Verbatim guard: drop edits whose `old` is not present in the
            # file shown to the LLM. We intentionally do this only when we
            # have visibility on the file; otherwise we trust the apply
            # layer to reject the edit. This guard is uniform across A1/A2/A3
            # (pre-registered in ADR 2026-05-04 addendum).
            if files is not None and path in files:
                if old not in files[path]:
                    LOGGER.info(
                        "providers_llm: dropping hallucinated edit (old not in %s)",
                        path,
                    )
                    continue
            # We deliberately clamp ``expected_replacements`` to 1 and force
            # ``allow_multiple=True``. Trusting the LLM's count regularly
            # produces ``replacement_count_too_low`` failures because the
            # model overestimates how many times a snippet appears. The
            # apply layer will still run the edit; it just becomes
            # tolerant to multiple matches.
            cleaned.append(
                {
                    "type": "replace_text",
                    "path": path,
                    "old": old,
                    "new": new,
                    "expected_replacements": 1,
                    "allow_multiple": True,
                }
            )
        elif kind == "write_file":
            content = item.get("content")
            if not isinstance(content, str):
                continue
            cleaned.append(
                {
                    "type": "write_file",
                    "path": path,
                    "content": content,
                }
            )
    return cleaned


# ---------------------------------------------------------------------------
# Initial provider
# ---------------------------------------------------------------------------


_TEMPERATURES = (0.0, 0.4, 0.8, 1.0)


def make_migrationbench_llm_initial_provider(
    adapter,
    extras: dict[str, Any],
):
    """Return a candidate provider that asks an LLM for ``N`` distinct edit sets.

    ``N`` is read from ``extras['llm_initial_candidates']``; when missing,
    the strategy's ``max_candidates`` is used at call time via the adapter
    (we can not see it from the provider, so we always emit the maximum
    we ever expect — the runner truncates to ``max_candidates``).
    """

    from adapters_v10.migrationbench.adapter import MigrationBenchAdapterV10

    if not isinstance(adapter, MigrationBenchAdapterV10):
        raise TypeError(
            "LLM initial provider requires MigrationBenchAdapterV10, got "
            f"{type(adapter).__name__}"
        )
    config = LLMConfig.from_extras(extras)
    if config is None:
        # Caller chose to disable the LLM or no API key in env: fall back.
        from scripts.bench.providers import (
            make_migrationbench_deterministic_provider,
        )
        return make_migrationbench_deterministic_provider(adapter, extras)

    n_target = max(1, int(extras.get("llm_initial_candidates", len(_TEMPERATURES))))
    n_target = min(n_target, len(_TEMPERATURES))

    def _deterministic_fallback_edits(
        observation: Observation,
        instance: RunInstance,
    ) -> list[dict[str, Any]]:
        context = migration_context_from_observation(observation, instance)
        workspace = adapter._require_base_workspace()  # type: ignore[attr-defined]
        pom_paths = [t for t in workspace.list_targets() if t.endswith("pom.xml")]
        pom_texts: dict[str, str] = {}
        for rel in pom_paths:
            try:
                pom_texts[rel] = workspace.read_file(rel, max_bytes=2_000_000)
            except Exception:  # noqa: BLE001
                continue
        return deterministic_maven_target_java_edits(pom_paths, pom_texts, context)

    def provide(observation: Observation, instance: RunInstance) -> Sequence[Candidate]:
        files = _read_target_files(adapter, observation)
        candidates: list[Candidate] = []
        signatures: set[str] = set()
        # Build the requested number of LLM candidates with progressively
        # higher temperature so the strategy receives genuinely distinct
        # inputs. We do NOT prepend a deterministic baseline anymore: when
        # the strategy keeps only ``max_candidates``, the baseline would
        # crowd out every LLM proposal. The deterministic edits remain
        # available as a fallback below if the API stays silent.
        for k in range(n_target):
            temperature = _TEMPERATURES[k]
            candidate_id = f"{instance.instance_id}-c{k+1}-llm{int(temperature*10)}"
            variation = (
                "Conservative POM-only edits."
                if k == 0
                else (
                    f"Diverse edit attempt {k}: optionally raise plugin versions "
                    "or fix lombok/javax→jakarta if visible."
                )
            )
            user = _build_initial_user_prompt(
                instance, observation, files, variation_hint=variation
            )
            response = _call_llm_json(
                config,
                system=_SYSTEM_PROMPT_INITIAL,
                user=user,
                temperature=temperature,
            )
            edits = _normalize_edits(response, files=files)
            if not edits:
                _trace_llm_call(
                    config,
                    call_kind="initial",
                    instance=instance,
                    system_prompt=_SYSTEM_PROMPT_INITIAL,
                    user_prompt=user,
                    temperature=temperature,
                    slot_index=k,
                    response=response,
                    normalized_edits=edits,
                    candidate_id=candidate_id,
                    candidate_emitted=False,
                    dropped_reason="empty_or_invalid_edits",
                    files=files,
                )
                LOGGER.info(
                    "providers_llm: empty/invalid edits for %s slot=%d",
                    instance.instance_id,
                    k,
                )
                continue
            sig = _signature(edits)
            if sig in signatures:
                _trace_llm_call(
                    config,
                    call_kind="initial",
                    instance=instance,
                    system_prompt=_SYSTEM_PROMPT_INITIAL,
                    user_prompt=user,
                    temperature=temperature,
                    slot_index=k,
                    response=response,
                    normalized_edits=edits,
                    candidate_id=candidate_id,
                    candidate_emitted=False,
                    dropped_reason="duplicate_signature",
                    files=files,
                )
                continue
            signatures.add(sig)
            candidates.append(
                Candidate(
                    candidate_id=candidate_id,
                    kind=CandidateKind.PATCH,
                    payload={
                        "branch_id": f"c{k+1}_llm",
                        "edit_set": {
                            "edits": edits,
                            "rationale": (response or {}).get(
                                "rationale", f"LLM proposal at temperature {temperature}"
                            ),
                            "expected_build_command": (response or {}).get(
                                "expected_build_command", "mvn clean verify"
                            ),
                        },
                    },
                    origin=f"llm_{config.model}_t{int(temperature*10)}",
                    metadata={
                        "source": "llm",
                        "temperature": temperature,
                        "model": config.model,
                        "provider": config.provider,
                    },
                )
            )
            _trace_llm_call(
                config,
                call_kind="initial",
                instance=instance,
                system_prompt=_SYSTEM_PROMPT_INITIAL,
                user_prompt=user,
                temperature=temperature,
                slot_index=k,
                response=response,
                normalized_edits=edits,
                candidate_id=candidate_id,
                candidate_emitted=True,
                dropped_reason=None,
                files=files,
            )
        if not candidates:
            # API silent or all responses unparseable: fall back to a single
            # deterministic target-Java candidate so the run still produces an
            # auditable artifact. The metadata flags the fallback so post-hoc
            # analysis can separate LLM vs deterministic outcomes.
            context = migration_context_from_observation(observation, instance)
            baseline_edits = _deterministic_fallback_edits(observation, instance)
            if baseline_edits:
                candidates.append(
                    Candidate(
                        candidate_id=f"{instance.instance_id}-c0-baseline",
                        kind=CandidateKind.PATCH,
                        payload={
                            "branch_id": "c0_baseline",
                            "edit_set": {
                                "edits": baseline_edits,
                                "rationale": (
                                    "Deterministic target-Java Maven fallback "
                                    "(LLM produced no usable edits)."
                                ),
                                "expected_build_command": context.expected_build_command,
                            },
                        },
                        origin="builtin_deterministic_maven_target_java",
                        metadata={
                            "source": "deterministic_fallback",
                            "migration_context": context.to_dict(),
                        },
                    )
                )
            else:
                LOGGER.warning(
                    "providers_llm: no candidates and no deterministic edits for %s",
                    instance.instance_id,
                )
        return candidates

    return provide


# ---------------------------------------------------------------------------
# Repair provider
# ---------------------------------------------------------------------------


def make_migrationbench_llm_repair_provider(
    adapter,
    extras: dict[str, Any],
):
    """Return a repair provider that consumes feedback and asks the LLM."""

    from adapters_v10.migrationbench.adapter import MigrationBenchAdapterV10

    if not isinstance(adapter, MigrationBenchAdapterV10):
        raise TypeError(
            "LLM repair provider requires MigrationBenchAdapterV10, got "
            f"{type(adapter).__name__}"
        )
    config = LLMConfig.from_extras(extras)
    if config is None:
        from scripts.bench.providers import make_migrationbench_noop_repair_provider
        return make_migrationbench_noop_repair_provider(adapter, extras)

    n_target = max(1, int(extras.get("llm_repair_candidates", 1)))
    n_target = min(n_target, len(_TEMPERATURES))

    def provide(
        feedback: FeedbackDigest,
        original: Candidate,
        observation: Observation,
        instance: RunInstance,
    ) -> Sequence[Candidate]:
        files = _read_target_files(adapter, observation)
        repairs: list[Candidate] = []
        signatures: set[str] = set()
        for k in range(n_target):
            temperature = _TEMPERATURES[k]
            candidate_id = f"{original.candidate_id}-r{k}-llm{int(temperature*10)}"
            user = _build_repair_user_prompt(
                instance, observation, files, feedback, original
            )
            response = _call_llm_json(
                config,
                system=_SYSTEM_PROMPT_REPAIR,
                user=user,
                temperature=temperature,
            )
            edits = _normalize_edits(response, files=files)
            if not edits:
                _trace_llm_call(
                    config,
                    call_kind="repair",
                    instance=instance,
                    system_prompt=_SYSTEM_PROMPT_REPAIR,
                    user_prompt=user,
                    temperature=temperature,
                    slot_index=k,
                    response=response,
                    normalized_edits=edits,
                    candidate_id=candidate_id,
                    candidate_emitted=False,
                    dropped_reason="empty_or_invalid_edits",
                    files=files,
                    parent_candidate_id=original.candidate_id,
                    feedback_failure_type=feedback.failure_type,
                )
                continue
            sig = _signature(edits)
            if sig in signatures:
                _trace_llm_call(
                    config,
                    call_kind="repair",
                    instance=instance,
                    system_prompt=_SYSTEM_PROMPT_REPAIR,
                    user_prompt=user,
                    temperature=temperature,
                    slot_index=k,
                    response=response,
                    normalized_edits=edits,
                    candidate_id=candidate_id,
                    candidate_emitted=False,
                    dropped_reason="duplicate_signature",
                    files=files,
                    parent_candidate_id=original.candidate_id,
                    feedback_failure_type=feedback.failure_type,
                )
                continue
            signatures.add(sig)
            repairs.append(
                Candidate(
                    candidate_id=candidate_id,
                    kind=CandidateKind.PATCH,
                    payload={
                        "branch_id": f"{original.payload.get('branch_id','c')}_r{k}",
                        "edit_set": {
                            "edits": edits,
                            "rationale": (response or {}).get(
                                "rationale",
                                f"LLM repair at temperature {temperature}",
                            ),
                            "expected_build_command": (response or {}).get(
                                "expected_build_command", "mvn clean verify"
                            ),
                        },
                    },
                    origin=f"llm_repair_{config.model}_t{int(temperature*10)}",
                    parent_id=original.candidate_id,
                    metadata={
                        "source": "llm_repair",
                        "temperature": temperature,
                        "model": config.model,
                        "provider": config.provider,
                        "feedback_failure_type": feedback.failure_type,
                    },
                )
            )
            _trace_llm_call(
                config,
                call_kind="repair",
                instance=instance,
                system_prompt=_SYSTEM_PROMPT_REPAIR,
                user_prompt=user,
                temperature=temperature,
                slot_index=k,
                response=response,
                normalized_edits=edits,
                candidate_id=candidate_id,
                candidate_emitted=True,
                dropped_reason=None,
                files=files,
                parent_candidate_id=original.candidate_id,
                feedback_failure_type=feedback.failure_type,
            )
        return repairs

    return provide


def _signature(edits: list[dict[str, Any]]) -> str:
    """Stable hash of an edits list (order-sensitive, payload-sensitive)."""

    import hashlib

    blob = json.dumps(edits, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


__all__ = [
    "LLMConfig",
    "LLMJsonResponse",
    "make_migrationbench_llm_initial_provider",
    "make_migrationbench_llm_repair_provider",
]
