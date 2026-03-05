# Sprint 05 — Current Artifact Functioning

## Sprint scope

Sprint 5 V3 extends the runtime with adaptive memory and emergence observability:
- per-agent episodic memory (`remember`, `recall`, `reinforce`, `decay_all`)
- emergence metrics computed from tick telemetry and audit log traces
- optional ACO heuristic function in pressure computation
- automatic lesson marker deposition on high-quality transitions
- memory/lesson prompt injection and CLI emergence dashboard

## Current artifact behavior

The artifact now executes a memory-aware stigmergic loop:

- Agents recall top-k episodic entries before deciding an action.
- Decisions carry recalled memory payloads and recent lesson markers.
- `think` prompt construction includes workspace context, episodic memory context, and reusable lessons.
- Environment deposits `lesson` markers when quality exceeds threshold on `completed/verified` transitions.
- Orchestrator computes run-level emergence metrics at end-of-run and stores per-tick emergence payload.
- CLI displays an emergence dashboard and includes emergence summary in JSON output.

## Public interfaces and contracts

### New core module

- `core.emergence`
  - `EmergenceMetrics`
  - `compute_emergence_metrics(tick_rows, total_agents, audit_log_path=None)`

### Updated runtime APIs

- `core.agent`
  - `MemoryEntry`
  - `AgentMemory`
  - `StigmergicAgent.memory`
- `core.tool_registry.Decision`
  - added fields: `tick`, `context`, `recalled_memories`, `lesson_markers`
- `core.pressure.compute_pressures(...)`
  - added optional `heuristic_fn: Callable[[Marker, str], float] | None`
- `core.orchestrator.TickRow`
  - added field: `emergence`
- `core.orchestrator.OrchestratorResult`
  - added field: `emergence_summary`

## Guardrails and constraints

- Config validation now requires `emergence` top-level section.
- New config checks:
  - `emergence.enabled` must be boolean
  - `emergence.metrics` must be non-empty list of strings
  - `agents.memory_capacity >= 1`
  - `agents.memory_decay_rate in [0, 1]`
  - `reinforcement.lesson_threshold in [0, 1]` when set
- Lesson markers use existing marker schema; no DB schema migration required.
- Marker mutations remain transactional with append-only audit events.

## Known limits / not implemented yet

- TravelPlanner adapter not implemented.
- CodeMigration adapter (V2) not implemented.
- SWE-bench adapter not implemented.
- Baseline runners/Pareto instrumentation still not fully aligned with V3 runtime.
- Emergence metrics are post-run aggregates; no online adaptive policy currently consumes them.

## Validation evidence

- `uv run pytest tests/ -v` -> `168 passed`
- `uv run python main.py --adapter assistant --objective "Summarize workspace status" --max-ticks 10 --agents 2`
  - emergence dashboard printed in CLI
  - emergence summary exported in JSON
- SQL check for lesson markers:
  - `SELECT id, marker_type, state FROM markers WHERE marker_type='lesson';`
