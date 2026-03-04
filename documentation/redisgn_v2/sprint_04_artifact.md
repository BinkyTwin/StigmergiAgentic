# Sprint 04 — Current Artifact Functioning

## Sprint scope

Sprint 4 V3 overhauls runtime reliability and coordination behavior:
- structured LLM output contracts (Pydantic)
- true async LLM and subprocess execution paths
- dependency-aware marker scheduling (DAG)
- reinforcement + backward propagation
- session-isolated marker persistence
- workspace-grounded prompting
- expanded validation coverage

## Current artifact behavior

The artifact now operates as an async-first stigmergic assistant runtime:

- `LLMClient` supports `call()` and `acall()` with optional schema validation.
- `think` uses typed outputs (`ThinkOutput`) and workspace context-aware system prompts.
- `decompose` enforces depth/subtask bounds and can create dependency edges (`depends_on`) between child markers.
- Agent candidate selection filters out blocked markers until dependencies are terminal.
- Environment applies positive reinforcement on successful transitions and optional backward propagation through dependency ancestry.
- Marker maintenance applies per-type decay and pruning.
- CLI runs can be isolated by session id (`pheromones/<session_id>/markers.db`) and expose session/reinforcement/DAG metadata in run summary.

## Public interfaces and contracts

### New core modules

- `core.schemas`
  - `ThinkOutput`
  - `SubtaskSpec`
  - `DecomposeOutput`
  - `ToolResult`
  - `LLMParsedResponse`
- `core.dependency`
  - `validate_dag`
  - `build_dependency_graph`
  - `topological_sort`
  - `unblocked_markers`
- `core.reinforcement`
  - `reinforce_on_success`
  - `penalize_on_failure`
  - `propagate_backward`

### Upgraded runtime APIs

- `llm.client.LLMClient.acall(prompt, system, response_schema)`
- `core.marker_store.MarkerStore(..., session_id, session_isolation)`
- `core.marker_store.MarkerStore.prune_markers(threshold)`
- `adapters.assistant.workspace.LocalWorkspace.get_context_summary(max_depth, max_files)`
- `core.environment.Environment.apply_reinforcement(marker_id, quality_score)`
- `core.orchestrator.Orchestrator(..., session_id)` and `OrchestratorResult.session_id`

## Guardrails and constraints

- Config validation now requires and validates V3 sections:
  - `reinforcement`
  - `decompose`
  - `async`
  - marker decay map/pruning/session fields
- Budget checks are enforced in both sync and async LLM paths.
- Dependency cycles can be detected (`validate_dag`), and blocked markers are excluded from candidate sets.
- `bash_exec` remains command-allowlisted and timeout-bounded under async subprocess execution.
- Marker mutations remain transactional and auditable.

## Known limits / not implemented yet

- TravelPlanner adapter not implemented.
- CodeMigration adapter (V2) not implemented.
- SWE-bench adapter not implemented.
- baseline runners and Pareto/emergence instrumentation are not yet aligned with V3 runtime semantics.
- reinforcement policy parameters are heuristic defaults and may need per-domain tuning.

## Validation evidence

- `uv run pytest tests/unit -q` -> `127 passed`
- `uv run pytest tests/integration/test_assistant_run.py -q` -> `4 passed`
- `uv run pytest tests/unit tests/integration -q` -> `131 passed`
