# ADR 012 — Sprint 6 V3 TravelPlanner Adapter and Programmatic Fidelity Evaluation

## Status
Accepted

## Date
2026-03-05

## Context

After five runtime-centric sprints, Sprint 6 is the first application-domain sprint. We need to validate:
- domain portability of V3 architecture (OC1)
- benchmark-facing evaluation for TravelPlanner with paper-aligned metrics (OC3 target comparison against SwarmAgentic 32.2%)

At the same time, V0.1 legacy code paths were still present in the repository and were no longer part of the V3 runtime contract.

## Decision

1. Remove obsolete V0.1 runtime surfaces (`agents/`, `environment/`, `stigmergy/`, `baselines/`, and legacy tests).
2. Implement a dedicated `travelplanner` adapter package with:
   - CSV/HF-backed workspace
   - deterministic search tools
   - LLM-only itinerary planning tool with strict JSON schema
   - programmatic constraint validation tool with bounded retry/replan loop
3. Implement a TravelPlanner evaluator that exposes the paper-facing metrics:
   - `delivery_rate`
   - `commonsense_micro`, `commonsense_macro`
   - `hard_constraint_micro`, `hard_constraint_macro`
   - `final_pass_rate`
4. Extend CLI/runtime dispatch to support `--adapter travelplanner` and dedicated config overrides.
5. Add reproducible setup script for TravelPlanner data assets and increase test coverage with domain unit/integration suites.

## Consequences

### Positive
- Confirms V3 runtime can host a non-assistant domain adapter without core refactor.
- Keeps evaluation deterministic and auditable (no LLM in constraint validation).
- Establishes reusable adapter pattern for upcoming benchmark adapters.
- Removes dead/obsolete code, reducing maintenance risk.

### Trade-offs
- TravelPlanner evaluation logic is substantial and increases domain code footprint.
- Full benchmark campaign (10+ real validation queries with tuned prompts/weights) remains an execution step after this implementation sprint.

## Alternatives considered

1. Keep V0.1 code for backward compatibility.
   - Rejected: adds confusion and invalid test collection paths.
2. Use LLM for validation.
   - Rejected: lower determinism and weaker reproducibility for benchmark metrics.
3. Delay adapter integration until after baseline runner migration.
   - Rejected: Sprint 6 objective is explicit domain validation now.

## Validation evidence

- `uv run pytest tests/unit tests/integration -q` -> `204 passed`
- `uv run pytest tests/ -q` -> `209 passed`
- `uv run python scripts/setup_travelplanner.py --output-dir /tmp/travelplanner_db_check --force` -> setup successful

