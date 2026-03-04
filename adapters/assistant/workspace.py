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

    def get_context_summary(self, max_depth: int = 3, max_files: int = 50) -> str:
        """Build a compact textual workspace summary for LLM grounding."""
        key_files = self._identify_key_files()
        tree = self._build_tree(self.root, max_depth=max_depth, max_files=max_files)

        snippets: list[str] = []
        for filename in ("README.md", "pyproject.toml", "requirements.txt", "Makefile"):
            content = self._read_if_exists(filename)
            if content:
                snippets.append(f"### {filename}\n{content}")

        key_files_section = "\n".join(f"- {name}" for name in key_files) or "- (none)"
        snippets_section = "\n\n".join(snippets) if snippets else "### Notes\n(no key file content)"

        return (
            f"# Workspace Context\n"
            f"Root: {self.root}\n\n"
            f"## Key Files\n{key_files_section}\n\n"
            f"## Directory Tree\n```text\n{tree}\n```\n\n"
            f"{snippets_section}\n"
        )

    def _build_tree(self, root: Path, max_depth: int, max_files: int) -> str:
        lines = [f"{root.name}/"]
        file_count = 0

        def walk(path: Path, depth: int) -> None:
            nonlocal file_count
            if depth >= max_depth:
                return
            try:
                entries = sorted(
                    path.iterdir(),
                    key=lambda item: (item.is_file(), item.name.lower()),
                )
            except OSError:
                return

            for entry in entries:
                indent = "  " * (depth + 1)
                if entry.is_dir():
                    lines.append(f"{indent}{entry.name}/")
                    walk(entry, depth + 1)
                    continue

                if file_count >= max_files:
                    continue
                lines.append(f"{indent}{entry.name}")
                file_count += 1

        walk(root, 0)
        if file_count >= max_files:
            lines.append("  ... (truncated)")
        return "\n".join(lines)

    def _read_if_exists(self, filename: str, max_chars: int = 2000) -> str:
        path = self.root / filename
        if not path.exists() or not path.is_file():
            return ""
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ""

        normalized = content.strip()
        if len(normalized) <= max_chars:
            return normalized
        return normalized[:max_chars].rstrip() + "\n...(truncated)"

    def _identify_key_files(self) -> list[str]:
        candidates = [
            "setup.py",
            "pyproject.toml",
            "Makefile",
            "Dockerfile",
            "requirements.txt",
            "README.md",
        ]
        discovered: list[str] = []
        for name in candidates:
            path = self.root / name
            if path.exists() and path.is_file():
                discovered.append(name)
        return discovered
