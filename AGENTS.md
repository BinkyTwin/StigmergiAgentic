# AGENTS.md

This file provides guidance to GitHub Copilot / Codex when working in this repository.

## Project Overview

Stigmergic orchestration framework V2 (redesign from scratch) for a Master's thesis (EMLV).

Current repository state is **Sprint 2 V2**: generic environment core + generic agents/orchestrator runtime.

## Current Scope (Sprint 2 V2)

Implemented:
- `core/marker.py` — generic marker model + configurable state machine
- `core/marker_store.py` — SQLite (WAL) transactional marker store + locks + decay + snapshots
- `core/decay.py` — intensity and inhibition decay
- `core/guardrails.py` — deep norms (budget, retry limit, lock TTL, traceability)
- `core/audit.py` — append-only JSONL audit trail
- `core/config.py` + `config/default.yaml` — loading, merge, strict validation
- `core/tool_registry.py` — tool contracts + action registry
- `core/pressure.py` — pressure computation + softmax action selection
- `core/environment.py` — runtime environment wrapper (store + guardrails + state machine)
- `core/agent.py` — homogeneous stigmergic agent (perceive/decide/execute)
- `core/orchestrator.py` — parallel tick loop + lock conflict resolution + stop conditions
- `adapters/base.py` — domain adapter/objective/workspace contracts
- `llm/client.py` + `llm/prompts.py` — provider-aware LLM client and prompt helpers
- `tests/unit/*` — 61 Sprint 1+2 unit tests

Not implemented yet:
- TravelPlanner adapter
- CodeMigration adapter (V2)
- SWE-bench adapter
- baseline runners aligned with V2 runtime
- emergence and Pareto instrumentation aligned with V2 runtime

## Architecture Baseline

### Marker Model

All inter-agent coordination traces are represented as `Marker` objects.

Required fields include:
- identity: `id`, `marker_type`, `target`
- signal: `intensity`, `state`, `payload`
- traceability: `created_by`, `created_at`, `updated_by`, `updated_at`
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
- `maintain_locks`
- `snapshot`

### Agent Runtime

`core.orchestrator.Orchestrator` executes the tick loop:
1. environment maintenance (TTL + decay)
2. snapshot
3. parallel `perceive_and_decide`
4. lock arbitration
5. parallel `execute`
6. sequential deposit via `Environment.apply_action_result`
7. stop-condition checks (`all_terminal`, `idle_cycles`, `budget_exhausted`, `max_ticks`)

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

llm/
  __init__.py
  client.py
  prompts.py

config/
  default.yaml

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
```

## Commands

### Environment

```bash
uv python install 3.11
uv venv --python 3.11 .venv
uv pip install -r requirements.txt
```

### Sprint 2 validation

```bash
uv run pytest tests/unit -v
uv run pytest tests/unit/test_agent.py tests/unit/test_orchestrator.py -v
uv run pytest tests/unit/test_pressure.py tests/unit/test_llm_client.py -v
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
