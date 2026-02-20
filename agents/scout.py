"""Scout agent: discovers Python 2 migration tasks and deposits task pheromones."""

from __future__ import annotations

import ast
import json
import logging
import re
from typing import Any

from .base_agent import BaseAgent

LOGGER = logging.getLogger(__name__)

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


class Scout(BaseAgent):
    """Analyze Python files and deposit prioritized migration tasks."""

    def perceive(self) -> dict[str, Any]:
        tasks = self.store.read_all("tasks")
        status = self.store.read_all("status")
        all_file_keys = self._discover_python_files()

        terminal_statuses = {"validated", "skipped", "needs_review"}
        candidate_files: list[str] = []

        for file_key in all_file_keys:
            if file_key in tasks:
                continue
            status_value = status.get(file_key, {}).get("status")
            if status_value in terminal_statuses:
                continue
            candidate_files.append(file_key)

        return {
            "candidate_files": sorted(candidate_files),
            "all_file_keys": all_file_keys,
        }

    def should_act(self, perception: dict[str, Any]) -> bool:
        return bool(perception.get("candidate_files"))

    def decide(self, perception: dict[str, Any]) -> dict[str, Any]:
        all_file_keys = set(perception["all_file_keys"])
        analyses: list[dict[str, Any]] = []

        for file_key in perception["candidate_files"]:
            file_path = self.target_repo_path / file_key
            try:
                file_content = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                LOGGER.warning(
                    "Scout could not read file=%s, skipping task extraction",
                    file_key,
                )
                continue

            regex_details = self._detect_patterns(file_content)
            dependencies = self._detect_internal_dependencies(
                file_key=file_key,
                file_content=file_content,
                all_file_keys=all_file_keys,
            )
            dep_count = len(dependencies)

            llm_analysis = None
            if self.llm_client is not None and self._llm_analysis_enabled():
                llm_analysis = self._llm_analyze_file(file_key, file_content)

            merged = self._merge_analyses(llm_analysis, regex_details)

            if llm_analysis is not None:
                raw_score = self._compute_hybrid_score(
                    merged, dep_count, llm_analysis
                )
                analysis_source = "hybrid"
                llm_complexity_score = float(
                    llm_analysis.get("complexity_score", 5.0)
                )
            else:
                raw_score = (len(merged) * 0.6) + (dep_count * 0.4)
                analysis_source = "regex"
                llm_complexity_score = None

            analyses.append(
                {
                    "file_key": file_key,
                    "patterns_found": sorted(
                        {entry["pattern"] for entry in merged}
                    ),
                    "pattern_details": merged,
                    "pattern_count": len(merged),
                    "dependencies": dependencies,
                    "dep_count": dep_count,
                    "raw_score": raw_score,
                    "analysis_source": analysis_source,
                    "llm_complexity_score": llm_complexity_score,
                }
            )

        return {"analyses": analyses}

    def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        analyses = list(action["analyses"])

        if not analyses:
            return {"entries": []}

        raw_scores = [entry["raw_score"] for entry in analyses]
        score_min = min(raw_scores)
        score_max = max(raw_scores)
        clamp_min, clamp_max = self.config.get("pheromones", {}).get(
            "task_intensity_clamp", [0.1, 1.0]
        )

        for entry in analyses:
            if score_max == score_min:
                normalized = 0.5
            else:
                normalized = (entry["raw_score"] - score_min) / (score_max - score_min)

            entry["intensity"] = self._clamp(
                float(normalized), float(clamp_min), float(clamp_max)
            )

        return {"entries": analyses}

    def deposit(self, result: dict[str, Any]) -> None:
        for entry in result.get("entries", []):
            file_key = entry["file_key"]

            task_payload: dict[str, Any] = {
                "intensity": entry["intensity"],
                "patterns_found": entry["patterns_found"],
                "pattern_count": entry["pattern_count"],
                "pattern_details": entry["pattern_details"],
                "dependencies": entry["dependencies"],
                "dep_count": entry["dep_count"],
                "analysis_source": entry.get("analysis_source", "regex"),
            }
            if entry.get("llm_complexity_score") is not None:
                task_payload["llm_complexity_score"] = entry["llm_complexity_score"]

            self.store.write(
                "tasks", file_key=file_key, data=task_payload, agent_id=self.name
            )

            status_payload = {
                "status": "pending",
                "retry_count": 0,
                "inhibition": 0.0,
                "metadata": {
                    "patterns_found": entry["patterns_found"],
                },
            }
            self.store.write(
                "status", file_key=file_key, data=status_payload, agent_id=self.name
            )

    def _discover_python_files(self) -> list[str]:
        file_keys: list[str] = []
        excluded_dirs = {".git", ".venv", "__pycache__"}

        for path in self.target_repo_path.rglob("*.py"):
            if any(part in excluded_dirs for part in path.parts):
                continue
            file_keys.append(path.relative_to(self.target_repo_path).as_posix())

        return sorted(file_keys)

    def _detect_patterns(self, file_content: str) -> list[dict[str, Any]]:
        details: list[dict[str, Any]] = []
        seen_by_pattern_line: set[tuple[str, int]] = set()

        ast_tree: ast.AST | None = None
        try:
            ast_tree = ast.parse(file_content)
        except SyntaxError:
            ast_tree = None

        if ast_tree is not None:
            for pattern, line in self._detect_ast_patterns(ast_tree):
                key = (pattern, line)
                if key in seen_by_pattern_line:
                    continue
                seen_by_pattern_line.add(key)
                details.append({"pattern": pattern, "line": line, "source": "ast"})

        for pattern, regex in REGEX_PATTERNS.items():
            for match in regex.finditer(file_content):
                line = self._line_from_offset(file_content, match.start())
                key = (pattern, line)
                if key in seen_by_pattern_line:
                    continue
                seen_by_pattern_line.add(key)
                details.append({"pattern": pattern, "line": line, "source": "regex"})

        if not self._has_future_import(file_content):
            details.append({"pattern": "future_imports", "line": 1, "source": "regex"})

        return sorted(
            details,
            key=lambda item: (
                int(item["line"]),
                str(item["pattern"]),
                str(item["source"]),
            ),
        )

    def _detect_ast_patterns(self, tree: ast.AST) -> list[tuple[str, int]]:
        detected: list[tuple[str, int]] = []
        imports_string = False

        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                if self._is_integer_like(node.left) and self._is_integer_like(
                    node.right
                ):
                    detected.append(("old_division", int(getattr(node, "lineno", 1))))

            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "string":
                        imports_string = True
                    if alias.name == "urllib2":
                        detected.append(
                            ("urllib_import", int(getattr(node, "lineno", 1)))
                        )

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
        self,
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
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imported_modules.add(node.module)
        else:
            import_re = re.compile(
                r"^\s*(?:from\s+([\w\.]+)\s+import|import\s+([\w\.]+))", re.MULTILINE
            )
            for match in import_re.finditer(file_content):
                module = match.group(1) or match.group(2)
                if module:
                    imported_modules.add(module)

        dependencies: set[str] = set()
        for module_name in imported_modules:
            for candidate in self._module_to_file_candidates(module_name):
                if candidate in all_file_keys and candidate != file_key:
                    dependencies.add(candidate)

        return sorted(dependencies)

    def _module_to_file_candidates(self, module_name: str) -> list[str]:
        normalized = module_name.replace(".", "/")
        return [f"{normalized}.py", f"{normalized}/__init__.py"]

    def _has_future_import(self, file_content: str) -> bool:
        return bool(
            re.search(r"^\s*from\s+__future__\s+import\s+", file_content, re.MULTILINE)
        )

    def _llm_analysis_enabled(self) -> bool:
        return bool(
            self.config.get("scout", {}).get("llm_analysis", {}).get("enabled", True)
        )

    def _llm_analyze_file(
        self, file_key: str, file_content: str
    ) -> dict[str, Any] | None:
        if self.llm_client is None:
            return None

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

        try:
            system_prompt = self._build_system_prompt(SCOUT_ROLE_PROMPT)
            response = self.llm_client.call(
                prompt=user_prompt, system=system_prompt
            )
            return self._parse_llm_analysis(response.content)
        except Exception:  # noqa: BLE001
            LOGGER.warning("Scout LLM analysis failed for %s, falling back to regex", file_key)
            return None

    def _parse_llm_analysis(self, raw_content: str) -> dict[str, Any] | None:
        text = raw_content.strip()
        if self.llm_client is not None:
            text = self.llm_client.extract_code_block(text)
        # Strip markdown fences if extract_code_block didn't handle them
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:]  # drop opening fence
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            LOGGER.warning("Scout LLM returned unparseable JSON")
            return None

        if not isinstance(data, dict) or "patterns" not in data:
            LOGGER.warning("Scout LLM response missing 'patterns' key")
            return None

        if not isinstance(data["patterns"], list):
            return None

        for pattern in data["patterns"]:
            if not isinstance(pattern, dict) or "name" not in pattern:
                return None

        return data

    def _merge_analyses(
        self,
        llm_analysis: dict[str, Any] | None,
        regex_details: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if llm_analysis is None:
            return list(regex_details)

        seen: set[tuple[str, int]] = set()
        merged: list[dict[str, Any]] = []

        regex_by_key: dict[tuple[str, int], dict[str, Any]] = {}
        for entry in regex_details:
            key = (entry["pattern"], int(entry["line"]))
            regex_by_key[key] = entry
            seen.add(key)

        for llm_pat in llm_analysis.get("patterns", []):
            name = str(llm_pat.get("name", "")).strip()
            if not name:
                continue
            line = self._coerce_line_number(llm_pat.get("line", 1))
            key = (name, line)

            if key in regex_by_key:
                # Both sources agree — mark as llm+regex
                entry = dict(regex_by_key[key])
                entry["source"] = "llm+regex"
                entry["severity"] = llm_pat.get("severity", "medium")
                if "description" in llm_pat:
                    entry["description"] = llm_pat["description"]
                merged.append(entry)
            else:
                # LLM-only pattern (novel or different line)
                merged.append({
                    "pattern": name,
                    "line": line,
                    "source": "llm",
                    "severity": llm_pat.get("severity", "medium"),
                    **({"description": llm_pat["description"]} if "description" in llm_pat else {}),
                })
                seen.add(key)

        # Add regex-only patterns not covered by LLM
        for entry in regex_details:
            key = (entry["pattern"], int(entry["line"]))
            if key not in {(m["pattern"], int(m["line"])) for m in merged}:
                merged.append(entry)

        return sorted(
            merged,
            key=lambda item: (int(item["line"]), str(item["pattern"])),
        )

    @staticmethod
    def _coerce_line_number(raw_line: Any) -> int:
        try:
            line_number = int(raw_line) if raw_line is not None else 1
        except (TypeError, ValueError):
            return 1
        return line_number if line_number > 0 else 1

    def _compute_hybrid_score(
        self,
        patterns: list[dict[str, Any]],
        dep_count: int,
        llm_analysis: dict[str, Any],
    ) -> float:
        cfg = self.config.get("scout", {}).get(
            "llm_analysis", {}
        ).get("intensity_weights", {
            "weighted_patterns": 0.5,
            "dependencies": 0.2,
            "llm_complexity": 0.3,
        })
        severity_cfg = self.config.get("scout", {}).get(
            "llm_analysis", {}
        ).get("severity_weights", SEVERITY_WEIGHTS)

        weighted_count = sum(
            float(severity_cfg.get(p.get("severity", "medium"), 1.0))
            for p in patterns
        )
        complexity = float(llm_analysis.get("complexity_score", 5.0)) / 10.0

        return (
            weighted_count * float(cfg.get("weighted_patterns", 0.5))
            + dep_count * float(cfg.get("dependencies", 0.2))
            + complexity * float(cfg.get("llm_complexity", 0.3))
        )

    def _is_integer_like(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return True
        ast_num = getattr(ast, "Num", None)
        if ast_num is None:
            return False
        return isinstance(node, ast_num) and isinstance(getattr(node, "n", None), int)

    def _line_from_offset(self, content: str, offset: int) -> int:
        return content.count("\n", 0, offset) + 1

    def _clamp(self, value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, value))
