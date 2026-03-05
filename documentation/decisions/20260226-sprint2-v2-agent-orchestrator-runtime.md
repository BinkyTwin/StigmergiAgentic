# ADR 010: Sprint 2 V2 Generic Agent Runtime (Pressure + Orchestrator)

- **Date**: 2026-02-26
- **Status**: Accepted
- **Scope**: V2 redesign Sprint 2 runtime layer

## Context

Sprint 1 delivered a generic marker environment (store, decay, guardrails, audit, config) but no executable multi-agent runtime. Sprint 2 requires a domain-agnostic execution layer that preserves stigmergic coordination constraints:
- indirect coordination through markers
- lock-safe concurrent execution
- environment-enforced governance
- deterministic testability with mock adapters

## Decision

1. Implement a generic action contract layer in `core/tool_registry.py`:
- `Tool` ABC
- `ToolRegistry`
- `Decision` and `ActionResult`

2. Implement pressure-driven decision primitives in `core/pressure.py`:
- normalized pressure computation by action type
- softmax/greedy selection with injectable RNG

3. Implement runtime composition and execution in:
- `core/environment.py` (store + guardrails + state machine + budgets)
- `core/agent.py` (role-free perceive/decide/execute)
- `core/orchestrator.py` (parallel tick loop, lock arbitration, stop conditions)

4. Keep orchestration asynchronous, with sync entrypoint for tests:
- `Orchestrator.run()` async
- `Orchestrator.run_sync()` sync wrapper

5. Port provider-aware LLM client into `llm/client.py` with mock-first tests:
- retries/backoff
- token/cost budget checks
- provider routing (`openrouter`, `zai`)

## Consequences

### Positive
- End-to-end generic runtime available without domain coupling.
- Lock conflict handling and budget governance stay centralized.
- Unit tests can validate parallel orchestration deterministically.
- Adapter layer contract is explicit before domain implementations.

### Tradeoffs
- Runtime telemetry is in-memory only in Sprint 2 (file export deferred).
- Existing legacy baseline/metrics modules remain out of scope and not aligned yet.
- Additional adapter work is still required for DSR iterations.

## Validation Evidence

- `uv run pytest tests/unit/test_pressure.py tests/unit/test_agent.py tests/unit/test_orchestrator.py tests/unit/test_llm_client.py -q` -> `30 passed`
- `uv run pytest tests/unit -v` -> `61 passed`
