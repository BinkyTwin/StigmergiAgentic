# ADR 013: Sprint 5 V3 Memory, Emergence, and Lesson Markers

- **Date**: 2026-03-04
- **Status**: Accepted
- **Scope**: Runtime cognition and observability extension over Sprint 4 V3

## Context

Sprint 4 V3 stabilized async/typed orchestration but still lacked three capabilities needed for thesis-grade analysis:
- agent-level episodic recall to influence future decisions
- explicit emergence telemetry aligned with tick-level runtime behavior
- reusable success traces beyond intensity reinforcement

Sprint 5 introduces these features while preserving marker schema and backward compatibility.

## Decision

1. Add in-agent episodic memory (`AgentMemory`) with bounded capacity and decay:
   - `remember(context, action, result, relevance, tick)`
   - `recall(current_context, current_tick, top_k)` scored by keyword overlap, relevance, and recency
   - `reinforce(entry_id, reward)` and `decay_all()`
2. Extend `Decision` payload with contextual cognition fields:
   - `tick`, `context`, `recalled_memories`, `lesson_markers`
3. Add `core/emergence.py` and compute 8 run-level metrics from `TickRow` + optional audit log:
   - specialization entropy
   - colony specialization
   - collaboration density
   - action switching rate
   - convergence tick
   - lock contention rate
   - parallel utilization
   - pressure entropy
4. Keep collaboration tracking schema-neutral by parsing append-only audit events instead of changing `Marker`.
5. Extend pressure model with optional ACO heuristic hook:
   - `compute_pressures(..., heuristic_fn=...)`
6. Deposit `lesson` markers automatically for high-quality transitions (`completed`/`verified`) using `reinforcement.lesson_threshold`.
7. Make `emergence` config section mandatory and expose emergence summary in orchestrator result + CLI dashboard.

## Consequences

### Positive
- Agents can reuse local experience across ticks with explicit bounded memory.
- Emergence is observable from runtime telemetry without offline post-processing.
- Lesson markers create a reusable long-lived signal independent from raw intensity values.
- No DB schema migration required (lesson/collaboration tracking uses existing structures).

### Tradeoffs
- More runtime state per agent (memory capacity and decay tuning now required).
- Additional config and validation complexity (`emergence`, memory, lesson threshold).
- Emergence metrics are descriptive signals; no automatic closed-loop optimization uses them yet.

## Validation Evidence

- `uv run pytest tests/ -v` -> `168 passed`
- `uv run python main.py --adapter assistant --objective "Summarize workspace status" --max-ticks 10 --agents 2`
  - emergence dashboard printed in CLI
  - emergence metrics exported in summary JSON
- SQL verification:
  - `SELECT id, marker_type, state, target FROM markers WHERE marker_type='lesson';`
  - confirms lesson marker persistence after high-quality transitions
