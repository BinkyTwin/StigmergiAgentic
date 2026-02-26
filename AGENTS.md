# AGENTS.md

This file provides guidance to GitHub Copilot / Codex when working in this repository.

## Project Overview

Stigmergic orchestration framework V2 (redesign from scratch) for a Master's thesis (EMLV).

Current repository state is **Sprint 1 V2**: only the generic environment core is implemented.

## Current Scope (Sprint 1 V2)

Implemented:
- `core/marker.py` — generic marker model + configurable state machine
- `core/marker_store.py` — SQLite (WAL) transactional marker store + locks + decay + snapshots
- `core/decay.py` — intensity and inhibition decay
- `core/guardrails.py` — deep norms (budget, retry limit, lock TTL, traceability)
- `core/audit.py` — append-only JSONL audit trail
- `core/config.py` + `config/default.yaml` — loading, merge, strict validation
- `tests/unit/*` — 31 Sprint 1 unit tests

Not implemented yet:
- generic agents
- orchestrator tick loop
- domain adapters (TravelPlanner, CodeMigration, SWE-bench)
- baselines and emergence metrics

## Architecture Baseline

### Marker Model

All inter-agent coordination traces are represented as `Marker` objects.

Required fields include:
- identity: `id`, `marker_type`, `target`
- signal: `intensity`, `state`, `payload`
- traceability: `created_by`, `created_at`, `updated_by`, `updated_at`
- coordination: `lock_owner`, `lock_tick`, `inhibition`, `retry_count`, `history`

### Marker Store

`core.marker_store.MarkerStore` is the only persistence API in Sprint 1:
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

config/
  default.yaml

tests/
  conftest.py
  unit/
    test_marker.py
    test_decay.py
    test_guardrails.py
    test_audit.py
    test_marker_store.py
```

## Commands

### Environment

```bash
uv python install 3.11
uv venv --python 3.11 .venv
uv pip install -r requirements.txt
```

### Sprint 1 validation

```bash
uv run pytest tests/unit -v
uv run pytest tests/unit/test_marker_store.py -v
uv run pytest tests/unit/test_guardrails.py -v
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
