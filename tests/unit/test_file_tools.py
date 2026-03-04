"""Unit tests for infrastructure file read/write tools."""

from __future__ import annotations

import asyncio
import copy
from pathlib import Path

from adapters.assistant.workspace import LocalWorkspace
from core.environment import Environment
from core.marker import Marker
from core.marker_store import MarkerStore
from tools.file_read import FileReadTool
from tools.file_write import FileWriteTool


def _make_marker(marker_id: str, payload: dict) -> Marker:
    return Marker(
        id=marker_id,
        marker_type="task",
        target=marker_id,
        intensity=1.0,
        state="pending",
        payload=payload,
        created_by="seed",
        created_at="2026-02-26T12:00:00+00:00",
        updated_by="seed",
        updated_at="2026-02-26T12:00:00+00:00",
        history=["created"],
    )


def _build_environment(
    tmp_path: Path,
    config_dict: dict,
    *,
    max_file_size_bytes: int = 1024,
) -> tuple[Environment, LocalWorkspace, dict]:
    config = copy.deepcopy(config_dict)
    workspace_root = tmp_path / "workspace"
    config["tools"]["sandbox_root"] = str(workspace_root)
    config["tools"]["max_file_size_bytes"] = max_file_size_bytes

    workspace = LocalWorkspace(
        root=workspace_root, max_file_size_bytes=max_file_size_bytes
    )
    store = MarkerStore(db_path=tmp_path / "pheromones" / "markers.db")
    env = Environment(store=store, config=config, workspace=workspace)
    return env, workspace, config


def test_file_read_success(tmp_path: Path, config_dict: dict) -> None:
    env, workspace, config = _build_environment(tmp_path, config_dict)
    (workspace.root / "notes.txt").write_text("hello world", encoding="utf-8")

    marker = _make_marker(
        "read-1",
        {"path": "notes.txt", "eligible_actions": ["file_read"]},
    )
    tool = FileReadTool(config=config)
    result = asyncio.run(
        tool.execute(
            agent_id="agent-1", marker=marker, environment=env, llm_client=None
        )
    )

    assert result.metadata == {}
    assert len(result.marker_updates) == 1
    update = result.marker_updates[0]
    assert update.payload["last_read"]["content"] == "hello world"
    assert update.state == "active"


def test_file_read_eligible_by_default_without_action_filter(
    tmp_path: Path,
    config_dict: dict,
) -> None:
    env, workspace, config = _build_environment(tmp_path, config_dict)
    (workspace.root / "notes.txt").write_text("hello world", encoding="utf-8")

    marker = _make_marker("read-default", {"path": "notes.txt"})
    tool = FileReadTool(config=config)
    assert tool.is_eligible(marker) is True

    result = asyncio.run(
        tool.execute(
            agent_id="agent-1", marker=marker, environment=env, llm_client=None
        )
    )
    assert result.metadata == {}
    assert result.marker_updates[0].payload["last_read"]["content"] == "hello world"


def test_file_read_rejects_path_escape(tmp_path: Path, config_dict: dict) -> None:
    env, _, config = _build_environment(tmp_path, config_dict)
    marker = _make_marker(
        "read-2",
        {"path": "../outside.txt", "eligible_actions": ["file_read"]},
    )
    tool = FileReadTool(config=config)
    result = asyncio.run(
        tool.execute(
            agent_id="agent-1", marker=marker, environment=env, llm_client=None
        )
    )
    assert result.metadata.get("failed") is True
    assert "path_outside_workspace" in str(result.metadata.get("reason"))


def test_file_read_rejects_oversized_file(tmp_path: Path, config_dict: dict) -> None:
    env, workspace, config = _build_environment(
        tmp_path, config_dict, max_file_size_bytes=4
    )
    (workspace.root / "big.txt").write_text("12345", encoding="utf-8")

    marker = _make_marker(
        "read-3",
        {"path": "big.txt", "eligible_actions": ["file_read"]},
    )
    tool = FileReadTool(config=config)
    result = asyncio.run(
        tool.execute(
            agent_id="agent-1", marker=marker, environment=env, llm_client=None
        )
    )
    assert result.metadata.get("failed") is True
    assert "file_too_large" in str(result.metadata.get("reason"))


def test_file_write_overwrite_success(tmp_path: Path, config_dict: dict) -> None:
    env, workspace, config = _build_environment(tmp_path, config_dict)
    marker = _make_marker(
        "write-1",
        {
            "write": {"mode": "overwrite", "path": "draft.txt", "content": "first"},
            "eligible_actions": ["file_write"],
        },
    )
    tool = FileWriteTool(config=config)
    result = asyncio.run(
        tool.execute(
            agent_id="agent-1", marker=marker, environment=env, llm_client=None
        )
    )

    assert result.metadata == {}
    assert (workspace.root / "draft.txt").read_text(encoding="utf-8") == "first"


def test_file_write_append_success(tmp_path: Path, config_dict: dict) -> None:
    env, workspace, config = _build_environment(tmp_path, config_dict)
    path = workspace.root / "append.txt"
    path.write_text("A", encoding="utf-8")

    marker = _make_marker(
        "write-2",
        {
            "write": {"mode": "append", "path": "append.txt", "content": "B"},
            "eligible_actions": ["file_write"],
        },
    )
    tool = FileWriteTool(config=config)
    result = asyncio.run(
        tool.execute(
            agent_id="agent-1", marker=marker, environment=env, llm_client=None
        )
    )

    assert result.metadata == {}
    assert path.read_text(encoding="utf-8") == "AB"


def test_file_write_replace_text_success(tmp_path: Path, config_dict: dict) -> None:
    env, workspace, config = _build_environment(tmp_path, config_dict)
    path = workspace.root / "replace.txt"
    path.write_text("hello hello", encoding="utf-8")

    marker = _make_marker(
        "write-3",
        {
            "write": {
                "mode": "replace_text",
                "path": "replace.txt",
                "old": "hello",
                "new": "bye",
                "count": 1,
            },
            "eligible_actions": ["file_write"],
        },
    )
    tool = FileWriteTool(config=config)
    result = asyncio.run(
        tool.execute(
            agent_id="agent-1", marker=marker, environment=env, llm_client=None
        )
    )

    assert result.metadata == {}
    assert path.read_text(encoding="utf-8") == "bye hello"
    assert result.marker_updates[0].payload["last_write"]["replacements"] == 1


def test_file_write_rejects_outside_workspace(
    tmp_path: Path, config_dict: dict
) -> None:
    env, _, config = _build_environment(tmp_path, config_dict)
    marker = _make_marker(
        "write-4",
        {
            "write": {"mode": "overwrite", "path": "../hack.txt", "content": "oops"},
            "eligible_actions": ["file_write"],
        },
    )
    tool = FileWriteTool(config=config)
    result = asyncio.run(
        tool.execute(
            agent_id="agent-1", marker=marker, environment=env, llm_client=None
        )
    )
    assert result.metadata.get("failed") is True
    assert "path_outside_workspace" in str(result.metadata.get("reason"))


def test_file_write_rejects_size_limit(tmp_path: Path, config_dict: dict) -> None:
    env, _, config = _build_environment(tmp_path, config_dict, max_file_size_bytes=3)
    marker = _make_marker(
        "write-5",
        {
            "write": {"mode": "overwrite", "path": "small.txt", "content": "abcd"},
            "eligible_actions": ["file_write"],
        },
    )
    tool = FileWriteTool(config=config)
    result = asyncio.run(
        tool.execute(
            agent_id="agent-1", marker=marker, environment=env, llm_client=None
        )
    )
    assert result.metadata.get("failed") is True
    assert "file_too_large" in str(result.metadata.get("reason"))
