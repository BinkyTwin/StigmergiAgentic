from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def _scan_for_legacy_imports(root: Path) -> list[str]:
    forbidden_modules = {"core", "adapters"}
    violations: list[str] = []

    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in forbidden_modules:
                        violations.append(f"{path.name}: import {alias.name}")
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] in forbidden_modules:
                    violations.append(f"{path.name}: from {node.module}")

    return violations


def test_core_v10_does_not_import_legacy_core_or_adapters() -> None:
    assert _scan_for_legacy_imports(REPO_ROOT / "core_v10") == []


def test_adapters_v10_does_not_import_legacy_core_or_adapters() -> None:
    assert _scan_for_legacy_imports(REPO_ROOT / "adapters_v10") == []
