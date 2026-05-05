from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from types import SimpleNamespace

from adapters.migrationbench.adapter import MigrationBenchAdapter
from adapters.migrationbench.schemas import MigrationBenchInstance, TypedEdit, TypedEditSet
import adapters.migrationbench.tools as migration_tools
from adapters.migrationbench.tools import (
    ApplyPatchCandidateTool,
    ClassifyBuildFailureTool,
    ProposePatchCandidateTool,
    RepairPatchCandidateTool,
    RunBuildValidationTool,
    SelectPatchCandidateTool,
    _feedback_digest,
    classify_maven_failure,
    parse_typed_edit_set,
)
from adapters.migrationbench.workspace import CommandResult, MigrationBenchWorkspace
from adapters.base import Objective
from core.environment import Environment
from core.marker import Marker
from core.marker_store import MarkerStore
from core.tool_registry import ActionResult
from scripts.migrationbench_cleanup import clean_stigmergic_artifacts


def _git_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "source"
    repo.mkdir()
    (repo / "pom.xml").write_text(
        "<project><properties>"
        "<maven.compiler.source>1.8</maven.compiler.source>"
        "<maven.compiler.target>1.8</maven.compiler.target>"
        "</properties></project>",
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "pom.xml"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    return repo, commit


def _instance(repo: Path, commit: str) -> MigrationBenchInstance:
    return MigrationBenchInstance(
        instance_id="local_repo",
        repo_url=str(repo),
        base_commit=commit,
        target_java=17,
        migration_mode="minimal",
    )


class FakeLLM:
    """Small async LLM double that returns raw content or raises exceptions."""

    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls = 0

    async def acall(self, **kwargs):
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return SimpleNamespace(
            content=str(response),
            parsed=None,
            tokens_used=11,
            cost_usd=0.001,
        )


def _patch_marker(instance: MigrationBenchInstance) -> Marker:
    return Marker(
        id="migrationbench::local::patch::b1",
        marker_type="patch_hypothesis",
        target="patch::b1",
        intensity=1.0,
        state="pending",
        payload={
            "objective_id": "migrationbench::local",
            "instance": instance.model_dump(),
            "branch_id": "b1",
            "parent_branch_id": None,
            "attempt": 0,
            "typed_edits": TypedEditSet(
                edits=[
                    TypedEdit(
                        type="replace_text",
                        path="pom.xml",
                        old="<maven.compiler.source>1.8</maven.compiler.source>",
                        new="<maven.compiler.source>17</maven.compiler.source>",
                    )
                ]
            ).model_dump(),
            "eligible_actions": ["apply_patch_candidate"],
        },
        created_by="test",
        created_at="2026-01-01T00:00:00+00:00",
        updated_by="test",
        updated_at="2026-01-01T00:00:00+00:00",
        history=["created"],
    )


def test_v7_initial_markers_use_closed_repair_colony_flow(tmp_path: Path) -> None:
    repo, commit = _git_repo(tmp_path)
    config = {"migrationbench": {"framework": "stigmergic_v7_repair_colony"}}
    adapter = MigrationBenchAdapter(config=config)
    objective = Objective(
        objective_id="migrationbench::local",
        description="Migrate local repo",
        payload={"instance": _instance(repo, commit).model_dump()},
    )

    markers = adapter.initial_markers(objective=objective, agent_id="seed")

    actions = [marker.payload["eligible_actions"][0] for marker in markers]
    assert actions == [
        "inspect_repository",
        "localize_migration_surface",
        "propose_patch_candidate",
    ]
    assert not any(action == "finalize_patch" for action in actions)


def test_failure_classifier_is_stable() -> None:
    assert classify_maven_failure("Non-parseable POM /tmp/pom.xml") == "pom_parse_error"
    assert (
        classify_maven_failure("Could not resolve dependencies for project")
        == "dependency_resolution_error"
    )
    assert classify_maven_failure("[ERROR] COMPILATION ERROR cannot find symbol") == "compile_error"
    assert classify_maven_failure("There are test failures. See surefire-reports") == "test_failure"
    assert classify_maven_failure("Unsupported class file major version 65") == "class_version_error"


def test_parse_typed_edit_set_normalizes_common_llm_variants() -> None:
    replacement = parse_typed_edit_set(
        {
            "edits": [
                {
                    "file": "pom.xml",
                    "replace": {
                        "old": "<maven.compiler.source>1.8</maven.compiler.source>",
                        "new": "<maven.compiler.source>17</maven.compiler.source>",
                    },
                }
            ]
        }
    )
    rewrite = parse_typed_edit_set({"file": "src/main/java/App.java", "content": "class App {}"})

    assert replacement.edits[0].path == "pom.xml"
    assert replacement.edits[0].type == "replace_text"
    assert replacement.edits[0].expected_replacements == 1
    assert rewrite.edits[0].type == "write_file"
    assert rewrite.edits[0].content == "class App {}"


def test_feedback_digest_keeps_maven_signal_under_cap() -> None:
    noisy = "\n".join(
        ["Downloading artifact"] * 300
        + [
            "[ERROR] COMPILATION ERROR",
            "[ERROR] /src/Foo.java:[1,1] cannot find symbol",
            "Caused by: java.lang.IllegalStateException",
            "Tests run: 4, Failures: 1",
            "BUILD FAILURE",
        ]
    )

    digest = _feedback_digest(noisy, max_chars=4500)

    assert "[ERROR] COMPILATION ERROR" in digest
    assert "Tests run: 4" in digest
    assert len(digest) <= 4500


def test_apply_patch_candidate_uses_isolated_branch_workspace(tmp_path: Path) -> None:
    repo, commit = _git_repo(tmp_path)
    instance = _instance(repo, commit)
    workspace = MigrationBenchWorkspace(instance=instance, root_dir=tmp_path / "workspace")
    workspace.prepare(force=True)
    store = MarkerStore(db_path=tmp_path / "markers.db")
    env = Environment(store=store, config={}, workspace=workspace)
    marker = _patch_marker(instance)

    action_result = asyncio.run(
        ApplyPatchCandidateTool().execute(
            agent_id="agent-1",
            marker=marker,
            environment=env,
            llm_client=None,
        )
    )

    updated = action_result.marker_updates[0]
    branch_file = workspace.branch_workspace("b1").read_file("pom.xml")
    base_file = workspace.read_file("pom.xml")
    assert updated.state == "planning"
    assert "17" in branch_file
    assert "1.8" in base_file


def test_propose_patch_candidate_retries_after_schema_validation_error(tmp_path: Path) -> None:
    repo, commit = _git_repo(tmp_path)
    instance = _instance(repo, commit)
    workspace = MigrationBenchWorkspace(instance=instance, root_dir=tmp_path / "workspace")
    workspace.prepare(force=True)
    env = Environment(store=MarkerStore(db_path=tmp_path / "markers.db"), config={}, workspace=workspace)
    marker = Marker(
        id="migrationbench::local::propose",
        marker_type="task",
        target="propose",
        intensity=1.0,
        state="pending",
        payload={
            "objective_id": "migrationbench::local",
            "instance": instance.model_dump(),
            "eligible_actions": ["propose_patch_candidate"],
        },
        created_by="seed",
        created_at="2026-01-01T00:00:00+00:00",
        updated_by="seed",
        updated_at="2026-01-01T00:00:00+00:00",
        history=["created"],
    )
    llm = FakeLLM(
        [
            '{"edits":[{"file":"pom.xml","new":"<project/>"}]}',
            '{"file":"pom.xml","content":"<project/>"}',
        ]
    )

    result = asyncio.run(
        ProposePatchCandidateTool().execute(
            agent_id="agent-1",
            marker=marker,
            environment=env,
            llm_client=llm,
        )
    )

    hypothesis = next(update for update in result.marker_updates if update.marker_type == "patch_hypothesis")
    assert llm.calls == 2
    assert result.metadata["llm_calls"] == 2
    assert hypothesis.payload["llm_failure"] == "recovered_after_schema_retry"
    assert hypothesis.payload["eligible_actions"] == ["apply_patch_candidate"]


def test_propose_patch_candidate_rejects_empty_or_irrelevant_edits(tmp_path: Path) -> None:
    repo, commit = _git_repo(tmp_path)
    instance = _instance(repo, commit)
    workspace = MigrationBenchWorkspace(instance=instance, root_dir=tmp_path / "workspace")
    workspace.prepare(force=True)
    env = Environment(
        store=MarkerStore(db_path=tmp_path / "markers.db"),
        config={"orchestrator": {"targeted_repair": {"max_cycles": 2}}},
        workspace=workspace,
    )
    marker = Marker(
        id="migrationbench::local::propose",
        marker_type="task",
        target="propose",
        intensity=1.0,
        state="pending",
        payload={"objective_id": "migrationbench::local", "eligible_actions": ["propose_patch_candidate"]},
        created_by="seed",
        created_at="2026-01-01T00:00:00+00:00",
        updated_by="seed",
        updated_at="2026-01-01T00:00:00+00:00",
        history=["created"],
    )
    llm = FakeLLM(['{"edits":[{"file":"README.md","content":"noop"}]}'])

    result = asyncio.run(
        ProposePatchCandidateTool().execute(
            agent_id="agent-1",
            marker=marker,
            environment=env,
            llm_client=llm,
        )
    )

    assert all(update.marker_type != "patch_hypothesis" for update in result.marker_updates)
    assert result.marker_updates[0].payload["failure_taxonomy"] == "empty_or_irrelevant_edits"
    assert result.validation is not None
    assert result.validation.repair is not None
    assert result.validation.repair.eligible_actions == ["propose_patch_candidate"]


def test_build_failure_creates_repair_marker(tmp_path: Path, monkeypatch) -> None:
    repo, commit = _git_repo(tmp_path)
    instance = _instance(repo, commit)
    workspace = MigrationBenchWorkspace(instance=instance, root_dir=tmp_path / "workspace")
    workspace.prepare(force=True)
    store = MarkerStore(db_path=tmp_path / "markers.db")
    config = {
        "orchestrator": {"targeted_repair": {"enabled": True, "max_cycles": 40}},
        "migrationbench": {"build_command": "mvn clean verify"},
    }
    env = Environment(
        store=store,
        config=config,
        workspace=workspace,
        state_machine=MigrationBenchAdapter(config=config).define_state_machine(),
    )
    marker = _patch_marker(instance)
    marker.payload["eligible_actions"] = ["run_build_validation"]
    marker.payload["patch_applies"] = True
    store.upsert_marker(marker, agent_id="seed")

    def fake_run_maven(self, command: str, *, timeout_seconds: float | None = None):
        return SimpleNamespace(
            returncode=1,
            stdout="[ERROR] COMPILATION ERROR cannot find symbol",
            stderr="",
            runtime_seconds=0.1,
            ok=False,
        )

    monkeypatch.setattr(
        MigrationBenchWorkspace,
        "run_maven",
        fake_run_maven,
    )
    build_result = asyncio.run(
        RunBuildValidationTool(config=config).execute(
            agent_id="agent-1",
            marker=marker,
            environment=env,
            llm_client=None,
        )
    )
    env.apply_action_result(agent_id="agent-1", result=build_result)
    classified = env.store.get_marker(marker.id)
    assert classified is not None
    classify_result = asyncio.run(
        ClassifyBuildFailureTool().execute(
            agent_id="agent-1",
            marker=classified,
            environment=env,
            llm_client=None,
        )
    )
    env.apply_action_result(agent_id="agent-1", result=classify_result)

    repairs = env.store.query_markers(marker_type="patch_hypothesis")
    assert any(marker.id.startswith("repair::") for marker in repairs)
    repair = next(marker for marker in repairs if marker.id.startswith("repair::"))
    assert repair.payload["failure_taxonomy"] == "compile_error"
    assert repair.payload["eligible_actions"] == ["repair_patch_candidate"]


def test_build_validation_requires_exact_java17_class_major_version(tmp_path: Path, monkeypatch) -> None:
    repo, commit = _git_repo(tmp_path)
    instance = _instance(repo, commit)
    instance.stats["num_test_cases"] = 2
    workspace = MigrationBenchWorkspace(instance=instance, root_dir=tmp_path / "workspace")
    workspace.prepare(force=True)
    branch = workspace.branch_workspace("b1", force=True)
    branch.apply_typed_edits(
        TypedEditSet(
            edits=[
                TypedEdit(
                    type="write_file",
                    path="pom.xml",
                    content="<project><modelVersion>4.0.0</modelVersion></project>",
                )
            ]
        )
    )
    marker = _patch_marker(instance)
    marker.payload["eligible_actions"] = ["run_build_validation"]
    marker.payload["patch_applies"] = True
    env = Environment(
        store=MarkerStore(db_path=tmp_path / "markers.db"),
        config={"migrationbench": {"build_command": "mvn clean verify"}},
        workspace=workspace,
    )

    def fake_run_maven(self, command: str, *, timeout_seconds: float | None = None):
        return CommandResult(
            command=["bash", "-lc", command],
            returncode=0,
            stdout="BUILD SUCCESS",
            stderr="",
            runtime_seconds=0.1,
        )

    monkeypatch.setattr(MigrationBenchWorkspace, "run_maven", fake_run_maven)
    monkeypatch.setattr(migration_tools, "_class_major_versions", lambda workspace: {52, 61})
    monkeypatch.setattr(migration_tools, "_surefire_test_count", lambda workspace: 2)

    result = asyncio.run(
        RunBuildValidationTool(config={"migrationbench": {"build_command": "mvn clean verify"}}).execute(
            agent_id="agent-1",
            marker=marker,
            environment=env,
            llm_client=None,
        )
    )

    updated = result.marker_updates[0]
    assert updated.payload["compile_success"] is True
    assert updated.payload["test_success"] is True
    assert updated.payload["compiled_major_version_ok"] is False
    assert updated.payload["build_success"] is False
    assert updated.payload["eligible_actions"] == ["classify_build_failure"]


def test_build_validation_selects_only_when_official_like_checks_pass(tmp_path: Path, monkeypatch) -> None:
    repo, commit = _git_repo(tmp_path)
    instance = _instance(repo, commit)
    instance.stats["num_test_cases"] = 1
    workspace = MigrationBenchWorkspace(instance=instance, root_dir=tmp_path / "workspace")
    workspace.prepare(force=True)
    workspace.branch_workspace("b1", force=True)
    marker = _patch_marker(instance)
    marker.payload["eligible_actions"] = ["run_build_validation"]
    marker.payload["patch_applies"] = True
    env = Environment(
        store=MarkerStore(db_path=tmp_path / "markers.db"),
        config={"migrationbench": {"build_command": "mvn clean verify"}},
        workspace=workspace,
    )

    def fake_run_maven(self, command: str, *, timeout_seconds: float | None = None):
        return CommandResult(
            command=["bash", "-lc", command],
            returncode=0,
            stdout="BUILD SUCCESS",
            stderr="",
            runtime_seconds=0.1,
        )

    monkeypatch.setattr(MigrationBenchWorkspace, "run_maven", fake_run_maven)
    monkeypatch.setattr(migration_tools, "_class_major_versions", lambda workspace: {61})
    monkeypatch.setattr(migration_tools, "_surefire_test_count", lambda workspace: 1)

    result = asyncio.run(
        RunBuildValidationTool(config={"migrationbench": {"build_command": "mvn clean verify"}}).execute(
            agent_id="agent-1",
            marker=marker,
            environment=env,
            llm_client=None,
        )
    )

    updated = result.marker_updates[0]
    assert updated.payload["build_success"] is True
    assert updated.payload["compiled_major_version_ok"] is True
    assert updated.payload["test_count_non_decreasing"] is True
    assert updated.payload["eligible_actions"] == ["select_patch_candidate"]


def test_select_patch_candidate_rejects_unvalidated_patch() -> None:
    marker = Marker(
        id="migrationbench::local::patch::b1",
        marker_type="patch_hypothesis",
        target="patch::b1",
        intensity=1.0,
        state="verified",
        payload={
            "objective_id": "migrationbench::local",
            "branch_id": "b1",
            "build_success": False,
            "patch_applies": True,
            "eligible_actions": ["select_patch_candidate"],
        },
        created_by="seed",
        created_at="2026-01-01T00:00:00+00:00",
        updated_by="seed",
        updated_at="2026-01-01T00:00:00+00:00",
        history=["created"],
    )

    result = asyncio.run(
        SelectPatchCandidateTool().execute(
            agent_id="agent-1",
            marker=marker,
            environment=SimpleNamespace(config={}),
            llm_client=None,
        )
    )

    updated = result.marker_updates[0]
    assert updated.state == "terminal"
    assert updated.payload["selected_for_official_eval"] is False
    assert updated.payload["failure_taxonomy"] == "selection_rejected_unvalidated_patch"


def test_select_patch_candidate_allows_explicit_best_partial_patch() -> None:
    marker = Marker(
        id="migrationbench::local::patch::b1::best_partial_finalize",
        marker_type="patch_hypothesis",
        target="patch::b1",
        intensity=1.0,
        state="pending",
        payload={
            "objective_id": "migrationbench::local",
            "branch_id": "b1",
            "build_success": False,
            "patch_applies": True,
            "best_partial_finalization": True,
            "failure_reason": "repair_cap_reached:compile_error",
            "eligible_actions": ["select_patch_candidate"],
        },
        created_by="seed",
        created_at="2026-01-01T00:00:00+00:00",
        updated_by="seed",
        updated_at="2026-01-01T00:00:00+00:00",
        history=["created"],
    )

    result = asyncio.run(
        SelectPatchCandidateTool().execute(
            agent_id="agent-1",
            marker=marker,
            environment=SimpleNamespace(config={}),
            llm_client=None,
        )
    )

    updated = result.marker_updates[0]
    assert updated.state == "planning"
    assert updated.payload["selected_for_official_eval"] is True
    assert updated.payload["eligible_actions"] == ["finalize_evaluated_patch"]


def test_repair_patch_candidate_blocks_repeated_failed_file_pattern(tmp_path: Path) -> None:
    repo, commit = _git_repo(tmp_path)
    instance = _instance(repo, commit)
    workspace = MigrationBenchWorkspace(instance=instance, root_dir=tmp_path / "workspace")
    workspace.prepare(force=True)
    workspace.branch_workspace("b1", force=True)
    store = MarkerStore(db_path=tmp_path / "markers.db")
    env = Environment(store=store, config={}, workspace=workspace)
    for idx in range(2):
        prior = _patch_marker(instance)
        prior.id = f"migrationbench::local::patch::prior{idx}"
        prior.payload["branch_id"] = f"prior{idx}"
        prior.payload["failure_taxonomy"] = "compile_error"
        prior.payload["edit_application"] = {"files_modified": ["pom.xml"]}
        prior.payload["attempt"] = idx
        store.upsert_marker(prior, agent_id="seed")
    repair = _patch_marker(instance)
    repair.id = "repair::migrationbench::local::patch::b1::attempt::1"
    repair.payload["failure_taxonomy"] = "compile_error"
    repair.payload["repair_feedback"] = ["[ERROR] COMPILATION ERROR"]
    repair.payload["eligible_actions"] = ["repair_patch_candidate"]
    llm = FakeLLM(
        [
            '{"edits":[{"file":"pom.xml","old":"<maven.compiler.source>1.8</maven.compiler.source>",'
            '"new":"<maven.compiler.source>17</maven.compiler.source>"}]}'
        ]
    )

    result = asyncio.run(
        RepairPatchCandidateTool().execute(
            agent_id="agent-1",
            marker=repair,
            environment=env,
            llm_client=llm,
        )
    )

    updated = result.marker_updates[0]
    assert updated.state == "terminal"
    assert updated.payload["failure_taxonomy"] == "anti_loop_repeated_repair"
    assert all(update.marker_type != "patch_hypothesis" for update in result.marker_updates[1:])


def test_empty_repair_retry_targets_root_patch_without_nested_repair_id(tmp_path: Path) -> None:
    repo, commit = _git_repo(tmp_path)
    instance = _instance(repo, commit)
    workspace = MigrationBenchWorkspace(instance=instance, root_dir=tmp_path / "workspace")
    workspace.prepare(force=True)
    store = MarkerStore(db_path=tmp_path / "markers.db")
    env = Environment(
        store=store,
        config={
            "orchestrator": {
                "targeted_repair": {
                    "enabled": True,
                    "max_cycles": 3,
                    "repair_marker_intensity": 0.95,
                }
            },
            "llm": {"max_tokens_total": 1000, "max_budget_usd": 1.0},
        },
        workspace=workspace,
        state_machine=MigrationBenchAdapter(
            config={"migrationbench": {"framework": "stigmergic_v7_repair_colony"}}
        ).define_state_machine(),
    )
    root = _patch_marker(instance)
    root.payload["failure_taxonomy"] = "build_failure"
    root.payload["eligible_actions"] = ["repair_patch_candidate"]
    store.upsert_marker(root, agent_id="seed")
    repair = Marker.from_dict(root.to_dict())
    repair.id = f"repair::{root.id}::{root.id}::attempt::1"
    repair.payload = {
        **root.payload,
        "repair_target_id": root.id,
        "repair_source_id": root.id,
        "repair_attempt": 1,
        "repair_feedback": ["previous build failed"],
        "eligible_actions": ["repair_patch_candidate"],
    }
    store.upsert_marker(repair, agent_id="seed")
    llm = FakeLLM(['{"edits": []}'])

    result = asyncio.run(
        RepairPatchCandidateTool().execute(
            agent_id="agent-1",
            marker=repair,
            environment=env,
            llm_client=llm,
        )
    )
    env.apply_action_result(agent_id="agent-1", result=result)

    assert store.get_marker(f"repair::{root.id}::{root.id}::attempt::2") is not None
    assert not any(marker.id.startswith("repair::repair::") for marker in store.query_markers())


def test_repair_patch_candidate_strips_repair_bookkeeping_from_new_branch(tmp_path: Path) -> None:
    repo, commit = _git_repo(tmp_path)
    instance = _instance(repo, commit)
    workspace = MigrationBenchWorkspace(instance=instance, root_dir=tmp_path / "workspace")
    workspace.prepare(force=True)
    store = MarkerStore(db_path=tmp_path / "markers.db")
    env = Environment(store=store, config={}, workspace=workspace)
    repair = _patch_marker(instance)
    repair.id = "repair::migrationbench::local::patch::b1::migrationbench::local::patch::b1::attempt::1"
    repair.payload.update(
        {
            "failure_taxonomy": "compile_error",
            "repair_target_id": "migrationbench::local::patch::b1",
            "repair_source_id": "migrationbench::local::patch::b1",
            "repair_attempt": 1,
            "repair_feedback": ["[ERROR] COMPILATION ERROR"],
            "eligible_actions": ["repair_patch_candidate"],
        }
    )
    llm = FakeLLM(
        [
            '{"edits":[{"type":"replace_text","path":"pom.xml",'
            '"old":"<maven.compiler.target>1.8</maven.compiler.target>",'
            '"new":"<maven.compiler.target>17</maven.compiler.target>"}]}'
        ]
    )

    result = asyncio.run(
        RepairPatchCandidateTool().execute(
            agent_id="agent-1",
            marker=repair,
            environment=env,
            llm_client=llm,
        )
    )

    hypothesis = next(update for update in result.marker_updates if update.id.endswith("::patch::b2"))
    assert hypothesis.payload["branch_id"] == "b2"
    assert "repair_target_id" not in hypothesis.payload
    assert "repair_source_id" not in hypothesis.payload
    assert "repair_attempt" not in hypothesis.payload


def test_v7_lessons_are_disabled_by_workflow_default(tmp_path: Path, config_dict: dict) -> None:
    config = dict(config_dict)
    config["migrationbench"] = {"workflow": "v7_repair_colony"}
    store = MarkerStore(db_path=tmp_path / "markers.db")
    seed = Marker(
        id="migrationbench::local::patch::b1",
        marker_type="patch_hypothesis",
        target="patch::b1",
        intensity=1.0,
        state="verified",
        payload={"failure_reason": "ok"},
        created_by="seed",
        created_at="2026-01-01T00:00:00+00:00",
        updated_by="seed",
        updated_at="2026-01-01T00:00:00+00:00",
        history=["created"],
    )
    store.upsert_marker(seed, agent_id="seed")
    env = Environment(store=store, config=config)
    completed = Marker.from_dict(seed.to_dict())
    completed.state = "terminal"

    env.apply_action_result(
        agent_id="agent-1",
        result=ActionResult(
            action_type="finalize_evaluated_patch",
            marker_updates=[completed],
            metadata={"quality_score": 0.99},
        ),
    )

    assert store.get_marker("lesson::migrationbench::local::patch::b1") is None


def test_force_clean_removes_marker_audit_and_artifacts(tmp_path: Path) -> None:
    out_dir = tmp_path / "instance_artifacts"
    artifacts = out_dir / "artifacts"
    artifacts.mkdir(parents=True)
    for name in ["markers.db", "markers.db-wal", "markers.db-shm", "audit_log.jsonl"]:
        (out_dir / name).write_text("stale", encoding="utf-8")
    (artifacts / "patch.diff").write_text("stale patch", encoding="utf-8")

    clean_stigmergic_artifacts(out_dir)

    assert out_dir.exists()
    assert not artifacts.exists()
    for name in ["markers.db", "markers.db-wal", "markers.db-shm", "audit_log.jsonl"]:
        assert not (out_dir / name).exists()
