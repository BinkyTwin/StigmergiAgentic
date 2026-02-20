"""Scout agent: discovers migration tasks and deposits task pheromones."""

from __future__ import annotations

import logging
from typing import Any

from .base_agent import BaseAgent
from .capabilities.discover import (
    discover_candidate_files,
    discover_files,
    normalize_discovered_entries,
)

LOGGER = logging.getLogger(__name__)


class Scout(BaseAgent):
    """Analyze candidate files and deposit prioritized migration tasks."""

    def perceive(self) -> dict[str, Any]:
        tasks = self.store.read_all("tasks")
        status = self.store.read_all("status")
        all_file_keys = discover_candidate_files(self.target_repo_path, self.config)

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
        analyses = discover_files(
            store=self.store,
            repo_path=self.target_repo_path,
            llm_client=self.llm_client,
            config=self.config,
            agent_name=self.name,
            candidate_files=list(perception.get("candidate_files", [])),
            all_file_keys=list(perception.get("all_file_keys", [])),
            build_system_prompt=self._build_system_prompt,
            logger=LOGGER,
        )
        return {"analyses": analyses}

    def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        analyses = list(action.get("analyses", []))
        entries = normalize_discovered_entries(analyses=analyses, config=self.config)
        return {"entries": entries}

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
                "file_kind": entry.get("file_kind", "python"),
                "file_extension": entry.get("file_extension", ""),
            }
            if entry.get("llm_complexity_score") is not None:
                task_payload["llm_complexity_score"] = entry["llm_complexity_score"]

            self.store.write(
                "tasks",
                file_key=file_key,
                data=task_payload,
                agent_id=self.name,
            )

            status_payload = {
                "status": "pending",
                "retry_count": 0,
                "inhibition": 0.0,
                "metadata": {
                    "patterns_found": entry["patterns_found"],
                    "file_kind": entry.get("file_kind", "python"),
                },
            }
            self.store.write(
                "status",
                file_key=file_key,
                data=status_payload,
                agent_id=self.name,
            )
