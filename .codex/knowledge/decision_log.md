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

## 2026-02-17

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Treat Sprint 4 as tooling-complete but benchmark-incomplete until fairness runs and Pareto reporting requirements are satisfied.
- `rationale`: Code paths and tests pass, but current evidence is smoke-level and does not yet meet protocol constraints (`>=5 runs/config`, confidence-interval reporting, complete baseline input coverage).
- `alternatives_rejected`: Mark Sprint 4 fully complete based only on single-run snapshot and mean/std-only Pareto output.
- `linked_adr`: `documentation/decisions/TBD-sprint4-benchmark-readiness.md`

## 2026-02-17 (Closure Implementation)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Upgrade Pareto tooling to enforce baseline coverage and export raw+aggregate evidence, then close Sprint 4 with a bounded 5x3 benchmark protocol on `docopt/docopt@0.6.2`.
- `rationale`: Prevents partial-data misinterpretation and provides reproducible closure artifacts when full unconstrained campaigns are too costly for the current iteration.
- `alternatives_rejected`: Keep aggregate-only Pareto output, accept silent missing-baseline inputs, or defer all benchmark execution until a later sprint.
- `linked_adr`: `documentation/decisions/TBD-sprint4-closure-bounded-benchmark-and-pareto-v2.md`

## 2026-02-17 (Benchmark Stability Hardening)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Add explicit LLM request timeout (`llm.request_timeout_seconds`) and sequential stage action cap (`loop.sequential_stage_action_cap`) to reduce benchmark run hangs.
- `rationale`: Repeated baseline runs showed long-running/non-terminating behavior under provider latency and nested stage loops; bounded runtime controls are needed for campaign completion.
- `alternatives_rejected`: Keep SDK default timeout behavior and unbounded stage `while run()` loops.
- `linked_adr`: `documentation/decisions/TBD-benchmark-runtime-stability-timeout-stage-cap.md`

## 2026-02-17 (Unbounded 5x3 Final Batch Execution)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Execute missing Sprint 4 benchmark runs in parallel using isolated temporary workspace copies, then treat `metrics/output/sprint4_20260217_full` as the canonical unbounded 5x3 batch.
- `rationale`: Parallelism reduces wall time, while per-worker workspace isolation avoids race conditions/cross-run contamination on shared runtime artifacts.
- `alternatives_rejected`: Run all remaining jobs serially, or run them in parallel from one workspace with shared `target_repo`/`pheromones`.
- `linked_adr`: `documentation/decisions/TBD-sprint4-unbounded-5x3-final-batch.md`

## 2026-02-19 (Sprint 5 Provider Switch: OpenRouter + Z.ai)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Make `LLMClient` provider-aware and adopt `zai` + `glm-5` as default Sprint 5 frontier configuration while preserving OpenRouter compatibility.
- `rationale`: Sprint 5 requires a frontier model (`glm-5`) and reliable provider switching without touching agent orchestration logic.
- `alternatives_rejected`: Fork a dedicated Z.ai client, or hard-replace OpenRouter paths with Z.ai-only logic.
- `linked_adr`: `documentation/decisions/TBD-sprint5-provider-switch-zai-glm5.md`

## 2026-02-19 (Anti-429 Controls for Z.ai)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Introduce built-in anti-rate-limit controls in `LLMClient` (inter-call pacing + 429-specific backoff floor + jitter), and enable them in default config.
- `rationale`: Repeated Sprint 5 runs encountered frequent Z.ai `429` responses; centralized pacing/backoff is required for stable batch execution.
- `alternatives_rejected`: Handle delays only in shell loops, or raise retries without pacing control.
- `linked_adr`: `documentation/decisions/TBD-sprint5-anti429-llm-pacing.md`
