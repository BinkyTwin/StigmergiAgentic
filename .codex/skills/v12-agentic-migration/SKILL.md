---
name: v12-agentic-migration
description: Use when implementing or auditing V12 autonomous MigrationBench agents over a stigmergic medium; enforces that the medium guides but never creates patches, that S2 and V12 share identical tools, and that LLM tool decisions are fully traced.
---

# V12 Agentic Migration

## Non-Negotiables

- The medium guides, never patches.
- The scheduler recommends, never applies.
- The agent sees the complete non-forbidden tool registry for the domain.
- Medium support/inhibition/risk are annotations, not tool visibility filters.
- Inhibited tools remain callable with rationale; forbidden tools are rejected
  only for technical impossibility or safety.
- The LLM chooses the tool and parameters.
- In V12.4, read-only tools improve perception and patch creation happens
  through the explicit LLM `propose_patch` channel, not through repair tools.
- For V12.2/V12.3 diagnostic code, only `edit_file_guarded` and `apply_patch`
  may mutate a workspace.
- `suggest_*` tools return `ToolProposal` only.
- S2 and V12 must expose identical tools, budgets and model settings.
- The verifier is sovereign; partial funnel progress is not strict success.

## Implementation Checklist

1. Use `core_v12/` for new V12 code.
2. Reuse V10 primitives for EventLog, WorkspaceHandle, FeedbackDigest and MigrationContext.
3. Do not call V11/B6 typed operators from the active V12 loop.
4. For V12.4, validate LLM patch proposals with `PatchProposal` and
   `guard_patch_proposal`; verifier execution is automatic after a valid patch.
5. Validate V12.2/V12.3 LLM tool calls with `ToolCall`.
6. Capture full local traces and redact keys, tokens, passwords and authorization values.
7. Add or update tests in `tests/unit/v12/` before running any campaign.

## Required Validation

```bash
uv run pytest tests/unit/v12 -q
```

For V12.4 SD-Feedback core work:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest tests/unit/v12/test_v12_sd_feedback.py -q --confcutdir=tests/unit/v12
```

Before any MigrationBench campaign, confirm:

- `medium_created_patch_count == 0`
- `suggest_tool_applied_patch_count == 0`
- `assert_same_tools_available_s2_and_v12()` passes

## Campaign Discipline

Run targeted subset before any main_30:

```text
fixtures/migrationbench/subsets/targeted_v12_agentic_5.jsonl
```

V12.3 diagnostic runner compares:

```text
S1_sd_feedback_like
S2_tool_feedback_agent
V12_stigmergic_tool_agent
```

V12.4 active design must compare:

```text
S1_sd_feedback_exact
S2_sd_feedback_readonly_tools
V12_stigmergic_sd_feedback
```

In V12.4, the harness runs verifier automatically after a valid patch proposal;
do not ask the LLM to spend steps choosing `run_maven` or `run_tests`.

Treat `B6_operator_search_deterministic` as archived historical baseline only.

Current V12.3 runner:

```bash
uv run python -m scripts.v12.run_v12_agentic_comparison \
  --subset fixtures/migrationbench/subsets/targeted_v12_agentic_5.jsonl \
  --out-dir campaign_results/v12/migrationbench_targeted_agentic \
  --max-steps 6 \
  --extras '{"official_eval":true,"use_llm_providers":true}' \
  --clean
```

After the runner, inspect `v12_readiness_report.json` plus
`audits/tool_trace_calls.csv` and `audits/medium_effect_attribution.csv` before
changing prompts, tools, or budgets.
