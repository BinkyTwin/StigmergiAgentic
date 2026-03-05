# Sprint 06 — Current Artifact Functioning

## Sprint scope

Sprint 6 V3 introduces the first application-domain adapter (`travelplanner`) on top of the stabilized V3 runtime:
- legacy V0.1 cleanup (obsolete runtime and tests removed)
- TravelPlanner database/query integration
- domain workspace, tools, adapter, and evaluator
- CLI support for `--adapter travelplanner`
- domain validation tests (unit + integration)

## Current artifact behavior

The `travelplanner` mode now executes a domain-specific DAG:

1. parallel search markers (flights/hotels/attractions)
2. itinerary planning marker (`plan_itinerary`)
3. constraint validation marker (`validate_constraints`) with bounded replanning loop
4. finalization marker producing the final plan/evaluation payload

Tool behavior:
- search tools are deterministic (CSV filters)
- planning is LLM-backed with strict JSON schema + fallback planner
- validation is fully programmatic (commonsense/hard constraints)

## Public interfaces and contracts

### New adapter package

- `adapters.travelplanner.adapter.TravelPlannerAdapter`
- `adapters.travelplanner.workspace.TravelPlannerWorkspace`
- `adapters.travelplanner.tools.*`
- `adapters.travelplanner.evaluator.TravelPlannerEvaluator`

### Updated shared APIs

- `core.schemas.TravelDayPlan`
- `core.schemas.TravelItineraryOutput`
- `main.py`
  - supports `--adapter assistant|travelplanner`
  - supports `--data-dir`, `--query-idx`

### Config and setup

- `config/travelplanner.yaml`
- `scripts/setup_travelplanner.py`

## Guardrails and constraints

- Domain validation retries bounded in `ValidateConstraintsTool` (`max_retries=2` for replanning branch)
- Marker lifecycle remains state-machine validated by `Environment.apply_action_result`
- Runtime budget/traceability/lock TTL remain enforced by core guardrails
- CSV/database loading is explicit and fails fast when missing

## Known limits / not implemented yet

- CodeMigration adapter (V2) still not implemented
- SWE-bench adapter still not implemented
- Baseline runners aligned with V3 runtime still not implemented
- Pareto instrumentation aligned with V3 runtime still not implemented
- No official full validation-set benchmark campaign persisted yet in this sprint artifact

## Validation evidence

- `uv run pytest tests/unit tests/integration -q` -> `204 passed`
- `uv run pytest tests/ -q` -> `209 passed`
- `uv run python scripts/setup_travelplanner.py --output-dir /tmp/travelplanner_db_check --force` -> setup + integrity check passed

