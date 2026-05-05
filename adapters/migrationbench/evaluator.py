"""Official MigrationBench evaluator wrapper and strict success contract."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from .schemas import MigrationBenchInstance, PatchStats
from .workspace import run_command


SUCCESS_RE = re.compile(r"Success\s*=\s*(True|False)|`\s*(True|False|0|1)\s*`")


def _tail(text: str, max_chars: int = 4000) -> str:
    return str(text or "")[-max_chars:]


class MigrationBenchEvaluator:
    """Small subprocess wrapper around the official `migration_bench.run_eval`."""

    def __init__(
        self,
        *,
        migrationbench_root: str | Path = "external/MigrationBench",
        run_official: bool = True,
        timeout_seconds: float = 1800.0,
    ) -> None:
        self.migrationbench_root = Path(migrationbench_root).expanduser().resolve()
        self.run_official = bool(run_official)
        self.timeout_seconds = float(timeout_seconds)

    @property
    def run_eval_script(self) -> Path:
        return self.migrationbench_root / "src" / "migration_bench" / "run_eval.py"

    def evaluate_patch(
        self,
        *,
        instance: MigrationBenchInstance,
        patch_path: str | Path,
        output_dir: str | Path,
        patch_stats: PatchStats | None = None,
        patch_applies: bool = False,
        patch_apply_reason: str = "",
        maven_command: str = "cd {root_dir}; mvn clean verify",
    ) -> dict[str, Any]:
        """Evaluate one patch and return official and internal telemetry."""
        started = time.perf_counter()
        patch_path = Path(patch_path).expanduser().resolve()
        output_dir = Path(output_dir).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        if patch_stats is None:
            text = patch_path.read_text(encoding="utf-8") if patch_path.exists() else ""
            patch_stats = PatchStats(
                patch_delivered=bool(text.strip()),
                patch_lines_added=sum(
                    1 for line in text.splitlines() if line.startswith("+") and not line.startswith("+++")
                ),
                patch_lines_deleted=sum(
                    1 for line in text.splitlines() if line.startswith("-") and not line.startswith("---")
                ),
                files_modified_count=sum(1 for line in text.splitlines() if line.startswith("diff --git ")),
            )

        base_payload: dict[str, Any] = {
            "official_success": False,
            "official_eval_ran": False,
            "official_eval_command": [],
            "official_eval_log": "",
            "official_eval_stdout_tail": "",
            "official_eval_stderr_tail": "",
            "official_eval_returncode": None,
            "build_success": False,
            "test_success": False,
            "compiled_major_version_ok": None,
            "test_count_non_decreasing": None,
            "dependency_policy_ok": None,
            "official_runtime_seconds": 0.0,
        }

        if not patch_stats.patch_delivered:
            base_payload["failure_reason"] = "empty_patch"
            base_payload["official_runtime_seconds"] = round(time.perf_counter() - started, 4)
            return base_payload
        if not patch_applies:
            base_payload["failure_reason"] = patch_apply_reason or "patch_does_not_apply"
            base_payload["official_runtime_seconds"] = round(time.perf_counter() - started, 4)
            return base_payload
        if not self.run_official:
            base_payload["failure_reason"] = "official_eval_not_run"
            base_payload["official_runtime_seconds"] = round(time.perf_counter() - started, 4)
            return base_payload
        if not self.run_eval_script.exists():
            base_payload["failure_reason"] = "official_evaluator_missing"
            base_payload["official_runtime_seconds"] = round(time.perf_counter() - started, 4)
            return base_payload

        log_path = output_dir / "official_eval.log"
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
            env=self._official_eval_env(),
            timeout_seconds=self.timeout_seconds,
        )
        combined = (result.stdout or "") + "\n" + (result.stderr or "")
        log_path.write_text(combined, encoding="utf-8")
        official_success = self._parse_success(combined)
        payload = {
            **base_payload,
            "official_success": bool(official_success),
            "official_eval_ran": True,
            "official_eval_command": command,
            "official_eval_log": str(log_path),
            "official_eval_stdout_tail": _tail(result.stdout),
            "official_eval_stderr_tail": _tail(result.stderr),
            "official_eval_returncode": result.returncode,
            "build_success": bool(official_success),
            "test_success": bool(official_success),
            "compiled_major_version_ok": bool(official_success),
            "test_count_non_decreasing": bool(official_success),
            "dependency_policy_ok": (
                bool(official_success) if instance.is_maximal_migration else None
            ),
            "official_runtime_seconds": round(time.perf_counter() - started, 4),
            "failure_reason": "ok" if official_success else "official_eval_failed",
        }
        (output_dir / "official_eval.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return payload

    def _parse_success(self, text: str) -> bool:
        """Parse official stdout/stderr where failures still exit zero."""
        matches = list(SUCCESS_RE.finditer(text or ""))
        if not matches:
            return False
        last = matches[-1]
        values = [group for group in last.groups() if group is not None]
        if not values:
            return False
        return values[-1] in {"True", "1"}

    def _official_eval_env(self) -> dict[str, str]:
        """Expose MigrationBench's `src` package path to its script entrypoint."""
        env = os.environ.copy()
        src_path = str(self.migrationbench_root / "src")
        current = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = src_path if not current else f"{src_path}{os.pathsep}{current}"
        return env


def build_strict_contract(
    *,
    instance: MigrationBenchInstance,
    framework: str,
    provider: str,
    model: str,
    seed: int,
    patch_path: str | Path,
    patch_stats: PatchStats,
    patch_applies: bool,
    patch_apply_reason: str,
    official: dict[str, Any],
    tokens_total: int = 0,
    cost_total_usd: float = 0.0,
    runtime_seconds: float = 0.0,
    repair_cycles: int = 0,
    llm_calls: int = 0,
    markers_created: int = 0,
    coordination_overhead: int = 0,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the common output contract for all MigrationBench arms."""
    artifact_delivered = patch_stats.patch_delivered
    official_success = bool(official.get("official_success", False))
    strict_success = bool(artifact_delivered and patch_applies and official_success)
    failure_reason = str(official.get("failure_reason", "") or "").strip()
    if strict_success:
        failure_reason = "ok"
    elif not artifact_delivered:
        failure_reason = "empty_patch"
    elif not patch_applies:
        failure_reason = patch_apply_reason or "patch_does_not_apply"
    elif not failure_reason or failure_reason == "ok":
        failure_reason = "official_eval_failed"

    payload = {
        "instance_id": instance.instance_id,
        "framework": framework,
        "provider": provider,
        "model": model,
        "seed": int(seed),
        "artifact_delivered": artifact_delivered,
        "patch_delivered": patch_stats.patch_delivered,
        "patch_applies": bool(patch_applies),
        "official_success": official_success,
        "strict_success": strict_success,
        "failure_reason": failure_reason,
        "migration_mode": instance.migration_mode,
        "target_java": int(instance.target_java),
        "build_success": bool(official.get("build_success", False)),
        "test_success": bool(official.get("test_success", False)),
        "compiled_major_version_ok": official.get("compiled_major_version_ok"),
        "test_count_non_decreasing": official.get("test_count_non_decreasing"),
        "dependency_policy_ok": official.get("dependency_policy_ok"),
        "tokens_total": int(tokens_total),
        "cost_total_usd": round(float(cost_total_usd), 6),
        "runtime_seconds": round(float(runtime_seconds), 4),
        "repair_cycles": int(repair_cycles),
        "llm_calls": int(llm_calls),
        "branch_count": 0,
        "best_branch_id": "",
        "failure_taxonomy": "",
        "dynamic_agents_min": None,
        "dynamic_agents_max": None,
        "dynamic_agents_avg": None,
        "caps_hit": {},
        "last_progress_at": None,
        "manual_abort": False,
        "abort_reason": "",
        "files_modified_count": int(patch_stats.files_modified_count),
        "patch_lines_added": int(patch_stats.patch_lines_added),
        "patch_lines_deleted": int(patch_stats.patch_lines_deleted),
        "markers_created": int(markers_created),
        "coordination_overhead": int(coordination_overhead),
        "patch_path": str(Path(patch_path)),
        "patch_apply_reason": patch_apply_reason,
        "official_eval": official,
    }
    if extra:
        payload.update(extra)
    return payload
