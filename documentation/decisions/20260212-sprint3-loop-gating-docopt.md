# 005 Sprint 3 Full Orchestration Loop with Blocking Gate on `docopt/docopt@0.6.2`

**Date** : 2026-02-12

**Status** : Accepted

**Context** : Lotfi + Codex (GPT-5)

---

## Context

Sprint 2.5 provided reproducible local/Docker execution but did not yet enforce the Sprint 3 end-to-end acceptance gate:
1) synthetic fixture run, and
2) real repository run on `docopt/docopt` tag `0.6.2`,
both with at least `80%` validated files and full metrics artifacts.

The implementation also needed to remain adaptive across all `.py` files (no hardcoded source-only filtering), while avoiding instability from script entrypoints, optional dependencies, and markdown-corrupted LLM outputs.

## Alternatives Considered

### Alternative 1: Keep previous fallback logic and tune only thresholds

**Description** : Keep compile/import failure as strictly blocking and adjust validator thresholds only.

**Advantages** :
- Minimal code changes
- Preserves strict interpretation of fallback failures

**Drawbacks** :
- Repeated false negatives on script-style files (`Usage:` exits) and optional dependencies
- Real gate on `docopt@0.6.2` remained below 80% in practice

---

### Alternative 2: Hardcode file scope exclusions (tests/examples/setup)

**Description** : Skip selected file categories to increase success rate.

**Advantages** :
- Fast path to higher validated ratio
- Lower token usage

**Drawbacks** :
- Violates Sprint constraint: no static hardcoded scope filtering
- Weakens thesis claims on adaptive stigmergic behavior

---

### Alternative 3: Adaptive fallback + robust orchestration + Docker hardening (Chosen)

**Description** : Implement full Sprint 3 loop/CLI/metrics, keep all `.py` in scope, and improve fallback/test classification plus runtime robustness (LLM output sanitation, Docker mount-safe behavior).

**Advantages** :
- Meets Sprint 3 functional scope and acceptance criteria
- Preserves adaptive behavior without static exclusions
- Works in both local and Docker paths with reproducible artifacts

**Drawbacks** :
- Higher implementation complexity
- Longer run times on real repository

---

## Decision

**Chosen option** : Alternative 3

**Rationale** :
- Delivers complete Sprint 3 feature set (loop + CLI + metrics + review + dry-run + maintenance).
- Resolves practical false negatives in fallback quality evaluation while keeping migration-related import failures strict (e.g., `urllib2` remains related failure).
- Ensures Docker execution remains reliable on macOS by handling mountpoint cleanup and target repo persistence safely.
- Validates the gate on both required repositories with required export artifacts.

## Consequences

### Positive
- Blocking gate now passes locally and in Docker for both synthetic and real repositories.
- Full run artifacts (`ticks.csv`, `summary.json`, `manifest.json`) are generated per run.
- Round-robin loop has explicit, auditable stop reasons and retry maintenance.
- Review and dry-run workflows are operational for controlled human intervention.

### Negative
- Real-repo runs are costlier in tokens/time.
- Additional complexity in fallback classification and Docker orchestration path.

### Code Impact
- Added: `main.py`, `stigmergy/loop.py`, `metrics/collector.py`, `metrics/export.py`, `metrics/__init__.py`
- Modified: `environment/pheromone_store.py`, `agents/tester.py`, `agents/validator.py`, `agents/transformer.py`, `stigmergy/llm_client.py`, `stigmergy/config.yaml`
- Modified: `docker-compose.yml`, `Makefile`
- Added tests: `tests/test_loop.py`, `tests/test_metrics.py`, `tests/test_main.py`
- Extended tests: `tests/test_tester.py`, `tests/test_validator.py`, `tests/test_pheromone_store.py`, `tests/test_llm_client.py`

## Validation

**Success criteria** :
1. [x] Full test suite passes locally and in Docker.
2. [x] Synthetic run reaches `>=80%` validated.
3. [x] Real `docopt@0.6.2` run reaches `>=80%` validated.
4. [x] Each run exports `run_{id}_ticks.csv`, `run_{id}_summary.json`, `run_{id}_manifest.json`.

**Executed checks** :
```bash
uv run pytest tests/ -q
uv run python main.py --repo tests/fixtures/synthetic_py2_repo --config stigmergy/config.yaml --seed 42 --verbose
uv run python main.py --repo https://github.com/docopt/docopt.git --repo-ref 0.6.2 --config stigmergy/config.yaml --seed 42 --verbose

docker compose run --rm test
REPO=tests/fixtures/synthetic_py2_repo docker compose run --rm migrate
REPO=https://github.com/docopt/docopt.git REPO_REF=0.6.2 docker compose run --rm migrate
```

**Observed gate results** :
- Local synthetic: `19/20 validated` (`95%`)
- Local docopt: `21/23 validated` (`91.3043%`)
- Docker synthetic: `19/20 validated` (`95%`)
- Docker docopt: `20/23 validated` (`86.9565%`)

## References

- `consigne/plan_poc_stigmergique.md`
- `documentation/decisions/20260212-sprint2.5-docker-infrastructure.md`
- `AGENTS.md`
- `CLAUDE.md`

## Metadata

- **Created by** : Codex (GPT-5)
- **Validated by** : Local + Docker execution evidence
- **Version** : 1.0
- **Last modified** : 2026-02-12
