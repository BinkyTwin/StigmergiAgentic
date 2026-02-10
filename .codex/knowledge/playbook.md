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
