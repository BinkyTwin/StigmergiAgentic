# ADR 011: Sprint 3 V2 Infrastructure Tools and Assistant Mode

- **Date**: 2026-02-26
- **Status**: Accepted
- **Scope**: V2 redesign Sprint 3 runtime enablement layer

## Context

Sprint 2 delivered a generic stigmergic core runtime, but no reusable infrastructure-tool layer and no general-purpose assistant adapter. Sprint 3 requires:
- a shared infrastructure action set usable across future adapters
- a minimal assistant mode to prove framework operation without benchmark adapters
- CLI execution path for direct end-to-end usage

## Decision

1. Add `tools/` as infrastructure-tool package implementing the same `Tool` ABC as domain tools.
   - `file_read`
   - `file_write`
   - `bash_exec`
   - `web_search`
   - `think`
   - `decompose`
   - centralized registration via `register_infrastructure_tools`

2. Add `adapters/assistant/` as minimal `DomainAdapter` implementation.
   - `LocalWorkspace` with filesystem sandboxing
   - objective mapping and initial marker seeding
   - infrastructure-tools-only registry
   - basic run evaluation output

3. Add `main.py` CLI for assistant runtime execution with config merge and run summary output.

4. Extend config model with required `tools` section and strict validation of tool-related constraints.

## Consequences

### Positive
- Framework can now run as a generic assistant without TravelPlanner/CodeMigration/SWE-bench adapters.
- Infrastructure actions are reusable by future adapters without orchestrator changes.
- Tool safety boundaries are explicit (workspace sandbox, command allowlist, size/time limits).
- Sprint 3 acceptance tests are reproducible through unit + integration gates.

### Tradeoffs
- CLI currently supports only `assistant` adapter.
- Web-search behavior depends on external provider configuration and keys.
- Initial decomposition quality is LLM-dependent, with heuristic fallback for keyless/offline runs.

## Validation Evidence

- `uv run pytest tests/unit -q` -> `81 passed`
- `uv run pytest tests/integration/test_assistant_run.py -q` -> `4 passed`
- `uv run pytest tests/unit tests/integration -q` -> `85 passed`
- `uv run python main.py --adapter assistant --objective "Create a short checklist" --max-ticks 12 --agents 1 --seed 7` -> JSON summary with `all_terminal`
