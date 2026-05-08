# ADR 023 — V12.4 Stigmergic SD-Feedback Agent

**Date:** 2026-05-08  
**Status:** Accepted  
**Supersedes directionally:** V12.3 as the active experimental design, while
preserving V12.3 traces and tests as diagnostic infrastructure.

## Context

V12.2/V12.3 restored agent autonomy compared with V11/B6, but still leaned too
far into "LLM tool-calling for everything": the agent spent budget deciding
whether to inspect, edit, run Maven, or run tests. MigrationBench already has a
strong verifier-gated SD-Feedback framing: the system should automatically
guard/apply/verify each patch attempt and convert invalid/no-progress attempts
into feedback.

The project needs a cleaner scientific attribution:

```text
same model + same verifier + same budget + same perception tools
difference = raw feedback vs feedback augmented by stigmergic medium
```

## Decision

V12.4 becomes the active design:

- SD-Feedback is the loop of truth.
- The agent may use read-only perception tools.
- The agent proposes patches through an explicit `propose_patch` channel.
- The harness validates patches, runs the verifier automatically, and applies
  accept/revert policy based on best-observed funnel progress.
- The medium augments future feedback with compact supports, inhibitions, hot
  files, active hypotheses, repeated-attempt warnings and best-observed state.
- The medium does not create patches, select patch parameters, run domain
  operators, or hide merely inhibited options.

The experimental arms are:

- `S1_sd_feedback_exact`;
- `S2_sd_feedback_readonly_tools`;
- `V12_stigmergic_sd_feedback`.

The primary scientific comparison is:

```text
V12_stigmergic_sd_feedback - S2_sd_feedback_readonly_tools
```

## Consequences

Positive:

- SD-Feedback becomes a strong baseline instead of a weak local approximation.
- The verifier remains sovereign and is no longer a tool the LLM wastes steps
  choosing.
- Read-only tools improve perception without becoming hidden repair scripts.
- Medium impact can be attributed to feedback augmentation rather than extra
  repair capacity.

Negative:

- The V12.3 runner is no longer sufficient for final claims.
- A new Docker runner is needed before any V12.4 benchmark campaign.
- Patch proposal parsing/guarding becomes a first-class interface to test and
  trace.

## Validation

Initial V12.4 core validation:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /tmp/stig-v12-env/bin/python -m pytest tests/unit/v12 -q --confcutdir=tests/unit/v12
# 53 passed
```

The focused V12.4 tests validate patch-channel guarding, invalid edit rejection,
funnel accept/revert policy, read-only tool registry, V12.4 arm definitions,
compact patch-free medium feedback and verifier-automatic prompt contract.
