"""V10 MigrationBench adapter — implements ``DomainAdapterV10``.

The adapter is created per-instance: ``setup`` materializes a base
checkout, and subsequent ``apply / validate / finalize / score`` calls
operate on isolated branch workspaces derived from it. The eight verifier
signals (see :data:`adapters_v10.migrationbench.SIGNAL_KEYS`) are captured
during ``finalize`` and stamped onto :class:`ArtifactResult.metadata` so
:meth:`score` can rebuild :data:`strict_success` deterministically.

Strict invariant: ``ScoreResult.strict_success`` is True only when every
verifier signal is True. There is no diagnostic fallback. The legacy V7
``_synthesize_best_partial_payload`` shortcut is structurally absent.
"""

from __future__ import annotations

import gc
import json
import re
import shutil
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from core_v10.contracts import (
    ApplyResult,
    ArtifactContract,
    ArtifactResult,
    ArtifactStatus,
    Candidate,
    CandidateKind,
    Capability,
    DomainAdapterV10,
    FeedbackDigest,
    Observation,
    RunInstance,
    ScoreResult,
    ValidationResult,
    ValidationStatus,
    WorkspaceHandle,
)

from adapters_v10.migrationbench.context import migration_context_from_instance
from adapters_v10.migrationbench.maven import classify_maven_failure
from adapters_v10.migrationbench.schemas import (
    MigrationBenchInstance,
    PatchStats,
    TypedEditSet,
)
from adapters_v10.migrationbench.verifier import (
    LocalVerificationResult,
    MigrationBenchVerifier,
    OfficialEvaluator,
    OfficialVerificationResult,
    PatchApplyResult,
    SIGNAL_KEYS,
)
from adapters_v10.migrationbench.workspace import (
    EditApplicationResult,
    MigrationBenchWorkspaceV10,
    WorkspaceError,
)


_BRANCH_KEY = "branch_id"
_PARENT_BRANCH_KEY = "parent_branch_id"
_VERIFICATION_DIRNAME = "_verify"
_RAW_OUTPUT_JAVA_PATH_PATTERNS = (
    re.compile(r"(?:^|\s)(?P<path>[\w./-]+\.java):\[\d+,\d+\]"),
    re.compile(r"(?:^|\s)(?P<path>[\w./-]+\.java):\d+:"),
)


class MigrationBenchAdapterV10(DomainAdapterV10):
    """Per-instance V10 adapter for the MigrationBench benchmark."""

    name = "migrationbench_v10"
    artifact_contract = ArtifactContract(required_artifacts=("patch.diff",))

    def __init__(
        self,
        *,
        verifier: MigrationBenchVerifier | None = None,
        official_evaluator: OfficialEvaluator | None = None,
        timeout_seconds: float = 600.0,
    ) -> None:
        self.verifier = verifier or MigrationBenchVerifier(
            official_evaluator=official_evaluator
        )
        self.timeout_seconds = float(timeout_seconds)
        self._instance: MigrationBenchInstance | None = None
        self._base_workspace: MigrationBenchWorkspaceV10 | None = None
        self._artifacts_dir: Path | None = None

    # ------------------------------------------------------------------
    # DomainAdapterV10 surface
    # ------------------------------------------------------------------

    def setup(self, instance: RunInstance) -> WorkspaceHandle:
        """Materialise the base checkout for ``instance`` and return its handle."""

        mb_instance = self._coerce_instance(instance)
        workspace_root = (
            Path(instance.metadata["workspace_root"]).expanduser().resolve()
        )
        artifacts_dir = (
            Path(instance.metadata.get("artifacts_dir", workspace_root / "artifacts"))
            .expanduser()
            .resolve()
        )
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        base = MigrationBenchWorkspaceV10(
            instance=mb_instance,
            root_dir=workspace_root,
            timeout_seconds=self.timeout_seconds,
        )
        if instance.metadata.get("prepare", True):
            base.prepare(reset_branches=True)

        self._instance = mb_instance
        self._base_workspace = base
        self._artifacts_dir = artifacts_dir
        migration_context = migration_context_from_instance(mb_instance)

        handle = base.as_handle(
            role="base",
            artifacts_dir=str(artifacts_dir),
            target_class_major=migration_context.target_class_major,
            migration_context=migration_context.to_dict(),
        )
        return handle

    def observe(self, workspace: WorkspaceHandle) -> Observation:
        instance = self._require_instance()
        base = self._require_base_workspace()
        targets = base.list_targets()
        migration_context = migration_context_from_instance(instance)
        return Observation(
            summary=(
                f"Migrate {instance.repo_url}@{instance.base_commit[:8]} from Java "
                f"{migration_context.source_java} to Java "
                f"{migration_context.target_java} ({instance.migration_mode})"
            ),
            data={
                "instance_id": instance.instance_id,
                "repo_url": instance.repo_url,
                "base_commit": instance.base_commit,
                "target_java": int(instance.target_java),
                "source_java": migration_context.source_java,
                "migration_mode": instance.migration_mode,
                "build_system": migration_context.build_system,
                "dependency_policy": migration_context.dependency_policy,
                "migration_context": migration_context.to_dict(),
                "stats": dict(instance.stats),
                "stratum": dict(instance.stratum),
                "pom_files": [t for t in targets if t.endswith("pom.xml")][:40],
                "java_files_sample": [t for t in targets if t.endswith(".java")][:40],
                "target_class_major": migration_context.target_class_major,
            },
        )

    def capabilities(self) -> list[Capability]:
        return [
            Capability(
                name="propose_typed_edits",
                kind="proposer",
                description=(
                    "Produce a TypedEditSet over pom.xml / *.java files migrating "
                    "Java 8 to the target Java version."
                ),
            ),
            Capability(
                name="apply_typed_edits",
                kind="applier",
                description="Apply a TypedEditSet to an isolated branch workspace.",
            ),
            Capability(
                name="local_verifier",
                kind="validator",
                description=(
                    "Run mvn dependency:resolve / clean compile / test and check "
                    "compiled class major versions."
                ),
            ),
            Capability(
                name="official_verifier",
                kind="validator",
                description=(
                    "Invoke the official MigrationBench run_eval.py and parse "
                    "Success markers."
                ),
            ),
            Capability(
                name="export_patch",
                kind="finalizer",
                description="Export git diff --binary as the candidate's patch artifact.",
            ),
        ]

    def apply(self, candidate: Candidate, workspace: WorkspaceHandle) -> ApplyResult:
        if candidate.kind != CandidateKind.PATCH:
            return ApplyResult(
                candidate_id=candidate.candidate_id,
                applied=False,
                workspace=workspace,
                summary="unsupported candidate kind",
                errors=[f"unsupported candidate kind: {candidate.kind.value}"],
            )

        try:
            edits = self._coerce_edit_set(candidate.payload)
        except (ValueError, TypeError) as exc:
            return ApplyResult(
                candidate_id=candidate.candidate_id,
                applied=False,
                workspace=workspace,
                summary="invalid edit payload",
                errors=[f"invalid_edit_payload:{exc}"],
            )

        try:
            branch = self._open_branch(candidate, workspace)
        except Exception as exc:  # noqa: BLE001
            reason = f"branch_workspace_error:{type(exc).__name__}:{exc}"
            return ApplyResult(
                candidate_id=candidate.candidate_id,
                applied=False,
                workspace=workspace,
                summary=reason,
                errors=[reason],
            )
        application: EditApplicationResult = branch.apply_typed_edits(edits)
        if not application.applied:
            return ApplyResult(
                candidate_id=candidate.candidate_id,
                applied=False,
                workspace=branch.as_handle(
                    branch_id=self._branch_id(candidate),
                    role="branch",
                ),
                summary=application.failure_reason,
                errors=[application.failure_reason],
                metadata={
                    "files_modified": list(application.files_modified),
                    "replacements": dict(application.replacements),
                },
            )

        return ApplyResult(
            candidate_id=candidate.candidate_id,
            applied=True,
            workspace=branch.as_handle(
                branch_id=self._branch_id(candidate),
                role="branch",
            ),
            summary="typed edits applied",
            metadata={
                "files_modified": list(application.files_modified),
                "replacements": dict(application.replacements),
            },
        )

    def validate(
        self, candidate: Candidate, workspace: WorkspaceHandle
    ) -> ValidationResult:
        branch = self._open_branch(candidate, workspace)
        local: LocalVerificationResult = self.verifier.verify_local(branch)
        # Pre-flight apply check ahead of finalize to surface early failure.
        patch_path = self._candidate_patch_path(candidate)
        patch_stats = branch.export_patch(patch_path)
        verification_root = (
            branch.root_dir.parent / _VERIFICATION_DIRNAME / candidate.candidate_id
        )
        verification = MigrationBenchWorkspaceV10(
            instance=self._require_instance(),
            root_dir=verification_root,
            timeout_seconds=self.timeout_seconds,
        )
        try:
            apply_check = self.verifier.verify_patch_applies(
                patch_path=patch_path,
                verification_workspace=verification,
            )
        finally:
            verification_cleaned = self._cleanup_path(verification_root)
        build_outputs_removed = branch.cleanup_build_outputs()
        official: OfficialVerificationResult | None = None
        local_chain_green = bool(
            patch_stats.patch_delivered
            and apply_check.applies
            and local.compile_success
            and local.test_success
            and local.class_version_ok
        )
        if local_chain_green and self.verifier.official_evaluator is not None:
            official_dir = (
                self._artifacts_dir_or_default(workspace)
                / candidate.candidate_id
                / "official_validation"
            )
            official = self.verifier.verify_official(
                instance=self._require_instance(),
                patch_path=patch_path,
                output_dir=official_dir,
            )

        signals = self.verifier.build_signals(
            patch_stats=patch_stats,
            patch_apply=apply_check,
            local=local,
            official=official,
            is_maximal=self._require_instance().is_maximal_migration,
        )
        require_official_success = official is not None
        local_for_result = local
        if require_official_success and not official.official_success:
            local_for_result = replace(
                local,
                failure_taxonomy=official.failure_reason or "official_eval_failed",
                digest=_official_feedback_text(official),
            )
        result = self.verifier.to_validation_result(
            candidate_id=candidate.candidate_id,
            signals=signals,
            local=local_for_result,
            validator_name=self.name,
            require_official_success=require_official_success,
        )
        # Augment metadata with patch + apply context for downstream finalize/score.
        merged_metadata = dict(result.metadata)
        merged_metadata.update(
            {
                "patch_path": str(patch_path),
                "patch_stats": _patch_stats_to_dict(patch_stats),
                "patch_apply": _apply_check_to_dict(apply_check),
                "branch_root": str(branch.root_dir),
                "verification_root": str(verification_root),
                "verification_cleaned": verification_cleaned,
                "build_outputs_removed": build_outputs_removed,
                "official": _official_to_dict(official),
                "official_required": require_official_success,
            }
        )
        return ValidationResult(
            candidate_id=result.candidate_id,
            status=result.status,
            validator_name=result.validator_name,
            signals=dict(result.signals),
            summary=result.summary,
            raw_output=result.raw_output,
            errors=list(result.errors),
            metadata=merged_metadata,
        )

    def diagnose(
        self, validation: ValidationResult, workspace: WorkspaceHandle
    ) -> FeedbackDigest:
        signals = dict(validation.signals)
        if validation.status == ValidationStatus.PASSED:
            return FeedbackDigest(
                candidate_id=validation.candidate_id,
                failure_type="none",
                severity="info",
                summary=(
                    "strict_success"
                    if signals.get("strict_success")
                    else (validation.summary or "validation_passed")
                ),
                metadata={
                    "signals": signals,
                    "migration_context": migration_context_from_instance(
                        self._require_instance()
                    ).to_dict(),
                },
            )

        failure_type = (
            validation.summary
            if validation.summary and validation.summary != "ok"
            else classify_maven_failure(validation.raw_output)
        )
        severity = (
            "warning"
            if signals.get("compile_success") and not signals.get("test_success")
            else "blocking"
        )
        recommended: list[dict[str, Any]] = []
        anti: list[str] = []
        if not signals.get("patch_delivered"):
            recommended.append(
                {"action": "produce_non_empty_patch", "rationale": "git diff is empty"}
            )
        if signals.get("patch_delivered") and not signals.get("patch_applies"):
            recommended.append(
                {
                    "action": "fix_patch_application",
                    "rationale": "patch fails git apply --check on a clean checkout",
                }
            )
        if signals.get("patch_applies") and not signals.get("compile_success"):
            lowered_output = (validation.raw_output or "").lower()
            if any(
                token in lowered_output
                for token in (
                    "lombok",
                    "delombok",
                    "illegalaccesserror",
                    "jdk.compiler",
                    "com.sun.tools.javac",
                )
            ):
                recommended.append(
                    {
                        "action": "upgrade_lombok_for_target_java",
                        "rationale": failure_type,
                    }
                )
            if any(
                token in lowered_output
                for token in (
                    "javafx.application.application",
                    "javafx.stage.stage",
                    "javafx.scene",
                    "textfield",
                    "pane",
                )
            ):
                recommended.append(
                    {
                        "action": "add_javafx_dependencies",
                        "rationale": failure_type,
                    }
                )
            if "sun.misc.base64" in lowered_output or "base64encoder" in lowered_output:
                recommended.append(
                    {
                        "action": "replace_sun_misc_base64",
                        "rationale": failure_type,
                    }
                )
            if any(
                token in lowered_output
                for token in (
                    "package jdk.jfr.events is not visible",
                    "import jdk.jfr.events",
                    "jdk.jfr.events.exceptionthrownevent",
                    "package sun.reflect.misc is not visible",
                    "does not export it",
                )
            ):
                recommended.append(
                    {
                        "action": "replace_jdk_internal_api",
                        "rationale": failure_type,
                    }
                )
            recommended.append(
                {"action": "fix_compile_error", "rationale": failure_type}
            )
            anti.append("do not repeat the same edit signature on the same files")
        if signals.get("compile_success") and not signals.get("test_success"):
            lowered_output = (validation.raw_output or "").lower()
            if any(
                token in lowered_output
                for token in (
                    "maven-bundle-plugin",
                    "org.apache.felix",
                    "bundleplugin",
                    "bnd",
                    "concurrentmodificationexception",
                )
            ):
                recommended.append(
                    {
                        "action": "upgrade_bundle_plugin",
                        "rationale": failure_type,
                    }
                )
            recommended.append(
                {"action": "fix_test_failure", "rationale": failure_type}
            )
        if signals.get("compile_success") and signals.get("class_version_ok") is False:
            recommended.append(
                {
                    "action": "ensure_maven_compiler_release",
                    "rationale": "compiled class major version mismatches target",
                }
            )
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
        if local_chain_green and not signals.get("official_success"):
            recommended.append(
                {
                    "action": "fix_official_eval_failure",
                    "rationale": failure_type,
                }
            )
            if "#tests" in (validation.raw_output or ""):
                recommended.append(
                    {
                        "action": "fix_official_test_summary",
                        "rationale": (
                            "official evaluator rejected the patch while counting "
                            "tests; keep tests intact and ensure mvn test reports "
                            "the standard test summary"
                        ),
                    }
                )

        # Universal anti-action: the official MigrationBench evaluator
        # (`run_eval.py` → `final_eval.py`) tracks the test count and
        # rejects any patch that drops it (`#tests=-2`). Surface this
        # constraint in the feedback for traceability across all bras.
        # Pre-registered as part of ADR 2026-05-04 (pistes 1+4).
        anti.append("preserve_existing_tests")

        return FeedbackDigest(
            candidate_id=validation.candidate_id,
            failure_type=failure_type or "build_failure",
            severity=severity,
            summary=validation.summary or failure_type,
            evidence=[validation.raw_output[-2000:]] if validation.raw_output else [],
            locations=_locations_from_raw_output(validation.raw_output or ""),
            candidate_causes=[],
            recommended_next_actions=recommended,
            anti_actions=anti,
            metadata={
                "signals": signals,
                "migration_context": migration_context_from_instance(
                    self._require_instance()
                ).to_dict(),
            },
        )

    def finalize(
        self, candidate: Candidate, workspace: WorkspaceHandle
    ) -> ArtifactResult:
        instance = self._require_instance()
        branch = self._open_branch(candidate, workspace)

        patch_path = self._candidate_patch_path(candidate)
        patch_stats: PatchStats = branch.export_patch(patch_path)

        verification_root = (
            branch.root_dir.parent / _VERIFICATION_DIRNAME / candidate.candidate_id
        )
        verification = MigrationBenchWorkspaceV10(
            instance=instance,
            root_dir=verification_root,
            timeout_seconds=self.timeout_seconds,
        )
        try:
            apply_check = self.verifier.verify_patch_applies(
                patch_path=patch_path,
                verification_workspace=verification,
            )
        finally:
            verification_cleaned = self._cleanup_path(verification_root)

        local = self.verifier.verify_local(branch)
        official: OfficialVerificationResult | None = None
        if (
            patch_stats.patch_delivered
            and apply_check.applies
            and local.compile_success
            and local.test_success
            and self.verifier.official_evaluator is not None
        ):
            official_dir = (
                self._artifacts_dir_or_default(workspace)
                / candidate.candidate_id
                / "official"
            )
            official = self.verifier.verify_official(
                instance=instance,
                patch_path=patch_path,
                output_dir=official_dir,
            )

        build_outputs_removed = branch.cleanup_build_outputs()
        signals = self.verifier.build_signals(
            patch_stats=patch_stats,
            patch_apply=apply_check,
            local=local,
            official=official,
            is_maximal=instance.is_maximal_migration,
        )

        status = (
            ArtifactStatus.DELIVERED
            if patch_stats.patch_delivered
            else ArtifactStatus.MISSING
        )
        artifacts: dict[str, Any] = {}
        if patch_path.exists() and patch_path.stat().st_size > 0:
            artifacts["patch.diff"] = patch_path

        signals_path = patch_path.with_name("signals.json")
        signals_path.write_text(
            json.dumps(signals, indent=2, sort_keys=True), encoding="utf-8"
        )
        artifacts["signals.json"] = signals_path

        metadata = {
            "patch_stats": _patch_stats_to_dict(patch_stats),
            "patch_apply": _apply_check_to_dict(apply_check),
            "local": _local_to_dict(local),
            "official": _official_to_dict(official),
            "signals": dict(signals),
            "instance": {
                "instance_id": instance.instance_id,
                "repo_url": instance.repo_url,
                "base_commit": instance.base_commit,
                "target_java": int(instance.target_java),
                "migration_mode": instance.migration_mode,
                "migration_context": migration_context_from_instance(
                    instance
                ).to_dict(),
            },
            "candidate_id": candidate.candidate_id,
            "branch_id": self._branch_id(candidate),
            "verification_cleaned": verification_cleaned,
            "build_outputs_removed": build_outputs_removed,
        }

        return ArtifactResult(
            candidate_id=candidate.candidate_id,
            status=status,
            artifacts=artifacts,
            summary=(
                "strict_success"
                if signals["strict_success"]
                else local.failure_taxonomy
            ),
            metadata=metadata,
        )

    def score(self, artifact: ArtifactResult) -> ScoreResult:
        signals = dict(artifact.metadata.get("signals", {}))
        if not signals or not all(k in signals for k in SIGNAL_KEYS):
            return ScoreResult(
                candidate_id=artifact.candidate_id,
                strict_success=False,
                metrics={"reason": "signals_missing"},
                summary="signals missing",
            )

        strict_success = bool(signals["strict_success"])
        metrics: dict[str, Any] = {key: signals.get(key) for key in SIGNAL_KEYS}
        metrics["artifact_delivered"] = artifact.delivered
        return ScoreResult(
            candidate_id=artifact.candidate_id,
            strict_success=strict_success,
            metrics=metrics,
            summary=(
                "strict_success" if strict_success else (artifact.summary or "failed")
            ),
            metadata={
                "patch_stats": dict(artifact.metadata.get("patch_stats", {})),
                "official": dict(artifact.metadata.get("official", {}) or {}),
            },
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _coerce_instance(self, instance: RunInstance) -> MigrationBenchInstance:
        meta = dict(instance.metadata)
        bench_payload = meta.get("instance")
        if isinstance(bench_payload, MigrationBenchInstance):
            return bench_payload
        if isinstance(bench_payload, dict):
            return MigrationBenchInstance.model_validate(bench_payload)
        # Otherwise expect the metadata itself to carry MB fields.
        required = {"repo_url", "base_commit"}
        if not required.issubset(meta):
            raise ValueError(
                f"RunInstance.metadata must include 'instance' or {sorted(required)}"
            )
        return MigrationBenchInstance.model_validate(
            {
                "instance_id": instance.instance_id,
                "repo_url": meta["repo_url"],
                "base_commit": meta["base_commit"],
                "target_java": meta.get("target_java"),
                "migration_mode": meta.get("migration_mode", "minimal"),
                "stats": meta.get("stats", {}),
                "stratum": meta.get("stratum", {}),
            }
        )

    def _coerce_edit_set(self, payload: dict[str, Any]) -> TypedEditSet:
        raw = payload.get("edit_set", payload.get("edits", payload))
        if isinstance(raw, TypedEditSet):
            return raw
        if isinstance(raw, list):
            return TypedEditSet.model_validate({"edits": raw})
        if isinstance(raw, dict):
            if "edits" in raw and isinstance(raw["edits"], list):
                return TypedEditSet.model_validate(raw)
            return TypedEditSet.model_validate({"edits": [raw]})
        raise TypeError(f"unsupported edits payload type: {type(raw).__name__}")

    def _branch_id(self, candidate: Candidate) -> str:
        explicit = str(candidate.payload.get(_BRANCH_KEY, "")).strip()
        if explicit:
            return explicit
        return f"cand_{candidate.candidate_id}"

    def _parent_branch_id(self, candidate: Candidate) -> str | None:
        raw = str(candidate.payload.get(_PARENT_BRANCH_KEY, "") or "").strip()
        return raw or None

    def _open_branch(
        self, candidate: Candidate, workspace: WorkspaceHandle
    ) -> MigrationBenchWorkspaceV10:
        base = self._require_base_workspace()
        branch_id = self._branch_id(candidate)
        parent = self._parent_branch_id(candidate)
        if parent:
            return base.fork_branch_workspace(
                source_branch_id=parent, branch_id=branch_id
            )
        return base.branch_workspace(branch_id)

    def _candidate_patch_path(self, candidate: Candidate) -> Path:
        artifacts_dir = self._artifacts_dir or Path(
            self._require_base_workspace().root_dir / "artifacts"
        )
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        candidate_dir = artifacts_dir / candidate.candidate_id
        candidate_dir.mkdir(parents=True, exist_ok=True)
        return candidate_dir / "patch.diff"

    def _artifacts_dir_or_default(self, workspace: WorkspaceHandle) -> Path:
        if self._artifacts_dir is not None:
            return self._artifacts_dir
        raw = workspace.metadata.get("artifacts_dir")
        if raw:
            path = Path(str(raw))
            path.mkdir(parents=True, exist_ok=True)
            return path
        fallback = Path(self._require_base_workspace().root_dir) / "artifacts"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

    @staticmethod
    def _cleanup_path(path: Path) -> bool:
        """Best-effort removal for disposable verification workspaces."""

        path = Path(path)
        if not path.exists():
            return False
        shutil.rmtree(path, ignore_errors=True)
        gc.collect()
        return not path.exists()

    def _require_instance(self) -> MigrationBenchInstance:
        if self._instance is None:
            raise WorkspaceError("adapter.setup() must be called before this operation")
        return self._instance

    def _require_base_workspace(self) -> MigrationBenchWorkspaceV10:
        if self._base_workspace is None:
            raise WorkspaceError("adapter.setup() must be called before this operation")
        return self._base_workspace


# ----------------------------------------------------------------------
# Helpers shared by validate / finalize for metadata serialization
# ----------------------------------------------------------------------


def _patch_stats_to_dict(stats: PatchStats) -> dict[str, Any]:
    return {
        "patch_delivered": stats.patch_delivered,
        "patch_lines_added": int(stats.patch_lines_added),
        "patch_lines_deleted": int(stats.patch_lines_deleted),
        "files_modified_count": int(stats.files_modified_count),
    }


def _apply_check_to_dict(apply: PatchApplyResult) -> dict[str, Any]:
    return {
        "applies": bool(apply.applies),
        "reason": apply.reason,
        "log_tail": apply.log_tail,
    }


def _local_to_dict(local: LocalVerificationResult) -> dict[str, Any]:
    payload = asdict(local)
    payload["class_versions"] = list(local.class_versions)
    payload["stages"] = dict(local.stages)
    return payload


def _official_to_dict(
    official: OfficialVerificationResult | None,
) -> dict[str, Any] | None:
    if official is None:
        return None
    payload = asdict(official)
    payload["command"] = list(official.command)
    return payload


def _official_feedback_text(official: OfficialVerificationResult) -> str:
    parts = [official.failure_reason or "official_eval_failed"]
    if official.stdout_tail:
        parts.append(f"stdout_tail:\n{official.stdout_tail}")
    if official.stderr_tail:
        parts.append(f"stderr_tail:\n{official.stderr_tail}")
    if official.log_path:
        parts.append(f"log_path: {official.log_path}")
    return "\n".join(parts)


def _locations_from_raw_output(raw_output: str) -> list[dict[str, str]]:
    locations: list[dict[str, str]] = []
    seen: set[str] = set()
    for pattern in _RAW_OUTPUT_JAVA_PATH_PATTERNS:
        for match in pattern.finditer(raw_output):
            path = match.group("path").replace("\\", "/")
            if "/repo/" in path:
                path = path.split("/repo/", 1)[1]
            if path.startswith("/") or ".." in path.split("/"):
                continue
            if path in seen:
                continue
            seen.add(path)
            locations.append({"path": path})
    return locations


__all__ = ["MigrationBenchAdapterV10"]
