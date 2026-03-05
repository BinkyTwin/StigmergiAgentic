"""Integration tests for assistant adapter end-to-end runtime."""

from __future__ import annotations

import copy
from types import SimpleNamespace

from adapters.assistant import AssistantAdapter
from core.agent import StigmergicAgent
from core.environment import Environment
from core.marker import Marker
from core.marker_store import MarkerStore
from core.orchestrator import Orchestrator
from core.tool_registry import ToolRegistry


class FakeLLMClient:
    """Deterministic fake client for integration runs."""

    def call(self, prompt: str, system: str | None = None) -> SimpleNamespace:
        if "Decompose the following objective" in prompt:
            content = '{"subtasks":[{"title":"Create draft"},{"title":"Check output"}]}'
        elif "Create draft" in prompt:
            content = (
                '{"analysis":"Create an initial artifact.",'
                '"write":{"mode":"overwrite","path":"draft.txt","content":"hello"}}'
            )
        elif "Check output" in prompt:
            content = (
                '{"analysis":"Validate generated artifact.",'
                '"command":"python -c \\"from pathlib import Path; '
                'print(Path(\\"draft.txt\\").read_text())\\""}'
            )
        else:
            content = '{"analysis":"Reasoning step completed."}'
        return SimpleNamespace(
            content=content,
            tokens_used=5,
            cost_usd=0.001,
            model="fake-model",
            latency_ms=1,
        )

    def extract_code_block(self, text: str) -> str:
        return text


def _build_runtime(
    tmp_path, config_dict: dict
) -> tuple[dict, AssistantAdapter, Environment, ToolRegistry]:
    config = copy.deepcopy(config_dict)
    config["agents"]["num_agents"] = 1
    config["agents"]["selection_temperature"] = 0.0
    config["orchestrator"]["parallel"] = False
    config["orchestrator"]["max_ticks"] = 40
    config["orchestrator"]["idle_cycles_to_stop"] = 5
    config["tools"]["sandbox_root"] = str(tmp_path / "workspace")
    config["tools"]["allowed_commands"] = ["python"]

    adapter = AssistantAdapter(config=config)
    workspace = adapter.create_workspace(config)
    store = MarkerStore(db_path=tmp_path / "pheromones" / "markers.db")
    env = Environment(
        store=store,
        config=config,
        workspace=workspace,
        state_machine=adapter.define_state_machine(),
    )

    registry = ToolRegistry()
    adapter.register_tools(registry)
    return config, adapter, env, registry


def test_assistant_run_end_to_end_with_mock_llm(tmp_path, config_dict: dict) -> None:
    config, adapter, env, registry = _build_runtime(tmp_path, config_dict)
    objective = adapter.create_objective(
        {"objective": "Prepare a concise delivery plan."}, config
    )
    assert "subtask_count" not in objective.payload
    for marker in adapter.initial_markers(objective=objective, agent_id="seed"):
        env.store.upsert_marker(marker=marker, agent_id="seed")

    agent = StigmergicAgent(agent_id="agent-1", tool_registry=registry, config=config)
    orchestrator = Orchestrator(
        environment=env,
        agents=[agent],
        config=config,
        llm_client=FakeLLMClient(),
    )
    result = orchestrator.run_sync()

    assert result.stop_reason == "all_terminal"
    assert result.total_ticks >= 1
    assert all(marker.state == "terminal" for marker in result.final_snapshot.markers)


def test_decompose_creates_submarkers_in_store(tmp_path, config_dict: dict) -> None:
    config, adapter, env, registry = _build_runtime(tmp_path, config_dict)
    config["orchestrator"]["max_ticks"] = 1
    objective = adapter.create_objective(
        {"objective": "Break this task into steps."}, config
    )
    for marker in adapter.initial_markers(objective=objective, agent_id="seed"):
        env.store.upsert_marker(marker=marker, agent_id="seed")

    agent = StigmergicAgent(agent_id="agent-1", tool_registry=registry, config=config)
    result = Orchestrator(
        environment=env,
        agents=[agent],
        config=config,
        llm_client=FakeLLMClient(),
    ).run_sync()

    assert result.total_ticks == 1
    child = env.store.get_marker(f"{objective.objective_id}::subtask::1")
    assert child is not None


def test_infrastructure_tool_executes_in_full_loop(tmp_path, config_dict: dict) -> None:
    config, _, env, registry = _build_runtime(tmp_path, config_dict)
    config["orchestrator"]["max_ticks"] = 1
    write_marker = Marker(
        id="write-loop",
        marker_type="task",
        target="write-loop",
        intensity=1.0,
        state="pending",
        payload={
            "eligible_actions": ["file_write"],
            "write": {
                "mode": "overwrite",
                "path": "generated.txt",
                "content": "hello",
            },
        },
        created_by="seed",
        created_at="2026-02-26T12:00:00+00:00",
        updated_by="seed",
        updated_at="2026-02-26T12:00:00+00:00",
        history=["created"],
    )
    env.store.upsert_marker(write_marker, agent_id="seed")

    agent = StigmergicAgent(agent_id="agent-1", tool_registry=registry, config=config)
    Orchestrator(
        environment=env,
        agents=[agent],
        config=config,
        llm_client=FakeLLMClient(),
    ).run_sync()

    assert (env.workspace.root / "generated.txt").read_text(encoding="utf-8") == "hello"
    updated = env.store.get_marker("write-loop")
    assert updated is not None
    assert updated.state == "active"


def test_assistant_evaluation_summary_matches_snapshot(
    tmp_path, config_dict: dict
) -> None:
    config, adapter, env, registry = _build_runtime(tmp_path, config_dict)
    objective = adapter.create_objective(
        {"objective": "Summarize repo status."}, config
    )
    for marker in adapter.initial_markers(objective=objective, agent_id="seed"):
        env.store.upsert_marker(marker=marker, agent_id="seed")

    agent = StigmergicAgent(agent_id="agent-1", tool_registry=registry, config=config)
    result = Orchestrator(
        environment=env,
        agents=[agent],
        config=config,
        llm_client=FakeLLMClient(),
    ).run_sync()

    metrics = adapter.evaluate_run({"markers": result.final_snapshot.markers})
    assert metrics["markers_total"] == len(result.final_snapshot.markers)
    assert 0.0 <= metrics["terminal_ratio"] <= 1.0
