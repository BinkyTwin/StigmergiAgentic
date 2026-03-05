# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project Overview

Stigmergic orchestration framework V3 for thesis research (EMLV).

The codebase is currently at **Sprint 5 V3** (Sprint 4 runtime overhaul + episodic memory, emergence telemetry, lesson markers, and heuristic-aware pressure).

## Sprint 5 V3 Status (2026-03-04)

Implemented modules:
- `core/marker.py`
- `core/marker_store.py`
- `core/decay.py`
- `core/schemas.py`
- `core/dependency.py`
- `core/reinforcement.py`
- `core/emergence.py`
- `core/guardrails.py`
- `core/audit.py`
- `core/config.py`
- `core/tool_registry.py`
- `core/pressure.py`
- `core/environment.py`
- `core/agent.py`
- `core/orchestrator.py`
- `adapters/base.py`
- `adapters/assistant/__init__.py`
- `adapters/assistant/adapter.py`
- `adapters/assistant/workspace.py`
- `tools/__init__.py`
- `tools/file_read.py`
- `tools/file_write.py`
- `tools/bash_exec.py`
- `tools/web_search.py`
- `tools/think.py`
- `tools/decompose.py`
- `llm/client.py`
- `llm/prompts.py`
- `config/default.yaml`
- `config/assistant.yaml`
- `main.py`
- `tests/unit/*` + `tests/integration/test_assistant_run.py` (168 tests)

Validated gate:
- `uv run pytest tests/unit -v` -> 164 passed
- `uv run pytest tests/integration/test_assistant_run.py -v` -> 4 passed
- `uv run pytest tests/ -v` -> 168 passed

## Design Principles

- Coordination medium first: markers are the single shared trace primitive.
- Separation of concerns: adapters provide domain logic through tool contracts.
- Strong governance: traceability, budget checks, retry limits, lock TTL.
- Auditability by default: append-only JSONL events with before/after payloads.
- Role-free agents: same agent logic, specialization through pressures and marker availability.

## Runtime Model

```text
snapshot -> decide (parallel) -> lock arbitration -> execute (parallel)
-> deposit (transactional) -> maintain (TTL + decay)
```

Stop conditions:
- `all_terminal`
- `idle_cycles`
- `budget_exhausted`
- `max_ticks`

## Marker State Machine Defaults

```text
pending -> active -> completed -> verified -> terminal
pending -> active -> failed -> retry -> pending
any -> skipped
any -> escalated
```

The state machine remains configurable and validated through `StateMachine`.

## Persistence Model

- Store: SQLite file `pheromones/markers.db`
- Mode: `WAL`
- Transaction model: `BEGIN IMMEDIATE` on all mutations
- Audit stream: `pheromones/audit_log.jsonl`

## Current Public API Surface

### `core.marker`
- `Marker`
- `StateMachine`
- `InvalidMarkerError`
- `InvalidTransitionError`

### `core.marker_store`
- `MarkerStore`
- `MarkerStoreError`

### `core.guardrails`
- `GuardrailEngine`
- `BudgetExceededError`
- `TraceabilityError`
- `ScopeLockError`

### `core.tool_registry`
- `Decision`
- `ActionResult`
- `Tool`
- `ToolRegistry`

### `core.pressure`
- `compute_pressures`
- `select_action`

`compute_pressures` now accepts optional `heuristic_fn(marker, action)` for ACO heuristic substitution.

### `core.environment`
- `Environment`
- `EnvironmentSnapshot`

### `core.agent`
- `StigmergicAgent`
- `AgentMemory`
- `MemoryEntry`

### `core.orchestrator`
- `Orchestrator`
- `TickRow`
- `OrchestratorResult`

`OrchestratorResult` now includes `emergence_summary`.

### `llm.client`
- `LLMClient`
- `LLMResponse`
- `ModelPricing`

### `tools`
- `register_infrastructure_tools`
- `FileReadTool`
- `FileWriteTool`
- `BashExecTool`
- `WebSearchTool`
- `ThinkTool`
- `DecomposeTool`

### `adapters.assistant`
- `AssistantAdapter`
- `LocalWorkspace`

## Commands

### Setup

```bash
uv python install 3.11
uv venv --python 3.11 .venv
uv pip install -r requirements.txt
```

### Test (Sprint 5)

```bash
uv run pytest tests/unit -v
uv run pytest tests/integration/test_assistant_run.py -v
uv run pytest tests/ -v
uv run python main.py --adapter assistant --objective "Create a short plan"
```

## Coding Rules

- Python 3.11+, strict type hints
- explicit exception classes for invalid state/contract violations
- concise docstrings on public classes/methods
- no hidden side-effects in store APIs
- preserve append-only audit semantics

## Documentation and Thesis Traceability

For each significant delivery:
- append `documentation/construction_log.md`
- add/update ADR in `documentation/decisions/`
- keep `AGENTS.md` and `CLAUDE.md` synchronized

For each sprint closure (mandatory):
- update or create `documentation/redisgn_v2/sprint_XX_artifact.md`
- include: sprint scope, current artifact behavior, public interfaces, guardrails, known limits, and validation evidence

## Knowledge Governance

Use project-local knowledge only:
- `.codex/knowledge/captures.md`
- `.codex/knowledge/playbook.md`
- `.codex/knowledge/decision_log.md`

Add exactly one capture per task, with 1-3 reusable patterns and concrete evidence.
