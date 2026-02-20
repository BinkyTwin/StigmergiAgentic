"""Validation capability for confidence-based commit/rollback decisions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError


def validate_file(
    store: Any,
    repo_path: str | Path,
    file_key: str,
    config: dict[str, Any],
    dry_run: bool,
    agent_name: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Validate one tested file and return validator execution payload."""

    del store, agent_name  # retained for API consistency

    quality_entry = kwargs.get("quality_entry", {}) or {}
    status_entry = kwargs.get("status_entry", {}) or {}

    confidence = float(quality_entry.get("confidence", 0.0))
    thresholds = config.get("thresholds", {})
    high = float(thresholds.get("validator_confidence_high", 0.8))
    low = float(thresholds.get("validator_confidence_low", 0.5))
    max_retry_count = int(thresholds.get("max_retry_count", 3))

    retry_count = int(status_entry.get("retry_count", 0))
    inhibition = float(status_entry.get("inhibition", 0.0))

    commit_file = kwargs.get("commit_file")
    rollback_file = kwargs.get("rollback_file")
    if not callable(commit_file):

        def commit_file(key: str, conf: float) -> None:  # type: ignore[no-redef]
            _commit_file(repo_path=repo_path, file_key=key, confidence=conf)

    if not callable(rollback_file):

        def rollback_file(key: str) -> None:  # type: ignore[no-redef]
            _rollback_file(repo_path=repo_path, file_key=key)

    try:
        if confidence >= high:
            updated_confidence = min(1.0, confidence + 0.1)
            if not dry_run:
                commit_file(file_key, updated_confidence)
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
            rollback_file(file_key)

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


def _commit_file(*, repo_path: str | Path, file_key: str, confidence: float) -> None:
    repo = _open_repo(repo_path)
    repo.git.add(file_key)
    has_staged_changes = bool(repo.index.diff("HEAD"))
    if not has_staged_changes:
        return
    message = (
        f"[stigmergic] Migrate {file_key} to Python 3 (confidence={confidence:.2f})"
    )
    repo.index.commit(message)


def _rollback_file(*, repo_path: str | Path, file_key: str) -> None:
    repo = _open_repo(repo_path)
    repo.git.checkout("HEAD", "--", file_key)


def _open_repo(repo_path: str | Path) -> Repo:
    try:
        return Repo(repo_path, search_parent_directories=True)
    except InvalidGitRepositoryError as exc:
        raise RuntimeError(f"No git repository found at {repo_path}") from exc
    except GitCommandError as exc:
        raise RuntimeError(f"Failed to access git repo: {exc}") from exc
