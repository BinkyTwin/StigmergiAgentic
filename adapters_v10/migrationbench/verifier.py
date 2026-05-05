"""V10 MigrationBench verifier — strict success gating.

The verifier is the *only* module that may stamp the ``strict_success``
signal on an artifact. It does so iff the full chain succeeds:

1. the candidate exported a non-empty patch (``patch_delivered``);
2. the patch applies cleanly on a fresh checkout (``patch_applies``);
3. ``mvn clean compile`` then ``mvn test`` succeed in the branch
   (``compile_success``, ``test_success``);
4. compiled classes have the JVM major version required by the instance's
   ``target_java`` (``class_version_ok``);
5. when the migration mode is ``maximal``, dependency policy is satisfied
   (``dependency_policy_ok``);
6. the official evaluator (``run_eval.py``) returns ``Success = True``
   (``official_success``).

There is no fallback path. Any failure in the chain yields
``strict_success=False`` and records the precise stage that broke. The
legacy V7 ``_synthesize_best_partial_payload`` shortcut has no equivalent
here: producing a partial-but-claimed-applied payload is structurally
impossible.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core_v10.contracts import ValidationResult, ValidationStatus

from adapters_v10.migrationbench._runtime import CommandResult, run_command
from adapters_v10.migrationbench.maven import (
    classify_maven_failure,
    feedback_digest,
    parse_class_major_versions,
    required_test_count,
    run_maven,
    surefire_test_count,
)
from adapters_v10.migrationbench.schemas import (
    JAVA_MAJOR_VERSION,
    MigrationBenchInstance,
    PatchStats,
)
from adapters_v10.migrationbench.workspace import MigrationBenchWorkspaceV10


SIGNAL_KEYS: tuple[str, ...] = (
    "patch_delivered",
    "patch_applies",
    "compile_success",
    "test_success",
    "class_version_ok",
    "dependency_policy_ok",
    "official_success",
    "strict_success",
)
"""Canonical ordering of the eight verifier signals."""


_SUCCESS_RE = re.compile(r"Success\s*=\s*(True|False)|`\s*(True|False|0|1)\s*`")


def _tail(text: str, max_chars: int = 4000) -> str:
    return str(text or "")[-max_chars:]


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class LocalVerificationResult:
    """Outcome of the local Maven build/test/class-version verification."""

    compile_success: bool = False
    test_success: bool = False
    class_version_ok: bool | None = None
    dependency_policy_ok: bool | None = None
    class_versions: list[int] = field(default_factory=list)
    surefire_tests: int | None = None
    required_tests: int | None = None
    failure_taxonomy: str = "build_failure"
    digest: str = ""
    runtime_seconds: float = 0.0
    stages: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class PatchApplyResult:
    """Outcome of pre-flight ``git apply --check`` on a clean checkout."""

    applies: bool
    reason: str
    log_tail: str = ""


@dataclass(slots=True)
class OfficialVerificationResult:
    """Outcome of the official ``run_eval.py`` invocation."""

    official_success: bool
    ran: bool
    returncode: int | None
    failure_reason: str
    command: list[str]
    stdout_tail: str
    stderr_tail: str
    log_path: str
    runtime_seconds: float


# ---------------------------------------------------------------------------
# Official evaluator wrapper
# ---------------------------------------------------------------------------


class OfficialEvaluator:
    """Thin wrapper around ``external/MigrationBench/src/migration_bench/run_eval.py``."""

    def __init__(
        self,
        *,
        migrationbench_root: str | Path = "external/MigrationBench",
        timeout_seconds: float = 1800.0,
    ) -> None:
        self.migrationbench_root = Path(migrationbench_root).expanduser().resolve()
        self.timeout_seconds = float(timeout_seconds)

    @property
    def run_eval_script(self) -> Path:
        return self.migrationbench_root / "src" / "migration_bench" / "run_eval.py"

    @property
    def available(self) -> bool:
        return self.run_eval_script.exists()

    def evaluate(
        self,
        *,
        instance: MigrationBenchInstance,
        patch_path: str | Path,
        output_dir: str | Path,
        maven_command: str = "cd {root_dir}; mvn clean verify",
    ) -> OfficialVerificationResult:
        started = time.perf_counter()
        patch_path = Path(patch_path).expanduser().resolve()
        output_dir = Path(output_dir).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        if not self.available:
            return OfficialVerificationResult(
                official_success=False,
                ran=False,
                returncode=None,
                failure_reason="official_evaluator_missing",
                command=[],
                stdout_tail="",
                stderr_tail="",
                log_path="",
                runtime_seconds=round(time.perf_counter() - started, 4),
            )

        command = [
            sys.executable,
            str(self.run_eval_script),
            "--github_url",
            instance.repo_url,
            "--git_diff_filename",
            str(patch_path),
            "--base_commit_id",
            instance.base_commit,
            "--maven_command",
            maven_command,
            "--is_maximal_migration",
            "1" if instance.is_maximal_migration else "0",
            "--require_compiled_java_major_version",
            str(instance.require_compiled_java_major_version),
            "--max_workers",
            "1",
        ]
        result = run_command(
            command,
            cwd=self.migrationbench_root,
            env=self._env(),
            timeout_seconds=self.timeout_seconds,
        )
        combined = (result.stdout or "") + "\n" + (result.stderr or "")
        log_path = output_dir / "official_eval.log"
        log_path.write_text(combined, encoding="utf-8")
        success = _parse_official_success(combined)
        payload = OfficialVerificationResult(
            official_success=bool(success),
            ran=True,
            returncode=result.returncode,
            failure_reason="ok" if success else "official_eval_failed",
            command=command,
            stdout_tail=_tail(result.stdout),
            stderr_tail=_tail(result.stderr),
            log_path=str(log_path),
            runtime_seconds=round(time.perf_counter() - started, 4),
        )
        (output_dir / "official_eval.json").write_text(
            json.dumps(_official_to_dict(payload), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return payload

    def _env(self) -> dict[str, str]:
        env = os.environ.copy()
        src = str(self.migrationbench_root / "src")
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = src if not existing else f"{src}{os.pathsep}{existing}"
        return env


def _parse_official_success(text: str) -> bool:
    matches = list(_SUCCESS_RE.finditer(text or ""))
    if not matches:
        return False
    last = matches[-1]
    values = [group for group in last.groups() if group is not None]
    if not values:
        return False
    return values[-1] in {"True", "1"}


def _official_to_dict(result: OfficialVerificationResult) -> dict[str, Any]:
    return {
        "official_success": result.official_success,
        "ran": result.ran,
        "returncode": result.returncode,
        "failure_reason": result.failure_reason,
        "command": list(result.command),
        "stdout_tail": result.stdout_tail,
        "stderr_tail": result.stderr_tail,
        "log_path": result.log_path,
        "runtime_seconds": result.runtime_seconds,
    }


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------


class MigrationBenchVerifier:
    """Orchestrates the local + official verification chain for V10."""

    def __init__(
        self,
        *,
        official_evaluator: OfficialEvaluator | None = None,
        compile_timeout_seconds: float = 600.0,
        test_timeout_seconds: float = 1200.0,
        dependency_timeout_seconds: float = 600.0,
    ) -> None:
        self.official_evaluator = official_evaluator
        self.compile_timeout_seconds = float(compile_timeout_seconds)
        self.test_timeout_seconds = float(test_timeout_seconds)
        self.dependency_timeout_seconds = float(dependency_timeout_seconds)

    # ---- local chain ---------------------------------------------------

    def verify_local(
        self, branch: MigrationBenchWorkspaceV10
    ) -> LocalVerificationResult:
        started = time.perf_counter()
        target_major = JAVA_MAJOR_VERSION[int(branch.instance.target_java)]
        stages: dict[str, int] = {}

        dep = run_maven(
            branch.repo_dir,
            "mvn -B -q dependency:resolve",
            timeout_seconds=self.dependency_timeout_seconds,
        )
        stages["dependency_resolve"] = dep.returncode
        if not dep.ok:
            digest = feedback_digest((dep.stdout or "") + "\n" + (dep.stderr or ""))
            return LocalVerificationResult(
                compile_success=False,
                test_success=False,
                class_version_ok=None,
                dependency_policy_ok=(
                    False if branch.instance.is_maximal_migration else None
                ),
                failure_taxonomy=classify_maven_failure(digest)
                if classify_maven_failure(digest) != "build_failure"
                else "dependency_resolution_error",
                digest=digest,
                runtime_seconds=round(time.perf_counter() - started, 4),
                stages=stages,
            )

        compile_result = run_maven(
            branch.repo_dir,
            "mvn -B -q clean compile",
            timeout_seconds=self.compile_timeout_seconds,
        )
        stages["compile"] = compile_result.returncode
        if not compile_result.ok:
            digest = feedback_digest(
                (compile_result.stdout or "") + "\n" + (compile_result.stderr or "")
            )
            return LocalVerificationResult(
                compile_success=False,
                test_success=False,
                class_version_ok=False,
                dependency_policy_ok=(
                    False if branch.instance.is_maximal_migration else None
                ),
                failure_taxonomy=classify_maven_failure(digest),
                digest=digest,
                runtime_seconds=round(time.perf_counter() - started, 4),
                stages=stages,
            )

        class_versions = self._collect_class_versions(branch.repo_dir)
        class_version_ok = bool(class_versions) and class_versions == {target_major}

        test_result = run_maven(
            branch.repo_dir,
            "mvn -B -q -DskipTests=false test",
            timeout_seconds=self.test_timeout_seconds,
        )
        stages["test"] = test_result.returncode
        observed_tests = surefire_test_count(branch.repo_dir)
        required = required_test_count(dict(branch.instance.stats))
        test_success = bool(
            test_result.ok
            and (
                required is None
                or observed_tests is None
                or observed_tests >= required
            )
        )

        if not test_result.ok or not test_success:
            digest = feedback_digest(
                (test_result.stdout or "") + "\n" + (test_result.stderr or "")
            )
            taxonomy = classify_maven_failure(digest)
            if not test_result.ok and taxonomy == "build_failure":
                taxonomy = "test_failure"
            return LocalVerificationResult(
                compile_success=True,
                test_success=False,
                class_version_ok=class_version_ok,
                dependency_policy_ok=(
                    True if branch.instance.is_maximal_migration else None
                ),
                class_versions=sorted(class_versions),
                surefire_tests=observed_tests,
                required_tests=required,
                failure_taxonomy=taxonomy,
                digest=digest,
                runtime_seconds=round(time.perf_counter() - started, 4),
                stages=stages,
            )

        return LocalVerificationResult(
            compile_success=True,
            test_success=True,
            class_version_ok=class_version_ok,
            dependency_policy_ok=(
                True if branch.instance.is_maximal_migration else None
            ),
            class_versions=sorted(class_versions),
            surefire_tests=observed_tests,
            required_tests=required,
            failure_taxonomy="ok" if class_version_ok else "class_version_error",
            digest="",
            runtime_seconds=round(time.perf_counter() - started, 4),
            stages=stages,
        )

    # ---- official chain ------------------------------------------------

    def verify_patch_applies(
        self,
        *,
        patch_path: Path,
        verification_workspace: MigrationBenchWorkspaceV10,
    ) -> PatchApplyResult:
        """Pre-flight ``git apply --check`` on a fresh checkout."""

        patch_path = Path(patch_path)
        if not patch_path.exists() or not patch_path.read_text(encoding="utf-8").strip():
            return PatchApplyResult(applies=False, reason="empty_patch")
        try:
            verification_workspace.prepare(force=True)
        except Exception as exc:  # noqa: BLE001
            return PatchApplyResult(
                applies=False,
                reason=f"verification_checkout_failed:{type(exc).__name__}:{exc}",
            )
        check = run_command(
            ["git", "apply", "--check", str(patch_path)],
            cwd=verification_workspace.repo_dir,
            timeout_seconds=120,
        )
        if not check.ok:
            return PatchApplyResult(
                applies=False,
                reason="git_apply_check_failed",
                log_tail=_tail((check.stderr or check.stdout), 1000),
            )
        return PatchApplyResult(applies=True, reason="ok")

    def verify_official(
        self,
        *,
        instance: MigrationBenchInstance,
        patch_path: Path,
        output_dir: Path,
    ) -> OfficialVerificationResult:
        if self.official_evaluator is None:
            return OfficialVerificationResult(
                official_success=False,
                ran=False,
                returncode=None,
                failure_reason="official_evaluator_missing",
                command=[],
                stdout_tail="",
                stderr_tail="",
                log_path="",
                runtime_seconds=0.0,
            )
        return self.official_evaluator.evaluate(
            instance=instance,
            patch_path=patch_path,
            output_dir=output_dir,
        )

    # ---- signals + ValidationResult ------------------------------------

    @staticmethod
    def build_signals(
        *,
        patch_stats: PatchStats,
        patch_apply: PatchApplyResult,
        local: LocalVerificationResult,
        official: OfficialVerificationResult | None,
        is_maximal: bool,
    ) -> dict[str, Any]:
        """Assemble the canonical eight-signal dict for one candidate.

        Strict invariant enforced here: ``strict_success`` is True only iff
        every prior signal is True (and ``dependency_policy_ok`` if the
        migration mode requires it).
        """

        official_success = bool(official.official_success) if official else False
        patch_delivered = bool(patch_stats.patch_delivered)
        patch_applies = bool(patch_apply.applies)
        compile_success = bool(local.compile_success)
        test_success = bool(local.test_success)
        class_version_ok = bool(local.class_version_ok) if local.class_version_ok else False
        dependency_policy_ok = (
            bool(local.dependency_policy_ok)
            if is_maximal
            else (local.dependency_policy_ok is not False)
        )

        strict_success = bool(
            patch_delivered
            and patch_applies
            and compile_success
            and test_success
            and class_version_ok
            and dependency_policy_ok
            and official_success
        )

        return {
            "patch_delivered": patch_delivered,
            "patch_applies": patch_applies,
            "compile_success": compile_success,
            "test_success": test_success,
            "class_version_ok": class_version_ok,
            "dependency_policy_ok": (
                bool(local.dependency_policy_ok) if is_maximal else None
            ),
            "official_success": official_success,
            "strict_success": strict_success,
        }

    @staticmethod
    def to_validation_result(
        *,
        candidate_id: str,
        signals: dict[str, Any],
        local: LocalVerificationResult,
        validator_name: str = "migrationbench_v10",
    ) -> ValidationResult:
        """Convert the verifier output into a ``core_v10.ValidationResult``.

        ``ValidationStatus.PASSED`` is reached as soon as the local chain
        (``patch_delivered`` + ``patch_applies`` + ``compile_success`` +
        ``test_success`` + ``class_version_ok``) is fully green. The
        official evaluator runs in :meth:`adapter.finalize` and is what
        gates ``strict_success`` in the final ``ScoreResult`` — so a
        validate that passes the local chain can still finalize to a
        non-strict outcome when the official evaluator rejects the patch.
        """

        local_chain_green = all(
            bool(signals.get(key))
            for key in (
                "patch_delivered",
                "patch_applies",
                "compile_success",
                "test_success",
                "class_version_ok",
            )
        )
        if local_chain_green:
            status = ValidationStatus.PASSED
        elif signals.get("compile_success"):
            status = ValidationStatus.PARTIAL
        else:
            status = ValidationStatus.FAILED

        return ValidationResult(
            candidate_id=candidate_id,
            status=status,
            validator_name=validator_name,
            signals=dict(signals),
            summary=local.failure_taxonomy,
            raw_output=local.digest,
            errors=(
                []
                if status != ValidationStatus.FAILED
                else [local.failure_taxonomy or "build_failure"]
            ),
            metadata={
                "class_versions": list(local.class_versions),
                "surefire_tests": local.surefire_tests,
                "required_tests": local.required_tests,
                "stages": dict(local.stages),
                "runtime_seconds": local.runtime_seconds,
            },
        )

    # ---- helpers -------------------------------------------------------

    def _collect_class_versions(self, repo_dir: Path) -> set[int]:
        versions: set[int] = set()
        if not repo_dir.exists():
            return versions
        class_files = [
            path
            for path in repo_dir.rglob("target/classes/**/*.class")
            if path.is_file()
        ][:2000]
        for path in class_files:
            result = run_command(
                ["bash", "-lc", f"javap -verbose {json.dumps(str(path))} | grep 'major version:'"],
                cwd=repo_dir,
                timeout_seconds=30,
            )
            versions |= parse_class_major_versions(result.stdout + result.stderr)
        return versions


def _command_to_dict(result: CommandResult) -> dict[str, Any]:
    return {
        "command": list(result.command),
        "returncode": result.returncode,
        "runtime_seconds": result.runtime_seconds,
    }


__all__ = [
    "LocalVerificationResult",
    "MigrationBenchVerifier",
    "OfficialEvaluator",
    "OfficialVerificationResult",
    "PatchApplyResult",
    "SIGNAL_KEYS",
]
