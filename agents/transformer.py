"""Transformer agent: converts Python 2 files to Python 3 using LLM guidance."""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from .base_agent import BaseAgent


class Transformer(BaseAgent):
    """Consume task pheromones and produce transformed Python 3 files."""

    def perceive(self) -> dict[str, Any]:
        pending_entries = self.store.query("status", status="pending")
        threshold_config = self.config.get("thresholds", {})
        pheromone_config = self.config.get("pheromones", {})

        intensity_min = float(threshold_config.get("transformer_intensity_min", 0.2))
        inhibition_threshold = float(pheromone_config.get("inhibition_threshold", 0.1))

        candidates: list[dict[str, Any]] = []
        for file_key, status_entry in pending_entries.items():
            task_entry = self.store.read_one("tasks", file_key)
            if not task_entry:
                continue

            intensity = float(task_entry.get("intensity", 0.0))
            inhibition = float(status_entry.get("inhibition", 0.0))
            if intensity <= intensity_min:
                continue
            if inhibition >= inhibition_threshold:
                continue

            candidates.append(
                {
                    "file_key": file_key,
                    "intensity": intensity,
                    "inhibition": inhibition,
                    "status_entry": status_entry,
                    "task_entry": task_entry,
                }
            )

        candidates.sort(key=lambda item: (-item["intensity"], item["file_key"]))
        return {"candidates": candidates}

    def should_act(self, perception: dict[str, Any]) -> bool:
        return bool(perception.get("candidates"))

    def decide(self, perception: dict[str, Any]) -> dict[str, Any]:
        candidate = perception["candidates"][0]
        file_key = candidate["file_key"]
        file_path = self.target_repo_path / file_key
        source_content = file_path.read_text(encoding="utf-8", errors="ignore")

        patterns = list(candidate["task_entry"].get("patterns_found", []))
        few_shot_examples = self._collect_few_shot_examples(
            target_patterns=patterns,
            target_file_key=file_key,
        )
        retry_context = self._build_retry_context(
            file_key=file_key, status_entry=candidate["status_entry"]
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

            llm_response = self.llm_client.call(
                prompt=action["prompt"],
                system=action["system_prompt"],
            )
            transformed_content = self.llm_client.extract_code_block(
                llm_response.content
            )
            if not transformed_content.strip():
                raise ValueError("LLM returned empty transformed content")

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
                "tokens_used": llm_response.tokens_used,
                "latency_ms": llm_response.latency_ms,
                "diff_lines": diff_lines,
                "patterns": action["patterns"],
                "retry_count": int(status_entry.get("retry_count", 0)),
                "inhibition": float(status_entry.get("inhibition", 0.0)),
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "success": False,
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
    ) -> list[str]:
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

            if len(examples) >= 3:
                break

        return examples

    def _build_retry_context(self, file_key: str, status_entry: dict[str, Any]) -> str:
        if int(status_entry.get("retry_count", 0)) <= 0:
            return ""

        quality_entry = self.store.read_one("quality", file_key) or {}
        issues = quality_entry.get("issues", [])
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
