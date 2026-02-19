# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Stigmergic orchestration of multi-agent LLM systems — a POC for a Master's thesis (EMLV). The system uses **4 specialized LLM agents** to automate Python 2 → Python 3 code migration, coordinated **only** through a shared environment (digital pheromones). No agent communicates directly with another; the environment (JSON pheromone files + Git repo) is the sole coordination medium.

This implements Grasse's stigmergy (1959) via the Agents & Artifacts paradigm (Ricci et al., 2007). **To our knowledge, this is the first empirical study applying stigmergic coordination to LLM agents** — existing multi-agent frameworks (MetaGPT, AutoGen, CrewAI, LangGraph) all rely on centralized supervisors.

## Architecture

### Core Loop

Round-robin (no supervisor): Scout → Transformer → Tester → Validator → repeat. Each agent: `perceive → should_act → decide → execute → deposit`. The deposited trace stimulates the next agent.

**Stop conditions** (OR): all files terminal, token/USD budget exhausted, max ticks (50), or 2 consecutive idle cycles.

### Agents

| Agent | Role | Uses LLM? |
|---|---|---|
| **Scout** | Analyzes Python 2 codebase (19 patterns), deposits task pheromones with priority | Yes |
| **Transformer** | Reads task pheromones, generates Python 3 code with stigmergic few-shot learning | Yes |
| **Tester** | Runs pytest on transformed files, deposits quality pheromones | No (deterministic) |
| **Validator** | Commits/reverts/escalates based on confidence thresholds | No |

All agents inherit from `agents/base_agent.py` (abstract class with the perceive→deposit cycle).

**Locality permissions** (Heylighen, 2016; Ricci et al., 2007):

| Agent | Reads | Writes |
|---|---|---|
| **Scout** | `.py` files in target_repo, status.json | tasks.json, status.json (`pending`) |
| **Transformer** | tasks.json (by intensity), quality.json (few-shot), status.json | `.py` files, status.json (`in_progress`, `transformed`) |
| **Tester** | status.json (`transformed`), `.py` files | quality.json, status.json (`tested`) |
| **Validator** | quality.json, status.json (`tested`) | status.json (terminal states), Git ops |

Transformer reading quality.json = **cognitive stigmergy** (Ricci et al., 2007): reading environmental traces, not direct communication.

### Implementation Status (2026-02-17)

Sprint 3 has been implemented and validated, and Sprint 4 closure tooling is now implemented:
- `main.py` now provides full CLI controls (`--repo-ref`, `--resume`, `--review`, `--dry-run`) plus run manifest hashing.
- `stigmergy/loop.py` implements the full round-robin orchestrator and all stop conditions.
- `metrics/collector.py` + `metrics/export.py` generate per-tick CSV, summary JSON, and manifest JSON.
- `environment/pheromone_store.py` now performs tick maintenance (`retry -> pending`, TTL zombie lock release).
- `agents/tester.py` includes adaptive fallback confidence with inconclusive/related classification and robust py_compile handling.
- `agents/validator.py` respects dry-run mode for git commit/revert paths.
- Sprint 3 tests are added (`tests/test_loop.py`, `tests/test_metrics.py`, `tests/test_main.py`).
- Sprint 4 tests now include Pareto + baseline coverage (`tests/test_pareto.py`, `tests/test_baselines_common.py`, `tests/test_baselines_single_agent.py`, `tests/test_baselines_sequential.py`).
- `metrics/pareto.py` now supports per-run plotting (`--plot-mode per-run`), required baseline validation (`--require-baselines`), and CI95 export payloads.
- Unbounded 5x3 benchmark batch on `docopt/docopt@0.6.2` is available in `metrics/output/sprint4_20260217_full` with `pareto.png` and `pareto_summary.json`.
- Gate runs pass on both required repositories:
  - synthetic fixture: 19/20 validated (95%)
  - real repo `docopt/docopt@0.6.2`: 21/23 validated local (91.3%), 20/23 validated Docker (86.96%).

### Pheromone Types (JSON files in `pheromones/`)

- **tasks.json** — Task pheromones (Scout deposits). Intensity = min-max normalization: `S_i = pattern_count * 0.6 + dep_count * 0.4`, `intensity_i = (S_i - S_min) / (S_max - S_min)`, clamped to [0.1, 1.0]. Exponential decay: `intensity *= e^(-0.05)` per tick.
- **status.json** — Status pheromones (all agents). State machine: `pending → in_progress → transformed → tested → validated | failed → retry | skipped`. Includes `inhibition` field (gamma) for anti-oscillation (Rodriguez, 2026): `gamma += 0.5` on retry, Transformer waits until `gamma < 0.1`. TTL scope lock: `in_progress` > 3 ticks without update → back to `pending` (zombie prevention).
- **quality.json** — Quality pheromones (Tester/Validator). Initial confidence = `tests_passed / tests_total` (0.5 if no tests). Reinforcement: pass → `+0.1`; fail → `-0.2` + retry. Coverage via pytest-cov (informational).
- **audit_log.jsonl** — Append-only JSONL audit trail. Every pheromone write logged with agent, timestamp, before/after values. Satisfies RQ3 (EU AI Act Art. 14).

### Pheromone Store API

Class `PheromoneStore` in `environment/pheromone_store.py`. 6 methods: `read_all`, `read_one`, `query`, `write`, `update`, `apply_decay`. JSON dicts keyed by filename. File locking via `fcntl.flock`. Write path enforces: auto-timestamp, agent signature, scope lock check, audit log append.

Pheromone files are **artifacts** (Ricci et al., 2007): inspectable (agents read state), controllable (agents modify via guardrails), composable (tasks → status → quality reference chain).

### Git Strategy

- Clone: `git clone --depth 1 {url}`, branch: `stigmergic-migration-{timestamp}`
- Only Validator commits: `[stigmergic] Migrate {file} to Python 3 (confidence={conf})`
- Rollback: `git checkout HEAD -- {filepath}`
- No auto-push (local only)

### Guardrails (`environment/guardrails.py`)

Enforced by the environment, not by agents. Taxonomy from Grisold et al. (2025):

**Deep norms** (stable, in config.yaml):
- **Traceability**: timestamped, agent-signed writes (EU AI Act Art. 14)
- **Token and cost budget**: hard ceiling from config
- **Anti-loop**: `retry_count > 3` → skip + log
- **Scope lock**: one agent per file (mutex) + TTL (3 ticks) for zombie prevention
- **Confidence thresholds**: 0.8 (validate), 0.5 (rollback), between → escalate

**Surface norms** (emergent, in pheromones):
- Task intensity (evolves with decay)
- File confidence (evolves with test results)
- Inhibition gamma (evolves with retries)
- Auto-rollback (confidence < 0.5 → git revert)

**Human escalation**: `needs_review` files are skipped by the loop. CLI `--review` mode lets humans resolve them. MVP: manual edit of status.json.

## Project Structure

```
agents/           → 4 specialized agents + base_agent.py
environment/      → pheromone_store.py, guardrails.py, decay.py
stigmergy/        → loop.py (main loop), config.yaml, llm_client.py (provider-aware: OpenRouter/Z.ai)
pheromones/       → tasks.json, status.json, quality.json, audit_log.jsonl
metrics/          → collector.py, pareto.py, export.py
baselines/        → single_agent.py, sequential.py (comparison experiments)
target_repo/      → Python 2 code under migration (cloned dynamically)
tests/            → pytest test suite
consigne/         → Architecture plan and literature review (specification docs)
```

## Environment Variables

Required: provider-specific key (set in `.env`, loaded by python-dotenv):
- `OPENROUTER_API_KEY` when `llm.provider=openrouter`
- `ZAI_API_KEY` when `llm.provider=zai`

## Commands

```bash
# Bootstrap environment with uv (recommended)
uv python install 3.11
uv venv --python 3.11 .venv
uv pip install -r requirements.txt

# Run the stigmergic POC
uv run python main.py --repo <python2_repo_url>

# Run with pinned repo ref (tag/branch/commit)
uv run python main.py --repo <python2_repo_url> --repo-ref <ref> --config stigmergy/config.yaml

# Full CLI options
uv run python main.py --repo <url> --config stigmergy/config.yaml --max-ticks 50 \
  --max-tokens 100000 --max-budget-usd 3.5 --model glm-5 --output-dir metrics/output \
  --verbose --seed 42

# Dry run (no Git writes)
uv run python main.py --repo <url> --dry-run

# Resume interrupted migration
uv run python main.py --resume

# Review needs_review files
uv run python main.py --review

# Review with explicit target repo/ref
uv run python main.py --review --repo <python2_repo_url> --repo-ref <ref>

# Run tests
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_pheromone_store.py -v

# Run Sprint 2 unit tests
uv run pytest tests/test_llm_client.py tests/test_base_agent.py tests/test_scout.py \
  tests/test_transformer.py tests/test_tester.py tests/test_validator.py -v

# Run Sprint 2 integration handoffs
uv run pytest tests/test_agents_integration.py -v

# Run baselines for comparison
uv run python baselines/single_agent.py --repo <url>
uv run python baselines/sequential.py --repo <url>

# Run thesis-grade unbounded benchmark (5 runs/mode)
uv run python baselines/single_agent.py --repo <url> --repo-ref <ref> --model <model> --runs 5
uv run python baselines/sequential.py --repo <url> --repo-ref <ref> --model <model> --runs 5
for i in 1 2 3 4 5; do
  uv run python main.py --repo <url> --repo-ref <ref> --model <model>
done

# Optional bounded smoke benchmark (fast sanity check)
uv run python baselines/single_agent.py --repo <url> --repo-ref <ref> --max-ticks 1 --max-tokens 5000 --runs 5
uv run python baselines/sequential.py --repo <url> --repo-ref <ref> --max-ticks 1 --max-tokens 5000 --runs 5
for i in 1 2 3 4 5; do
  uv run python main.py --repo <url> --repo-ref <ref> --max-ticks 1 --max-tokens 5000
done

# Export metrics to CSV
uv run python metrics/export.py --output results.csv

# Generate Pareto cost-precision analysis
uv run python metrics/pareto.py --output pareto.png
uv run python metrics/pareto.py --input-dir <out_dir> --output <out_dir>/pareto.png \
  --plot-mode per-run --require-baselines stigmergic,single_agent,sequential \
  --export-json <out_dir>/pareto_summary.json
```

## Docker Commands (Sprint 2.5)

```bash
# Build the Docker image
make docker-build
# or: docker compose build

# Run full test suite in Docker
make docker-test
# or: docker compose run --rm test

# Run tests with coverage in Docker
make docker-test-cov
# or: docker compose run --rm test-cov

# Run migration in Docker
make docker-migrate REPO=<python2_repo_url>
# or: REPO=<url> REPO_REF=<ref> docker compose run --rm migrate

# Interactive shell in Docker container
make docker-shell
# or: docker compose run --rm shell
```

## Key Configuration (`stigmergy/config.yaml`)

```yaml
pheromones:
  decay_type: "exponential"          # or "linear"
  decay_rate: 0.05                   # rho for exponential decay
  inhibition_decay_rate: 0.08         # k_gamma (calibrated for ~20 tick recovery)
  inhibition_threshold: 0.1          # gamma max to resume file
  task_intensity_clamp: [0.1, 1.0]

thresholds:
  transformer_intensity_min: 0.2     # lowered from 0.3 to prevent starvation
  validator_confidence_high: 0.8
  validator_confidence_low: 0.5
  max_retry_count: 3
  scope_lock_ttl: 3                  # ticks before releasing zombie in_progress

llm:
  provider: "zai"                    # "openrouter" or "zai"
  model: "glm-5"
  base_url: "https://api.z.ai/api/coding/paas/v4"  # coding-plan endpoint
  temperature: 0.2
  max_response_tokens: 0            # deprecated/ignored: client never sends max_tokens
  estimated_completion_tokens: 4096 # budget pre-check estimate when uncapped
  max_tokens_total: 200000
  max_budget_usd: 0.0               # 0 disables cost cap
  pricing_endpoint: ""              # optional, mainly for provider=openrouter
  request_timeout_seconds: 300      # avoid long stuck requests on provider side

loop:
  max_ticks: 50
  idle_cycles_to_stop: 2
  sequential_stage_action_cap: 50   # optional cap per stage/tick for sequential baseline

tester:
  fallback_quality:
    compile_import_fail: 0.4
    related_regression: 0.6
    pass_or_inconclusive: 0.8
```

## Error Handling

Two categories: **file errors** (non-fatal, file fails but loop continues — e.g., parse errors, LLM timeout, pytest crash) and **system errors** (fatal, save state and terminate — e.g., invalid API key, budget exhausted, corrupted JSON). Pheromone state is always saved before termination via file locking.

## Logging

Two streams: **operational** (Python `logging`, INFO/DEBUG, `logs/stigmergic.log`) for agent activity and metrics, and **audit** (JSONL append-only, `pheromones/audit_log.jsonl`) for every pheromone modification with before/after values (satisfies RQ3).

## Testing

- **9 unit tests** (mocked LLM): pheromone CRUD, locking, decay, inhibition, normalization, pattern detection, prompt building, guardrails, state transitions
- **4 integration tests** (real pheromone store): scout→transformer, transformer→tester, tester→validator, full single-file cycle
- **1 E2E test** (real API calls): complete migration of synthetic repo (~15 files, 19 Py2 patterns)

## Tech Stack

- **Python 3.11+**
- **LLM Provider**: Configurable (`openrouter` or `zai`). Sprint 5 frontier default: `zai` + `glm-5`.
- **Pheromone store**: local JSON files with fcntl file locking
- **Tooling**: uv for environment/bootstrap and command execution
- **Testing**: pytest + pytest-cov
- **Versioning**: Git (local) — the stigmergic medium itself
- **Config**: YAML (`stigmergy/config.yaml`)
- **Metrics**: CSV + matplotlib (Pareto frontier analysis)
- **Env vars**: python-dotenv

## Research Context

The POC validates three research questions:
- **RQ1**: Can digital pheromones coordinate LLM agents without central supervision?
- **RQ2**: Does stigmergic coordination match/exceed Agentless baseline (Xia et al., 2024)?
- **RQ3**: Do environmental traces enable complete auditability (EU AI Act compliance)?

Evaluation uses Pareto frontier analysis comparing stigmergic (4 agents) vs single-agent vs sequential pipeline. **Baseline fairness** (Kapoor et al., 2024; Gao et al., 2025): same LLM model, same temperature (0.2), same prompt templates, same guardrails, same test repo, >= 5 runs per config, confidence intervals on all metrics.

**Scientific novelty**: to our knowledge, first POC applying Grasse's stigmergy (1959) to LLM agent coordination. No existing framework uses decentralized environmental coordination — all rely on supervisors or direct messaging.

## Language

The specification documents in `consigne/` are written in French. Code, comments, and documentation should be in English.

## End-of-Sprint Workflow

When completing a sprint, agents MUST follow the structured workflow to ensure code quality and proper documentation:

### Quick Start
```bash
# 1. Run automated validation
./scripts/sprint_end.sh

# 2. Review checklist
# See .agent/workflows/end-of-sprint.md for complete checklist

# 3. Make atomic commits
git add <files>
git commit -m "type(scope): description"

# 4. Sync and push
git fetch origin
git rebase origin/develop
git push origin <branch>

# 5. Create PR on GitHub
```

### Commit Convention
Format: `type(scope): description`

**Types**: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`  
**Scopes**: `scout`, `transformer`, `tester`, `validator`, `pheromone`, `guardrails`, `metrics`, `loop`, `thesis`

**Examples**:
- `feat(scout): implement AST pattern detection for print statements`
- `fix(transformer): correct syntax in f-string conversion`
- `test(pheromone): add unit tests for intensity decay logic`
- `docs(thesis): update construction log for sprint 2026-02-10`

### Documentation Updates
Every sprint MUST update:
- `documentation/construction_log.md` — Sprint summary, challenges, decisions
- `CLAUDE.md` — If project architecture or workflow changes
- `AGENTS.md` — If architecture or commands change

### Workflow Files
- **Checklist**: `.agent/workflows/end-of-sprint.md` — Complete validation checklist
- **Script**: `scripts/sprint_end.sh` — Automated validation (tests, linting, formatting)

## Update
- Always update CLAUDE.md when you make changes to the project. To stay updated with the latest changes, use the command `git log -1` to see the last commit message.

- Mobile-readable snapshot document: `documentation/MOBILE_RESULTS.md` (quick scoreboard + JSON extracts).
