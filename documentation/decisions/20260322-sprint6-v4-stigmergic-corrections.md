# ADR 013 — Sprint 6 V4 Stigmergic Corrections and Opt-In Runtime Adaptivity

## Status
Accepted

## Date
2026-03-22

## Context

The Sprint 6 V3 runtime already implemented indirect coordination through markers, but an OC1-OC5 alignment audit highlighted four scientific weaknesses relative to stigmergic theory:
- agents perceived the full global snapshot instead of a local neighborhood
- marker evaporation was only maintenance-driven, not time-continuous
- reinforcement was explicit-success-driven only, not traffic-sensitive
- lock arbitration and emergence metrics were not reused as adaptive control signals

The thesis needs a stronger stigmergic claim without breaking the existing runtime contract, domain adapters, or current tests.

## Decision

1. Introduce **opt-in local sensing** in `core.agent` through an `AgentAffinityProfile` and per-agent candidate filtering/scoring.
2. Introduce **read-time temporal decay** through `Marker.last_active_at`, SQLite migration support, and `effective_intensity()` applied during `Environment.snapshot()`.
3. Introduce **frequentation reinforcement** via a `marker_reads` table, `record_read()`/`read_count()`, and maintenance-time reinforcement boosts.
4. Introduce **opt-in emergent conflict resolution** in the orchestrator using affinity-weighted stochastic contender selection with sequential fallback.
5. Introduce an **opt-in emergence feedback loop** that adapts in-memory runtime parameters from computed emergence metrics and audits those adaptations.
6. Keep all five capabilities disabled by default in YAML config to preserve backward-compatible behavior.

## Consequences

### Positive
- The runtime now supports a more defensible stigmergic interpretation: local perception, continuous evaporation semantics, path reinforcement by traffic, and adaptive feedback.
- The implementation remains adapter-neutral and preserves the existing public runtime surfaces.
- The new capabilities are composable and can be benchmarked incrementally per feature.

### Trade-offs
- Runtime complexity increases, especially in `core.agent`, `core.marker_store`, and `core.orchestrator`.
- Emergent-resolution stochasticity introduces more non-determinism when enabled.
- The current change validates infrastructure and tests, but benchmark impact still needs dedicated TravelPlanner measurement.

## Alternatives considered

1. Hard-replace the old runtime behavior.
   - Rejected: would break backward compatibility and invalidate current baselines/tests.
2. Implement only local sensing and stop there.
   - Rejected: the audit identified multiple distinct theoretical gaps, not a single one.
3. Keep emergence metrics as post-hoc analytics only.
   - Rejected: does not address the lack of adaptive feedback in the runtime itself.

## Validation evidence

- `uv run pytest tests/unit tests/integration -q` -> `235 passed`
- `uv run pytest tests/ -q` -> `235 passed`
