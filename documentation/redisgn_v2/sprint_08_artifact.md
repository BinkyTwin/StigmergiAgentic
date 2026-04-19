# Sprint 08 — V6 General Runtime Improvement Artifact

## Sprint scope

Sprint 8 implements the first executable wave of the V6 framework plan without touching the benchmark contract:
- freeze `config/ablation/v5_full.yaml` and add V6 ablation presets (`v6_base`, `v6_A`, `v6_B`, `v6_C`)
- add explicit per-marker lock contention telemetry in the generic runtime
- implement a unified recovery controller for stagnation (`recovery_controller`)
- add short-horizon stickiness in agents, automatically disabled while recovery is active
- add a generic targeted-repair contract plus runtime repair-marker deposition
- bridge TravelPlanner validation to the generic repair contract behind an opt-in config flag

## Current artifact behavior

The generic runtime now exposes three new V6 mechanisms:

1. **Explicit contention telemetry**
   - every lock attempt is recorded in `marker_lock_events`
   - the store exposes aggregated `lock_stats` and `lock_stats_snapshot`
   - environment snapshots inject `runtime_lock_stats` into marker payloads for agent-side control

2. **Unified stagnation recovery controller**
   - activation requires:
     - no recent terminal progress
     - pending work still present
     - recent contention above threshold
     - cooldown respected
   - once active, the controller can:
     - boost effective selection temperature temporarily
     - apply temporary inhibition relief in snapshots
     - bias target choice away from recently contested markers
     - extend the effective idle threshold through dynamic idle
   - each activation is audited as `recovery_activation`

3. **Targeted repair contract**
   - tools may now return structured `ValidationResult` + `RepairRequest`
   - when `orchestrator.targeted_repair.enabled=true`, the runtime creates a generic `repair` marker
   - the repair marker clones the target payload, injects compact feedback, and stays executable through the target tool contract

TravelPlanner now supports two validation-repair modes:
- legacy mode: validator directly requeues the plan marker
- V6-C mode: validator emits the generic repair contract, and the runtime creates the repair marker while TravelPlanner keeps its own validation logic and feedback semantics

## Public interfaces and contracts

### Configs

- `config/ablation/v5_full.yaml` — frozen V5 reference
- `config/ablation/v6_base.yaml` — V5 reference + `idle_cycles_to_stop=16`
- `config/ablation/v6_A.yaml` — V6 base + recovery controller
- `config/ablation/v6_B.yaml` — V6-A + stickiness
- `config/ablation/v6_C.yaml` — V6-A + targeted repair

### Core runtime

- `core.marker_store.MarkerStore`
  - `record_lock_attempt`
  - `lock_stats`
  - `lock_stats_snapshot`
- `core.tool_registry`
  - `RepairRequest`
  - `ValidationResult`
  - `build_repair_marker_id`
- `core.environment.Environment`
  - snapshot control overlays
  - runtime repair-marker deposition
- `core.orchestrator.Orchestrator`
  - recovery controller
  - dynamic idle computation
  - control telemetry in `TickRow.control`

## Guardrails and constraints

- `config/ablation/v5_full.yaml` remains unchanged
- `third_party/travelplanner_official/` remains unchanged
- `scripts/eval_travelplanner_official.py` remains unchanged
- benchmark semantics are preserved; no scorer or split changes are introduced in this sprint
- stickiness is automatically disabled while recovery is active to avoid controller competition
- targeted repair stays opt-in and adapter logic remains outside `core/`

## Known limits / not executed in this session

- paired-seed `v5_full` vs `v6_base` reruns were not executed here
- the comparative V6 benchmark campaign (`V6-base`, `V6-A`, `V6-B`, `V6-C`) was not executed here
- `V6.2` persistent subgoal coverage is intentionally not implemented in this sprint
- full repository validation with optional `langgraph` dependency was not rerun in this task

## Validation evidence

- `uv run pytest tests/unit/test_config.py tests/unit/test_marker_store.py tests/unit/test_environment.py tests/unit/test_agent.py tests/unit/test_orchestrator.py tests/unit/test_travelplanner_tools.py -q` -> `77 passed`
- `uv run pytest tests/integration/test_travelplanner.py -q` -> `5 passed`
