# Project Captures

## 2026-02-10 — Sprint 1 Environment Foundation

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Sprint 1 environment medium (store, decay, guardrails, tests)`

### Outcome
Implemented a fully testable JSON-based stigmergic medium with POSIX file locking, append-only audit trail, and guardrails enforced by environment primitives.

### Reusable Patterns (1-3)
1. Use a single environment guardrail layer to enforce token budget, retry ceiling, scope lock, and TTL instead of distributing those checks across agents.
2. Persist pheromones as inspectable JSON artifacts and pair every mutation with an append-only JSONL audit event for traceability.
3. Standardize local execution with `uv` + pinned Python minor version and run all validation through `uv run` for reproducible results.

### Evidence
- `uv run pytest tests/test_pheromone_store.py -v` (passed)
- `uv run pytest tests/test_guardrails.py -v` (passed)
- `uv run pytest tests -v -k "pheromone or guardrails"` run twice with stable green results

## 2026-02-11 — Sprint 2 Agent Layer and Deterministic Validation

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Sprint 2 agents, llm client, synthetic fixture repository, unit+integration tests`

### Outcome
Implemented all Sprint 2 units end-to-end: OpenRouter client, four isolated agents, synthetic Python 2 fixture repository, and deterministic handoff tests across the pheromone medium.

### Reusable Patterns (1-3)
1. Keep core orchestration tests deterministic with mocked LLM responses while providing an optional non-blocking live API smoke test.
2. Encode cross-agent coordination only through pheromone transitions (`pending -> in_progress -> transformed -> tested -> validated|needs_review|retry`), never direct agent calls.
3. Store a versioned synthetic legacy-code fixture in `tests/fixtures/` and explicitly exclude it from project-level pytest collection.

### Evidence
- `uv run pytest tests/ -v` (`29 passed, 1 skipped`)
- `uv run pytest tests/test_agents_integration.py -v` (all handoff scenarios passed)
