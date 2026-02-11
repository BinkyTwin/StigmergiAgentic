# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Stigmergic orchestration of multi-agent LLM systems — a POC for a Master's thesis (EMLV). The system uses **4 specialized LLM agents** to automate Python 2 → Python 3 code migration, coordinated **only** through a shared environment (digital pheromones). No agent communicates directly with another; the environment (JSON pheromone files + Git repo) is the sole coordination medium.

This implements Grasse's stigmergy (1959) via the Agents & Artifacts paradigm (Ricci et al., 2007). **To our knowledge, this is the first empirical study applying stigmergic coordination to LLM agents** — existing multi-agent frameworks (MetaGPT, AutoGen, CrewAI, LangGraph) all rely on centralized supervisors.

## Architecture

### Core Loop

Round-robin (no supervisor): Scout → Transformer → Tester → Validator → repeat. Each agent: `perceive → should_act → decide → execute → deposit`. The deposited trace stimulates the next agent.

**Stop conditions** (OR): all files terminal, token budget exhausted, max ticks (50), or 2 consecutive idle cycles.

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

### Implementation Status (2026-02-11)

Sprint 2 has been implemented and validated locally:
- `stigmergy/llm_client.py` is available with OpenRouter retry/backoff, budget gating, and token accounting.
- `agents/base_agent.py` and all specialized agents are implemented.
- A versioned synthetic Python 2 fixture repo exists at `tests/fixtures/synthetic_py2_repo/`.
- Unit and integration test coverage for Sprint 2 flows is implemented in `tests/test_*`.

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
- **Token budget**: hard ceiling from config
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
stigmergy/        → loop.py (main loop), config.yaml, llm_client.py (OpenRouter)
pheromones/       → tasks.json, status.json, quality.json, audit_log.jsonl
metrics/          → collector.py, pareto.py, export.py
baselines/        → single_agent.py, sequential.py (comparison experiments)
target_repo/      → Python 2 code under migration (cloned dynamically)
tests/            → pytest test suite
consigne/         → Architecture plan and literature review (specification docs)
```

## Environment Variables

Required: `OPENROUTER_API_KEY` (set in `.env`, loaded by python-dotenv). See `.env.example`.

## Commands

```bash
# Bootstrap environment with uv (recommended)
uv python install 3.11
uv venv --python 3.11 .venv
uv pip install -r requirements.txt

# Run the stigmergic POC
uv run python main.py --repo <python2_repo_url>

# Full CLI options
uv run python main.py --repo <url> --config stigmergy/config.yaml --max-ticks 50 \
  --max-tokens 100000 --model qwen/qwen3-235b-a22b-2507 --output-dir metrics/output \
  --verbose --seed 42

# Dry run (no Git writes)
uv run python main.py --repo <url> --dry-run

# Resume interrupted migration
uv run python main.py --resume

# Review needs_review files
uv run python main.py --review

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

# Export metrics to CSV
uv run python metrics/export.py --output results.csv

# Generate Pareto cost-precision analysis
uv run python metrics/pareto.py --output pareto.png
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
  model: "qwen/qwen3-235b-a22b-2507"
  temperature: 0.2
  max_response_tokens: 4096
  max_tokens_total: 100000

loop:
  max_ticks: 50
  idle_cycles_to_stop: 2
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
- **LLM Provider**: OpenRouter (qwen/qwen3-235b-a22b-2507 for dev, Claude Sonnet/GPT-4o for results)
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
