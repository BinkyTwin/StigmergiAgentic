---
name: docker-benchmark-tests
description: Run StigmergiAgentic Docker tests, smoke checks, and benchmark campaigns with mandatory no-cache builds. Use for docker compose tests, V10/V11/V12 MigrationBench validation, campaign launches, or when the user says Docker tests must never use cache.
---

# Docker Benchmark Tests

## Core Rules

- Always build the target Docker service with `--no-cache --pull --progress=plain` before running it.
- Do not rely on `docker compose run --build`; it can rebuild through normal cache paths.
- Do not pass secrets as CLI arguments. Load API keys from the environment or Compose `.env` mapping.
- Use Docker for real MigrationBench benchmark evidence. Host `uv run pytest ...` is fine for focused unit validation, not campaign claims.
- For mounted workspaces on macOS, clear directory contents when needed; do not delete the bind-mount root.
- Do not run `main_30`, paid LLM provider campaigns, or broad Docker prune commands unless the user explicitly asks.
- Keep `campaign_results/` uncommitted unless the user explicitly asks for generated evidence to be versioned.

## Wrapper

Prefer the bundled wrapper for Docker-backed validation:

```bash
.codex/skills/docker-benchmark-tests/scripts/run_no_cache_compose.sh --service test
```

Common variants:

```bash
# Full pytest suite in docker-compose.yml:test
.codex/skills/docker-benchmark-tests/scripts/run_no_cache_compose.sh --service test

# Coverage service
.codex/skills/docker-benchmark-tests/scripts/run_no_cache_compose.sh --service test-cov

# V11 MigrationBench smoke through docker-compose.campaign.yml
.codex/skills/docker-benchmark-tests/scripts/run_no_cache_compose.sh \
  --compose-file docker-compose.campaign.yml \
  --service v11-migrationbench-smoke

# V11 historical main_30 only when explicitly requested
.codex/skills/docker-benchmark-tests/scripts/run_no_cache_compose.sh \
  --compose-file docker-compose.campaign.yml \
  --service v11-migrationbench-main30
```

Pass non-secret campaign knobs as environment variables before the command:

```bash
V11_MIGRATION_LIMIT=1 V11_OFFICIAL_EVAL=false \
  .codex/skills/docker-benchmark-tests/scripts/run_no_cache_compose.sh \
  --compose-file docker-compose.campaign.yml \
  --service v11-migrationbench-smoke
```

For secrets, export them in the shell, keep them in an ignored `.env`, or let Compose read the existing env mapping.

## V12 Discipline

- Run `uv run pytest tests/unit/v12 -q` before any Docker campaign.
- Use `fixtures/migrationbench/subsets/targeted_v12_agentic_5.jsonl` before any `main_30` once a V12 campaign service exists.
- Compare only `S1_sd_feedback_like`, `S2_tool_feedback_agent`, and `V12_stigmergic_tool_agent`.
- Confirm S2 and V12 share identical tools, budgets, model settings, instances, and verifier contracts.
- Confirm medium/tool safety counters stay zero for medium-created patches and proposal-applied patches.

## After Running

- Capture the exact service, compose file, key environment knobs, output directory, and whether the run was smoke, targeted, or main_30.
- For V11 campaign evidence, run the audit after completion:

```bash
uv run python -m scripts.v11.audit_v11_campaign \
  --campaign-root campaign_results/v11/migrationbench_main30_targetaware_full_llmtraces
```

- Report strict success separately from safety, causal activation, operator/tool surface, and best-observed progress.
