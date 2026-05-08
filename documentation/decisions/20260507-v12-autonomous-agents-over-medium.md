# ADR 022 — V12 Autonomous Agents over a Stigmergic Medium

**Date:** 2026-05-07  
**Status:** Accepted  
**Supersedes directionally:** ADR 021 for future work, while preserving V11/B6 as historical evidence.

## Context

V11 introduced the missing causal machinery: signal reads, affordances, worker
activation, decision influence, trajectory divergence, target-aware
MigrationContext and guarded edits. However, B6 evolved into a deterministic
operator arm where Python code increasingly repaired MigrationBench projects
instead of merely guiding LLM agents.

That invalidates the intended scientific claim. A stigmergic environment should
guide, attract, inhibit and inform autonomous agents. It should not encode the
domain solution.

## Decision

Create V12 as a separate `core_v12/` line:

- the medium exposes `AgentLocalView`;
- the LLM chooses tool calls and parameters;
- tools execute controlled read/search/inspect/edit/verify/proposal operations;
- proposal tools never mutate workspaces;
- patches can only be created through explicit agent-selected guarded edit
  tools;
- S2 and V12 share the exact same tool registry, budgets and model settings.

V11/B6 remains an archived baseline named `B6_operator_search_deterministic`.
It is not the active direction for new claims.

## Consequences

Positive:

- V12 restores attribution: any gain over S2 can be tied to the stigmergic local
  view rather than extra domain operators.
- Tool use becomes auditable through strict schemas and EventLog traces.
- The agent-computer interface can be optimized without hiding domain fixes in
  the scheduler.

Negative:

- V12 is slower and more expensive than deterministic operators.
- Tool-call quality becomes model-dependent.
- The first V12 increment needs a new campaign runner before main_30 evidence
  can be collected.

## Non-Negotiables

- medium guides, never patches;
- scheduler recommends, never applies;
- LLM chooses tool and parameters;
- tools execute guarded operations;
- verifier is sovereign;
- S2 and V12 expose identical tools.

## Validation

Initial foundation validation:

```bash
uv run pytest tests/unit/v12 -q
# 13 passed
```

This validates tool schemas, proposal-only tools, guarded editing, local-view
pheromones, target-context enforcement, verifier feedback updates, EventLog
replay and S2/V12 tool parity.
