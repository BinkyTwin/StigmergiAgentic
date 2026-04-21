# ADR 017 — Sprint 9 Full Implementation: Persistent Skills, Protocol Artifacts, and Cross-Run Coordination

- Date: 2026-04-21
- Status: Accepted

## Context

ADR 016 introduced the groundwork (config seams, schema, prompts, adapter/runtime stubs) for Sprint 9. This ADR records the completion of the functional implementation for the three thesis claims C1, C2, and C3.

The Sprint 8 runtime provided the substrate; Sprint 9 now adds:
1. **Persistence layer** — two new SQLite stores (`skills.db`, `protocols.db`) with `session_isolation=False` for cross-run visibility.
2. **Promotion logic** — lesson markers reaching quality/usage thresholds are promoted to durable skill markers.
3. **Protocol evolution** — emergence metrics are persisted per config namespace; the best protocol is recalled and applied clamped to the next run.
4. **Protocol compilation** — both assistant and TravelPlanner domains can generate task DAGs from objectives via LLM-conditioned compilation.

## Decision

1. **Separate stores with cross-run semantics**
   - `skills_store` and `protocol_store` are dedicated `MarkerStore` instances with `session_isolation=False` and `traceability=False`.
   - This isolates cross-run artifacts from per-run session data without changing the `MarkerStore` internals.

2. **Skill promotion as a side-effect of action success**
   - `_maybe_promote_to_skill()` is called inside `Environment.apply_action_result()`, not inside the agent.
   - This keeps promotion policy as an environment-enforced guardrail rather than an agent-level heuristic.

3. **Protocol namespace hashing**
   - `_build_protocol_namespace()` uses MD5 of `{adapter, model, alpha, beta}` to create stable config-scoped slots.
   - This allows A/B config comparisons without collision while keeping the key human-readable.

4. **Baseline immutability**
   - The `baseline` slot is written once and never overwritten.
   - This guarantees that `clamp_cross_run_adaptations()` always has a stable reference point.

5. **Opt-in everywhere**
   - All three features default to `enabled: false`.
   - `read_only` sub-flags allow safe evaluation/read-only replay without mutation.

## Consequences

### Positive

- Cross-run skill accumulation and protocol evolution are now end-to-end testable.
- The runtime preserves Sprint 8 behavior when Sprint 9 flags are off.
- Baseline immutability prevents config drift during long benchmark campaigns.
- Both assistant and TravelPlanner domains support protocol compilation.

### Negative

- Two additional SQLite files (`skills.db`, `protocols.db`) add disk I/O overhead.
- Protocol namespace hashing does not include the full config; exotic overrides may collide.
- Skill promotion does not yet deduplicate by semantic similarity (only by lesson ID).

## Alternatives Considered

### Single store with marker-type filtering

Rejected because session isolation is a `MarkerStore`-level flag; mixing session-scoped and global markers in one DB would require a schema change or manual filtering on every query.

### Agent-driven promotion

Rejected because promotion is a global policy (thresholds, quality gates) best enforced by the environment, not left to individual agent heuristics.

## Validation

- Full test suite: `uv run pytest tests/ -q --ignore=tests/unit/test_travelplanner_langgraph_supervisor.py` -> **307 passed**
