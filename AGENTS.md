# AGENTS.md

This file provides guidance to GitHub Copilot / Codex when working with code in this repository.

## Project Overview

Stigmergic orchestration of multi-agent LLM systems — a POC for a Master's thesis (EMLV). The system uses **4 specialized LLM agents** to automate Python 2 → Python 3 code migration, coordinated **only** through a shared environment (digital pheromones). No agent communicates directly with another; the environment (JSON pheromone files + Git repo) is the sole coordination medium.

This implements Grassé's stigmergy (1959) via the Agents & Artifacts paradigm (Ricci et al., 2007).

## Architecture

### Core Loop

Round-robin (no supervisor): Scout → Transformer → Tester → Validator → repeat. Each agent: `perceive → should_act → decide → execute → deposit`. The deposited trace stimulates the next agent.

Stop conditions are OR-combined: all files terminal, token budget exhausted, max ticks reached, or idle cycle threshold reached.

### Agents

| Agent | Role | Uses LLM? |
|---|---|---|
| **Scout** | Analyzes Python 2 codebase, deposits task pheromones with priority | Yes |
| **Transformer** | Reads task pheromones, generates Python 3 code | Yes |
| **Tester** | Runs pytest on transformed files, deposits quality pheromones | No (deterministic) |
| **Validator** | Commits/reverts/escalates based on confidence thresholds | No |

All agents inherit from `agents/base_agent.py` (abstract class with the perceive→deposit cycle).

### Implementation Status (2026-02-12)

Sprint 3 is implemented and gate-validated:
- `main.py` provides CLI orchestration with `--repo-ref`, `--resume`, `--review`, `--dry-run`, and run manifest hashing.
- `stigmergy/loop.py` implements full round-robin execution and 4 stop conditions (`all_terminal`, `budget_exhausted`, `max_ticks`, `idle_cycles`).
- `metrics/collector.py` and `metrics/export.py` export `run_{id}_ticks.csv`, `run_{id}_summary.json`, `run_{id}_manifest.json`.
- `environment/pheromone_store.py` includes tick maintenance for `retry -> pending` and TTL lock release.
- `agents/tester.py` includes adaptive fallback confidence with inconclusive/related handling and robust compile checks.
- `agents/validator.py` supports runtime `dry_run` (no git mutations).
- Full Sprint 3 test suite is available (`test_loop.py`, `test_metrics.py`, `test_main.py` + extensions).
- Sprint 3 blocking gates pass:
  - synthetic fixture run: 19/20 validated (95%)
  - real repo `docopt/docopt@0.6.2`: 21/23 validated local (91.3%), 20/23 validated Docker (86.96%).

### Three Pheromone Types (JSON files in `pheromones/`)

- **tasks.json** — Task pheromones (Scout deposits). Intensity = `normalize(pattern_count × 0.6 + dep_count × 0.4)`. Evaporation: -0.05/tick.
- **status.json** — Status pheromones (all agents). State machine: `pending → in_progress → transformed → tested → validated | needs_review | failed → retry | skipped`.
- **quality.json** — Quality pheromones (Tester/Validator). Reinforcement: pass → `confidence += 0.1`; fail → `confidence -= 0.2` + retry.

### Guardrails (`environment/guardrails.py`)

Enforced by the environment, not by agents:
- **Traceability**: timestamped, agent-signed writes (EU AI Act Art. 14)
- **Token budget**: hard ceiling from config
- **Auto-rollback**: `tests_failed > threshold` → git revert
- **Human escalation**: `0.5 < confidence < 0.8` → needs_review
- **Anti-loop**: `retry_count > 3` → skip + log
- **Scope lock**: one agent per file (mutex)

## Project Structure

```
agents/           → 4 specialized agents + base_agent.py
environment/      → pheromone_store.py, guardrails.py, decay.py
stigmergy/        → loop.py (main loop), config.yaml, llm_client.py (OpenRouter)
pheromones/       → tasks.json, status.json, quality.json (runtime trace store)
metrics/          → collector.py, pareto.py, export.py
baselines/        → single_agent.py, sequential.py (comparison experiments)
target_repo/      → Python 2 code under migration (cloned dynamically)
tests/            → pytest test suite
consigne/         → Architecture plan and literature review (specification docs)
documentation/    → Construction logs, decisions, and technical notes for thesis
```

## Commands

### Local (uv)

```bash
# Bootstrap environment with uv (recommended)
uv python install 3.11
uv venv --python 3.11 .venv
uv pip install -r requirements.txt

# Run the stigmergic POC
uv run python main.py --repo <python2_repo_url> --config stigmergy/config.yaml

# Run with pinned repo ref (tag/branch/commit)
uv run python main.py --repo <python2_repo_url> --repo-ref <ref> --config stigmergy/config.yaml

# Review needs_review files interactively
uv run python main.py --review --repo <python2_repo_url> --repo-ref <ref>

# Run tests
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_pheromone_store.py -v

# Run Sprint 2 agent tests
uv run pytest tests/test_llm_client.py tests/test_base_agent.py tests/test_scout.py \
  tests/test_transformer.py tests/test_tester.py tests/test_validator.py -v

# Run Sprint 2 handoff integration tests
uv run pytest tests/test_agents_integration.py -v

# Run Sprint 3 loop/metrics/cli tests
uv run pytest tests/test_loop.py tests/test_metrics.py tests/test_main.py -v

# Run baselines for comparison
uv run python baselines/single_agent.py --repo <url>
uv run python baselines/sequential.py --repo <url>

# Export metrics to CSV
uv run python metrics/export.py --output results.csv

# Generate Pareto cost-precision analysis
uv run python metrics/pareto.py --output pareto.png
```

### Docker (Sprint 2.5)

```bash
# Build the Docker image
make docker-build

# Run full test suite in Docker
make docker-test
# or: docker compose run --rm test

# Run tests with coverage in Docker
make docker-test-cov

# Run migration in Docker
make docker-migrate REPO=<python2_repo_url>
# Run migration in Docker with pinned ref
make docker-migrate REPO=<python2_repo_url> REPO_REF=<ref>

# Interactive shell in Docker container
make docker-shell
```

## Tech Stack

- **Python 3.11+**
- **LLM Provider**: OpenRouter (qwen/qwen3-235b-a22b-2507 for dev, Claude Sonnet/GPT-4o for results)
- **Pheromone store**: local JSON files
- **Tooling**: uv for Python/runtime orchestration
- **Testing**: pytest + pytest-cov
- **Versioning**: Git (local) — the stigmergic medium itself
- **Config**: YAML (`stigmergy/config.yaml` — thresholds, decay rates, token budget)
- **Metrics**: CSV + matplotlib (Pareto frontier analysis)

## Key Configuration (`stigmergy/config.yaml`)

Critical thresholds that affect agent behavior:
- `thresholds.transformer_intensity_min: 0.2` — minimum task pheromone intensity to trigger transformation
- `thresholds.validator_confidence_high: 0.8` — auto-validate above
- `thresholds.validator_confidence_low: 0.5` — auto-rollback below
- `pheromones.decay_rate: 0.05` — exponential evaporation rate per tick
- `max_retry_count: 3` — anti-loop guardrail
- `max_tokens_total: 200000` — budget ceiling (Sprint 3 gate tuning)
- `tester.fallback_quality.compile_import_fail: 0.4`
- `tester.fallback_quality.related_regression: 0.6`
- `tester.fallback_quality.pass_or_inconclusive: 0.8`

## Research Context

The POC validates three research questions:
- **RQ1**: Can digital pheromones coordinate LLM agents without central supervision?
- **RQ2**: Does stigmergic coordination match/exceed Agentless baseline (Xia et al., 2024)?
- **RQ3**: Do environmental traces enable complete auditability (EU AI Act compliance)?

Evaluation uses Pareto frontier analysis comparing stigmergic (4 agents) vs single-agent vs sequential pipeline vs hierarchical baselines. Minimum 5 runs per configuration for stochastic variability.

## Code Style Guidelines

When generating code for this project:

### General Principles
- Use **type hints** for all function parameters and return types
- Follow **PEP 8** style guide
- Use **descriptive variable names** that reflect the stigmergic domain (e.g., `pheromone_intensity`, `task_trace`)
- Add **docstrings** to all classes and public methods
- Keep functions **focused** and **single-purpose**

### Naming Conventions
- Classes: `PascalCase` (e.g., `BaseAgent`, `PheromoneStore`)
- Functions/methods: `snake_case` (e.g., `perceive_environment`, `deposit_pheromone`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRY_COUNT`, `DEFAULT_THRESHOLD`)
- Private methods: prefix with `_` (e.g., `_validate_intensity`)

### Agent-Specific Guidelines
- All agents must inherit from `BaseAgent`
- Implement the four core methods: `perceive()`, `should_act()`, `decide()`, `execute()`
- Use the pheromone store for all inter-agent communication
- Never import or reference other agent classes directly
- Log all significant actions with timestamps and agent signature

### Pheromone Management
- Always validate pheromone intensity before acting
- Use atomic operations when reading/writing pheromones
- Include metadata: timestamp, agent_id, confidence
- Respect the evaporation schedule (managed by environment)

### Error Handling

Two categories with distinct strategies:

**File Errors (Non-Fatal)** — File fails, loop continues:
- Illisible file (`IOError`) → Scout skips, logs WARNING
- AST parse error (`SyntaxError`) → Scout uses regex-only analysis
- Invalid LLM output → Transformer sets status to `failed`
- LLM timeout → Retry with exponential backoff (3 attempts)
- pytest crash (`subprocess.CalledProcessError`) → Tester sets confidence=0.0, logs issues
- Git conflict (`GitCommandError`) → Validator reverts, status to `failed`
- Insufficient budget for file → Skip file, log WARNING

**System Errors (Fatal)** — Save state and terminate:
- Invalid API key (`401 Unauthorized`) → Immediate stop with clear error message
- Global budget exhausted → Clean stop, export metrics
- Corrupted JSON (`JSONDecodeError`) → Attempt recovery, or stop
- Disk full (`OSError`) → Clean stop, log error

In all cases: pheromone state is saved before termination (JSON files remain consistent via file locking)

### Testing

Implement a comprehensive test suite with three levels:

**Unit Tests (9 tests, mocked LLM)**:
- Pheromone CRUD operations
- File locking mechanisms
- Decay and inhibition logic
- Intensity normalization
- Pattern detection (AST + regex)
- Prompt building
- Guardrail enforcement
- State machine transitions

**Integration Tests (4 tests, real pheromone store)**:
- Scout → Transformer handoff
- Transformer → Tester handoff
- Tester → Validator handoff
- Full single-file migration cycle

**End-to-End Test (1 test, real API calls)**:
- Complete migration of synthetic repo (~15 files, covering all 19 Python 2 patterns)

## Logging

Two distinct log streams:

**1. Operational Log** (Python `logging` standard):
- Level: `INFO` by default, `DEBUG` with `--verbose` flag
- Format: `{timestamp} {level} [{agent}] {message}`
- Output: stdout + rotating file `logs/stigmergic.log`
- Content: agent activity, decisions, metrics

**2. Audit Log** (JSONL append-only):
- File: `pheromones/audit_log.jsonl`
- Format: one JSON object per line
- Content: every pheromone modification with agent, timestamp, before/after values
- Purpose: satisfies RQ3 (EU AI Act Art. 14 traceability requirement)

## Language

The specification documents in `consigne/` are written in French. Code, comments, and documentation should be in English.

## Documentation

All development work should be documented in `documentation/` for thesis annex purposes:
- Log construction decisions in `construction_log.md`
- Document significant technical choices in `decisions/`
- Keep running notes in `technical_notes.md`

### Development Workflow

This POC follows a two-phase workflow:
- **Planning Phase (Claude)**: Architecture design, specification, and implementation planning
  - See `consigne/plan_poc_stigmergique.md` for detailed architecture (1200+ lines)
  - See `CLAUDE.md` for high-level guidance to Claude Code
- **Implementation Phase (Codex)**: Code generation, testing, and verification based on the established plan
  - Follow the specifications in `consigne/plan_poc_stigmergique.md`
  - Use the tech stack and patterns defined by Claude
  - Implement the test suite as specified below

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
- `AGENTS.md` — If architecture changes
- `CLAUDE.md` — If workflow changes

### Workflow Files
- **Checklist**: `.agent/workflows/end-of-sprint.md` — Complete validation checklist
- **Script**: `scripts/sprint_end.sh` — Automated validation (tests, linting, formatting)

## Update

Always update AGENTS.md and CLAUDE.md when you make changes to the project. To stay updated with the latest changes, use the command `git log -1` to see the last commit message.
