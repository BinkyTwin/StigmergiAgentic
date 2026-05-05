"""Maven invocation, build-output parsing, and failure taxonomy for V10.

These helpers are pure — they take repository paths and command outputs and
return parsed structures. The :class:`MigrationBenchVerifier` in
``verifier.py`` is the only entry point that orchestrates the full
``apply → build → official eval`` chain and emits the eight verifier signals.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from adapters_v10.migrationbench._runtime import CommandResult, run_command


_FAILURE_TAXONOMY_ORDER: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "pom_parse_error",
        ("non-parseable pom", "malformed pom", "modelparseexception"),
    ),
    (
        "dependency_resolution_error",
        (
            "could not resolve dependencies",
            "failed to collect dependencies",
            "could not find artifact",
            "dependency resolution",
            "dependencyresolutionexception",
        ),
    ),
    (
        "class_version_error",
        (
            "unsupported class file major version",
            "invalid target release",
            "release version",
            "source option",
            "target option",
        ),
    ),
    (
        "compile_error",
        (
            "compilation failure",
            "compilation error",
            "cannot find symbol",
            "package ",
            "does not exist",
            "maven-compiler-plugin",
        ),
    ),
    (
        "test_failure",
        ("there are test failures", "surefire", "tests run:", "test failure"),
    ),
)


def classify_maven_failure(text: str) -> str:
    """Classify Maven/build feedback into a reusable repair taxonomy.

    Returns one of ``pom_parse_error``, ``dependency_resolution_error``,
    ``class_version_error``, ``compile_error``, ``test_failure``,
    ``patch_apply_error`` or ``build_failure``.
    """

    lowered = str(text or "").lower()
    for label, tokens in _FAILURE_TAXONOMY_ORDER:
        if any(token in lowered for token in tokens):
            return label
    if "git_apply" in lowered or "patch does not apply" in lowered:
        return "patch_apply_error"
    return "build_failure"


def feedback_digest(text: str, *, max_chars: int = 12_000) -> str:
    """Extract Maven failure signal lines without download progress noise."""

    lines = [line.rstrip() for line in str(text or "").splitlines()]
    selected: list[str] = []

    for idx, line in enumerate(lines):
        lowered = line.lower()
        if "[error]" in lowered:
            selected.extend(lines[idx : min(len(lines), idx + 30)])
        if "caused by:" in lowered:
            selected.extend(lines[idx : min(len(lines), idx + 6)])
        if "tests run:" in lowered:
            selected.append(line)
        if "build failure" in lowered:
            selected.extend(lines[idx : min(len(lines), idx + 4)])

    if lines:
        selected.append(lines[-1])
    if not selected:
        cleaned = "\n".join(lines)
        return cleaned[-max(1, int(max_chars)) :]

    compact = "\n".join(dict.fromkeys(line for line in selected if line.strip()))
    return compact[-max(1, int(max_chars)) :]


def run_maven(
    repo_dir: Path,
    command: str = "mvn clean verify",
    *,
    timeout_seconds: float = 600.0,
) -> CommandResult:
    """Run a Maven command in the given repository root."""

    return run_command(
        ["bash", "-lc", command],
        cwd=Path(repo_dir),
        timeout_seconds=float(timeout_seconds),
    )


def surefire_test_count(repo_dir: Path) -> int | None:
    """Sum the ``tests`` attribute over Surefire ``TEST-*.xml`` reports."""

    repo_dir = Path(repo_dir)
    total = 0
    found = False
    for report in repo_dir.rglob("target/surefire-reports/TEST-*.xml"):
        try:
            root = ET.parse(report).getroot()
            total += int(float(root.attrib.get("tests", 0) or 0))
            found = True
        except (ET.ParseError, ValueError, OSError):
            continue
    return total if found else None


def required_test_count(stats: dict[str, object]) -> int | None:
    """Return the ``num_test_cases`` required by an instance, if available."""

    raw = dict(stats or {}).get("num_test_cases")
    try:
        value = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def class_major_versions_in_target(
    repo_dir: Path,
    *,
    timeout_seconds: float = 30.0,
    max_files: int = 2000,
) -> set[int]:
    """Return JVM ``major_version`` bytes for classes under ``target/classes``.

    Uses ``javap -verbose`` per class file (capped at ``max_files``). Returns
    an empty set when the repository has not been built yet.
    """

    repo_dir = Path(repo_dir)
    if not repo_dir.exists():
        return set()

    versions: set[int] = set()
    class_files = [
        path
        for path in repo_dir.rglob("target/classes/**/*.class")
        if path.is_file()
    ][: max(1, int(max_files))]

    for path in class_files:
        result = run_command(
            ["bash", "-lc", f"javap -verbose {json.dumps(str(path))} | grep 'major version:'"],
            cwd=repo_dir,
            timeout_seconds=float(timeout_seconds),
        )
        match = re.search(r"major version:\s*(\d+)", result.stdout + result.stderr)
        if match:
            versions.add(int(match.group(1)))
    return versions


def parse_class_major_versions(text: str) -> set[int]:
    """Parse one or more ``major version: N`` lines from raw javap output."""

    return {int(match.group(1)) for match in re.finditer(r"major version:\s*(\d+)", text or "")}


__all__ = [
    "class_major_versions_in_target",
    "classify_maven_failure",
    "feedback_digest",
    "parse_class_major_versions",
    "required_test_count",
    "run_maven",
    "surefire_test_count",
]
