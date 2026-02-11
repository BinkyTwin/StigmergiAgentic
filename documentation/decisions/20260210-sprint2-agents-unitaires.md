# 003 Sprint 2 Agent Layer, LLM Client, and Synthetic Fixture Strategy

**Date** : 2026-02-11

**Status** : Accepted

**Context** : Lotfi + Codex

---

## Context

Sprint 2 requires implementing the full agent layer on top of the Sprint 1 medium:
- OpenRouter-backed LLM client with retry and budget controls
- Four specialized agents (Scout, Transformer, Tester, Validator)
- Deterministic handoff via pheromones only
- Reproducible fixture repository covering the Python 2 pattern set

The implementation must remain audit-friendly for thesis annex evidence and avoid network-dependence in default test runs.

## Alternatives Considered

### Alternative 1: Direct API-first testing for all agent flows

**Description** : Use real OpenRouter calls as the default validation path for unit and integration tests.

**Advantages** :
- High realism
- Early detection of provider regressions

**Drawbacks** :
- Non-deterministic and flaky in CI/local contexts
- Requires valid API keys and network availability
- Harder to isolate logic bugs from provider/network noise

---

### Alternative 2: Mock-only approach with no live API checks

**Description** : Keep all Sprint 2 validation fully mocked.

**Advantages** :
- Deterministic and fast
- Fully offline-compatible

**Drawbacks** :
- No direct smoke validation of OpenRouter wiring
- Risk of drift between mocks and provider behavior

---

### Alternative 3: Mock-first tests + optional non-blocking live smoke (Chosen)

**Description** : Core tests are deterministic mocks; a `live_api` smoke test exists but is skipped when key is missing/invalid.

**Advantages** :
- Keeps the suite deterministic and reproducible
- Preserves a real-provider sanity check path
- Balances scientific reproducibility and practical runtime verification

**Drawbacks** :
- Live smoke is not part of blocking acceptance
- Requires manual interpretation of skipped live tests

---

## Decision

**Chosen option** : Alternative 3

**Rationale** :
- Aligns with Sprint 2 autonomy goals while preserving robust local execution
- Supports thesis reproducibility constraints
- Enables full agent behavior validation without coupling acceptance to external API availability

## Consequences

### Positive
- All core Sprint 2 tests run locally without network dependency
- Agent handoffs are validated end-to-end via pheromone traces
- LLM integration remains verifiable through optional smoke mode

### Negative
- Live provider validation is advisory, not blocking
- Requires maintaining stable mocks as LLM client evolves

### Code Impact
- Added `stigmergy/llm_client.py`
- Added `agents/` package (`base_agent`, `scout`, `transformer`, `tester`, `validator`)
- Added synthetic fixture repository under `tests/fixtures/synthetic_py2_repo/`
- Added Sprint 2 tests (`test_llm_client`, `test_base_agent`, `test_scout`, `test_transformer`, `test_tester`, `test_validator`, `test_agents_integration`)

### Methodology Impact
- Establishes a deterministic Sprint 2 baseline for Sprint 3 loop integration
- Strengthens reproducibility and traceability evidence for annex documentation

## Validation

**Success criteria** :
1. [x] `LLMClient` retry, budget, and extraction logic validated with deterministic tests
2. [x] Each agent runs in isolation and deposits correct pheromone traces
3. [x] Integration handoffs (`Scout->Transformer->Tester->Validator`) validated
4. [x] Synthetic Python 2 fixture repository versioned and reusable

**Executed tests** :
```bash
uv run pytest tests/ -v
uv run pytest tests/ --cov
```

**Implementation result** :
- [x] All criteria validated
- [x] Decision confirmed

## References

- `consigne/plan_poc_stigmergique.md`
- Ricci et al. (2007), Agents & Artifacts
- EU AI Act Article 14 traceability requirement (project corpus)

## Metadata

- **Created by** : Codex
- **Validated by** : Auto-validated with local test evidence
- **Version** : 1.0
- **Last modified** : 2026-02-11
