"""Tester agent: runs deterministic checks and deposits quality pheromones."""

from __future__ import annotations

import os
import py_compile
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from .base_agent import BaseAgent


class Tester(BaseAgent):
    """Execute tests for transformed files and compute confidence signals."""

    __test__ = False

    def perceive(self) -> dict[str, Any]:
        transformed_entries = self.store.query("status", status="transformed")
        candidates = sorted(transformed_entries.keys())
        return {"candidates": candidates, "status_entries": transformed_entries}

    def should_act(self, perception: dict[str, Any]) -> bool:
        return bool(perception.get("candidates"))

    def decide(self, perception: dict[str, Any]) -> dict[str, Any]:
        file_key = perception["candidates"][0]
        file_path = self.target_repo_path / file_key
        status_entry = perception["status_entries"][file_key]
        test_file = self._discover_test_file(file_path)

        return {
            "file_key": file_key,
            "file_path": file_path,
            "status_entry": status_entry,
            "test_file": test_file,
        }

    def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        file_key = action["file_key"]
        file_path: Path = action["file_path"]
        test_file: Path | None = action["test_file"]

        if test_file is not None:
            stats = self._run_pytest_for_file(file_path=file_path, test_file=test_file)
            stats["test_mode"] = "pytest"
        else:
            stats = self._run_fallback_checks(file_path=file_path)
            stats["test_mode"] = "fallback"

        tests_total = int(stats.get("tests_total", 0))
        tests_passed = int(stats.get("tests_passed", 0))
        tests_failed = int(stats.get("tests_failed", 0))

        confidence = 0.5 if tests_total == 0 else tests_passed / tests_total

        return {
            "file_key": file_key,
            "tests_total": tests_total,
            "tests_passed": tests_passed,
            "tests_failed": tests_failed,
            "coverage": float(stats.get("coverage", 0.0)),
            "issues": list(stats.get("issues", [])),
            "confidence": confidence,
            "test_mode": stats["test_mode"],
            "test_file": (
                str(test_file.relative_to(self.target_repo_path)) if test_file else None
            ),
            "retry_count": int(action["status_entry"].get("retry_count", 0)),
            "inhibition": float(action["status_entry"].get("inhibition", 0.0)),
        }

    def deposit(self, result: dict[str, Any]) -> None:
        file_key = result["file_key"]

        quality_payload = {
            "confidence": float(result["confidence"]),
            "tests_total": int(result["tests_total"]),
            "tests_passed": int(result["tests_passed"]),
            "tests_failed": int(result["tests_failed"]),
            "coverage": float(result["coverage"]),
            "issues": list(result["issues"]),
            "metadata": {
                "test_mode": result["test_mode"],
                "test_file": result["test_file"],
            },
        }
        self.store.write(
            "quality", file_key=file_key, data=quality_payload, agent_id=self.name
        )

        self.store.update(
            "status",
            file_key=file_key,
            agent_id=self.name,
            status="tested",
            previous_status="transformed",
            retry_count=int(result.get("retry_count", 0)),
            inhibition=float(result.get("inhibition", 0.0)),
            metadata={
                "tests_total": int(result["tests_total"]),
                "tests_failed": int(result["tests_failed"]),
                "coverage": float(result["coverage"]),
                "test_mode": result["test_mode"],
            },
        )

    def _discover_test_file(self, file_path: Path) -> Path | None:
        file_stem = file_path.stem
        expected_name = f"test_{file_stem}.py"

        candidate_1 = self.target_repo_path / "tests" / expected_name
        if candidate_1.exists():
            return candidate_1

        candidate_2 = file_path.parent / expected_name
        if candidate_2.exists():
            return candidate_2

        return None

    def _run_pytest_for_file(self, file_path: Path, test_file: Path) -> dict[str, Any]:
        module_name = self._to_module_name(file_path)
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

        env = os.environ.copy()
        existing_python_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            str(self.target_repo_path)
            if not existing_python_path
            else f"{self.target_repo_path}{os.pathsep}{existing_python_path}"
        )

        completed = subprocess.run(
            cmd,
            cwd=self.target_repo_path,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

        output = f"{completed.stdout}\n{completed.stderr}"
        parsed = self._parse_pytest_summary(output=output)
        coverage = self._parse_coverage(output=output)

        if parsed["tests_total"] == 0:
            if completed.returncode == 0:
                parsed["tests_total"] = 1
                parsed["tests_passed"] = 1
            else:
                parsed["tests_total"] = 1
                parsed["tests_failed"] = 1

        issues: list[str] = []
        if completed.returncode != 0:
            issues.append(self._compact_issue(output))

        return {
            **parsed,
            "coverage": coverage,
            "issues": issues,
        }

    def _run_fallback_checks(self, file_path: Path) -> dict[str, Any]:
        issues: list[str] = []

        try:
            py_compile.compile(str(file_path), doraise=True)
        except py_compile.PyCompileError as exc:
            issues.append(f"py_compile: {exc.msg}")
            return {
                "tests_total": 1,
                "tests_passed": 0,
                "tests_failed": 1,
                "coverage": 0.0,
                "issues": issues,
            }

        module_name = self._to_module_name(file_path)
        env = os.environ.copy()
        existing_python_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            str(self.target_repo_path)
            if not existing_python_path
            else f"{self.target_repo_path}{os.pathsep}{existing_python_path}"
        )

        completed = subprocess.run(
            [sys.executable, "-c", f"import {module_name}"],
            cwd=self.target_repo_path,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

        if completed.returncode != 0:
            issues.append(
                self._compact_issue(f"{completed.stdout}\n{completed.stderr}")
            )
            return {
                "tests_total": 1,
                "tests_passed": 0,
                "tests_failed": 1,
                "coverage": 0.0,
                "issues": issues,
            }

        return {
            "tests_total": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "coverage": 0.0,
            "issues": issues,
        }

    def _parse_pytest_summary(self, output: str) -> dict[str, int]:
        passed = self._extract_summary_value(output, "passed")
        failed = self._extract_summary_value(output, "failed")
        errors = self._extract_summary_value(output, "error")
        tests_total = passed + failed + errors

        return {
            "tests_total": tests_total,
            "tests_passed": passed,
            "tests_failed": failed + errors,
        }

    def _extract_summary_value(self, output: str, keyword: str) -> int:
        pattern = re.compile(rf"(?P<count>\d+)\s+{keyword}s?")
        match = pattern.search(output)
        if not match:
            return 0
        return int(match.group("count"))

    def _parse_coverage(self, output: str) -> float:
        match = re.search(r"TOTAL\s+\d+\s+\d+\s+(?P<percent>\d+)%", output)
        if not match:
            return 0.0
        return int(match.group("percent")) / 100.0

    def _to_module_name(self, file_path: Path) -> str:
        relative = file_path.relative_to(self.target_repo_path)
        return ".".join(relative.with_suffix("").parts)

    def _compact_issue(self, output: str) -> str:
        clean = " ".join(line.strip() for line in output.splitlines() if line.strip())
        if len(clean) > 300:
            return clean[:297] + "..."
        return clean
