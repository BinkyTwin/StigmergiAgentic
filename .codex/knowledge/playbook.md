# Project Playbook

## Repo
- `repo_slug`: `stigmergiagentic-33b989`

## Active Practices

### Environment-First Guardrail Enforcement
- Keep governance rules in `environment/guardrails.py` so every writer path is mediated by one policy layer.
- Enforce lock ownership with status metadata (`lock_owner`, `lock_acquired_tick`) for scope safety.
- Apply TTL release before normal processing to avoid zombie `in_progress` states.

### Artifact Traceability Standard
- Treat `tasks.json`, `status.json`, `quality.json` as current state only.
- Record all mutations as append-only events in `pheromones/audit_log.jsonl`.
- Include agent signature and timestamp on every write/update path.

### Runtime Reproducibility Standard
- Bootstrap with `uv` and pinned Python 3.11.
- Use `uv run` for all python/test commands.
- Keep dependency source of truth in `requirements.txt` for current sprint.

### Agent Handoff Validation Standard
- Validate each specialized agent in isolation before enabling chained handoffs.
- Use pheromone state transitions as the single integration contract across agents.
- Keep one optional `live_api` smoke test separate from blocking acceptance to preserve deterministic local runs.

### Adaptive Fallback Quality Standard
- Run fallback in two phases: compile/import baseline first, then global pytest classification.
- Classify runtime/import failures into `related` vs `inconclusive`; reserve hard failures for syntax and migration-related import regressions.
- Keep confidence mapping explicit in config (`compile_import_fail`, `related_regression`, `pass_or_inconclusive`) and align validator thresholds against it.

### Docker Mountpoint Reliability Standard
- Treat mounted working directories as persistent mountpoints: clear contents, not mount roots.
- For git URL sources on mounted targets, clone into a temp path then copy into the mountpoint.
- Use a named Docker volume for high-churn target repositories to avoid host bind-mount deadlocks on macOS.

### Cost-Aware LLM Budgeting Standard
- Keep `max_response_tokens <= 0` to avoid hard truncation on reasoning-heavy tasks.
- Use `max_tokens_total` as deterministic safety ceiling and `max_budget_usd` as optional spend ceiling.
- Read `usage.cost` when available; fallback to pricing-based token estimation for pre-call checks and cost continuity.

### No-Output-Cap Runtime Policy
- Never send `max_tokens` in LLM chat completion payloads for migration runs.
- Treat `llm.max_response_tokens` as deprecated/ignored to prevent accidental regressions from config changes.
- Rebuild Docker runtime image before gate runs after any LLM client policy change.

### Sprint Closure Audit Standard
- Mark sprint status explicitly as `tooling complete` only after targeted + full pytest passes.
- Mark sprint status as `evidence complete` only after protocol checks pass (fairness constraints, repeated runs, reproducible artifacts).
- Validate quality gates (`ruff`, `black --check`, `mypy`) separately from functional tests so debt is visible and not masked by green pytest results.
- For Pareto analysis, verify multi-baseline input coverage before interpretation (`>=1 summary per baseline`, and thesis runs should use `>=5` runs per mode).

### Pareto Evidence Integrity Standard
- Export and persist both raw run points and baseline aggregates in the same summary payload.
- Fail analysis commands when expected baselines are missing instead of silently plotting partial data.
- Distinguish bounded benchmark snapshots from unconstrained thesis campaigns in documentation headers and regeneration commands.

### Benchmark Runtime Stability Standard
- Configure explicit provider request timeouts in `LLMClient` (`llm.request_timeout_seconds`) for long multi-run campaigns.
- Cap sequential per-stage actions per tick (`loop.sequential_stage_action_cap`) to avoid unbounded `while stage_runner.run()` cycles.
- Re-run focused baseline/LLM unit tests after stability guardrail changes before restarting benchmark batches.

### Parallel Benchmark Isolation Standard
- Run concurrent benchmark processes from isolated temporary workspace copies to prevent shared-state interference.
- Share only the final `--output-dir`; keep runtime working artifacts (`target_repo`, `pheromones`, temporary clone paths) local to each worker.
- Track campaign completeness by counting `summary` files per baseline and only then generate aggregate analytics.

### Multi-Provider LLM Wiring Standard
- Route provider differences (`env var`, `base_url`, pricing support) through `LLMClient` initialization, not agent code paths.
- Keep one explicit provider selector in config (`llm.provider`) and allow `llm.base_url` override for endpoint variants (for example coding-plan vs general endpoint).
- Run a live smoke check immediately after provider/model switch before launching long benchmark or migration jobs.
