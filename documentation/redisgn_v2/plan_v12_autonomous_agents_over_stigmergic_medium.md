# Plan V12 — Autonomous Agents over a Stigmergic Medium

**Date:** 2026-05-07  
**Status:** canonical V12 direction; V12.1 foundation and V12.2 native LLM
tool-call provider delivered  
**Position:** V10 remains the verifier/replay substrate; V11/B6 is archived as a historical deterministic-operator baseline; V12 restores the scientific claim that the environment guides autonomous LLM agents rather than solving in their place.

## 0. Executive Summary

V11 correctly introduced causal telemetry, affordances, target-aware context and guarded edit validation, but B6 drifted into a deterministic operator system. That made the benchmark safer, not scientifically stronger: the medium started coding domain repairs instead of making LLM agents more autonomous, better informed and less repetitive.

V12 changes the contract:

```text
medium observes -> medium guides -> LLM chooses tool + params
-> tool executes under guard -> verifier judges
-> feedback updates medium
```

The medium must never create a patch. The scheduler must never apply a domain operator. The only valid patch-producing path is an explicit LLM-selected call to `edit_file_guarded` or `apply_patch`.

## 1. Source Grounding

- **MigrationBench / SD-Feedback**: MigrationBench defines repository-level Java 8 migration toward Java 17/21 with build, test and official evaluation. SD-Feedback iterates on syntactic feedback (invalid patch format, absent snippets, missing files) and semantic feedback (pre/post error changes), which makes it the right S1 baseline rather than a stigmergic method. Source: [arXiv:2505.09569](https://arxiv.org/pdf/2505.09569).
- **ReAct**: V12 follows interleaved reasoning/action: the model sees observations, selects actions, reads tool outputs, and revises its next step. Source: [arXiv:2210.03629](https://arxiv.org/abs/2210.03629).
- **Toolformer**: V12 treats tool selection and parameter selection as model responsibilities. Source: [arXiv:2302.04761](https://arxiv.org/abs/2302.04761).
- **SWE-agent / ACI**: V12 prioritizes a small, well-documented agent-computer interface for reading, searching, editing and testing repositories. Source: [arXiv:2405.15793](https://arxiv.org/abs/2405.15793).
- **Anthropic agent engineering guidance**: V12 adopts the distinction between workflows and agents: workflows follow fixed code paths; agents dynamically direct their own tool usage. V12 also follows the recommendations for simple design, transparency, sandboxing and careful tool documentation. Source: [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents).
- **OpenAI tool calling / tracing / trace grading**: V12 requires strict tool-call schemas, complete trace capture and trace-level evaluation for decisions and failures. Sources: [Function calling](https://platform.openai.com/docs/guides/function-calling), [Tracing](https://openai.github.io/openai-agents-js/guides/tracing/), [Trace grading](https://developers.openai.com/api/docs/guides/trace-grading).
- **Self-Debugging / Self-Refine**: V12 keeps external verifier feedback in the loop and records whether iterative correction improves or decays. Sources: [Self-Debugging](https://arxiv.org/abs/2304.05128), [Self-Refine](https://arxiv.org/abs/2303.17651).

## 2. Scientific Contract

V12 is valid only if these invariants hold:

- medium guides, never patches;
- scheduler recommends, never applies;
- LLM chooses tool and parameters;
- tools execute guarded operations only;
- verifier is sovereign;
- S2 and V12 expose identical tools and budgets;
- any V12 gain over S2 is attributable to the stigmergic local view, not a richer tool set.

Hard gates:

```text
medium_created_patch_count == 0
suggest_tool_applied_patch_count == 0
same_tool_registry(S2, V12) == true
```

## 3. Architecture

### 3.1 Core namespace

V12 lives in `core_v12/` and consumes stable V10/V11 primitives where useful:

- `MigrationContext` from `adapters_v10/migrationbench/context.py`;
- `WorkspaceHandle`, `FeedbackDigest`, `ValidationResult` from `core_v10/contracts.py`;
- `JsonlEventLog` from `core_v10/event_log.py`;
- `validate_edit_set_against_workspace()` from `core_v10/operators/guarded_edit_set.py`.

V12 does not use B6 typed Maven operators as an active repair mechanism.

### 3.2 Tools

`core_v12/tools/` defines:

- `ToolCall`: strict LLM-selected tool invocation;
- `ToolSpec`: public tool description shown to the agent;
- `ToolResult`: deterministic execution envelope;
- `ToolProposal`: structured proposal that cannot apply a patch;
- `ToolRegistry`: identical S2/V12 tool registry;
- `ToolExecutor`: controlled execution with failures converted to traceable results.
- `native_schema.py`: provider-facing OpenAI-compatible native function schemas
  for every V12 tool.

Default tools:

- inspect/read: `read_file`, `search_repo`, `inspect_pom`;
- edit: `edit_file_guarded`, `apply_patch`;
- verify: `run_maven`, `run_tests`, `run_official_eval`;
- proposal-only: `suggest_maven_compiler_config`, `suggest_lombok_upgrade`, `suggest_surefire_upgrade`, `suggest_javafx_dependencies`, `suggest_base64_rewrite`.

### 3.3 Medium local view

`AgentLocalView` contains only guidance:

- objective;
- migration_context;
- current_best;
- recent_failures;
- hot_files;
- tool_registry: the complete non-forbidden domain-compatible toolbox;
- tool_annotations: per-tool support, inhibition, risk, recommendation, reason,
  evidence and recent outcomes;
- forbidden_tools: tools that are technically impossible or unsafe to call;
- supported_tools and inhibited_tools are legacy projections only, not filters;
- supported_actions;
- anti_actions;
- relevant_pheromones;
- candidate_history.

It must not contain a ready-to-apply patch or deterministic operator output.
It must not hide merely inhibited tools. Inhibited means discouraged but still
callable with rationale; forbidden means non-callable.

### 3.4 Agent loop

`AgentLoop` implements:

```text
local_view -> LLM ToolCall JSON -> ToolExecutor
-> EventLog -> verifier feedback -> medium update
```

The loop records:

- `agent.local_view.created`;
- `pheromone.read`;
- `agent.tool_call.requested`;
- `agent.tool_call.parse_failed`;
- `tool.executed`;
- `tool.proposal.returned`;
- `candidate.created_by_agent`;
- `verifier.feedback`;
- `medium.updated`.

### 3.5 Native LLM tool-call provider

V12.2 connects MigrationBench to a live `ToolChooser` through native
OpenAI-compatible Chat Completions tool calls, compatible with DeepSeek's strict
tool-call beta.

Provider contract:

- expose every V12 tool as its own native function, never as a generic
  `call_tool`;
- send the whole non-forbidden toolbox to the provider, never a medium-derived
  shortlist;
- include required `rationale` in every function schema;
- use `strict:true`, `additionalProperties:false`, and all schema fields in
  `required`;
- avoid DeepSeek strict-incompatible constraints such as `minLength`,
  `maxLength`, `minItems`, and `maxItems`;
- parse exactly one `message.tool_calls[0]` into `ToolCall`;
- reject zero calls, multiple calls, unknown tools, invalid JSON arguments, or
  locally schema-invalid arguments;
- retry only provider/schema failures, not rejected or failed tool executions;
- never fall back to V10/V11 deterministic providers or free edit-set patches.

Trace contract:

- write `llm_traces/calls.jsonl` and per-instance JSONL traces;
- record prompts, local view, native tool schemas, schema hash, raw message, raw
  tool calls, parsed call, parse status/errors, retry index, provider parameter
  fallback, duration, finish reason and usage;
- redact API keys, bearer tokens, authorization headers, passwords and generic
  `*_key` secrets while keeping raw tool-call arguments available for audit.

## 4. Experimental Arms

V12 compares:

| Arm | Description |
|---|---|
| `S1_sd_feedback_like` | LLM patch libre + verifier feedback; no medium; SD-Feedback-like control. |
| `S2_tool_feedback_agent` | LLM receives feedback and the V12 tool registry; no stigmergic local view. |
| `V12_stigmergic_tool_agent` | Same LLM, same tools, same budgets, plus `AgentLocalView`. |
| `B6_operator_search_deterministic` | Archived historical baseline; not an active V12 direction. |

Primary attribution comparison:

```text
V12_stigmergic_tool_agent - S2_tool_feedback_agent
```

Secondary comparison:

```text
S2_tool_feedback_agent - S1_sd_feedback_like
```

## 5. Metrics

Report separately:

- strict success: `strict_success`;
- search quality: `best_observed_funnel`;
- tool behavior: `tool_calls`, `tool_success_rate`, `harmful_tool_calls`;
- LLM cost/usage: `repair_llm_calls`, `total_tokens`;
- stigmergic effect: `medium_pheromone_reads`, `useful_divergence`;
- recommendation effect: `tool_recommendation_follow_rate`,
  `tool_recommendation_override_rate`, `inhibited_tool_usage_rate`,
  `successful_override_rate`, `harmful_override_rate`,
  `forbidden_tool_attempt_count`,
  `strongly_supported_tool_ignored_count`;
- safety gates: `medium_created_patch_count`, `suggest_tool_applied_patch_count`.

No partial result may be reported as strict benchmark success.

## 6. Minimal Campaign

Targeted subset:

- `camphul__trampoline`;
- `jodaorg__joda__beans`;
- `blueobelisk__chemicaltagger`;
- `aingezzz__easy__crypto`;
- `artur__a__vaadin__helper`.

Expected outputs:

- `comparison.json`;
- `v12_readiness_report.json`;
- `audits/tool_trace_calls.csv`;
- `audits/pairwise_best_observed.csv`;
- `audits/medium_effect_attribution.csv`.

Docker remains mandatory for real MigrationBench campaigns.

## 7. Implementation Phases

### Phase V12.1 — Agent-computer interface foundation

Delivered by the first V12 increment:

- `core_v12/tools/{schema,registry,executor}.py`;
- `core_v12/medium/local_view.py`;
- `core_v12/agent_loop.py`;
- V12 unit tests for schema, guarded tool execution, proposal-only tools, local view, EventLog trace replay and S2/V12 tool parity.

### Phase V12.2 — LLM provider integration

Delivered:

- add `core_v12/tools/native_schema.py`;
- add `scripts/bench/providers_v12_llm.py`;
- use native OpenAI-compatible Chat Completions `tools=[...]`, with DeepSeek
  strict beta base URL when no explicit base URL is configured;
- adapt provider tracing style to V12 `ToolCall`;
- record full prompts, tool specs, raw model response, parsed call, parse errors and usage;
- redact secrets in traces;
- retry only schema failures, not failed domain decisions.

### Phase V12.3 — MigrationBench harness

Delivered:

- add `scripts/v12/run_v12_agentic_comparison.py` with S1/S2/V12 arms;
- preserve the same subset denominator, max-step budget, model config and tool
  registry for S2 and V12;
- thread `instance` and `observation` into `V12NativeToolClient.choose_tool()`
  so traces are instance-named and observation-aware;
- create isolated candidate branches only after the LLM explicitly chooses
  `edit_file_guarded` or `apply_patch`;
- compute V12 metrics from EventLog with `scripts/v12/audit_v12_campaign.py`;
- write `comparison.json`, `v12_readiness_report.json`,
  `audits/best_observed_funnel.csv`,
  `audits/pairwise_best_observed.csv`, `audits/tool_trace_calls.csv` and
  `audits/medium_effect_attribution.csv`.

### Phase V12.4 — Stigmergic SD-Feedback Agent

V12.4 supersedes the "LLM tool-calling for everything" direction as the active
scientific target. It keeps the verifier-gated SD-Feedback loop as the source
of truth and uses the medium as a compact feedback amplifier.

Corrected loop:

```text
1. Harness gives objective, current state and verifier feedback.
2. LLM may call read-only perception tools.
3. LLM emits an explicit propose_patch payload.
4. Harness validates the patch with guarded apply checks.
5. Harness runs the MigrationBench verifier automatically.
6. If the patch is invalid, no-progress, or regressive: feedback + revert.
7. If the patch improves the funnel: accept/commit as current state.
8. Medium updates supports, inhibitions, hot files, active hypotheses and
   repeated-attempt warnings.
9. Next iteration receives raw feedback plus, only in V12, a compact
   stigmergic feedback block.
```

The key correction is:

```text
read-only tools + explicit LLM patch proposal channel
```

Read-only tools improve perception. They do not repair. The patch proposal is
the autonomous LLM action, not a deterministic Python operator.

V12.4 arm design:

| Arm | Description |
|---|---|
| `S1_sd_feedback_exact` | SD-Feedback loop: feedback + patch proposal; no interactive read-only tools; no medium. |
| `S2_sd_feedback_readonly_tools` | Same loop plus read-only perception tools; no medium. |
| `V12_stigmergic_sd_feedback` | Same model, same budget, same tools and same patch proposal channel as S2, plus compact stigmergic feedback. |

The primary attribution comparison becomes:

```text
V12_stigmergic_sd_feedback - S2_sd_feedback_readonly_tools
```

The secondary comparison is:

```text
S2_sd_feedback_readonly_tools - S1_sd_feedback_exact
```

Read-only tool surface:

- `read_file`;
- `search_repo`;
- `inspect_pom`;
- `read_build_log`;
- `parse_maven_errors`;
- `inspect_effective_pom`;
- `dependency_tree`;
- `lookup_dependency_version`.

Patch channel:

- `PatchProposal(action="propose_patch", patch=...)` for unified diffs;
- `PatchProposal(action="propose_patch", edit_set=...)` for strict edit sets;
- exactly one patch shape is allowed;
- unified diffs must pass `git apply --check`;
- edit sets must pass `validate_edit_set_against_workspace()` against the real
  parent workspace;
- invalid proposals become syntactic SD-Feedback, not MigrationBench validation
  attempts.

Accept/revert policy:

```text
strict_success      = 100
official_success    = 80
test_success        = 60
class_version_ok    = 50
compile_success     = 40
patch_applies       = 20
patch_delivered     = 10
none                = 0
replacement_error   = -20
```

```text
if new_score > current_score:
    accept as current state
elif new_score == current_score and failure_family changed:
    optional exploratory accept
else:
    revert and add inhibition
```

The best-observed candidate must be retained even when the current branch is
reverted.

Stigmergic feedback block:

```json
{
  "failed_attempts_summary": [],
  "inhibitions": [],
  "supports": [],
  "hot_files": [],
  "active_hypotheses": [],
  "best_observed": {},
  "anti_actions": [],
  "candidate_history": [],
  "medium_created_patch_count": 0
}
```

Compaction limits:

- top 5 supports;
- top 5 inhibitions;
- top 5 hot files;
- top 3 active hypotheses;
- at most 10 failed-attempt summaries.

V12.4 metrics:

- strict_success;
- best_observed_funnel;
- accepted_patch_count;
- reverted_patch_count;
- syntax_feedback_count;
- semantic_feedback_count;
- repeated_action_rate;
- medium_inhibition_follow_rate;
- medium_support_follow_rate;
- useful_medium_hint_rate;
- harmful_medium_hint_rate;
- tokens_per_attempt;
- verifier_runs.

## 8. Current Limits

- V12.1/V12.2/V12.3 are implemented and unit-tested; V12.3 has targeted
  evidence but is not the final scientific design because it still treats tool
  calls as the main action interface.
- V12.4 has core primitives and unit tests, but the Docker campaign runner for
  `S1_sd_feedback_exact` vs `S2_sd_feedback_readonly_tools` vs
  `V12_stigmergic_sd_feedback` remains to be implemented before any new
  MigrationBench claim.
- The archived B6 operators may be kept for historical comparison and offline diagnostics, but must not be called by the V12 active agent loop.
- Proposal tools can include suggested edit shapes, but they cannot mutate a workspace and cannot create a candidate.
