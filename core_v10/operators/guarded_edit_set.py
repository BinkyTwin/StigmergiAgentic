"""Workspace-backed guards for free-form edit sets.

The guard is intentionally independent from providers. Providers may show the
LLM truncated files, but strategy runners must validate candidate edits against
the real adapter workspace before handing them to the apply layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from core_v10.contracts import JsonDict


@dataclass(frozen=True)
class GuardedEditIssue:
    """One rejected edit with enough context for EventLog audits."""

    index: int
    path: str
    reason: str
    expected_replacements: int | None = None
    actual_replacements: int | None = None
    edit_type: str | None = None

    def to_dict(self) -> JsonDict:
        return {
            "index": int(self.index),
            "path": self.path,
            "reason": self.reason,
            "expected_replacements": self.expected_replacements,
            "actual_replacements": self.actual_replacements,
            "edit_type": self.edit_type,
        }


@dataclass(frozen=True)
class GuardedEditSetResult:
    """Result of validating an edit set against a concrete workspace."""

    ok: bool
    issues: tuple[GuardedEditIssue, ...] = field(default_factory=tuple)
    checked_edit_count: int = 0

    def to_dict(self) -> JsonDict:
        return {
            "ok": bool(self.ok),
            "checked_edit_count": int(self.checked_edit_count),
            "issues": [issue.to_dict() for issue in self.issues],
        }


def validate_edit_set_against_workspace(
    edit_set: Any,
    workspace: Any,
) -> GuardedEditSetResult:
    """Validate a TypedEditSet-like payload against the real workspace.

    Checks are deliberately strict for ``replace_text`` because a missing
    ``old`` span otherwise reaches the adapter as ``replacement_count_too_low``
    and wastes a benchmark validation slot.
    """

    raw = edit_set if isinstance(edit_set, dict) else {}
    edits = raw.get("edits")
    if not isinstance(edits, list):
        return GuardedEditSetResult(
            ok=False,
            issues=(
                GuardedEditIssue(
                    index=-1,
                    path="",
                    reason="edit_set_missing_edits",
                ),
            ),
            checked_edit_count=0,
        )

    issues: list[GuardedEditIssue] = []
    file_cache: dict[str, str] = {}
    for index, item in enumerate(edits):
        if not isinstance(item, dict):
            issues.append(
                GuardedEditIssue(index=index, path="", reason="edit_not_object")
            )
            continue
        edit_type = str(item.get("type") or "")
        raw_path = str(item.get("path") or "")
        safe_path = _safe_relative_path(raw_path)
        if safe_path is None:
            issues.append(
                GuardedEditIssue(
                    index=index,
                    path=raw_path,
                    reason="unsafe_path",
                    edit_type=edit_type,
                )
            )
            continue
        justification = _justification_for(raw, item)
        if _is_test_path(safe_path) and not _has_test_justification(justification):
            issues.append(
                GuardedEditIssue(
                    index=index,
                    path=safe_path,
                    reason="test_modification_without_justification",
                    edit_type=edit_type,
                )
            )
            continue

        if edit_type == "replace_text":
            old = item.get("old")
            if not isinstance(old, str) or not old:
                issues.append(
                    GuardedEditIssue(
                        index=index,
                        path=safe_path,
                        reason="old_span_empty",
                        edit_type=edit_type,
                    )
                )
                continue
            if safe_path in file_cache:
                text = file_cache[safe_path]
            else:
                text = _read_workspace_file(workspace, safe_path)
            if text is None:
                issues.append(
                    GuardedEditIssue(
                        index=index,
                        path=safe_path,
                        reason="path_not_found",
                        edit_type=edit_type,
                    )
                )
                continue
            expected = _expected_replacements(item.get("expected_replacements"))
            if expected is None or expected <= 0:
                issues.append(
                    GuardedEditIssue(
                        index=index,
                        path=safe_path,
                        reason="expected_replacements_invalid",
                        expected_replacements=expected,
                        edit_type=edit_type,
                    )
                )
                continue
            actual = text.count(old)
            allow_multiple = bool(item.get("allow_multiple", False))
            ok_count = actual >= expected if allow_multiple else actual == expected
            if not ok_count:
                issues.append(
                    GuardedEditIssue(
                        index=index,
                        path=safe_path,
                        reason=(
                            "old_span_absent"
                            if actual == 0
                            else "replacement_count_mismatch"
                        ),
                        expected_replacements=expected,
                        actual_replacements=actual,
                        edit_type=edit_type,
                    )
                )
                continue
            file_cache[safe_path] = text.replace(old, str(item.get("new") or ""))
        elif edit_type == "write_file":
            parent = _resolve_workspace_path(workspace, safe_path)
            if parent is None or not parent.parent.exists():
                issues.append(
                    GuardedEditIssue(
                        index=index,
                        path=safe_path,
                        reason="parent_path_not_found",
                        edit_type=edit_type,
                    )
                )
                continue
            file_cache[safe_path] = str(item.get("content") or "")
        else:
            issues.append(
                GuardedEditIssue(
                    index=index,
                    path=safe_path,
                    reason="unsupported_edit_type",
                    edit_type=edit_type,
                )
            )

    return GuardedEditSetResult(
        ok=not issues,
        issues=tuple(issues),
        checked_edit_count=len(edits),
    )


def _safe_relative_path(raw_path: str) -> str | None:
    path = raw_path.strip().replace("\\", "/")
    if not path:
        return None
    posix = PurePosixPath(path)
    if posix.is_absolute():
        return None
    if any(part in {"", ".", ".."} for part in posix.parts):
        return None
    return str(posix)


def _expected_replacements(raw: Any) -> int | None:
    if raw is None:
        return 1
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _justification_for(edit_set: dict[str, Any], edit: dict[str, Any]) -> str:
    return "\n".join(
        str(value)
        for value in (
            edit.get("justification"),
            edit.get("rationale"),
            edit_set.get("justification"),
            edit_set.get("rationale"),
        )
        if value
    ).lower()


def _is_test_path(path: str) -> bool:
    lowered = path.lower()
    parts = lowered.split("/")
    return (
        "test" in parts
        or lowered.startswith("src/test/")
        or lowered.endswith("test.java")
        or "/test/" in lowered
    )


def _has_test_justification(text: str) -> bool:
    if "test" not in text:
        return False
    return any(
        token in text
        for token in (
            "compile",
            "migration",
            "preserve",
            "fix",
            "justification",
        )
    )


def _read_workspace_file(workspace: Any, rel_path: str) -> str | None:
    if hasattr(workspace, "read_file"):
        try:
            return str(workspace.read_file(rel_path, max_bytes=2_000_000))
        except Exception:  # noqa: BLE001
            return None
    path = _resolve_workspace_path(workspace, rel_path)
    if path is None or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return None


def _resolve_workspace_path(workspace: Any, rel_path: str) -> Path | None:
    roots: list[Path] = []
    metadata = getattr(workspace, "metadata", None)
    if isinstance(metadata, dict):
        repo_dir = metadata.get("repo_dir")
        if repo_dir:
            roots.append(Path(repo_dir))
    root = getattr(workspace, "root", None)
    if root is not None:
        root_path = Path(root)
        roots.append(root_path / "repo")
        roots.append(root_path)
    for base in roots:
        path = base / rel_path
        if path.exists() or path.parent.exists():
            return path
    return roots[0] / rel_path if roots else None


__all__ = [
    "GuardedEditIssue",
    "GuardedEditSetResult",
    "validate_edit_set_against_workspace",
]
