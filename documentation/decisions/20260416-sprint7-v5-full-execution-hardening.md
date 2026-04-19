# ADR 014 — Sprint 7 V5-Full Execution Hardening

## Status
Accepted

## Date
2026-04-16

## Context

The V5 TravelPlanner execution plan required four concrete capabilities that were still missing after Sprint 6:
- a V5-full preset that increases the execution budget (`max_ticks`, `num_agents`)
- marker shaping inside the TravelPlanner adapter to preserve productive retries and penalize invalid plan paths
- train-only prompt enrichment and train-only hyperparameter tuning
- a benchmark runner interface that matches the plan's CLI and scores the requested subset correctly

The plan also explicitly forbids changes to `core/`, to the vendored official TravelPlanner scorer, and to validation-set purity during tuning.

## Decision

1. Keep all V5-full execution changes in `adapters/travelplanner/`, `config/`, and `scripts/`, with no `core/` modifications.
2. Implement marker shaping only at the TravelPlanner tool layer:
   - empty deterministic searches keep intensity unchanged
   - empty plans reset the planning marker to `intensity=0.8`
   - failed validations boost the validator marker and optionally inhibit the faulty plan path
3. Load prompt few-shots from `osunlp/TravelPlanner` split `train` only, with warning-only fallback if the dataset is unavailable.
4. Implement train-only ACO tuning through generated temporary configs that switch the dataset split to `train`, while preserving `config/ablation/v5_full.yaml` as a validation preset except for the selected `alpha`, `beta`, and `selection_temperature`.
5. Extend the existing benchmark runner rather than replacing it:
   - add the `stigmergic` alias
   - add inclusive `--start` / `--end`
   - pass the evaluated subset bounds to the official scorer

## Consequences

### Positive
- The V5-full plan is now executable without breaking the shared runtime contract.
- Scientific purity is preserved: few-shots and tuning remain train-only, while the reusable base preset stays validation-oriented.
- Benchmark commands written in the plan now map directly to the runner behavior.

### Trade-offs
- TravelPlanner tool logic becomes more stateful because prompt loading and shaping decisions now influence marker dynamics.
- Full local validation depends on the `langgraph` package being available, because the repository now includes a LangGraph baseline test module.
- The tuning and final benchmark campaigns remain intentionally manual because they are time- and cost-heavy.

## Alternatives considered

1. Modify `core.pressure` or `core.orchestrator` for shaping.
   - Rejected: violates the plan constraint and would blur the adapter/runtime boundary.
2. Rewrite `v5_full.yaml` through a full YAML dump during tuning.
   - Rejected: would erase the human-readable header comments that describe the preset contract.
3. Add a separate benchmark runner for V5.
   - Rejected: higher maintenance cost than extending the existing runner with compatible aliases and subset propagation.

## Validation evidence

- `uv run pytest tests/unit/test_config.py tests/unit/test_travelplanner_tools.py tests/unit/test_travelplanner_marker_shaping.py tests/unit/test_travelplanner_benchmark_runner.py tests/unit/test_tune_aco_travelplanner.py -q` -> `43 passed`
- `uv run --with 'langgraph>=1.0.0' pytest tests/ -q` -> `275 passed`
