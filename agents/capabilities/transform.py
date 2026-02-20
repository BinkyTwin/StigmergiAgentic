"""Transformation capability for Python and non-Python task files."""

from __future__ import annotations

import ast
import difflib
from pathlib import Path
from typing import Any

TRANSFORMER_ROLE_PROMPT = (
    "Your role: TRANSFORMER (builder/worker). "
    "You convert Python 2 files to Python 3, guided by task pheromones from a Scout agent. "
    "Traces you read: pattern lists (what to fix), quality traces from prior "
    "attempts (what went wrong), and validated examples (successful migrations). "
    "Traces you deposit: the transformed Python 3 file. "
    "A downstream Tester agent will run tests against your output, "
    "so ensure syntactic validity and semantic preservation. "
    "Return only the complete converted Python 3 file, no explanations."
)


def select_transform_candidates(
    store: Any,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Select ranked candidate files for the transformer."""

    candidate_status_entries = store.query("status", status__in={"pending", "retry"})
    threshold_config = config.get("thresholds", {})
    pheromone_config = config.get("pheromones", {})

    intensity_min = float(threshold_config.get("transformer_intensity_min", 0.2))
    inhibition_threshold = float(pheromone_config.get("inhibition_threshold", 0.1))

    preferred_candidates: list[dict[str, Any]] = []
    fallback_candidates: list[dict[str, Any]] = []
    inhibited_candidates: list[dict[str, Any]] = []

    for file_key, status_entry in candidate_status_entries.items():
        task_entry = store.read_one("tasks", file_key)
        if not task_entry:
            continue

        intensity = float(task_entry.get("intensity", 0.0))
        inhibition = float(status_entry.get("inhibition", 0.0))
        candidate = {
            "file_key": file_key,
            "intensity": intensity,
            "inhibition": inhibition,
            "status_entry": status_entry,
            "task_entry": task_entry,
        }
        if inhibition >= inhibition_threshold:
            inhibited_candidates.append(candidate)
            continue

        fallback_candidates.append(candidate)
        if intensity > intensity_min:
            preferred_candidates.append(candidate)

    if preferred_candidates:
        return sorted(
            preferred_candidates,
            key=lambda item: (-item["intensity"], item["file_key"]),
        )
    if fallback_candidates:
        return sorted(
            fallback_candidates, key=lambda item: (-item["intensity"], item["file_key"])
        )
    return sorted(
        inhibited_candidates,
        key=lambda item: (item["inhibition"], -item["intensity"], item["file_key"]),
    )


def transform_file(
    store: Any,
    repo_path: str | Path,
    llm_client: Any | None,
    file_key: str,
    config: dict[str, Any],
    agent_name: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Transform one file and return transformer execution result.

    Required parameters follow Sprint 6 API freeze.
    Optional keyword arguments allow wrappers to provide richer prompts/callbacks.
    """

    status_entry = kwargs.get("status_entry") or (
        store.read_one("status", file_key) or {}
    )
    task_entry = kwargs.get("task_entry") or (store.read_one("tasks", file_key) or {})
    file_kind = str(
        kwargs.get("file_kind")
        or task_entry.get("file_kind")
        or _infer_file_kind(file_key)
    )

    repo_root = Path(repo_path)
    file_path = repo_root / file_key
    source_content = str(
        kwargs.get("source_content")
        if kwargs.get("source_content") is not None
        else file_path.read_text(encoding="utf-8", errors="ignore")
    )
    patterns = list(kwargs.get("patterns") or task_entry.get("patterns_found", []))
    prompt = str(
        kwargs.get("prompt")
        or _build_default_prompt(
            file_key=file_key,
            source_content=source_content,
            patterns=patterns,
            file_kind=file_kind,
        )
    )
    system_prompt = str(
        kwargs.get("system_prompt")
        or kwargs.get("role_prompt")
        or TRANSFORMER_ROLE_PROMPT
    )

    store.update(
        "status",
        file_key=file_key,
        agent_id=agent_name,
        status="in_progress",
        previous_status=status_entry.get("status", "pending"),
        retry_count=int(status_entry.get("retry_count", 0)),
        inhibition=float(status_entry.get("inhibition", 0.0)),
        current_tick=int(config.get("runtime", {}).get("tick", 0)),
    )

    try:
        if llm_client is None:
            raise RuntimeError("Transformer requires an initialized LLM client")

        llm_response = llm_client.call(prompt=prompt, system=system_prompt)
        total_tokens_used = int(llm_response.tokens_used)
        total_latency_ms = int(llm_response.latency_ms)
        transformed_content = llm_client.extract_code_block(llm_response.content)
        if not transformed_content.strip():
            raise ValueError("LLM returned empty transformed content")

        repair_attempts_used = 0
        syntax_gate_passed = True
        syntax_gate = kwargs.get("syntax_gate_config") or _syntax_gate_config(config)
        syntax_gate_enabled = bool(syntax_gate.get("enabled", True))
        repair_attempts_max = int(syntax_gate.get("repair_attempts_max", 2))

        validate_python_syntax = (
            kwargs.get("validate_python_syntax") or _validate_python_syntax
        )
        build_syntax_repair_prompt = (
            kwargs.get("build_syntax_repair_prompt") or _build_syntax_repair_prompt
        )

        if file_kind == "python" and syntax_gate_enabled:
            syntax_error = validate_python_syntax(
                source_code=transformed_content,
                file_key=file_key,
            )
            while syntax_error and repair_attempts_used < repair_attempts_max:
                repair_attempts_used += 1
                repair_prompt = build_syntax_repair_prompt(
                    file_key=file_key,
                    broken_content=transformed_content,
                    syntax_error=syntax_error,
                )
                repair_response = llm_client.call(
                    prompt=repair_prompt, system=system_prompt
                )
                total_tokens_used += int(repair_response.tokens_used)
                total_latency_ms += int(repair_response.latency_ms)
                transformed_content = llm_client.extract_code_block(
                    repair_response.content
                )
                if not transformed_content.strip():
                    raise ValueError("LLM returned empty repaired content")
                syntax_error = validate_python_syntax(
                    source_code=transformed_content,
                    file_key=file_key,
                )

            if syntax_error:
                syntax_gate_passed = False
                return {
                    "success": False,
                    "retryable": True,
                    "file_key": file_key,
                    "error": f"syntax_gate_failed: {syntax_error}",
                    "tokens_used": total_tokens_used,
                    "latency_ms": total_latency_ms,
                    "repair_attempts_used": repair_attempts_used,
                    "syntax_gate_passed": syntax_gate_passed,
                    "large_file_mode": bool(kwargs.get("large_file_mode", False)),
                    "retry_count": int(status_entry.get("retry_count", 0)) + 1,
                    "inhibition": float(status_entry.get("inhibition", 0.0)) + 0.5,
                    "file_kind": file_kind,
                    "transform_mode": "python_syntax_gate",
                }

        transformed_to_write = transformed_content.rstrip("\n") + "\n"
        file_path.write_text(transformed_to_write, encoding="utf-8")

        count_diff_lines = kwargs.get("count_diff_lines") or _count_diff_lines
        diff_lines = count_diff_lines(
            before=source_content,
            after=transformed_content,
            file_key=file_key,
        )

        return {
            "success": True,
            "file_key": file_key,
            "tokens_used": total_tokens_used,
            "latency_ms": total_latency_ms,
            "diff_lines": diff_lines,
            "patterns": patterns,
            "repair_attempts_used": repair_attempts_used,
            "syntax_gate_passed": syntax_gate_passed,
            "large_file_mode": bool(kwargs.get("large_file_mode", False)),
            "retry_count": int(status_entry.get("retry_count", 0)),
            "inhibition": float(status_entry.get("inhibition", 0.0)),
            "file_kind": file_kind,
            "transform_mode": (
                "python_syntax_gate" if file_kind == "python" else "text_full_file"
            ),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "success": False,
            "retryable": False,
            "file_key": file_key,
            "error": str(exc),
            "retry_count": int(status_entry.get("retry_count", 0)),
            "inhibition": float(status_entry.get("inhibition", 0.0)),
            "file_kind": file_kind,
            "transform_mode": "unknown",
        }


def collect_few_shot_examples(
    store: Any,
    repo_path: str | Path,
    target_patterns: list[str],
    target_file_key: str,
    max_examples: int = 3,
) -> list[str]:
    """Gather validated file examples that share patterns with the target.

    Reads quality and status pheromones (cognitive stigmergy) to find
    high-confidence validated files whose patterns overlap with the target.
    """

    if max_examples <= 0:
        return []

    validated_entries = store.query("status", status="validated")
    quality_entries = store.read_all("quality")
    target_pattern_set = set(target_patterns)
    repo_root = Path(repo_path)

    examples: list[str] = []
    for file_key in sorted(validated_entries.keys()):
        if file_key == target_file_key:
            continue

        quality = quality_entries.get(file_key, {})
        if float(quality.get("confidence", 0.0)) < 0.8:
            continue

        task_entry = store.read_one("tasks", file_key) or {}
        if str(task_entry.get("file_kind", _infer_file_kind(file_key))) != "python":
            continue

        example_patterns = set(task_entry.get("patterns_found", []))
        if target_pattern_set and not (target_pattern_set & example_patterns):
            continue

        example_file = repo_root / file_key
        if not example_file.exists():
            continue

        transformed_text = example_file.read_text(encoding="utf-8", errors="ignore")
        examples.append(
            "\n".join(
                [
                    f"Example file: {file_key}",
                    f"Patterns: {sorted(example_patterns)}",
                    "Converted output:",
                    transformed_text,
                ]
            )
        )

        if len(examples) >= max_examples:
            break

    return examples


def build_retry_context(
    store: Any,
    file_key: str,
    status_entry: dict[str, Any],
    max_issues: int | None = None,
) -> str:
    """Build retry context string from quality pheromones for a file.

    Reads quality traces to inform the LLM about previous failure issues.
    """

    if int(status_entry.get("retry_count", 0)) <= 0:
        return ""

    quality_entry = store.read_one("quality", file_key) or {}
    issues = list(quality_entry.get("issues", []))
    if max_issues is not None:
        issues = issues[:max_issues]
    if not issues:
        return "Retry context: this file was previously retried."

    issues_text = "\n".join(f"- {issue}" for issue in issues)
    return f"Retry context from previous failures:\n{issues_text}"


def _build_default_prompt(
    *,
    file_key: str,
    source_content: str,
    patterns: list[str],
    file_kind: str,
) -> str:
    if file_kind != "python":
        return "\n\n".join(
            [
                "Update this text file so it matches a completed Python 3 migration.",
                f"File: {file_key}",
                f"Detected migration traces: {patterns}",
                "Instructions:",
                "- Update outdated Python 2 references to Python 3 equivalents.",
                "- Keep wording and intent as stable as possible.",
                "- Return ONLY the full updated file content.",
                "Source file:",
                "---",
                source_content,
                "---",
            ]
        )

    return "\n\n".join(
        [
            "Convert this Python 2 file to Python 3.",
            f"File: {file_key}",
            f"Patterns to address: {patterns}",
            "Source file:",
            "---",
            source_content,
            "---",
            "Return ONLY the complete converted Python 3 file.",
        ]
    )


def _infer_file_kind(file_key: str) -> str:
    return "python" if str(file_key).endswith(".py") else "text"


def _count_diff_lines(before: str, after: str, file_key: str) -> int:
    diff = difflib.unified_diff(
        before.splitlines(),
        after.splitlines(),
        fromfile=f"a/{file_key}",
        tofile=f"b/{file_key}",
        lineterm="",
    )

    count = 0
    for line in diff:
        if line.startswith(("+++", "---", "@@")):
            continue
        if line.startswith("+") or line.startswith("-"):
            count += 1
    return count


def _validate_python_syntax(source_code: str, file_key: str) -> str | None:
    try:
        ast.parse(source_code, filename=file_key)
    except SyntaxError as exc:
        line = exc.lineno if exc.lineno is not None else "?"
        column = exc.offset if exc.offset is not None else "?"
        message = exc.msg if exc.msg else "invalid syntax"
        return f"{message} (line {line}, column {column})"
    return None


def _build_syntax_repair_prompt(
    *,
    file_key: str,
    broken_content: str,
    syntax_error: str,
) -> str:
    return "\n\n".join(
        [
            "Repair this Python file so it is syntactically valid Python 3.",
            f"File: {file_key}",
            f"Compiler error: {syntax_error}",
            "Constraints:",
            "- Return ONLY the full corrected Python file.",
            "- Preserve semantics as much as possible.",
            "- Do not include markdown fences or explanations.",
            "Broken file content:",
            "---",
            broken_content,
            "---",
        ]
    )


def _syntax_gate_config(config: dict[str, Any]) -> dict[str, Any]:
    section = config.get("transformer", {}).get("syntax_gate", {})
    return {
        "enabled": bool(section.get("enabled", True)),
        "repair_attempts_max": int(section.get("repair_attempts_max", 2)),
    }
