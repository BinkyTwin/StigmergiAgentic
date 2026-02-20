"""Discovery capability shared across specialized and generalist agents."""

from __future__ import annotations

import ast
import json
import logging
import re
from pathlib import Path
from typing import Any, Callable

from ._config import non_python_config as _non_python_config

SCOUT_ROLE_PROMPT = (
    "Your role: SCOUT (explorer/forager). "
    "You analyze Python 2 source files to identify ALL migration patterns. "
    "Your output becomes task pheromones that guide a downstream Transformer agent. "
    "Any pattern you miss will not be addressed by the colony. "
    "Return only valid JSON matching the requested schema."
)

SEVERITY_WEIGHTS = {"high": 1.5, "medium": 1.0, "low": 0.5}

PATTERN_NAMES = [
    "print_statement",
    "print_chevron",
    "dict_iteritems",
    "dict_iterkeys",
    "dict_itervalues",
    "dict_has_key",
    "xrange",
    "unicode_literal",
    "long_literal",
    "raise_syntax",
    "except_syntax",
    "old_division",
    "raw_input",
    "apply_builtin",
    "execfile_builtin",
    "string_module",
    "urllib_import",
    "metaclass_syntax",
    "future_imports",
]

REGEX_PATTERNS: dict[str, re.Pattern[str]] = {
    "print_statement": re.compile(r"^\s*print\s+[^\(].*", re.MULTILINE),
    "print_chevron": re.compile(r"^\s*print\s*>>\s*[^,]+,", re.MULTILINE),
    "dict_iteritems": re.compile(r"\.iteritems\s*\("),
    "dict_iterkeys": re.compile(r"\.iterkeys\s*\("),
    "dict_itervalues": re.compile(r"\.itervalues\s*\("),
    "dict_has_key": re.compile(r"\.has_key\s*\("),
    "xrange": re.compile(r"\bxrange\b"),
    "unicode_literal": re.compile(r"\bu[\"']"),
    "long_literal": re.compile(r"\b\d+L\b"),
    "raise_syntax": re.compile(r"\braise\s+[\w\.]+\s*,\s*[^\n]+"),
    "except_syntax": re.compile(r"\bexcept\s+[^:\n]+\s*,\s*\w+\s*:"),
    "raw_input": re.compile(r"\braw_input\s*\("),
    "apply_builtin": re.compile(r"\bapply\s*\("),
    "execfile_builtin": re.compile(r"\bexecfile\s*\("),
    "urllib_import": re.compile(r"\b(import\s+urllib2|from\s+urllib2\s+import)\b"),
    "metaclass_syntax": re.compile(r"__metaclass__\s*="),
}

_TEXT_PY_REF_RE = re.compile(r"(?P<ref>[A-Za-z0-9_./-]+\.py)\b")


def discover_candidate_files(
    repo_path: str | Path, config: dict[str, Any]
) -> list[str]:
    """Return discoverable files for this run.

    Python files are always included. Non-Python files are included only when
    `capabilities.non_python.enabled` is true.
    """

    root = Path(repo_path)
    excluded_dirs = {
        ".git",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }
    non_python = _non_python_config(config)
    include_text = bool(non_python["enabled"])
    include_extensions = set(non_python["include_extensions"])

    file_keys: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in excluded_dirs for part in relative.parts):
            continue

        suffix = path.suffix.lower()
        if suffix == ".py":
            file_keys.append(relative.as_posix())
            continue

        if include_text and suffix in include_extensions:
            file_keys.append(relative.as_posix())

    return sorted(file_keys)


def discover_files(
    store: Any,
    repo_path: str | Path,
    llm_client: Any | None,
    config: dict[str, Any],
    agent_name: str,
    *,
    candidate_files: list[str] | None = None,
    all_file_keys: list[str] | None = None,
    build_system_prompt: Callable[[str], str] | None = None,
    logger: logging.Logger | None = None,
    filter_existing: bool = False,
) -> list[dict[str, Any]]:
    """Analyze candidate files and return raw discovery entries.

    Returned entries must be normalized with `normalize_discovered_entries`.

    When *filter_existing* is True and *store* is not None, files already
    present in task pheromones are skipped (avoids re-scanning).
    """

    del agent_name  # retained for API symmetry with other capabilities.

    root = Path(repo_path)
    log = logger or logging.getLogger(__name__)
    file_keys = candidate_files or discover_candidate_files(root, config)

    if filter_existing and store is not None:
        existing_tasks = set(store.read_all("tasks").keys())
        file_keys = [fk for fk in file_keys if fk not in existing_tasks]
    known_file_keys = set(all_file_keys or file_keys)
    python_file_keys = {key for key in known_file_keys if key.endswith(".py")}

    analyses: list[dict[str, Any]] = []
    for file_key in file_keys:
        file_path = root / file_key
        suffix = file_path.suffix.lower()
        file_kind = "python" if suffix == ".py" else "text"

        try:
            file_content = _read_text_file(
                path=file_path, config=config, file_kind=file_kind
            )
        except OSError:
            log.warning(
                "Scout could not read file=%s, skipping task extraction", file_key
            )
            continue

        if file_content is None:
            continue

        entry: dict[str, Any] | None
        if file_kind == "python":
            entry = _analyze_python_file(
                file_key=file_key,
                file_content=file_content,
                all_python_file_keys=python_file_keys,
                llm_client=llm_client,
                config=config,
                build_system_prompt=build_system_prompt,
                logger=log,
            )
        else:
            entry = _analyze_text_file(
                file_key=file_key,
                file_content=file_content,
                all_file_keys=known_file_keys,
                config=config,
            )

        if entry is None:
            continue

        entry["file_kind"] = file_kind
        entry["file_extension"] = suffix
        analyses.append(entry)

    return analyses


def normalize_discovered_entries(
    analyses: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Attach normalized/clamped intensities to discovery entries."""

    entries = [dict(item) for item in analyses]
    if not entries:
        return entries

    raw_scores = [float(entry.get("raw_score", 0.0)) for entry in entries]
    score_min = min(raw_scores)
    score_max = max(raw_scores)
    clamp_min, clamp_max = config.get("pheromones", {}).get(
        "task_intensity_clamp", [0.1, 1.0]
    )

    for entry in entries:
        raw_score = float(entry.get("raw_score", 0.0))
        if score_max == score_min:
            normalized = 0.5
        else:
            normalized = (raw_score - score_min) / (score_max - score_min)
        entry["intensity"] = _clamp(
            float(normalized), float(clamp_min), float(clamp_max)
        )

    return entries


def _analyze_python_file(
    *,
    file_key: str,
    file_content: str,
    all_python_file_keys: set[str],
    llm_client: Any | None,
    config: dict[str, Any],
    build_system_prompt: Callable[[str], str] | None,
    logger: logging.Logger,
) -> dict[str, Any]:
    regex_details = _detect_patterns(file_content)
    dependencies = _detect_internal_dependencies(
        file_key=file_key,
        file_content=file_content,
        all_file_keys=all_python_file_keys,
    )
    dep_count = len(dependencies)

    llm_analysis = None
    if llm_client is not None and _llm_analysis_enabled(config):
        llm_analysis = _llm_analyze_file(
            file_key=file_key,
            file_content=file_content,
            llm_client=llm_client,
            build_system_prompt=build_system_prompt,
            logger=logger,
        )

    merged = _merge_analyses(llm_analysis, regex_details)
    if llm_analysis is not None:
        raw_score = _compute_hybrid_score(
            patterns=merged,
            dep_count=dep_count,
            llm_analysis=llm_analysis,
            config=config,
        )
        analysis_source = "hybrid"
        llm_complexity_score: float | None = float(
            llm_analysis.get("complexity_score", 5.0)
        )
    else:
        raw_score = (len(merged) * 0.6) + (dep_count * 0.4)
        analysis_source = "regex"
        llm_complexity_score = None

    return {
        "file_key": file_key,
        "patterns_found": sorted({entry["pattern"] for entry in merged}),
        "pattern_details": merged,
        "pattern_count": len(merged),
        "dependencies": dependencies,
        "dep_count": dep_count,
        "raw_score": raw_score,
        "analysis_source": analysis_source,
        "llm_complexity_score": llm_complexity_score,
    }


def _analyze_text_file(
    *,
    file_key: str,
    file_content: str,
    all_file_keys: set[str],
    config: dict[str, Any],
) -> dict[str, Any] | None:
    non_python = _non_python_config(config)
    legacy_tokens: list[str] = non_python["legacy_tokens"]

    pattern_details = _detect_text_legacy_patterns(file_content, legacy_tokens)
    dependencies, ref_details = _detect_text_python_dependencies(
        file_content=file_content,
        file_key=file_key,
        all_file_keys=all_file_keys,
    )
    pattern_details.extend(ref_details)

    if not pattern_details and not dependencies:
        return None

    dep_count = len(dependencies)
    raw_score = (len(pattern_details) * 0.6) + (dep_count * 0.4)
    return {
        "file_key": file_key,
        "patterns_found": sorted({entry["pattern"] for entry in pattern_details}),
        "pattern_details": sorted(
            pattern_details,
            key=lambda item: (
                int(item.get("line", 1)),
                str(item.get("pattern", "")),
                str(item.get("source", "")),
            ),
        ),
        "pattern_count": len(pattern_details),
        "dependencies": dependencies,
        "dep_count": dep_count,
        "raw_score": raw_score,
        "analysis_source": "text_scan",
        "llm_complexity_score": None,
    }


def _detect_patterns(file_content: str) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    seen_by_pattern_line: set[tuple[str, int]] = set()

    ast_tree: ast.AST | None = None
    try:
        ast_tree = ast.parse(file_content)
    except SyntaxError:
        ast_tree = None

    if ast_tree is not None:
        for pattern, line in _detect_ast_patterns(ast_tree):
            key = (pattern, line)
            if key in seen_by_pattern_line:
                continue
            seen_by_pattern_line.add(key)
            details.append({"pattern": pattern, "line": line, "source": "ast"})

    for pattern, regex in REGEX_PATTERNS.items():
        for match in regex.finditer(file_content):
            line = _line_from_offset(file_content, match.start())
            key = (pattern, line)
            if key in seen_by_pattern_line:
                continue
            seen_by_pattern_line.add(key)
            details.append({"pattern": pattern, "line": line, "source": "regex"})

    if not _has_future_import(file_content):
        details.append({"pattern": "future_imports", "line": 1, "source": "regex"})

    return sorted(
        details,
        key=lambda item: (
            int(item["line"]),
            str(item["pattern"]),
            str(item["source"]),
        ),
    )


def _detect_text_legacy_patterns(
    file_content: str,
    legacy_tokens: list[str],
) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()

    for token in legacy_tokens:
        token_text = str(token).strip()
        if not token_text:
            continue
        regex = re.compile(re.escape(token_text), re.IGNORECASE)
        pattern_name = f"legacy_token_{_to_pattern_id(token_text)}"
        for match in regex.finditer(file_content):
            line = _line_from_offset(file_content, match.start())
            key = (pattern_name, line)
            if key in seen:
                continue
            seen.add(key)
            details.append(
                {
                    "pattern": pattern_name,
                    "line": line,
                    "source": "text_scan",
                    "token": token_text,
                }
            )

    return details


def _detect_text_python_dependencies(
    *,
    file_content: str,
    file_key: str,
    all_file_keys: set[str],
) -> tuple[list[str], list[dict[str, Any]]]:
    dependencies: set[str] = set()
    details: list[dict[str, Any]] = []

    for match in _TEXT_PY_REF_RE.finditer(file_content):
        raw_ref = match.group("ref")
        if not raw_ref:
            continue
        resolved = _resolve_python_reference(raw_ref, file_key, all_file_keys)
        if resolved is None:
            continue
        dependencies.add(resolved)
        details.append(
            {
                "pattern": "python_file_reference",
                "line": _line_from_offset(file_content, match.start()),
                "source": "text_scan",
                "reference": raw_ref,
            }
        )

    return sorted(dependencies), details


def _resolve_python_reference(
    raw_ref: str,
    file_key: str,
    all_file_keys: set[str],
) -> str | None:
    normalized = raw_ref.strip().replace("\\", "/")
    if normalized in all_file_keys:
        return normalized

    current_dir = Path(file_key).parent.as_posix()
    if current_dir and current_dir != ".":
        candidate = f"{current_dir}/{normalized}".replace("//", "/")
        if candidate in all_file_keys:
            return candidate

    basename = Path(normalized).name
    matches = [
        key for key in all_file_keys if key.endswith(f"/{basename}") or key == basename
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _detect_ast_patterns(tree: ast.AST) -> list[tuple[str, int]]:
    detected: list[tuple[str, int]] = []
    imports_string = False

    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            if _is_integer_like(node.left) and _is_integer_like(node.right):
                detected.append(("old_division", int(getattr(node, "lineno", 1))))

        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "string":
                    imports_string = True
                if alias.name == "urllib2":
                    detected.append(("urllib_import", int(getattr(node, "lineno", 1))))

        if isinstance(node, ast.ImportFrom):
            if node.module == "urllib2":
                detected.append(("urllib_import", int(getattr(node, "lineno", 1))))

        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__metaclass__":
                    detected.append(
                        ("metaclass_syntax", int(getattr(node, "lineno", 1)))
                    )

        if isinstance(node, ast.Call):
            if (
                imports_string
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "string"
            ):
                detected.append(("string_module", int(getattr(node, "lineno", 1))))

    return detected


def _detect_internal_dependencies(
    *,
    file_key: str,
    file_content: str,
    all_file_keys: set[str],
) -> list[str]:
    imported_modules: set[str] = set()

    try:
        tree = ast.parse(file_content)
    except SyntaxError:
        tree = None

    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
    else:
        import_re = re.compile(
            r"^\s*(?:from\s+([\w\.]+)\s+import|import\s+([\w\.]+))",
            re.MULTILINE,
        )
        for match in import_re.finditer(file_content):
            module = match.group(1) or match.group(2)
            if module:
                imported_modules.add(module)

    dependencies: set[str] = set()
    for module_name in imported_modules:
        for candidate in _module_to_file_candidates(module_name):
            if candidate in all_file_keys and candidate != file_key:
                dependencies.add(candidate)

    return sorted(dependencies)


def _module_to_file_candidates(module_name: str) -> list[str]:
    normalized = module_name.replace(".", "/")
    return [f"{normalized}.py", f"{normalized}/__init__.py"]


def _has_future_import(file_content: str) -> bool:
    return bool(
        re.search(r"^\s*from\s+__future__\s+import\s+", file_content, re.MULTILINE)
    )


def _llm_analysis_enabled(config: dict[str, Any]) -> bool:
    return bool(config.get("scout", {}).get("llm_analysis", {}).get("enabled", True))


def _llm_analyze_file(
    *,
    file_key: str,
    file_content: str,
    llm_client: Any,
    build_system_prompt: Callable[[str], str] | None,
    logger: logging.Logger,
) -> dict[str, Any] | None:
    known_patterns = (
        "print_statement, dict_iteritems, dict_iterkeys, dict_itervalues, "
        "dict_has_key, xrange, unicode_literal, long_literal, raise_syntax, "
        "except_syntax, old_division, raw_input, apply_builtin, execfile_builtin, "
        "string_module, urllib_import, metaclass_syntax, future_imports"
    )

    user_prompt = (
        "Analyze this Python 2 file for ALL patterns that need conversion to Python 3.\n\n"
        f"File: {file_key}\n---\n{file_content}\n---\n\n"
        "Return a JSON object:\n"
        "{\n"
        '  "patterns": [\n'
        '    {"name": "snake_case_id", "line": <int>, "severity": "high|medium|low",\n'
        '     "description": "Brief explanation"}\n'
        "  ],\n"
        '  "complexity_score": <float 1-10>,\n'
        '  "summary": "One sentence on migration difficulty"\n'
        "}\n\n"
        f"Known pattern identifiers (non-exhaustive):\n{known_patterns}\n\n"
        "You may identify patterns beyond this list. Use descriptive snake_case names."
    )

    system_prompt = (
        build_system_prompt(SCOUT_ROLE_PROMPT)
        if build_system_prompt
        else SCOUT_ROLE_PROMPT
    )
    try:
        response = llm_client.call(prompt=user_prompt, system=system_prompt)
        return _parse_llm_analysis(
            response.content, llm_client=llm_client, logger=logger
        )
    except Exception:  # noqa: BLE001
        logger.warning(
            "Scout LLM analysis failed for %s, falling back to regex", file_key
        )
        return None


def _parse_llm_analysis(
    raw_content: str,
    *,
    llm_client: Any | None,
    logger: logging.Logger,
) -> dict[str, Any] | None:
    text = raw_content.strip()
    if llm_client is not None:
        text = llm_client.extract_code_block(text)

    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Scout LLM returned unparseable JSON")
        return None

    if not isinstance(data, dict) or "patterns" not in data:
        logger.warning("Scout LLM response missing 'patterns' key")
        return None
    if not isinstance(data["patterns"], list):
        return None
    for pattern in data["patterns"]:
        if not isinstance(pattern, dict) or "name" not in pattern:
            return None
    return data


def _merge_analyses(
    llm_analysis: dict[str, Any] | None,
    regex_details: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if llm_analysis is None:
        return list(regex_details)

    merged: list[dict[str, Any]] = []
    regex_by_key: dict[tuple[str, int], dict[str, Any]] = {}
    for entry in regex_details:
        key = (entry["pattern"], int(entry["line"]))
        regex_by_key[key] = entry

    for llm_pattern in llm_analysis.get("patterns", []):
        name = str(llm_pattern.get("name", "")).strip()
        if not name:
            continue
        line = _coerce_line_number(llm_pattern.get("line", 1))
        key = (name, line)

        if key in regex_by_key:
            entry = dict(regex_by_key[key])
            entry["source"] = "llm+regex"
            entry["severity"] = llm_pattern.get("severity", "medium")
            if "description" in llm_pattern:
                entry["description"] = llm_pattern["description"]
            merged.append(entry)
        else:
            payload = {
                "pattern": name,
                "line": line,
                "source": "llm",
                "severity": llm_pattern.get("severity", "medium"),
            }
            if "description" in llm_pattern:
                payload["description"] = llm_pattern["description"]
            merged.append(payload)

    existing = {(entry["pattern"], int(entry["line"])) for entry in merged}
    for entry in regex_details:
        key = (entry["pattern"], int(entry["line"]))
        if key not in existing:
            merged.append(entry)

    return sorted(merged, key=lambda item: (int(item["line"]), str(item["pattern"])))


def _compute_hybrid_score(
    *,
    patterns: list[dict[str, Any]],
    dep_count: int,
    llm_analysis: dict[str, Any],
    config: dict[str, Any],
) -> float:
    weights = (
        config.get("scout", {})
        .get("llm_analysis", {})
        .get(
            "intensity_weights",
            {
                "weighted_patterns": 0.5,
                "dependencies": 0.2,
                "llm_complexity": 0.3,
            },
        )
    )
    severity_weights = (
        config.get("scout", {})
        .get("llm_analysis", {})
        .get(
            "severity_weights",
            SEVERITY_WEIGHTS,
        )
    )

    weighted_count = sum(
        float(severity_weights.get(entry.get("severity", "medium"), 1.0))
        for entry in patterns
    )
    complexity = float(llm_analysis.get("complexity_score", 5.0)) / 10.0
    return (
        weighted_count * float(weights.get("weighted_patterns", 0.5))
        + dep_count * float(weights.get("dependencies", 0.2))
        + complexity * float(weights.get("llm_complexity", 0.3))
    )


def _coerce_line_number(raw_line: Any) -> int:
    try:
        line_number = int(raw_line) if raw_line is not None else 1
    except (TypeError, ValueError):
        return 1
    return line_number if line_number > 0 else 1


def _line_from_offset(content: str, offset: int) -> int:
    return content.count("\n", 0, offset) + 1


def _is_integer_like(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return True
    ast_num = getattr(ast, "Num", None)
    if ast_num is None:
        return False
    return isinstance(node, ast_num) and isinstance(getattr(node, "n", None), int)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _to_pattern_id(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return normalized or "legacy"


def _read_text_file(
    *,
    path: Path,
    config: dict[str, Any],
    file_kind: str,
) -> str | None:
    non_python = _non_python_config(config)
    if file_kind == "text":
        file_size = path.stat().st_size
        if file_size > int(non_python["max_text_file_bytes"]):
            return None
    return path.read_text(encoding="utf-8", errors="ignore")
