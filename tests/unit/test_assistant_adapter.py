"""Unit tests for assistant adapter and local workspace wiring."""

from __future__ import annotations

import copy
from pathlib import Path

from adapters.assistant import AssistantAdapter
from adapters.assistant.workspace import LocalWorkspace
from core.marker import Marker
from core.tool_registry import ToolRegistry


def _build_config(config_dict: dict, workspace_root: Path) -> dict:
    config = copy.deepcopy(config_dict)
    config["tools"]["sandbox_root"] = str(workspace_root)
    return config


def test_create_workspace_uses_sandbox_root(tmp_path: Path, config_dict: dict) -> None:
    workspace_root = tmp_path / "workspace"
    config = _build_config(config_dict, workspace_root)
    adapter = AssistantAdapter(config=config)
    workspace = adapter.create_workspace(config)

    (workspace_root / "a.txt").write_text("x", encoding="utf-8")
    assert workspace.root == workspace_root.resolve()
    assert workspace.list_targets() == ["a.txt"]


def test_create_objective_maps_user_input(tmp_path: Path, config_dict: dict) -> None:
    config = _build_config(config_dict, tmp_path / "workspace")
    adapter = AssistantAdapter(config=config)

    objective = adapter.create_objective(
        {"objective": "Write a migration plan", "subtask_count": 4},
        config,
    )
    assert objective.description == "Write a migration plan"
    assert objective.payload["subtask_count"] == 4
    assert objective.objective_id


def test_create_objective_does_not_force_subtask_count(
    tmp_path: Path, config_dict: dict
) -> None:
    config = _build_config(config_dict, tmp_path / "workspace")
    adapter = AssistantAdapter(config=config)

    objective = adapter.create_objective(
        {"objective": "Write a migration plan"}, config
    )
    assert "subtask_count" not in objective.payload


def test_register_tools_exposes_infrastructure_actions(
    tmp_path: Path, config_dict: dict
) -> None:
    config = _build_config(config_dict, tmp_path / "workspace")
    adapter = AssistantAdapter(config=config)
    registry = ToolRegistry()
    adapter.register_tools(registry)

    assert set(registry.action_types()) == {
        "file_read",
        "file_write",
        "bash_exec",
        "web_search",
        "think",
        "decompose",
    }


def test_initial_markers_default_to_decompose_seed(
    tmp_path: Path, config_dict: dict
) -> None:
    config = _build_config(config_dict, tmp_path / "workspace")
    adapter = AssistantAdapter(config=config)
    objective = adapter.create_objective({"objective": "Plan tasks"}, config)

    markers = adapter.initial_markers(objective=objective, agent_id="seed")
    assert len(markers) == 1
    assert markers[0].state == "pending"
    assert "eligible_actions" not in markers[0].payload


def test_initial_markers_with_subtasks_create_children(
    tmp_path: Path, config_dict: dict
) -> None:
    config = _build_config(config_dict, tmp_path / "workspace")
    adapter = AssistantAdapter(config=config)
    objective = adapter.create_objective(
        {
            "objective": "Deliver feature",
            "subtasks": ["Analyze", "Implement", "Verify"],
        },
        config,
    )

    markers = adapter.initial_markers(objective=objective, agent_id="seed")
    assert len(markers) == 4
    root = markers[0]
    assert root.payload["decomposed"] is True
    assert "eligible_actions" not in root.payload
    assert all(
        marker.payload.get("parent_id") == objective.objective_id
        for marker in markers[1:]
    )
    assert all("eligible_actions" not in marker.payload for marker in markers[1:])


def test_evaluate_run_returns_completion_metrics(
    tmp_path: Path, config_dict: dict
) -> None:
    config = _build_config(config_dict, tmp_path / "workspace")
    adapter = AssistantAdapter(config=config)

    snapshot = {
        "markers": [
            Marker(
                id="m1",
                marker_type="task",
                target="m1",
                intensity=0.4,
                state="terminal",
                payload={},
                created_by="a",
                created_at="2026-02-26T12:00:00+00:00",
                updated_by="a",
                updated_at="2026-02-26T12:00:00+00:00",
            ),
            Marker(
                id="m2",
                marker_type="task",
                target="m2",
                intensity=0.8,
                state="active",
                payload={},
                created_by="a",
                created_at="2026-02-26T12:00:00+00:00",
                updated_by="a",
                updated_at="2026-02-26T12:00:00+00:00",
            ),
        ]
    }

    metrics = adapter.evaluate_run(snapshot)
    assert metrics["markers_total"] == 2
    assert metrics["markers_terminal"] == 1
    assert metrics["terminal_ratio"] == 0.5


def test_workspace_context_summary_includes_tree_and_snippets(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    (workspace_root / "README.md").write_text("# Demo\\nContext", encoding="utf-8")
    (workspace_root / "pyproject.toml").write_text("[tool.demo]\\nname='x'", encoding="utf-8")
    (workspace_root / "src").mkdir(parents=True, exist_ok=True)
    (workspace_root / "src" / "app.py").write_text("print('ok')", encoding="utf-8")

    workspace = LocalWorkspace(root=workspace_root)
    summary = workspace.get_context_summary(max_depth=3, max_files=10)

    assert "Workspace Context" in summary
    assert "README.md" in summary
    assert "src/" in summary


def test_workspace_context_summary_respects_tree_depth(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    nested = workspace_root / "a" / "b" / "c"
    nested.mkdir(parents=True, exist_ok=True)
    (nested / "deep.txt").write_text("deep", encoding="utf-8")

    workspace = LocalWorkspace(root=workspace_root)
    shallow = workspace.get_context_summary(max_depth=1, max_files=20)
    deep = workspace.get_context_summary(max_depth=4, max_files=20)

    assert "deep.txt" not in shallow
    assert "deep.txt" in deep


def test_workspace_identifies_key_files(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    (workspace_root / "Makefile").write_text("test:\\n\\tpytest", encoding="utf-8")
    (workspace_root / "requirements.txt").write_text("pytest>=8", encoding="utf-8")

    workspace = LocalWorkspace(root=workspace_root)
    keys = workspace._identify_key_files()

    assert "Makefile" in keys
    assert "requirements.txt" in keys
