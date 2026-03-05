# Sprint 03 — Current Artifact Functioning

## Sprint scope

Sprint 3 V2 adds the infrastructure-tool layer and a generic assistant mode on top of the Sprint 2 runtime:
- infrastructure tools package (`tools/`)
- assistant domain adapter (`adapters/assistant/`)
- filesystem-rooted workspace contract (`LocalWorkspace`)
- CLI entrypoint (`main.py`) for assistant execution
- unit and integration coverage for tool/runtime behavior

## Current artifact behavior

The artifact now runs as a domain-agnostic multi-agent assistant:

- Objective is converted into one root marker by `AssistantAdapter`.
- Agents choose actions by pressure and execute registered infrastructure tools.
- `DecomposeTool` can create child markers from one objective.
- `ThinkTool` advances marker lifecycle with LLM-backed or fallback reasoning.
- File read/write, guarded bash execution, and optional web search are available as tool actions.
- Runs can be launched via CLI with adapter `assistant`.

## Public interfaces and contracts

### Tools (`tools/`)

- `register_infrastructure_tools(registry, config)`
- `FileReadTool`
- `FileWriteTool` (structured modes: `overwrite`, `append`, `replace_text`)
- `BashExecTool` (allowlist + timeout + stdout/stderr capture)
- `WebSearchTool` (`none`/`tavily`/`serper`, with `none` as explicit no-op)
- `ThinkTool`
- `DecomposeTool`

### Assistant adapter (`adapters/assistant`)

- `AssistantAdapter`
  - `create_workspace`
  - `create_objective`
  - `register_tools`
  - `define_state_machine`
  - `initial_markers`
  - `evaluate_run`
- `LocalWorkspace`
  - sandboxed path resolution
  - read/write/replace primitives
  - target listing

### CLI (`main.py`)

Supported arguments:
- `--adapter assistant`
- `--objective "..."`
- `--workspace <path>`
- `--config <path>`
- `--max-ticks <int>`
- `--agents <int>`
- `--seed <int>`

Output:
- JSON run summary with stop reason, tokens/cost counters, marker counts, and evaluation.

## Guardrails and constraints

- Config validation now requires `tools` section and validates:
  - sandbox root
  - command allowlist
  - timeout and file-size bounds
  - search provider and max results
- Workspace operations are constrained to `tools.sandbox_root`.
- Bash tool only executes allowlisted commands.
- Marker mutations still flow through `Environment.apply_action_result` and `MarkerStore` transactions.
- Append-only audit semantics are preserved.

## Known limits / not implemented yet

- TravelPlanner adapter not implemented.
- CodeMigration adapter (V2) not implemented.
- SWE-bench adapter not implemented.
- V2 baseline runners and V2 emergence/Pareto instrumentation not implemented.
- Web search providers require external API keys (`TAVILY_API_KEY`, `SERPER_API_KEY`) when enabled.

## Validation evidence

- `uv run pytest tests/unit -q` -> `81 passed`
- `uv run pytest tests/integration/test_assistant_run.py -q` -> `4 passed`
- `uv run pytest tests/unit tests/integration -q` -> `85 passed`
- `uv run python main.py --adapter assistant --objective "Create a short checklist" --max-ticks 12 --agents 1 --seed 7`
  - Result: successful run, `stop_reason=all_terminal`, JSON summary emitted
