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
