# ADR 012: Sprint 4 V3 Runtime Overhaul

- **Date**: 2026-03-04
- **Status**: Accepted
- **Scope**: V3 runtime reliability and coordination upgrade

## Context

Sprint 3 V2 delivered a functional generic assistant runtime but exposed critical limits for complex workflows:
- weak workspace grounding in prompts
- heuristic/untyped LLM outputs
- incomplete async execution path
- no dependency-aware marker gating
- no positive reinforcement feedback loop
- no session-isolated persistence for concurrent runs

The Sprint 4 V3 objective is to harden runtime behavior while preserving backward compatibility for existing sync paths and tool contracts.

## Decision

1. Introduce structured output contracts with Pydantic (`core/schemas.py`) and support schema-aware async LLM calls (`LLMClient.acall`).
2. Add DAG primitives (`core/dependency.py`) and enforce dependency satisfaction in agent candidate selection.
3. Add reinforcement primitives (`core/reinforcement.py`) and integrate reinforcement + backward propagation in environment deposit flow.
4. Upgrade marker persistence behavior:
   - SQL-backed filtering in `query_markers`
   - marker pruning support
   - per-session database isolation (`pheromones/<session_id>/markers.db`) when enabled.
5. Improve grounding and actionability:
   - workspace context summarization (`LocalWorkspace.get_context_summary`)
   - V3 prompt builder with workspace context/tool surface
   - typed `think` and bounded DAG-aware `decompose`.
6. Move bash execution to true async subprocess handling.
7. Expose run/session metadata in CLI and summary outputs (session id/path, reinforcement/DAG metadata).

## Consequences

### Positive
- Better runtime determinism for structured outputs and subtask dependencies.
- Safer concurrent operation through session isolation.
- Stronger orchestration signal quality via reinforcement and propagation.
- Improved model grounding with workspace-aware prompting.
- Higher test confidence through expanded unit coverage.

### Tradeoffs
- Runtime complexity increases (async budget reservation/reconciliation, new config sections).
- Additional configuration burden (`reinforcement`, `decompose`, `async`, marker decay maps/pruning/session).
- Reinforcement policy remains heuristic and may require tuning per future adapter domain.

## Validation Evidence

- `uv run pytest tests/unit -q` -> `127 passed`
- `uv run pytest tests/integration/test_assistant_run.py -q` -> `4 passed`
- `uv run pytest tests/unit tests/integration -q` -> `131 passed`
