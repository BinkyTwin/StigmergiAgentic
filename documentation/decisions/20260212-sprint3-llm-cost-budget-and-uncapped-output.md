# 006 Sprint 3 LLM Cost Budgeting with Uncapped Output Tokens

**Date** : 2026-02-12

**Status** : Accepted

**Context** : Lotfi + Codex (GPT-5)

---

## Context

Sprint 3 gate runs showed that a hard `max_response_tokens=4096` completion cap could degrade migration quality for thinking-heavy models: files were retried repeatedly instead of receiving one complete high-quality transform.  
At the same time, token-only budgeting (`max_tokens_total`) did not provide direct spend control in USD.

The runtime needed two improvements:
1. disable hard output truncation by default, and
2. track/enforce an optional USD budget using OpenRouter pricing + real usage cost.

## Alternatives Considered

### Alternative 1: Keep hard output cap and token-only budget

**Advantages** :
- Simple and deterministic cap.
- No extra pricing logic.

**Drawbacks** :
- Increased retry loops on complex files.
- Budget cannot be interpreted directly as monetary cost.

---

### Alternative 2: Uncap output, no budget guard

**Advantages** :
- Best chance of complete transformations.
- Very simple behavior.

**Drawbacks** :
- Unbounded spend risk.
- Harder to compare runs with controlled cost envelopes.

---

### Alternative 3: Uncap output + dual budget guard (tokens and USD) (Chosen)

**Description** : Set `max_response_tokens=0` (omit `max_tokens` in API call), keep token budget, and add optional cost budget:
- fetch model pricing from OpenRouter (`/api/v1/models/user`) for pre-call estimate,
- read `usage.cost` post-call when returned by provider,
- export cumulative cost in run metrics.

**Advantages** :
- Preserves thinking-heavy model behavior.
- Adds spend-aware control without losing existing token guardrail.
- Improves observability for thesis cost/quality analysis.

**Drawbacks** :
- Additional client complexity.
- Pricing endpoint/network dependency for pre-call estimation (with graceful fallback).

---

## Decision

**Chosen option** : Alternative 3

**Rationale** :
- Hard completion caps were counterproductive for this migration workload.
- Cost governance must be explicit in USD for reproducible benchmark comparisons.
- OpenRouter already exposes both model pricing and per-request `usage.cost`, enabling robust accounting.

## Consequences

### Positive
- API requests no longer enforce a hard output cap when `max_response_tokens <= 0`.
- Optional `llm.max_budget_usd` can stop runs by spend, in addition to `max_tokens_total`.
- Summary/tick metrics now include `total_cost_usd` (and per-file cost metric).

### Negative
- Slightly more configuration surface.
- If pricing endpoint is unavailable, pre-call cost estimate may be skipped unless strict mode is enabled.

### Code Impact
- Modified: `stigmergy/llm_client.py` (uncapped request payload + cost tracking + pricing fetch + cost pre-check)
- Modified: `stigmergy/loop.py` (cost-based stop condition)
- Modified: `metrics/collector.py`, `metrics/export.py` (cost metrics)
- Modified: `main.py` (`--max-budget-usd`, manifest budget fields)
- Modified: `stigmergy/config.yaml` (cost budget/pricing keys)
- Extended tests: `tests/test_llm_client.py`, `tests/test_loop.py`, `tests/test_main.py`, `tests/test_metrics.py`

## Validation

**Executed checks** :
```bash
uv run pytest tests/test_llm_client.py tests/test_loop.py tests/test_metrics.py tests/test_main.py -v
uv run pytest tests/ -q
uv run python main.py --repo tests/fixtures/synthetic_py2_repo --config stigmergy/config.yaml --seed 42 --max-ticks 1 --verbose
```

**Observed results** :
- `60 passed, 1 skipped` on full test suite.
- Live one-tick run confirms:
  - no explicit `max_tokens` in request payload (uncapped mode),
  - `total_cost_usd` present in run summary.

## References

- [OpenRouter models endpoint](https://openrouter.ai/docs/api-reference/list-available-models)
- [OpenRouter chat completion response (`usage.cost`)](https://openrouter.ai/docs/api-reference/chat/send-chat-completion-request)
- `documentation/decisions/20260212-sprint3-loop-gating-docopt.md`

## Metadata

- **Created by** : Codex (GPT-5)
- **Version** : 1.0
- **Last modified** : 2026-02-12
