"""Transformer agent: converts migration-target files using LLM guidance."""

from __future__ import annotations

from typing import Any

from .base_agent import BaseAgent
from .capabilities.transform import (
    TRANSFORMER_ROLE_PROMPT,
    build_retry_context,
    collect_few_shot_examples,
    select_transform_candidates,
    transform_file,
)


class Transformer(BaseAgent):
    """Consume task pheromones and produce transformed files."""

    def perceive(self) -> dict[str, Any]:
        candidates = select_transform_candidates(store=self.store, config=self.config)
        return {"candidates": candidates}

    def should_act(self, perception: dict[str, Any]) -> bool:
        return bool(perception.get("candidates"))

    def decide(self, perception: dict[str, Any]) -> dict[str, Any]:
        candidate = perception["candidates"][0]
        file_key = candidate["file_key"]
        file_path = self.target_repo_path / file_key
        source_content = file_path.read_text(encoding="utf-8", errors="ignore")
        task_entry = candidate.get("task_entry", {})
        file_kind = str(task_entry.get("file_kind", self._infer_file_kind(file_key)))

        line_count = self._line_count(source_content)
        patterns = list(task_entry.get("patterns_found", []))
        large_file_mode = False
        few_shot_examples: list[str] = []
        retry_context = ""

        if file_kind == "python":
            large_file_config = self._large_file_config()
            large_file_mode = line_count >= int(large_file_config["line_threshold"])
            max_few_shot_examples = (
                int(large_file_config["max_few_shot_examples"])
                if large_file_mode
                else 3
            )
            max_retry_issues = (
                int(large_file_config["max_retry_issues"]) if large_file_mode else None
            )
            few_shot_examples = collect_few_shot_examples(
                store=self.store,
                repo_path=self.target_repo_path,
                target_patterns=patterns,
                target_file_key=file_key,
                max_examples=max_few_shot_examples,
            )
            retry_context = build_retry_context(
                store=self.store,
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
            file_kind=file_kind,
        )

        return {
            "file_key": file_key,
            "file_path": file_path,
            "source_content": source_content,
            "patterns": patterns,
            "prompt": prompt,
            "system_prompt": self._build_system_prompt(TRANSFORMER_ROLE_PROMPT),
            "status_entry": candidate["status_entry"],
            "task_entry": task_entry,
            "line_count": line_count,
            "large_file_mode": large_file_mode,
            "file_kind": file_kind,
        }

    def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        return transform_file(
            store=self.store,
            repo_path=self.target_repo_path,
            llm_client=self.llm_client,
            file_key=action["file_key"],
            config=self.config,
            agent_name=self.name,
            status_entry=action["status_entry"],
            task_entry=action.get("task_entry", {}),
            source_content=action["source_content"],
            patterns=action["patterns"],
            prompt=action["prompt"],
            system_prompt=action["system_prompt"],
            large_file_mode=bool(action.get("large_file_mode", False)),
            file_kind=action.get("file_kind"),
        )

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
                    "file_kind": str(result.get("file_kind", "python")),
                    "transform_mode": str(
                        result.get("transform_mode", "python_syntax_gate")
                    ),
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
                    "file_kind": str(result.get("file_kind", "python")),
                    "transform_mode": str(
                        result.get("transform_mode", "python_syntax_gate")
                    ),
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
            metadata={
                "error": result.get("error", "unknown transformer error"),
                "file_kind": str(result.get("file_kind", "python")),
            },
        )

    def _build_prompt(
        self,
        file_key: str,
        source_content: str,
        patterns: list[str],
        few_shot_examples: list[str],
        retry_context: str,
        file_kind: str,
    ) -> str:
        if file_kind != "python":
            return "\n\n".join(
                [
                    "Update this text file so it matches a completed Python 3 migration.",
                    f"File: {file_key}",
                    f"Detected migration traces: {patterns}",
                    "Constraints:",
                    "- Keep content intent stable.",
                    "- Update Python 2 references to Python 3 conventions.",
                    "- Return ONLY the complete updated file, no explanations.",
                    "Source file:",
                    "---",
                    source_content,
                    "---",
                ]
            )

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

    def _infer_file_kind(self, file_key: str) -> str:
        return "python" if file_key.endswith(".py") else "text"
