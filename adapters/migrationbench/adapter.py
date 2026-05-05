"""Domain adapter for repository-level Java migration on MigrationBench."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from adapters.base import DomainAdapter, Objective, Workspace
from core.marker import Marker, StateMachine, utc_now_iso
from core.tool_registry import ToolRegistry
from tools.think import ThinkTool

from .schemas import MigrationBenchInstance
from .tools import (
    ApplyPatchCandidateTool,
    ClassifyBuildFailureTool,
    FinalizeEvaluatedPatchTool,
    FinalizePatchTool,
    InspectRepositoryTool,
    LocalizeMigrationSurfaceTool,
    ProposePatchCandidateTool,
    ProposePatchTool,
    RepairPatchCandidateTool,
    RunBuildTool,
    RunBuildValidationTool,
    SelectPatchCandidateTool,
)
from .evaluator import MigrationBenchEvaluator, build_strict_contract
from .workspace import MigrationBenchWorkspace


class MigrationBenchAdapter(DomainAdapter):
    """Patch-centric MigrationBench adapter for V6 static evaluation."""

    def __init__(self, *, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self._workspace: MigrationBenchWorkspace | None = None

    def create_workspace(self, config: dict[str, Any]) -> Workspace:
        cfg = dict(config.get("migrationbench", {}))
        raw_instance = cfg.get("instance")
        if not isinstance(raw_instance, dict):
            raise ValueError("migrationbench.instance is required")
        instance = MigrationBenchInstance.model_validate(raw_instance)
        root_dir = cfg.get(
            "workspace_dir",
            f"workspaces/migrationbench/stigmergic_v6_static/{instance.instance_id}/seed42",
        )
        workspace = MigrationBenchWorkspace(
            instance=instance,
            root_dir=root_dir,
            timeout_seconds=float(cfg.get("workspace_timeout_seconds", 600)),
        )
        workspace.prepare(force=bool(cfg.get("force_workspace", False)))
        self._workspace = workspace
        return workspace

    def create_objective(
        self,
        user_input: dict[str, Any],
        config: dict[str, Any],
    ) -> Objective:
        if self._workspace is None:
            self.create_workspace(config)
        assert self._workspace is not None
        instance = self._workspace.instance
        description = (
            f"Migrate {instance.repo_url} at {instance.base_commit} "
            f"to Java {instance.target_java} ({instance.migration_mode})."
        )
        return Objective(
            objective_id=f"migrationbench::{instance.instance_id}::{uuid4()}",
            description=description,
            payload={"instance": instance.model_dump()},
        )

    def register_tools(self, registry: ToolRegistry) -> None:
        if self._is_v7_colony():
            registry.register(InspectRepositoryTool())
            registry.register(LocalizeMigrationSurfaceTool())
            registry.register(ProposePatchCandidateTool())
            registry.register(ApplyPatchCandidateTool())
            registry.register(RunBuildValidationTool(config=self.config))
            registry.register(ClassifyBuildFailureTool())
            registry.register(RepairPatchCandidateTool())
            registry.register(SelectPatchCandidateTool())
            registry.register(FinalizeEvaluatedPatchTool(config=self.config))
            hint_tools = [
                "inspect_repository",
                "localize_migration_surface",
                "propose_patch_candidate",
                "apply_patch_candidate",
                "run_build_validation",
                "classify_build_failure",
                "repair_patch_candidate",
                "select_patch_candidate",
                "finalize_evaluated_patch",
            ]
        else:
            registry.register(InspectRepositoryTool())
            registry.register(ProposePatchTool())
            registry.register(RunBuildTool(config=self.config))
            registry.register(FinalizePatchTool(config=self.config))
            hint_tools = [
                "inspect_repository",
                "propose_patch",
                "run_build",
                "finalize_patch",
            ]
        registry.register(
            ThinkTool(
                config=self.config,
                available_hint_tools=hint_tools,
            )
        )

    def define_state_machine(self) -> StateMachine:
        return StateMachine(
            transitions={
                "pending": {"planning", "terminal", "skipped", "escalated"},
                "planning": {"planning", "terminal", "skipped", "escalated"},
                "terminal": {"terminal", "planning", "skipped", "escalated"},
                "skipped": {"skipped"},
                "escalated": {"escalated"},
            }
        )

    def initial_markers(self, objective: Objective, agent_id: str) -> list[Marker]:
        if self._is_v7_colony():
            return self._initial_markers_v7(objective=objective, agent_id=agent_id)

        now = utc_now_iso()
        base_payload = {
            "objective": objective.description,
            "objective_id": objective.objective_id,
            "instance": dict(objective.payload.get("instance", {})),
        }
        inspect_id = f"{objective.objective_id}::inspect_repository"
        patch_id = f"{objective.objective_id}::propose_patch"
        build_id = f"{objective.objective_id}::run_build"
        finalize_id = f"{objective.objective_id}::finalize_patch"
        specs = [
            (inspect_id, 1.0, [], ["inspect_repository"]),
            (patch_id, 0.95, [inspect_id], ["propose_patch"]),
            (build_id, 0.85, [patch_id], ["run_build"]),
            (finalize_id, 0.8, [patch_id], ["finalize_patch"]),
        ]
        markers: list[Marker] = []
        for marker_id, intensity, depends_on, actions in specs:
            markers.append(
                Marker(
                    id=marker_id,
                    marker_type="task",
                    target=marker_id,
                    intensity=float(intensity),
                    state="pending",
                    payload={
                        **base_payload,
                        "depends_on": depends_on,
                        "eligible_actions": actions,
                    },
                    created_by=agent_id,
                    created_at=now,
                    updated_by=agent_id,
                    updated_at=now,
                    history=["created"],
                )
            )
        return markers

    def _initial_markers_v7(self, objective: Objective, agent_id: str) -> list[Marker]:
        """Seed only discovery/localization/proposal; patch branches emerge later."""
        now = utc_now_iso()
        base_payload = {
            "objective": objective.description,
            "objective_id": objective.objective_id,
            "instance": dict(objective.payload.get("instance", {})),
            "workflow": "v7_repair_colony",
        }
        inspect_id = f"{objective.objective_id}::inspect_repository"
        localize_id = f"{objective.objective_id}::localize_migration_surface"
        propose_id = f"{objective.objective_id}::propose_patch_candidate"
        specs = [
            (inspect_id, 1.0, [], ["inspect_repository"]),
            (localize_id, 0.95, [inspect_id], ["localize_migration_surface"]),
            (propose_id, 0.9, [localize_id], ["propose_patch_candidate"]),
        ]
        markers: list[Marker] = []
        for marker_id, intensity, depends_on, actions in specs:
            markers.append(
                Marker(
                    id=marker_id,
                    marker_type="task",
                    target=marker_id,
                    intensity=float(intensity),
                    state="pending",
                    payload={
                        **base_payload,
                        "depends_on": depends_on,
                        "eligible_actions": actions,
                    },
                    created_by=agent_id,
                    created_at=now,
                    updated_by=agent_id,
                    updated_at=now,
                    history=["created"],
                )
            )
        return markers

    def evaluate_run(self, env_snapshot: dict[str, Any]) -> dict[str, Any]:
        markers = env_snapshot.get("markers", [])
        final_payload: dict[str, Any] = {}
        for marker in markers:
            marker_id = str(getattr(marker, "id", ""))
            marker_type = str(getattr(marker, "marker_type", ""))
            payload = dict(getattr(marker, "payload", {}))
            if (
                marker_type == "task"
                and (
                    marker_id.endswith("::finalize_patch")
                    or marker_id.endswith("::finalize_evaluated_patch")
                )
            ):
                final_payload = payload
                break
        if not final_payload and self._is_v7_colony():
            final_payload = self._evaluate_best_partial_payload(markers)
        strict = bool(final_payload.get("strict_success", False))
        return {
            "strict_success_rate": 1.0 if strict else 0.0,
            "official_success_rate": 1.0 if final_payload.get("official_success") else 0.0,
            "artifact_delivery_rate": 1.0 if final_payload.get("artifact_delivered") else 0.0,
            "patch_applies_rate": 1.0 if final_payload.get("patch_applies") else 0.0,
            "failure_reason": str(final_payload.get("failure_reason", "missing_final_patch")),
            "final_contract": final_payload,
        }

    def _evaluate_best_partial_payload(self, markers: Iterable[Any]) -> dict[str, Any]:
        """V7.2 best-partial fallback with the same artifact/eval contract as finalize.

        The first V7.2 version only surfaced the selected marker payload after the run.
        That made `patch_applies` visible but skipped patch export and official eval, so
        best-partial patches had no path to `strict_success`. This method turns the best
        branch into a real `patch.diff` and evaluates it through the common strict contract.
        """
        best = self._synthesize_best_partial_payload(markers)
        if not best:
            return {}
        if self._workspace is None:
            best["artifact_delivered"] = bool(best.get("artifact_delivered", False))
            best["patch_delivered"] = bool(best.get("patch_delivered", False))
            best.setdefault("failure_reason", "best_partial_workspace_missing")
            return best

        workspace = self._workspace
        cfg = dict(self.config.get("migrationbench", {}))
        branch_id = str(best.get("branch_id", "b1")).strip() or "b1"
        try:
            branch = workspace.branch_workspace(branch_id, force=False)
            output_dir = Path(cfg.get("artifact_dir", workspace.root_dir / "artifacts"))
            patch_path = output_dir / f"{branch_id}_best_partial_patch.diff"
            final_patch_path = output_dir / "patch.diff"
            official_dir = output_dir / "official"
            stats = branch.export_patch(patch_path)
            if patch_path.exists():
                final_patch_path.parent.mkdir(parents=True, exist_ok=True)
                final_patch_path.write_text(
                    patch_path.read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
            patch_applies, patch_reason = branch.verify_patch_applies(
                patch_path=patch_path,
                verification_root=branch.root_dir / "verification",
                force=True,
            )
            evaluator = MigrationBenchEvaluator(
                migrationbench_root=cfg.get("official_root", "external/MigrationBench"),
                run_official=bool(cfg.get("run_official_eval", True)),
                timeout_seconds=float(cfg.get("official_timeout_seconds", 1800)),
            )
            official = evaluator.evaluate_patch(
                instance=workspace.instance,
                patch_path=patch_path,
                output_dir=official_dir,
                patch_stats=stats,
                patch_applies=patch_applies,
                patch_apply_reason=patch_reason,
                maven_command=str(
                    cfg.get("official_maven_command", "cd {root_dir}; mvn clean verify")
                ),
            )
            llm_cfg = dict(self.config.get("llm", {}))
            contract = build_strict_contract(
                instance=workspace.instance,
                framework=str(cfg.get("framework", "stigmergic_v7_repair_colony")),
                provider=str(llm_cfg.get("provider", "")),
                model=str(llm_cfg.get("model", "")),
                seed=int(cfg.get("seed", 42)),
                patch_path=final_patch_path,
                patch_stats=stats,
                patch_applies=patch_applies,
                patch_apply_reason=patch_reason,
                official=official,
                extra={
                    "best_branch_id": branch_id,
                    "branch_count": self._branch_count(markers),
                    "failure_taxonomy": best.get("failure_taxonomy", ""),
                    "build_feedback_digest": best.get("build_feedback_digest", ""),
                    "best_partial_finalization": True,
                },
            )
            contract["best_partial_finalization"] = True
            return contract
        except Exception as exc:  # noqa: BLE001
            best["artifact_delivered"] = bool(best.get("artifact_delivered", False))
            best["patch_delivered"] = bool(best.get("patch_delivered", False))
            best["failure_reason"] = f"best_partial_eval_failed:{type(exc).__name__}"
            best["best_partial_eval_error"] = str(exc)
            return best

    @staticmethod
    def _synthesize_best_partial_payload(markers: Iterable[Any]) -> dict[str, Any]:
        candidates: list[tuple[float, str, dict[str, Any]]] = []
        for marker in markers:
            if str(getattr(marker, "marker_type", "")) != "patch_hypothesis":
                continue
            payload = dict(getattr(marker, "payload", {}))
            score = float(payload.get("quality_score", 0.0) or 0.0)
            if payload.get("compile_success"):
                score += 0.6
            if payload.get("patch_applies"):
                score += 0.3
            if payload.get("typed_edits", {}).get("edits"):
                score += 0.05
            branch = str(payload.get("branch_id", "")).strip() or "b0"
            candidates.append((score, branch, payload))
        if not candidates:
            return {}
        candidates.sort(key=lambda item: (-item[0], item[1]))
        best = dict(candidates[0][2])
        best.setdefault("failure_reason", "best_partial_finalization")
        best["best_partial_finalization"] = True
        best.setdefault("strict_success", False)
        best.setdefault("official_success", False)
        best.setdefault("patch_applies", bool(best.get("patch_applies", False)))
        return best

    @staticmethod
    def _branch_count(markers: Iterable[Any]) -> int:
        return len(
            {
                str(getattr(marker, "payload", {}).get("branch_id", "")).strip()
                for marker in markers
                if str(getattr(marker, "marker_type", "")) == "patch_hypothesis"
                and str(getattr(marker, "payload", {}).get("branch_id", "")).strip()
            }
        )

    def _is_v7_colony(self) -> bool:
        migration_cfg = dict(self.config.get("migrationbench", {}))
        framework = str(migration_cfg.get("framework", "")).strip()
        workflow = str(migration_cfg.get("workflow", "")).strip()
        return framework == "stigmergic_v7_repair_colony" or workflow == "v7_repair_colony"
