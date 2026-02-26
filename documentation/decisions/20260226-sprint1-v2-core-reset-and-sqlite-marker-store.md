# ADR 009: Sprint 1 V2 Core Reset and SQLite Marker Store

- **Date**: 2026-02-26
- **Status**: Accepted
- **Scope**: V2 redesign baseline (Sprint 1)

## Context

The previous runtime (V0.1) was specialized around Python 2 -> Python 3 migration with fixed roles and JSON pheromone files. The V2 redesign requires a domain-agnostic stigmergic core with stronger concurrency and auditability guarantees.

## Decision

1. Perform a hard reset of runtime code in the new branch:
- remove `agents/`, `environment/`, `stigmergy/`, `main.py`, and legacy `tests/test_*.py`

2. Implement a generic core environment in `core/`:
- `Marker` + configurable `StateMachine`
- `MarkerStore` backed by SQLite with WAL
- `GuardrailEngine` for deep norms (budget, retry, lock TTL, traceability)
- append-only JSONL `AuditLog`
- validated configuration loading/merging (`core/config.py` + `config/default.yaml`)

3. Validate Sprint 1 with a strict unit-test gate only:
- `uv run pytest tests/unit -v` (31 tests)

## Consequences

### Positive
- Robust transactional storage and read concurrency via SQLite WAL
- Unified, generic marker schema for future adapters
- Strong traceability and governance from Sprint 1 onward
- Clear baseline for Sprint 2+ without legacy coupling

### Tradeoffs
- No runtime backward compatibility with V0.1 on this branch
- Additional migration work needed later for orchestrator and adapters

## Validation Evidence

- `uv run pytest tests/unit -v` -> `31 passed`
- `uv run pytest tests/unit/test_marker_store.py -v` -> `12 passed`
- `uv run pytest tests/unit/test_guardrails.py -v` -> `6 passed`
