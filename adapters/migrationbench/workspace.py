"""Workspace isolation and patch artifact helpers for MigrationBench."""

from __future__ import annotations

import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from adapters.base import Workspace

from .schemas import (
    EditApplicationResult,
    MigrationBenchInstance,
    PatchStats,
    TypedEdit,
    TypedEditSet,
)


@dataclass(slots=True)
class CommandResult:
    """Small subprocess result envelope with timing."""

    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    runtime_seconds: float

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run_command(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout_seconds: float | None = None,
) -> CommandResult:
    """Run one command and capture stdout/stderr without raising."""
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
        return CommandResult(
            command=command,
            returncode=int(completed.returncode),
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            runtime_seconds=time.perf_counter() - started,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return CommandResult(
            command=command,
            returncode=124,
            stdout=stdout,
            stderr=stderr + f"\nTimed out after {timeout_seconds} seconds.",
            runtime_seconds=time.perf_counter() - started,
        )


class WorkspaceError(RuntimeError):
    """Raised when workspace setup or patch handling fails."""


class MigrationBenchWorkspace(Workspace):
    """Isolated clean checkout for one `(framework, instance, seed)` run."""

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

    def branch_workspace(
        self,
        branch_id: str,
        *,
        force: bool = False,
    ) -> "MigrationBenchWorkspace":
        """Create a clean candidate workspace from the base checkout."""
        self.prepare(force=False)
        branch_root = self.root_dir / "branches" / self._safe_branch_id(branch_id)
        if force and branch_root.exists():
            shutil.rmtree(branch_root)
        branch = MigrationBenchWorkspace(
            instance=self.instance,
            root_dir=branch_root,
            timeout_seconds=self.timeout_seconds,
        )
        if not branch.repo_dir.exists():
            branch_root.mkdir(parents=True, exist_ok=True)
            shutil.copytree(self.repo_dir, branch.repo_dir)
            branch.checkout_base()
        return branch

    def fork_branch_workspace(
        self,
        *,
        source_branch_id: str,
        branch_id: str,
        force: bool = False,
    ) -> "MigrationBenchWorkspace":
        """Fork one candidate workspace from another candidate branch."""
        source = self.branch_workspace(source_branch_id, force=False)
        branch_root = self.root_dir / "branches" / self._safe_branch_id(branch_id)
        if force and branch_root.exists():
            shutil.rmtree(branch_root)
        branch = MigrationBenchWorkspace(
            instance=self.instance,
            root_dir=branch_root,
            timeout_seconds=self.timeout_seconds,
        )
        if not branch.repo_dir.exists():
            branch_root.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source.repo_dir, branch.repo_dir)
        return branch

    def list_targets(self) -> list[str]:
        """List key repository files that are useful to migration agents."""
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

    def prepare(self, *, force: bool = False) -> None:
        """Clone/copy the repository and checkout the exact base commit."""
        if force and self.root_dir.exists():
            shutil.rmtree(self.root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        if self.repo_dir.exists():
            return

        clone_result = run_command(
            ["git", "clone", self.instance.repo_url, str(self.repo_dir)],
            timeout_seconds=self.timeout_seconds,
        )
        if not clone_result.ok:
            raise WorkspaceError(
                f"git clone failed for {self.instance.repo_url}: {clone_result.stderr[-2000:]}"
            )
        self.checkout_base()

    def checkout_base(self) -> None:
        """Reset repository to the registered base commit."""
        result = run_command(
            ["git", "checkout", self.instance.base_commit],
            cwd=self.repo_dir,
            timeout_seconds=self.timeout_seconds,
        )
        if not result.ok:
            raise WorkspaceError(
                f"git checkout failed for {self.instance.base_commit}: {result.stderr[-2000:]}"
            )
        run_command(["git", "reset", "--hard"], cwd=self.repo_dir, timeout_seconds=60)
        run_command(["git", "clean", "-fdx"], cwd=self.repo_dir, timeout_seconds=60)

    def read_file(self, rel_path: str, *, max_bytes: int = 120_000) -> str:
        """Read a repository-relative file with a defensive size cap."""
        path = self._safe_path(rel_path)
        if not path.exists() or not path.is_file():
            raise WorkspaceError(f"File not found: {rel_path}")
        data = path.read_bytes()
        if len(data) > int(max_bytes):
            data = data[: int(max_bytes)]
        return data.decode("utf-8", errors="replace")

    def write_file(self, rel_path: str, content: str) -> None:
        """Write a complete repository-relative file."""
        path = self._safe_path(rel_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(content), encoding="utf-8")

    def apply_typed_edits(self, edits: TypedEditSet | list[TypedEdit]) -> EditApplicationResult:
        """Apply typed edits and fail loudly on mismatched search/replace blocks."""
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
        except Exception as exc:  # noqa: BLE001
            return EditApplicationResult(
                applied=False,
                failure_reason=f"edit_application_error:{type(exc).__name__}:{exc}",
                files_modified=sorted(files_modified),
                replacements=replacements,
            )

        return EditApplicationResult(
            applied=True,
            failure_reason="ok",
            files_modified=sorted(files_modified),
            replacements=replacements,
        )

    def export_patch(self, patch_path: str | Path) -> PatchStats:
        """Export `git diff --binary` to the requested artifact path."""
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

    def verify_patch_applies(
        self,
        *,
        patch_path: str | Path,
        verification_root: str | Path,
        force: bool = True,
    ) -> tuple[bool, str]:
        """Apply-check the produced patch on a second fresh checkout."""
        patch_path = Path(patch_path).expanduser().resolve()
        if not patch_path.exists() or not patch_path.read_text(encoding="utf-8").strip():
            return False, "empty_patch"

        verification_root = Path(verification_root).expanduser().resolve()
        verify_workspace = MigrationBenchWorkspace(
            instance=self.instance,
            root_dir=verification_root,
            timeout_seconds=self.timeout_seconds,
        )
        try:
            verify_workspace.prepare(force=force)
        except Exception as exc:  # noqa: BLE001
            return False, f"verification_checkout_failed:{type(exc).__name__}:{exc}"

        check = run_command(
            ["git", "apply", "--check", str(patch_path)],
            cwd=verify_workspace.repo_dir,
            timeout_seconds=120,
        )
        if not check.ok:
            return False, f"git_apply_check_failed:{(check.stderr or check.stdout)[-1000:]}"
        apply = run_command(
            ["git", "apply", str(patch_path)],
            cwd=verify_workspace.repo_dir,
            timeout_seconds=120,
        )
        if not apply.ok:
            return False, f"git_apply_failed:{(apply.stderr or apply.stdout)[-1000:]}"
        return True, "ok"

    def run_maven(
        self,
        command: str = "mvn clean verify",
        *,
        timeout_seconds: float | None = None,
    ) -> CommandResult:
        """Run a Maven command in the repository root."""
        timeout = self.timeout_seconds if timeout_seconds is None else timeout_seconds
        return run_command(["bash", "-lc", command], cwd=self.repo_dir, timeout_seconds=timeout)

    def summarize(self, *, max_files: int = 40, max_pom_bytes: int = 80_000) -> dict[str, Any]:
        """Return compact repository context for prompts and traces."""
        poms = [path for path in self.list_targets() if path.endswith("pom.xml")]
        java_files = [path for path in self.list_targets() if path.endswith(".java")]
        pom_snippets: dict[str, str] = {}
        for rel in poms[:8]:
            try:
                pom_snippets[rel] = self.read_file(rel, max_bytes=max_pom_bytes)
            except Exception:  # noqa: BLE001
                continue
        return {
            "instance_id": self.instance.instance_id,
            "repo_url": self.instance.repo_url,
            "base_commit": self.instance.base_commit,
            "target_java": self.instance.target_java,
            "migration_mode": self.instance.migration_mode,
            "pom_files": poms[:max_files],
            "java_files_sample": java_files[:max_files],
            "pom_snippets": pom_snippets,
            "stats": dict(self.instance.stats),
            "stratum": dict(self.instance.stratum),
        }

    def _safe_path(self, rel_path: str) -> Path:
        rel = str(rel_path).strip().replace("\\", "/")
        candidate = (self.repo_dir / rel).resolve()
        try:
            candidate.relative_to(self.repo_dir.resolve())
        except ValueError as exc:
            raise WorkspaceError(f"Path escapes repository: {rel_path}") from exc
        return candidate

    def _safe_branch_id(self, branch_id: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(branch_id).strip())
        return cleaned.strip("._") or "branch"
