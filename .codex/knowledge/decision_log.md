# Decision Log

## 2026-02-10

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Adopt JSON pheromone store with POSIX file locking and append-only audit trail for Sprint 1.
- `rationale`: Aligns with architecture plan artifacts while ensuring concurrency safety and RQ3 traceability.
- `alternatives_rejected`: Plain unlocked JSON store, full SQLite migration in Sprint 1.
- `linked_adr`: `documentation/decisions/20260210-sprint1-environment-medium.md`

## 2026-02-11

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Implement Sprint 2 validation as mock-first tests with optional non-blocking `live_api` smoke coverage.
- `rationale`: Keeps agent behavior tests deterministic while preserving a direct OpenRouter wiring check path.
- `alternatives_rejected`: Fully live API blocking tests, fully mocked suite without any smoke check.
- `linked_adr`: `documentation/decisions/20260210-sprint2-agents-unitaires.md`

## 2026-02-12

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Adopt Sprint 3 adaptive fallback classification and mountpoint-safe Docker execution to satisfy the blocking gate on `docopt/docopt@0.6.2`.
- `rationale`: Preserves adaptive all-file coverage without static scope filtering while eliminating false negatives from script entrypoints, optional dependencies, and host mount deadlocks.
- `alternatives_rejected`: Threshold-only tuning without fallback reclassification, static exclusion of tests/examples/setup files, bind-mounted `target_repo` with direct delete/reclone.
- `linked_adr`: `documentation/decisions/20260212-sprint3-loop-gating-docopt.md`

## 2026-02-12 (Patch)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Remove hard LLM completion cap and add optional USD cost budgeting using OpenRouter pricing + usage-based accounting.
- `rationale`: Hard output caps reduced migration quality on thinking models; USD-level control is required for reliable cost governance and comparability.
- `alternatives_rejected`: Keep `max_response_tokens=4096`, rely only on token-count budgeting, or disable budgeting entirely.
- `linked_adr`: `documentation/decisions/20260212-sprint3-llm-cost-budget-and-uncapped-output.md`

## 2026-02-12 (Patch 2)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Hard-disable `max_tokens` in runtime requests (ignore `llm.max_response_tokens` even when set).
- `rationale`: Prevents accidental reintroduction of output truncation during migrations, especially in stale Docker-image scenarios.
- `alternatives_rejected`: Keep optional `max_response_tokens` passthrough, rely on manual config discipline.
- `linked_adr`: `documentation/decisions/20260212-sprint3-llm-cost-budget-and-uncapped-output.md`
