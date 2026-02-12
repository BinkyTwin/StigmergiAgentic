"""Validator agent: final decisioning with git commit/revert/escalation."""

from __future__ import annotations

from typing import Any

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

from .base_agent import BaseAgent


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
        file_key = action["file_key"]
        quality_entry = action["quality_entry"]
        status_entry = action["status_entry"]
        dry_run = self._is_dry_run()

        confidence = float(quality_entry.get("confidence", 0.0))
        thresholds = self.config.get("thresholds", {})
        high = float(thresholds.get("validator_confidence_high", 0.8))
        low = float(thresholds.get("validator_confidence_low", 0.5))
        max_retry_count = int(thresholds.get("max_retry_count", 3))

        retry_count = int(status_entry.get("retry_count", 0))
        inhibition = float(status_entry.get("inhibition", 0.0))

        try:
            if confidence >= high:
                updated_confidence = min(1.0, confidence + 0.1)
                if not dry_run:
                    self._commit_file(file_key=file_key, confidence=updated_confidence)
                return {
                    "success": True,
                    "file_key": file_key,
                    "status": "validated",
                    "updated_confidence": updated_confidence,
                    "retry_count": retry_count,
                    "inhibition": inhibition,
                    "decision_metadata": {
                        "decision": "auto_validate",
                        "dry_run": dry_run,
                    },
                }

            if confidence >= low:
                return {
                    "success": True,
                    "file_key": file_key,
                    "status": "needs_review",
                    "updated_confidence": confidence,
                    "retry_count": retry_count,
                    "inhibition": inhibition,
                    "decision_metadata": {
                        "decision": "human_escalation",
                        "dry_run": dry_run,
                    },
                }

            updated_confidence = max(0.0, confidence - 0.2)
            if not dry_run:
                self._rollback_file(file_key=file_key)

            next_retry_count = retry_count + 1
            next_status = "retry" if next_retry_count <= max_retry_count else "skipped"
            next_inhibition = inhibition + 0.5 if next_status == "retry" else inhibition

            return {
                "success": True,
                "file_key": file_key,
                "status": next_status,
                "updated_confidence": updated_confidence,
                "retry_count": next_retry_count,
                "inhibition": next_inhibition,
                "decision_metadata": {
                    "decision": "rollback",
                    "max_retry_count": max_retry_count,
                    "dry_run": dry_run,
                },
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "success": False,
                "file_key": file_key,
                "error": str(exc),
                "retry_count": retry_count,
                "inhibition": inhibition,
            }

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
