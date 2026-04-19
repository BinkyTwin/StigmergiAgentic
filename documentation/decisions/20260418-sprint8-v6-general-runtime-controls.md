# ADR 015 — Sprint 8 V6 General Runtime Controls and Targeted Repair

## Status
Accepted

## Date
2026-04-18

## Context

The V6 framework-improvement plan explicitly requires:
- a paired-seed-ready baseline branch (`v6_base`) without touching `v5_full.yaml`
- a framework-general anti-stagnation controller based on real lock contention, not `marker_reads`
- a short-horizon stability mechanism that must not compete with the recovery controller
- a generic targeted-repair contract that adapters can opt into without moving domain logic into `core/`

The repository already had a generic emergence feedback loop and a TravelPlanner-local `validate -> feedback -> replan` pattern, so the implementation had to add control-plane leverage without introducing competing runtime controllers or benchmark drift.

## Decision

1. Implement V6 phase-1 controls as explicit opt-in runtime surfaces:
   - `orchestrator.recovery_controller`
   - `agents.stickiness`
   - `orchestrator.targeted_repair`
2. Add explicit lock-attempt instrumentation in `core.marker_store` through a dedicated `marker_lock_events` table and expose aggregated `lock_stats` / `lock_stats_snapshot`.
3. Keep the recovery controller in `core.orchestrator` as a bounded runtime overlay:
   - activation requires recent terminal stagnation, pending work, sufficient recent lock contention, and cooldown satisfaction
   - recovery only applies temporary temperature boost and inhibition relief, plus conflict-aware target preference
   - dynamic idle remains in the same control surface
4. Implement stickiness in `core.agent` as a small, short-lived bonus on the last productive action/target, and disable it automatically while recovery is active.
5. Extend `core.tool_registry.ActionResult` with structured `ValidationResult` / `RepairRequest`, and let `Environment.apply_action_result` materialize generic repair markers only when `targeted_repair` is enabled.
6. Bridge TravelPlanner to the generic repair contract without moving TravelPlanner validation semantics into `core/`:
   - keep TravelPlanner validation and feedback generation in `adapters/travelplanner/tools.py`
   - when opt-in repair is enabled, emit the structured repair contract and let the runtime create the repair marker
7. Preserve benchmark hygiene by adding new V6 presets (`v6_base`, `v6_A`, `v6_B`, `v6_C`) while leaving `config/ablation/v5_full.yaml` unchanged.

## Consequences

### Positive
- The V6 plan is now executable as a clean framework-general phase-1 implementation.
- Contention is measured from real lock outcomes rather than perception-side reads.
- Recovery, stickiness, and targeted repair can be ablated independently through config.
- TravelPlanner can consume the generic repair contract without contaminating `core/` with domain rules.

### Trade-offs
- Runtime complexity increases: snapshots now carry ephemeral control overlays and lock telemetry.
- Targeted repair introduces a second class of executable markers (`repair`) that adapters must understand if they opt in.
- The implementation provides the infrastructure and presets, but not the paired-seed benchmark evidence itself.

## Alternatives considered

1. Reuse `marker_reads` as the main contention signal.
   - Rejected: reads are a perception trace, not a direct record of failed lock attempts.
2. Mutate `v5_full.yaml` into the new V6 baseline.
   - Rejected: the plan explicitly requires keeping the V5 reference frozen.
3. Keep targeted repair fully TravelPlanner-local.
   - Rejected: would not satisfy the framework-general contract required by V6-C.
4. Add a second independent controller beside the existing feedback loop.
   - Rejected: the V6 review explicitly warned against competing adaptive controllers.

## Validation evidence

- `uv run pytest tests/unit/test_config.py tests/unit/test_marker_store.py tests/unit/test_environment.py tests/unit/test_agent.py tests/unit/test_orchestrator.py tests/unit/test_travelplanner_tools.py -q` -> `77 passed`
- `uv run pytest tests/integration/test_travelplanner.py -q` -> `5 passed`
