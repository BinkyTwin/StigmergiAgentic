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

## 2026-02-12 — Sprint 3 Full Loop + Blocking Gate Validation

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Sprint 3 orchestration loop, CLI, metrics, adaptive tester fallback, Docker gate execution`

### Outcome
Implemented and validated the full Sprint 3 runtime with deterministic stop conditions, per-run artifacts, adaptive quality fallback, and successful blocking gates on both synthetic and real repositories (local + Docker).

### Reusable Patterns (1-3)
1. For mixed script/library repos, treat compile-success + usage/optional-dependency import failures as `inconclusive` signals instead of hard failures, while keeping legacy stdlib misses (for example `urllib2`) as related failures.
2. Sanitize LLM outputs before file writes by stripping markdown fence wrappers (including unclosed fences) to avoid test/code corruption on retries.
3. In Docker on macOS, avoid bind-mount churn for actively rewritten repos by using a named volume for the working tree and implementing mountpoint-safe cleanup logic.

### Evidence
- Local: `uv run pytest tests/ -q` (`49 passed, 1 skipped`)
- Local synthetic gate: `metrics/output/run_20260212T170852Z_summary.json` (`success_rate=0.95`)
- Local real gate: `metrics/output/run_20260212T170936Z_summary.json` (`success_rate=0.913043`)
- Docker synthetic gate: `metrics/output/run_20260212T173610Z_summary.json` (`success_rate=0.95`)
- Docker real gate: `metrics/output/run_20260212T173704Z_summary.json` (`success_rate=0.869565`)
