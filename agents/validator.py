"""Validator agent: final decisioning with git commit/revert/escalation."""

from __future__ import annotations

from typing import Any

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

from .base_agent import BaseAgent
from .capabilities.validate import validate_file


class Validator(BaseAgent):
    """Validate tested files using confidence thresholds and git operations."""

    def perceive(self) -> dict[str, Any]:
        tested_entries = self.store.query("status", status="tested")
        candidates = sorted(tested_entries.keys())
        return {"candidates": candidates, "status_entries": tested_entries}

    def should_act(self, perception: dict[str, Any]) -> bool:
        return bool(perception.get("candidates"))

    def decide(self, perception: dict[str, Any]) -> dict[str, Any]:
        file_key = perception["candidates"][0]
        quality_entry = self.store.read_one("quality", file_key) or {}
        status_entry = perception["status_entries"][file_key]

        return {
            "file_key": file_key,
            "quality_entry": quality_entry,
            "status_entry": status_entry,
        }

    def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        return validate_file(
            store=self.store,
            repo_path=self.target_repo_path,
            file_key=action["file_key"],
            config=self.config,
            dry_run=self._is_dry_run(),
            agent_name=self.name,
            quality_entry=action["quality_entry"],
            status_entry=action["status_entry"],
            commit_file=self._commit_file,
            rollback_file=self._rollback_file,
        )

    def deposit(self, result: dict[str, Any]) -> None:
        file_key = result["file_key"]

        if not result.get("success"):
            self.store.update(
                "status",
                file_key=file_key,
                agent_id=self.name,
                status="failed",
                previous_status="tested",
                retry_count=int(result.get("retry_count", 0)),
                inhibition=float(result.get("inhibition", 0.0)),
                metadata={"error": result.get("error", "validator failure")},
            )
            return

        self.store.update(
            "quality",
            file_key=file_key,
            agent_id=self.name,
            confidence=float(result.get("updated_confidence", 0.0)),
        )

        self.store.update(
            "status",
            file_key=file_key,
            agent_id=self.name,
            status=result["status"],
            previous_status="tested",
            retry_count=int(result.get("retry_count", 0)),
            inhibition=float(result.get("inhibition", 0.0)),
            metadata=result.get("decision_metadata", {}),
        )

    def _commit_file(self, file_key: str, confidence: float) -> None:
        repo = self._open_repo()
        repo.git.add(file_key)

        has_staged_changes = bool(repo.index.diff("HEAD"))
        if not has_staged_changes:
            return

        message = (
            f"[stigmergic] Migrate {file_key} to Python 3 (confidence={confidence:.2f})"
        )
        repo.index.commit(message)

    def _rollback_file(self, file_key: str) -> None:
        repo = self._open_repo()
        repo.git.checkout("HEAD", "--", file_key)

    def _open_repo(self) -> Repo:
        try:
            return Repo(self.target_repo_path, search_parent_directories=True)
        except InvalidGitRepositoryError as exc:
            raise RuntimeError(
                f"No git repository found at {self.target_repo_path}"
            ) from exc
        except GitCommandError as exc:
            raise RuntimeError(f"Failed to access git repo: {exc}") from exc

    def _is_dry_run(self) -> bool:
        return bool(self.config.get("runtime", {}).get("dry_run", False))
