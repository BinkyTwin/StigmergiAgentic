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

## 2026-02-17 — Sprint 4 Readiness Audit (Tooling vs Benchmark Completion)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Sprint 4 closure audit (baselines, Pareto, validation gates, thesis-readiness gaps)`

### Outcome
Validated that Sprint 4 code tooling is operational (`baselines/*`, `metrics/pareto.py`) and the full test suite is green, while identifying that thesis-grade Sprint 4 evidence remains incomplete (multi-run fairness benchmark and Pareto methodology alignment).

### Reusable Patterns (1-3)
1. Separate sprint closure into two explicit gates: `tooling complete` (code/tests) and `evidence complete` (benchmark protocol + reproducibility artifacts).
2. Run validation in layered order: target-scope tests, full suite, then static quality gates (`ruff`, `black --check`, `mypy`) to isolate regressions faster.
3. Before Pareto aggregation, verify input summaries contain all compared baselines and enough repetitions per mode; otherwise, treat results as smoke-only.

### Evidence
- `uv run pytest tests/test_loop.py tests/test_metrics.py tests/test_main.py tests/test_pareto.py -v --tb=short` (`17 passed`)
- `uv run pytest tests/ -v --tb=short` (`62 passed, 1 skipped`)
- `uv run pytest tests/ --cov --cov-report=term-missing --no-cov-on-fail` (`TOTAL 86%`)
- `uv run ruff check . --exclude tests/fixtures` (fails: `E402` in `baselines/*`, `F401` in `main.py`)
- `uv run mypy agents/ environment/ stigmergy/ --ignore-missing-imports` (type issues in `environment/pheromone_store.py`, `agents/scout.py`)
- `uv run python metrics/pareto.py --input-dir metrics/output --output /tmp/stigmergiagentic_pareto_check.png --export-json /tmp/stigmergiagentic_pareto_check.json` (`points=13`, `baselines=1`)

## 2026-02-17 — Sprint 4 Closure Implementation (Pareto V2 + 5x3 Benchmark)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Sprint 4 execution closure (static quality, baseline tests, Pareto CLI V2, bounded 5x3 benchmark, docs sync)`

### Outcome
Completed Sprint 4 closure work end-to-end: static gates green (`ruff`, `black --check`, `mypy`), expanded baseline/Pareto tests, upgraded Pareto tooling (per-run mode + baseline coverage check + CI95 export), and executed a 5x3 bounded benchmark on `docopt/docopt@0.6.2` with refreshed mobile/documentation outputs.

### Reusable Patterns (1-3)
1. Add explicit baseline coverage guards (`--require-baselines`) to analysis tooling so incomplete experiment folders fail fast instead of producing misleading charts.
2. Keep both visualization layers in Pareto workflows: per-run scatter for transparency and aggregate CI95 overlays for comparability.
3. When runtime/cost constraints prevent full unconstrained campaigns, run a bounded protocol with identical caps across configurations and document bounds directly in the results artifact.

### Evidence
- `uv run ruff check . --exclude tests/fixtures` (`All checks passed`)
- `uv run black --check . --exclude '/tests/fixtures/'` (`4985 files would be left unchanged`)
- `uv run mypy agents/ environment/ stigmergy/ --ignore-missing-imports` (`Success: no issues found`)
- `uv run pytest tests/ -v --tb=short` (`72 passed, 1 skipped`)
- `make docker-test` (`72 passed, 1 skipped`)
- Benchmark (5 runs each):
  - `uv run python baselines/single_agent.py ... --max-ticks 1 --max-tokens 5000 --runs 5`
  - `uv run python baselines/sequential.py ... --max-ticks 1 --max-tokens 5000 --runs 5`
  - `for i in 1..5: uv run python main.py ... --max-ticks 1 --max-tokens 5000`
- `uv run python metrics/pareto.py --input-dir metrics/output/sprint4_20260217_benchmark --plot-mode per-run --require-baselines stigmergic,single_agent,sequential --export-json ...` (`points=15`, `baselines=3`)

## 2026-02-17 — Benchmark Stability Hardening (Timeout + Sequential Stage Cap)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `medium`
- `scope`: `Runtime stability during repeated baseline benchmarking`

### Outcome
Added explicit OpenRouter request timeout wiring in `LLMClient` and introduced a per-stage action cap in the sequential baseline loop to reduce non-terminating benchmark runs.

### Reusable Patterns (1-3)
1. For repeated LLM benchmark campaigns, set explicit provider request timeouts instead of relying on SDK defaults.
2. Bound nested `while agent.run()` stage loops with configurable action caps to prevent runaway per-tick execution.
3. Validate stability guardrails with focused unit tests before resuming long benchmark batches.

### Evidence
- `uv run pytest tests/test_llm_client.py tests/test_baselines_sequential.py -v --tb=short` (`14 passed, 1 skipped`)
- `uv run ruff check baselines/sequential.py stigmergy/llm_client.py tests/test_baselines_sequential.py tests/test_llm_client.py` (`All checks passed`)

## 2026-02-17 — Unbounded 5x3 Completion (Parallel Isolated Runs + Pareto Final)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Finalize Sprint 4 evidence batch and close end-of-sprint gates`

### Outcome
Completed the full unbounded benchmark set (`5 x 3` runs) by launching missing runs in parallel from isolated temporary workspaces, then generated final Pareto artifacts and passed the sprint end gate.

### Reusable Patterns (1-3)
1. For concurrent campaign runs, isolate each process in its own copied workspace to avoid collisions on `target_repo`, `.target_repo_clone_tmp`, and `pheromones`.
2. Count completion from `run_*_summary.json` (not manifests) to avoid false-positive progress when runs start but have not finished.
3. After benchmark completion, regenerate Pareto with `--require-baselines` and immediately run `./scripts/sprint_end.sh` to lock both evidence and code-quality gates.

### Evidence
- Final counts in `metrics/output/sprint4_20260217_full`: `{'single_agent': 5, 'sequential': 5, 'stigmergic': 5}`
- `uv run python metrics/pareto.py --input-dir metrics/output/sprint4_20260217_full --plot-mode per-run --require-baselines stigmergic,single_agent,sequential --export-json metrics/output/sprint4_20260217_full/pareto_summary.json`
- `uv run pytest tests/ -v` (`74 passed, 1 skipped`)
- `./scripts/sprint_end.sh` (pass: tests, coverage, lint, format, mypy)
