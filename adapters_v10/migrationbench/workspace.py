"""Isolated repository workspace and patch helpers for V10 MigrationBench.

Adapter-owned workspace abstraction. The runtime in ``core_v10`` only sees a
``WorkspaceHandle``; concrete clone, branch isolation, edit application, and
patch export logic stays here.

Differences from the legacy ``adapters/migrationbench/workspace.py``:

- no inheritance from ``adapters.base.Workspace`` (cloison étanche);
- no Maven invocation (moved to ``maven.py``);
- no ``verify_patch_applies`` (moved to ``verifier.py`` as part of the strict
  finalize chain);
- ``apply_typed_edits`` returns a local lightweight ``EditApplicationResult``
  rather than the legacy V7-coupled schema;
- exposes :meth:`as_handle` to bridge to ``core_v10.WorkspaceHandle``.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from core_v10.contracts import WorkspaceHandle

from adapters_v10.migrationbench.context import migration_context_from_instance
from adapters_v10.migrationbench._runtime import CommandResult, run_command
from adapters_v10.migrationbench.schemas import (
    MigrationBenchInstance,
    PatchStats,
    TypedEdit,
    TypedEditSet,
)


class WorkspaceError(RuntimeError):
    """Raised when workspace setup or patch handling fails."""


_COPY_IGNORE_NAMES: tuple[str, ...] = (
    "target",
    "build",
    "out",
    ".gradle",
    ".idea",
    ".DS_Store",
)
"""Generated workspace paths that must not be duplicated between branches."""


_BUILD_OUTPUT_DIRS: frozenset[str] = frozenset({"target", "build", "out", ".gradle"})
"""Directory names removed after Maven verification."""


@dataclass(slots=True)
class EditApplicationResult:
    """Outcome of applying a :class:`TypedEditSet` to a workspace."""

    applied: bool
    failure_reason: str = "ok"
    files_modified: list[str] = field(default_factory=list)
    replacements: dict[str, int] = field(default_factory=dict)


class MigrationBenchWorkspaceV10:
    """Isolated clean checkout for one MigrationBench instance under V10.

    A workspace owns one local clone of the target repository pinned at
    ``instance.base_commit``. Concurrent patch attempts get their own
    isolated branch workspace via :meth:`branch_workspace`; nested repair
    chains use :meth:`fork_branch_workspace` to copy from another branch.
    """

    def __init__(
        self,
        *,
        instance: MigrationBenchInstance,
        root_dir: str | Path,
        timeout_seconds: float = 600.0,
    ) -> None:
        self.instance = instance
        self.root_dir = Path(root_dir).expanduser().resolve()
        self.repo_dir = self.root_dir / "repo"
        self.timeout_seconds = float(timeout_seconds)

    # ----- handle bridge ------------------------------------------------

    def as_handle(self, **extra_metadata: object) -> WorkspaceHandle:
        """Return the ``core_v10`` opaque workspace handle for this branch."""

        metadata: dict[str, object] = {
            "repo_url": self.instance.repo_url,
            "base_commit": self.instance.base_commit,
            "target_java": int(self.instance.target_java),
            "repo_dir": str(self.repo_dir),
            "migration_context": migration_context_from_instance(self.instance).to_dict(),
        }
        metadata.update(extra_metadata)
        return WorkspaceHandle(
            root=self.root_dir,
            instance_id=self.instance.instance_id,
            metadata=metadata,
        )

    # ----- clone / branching --------------------------------------------

    def prepare(self, *, force: bool = False) -> None:
        """Clone the repository (if needed) and checkout the base commit."""

        if force and self.root_dir.exists():
            shutil.rmtree(self.root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        if self.repo_dir.exists():
            return

        clone = run_command(
            ["git", "clone", self.instance.repo_url, str(self.repo_dir)],
            timeout_seconds=self.timeout_seconds,
        )
        if not clone.ok:
            raise WorkspaceError(
                f"git clone failed for {self.instance.repo_url}: "
                f"{clone.stderr[-2000:]}"
            )
        self.checkout_base()

    def checkout_base(self) -> None:
        """Reset the repository to the registered base commit."""

        result = run_command(
            ["git", "checkout", self.instance.base_commit],
            cwd=self.repo_dir,
            timeout_seconds=self.timeout_seconds,
        )
        if not result.ok:
            raise WorkspaceError(
                f"git checkout failed for {self.instance.base_commit}: "
                f"{result.stderr[-2000:]}"
            )
        run_command(["git", "reset", "--hard"], cwd=self.repo_dir, timeout_seconds=60)
        run_command(["git", "clean", "-fdx"], cwd=self.repo_dir, timeout_seconds=60)

    def branch_workspace(
        self,
        branch_id: str,
        *,
        force: bool = False,
    ) -> "MigrationBenchWorkspaceV10":
        """Create an isolated candidate workspace from the base checkout."""

        self.prepare(force=False)
        branch_root = self.root_dir / "branches" / self._safe_branch_id(branch_id)
        if force and branch_root.exists():
            shutil.rmtree(branch_root)
        branch = MigrationBenchWorkspaceV10(
            instance=self.instance,
            root_dir=branch_root,
            timeout_seconds=self.timeout_seconds,
        )
        if not branch.repo_dir.exists():
            branch_root.mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                self.repo_dir,
                branch.repo_dir,
                ignore=shutil.ignore_patterns(*_COPY_IGNORE_NAMES),
            )
            branch.checkout_base()
        return branch

    def fork_branch_workspace(
        self,
        *,
        source_branch_id: str,
        branch_id: str,
        force: bool = False,
    ) -> "MigrationBenchWorkspaceV10":
        """Fork one candidate workspace from another candidate branch."""

        source = self.branch_workspace(source_branch_id, force=False)
        branch_root = self.root_dir / "branches" / self._safe_branch_id(branch_id)
        if force and branch_root.exists():
            shutil.rmtree(branch_root)
        branch = MigrationBenchWorkspaceV10(
            instance=self.instance,
            root_dir=branch_root,
            timeout_seconds=self.timeout_seconds,
        )
        if not branch.repo_dir.exists():
            branch_root.mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                source.repo_dir,
                branch.repo_dir,
                ignore=shutil.ignore_patterns(*_COPY_IGNORE_NAMES),
            )
        return branch

    def cleanup_build_outputs(self) -> list[str]:
        """Remove generated Maven/build directories from this workspace.

        Verification may leave large ``target/`` trees behind. Those trees are
        never part of the patch contract and copying them into repair branches
        can exhaust file descriptors on long budgeted campaigns. The cleanup is
        conservative: it never descends into ``.git`` and only removes common
        generated directory names.
        """

        if not self.repo_dir.exists():
            return []

        removed: list[str] = []
        for current, dirs, _files in os.walk(self.repo_dir):
            dirs[:] = [name for name in dirs if name != ".git"]
            for name in list(dirs):
                if name not in _BUILD_OUTPUT_DIRS:
                    continue
                path = Path(current) / name
                try:
                    rel = path.relative_to(self.repo_dir).as_posix()
                except ValueError:
                    rel = str(path)
                shutil.rmtree(path, ignore_errors=True)
                removed.append(rel)
                dirs.remove(name)
        return sorted(removed)

    # ----- file IO -------------------------------------------------------

    def read_file(self, rel_path: str, *, max_bytes: int = 120_000) -> str:
        path = self._safe_path(rel_path)
        if not path.exists() or not path.is_file():
            raise WorkspaceError(f"File not found: {rel_path}")
        data = path.read_bytes()
        if len(data) > int(max_bytes):
            data = data[: int(max_bytes)]
        return data.decode("utf-8", errors="replace")

    def write_file(self, rel_path: str, content: str) -> None:
        path = self._safe_path(rel_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(content), encoding="utf-8")

    def list_targets(self) -> list[str]:
        """Return Maven and Java sources useful for migration prompts."""

        if not self.repo_dir.exists():
            return []
        targets: list[str] = []
        for pattern in ("pom.xml", "**/pom.xml", "**/*.java"):
            for path in self.repo_dir.glob(pattern):
                if path.is_file():
                    rel = path.relative_to(self.repo_dir).as_posix()
                    if rel not in targets:
                        targets.append(rel)
        return sorted(targets)[:250]

    # ----- typed edits ---------------------------------------------------

    def apply_typed_edits(
        self, edits: TypedEditSet | list[TypedEdit]
    ) -> EditApplicationResult:
        """Apply typed edits and fail loudly on mismatched search/replace."""

        edit_list = edits.edits if isinstance(edits, TypedEditSet) else list(edits)
        files_modified: set[str] = set()
        replacements: dict[str, int] = {}
        try:
            for edit in edit_list:
                if edit.type == "write_file":
                    self.write_file(edit.path, edit.content or "")
                    files_modified.add(edit.path)
                    continue

                current = self.read_file(edit.path, max_bytes=20_000_000)
                old = edit.old or ""
                count = current.count(old)
                replacements[edit.path] = count
                expected = int(edit.expected_replacements)
                if not edit.allow_multiple and count != expected:
                    return EditApplicationResult(
                        applied=False,
                        failure_reason=(
                            "replacement_count_mismatch:"
                            f"{edit.path}:expected={expected}:actual={count}"
                        ),
                        files_modified=sorted(files_modified),
                        replacements=replacements,
                    )
                if edit.allow_multiple and count < expected:
                    return EditApplicationResult(
                        applied=False,
                        failure_reason=(
                            "replacement_count_too_low:"
                            f"{edit.path}:expected>={expected}:actual={count}"
                        ),
                        files_modified=sorted(files_modified),
                        replacements=replacements,
                    )
                updated = current.replace(old, edit.new or "")
                self.write_file(edit.path, updated)
                files_modified.add(edit.path)
        except WorkspaceError as exc:
            return EditApplicationResult(
                applied=False,
                failure_reason=f"edit_application_error:WorkspaceError:{exc}",
                files_modified=sorted(files_modified),
                replacements=replacements,
            )

        return EditApplicationResult(
            applied=True,
            failure_reason="ok",
            files_modified=sorted(files_modified),
            replacements=replacements,
        )

    # ----- patch export --------------------------------------------------

    def export_patch(self, patch_path: str | Path) -> PatchStats:
        """Export ``git diff --binary`` to the requested artifact path."""

        patch_path = Path(patch_path)
        patch_path.parent.mkdir(parents=True, exist_ok=True)
        result = run_command(["git", "diff", "--binary"], cwd=self.repo_dir)
        patch_text = result.stdout if result.ok else ""
        patch_path.write_text(patch_text, encoding="utf-8")
        return self.patch_stats(patch_text)

    def patch_stats(self, patch_text: str | None = None) -> PatchStats:
        """Compute lightweight patch delivery statistics."""

        if patch_text is None:
            result = run_command(["git", "diff", "--binary"], cwd=self.repo_dir)
            patch_text = result.stdout if result.ok else ""
        lines = patch_text.splitlines()
        files = {
            line.split(" b/", 1)[-1]
            for line in lines
            if line.startswith("diff --git ")
        }
        added = sum(
            1
            for line in lines
            if line.startswith("+") and not line.startswith("+++")
        )
        deleted = sum(
            1
            for line in lines
            if line.startswith("-") and not line.startswith("---")
        )
        return PatchStats(
            patch_delivered=bool(str(patch_text).strip()),
            patch_lines_added=added,
            patch_lines_deleted=deleted,
            files_modified_count=len(files),
        )

    # ----- helpers -------------------------------------------------------

    def _safe_path(self, rel_path: str) -> Path:
        rel = str(rel_path).strip().replace("\\", "/")
        candidate = (self.repo_dir / rel).resolve()
        try:
            candidate.relative_to(self.repo_dir.resolve())
        except ValueError as exc:
            raise WorkspaceError(f"Path escapes repository: {rel_path}") from exc
        return candidate

    @staticmethod
    def _safe_branch_id(branch_id: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(branch_id).strip())
        return cleaned.strip("._") or "branch"


__all__ = [
    "CommandResult",
    "EditApplicationResult",
    "MigrationBenchWorkspaceV10",
    "WorkspaceError",
    "run_command",
]
