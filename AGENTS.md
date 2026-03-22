# AGENTS.md

This file provides guidance to GitHub Copilot / Codex when working in this repository.

## Project Overview

Stigmergic orchestration framework V3 (runtime overhaul on top of V2 foundations) for a Master's thesis (EMLV).

Current repository state is **Sprint 6 V3**: Sprint 5 runtime + TravelPlanner domain adapter (workspace/tools/evaluator), legacy V0.1 cleanup, TravelPlanner validation tests, and V4 stigmergic-correction features (local sensing, time decay, frequentation, emergent conflict resolution, emergence feedback).

## Current Scope (Sprint 6 V3)

Implemented:
- `core/marker.py` — generic marker model + configurable state machine + `last_active_at`
- `core/marker_store.py` — SQLite (WAL) transactional marker store + locks + differential decay + read tracking/frequentation + pruning + SQL queries + optional session isolation
- `core/decay.py` — intensity/inhibition decay + per-marker-type decay + read-time effective intensity
- `core/schemas.py` — Pydantic schemas for structured LLM/tool outputs
- `core/dependency.py` — DAG validation, topological ordering, unblocked filtering
- `core/reinforcement.py` — success reinforcement + backward propagation + frequentation boost
- `core/emergence.py` — 8-run emergence metrics from tick rows + audit collaboration parsing + feedback adaptations
- `core/guardrails.py` — deep norms (budget, retry limit, lock TTL, traceability)
- `core/audit.py` — append-only JSONL audit trail
- `core/config.py` + `config/default.yaml` — V3 config sections (`reinforcement`, `decompose`, `async`, marker decay map/pruning/session)
- `core/tool_registry.py` — tool contracts + action registry
- `core/pressure.py` — pressure computation + softmax action selection + optional ACO `heuristic_fn`
- `core/environment.py` — runtime wrapper with reinforcement + propagation + time-decayed snapshots + maintenance metrics + lesson marker deposit
- `core/agent.py` — dependency-aware candidate selection (`unblocked_markers`) + episodic memory recall/reinforcement + local-sensing affinity profile
- `core/orchestrator.py` — parallel tick loop + async execution + session_id + emergence summary + emergent conflict resolution + feedback loop
- `adapters/base.py` — domain adapter/objective/workspace contracts
- `adapters/assistant/*` — generic assistant adapter + local workspace context summarization
- `adapters/travelplanner/*` — TravelPlanner workspace + domain tools + adapter + evaluator
- `tools/*` — infrastructure tools (`file_read`, `file_write`, async `bash_exec`, `web_search`, typed `think`, bounded DAG-aware `decompose`)
- `llm/client.py` + `llm/prompts.py` — provider-aware sync+async client with structured response validation, memory/lesson prompt contexts
- `main.py` — multi-adapter CLI (`assistant`, `travelplanner`) with per-run session_id, session DB path, DAG/reinforcement metadata + emergence dashboard
- `config/assistant.yaml` — assistant mode overrides
- `config/travelplanner.yaml` — TravelPlanner mode overrides
- `scripts/setup_travelplanner.py` — dataset/database setup helper
- `tests/unit/*` + `tests/integration/*` — 235 tests passed (TravelPlanner + V4 stigmergic corrections included)

Not implemented yet:
- CodeMigration adapter (V2)
- SWE-bench adapter
- baseline runners aligned with V2 runtime
- Pareto instrumentation aligned with V2 runtime

## Architecture Baseline

### Marker Model

All inter-agent coordination traces are represented as `Marker` objects.

Required fields include:
- identity: `id`, `marker_type`, `target`
- signal: `intensity`, `state`, `payload`
- traceability: `created_by`, `created_at`, `updated_by`, `updated_at`, `last_active_at`
- coordination: `lock_owner`, `lock_tick`, `inhibition`, `retry_count`, `history`

### Marker Store

`core.marker_store.MarkerStore` is the persistence API:
- SQLite file: `pheromones/markers.db`
- `PRAGMA journal_mode=WAL`
- atomic mutations (`BEGIN IMMEDIATE`)
- append-only audit in `pheromones/audit_log.jsonl`

Public methods:
- `upsert_marker`
- `get_marker`
- `get_by_type_target`
- `query_markers`
- `acquire_lock`
- `release_lock`
- `apply_decay`
- `apply_frequentation`
- `maintain_locks`
- `record_read`
- `read_count`
- `snapshot`

### Agent Runtime

`core.orchestrator.Orchestrator` executes the tick loop:
1. environment maintenance (TTL + decay)
   - optional frequentation reinforcement during maintenance
2. snapshot
3. parallel `perceive_and_decide`
4. lock arbitration (sequential or emergent weighted contention resolution)
5. parallel `execute`
6. sequential deposit via `Environment.apply_action_result`
7. optional emergence feedback adaptation
8. stop-condition checks (`all_terminal`, `idle_cycles`, `budget_exhausted`, `max_ticks`)

### Guardrails

Deep norms are environment-enforced, not agent-enforced:
- token/cost budget ceilings
- retry overflow (`retry_count > max_retry_count`)
- lock TTL expiration
- traceability metadata checks

## Project Structure (Current)

```text
core/
  __init__.py
  marker.py
  marker_store.py
  decay.py
  schemas.py
  dependency.py
  reinforcement.py
  emergence.py
  guardrails.py
  audit.py
  config.py
  tool_registry.py
  pressure.py
  environment.py
  agent.py
  orchestrator.py

adapters/
  __init__.py
  base.py
  assistant/
    __init__.py
    adapter.py
    workspace.py
  travelplanner/
    __init__.py
    adapter.py
    workspace.py
    tools.py
    evaluator.py

tools/
  __init__.py
  file_read.py
  file_write.py
  bash_exec.py
  web_search.py
  think.py
  decompose.py

llm/
  __init__.py
  client.py
  prompts.py

config/
  default.yaml
  assistant.yaml
  travelplanner.yaml

scripts/
  setup_travelplanner.py

tests/
  conftest.py
  fixtures/
    mock_adapter.py
  unit/
    test_marker.py
    test_decay.py
    test_guardrails.py
    test_audit.py
    test_marker_store.py
    test_pressure.py
    test_agent.py
    test_orchestrator.py
    test_llm_client.py
    test_file_tools.py
    test_bash_tool.py
    test_assistant_adapter.py
    test_travelplanner_workspace.py
    test_travelplanner_tools.py
    test_travelplanner_adapter.py
    test_travelplanner_evaluator.py
    test_agent_memory.py
    test_emergence.py
    test_config.py
  integration/
    test_assistant_run.py
    test_travelplanner.py
```

## Commands

### Environment

```bash
uv python install 3.11
uv venv --python 3.11 .venv
uv pip install -r requirements.txt
```

### Sprint 6 validation

```bash
uv run pytest tests/unit -v
uv run pytest tests/integration/test_assistant_run.py tests/integration/test_travelplanner.py -v
uv run pytest tests/ -v
uv run python main.py --adapter assistant --objective "Summarize workspace status"
uv run python scripts/setup_travelplanner.py
uv run python main.py --adapter travelplanner --objective "Query 0"
```

## Code Style Guidelines

- Python 3.11+
- type hints on public functions/methods
- PEP 8
- focused functions and explicit errors
- all comments and docs in English

## Error Handling Policy

- Validation errors: raise explicit `ValueError` subclasses
- Store runtime errors: raise `MarkerStoreError`
- Guardrail breaches: raise dedicated guardrail exceptions
- Preserve append-only audit semantics for all marker mutations

## Documentation Requirements

When Sprint scope changes, update all of:
- `AGENTS.md`
- `CLAUDE.md`
- `documentation/construction_log.md`
- relevant ADR in `documentation/decisions/`

For every sprint closure (mandatory):
- update or create `documentation/redisgn_v2/sprint_XX_artifact.md`
- describe the current artifact behavior, interfaces, guardrails, limits, and validation evidence
- keep file naming as `sprint_XX_artifact.md`

## Knowledge Loop (Mandatory)

At end of task:
1. Add exactly one capture entry in `.codex/knowledge/captures.md`
2. Update reusable patterns in `.codex/knowledge/playbook.md`
3. Append one decision in `.codex/knowledge/decision_log.md`

## Git Workflow

- Branch prefix: `codex/`
- Commit convention: `type(scope): description`
- Keep atomic commits by concern (`chore`, `feat`, `test`, `docs`)
