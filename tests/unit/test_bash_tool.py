"""Unit tests for guarded bash execution tool."""

from __future__ import annotations

import asyncio
import copy
from pathlib import Path

from adapters.assistant.workspace import LocalWorkspace
from core.environment import Environment
from core.marker import Marker
from core.marker_store import MarkerStore
from tools.bash_exec import BashExecTool


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


def _build_environment(tmp_path: Path, config_dict: dict) -> tuple[Environment, LocalWorkspace, dict]:
    config = copy.deepcopy(config_dict)
    workspace_root = tmp_path / "workspace"
    config["tools"]["sandbox_root"] = str(workspace_root)
    config["tools"]["allowed_commands"] = ["python"]
    config["tools"]["bash_timeout_seconds"] = 1

    workspace = LocalWorkspace(root=workspace_root)
    store = MarkerStore(db_path=tmp_path / "pheromones" / "markers.db")
    env = Environment(store=store, config=config, workspace=workspace)
    return env, workspace, config


def test_bash_exec_success(tmp_path: Path, config_dict: dict) -> None:
    env, _, config = _build_environment(tmp_path, config_dict)
    marker = _make_marker(
        "bash-1",
        {
            "command": "python -c \"print('ok')\"",
            "eligible_actions": ["bash_exec"],
        },
    )
    tool = BashExecTool(config=config)
    result = asyncio.run(
        tool.execute(agent_id="agent-1", marker=marker, environment=env, llm_client=None)
    )
    assert result.metadata == {}
    assert result.marker_updates[0].payload["last_bash"]["stdout"].strip() == "ok"


def test_bash_exec_rejects_non_whitelisted_command(tmp_path: Path, config_dict: dict) -> None:
    env, _, config = _build_environment(tmp_path, config_dict)
    marker = _make_marker(
        "bash-2",
        {
            "command": "ls -la",
            "eligible_actions": ["bash_exec"],
        },
    )
    tool = BashExecTool(config=config)
    result = asyncio.run(
        tool.execute(agent_id="agent-1", marker=marker, environment=env, llm_client=None)
    )
    assert result.metadata.get("failed") is True
    assert "command_not_allowed" in str(result.metadata.get("reason"))


def test_bash_exec_captures_stderr(tmp_path: Path, config_dict: dict) -> None:
    env, _, config = _build_environment(tmp_path, config_dict)
    marker = _make_marker(
        "bash-3",
        {
            "command": "python -c \"import sys; sys.stderr.write('err\\n')\"",
            "eligible_actions": ["bash_exec"],
        },
    )
    tool = BashExecTool(config=config)
    result = asyncio.run(
        tool.execute(agent_id="agent-1", marker=marker, environment=env, llm_client=None)
    )
    assert result.metadata == {}
    assert "err" in result.marker_updates[0].payload["last_bash"]["stderr"]


def test_bash_exec_times_out(tmp_path: Path, config_dict: dict) -> None:
    env, _, config = _build_environment(tmp_path, config_dict)
    marker = _make_marker(
        "bash-4",
        {
            "command": "python -c \"import time; time.sleep(0.4)\"",
            "timeout_seconds": 0.05,
            "eligible_actions": ["bash_exec"],
        },
    )
    tool = BashExecTool(config=config)
    result = asyncio.run(
        tool.execute(agent_id="agent-1", marker=marker, environment=env, llm_client=None)
    )
    assert result.metadata.get("failed") is True
    assert result.metadata.get("reason") == "timeout"


def test_bash_exec_preserves_non_zero_return_code(tmp_path: Path, config_dict: dict) -> None:
    env, _, config = _build_environment(tmp_path, config_dict)
    marker = _make_marker(
        "bash-5",
        {
            "command": "python -c \"import sys; sys.exit(3)\"",
            "eligible_actions": ["bash_exec"],
        },
    )
    tool = BashExecTool(config=config)
    result = asyncio.run(
        tool.execute(agent_id="agent-1", marker=marker, environment=env, llm_client=None)
    )
    assert result.metadata == {}
    assert result.marker_updates[0].payload["last_bash"]["returncode"] == 3


def test_bash_exec_runs_in_workspace_cwd(tmp_path: Path, config_dict: dict) -> None:
    env, workspace, config = _build_environment(tmp_path, config_dict)
    (workspace.root / "probe.txt").write_text("ok", encoding="utf-8")

    marker = _make_marker(
        "bash-6",
        {
            "command": "python -c \"from pathlib import Path; print(Path('probe.txt').exists())\"",
            "eligible_actions": ["bash_exec"],
        },
    )
    tool = BashExecTool(config=config)
    result = asyncio.run(
        tool.execute(agent_id="agent-1", marker=marker, environment=env, llm_client=None)
    )
    assert result.metadata == {}
    assert result.marker_updates[0].payload["last_bash"]["stdout"].strip() == "True"
