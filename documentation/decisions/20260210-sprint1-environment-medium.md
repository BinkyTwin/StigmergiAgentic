# 002 Sprint 1 Environment Medium and Runtime Standardization

**Date** : 2026-02-10

**Status** : Accepted

**Context** : Lotfi + Codex

---

## Context

Sprint 1 requires the stigmergic medium to work independently from agents. The implementation must provide:
- JSON-based pheromone persistence with concurrency safety
- Environmental guardrails (budget, anti-loop, scope lock, TTL, traceability)
- Deterministic decay behavior for task intensity and inhibition gamma
- Reproducible local execution for thesis annex evidence

Academic constraints include full traceability (RQ3) and reproducibility of experiments.

## Alternatives Considered

### Alternative 1: Plain JSON store without locking

**Description** : Simple read/write operations on JSON files, no file lock.

**Advantages** :
- Fast to implement
- Minimal code complexity

**Drawbacks** :
- Unsafe under concurrent writes
- Risk of JSON corruption
- Weak scientific reproducibility

---

### Alternative 2: SQLite store for all pheromones

**Description** : Replace JSON files with a transactional SQLite DB.

**Advantages** :
- Strong consistency guarantees
- Better query capabilities

**Drawbacks** :
- Diverges from the planned JSON artifact model
- Higher implementation overhead for Sprint 1
- Less aligned with explicit artifact inspectability in the current plan

---

### Alternative 3: JSON store + `fcntl.flock` + append-only audit (Chosen)

**Description** : Keep JSON artifacts as specified, enforce file locks, and append every mutation to an audit log.

**Advantages** :
- Matches the architecture plan exactly
- Preserves inspectable artifacts (`tasks.json`, `status.json`, `quality.json`)
- Provides reliable traceability via `audit_log.jsonl`
- Feasible within Sprint 1 timeline

**Drawbacks** :
- Query model remains basic vs database systems
- Locking approach is POSIX-specific

---

## Decision

**Chosen option** : Alternative 3

**Rationale** :
- Directly aligned with the PoC architecture in `consigne/plan_poc_stigmergique.md`
- Satisfies traceability and auditability requirements for RQ3
- Keeps implementation scope controlled for Sprint 1 while providing concurrency safety
- Supports deterministic tests and reproducible local execution through `uv`

## Consequences

### Positive
- Reliable JSON CRUD under concurrent access
- Guardrails enforced centrally by the environment
- Append-only audit trail available for thesis evidence
- Reproducible local environment (`uv`, Python 3.11)

### Negative
- Limited query expressiveness compared to SQL
- Platform dependency on POSIX locking semantics

### Code Impact
- Added: `environment/pheromone_store.py`
- Added: `environment/guardrails.py`
- Added: `environment/decay.py`
- Added: `tests/test_pheromone_store.py`
- Added: `tests/test_guardrails.py`
- Added: `stigmergy/config.yaml`

### Methodology Impact
- Enables measurable verification of RQ3 through audit logs
- Establishes Sprint 1 acceptance baseline for future sprints

## Validation

**Success criteria** :
1. [x] Store CRUD + query + locking implemented
2. [x] Guardrails behavior covered by tests
3. [x] Decay/inhibition logic covered by tests
4. [x] `uv run` workflow validated with Python 3.11

**Executed tests** :
```bash
uv run pytest tests/test_pheromone_store.py -v
uv run pytest tests/test_guardrails.py -v
uv run pytest tests -v -k "pheromone or guardrails"
```

**Implementation result** :
- [x] All criteria validated
- [x] Decision confirmed

## References

- `consigne/plan_poc_stigmergique.md`
- Ricci et al. (2007), Agents & Artifacts
- EU AI Act Article 14 traceability requirements (as cited in project corpus)

## Metadata

- **Created by** : Codex
- **Validated by** : Auto-validated with test evidence
- **Version** : 1.0
- **Last modified** : 2026-02-10
