# Sprint 01 — Current Artifact Functioning

## Sprint scope

Sprint 1 V2 delivers only the generic environment core. No agents, orchestrator, adapters, or baselines are implemented yet.

## Current artifact behavior

The artifact is a generic marker-based coordination substrate:

- `Marker` is the shared trace unit.
- `MarkerStore` persists markers in SQLite (`WAL`) with transactional writes.
- Locking is marker-scoped (`lock_owner`, `lock_tick`).
- Decay and lock maintenance are handled by store operations.
- Every mutation is audited in append-only JSONL (`before`/`after`).

## Public interfaces and contracts

### Marker model (`core/marker.py`)

- `Marker` dataclass with validation for:
  - `intensity` in `[0.0, 1.0]`
  - `inhibition` in `[0.0, 1.0]`
  - `retry_count >= 0`
- `StateMachine` for legal state transitions.

### Marker store (`core/marker_store.py`)

Public API:
- `upsert_marker`
- `get_marker`
- `get_by_type_target`
- `query_markers`
- `acquire_lock`
- `release_lock`
- `apply_decay`
- `maintain_locks`
- `snapshot`

### Guardrails (`core/guardrails.py`)

- Budget ceilings (tokens/cost)
- Retry overflow checks
- Lock TTL checks
- Traceability field checks

### Audit (`core/audit.py`)

- `AuditEvent`
- `AuditLog.append` / `AuditLog.read_all`

### Config (`core/config.py` + `config/default.yaml`)

- `load_config`
- `merge_config`
- `validate_config`

## Guardrails and constraints

- Store mutations are transactional (`BEGIN IMMEDIATE`).
- Retry overflow forces skip state.
- Lock conflicts are rejected.
- Traceability can be enforced per mutation.
- Audit stream is append-only and human-readable.

## Known limits / not implemented yet

- No generic agent runtime in Sprint 1.
- No orchestrator tick loop.
- No domain adapters (TravelPlanner, CodeMigration, SWE-bench).
- No emergence metrics or baseline runners.

## Validation evidence

- `uv run pytest tests/unit -v` -> `31 passed`
- `uv run pytest tests/unit/test_marker_store.py -v` -> `12 passed`
- `uv run pytest tests/unit/test_guardrails.py -v` -> `6 passed`
