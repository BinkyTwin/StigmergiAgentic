"""Testing capability shared by specialized and generalist agents."""

from __future__ import annotations

import json
import os
import py_compile
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from ._config import non_python_config as _non_python_config

_PY_REF_RE = re.compile(r"(?P<ref>[A-Za-z0-9_./-]+\.py)\b")


def test_file(
    store: Any,
    repo_path: str | Path,
    file_key: str,
    config: dict[str, Any],
    agent_name: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run quality checks for one file and return tester execution payload."""

    del agent_name  # retained to keep API aligned across capabilities

    repo_root = Path(repo_path)
    file_path = repo_root / file_key
    status_entry = kwargs.get("status_entry") or (
        store.read_one("status", file_key) or {}
    )
    task_entry = kwargs.get("task_entry") or (store.read_one("tasks", file_key) or {})
    file_kind = str(
        kwargs.get("file_kind")
        or task_entry.get("file_kind")
        or _infer_file_kind(file_key)
    )

    if file_kind == "python":
        test_file_path = kwargs.get("test_file_path")
        if test_file_path is None:
            test_file_path = discover_test_file(
                repo_root=repo_root, file_path=file_path
            )

        if test_file_path is not None:
            run_pytest_for_file = kwargs.get("run_pytest_for_file")
            if not callable(run_pytest_for_file):
                run_pytest_for_file = _default_run_pytest_for_file(repo_root, config)
            stats = run_pytest_for_file(file_path=file_path, test_file=test_file_path)
            stats["test_mode"] = "pytest"
            tests_total = int(stats.get("tests_total", 0))
            tests_passed = int(stats.get("tests_passed", 0))
            confidence = 0.5 if tests_total == 0 else tests_passed / tests_total
            test_file_value = str(Path(test_file_path).relative_to(repo_root))
        else:
            run_adaptive_fallback = kwargs.get("run_adaptive_fallback")
            if not callable(run_adaptive_fallback):
                run_adaptive_fallback = _default_run_adaptive_fallback(
                    repo_root, config
                )
            stats = run_adaptive_fallback(file_key=file_key, file_path=file_path)
            confidence = float(stats.get("confidence", 0.0))
            test_file_value = None
    else:
        evaluate_non_python = (
            kwargs.get("evaluate_non_python") or evaluate_non_python_strict
        )
        stats = evaluate_non_python(
            file_key=file_key,
            file_path=file_path,
            repo_root=repo_root,
            config=config,
        )
        confidence = float(stats.get("confidence", 0.0))
        test_file_value = None

    tests_total = int(stats.get("tests_total", 0))
    tests_passed = int(stats.get("tests_passed", 0))
    tests_failed = int(stats.get("tests_failed", 0))
    return {
        "file_key": file_key,
        "tests_total": tests_total,
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
        "coverage": float(stats.get("coverage", 0.0)),
        "issues": list(stats.get("issues", [])),
        "confidence": confidence,
        "test_mode": str(stats.get("test_mode", "unknown")),
        "test_file": test_file_value,
        "retry_count": int(status_entry.get("retry_count", 0)),
        "inhibition": float(status_entry.get("inhibition", 0.0)),
        "file_kind": file_kind,
    }


def discover_test_file(repo_root: Path, file_path: Path) -> Path | None:
    """Find a colocated or tests/ prefixed pytest file for one module."""

    file_stem = file_path.stem
    expected_name = f"test_{file_stem}.py"

    candidate_1 = repo_root / "tests" / expected_name
    if candidate_1.exists():
        return candidate_1

    candidate_2 = file_path.parent / expected_name
    if candidate_2.exists():
        return candidate_2

    return None


def evaluate_non_python_strict(
    *,
    file_key: str,
    file_path: Path,
    repo_root: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Run strict validation guardrails for non-Python text files."""

    issues: list[str] = []
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    suffix = file_path.suffix.lower()
    non_python = _non_python_config(config)
    strict_guardrails = bool(non_python["strict_guardrails"])

    if strict_guardrails:
        parse_issue = _validate_structured_text(
            content=content, suffix=suffix, file_path=file_path
        )
        if parse_issue:
            issues.append(parse_issue)

    legacy_tokens = list(non_python["legacy_tokens"])
    lowered_content = content.lower()
    for token in legacy_tokens:
        normalized = token.strip().lower()
        if not normalized:
            continue
        if normalized in lowered_content:
            issues.append(f"legacy_reference:{token}")

    for match in _PY_REF_RE.finditer(content):
        raw_ref = match.group("ref")
        if not raw_ref:
            continue
        if not _python_reference_exists(
            raw_ref=raw_ref, file_path=file_path, repo_root=repo_root
        ):
            issues.append(f"missing_python_reference:{raw_ref}")

    issues = sorted(set(issues))
    passed = 0 if issues else 1
    failed = 1 if issues else 0
    confidence = (
        float(non_python["fail_confidence"])
        if issues
        else float(non_python["pass_confidence"])
    )

    return {
        "tests_total": 1,
        "tests_passed": passed,
        "tests_failed": failed,
        "coverage": 0.0,
        "issues": issues,
        "confidence": confidence,
        "test_mode": "non_python_strict",
    }


def _validate_structured_text(
    *, content: str, suffix: str, file_path: Path
) -> str | None:
    try:
        if suffix == ".json":
            json.loads(content)
        elif suffix in {".yaml", ".yml"}:
            yaml.safe_load(content)
        elif suffix == ".toml":
            tomllib.loads(content)
        elif suffix == ".sh":
            completed = subprocess.run(
                ["bash", "-n", str(file_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                stderr = (
                    completed.stderr.strip()
                    or completed.stdout.strip()
                    or "invalid shell syntax"
                )
                return f"shell_syntax:{stderr}"
    except Exception as exc:  # noqa: BLE001
        return f"parse_error:{suffix}:{exc}"
    return None


def _python_reference_exists(*, raw_ref: str, file_path: Path, repo_root: Path) -> bool:
    normalized = raw_ref.strip().replace("\\", "/")
    if not normalized:
        return True

    direct_repo = (repo_root / normalized).resolve()
    if direct_repo.exists():
        return True

    relative_to_file = (file_path.parent / normalized).resolve()
    if relative_to_file.exists():
        return True

    basename = Path(normalized).name
    candidates = list(repo_root.rglob(basename))
    return any(candidate.suffix == ".py" for candidate in candidates)


def _infer_file_kind(file_key: str) -> str:
    return "python" if str(file_key).endswith(".py") else "text"


# ---------------------------------------------------------------------------
# Default subprocess implementations (standalone, no wrapper needed)
# ---------------------------------------------------------------------------

PY2_STDLIB_MODULES = {
    "ConfigParser",
    "Queue",
    "StringIO",
    "cPickle",
    "cStringIO",
    "commands",
    "cookielib",
    "httplib",
    "urlparse",
    "urllib2",
}


def _default_run_pytest_for_file(repo_root: Path, config: dict[str, Any]) -> Any:
    """Return a callable matching the ``run_pytest_for_file`` callback API."""

    def _run(*, file_path: Path, test_file: Path) -> dict[str, Any]:
        module_name = _to_module_name(file_path, repo_root)
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(test_file),
            "--maxfail=1",
            "-q",
            f"--cov={module_name}",
            "--cov-report=term",
        ]
        env = _python_env(repo_root)
        completed = subprocess.run(
            cmd,
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
        output = f"{completed.stdout}\n{completed.stderr}"
        parsed = _parse_pytest_summary(output)
        coverage = _parse_coverage(output)

        if parsed["tests_total"] == 0:
            if completed.returncode == 0:
                parsed["tests_total"] = 1
                parsed["tests_passed"] = 1
            else:
                parsed["tests_total"] = 1
                parsed["tests_failed"] = 1

        issues: list[str] = []
        if completed.returncode != 0:
            issues.append(_compact_issue(output))

        return {**parsed, "coverage": coverage, "issues": issues}

    return _run


def _default_run_adaptive_fallback(repo_root: Path, config: dict[str, Any]) -> Any:
    """Return a callable matching the ``run_adaptive_fallback`` callback API."""

    fallback_config = config.get("tester", {}).get("fallback_quality", {})
    thresholds = {
        "compile_import_fail": float(fallback_config.get("compile_import_fail", 0.4)),
        "related_regression": float(fallback_config.get("related_regression", 0.6)),
        "pass_or_inconclusive": float(fallback_config.get("pass_or_inconclusive", 0.8)),
    }
    optional_hints = _optional_dependency_hints(config)

    def _run(*, file_key: str, file_path: Path) -> dict[str, Any]:
        fallback = _run_fallback_checks(
            file_path=file_path,
            repo_root=repo_root,
            optional_hints=optional_hints,
        )

        if not bool(fallback.get("compile_import_ok")):
            return {
                **fallback,
                "confidence": thresholds["compile_import_fail"],
                "test_mode": "fallback_compile_import_fail",
            }

        global_pytest = _run_global_pytest(
            file_path=file_path,
            repo_root=repo_root,
            optional_hints=optional_hints,
        )
        classification = str(global_pytest.get("classification", "inconclusive"))
        confidence = (
            thresholds["related_regression"]
            if classification == "related"
            else thresholds["pass_or_inconclusive"]
        )

        merged_issues = list(fallback.get("issues", []))
        for issue in global_pytest.get("issues", []):
            if issue not in merged_issues:
                merged_issues.append(issue)

        return {
            "tests_total": int(global_pytest.get("tests_total", 0)),
            "tests_passed": int(global_pytest.get("tests_passed", 0)),
            "tests_failed": int(global_pytest.get("tests_failed", 0)),
            "coverage": 0.0,
            "issues": merged_issues,
            "confidence": confidence,
            "test_mode": f"fallback_global_{classification}",
            "classification": classification,
            "file_key": file_key,
        }

    return _run


def _run_fallback_checks(
    *, file_path: Path, repo_root: Path, optional_hints: list[str]
) -> dict[str, Any]:
    """Run py_compile + import check for a single Python file."""

    issues: list[str] = []
    compiled_output_path: Path | None = None
    temp_handle = tempfile.NamedTemporaryFile(suffix=".pyc", delete=False)
    try:
        compiled_output_path = Path(temp_handle.name)
    finally:
        temp_handle.close()

    try:
        py_compile.compile(
            str(file_path), cfile=str(compiled_output_path), doraise=True
        )
    except py_compile.PyCompileError as exc:
        issues.append(f"py_compile: {exc.msg}")
        return {
            "tests_total": 1,
            "tests_passed": 0,
            "tests_failed": 1,
            "coverage": 0.0,
            "issues": issues,
            "compile_import_ok": False,
        }
    finally:
        if compiled_output_path is not None:
            compiled_output_path.unlink(missing_ok=True)

    module_name = _to_module_name(file_path, repo_root)
    env = _python_env(repo_root)
    completed = subprocess.run(
        [sys.executable, "-c", f"import {module_name}"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    if completed.returncode != 0:
        output = f"{completed.stdout}\n{completed.stderr}"
        issues.append(_compact_issue(output))
        if _is_inconclusive_import_failure(
            file_path=file_path,
            repo_root=repo_root,
            output=output,
            optional_hints=optional_hints,
        ):
            return {
                "tests_total": 0,
                "tests_passed": 0,
                "tests_failed": 0,
                "coverage": 0.0,
                "issues": issues,
                "compile_import_ok": True,
            }
        return {
            "tests_total": 1,
            "tests_passed": 0,
            "tests_failed": 1,
            "coverage": 0.0,
            "issues": issues,
            "compile_import_ok": False,
        }

    return {
        "tests_total": 0,
        "tests_passed": 0,
        "tests_failed": 0,
        "coverage": 0.0,
        "issues": issues,
        "compile_import_ok": True,
    }


def _run_global_pytest(
    *, file_path: Path, repo_root: Path, optional_hints: list[str]
) -> dict[str, Any]:
    """Run global pytest and classify failures."""

    env = _python_env(repo_root)
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    output = f"{completed.stdout}\n{completed.stderr}"
    parsed = _parse_pytest_summary(output)

    if parsed["tests_total"] == 0:
        if completed.returncode == 0:
            parsed["tests_total"] = 1
            parsed["tests_passed"] = 1
        else:
            parsed["tests_total"] = 1
            parsed["tests_failed"] = 1

    issues: list[str] = []
    classification = "pass"
    if completed.returncode != 0:
        classification = _classify_global_failure(
            file_path=file_path,
            repo_root=repo_root,
            output=output,
            optional_hints=optional_hints,
        )
        issues.append(_compact_issue(output))

    return {**parsed, "issues": issues, "classification": classification}


# ---------------------------------------------------------------------------
# Helpers shared by default implementations
# ---------------------------------------------------------------------------


def _python_env(repo_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(repo_root) if not existing else f"{repo_root}{os.pathsep}{existing}"
    )
    return env


def _to_module_name(file_path: Path, repo_root: Path) -> str:
    relative = file_path.relative_to(repo_root)
    return ".".join(relative.with_suffix("").parts)


def _parse_pytest_summary(output: str) -> dict[str, int]:
    passed = _extract_summary_value(output, "passed")
    failed = _extract_summary_value(output, "failed")
    errors = _extract_summary_value(output, "error")
    return {
        "tests_total": passed + failed + errors,
        "tests_passed": passed,
        "tests_failed": failed + errors,
    }


def _extract_summary_value(output: str, keyword: str) -> int:
    match = re.search(rf"(?P<count>\d+)\s+{keyword}s?", output)
    return int(match.group("count")) if match else 0


def _parse_coverage(output: str) -> float:
    match = re.search(r"TOTAL\s+\d+\s+\d+\s+(?P<percent>\d+)%", output)
    return int(match.group("percent")) / 100.0 if match else 0.0


def _compact_issue(output: str) -> str:
    clean = " ".join(line.strip() for line in output.splitlines() if line.strip())
    return clean[:297] + "..." if len(clean) > 300 else clean


def _extract_missing_modules(output: str) -> list[str]:
    pattern = re.compile(r"No module named ['\"](?P<name>[^'\"]+)['\"]")
    return [m.group("name") for m in pattern.finditer(output)]


def _is_optional_missing_module(
    module_name: str, file_path: Path, repo_root: Path
) -> bool:
    root = module_name.split(".", 1)[0]
    if root in PY2_STDLIB_MODULES:
        return False
    if (repo_root / (root.replace(".", "/") + ".py")).exists():
        return False
    if (repo_root / root / "__init__.py").exists():
        return False
    if root == file_path.stem:
        return False
    return True


def _contains_optional_dependency_hint(output: str, hints: list[str]) -> bool:
    lowered = output.lower()
    return any(hint in lowered for hint in hints)


def _optional_dependency_hints(config: dict[str, Any]) -> list[str]:
    hints = config.get("tester", {}).get("optional_dependency_hints")
    if isinstance(hints, list):
        normalized = [
            str(item).strip().lower()
            for item in hints
            if isinstance(item, str) and str(item).strip()
        ]
        if normalized:
            return normalized
    return ["requires that", "pip install", "optional dependency"]


def _is_inconclusive_import_failure(
    *,
    file_path: Path,
    repo_root: Path,
    output: str,
    optional_hints: list[str],
) -> bool:
    lowered = output.lower()
    if "usage:" in lowered or "systemexit" in lowered:
        return True
    if _contains_optional_dependency_hint(output, optional_hints):
        return True
    missing = _extract_missing_modules(output)
    if missing:
        return all(
            _is_optional_missing_module(name, file_path, repo_root) for name in missing
        )
    return False


def _classify_global_failure(
    *,
    file_path: Path,
    repo_root: Path,
    output: str,
    optional_hints: list[str],
) -> str:
    lowered = output.lower()
    if any(
        marker in lowered
        for marker in [
            "importerror while loading conftest",
            "usage:",
            "systemexit",
            "no tests ran",
        ]
    ):
        return "inconclusive"
    if _contains_optional_dependency_hint(output, optional_hints):
        return "inconclusive"
    missing = _extract_missing_modules(output)
    if missing and all(
        _is_optional_missing_module(name, file_path, repo_root) for name in missing
    ):
        return "inconclusive"

    module_name = _to_module_name(file_path, repo_root)
    relative_path = file_path.relative_to(repo_root).as_posix()
    markers = [relative_path, file_path.name, module_name]
    if any(marker in output for marker in markers):
        return "related"
    return "inconclusive"
