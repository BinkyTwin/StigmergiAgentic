# Phase 8 V12 — Autonomous Agents over a Stigmergic Medium

**Status:** V12.1 foundation, V12.2 native LLM tool-call provider, and V12.3
targeted S1/S2/V12 campaign runner implemented on
`codex/v11-stigmergic-medium-kernel` after V11/B6 was archived as a historical
baseline.

## Scope

Phase 8 starts V12 as a separate namespace. The goal is to preserve the useful
V10/V11 substrate while removing the B6 scientific drift where deterministic
operators repaired the domain instead of guiding autonomous LLM agents.

## Current Artifact Behavior

V12 now exposes:

- strict tool schemas: `ToolCall`, `ToolSpec`, `ToolResult`, `ToolProposal`;
- a default tool registry shared by S2 and V12;
- controlled execution for read/search/inspect/edit/verify/proposal tools;
- proposal-only `suggest_*` tools that never mutate the workspace;
- `AgentLocalView` and `V12StigmergicMedium`;
- a complete non-forbidden toolbox in each local view, plus per-tool
  annotations instead of medium-side tool hiding;
- OpenAI-compatible native tool-call schemas for every V12 tool;
- a MigrationBench V12.2 LLM provider using native Chat Completions
  `tools=[...]`, compatible with DeepSeek strict beta;
- full redacted V12.2 traces for prompts, schemas, raw tool calls, parsed calls,
  parse errors, finish reason and usage;
- provider calls force native tool use with `tool_choice="required"` and fail
  fast when non-DeepSeek providers omit an explicit model;
- DeepSeek V4 tool-choice calls disable thinking mode because the live API
  rejects `tool_choice="required"` on the reasoner path;
- DeepSeek live calls use direct HTTP with explicit timeout after the
  OpenAI-compatible SDK path hung locally while the equivalent HTTP request
  succeeded;
- `AgentLoop` that logs local views, LLM tool calls, parse failures, tool
  results, proposals,
  agent-created candidates, verifier feedback and medium updates.
- `AgentLoop.context_preparer`, used by the V12.3 runner to create isolated
  candidate branches only after the LLM explicitly chooses a mutating tool.
- `scripts/v12/run_v12_agentic_comparison.py`, the V12.3 runner for
  `S1_sd_feedback_like`, `S2_tool_feedback_agent` and
  `V12_stigmergic_tool_agent`.
- `scripts/v12/audit_v12_campaign.py`, which writes replay-derived
  `best_observed_funnel.csv`, `pairwise_best_observed.csv`,
  `tool_trace_calls.csv`, `medium_effect_attribution.csv` and
  `v12_readiness_report.json`.

## Public Interfaces

- `core_v12.tools.build_default_tool_registry()`
- `core_v12.tools.ToolExecutor`
- `core_v12.medium.V12StigmergicMedium`
- `core_v12.medium.AgentLocalView`
- `core_v12.agent_loop.AgentLoop`
- `core_v12.agent_loop.ToolChoiceError`
- `core_v12.agent_loop.V12_EXPERIMENTAL_ARMS`
- `core_v12.agent_loop.assert_same_tools_available_s2_and_v12()`
- `core_v12.tools.registry_to_native_tools()`
- `core_v12.tools.parse_native_tool_call_message()`
- `core_v12.metrics.summarize_tool_recommendation_metrics()`
- `scripts.bench.providers_v12_llm.V12NativeToolClient`
- `scripts.bench.providers_v12_llm.make_migrationbench_v12_tool_chooser()`
- `scripts.v12.run_v12_agentic_comparison.run_v12_agentic_comparison()`
- `scripts.v12.audit_v12_campaign.audit_v12_campaign()`

## Guardrails

- The medium has no patch-producing method and reports
  `created_patch_count == 0`.
- Only `edit_file_guarded` and `apply_patch` can mutate a workspace.
- `edit_file_guarded` reuses the V11 central guard against the real workspace.
- Every `suggest_*` tool returns a `ToolProposal` and `workspace_mutated=False`.
- S2 and V12 must use identical tool names.
- The medium may annotate support/inhibition/risk, but it must not remove
  merely inhibited tools from the agent-visible toolbox.
- `forbidden_tools` are the only non-callable tools and must be justified by
  technical impossibility or safety.
- Tool traces are redacted for common secret-bearing fields.
- The V12.2 provider never creates `Candidate`, `TypedEditSet` or a patch.
- Native provider parsing accepts exactly one tool call; zero, multiple, unknown
  or schema-invalid tool calls become parse failures.
- The V12.2 provider uses the current repo DeepSeek default
  `deepseek-v4-flash` and never silently routes that model name through another
  provider.
- Schema retries are allowed only before tool execution. A `rejected` or
  `failed` tool result is a domain outcome, not a provider schema error.

## Validation

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/unit/v12 -q
# 44 passed

PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/unit/v12 tests/unit/v11/test_b6_guarded_fallback.py tests/unit/v11/test_operator_guards.py -q
# 77 passed
```

Covered scenarios:

- strict LLM tool-call schema;
- medium does not create patches;
- guarded edit execution rejects absent spans and applies exact spans;
- S2/V12 tool parity;
- stigmergic view adds pheromones and hot files;
- verifier feedback updates the medium;
- agent can choose `edit_file_guarded`;
- agent can inspect POM before patch;
- proposal tools do not mutate workspaces;
- target-dependent proposal tools reject missing migration context instead of
  defaulting to Java 17;
- EventLog replay preserves V12 tool traces;
- local LLM traces redact secrets.
- native schemas are strict-compatible for OpenAI/DeepSeek tool calls;
- native provider parses valid DeepSeek/OpenAI-style tool responses;
- schema failures retry once and emit `agent.tool_call.parse_failed`;
- the provider sends the whole non-forbidden toolbox, not a recommendation
  shortlist;
- recommendation follow/override/forbidden metrics are reconstructible from
  EventLog payloads;
- `parallel_tool_calls=false` is tried, with one traced provider-parameter
  fallback if a provider rejects that parameter;
- `tool_choice="required"` is sent so the provider cannot default to prose when
  tools are present;
- DeepSeek requests include `extra_body={"thinking": {"type": "disabled"}}`;
- live DeepSeek smoke through `V12NativeToolClient` returned one `inspect_pom`
  native tool call with a redacted trace file;
- config parsing rejects ambiguous provider/model defaults and handles string
  booleans consistently;
- full `llm_traces/calls.jsonl` and per-instance JSONL records are emitted.
- V12.3 mutating tools run on isolated agent candidate branches, not on the
  base workspace.
- V12.3 audits reconstruct best-observed funnel and medium-attribution rows
  from EventLogs.
- S2/V12 tool registry equality is checked in the readiness report.
- Docker validation after the V12.3 guidance hardening:

```bash
docker compose -f docker-compose.campaign.yml run --rm --no-deps \
  v12-migrationbench-targeted \
  /opt/venv/bin/python -m pytest \
  tests/unit/v12 \
  tests/unit/v10/migrationbench/test_verifier.py::test_collect_class_versions_reads_class_header_without_javap \
  -q
# 46 passed
```

## Targeted Campaign Evidence

Latest Docker targeted campaign:

```text
campaign_results/v12/migrationbench_targeted_agentic_guided_v2
subset: fixtures/migrationbench/subsets/targeted_v12_agentic_5.jsonl
arms: S1_sd_feedback_like, S2_tool_feedback_agent, V12_stigmergic_tool_agent
official_eval: true
use_llm_providers: true
max_steps: 6
```

Readiness gates are green:

- `medium_created_patch_count == 0`
- `suggest_tool_applied_patch_count == 0`
- S2 and V12 expose the same tool registry
- tool traces are present

Best-observed comparison against S2:

- V12 better: 1 instance (`jodaorg__joda__beans`, `patch_applies -> compile_success`)
- V12 same: 4 instances
- V12 worse: 0 instances

Strict success is still `0/5` for all three arms on this targeted subset.
The current result supports the narrower claim that V12 guidance is now
non-inferior to S2 on best-observed funnel for the targeted subset, while
preserving the scientific non-negotiables.

## Known Limits

- V12.3 has targeted Docker evidence, but it is no longer the final active
  scientific design. It remains diagnostic infrastructure.
- V12.4 reframes the active design as **Stigmergic SD-Feedback Agent**:
  SD-Feedback is the verifier-gated loop, read-only tools improve perception,
  the LLM emits an explicit `propose_patch`, and the harness guards, verifies,
  accepts or reverts.
- V12.4 core primitives are implemented in `core_v12/sd_feedback.py` and
  `build_sd_feedback_readonly_tool_registry()`. Unit tests cover the patch
  channel, invalid edit rejection, accept/revert policy, read-only registry,
  V12.4 arm definitions and compact patch-free medium feedback.
- V12.4 does not yet have the full Docker runner for
  `S1_sd_feedback_exact` vs `S2_sd_feedback_readonly_tools` vs
  `V12_stigmergic_sd_feedback`; do not run or cite a V12 `main_30` until that
  runner and its targeted subset audit exist.
- V11/B6 artifacts remain useful as historical evidence but are no longer the
  active research direction.
