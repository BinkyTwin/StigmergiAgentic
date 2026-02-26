# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project Overview

Stigmergic orchestration framework V2 for thesis research (EMLV).

The codebase is currently at **Sprint 1 V2** (core environment only). Legacy V0.1 runtime was removed on this branch to start a clean redesign baseline.

## Sprint 1 V2 Status (2026-02-26)

Implemented modules:
- `core/marker.py`
- `core/marker_store.py`
- `core/decay.py`
- `core/guardrails.py`
- `core/audit.py`
- `core/config.py`
- `config/default.yaml`
- `tests/unit/*` (31 tests)

Validated gate:
- `uv run pytest tests/unit -v` -> 31 passed

## Design Principles

- Coordination medium first: markers are the single shared trace primitive.
- Separation of concerns: domain logic is out of scope for Sprint 1.
- Strong governance: traceability, budget checks, retry limits, lock TTL.
- Auditability by default: append-only JSONL events with before/after payloads.

## Marker State Machine Defaults

```text
pending -> active -> completed -> verified -> terminal
pending -> active -> failed -> retry -> pending
any -> skipped
any -> escalated
```

The state machine is configurable and validated through `StateMachine`.

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

### `core.audit`
- `AuditEvent`
- `AuditLog`

### `core.config`
- `load_config`
- `merge_config`
- `validate_config`

## Commands

### Setup

```bash
uv python install 3.11
uv venv --python 3.11 .venv
uv pip install -r requirements.txt
```

### Test (Sprint 1)

```bash
uv run pytest tests/unit -v
uv run pytest tests/unit/test_marker_store.py -v
uv run pytest tests/unit/test_guardrails.py -v
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

## Knowledge Governance

Use project-local knowledge only:
- `.codex/knowledge/captures.md`
- `.codex/knowledge/playbook.md`
- `.codex/knowledge/decision_log.md`

Add exactly one capture per task, with 1-3 reusable patterns and concrete evidence.
