"""Minimal subprocess helpers shared by V10 MigrationBench modules."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


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

    @property
    def timed_out(self) -> bool:
        return self.returncode == 124


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
