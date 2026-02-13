"""Transformer agent: converts Python 2 files to Python 3 using LLM guidance."""

from __future__ import annotations

import ast
import difflib
from pathlib import Path
from typing import Any

from .base_agent import BaseAgent


class Transformer(BaseAgent):
    """Consume task pheromones and produce transformed Python 3 files."""

    def perceive(self) -> dict[str, Any]:
        candidate_status_entries = self.store.query(
            "status", status__in={"pending", "retry"}
        )
        threshold_config = self.config.get("thresholds", {})
        pheromone_config = self.config.get("pheromones", {})

        intensity_min = float(threshold_config.get("transformer_intensity_min", 0.2))
        inhibition_threshold = float(pheromone_config.get("inhibition_threshold", 0.1))

        preferred_candidates: list[dict[str, Any]] = []
        fallback_candidates: list[dict[str, Any]] = []
        inhibited_candidates: list[dict[str, Any]] = []
        for file_key, status_entry in candidate_status_entries.items():
            task_entry = self.store.read_one("tasks", file_key)
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
            candidates = preferred_candidates
            candidates.sort(key=lambda item: (-item["intensity"], item["file_key"]))
            return {"candidates": candidates}

        if fallback_candidates:
            candidates = fallback_candidates
            candidates.sort(key=lambda item: (-item["intensity"], item["file_key"]))
            return {"candidates": candidates}

        candidates = inhibited_candidates
        candidates.sort(key=lambda item: (item["inhibition"], -item["intensity"], item["file_key"]))
        return {"candidates": candidates}

    def should_act(self, perception: dict[str, Any]) -> bool:
        return bool(perception.get("candidates"))

    def decide(self, perception: dict[str, Any]) -> dict[str, Any]:
        candidate = perception["candidates"][0]
        file_key = candidate["file_key"]
        file_path = self.target_repo_path / file_key
        source_content = file_path.read_text(encoding="utf-8", errors="ignore")
        line_count = self._line_count(source_content)

        large_file_config = self._large_file_config()
        large_file_mode = line_count >= int(large_file_config["line_threshold"])
        max_few_shot_examples = (
            int(large_file_config["max_few_shot_examples"])
            if large_file_mode
            else 3
        )
        max_retry_issues = (
            int(large_file_config["max_retry_issues"])
            if large_file_mode
            else None
        )

        patterns = list(candidate["task_entry"].get("patterns_found", []))
        few_shot_examples = self._collect_few_shot_examples(
            target_patterns=patterns,
            target_file_key=file_key,
            max_examples=max_few_shot_examples,
        )
        retry_context = self._build_retry_context(
            file_key=file_key,
            status_entry=candidate["status_entry"],
            max_issues=max_retry_issues,
        )

        prompt = self._build_prompt(
            file_key=file_key,
            source_content=source_content,
            patterns=patterns,
            few_shot_examples=few_shot_examples,
            retry_context=retry_context,
        )

        return {
            "file_key": file_key,
            "file_path": file_path,
            "source_content": source_content,
            "patterns": patterns,
            "prompt": prompt,
            "system_prompt": (
                "You are a Python 2 to Python 3 migration expert. "
                "Convert the full file while preserving semantics."
            ),
            "status_entry": candidate["status_entry"],
            "line_count": line_count,
            "large_file_mode": large_file_mode,
        }

    def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        file_key = action["file_key"]
        status_entry = action["status_entry"]

        self.store.update(
            "status",
            file_key=file_key,
            agent_id=self.name,
            status="in_progress",
            previous_status=status_entry.get("status", "pending"),
            retry_count=int(status_entry.get("retry_count", 0)),
            inhibition=float(status_entry.get("inhibition", 0.0)),
            current_tick=int(self.config.get("runtime", {}).get("tick", 0)),
        )

        try:
            if self.llm_client is None:
                raise RuntimeError("Transformer requires an initialized LLM client")

            syntax_gate_config = self._syntax_gate_config()
            syntax_gate_enabled = bool(syntax_gate_config["enabled"])
            repair_attempts_max = int(syntax_gate_config["repair_attempts_max"])

            llm_response = self.llm_client.call(
                prompt=action["prompt"],
                system=action["system_prompt"],
            )
            total_tokens_used = int(llm_response.tokens_used)
            total_latency_ms = int(llm_response.latency_ms)
            transformed_content = self.llm_client.extract_code_block(
                llm_response.content
            )
            if not transformed_content.strip():
                raise ValueError("LLM returned empty transformed content")

            repair_attempts_used = 0
            syntax_gate_passed = True

            if syntax_gate_enabled:
                syntax_error = self._validate_python_syntax(
                    source_code=transformed_content,
                    file_key=file_key,
                )
                while syntax_error and repair_attempts_used < repair_attempts_max:
                    repair_attempts_used += 1
                    repair_prompt = self._build_syntax_repair_prompt(
                        file_key=file_key,
                        broken_content=transformed_content,
                        syntax_error=syntax_error,
                    )
                    repair_response = self.llm_client.call(
                        prompt=repair_prompt,
                        system=action["system_prompt"],
                    )
                    total_tokens_used += int(repair_response.tokens_used)
                    total_latency_ms += int(repair_response.latency_ms)
                    transformed_content = self.llm_client.extract_code_block(
                        repair_response.content
                    )
                    if not transformed_content.strip():
                        raise ValueError("LLM returned empty repaired content")

                    syntax_error = self._validate_python_syntax(
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
                        "large_file_mode": bool(action.get("large_file_mode", False)),
                        "retry_count": int(status_entry.get("retry_count", 0)) + 1,
                        "inhibition": float(status_entry.get("inhibition", 0.0)) + 0.5,
                    }

            file_path: Path = action["file_path"]
            file_path.write_text(transformed_content + "\n", encoding="utf-8")

            diff_lines = self._count_diff_lines(
                before=action["source_content"],
                after=transformed_content,
                file_key=file_key,
            )

            return {
                "success": True,
                "file_key": file_key,
                "tokens_used": total_tokens_used,
                "latency_ms": total_latency_ms,
                "diff_lines": diff_lines,
                "patterns": action["patterns"],
                "repair_attempts_used": repair_attempts_used,
                "syntax_gate_passed": syntax_gate_passed,
                "large_file_mode": bool(action.get("large_file_mode", False)),
                "retry_count": int(status_entry.get("retry_count", 0)),
                "inhibition": float(status_entry.get("inhibition", 0.0)),
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "success": False,
                "retryable": False,
                "file_key": file_key,
                "error": str(exc),
                "retry_count": int(status_entry.get("retry_count", 0)),
                "inhibition": float(status_entry.get("inhibition", 0.0)),
            }

    def deposit(self, result: dict[str, Any]) -> None:
        if result.get("success"):
            self.store.update(
                "status",
                file_key=result["file_key"],
                agent_id=self.name,
                status="transformed",
                previous_status="in_progress",
                retry_count=int(result.get("retry_count", 0)),
                inhibition=float(result.get("inhibition", 0.0)),
                metadata={
                    "tokens_used": int(result.get("tokens_used", 0)),
                    "latency_ms": int(result.get("latency_ms", 0)),
                    "diff_lines": int(result.get("diff_lines", 0)),
                    "patterns_migrated": list(result.get("patterns", [])),
                    "repair_attempts_used": int(result.get("repair_attempts_used", 0)),
                    "syntax_gate_passed": bool(result.get("syntax_gate_passed", True)),
                    "large_file_mode": bool(result.get("large_file_mode", False)),
                },
            )
            return

        if result.get("retryable", False):
            self.store.update(
                "status",
                file_key=result["file_key"],
                agent_id=self.name,
                status="retry",
                previous_status="in_progress",
                retry_count=int(result.get("retry_count", 0)),
                inhibition=float(result.get("inhibition", 0.0)),
                metadata={
                    "error": result.get("error", "transformer retryable failure"),
                    "transformer_syntax_gate_failed": True,
                    "repair_attempts_used": int(result.get("repair_attempts_used", 0)),
                },
            )
            return

        self.store.update(
            "status",
            file_key=result["file_key"],
            agent_id=self.name,
            status="failed",
            previous_status="in_progress",
            retry_count=int(result.get("retry_count", 0)),
            inhibition=float(result.get("inhibition", 0.0)),
            metadata={"error": result.get("error", "unknown transformer error")},
        )

    def _collect_few_shot_examples(
        self,
        target_patterns: list[str],
        target_file_key: str,
        max_examples: int = 3,
    ) -> list[str]:
        if max_examples <= 0:
            return []

        validated_entries = self.store.query("status", status="validated")
        quality_entries = self.store.read_all("quality")
        target_pattern_set = set(target_patterns)

        examples: list[str] = []
        for file_key in sorted(validated_entries.keys()):
            if file_key == target_file_key:
                continue

            quality = quality_entries.get(file_key, {})
            if float(quality.get("confidence", 0.0)) < 0.8:
                continue

            task_entry = self.store.read_one("tasks", file_key) or {}
            example_patterns = set(task_entry.get("patterns_found", []))
            if target_pattern_set and not (target_pattern_set & example_patterns):
                continue

            example_file = self.target_repo_path / file_key
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

    def _build_retry_context(
        self,
        file_key: str,
        status_entry: dict[str, Any],
        max_issues: int | None = None,
    ) -> str:
        if int(status_entry.get("retry_count", 0)) <= 0:
            return ""

        quality_entry = self.store.read_one("quality", file_key) or {}
        issues = list(quality_entry.get("issues", []))
        if max_issues is not None:
            issues = issues[:max_issues]
        if not issues:
            return "Retry context: this file was previously retried."

        issues_text = "\n".join(f"- {issue}" for issue in issues)
        return f"Retry context from previous failures:\n{issues_text}"

    def _build_prompt(
        self,
        file_key: str,
        source_content: str,
        patterns: list[str],
        few_shot_examples: list[str],
        retry_context: str,
    ) -> str:
        sections = [
            "Convert this Python 2 file to Python 3.",
            f"File: {file_key}",
            f"Patterns to address: {patterns}",
        ]

        if few_shot_examples:
            sections.append("Few-shot examples from validated traces:")
            sections.extend(few_shot_examples)

        if retry_context:
            sections.append(retry_context)

        sections.extend(
            [
                "Source file:",
                "---",
                source_content,
                "---",
                "Return ONLY the complete converted Python 3 file.",
            ]
        )

        return "\n\n".join(sections)

    def _count_diff_lines(self, before: str, after: str, file_key: str) -> int:
        diff = difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile=f"a/{file_key}",
            tofile=f"b/{file_key}",
            lineterm="",
        )

        count = 0
        for line in diff:
            if (
                line.startswith("+++")
                or line.startswith("---")
                or line.startswith("@@")
            ):
                continue
            if line.startswith("+") or line.startswith("-"):
                count += 1
        return count

    def _validate_python_syntax(self, source_code: str, file_key: str) -> str | None:
        try:
            ast.parse(source_code, filename=file_key)
        except SyntaxError as exc:
            line = exc.lineno if exc.lineno is not None else "?"
            column = exc.offset if exc.offset is not None else "?"
            message = exc.msg if exc.msg else "invalid syntax"
            return f"{message} (line {line}, column {column})"
        return None

    def _build_syntax_repair_prompt(
        self,
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

    def _line_count(self, source_content: str) -> int:
        if not source_content:
            return 0
        return source_content.count("\n") + 1

    def _syntax_gate_config(self) -> dict[str, Any]:
        config = self.config.get("transformer", {}).get("syntax_gate", {})
        return {
            "enabled": bool(config.get("enabled", True)),
            "repair_attempts_max": int(config.get("repair_attempts_max", 2)),
        }

    def _large_file_config(self) -> dict[str, Any]:
        config = self.config.get("transformer", {}).get("large_file", {})
        return {
            "line_threshold": int(config.get("line_threshold", 250)),
            "max_few_shot_examples": int(config.get("max_few_shot_examples", 0)),
            "max_retry_issues": int(config.get("max_retry_issues", 2)),
        }
