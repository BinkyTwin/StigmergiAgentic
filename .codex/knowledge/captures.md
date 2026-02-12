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

## 2026-02-12 — Sprint 3 Patch: Uncapped Output and USD Cost Budget

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `LLM client budget model, loop/metrics propagation, CLI budget override`

### Outcome
Removed hard completion capping by default and introduced an optional USD budget control based on OpenRouter model pricing (pre-call estimate) and `usage.cost` (post-call accounting), with cost metrics exported per run.

### Reusable Patterns (1-3)
1. For thinking-heavy LLM workflows, prefer uncapped completion output (`max_tokens` omitted) and control spend with a separate budget mechanism instead of truncation.
2. Combine two budget layers: token ceiling for deterministic guardrails and cost ceiling for monetary governance.
3. Persist cumulative run cost in the same metrics stream as token usage to enable direct cost-quality analysis.

### Evidence
- `uv run pytest tests/ -q` (`60 passed, 1 skipped`)
- `uv run python main.py --repo tests/fixtures/synthetic_py2_repo --config stigmergy/config.yaml --seed 42 --max-ticks 1 --verbose` (`total_cost_usd` present, uncapped request payload)

## 2026-02-12 — Runtime Hard-Disable of `max_tokens` + Docker Image Freshness

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `LLM client request payload policy and Docker execution consistency`

### Outcome
Hardened runtime behavior so the client never sends `max_tokens` to OpenRouter (even if configured), preventing accidental output truncation from local configuration drift and stale Docker images.

### Reusable Patterns (1-3)
1. For reasoning-heavy migrations, enforce uncapped completion at client layer instead of trusting config defaults.
2. Keep budget control separate from generation caps (`max_tokens_total`/`max_budget_usd` without per-call output limit).
3. Rebuild Docker image before benchmark/gate runs when runtime policy changes to avoid executing stale logic.

### Evidence
- `uv run pytest tests/test_llm_client.py -q` (`10 passed, 1 skipped`)
- `uv run pytest tests/ -q` (`60 passed, 1 skipped`)
- Docker verbose request payload confirms no `max_tokens` field in `json_data`.
