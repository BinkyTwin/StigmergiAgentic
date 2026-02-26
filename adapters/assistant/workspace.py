"""Filesystem-rooted workspace for the generic assistant adapter."""

from __future__ import annotations

from pathlib import Path

from adapters.base import Workspace


class WorkspacePathError(ValueError):
    """Raised when a requested path escapes the workspace root."""


class LocalWorkspace(Workspace):
    """Workspace implementation constrained to one root directory."""

    def __init__(self, *, root: str | Path, max_file_size_bytes: int = 1_048_576) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_file_size_bytes = int(max_file_size_bytes)

    def list_targets(self) -> list[str]:
        targets: list[str] = []
        for path in self.root.rglob("*"):
            if path.is_file():
                targets.append(str(path.relative_to(self.root)))
        return sorted(targets)

    def resolve_path(self, path: str | Path) -> Path:
        raw = Path(path)
        candidate = raw if raw.is_absolute() else self.root / raw
        resolved = candidate.resolve()
        if resolved == self.root or self.root in resolved.parents:
            return resolved
        raise WorkspacePathError(f"path_outside_workspace:{path}")

    def read_text(self, *, path: str, max_bytes: int | None = None) -> str:
        resolved = self.resolve_path(path)
        if not resolved.exists():
            raise FileNotFoundError(f"missing_file:{path}")
        if not resolved.is_file():
            raise IsADirectoryError(f"not_a_file:{path}")

        raw = resolved.read_bytes()
        limit = self._effective_limit(max_bytes=max_bytes)
        if len(raw) > limit:
            raise ValueError(f"file_too_large:{len(raw)}>{limit}")
        return raw.decode("utf-8")

    def write_text(
        self,
        *,
        path: str,
        content: str,
        mode: str,
        max_bytes: int | None = None,
    ) -> int:
        resolved = self.resolve_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)

        mode_normalized = mode.strip().lower()
        if mode_normalized not in {"overwrite", "append"}:
            raise ValueError(f"unsupported_write_mode:{mode}")

        existing = ""
        if resolved.exists():
            existing = resolved.read_text(encoding="utf-8")

        if mode_normalized == "overwrite":
            final_content = content
        else:
            final_content = existing + content

        final_size = len(final_content.encode("utf-8"))
        limit = self._effective_limit(max_bytes=max_bytes)
        if final_size > limit:
            raise ValueError(f"file_too_large:{final_size}>{limit}")

        resolved.write_text(final_content, encoding="utf-8")
        return len(content.encode("utf-8"))

    def replace_text(
        self,
        *,
        path: str,
        old: str,
        new: str,
        count: int = -1,
        max_bytes: int | None = None,
    ) -> tuple[int, int]:
        if old == "":
            raise ValueError("replace_text_old_cannot_be_empty")

        source = self.read_text(path=path, max_bytes=max_bytes)
        replacements = source.count(old) if count < 0 else min(source.count(old), count)
        final_content = source.replace(old, new, count)

        final_size = len(final_content.encode("utf-8"))
        limit = self._effective_limit(max_bytes=max_bytes)
        if final_size > limit:
            raise ValueError(f"file_too_large:{final_size}>{limit}")

        resolved = self.resolve_path(path)
        resolved.write_text(final_content, encoding="utf-8")
        return replacements, final_size

    def _effective_limit(self, *, max_bytes: int | None) -> int:
        if max_bytes is None:
            return self.max_file_size_bytes
        return min(self.max_file_size_bytes, int(max_bytes))
