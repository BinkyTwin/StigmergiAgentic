# CLAUDE.md

This file is the repository handoff for Claude agents.
It describes the current source of truth, the active architecture, and the
commands that matter now. Keep it current when the project direction changes.

## Current Project State

StigmergiAgentic is a Master's thesis codebase about verifier-gated,
stigmergic coordination for code migration benchmarks.

The active implementation line is **V12**:

- `core_v12/` is the active V12 autonomous-agent layer.
- `core_v10/` is the active orchestration runtime.
- `adapters_v10/` is the active adapter layer.
- `scripts/bench/`, `scripts/v11/`, and `scripts/v12/` are the active
  benchmark harness/audit surfaces.
- `core/`, `adapters/`, `tools/`, `llm/`, and the old TravelPlanner stack are
  legacy Sprint 9 / V3 code. Treat them as historical unless the user explicitly
  asks for legacy work.

Do not build new features in the legacy `core/` runtime. New framework work
belongs in `core_v12/` first, reusing `core_v10/` and `adapters_v10/` only as
stable verifier, workspace, EventLog and MigrationContext substrate.

## Canonical Documents

Use these first when orienting yourself:

- `documentation/redisgn_v2/plan_v10_from_scratch_rebuild.md` — V10 rebuild plan.
- `documentation/redisgn_v2/plan_v11_stigmergic_medium_kernel.md` — V11 plan.
- `documentation/redisgn_v2/plan_v12_autonomous_agents_over_stigmergic_medium.md` — current V12 plan.
- `documentation/redisgn_v2/phase_07_artifact.md` — current V11 artifact notes.
- `documentation/redisgn_v2/phase_08_artifact.md` — current V12 foundation notes.
- `documentation/decisions/20260503-pivot-v10-from-scratch.md` — V10 pivot ADR.
- `documentation/decisions/20260506-v11-stigmergic-medium-kernel.md` — V11 ADR.
- `documentation/decisions/20260507-v12-autonomous-agents-over-medium.md` — V12 ADR.
- `campaign_results/v11/migrationbench_main30_targetaware_full_llmtraces/audits/`
  — latest V11/B6 historical audit outputs.

## Current V12 Status

V12 is the active research direction after the V11/B6 failure mode was
identified. V11/B6 made the system safer, but drifted toward deterministic
operators that repaired MigrationBench projects in Python. V12 restores the
scientific principle: the medium guides; the LLM agent chooses tools and
parameters; tools execute under guard; the verifier judges; feedback updates
the medium.

Implemented:

- `core_v12/tools/`: strict `ToolCall`, `ToolSpec`, `ToolResult`,
  `ToolProposal`, registry and executor.
- Default V12 tools: read/search/inspect, guarded edit, patch apply, Maven/test
  verification, official-eval hook, and proposal-only `suggest_*` tools.
- `core_v12/tools/native_schema.py`: OpenAI-compatible native tool-call
  schemas for every V12 tool, with `strict:true`, `additionalProperties:false`,
  required `rationale`, and local parse/schema validation.
- `core_v12/medium/local_view.py`: `AgentLocalView` and
  `V12StigmergicMedium`. Local views expose the complete non-forbidden toolbox
  plus per-tool annotations; the medium annotates tools, it does not hide
  inhibited tools.
- `core_v12/agent_loop.py`: local view -> LLM native tool call -> tool
  execution -> EventLog -> verifier feedback -> medium update.
- `core_v12/sd_feedback.py`: V12.4 SD-Feedback primitives: explicit
  `propose_patch` channel, patch guards, best-observed funnel scoring,
  accept/revert policy, compact stigmergic feedback block, and V12.4 arm
  definitions.
- `core_v12/tools/executor.py`: two tool surfaces now exist. The V12.2/V12.3
  default registry still contains guarded mutating tools, while
  `build_sd_feedback_readonly_tool_registry()` exposes the V12.4 perception-only
  toolbox: read/search/inspect, safe build-log reading, Maven-error parsing,
  effective-pom/dependency-tree inspection, and dependency-version lookup.
- `scripts/bench/providers_v12_llm.py`: MigrationBench V12.2 provider using
  native OpenAI-compatible Chat Completions tool calls, compatible with
  DeepSeek strict beta; no deterministic V10/V11 fallback and no patch
  creation by the provider.
- Full V12.2 LLM traces under `llm_traces/` with prompts, tool schemas, raw
  tool calls, parsed call, parse errors, usage, and redacted secrets.
- `scripts/v12/run_v12_agentic_comparison.py`: V12.3 targeted comparison
  runner for `S1_sd_feedback_like`, `S2_tool_feedback_agent`, and
  `V12_stigmergic_tool_agent`.
- `scripts/v12/audit_v12_campaign.py`: V12.3 audit writer for
  `best_observed_funnel.csv`, `pairwise_best_observed.csv`,
  `tool_trace_calls.csv`, `medium_effect_attribution.csv`, and
  `v12_readiness_report.json`.
- `core_v12/metrics.py`: recommendation follow/override, inhibited usage,
  forbidden-attempt and harmful/successful override metrics.
- V12 experimental arm definitions:
  - V12.3 archived/diagnostic arms: `S1_sd_feedback_like`,
    `S2_tool_feedback_agent`, `V12_stigmergic_tool_agent`.
  - V12.4 active design arms: `S1_sd_feedback_exact`,
    `S2_sd_feedback_readonly_tools`, `V12_stigmergic_sd_feedback`.
- Repo-local skill `.codex/skills/v12-agentic-migration/SKILL.md`.
- Targeted subset `fixtures/migrationbench/subsets/targeted_v12_agentic_5.jsonl`.

Latest targeted evidence:

- Root: `campaign_results/v12/migrationbench_targeted_sdfeedback_v12_4`
- Protocol: targeted 5, `official_eval=true`, `use_llm_providers=true`,
  `max_iterations=6`, `inspection_steps=1`, V12.4 SD-Feedback arms:
  `S1_sd_feedback_exact`, `S2_sd_feedback_readonly_tools`,
  `V12_stigmergic_sd_feedback`.
- Readiness gates green: medium-created patches = 0, suggest-applied patches =
  0, S2/V12 tool registry parity = true, tool traces present.
- Best-observed V12 vs S2: same on 5 instances, worse on 0, better on 0.
- V12 and S2 both improve S1 on `camphul__trampoline`
  (`patch_applies -> class_version_ok`), so the read-only inspection loop helps
  there; the stigmergic context does not yet outperform S2 on this subset.
- Strict success remains 0/5 for S1, S2 and V12. This is a targeted
  traceability/non-regression result, not a benchmark success claim.

Latest V12.4 code evidence:

- V12.4 re-centers SD-Feedback: LLM proposes a patch, the harness guards it,
  the verifier runs automatically, accept/revert is decided by funnel progress,
  and the medium only augments future feedback.
- Unit tests validate the patch channel, invalid edit rejection,
  accept/revert policy, read-only tool registry, V12.4 arm definitions,
  compact patch-free stigmergic feedback block, and verifier-automatic prompt
  contract.

Still not ready:

- Do not run or interpret V12 `main_30`.
- V12.4 has a targeted Docker runner and green targeted readiness gates, but no
  evidence of superiority over S2 yet.
- Before `main_30`, improve the medium so it produces useful, compact
  recommendations for `jodaorg__joda__beans`/bundle-plugin style failures and
  SD parser-format failures, then rerun targeted evidence.
- Keep using read-only tools plus the explicit LLM SD-Feedback patch channel.
  Do not reuse the V12.3 "LLM tool-calling for everything" runner as the final
  V12.4 design.

Archived V11 result:

- Root:
  `campaign_results/v11/migrationbench_main30_targetaware_full_llmtraces`
- Protocol:
  B2/B5/B6, `official_eval=true`, `use_llm_providers=true`,
  `b6_fallback_policy=guarded_only`.
- Readiness:
  `ready_for_main30_launch=true`, full denominator, replay parity true.
- Strict success:
  B2 = 1/30, B5 = 1/30, B6 = 1/30.
- Safety:
  B6 `replacement_count_too_low_total=0`, `validation_error_total=0`.
- Operators:
  B6 `operator_invoked_total=26`, `operator_applied_total=26`.
- Best-observed:
  B6 vs B5 = 28 same, 1 better, 1 worse; not superior overall.

Interpretation:

> B6 is a historical deterministic-operator baseline. It eliminates unsafe
> replacement errors, but it is not the active scientific direction because the
> medium began coding solutions instead of guiding autonomous agents.

## Active Project Structure

```text
core_v12/
  agent_loop.py             # V12 autonomous LLM tool loop and arm definitions
  metrics.py                # Tool recommendation follow/override metrics
  sd_feedback.py            # V12.4 patch channel, funnel policy, feedback block
  tools/
    schema.py               # ToolCall, ToolSpec, ToolResult, ToolProposal
    registry.py             # Shared S2/V12 ToolRegistry
    executor.py             # Controlled tools; includes V12.4 read-only registry
    native_schema.py        # OpenAI-compatible native function schemas/parser
  medium/
    local_view.py           # AgentLocalView and V12StigmergicMedium

scripts/bench/
  providers_v12_llm.py      # V12.2 native tool-call provider/tracing

scripts/v12/
  run_v12_agentic_comparison.py  # V12.3 S1/S2/V12 targeted runner
  audit_v12_campaign.py          # V12.3 audits/readiness report

core_v10/
  contracts.py              # Domain contracts: Candidate, Workspace, Validation, Score
  event_log.py              # Append-only JSONL EventLog and replay records
  hypothesis_graph.py       # Candidate lineage and workspace graph
  verifier.py               # Apply -> validate -> diagnose -> score loop
  strategy_runner.py        # A1/A2/A3/A4 and V11 B2/B5/B6 strategies
  signals.py                # V10 signal records/store
  signal_policy.py          # Signal policy for verifier feedback
  blackboard.py             # Typed replay blackboard projection
  replay.py                 # Replay helpers
  operators/
    guarded_edit_set.py     # Central guard for LLM edit sets vs real workspace
    text_operator.py        # ExactReplaceText and text operator helpers
  stigmergy/
    events.py               # V11 event taxonomy constants
    records.py              # Affordance, SignalRead, DecisionInfluence, etc.
    affordances.py          # Feedback -> action affordance taxonomy
    medium.py               # StigmergicMediumKernel
    scheduler.py            # Worker registry and activation scoring

adapters_v10/
  base.py                   # Adapter interface
  toy.py                    # Toy adapter for fast tests
  migrationbench/
    adapter.py              # DomainAdapterV10 implementation
    workspace.py            # Isolated base/branch workspaces
    verifier.py             # Maven + official MigrationBench verifier
    schemas.py              # MigrationBench instance schemas
    context.py              # MigrationContext source/target/build metadata
    compatibility.py        # JavaCompatibilityProfile table
    maven.py                # Maven inspection/helpers
    operators/
      maven.py              # Target-aware typed Maven operators

scripts/
  bench/
    harness.py              # Unified benchmark harness
    compare_strategies.py   # V10/V11 ladders and comparison.json
    providers.py            # Deterministic providers
    providers_llm.py        # DeepSeek/OpenAI-compatible LLM providers + traces
    telemetry.py            # Summary reconstruction from EventLog
    artifacts.py            # Artifact export helpers
    docker.py               # Docker helper utilities
  v11/
    run_v11_smoke.py
    run_v11_migrationbench_campaign.py
    audit_v11_campaign.py
  v12/
    run_v12_agentic_comparison.py
    audit_v12_campaign.py

tests/
  unit/v10/
  unit/v11/
  integration/v10/
  integration/v11/

fixtures/migrationbench/subsets/
  smoke_5.jsonl
  targeted_v12_agentic_5.jsonl
  main_30.jsonl

campaign_results/v11/
  migrationbench_main30_targetaware_full_llmtraces/
    comparison.json
    v11_readiness_report.json
    audits/

campaign_results/v12/
  # expected V12.3 output root, created by the runner:
  # migrationbench_targeted_agentic/
  #   comparison.json
  #   v12_readiness_report.json
  #   audits/
  #   S1_sd_feedback_like/
  #   S2_tool_feedback_agent/
  #   V12_stigmergic_tool_agent/
```

## Core Invariants

- V12 medium guides, never patches.
- V12 scheduler/local view recommends, never applies.
- The V12 agent sees every non-forbidden compatible tool; support/inhibition
  are annotations, not visibility filters.
- Inhibited tools remain callable with rationale. Forbidden tools are rejected
  because they are technically impossible or unsafe.
- The LLM chooses tool and parameters.
- Tools execute guarded operations only.
- In V12.4, the agent may use read-only tools for perception, then proposes a
  patch through an explicit `propose_patch` / `PatchProposal` channel.
- The V12.4 harness, not the LLM, runs validation automatically after a patch
  proposal.
- V12.4 accept/revert is based on best-observed funnel score: accept progress,
  optionally accept equal-score changed failure families as exploratory, revert
  no-progress repeats.
- The verifier is sovereign.
- S2 and V12 must expose identical tools and budgets.
- `suggest_*` tools must return proposals only and must not mutate workspaces.
- EventLog is the source of truth for telemetry. Summaries must be replayable.
- `live_summary == replay_summary_from_dir(out_dir)` must hold for benchmark arms.
- `strict_success=True` requires the full verifier/finalization contract.
- Do not count partial funnel progress as strict benchmark success.
- B6 is archived as `B6_operator_search_deterministic`; do not use it as the
  active V12 mechanism.
- No candidate with free-form LLM `replace_text` may reach adapter validation
  unless `guarded_edit_set` validated it against the real parent branch workspace.
- Operators must be target-aware through `MigrationContext`; do not create
  Java-17-specific operator names or silent Java-17 defaults.
- MigrationBench target data must fail fast when missing in benchmark mode.
- Docker is mandatory for real benchmark campaigns.

## MigrationContext Rules

MigrationBench migrations are not hardcoded Java 17 migrations. Every adapter
observation should carry a `MigrationContext` with at least:

- `source_language`
- `source_version`
- `target_language`
- `target_version`
- `target_class_major`
- `build_system`
- `migration_mode`
- `dependency_policy`
- `framework_hints`

Use `adapters_v10/migrationbench/compatibility.py` for Java-specific thresholds:

- compiler plugin minimum
- surefire minimum
- Lombok minimum
- JavaFX version
- JAXB namespace default

## Commands

### Environment

```bash
uv python install 3.11
uv venv --python 3.11 .venv
uv pip install -r requirements.txt
```

### Focused Validation

Use focused tests first; full historical suites are often unnecessary.

```bash
uv run pytest tests/unit/v12 -q
uv run pytest tests/unit/v11 -q
uv run pytest tests/integration/v11 -q
uv run pytest tests/unit/v10/bench -q
uv run pytest tests/unit/v10/migrationbench -q
```

For V12 foundation work:

```bash
uv run pytest tests/unit/v12 -q
```

For V12.2 native LLM tool-call provider work:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/unit/v12 -q
PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/unit/v12 tests/unit/v11/test_b6_guarded_fallback.py tests/unit/v11/test_operator_guards.py -q
```

For V12.3 targeted comparison work:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/unit/v12 -q
PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/unit/v12 tests/unit/v11/test_b6_guarded_fallback.py tests/unit/v11/test_operator_guards.py -q

uv run python -m scripts.v12.run_v12_agentic_comparison \
  --subset fixtures/migrationbench/subsets/targeted_v12_agentic_5.jsonl \
  --out-dir campaign_results/v12/migrationbench_targeted_agentic \
  --max-steps 6 \
  --extras '{"official_eval":true,"use_llm_providers":true}' \
  --clean

uv run python -m scripts.v12.audit_v12_campaign \
  --campaign-root campaign_results/v12/migrationbench_targeted_agentic
```

For V12.4 SD-Feedback core work:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest tests/unit/v12/test_v12_sd_feedback.py -q --confcutdir=tests/unit/v12
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest tests/unit/v12 -q --confcutdir=tests/unit/v12
```

For the V12.4 targeted SD-Feedback campaign, use Docker and keep `--clean`
semantics:

```bash
docker compose -f docker-compose.campaign.yml build --no-cache v12-sdfeedback-targeted
docker compose -f docker-compose.campaign.yml up v12-sdfeedback-targeted

PYTHONPATH=. uv run python -m scripts.v12.audit_v12_campaign \
  --campaign-root campaign_results/v12/migrationbench_targeted_sdfeedback_v12_4
```

If the repo-local `.venv` is corrupted, a clean temporary environment is
acceptable for unit validation:

```bash
uv venv /tmp/stig-v12-env --python 3.12
uv pip install --python /tmp/stig-v12-env/bin/python pytest pydantic pydantic-core pyyaml gitpython parameterized javalang python-dotenv openai
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /tmp/stig-v12-env/bin/python -m pytest tests/unit/v12 -q --confcutdir=tests/unit/v12
```

For V11 campaign audit tooling:

```bash
uv run pytest tests/unit/v11/test_v11_campaign_audit.py -q
```

### V11 Smoke

```bash
uv run python -m scripts.v11.run_v11_smoke \
  --out-dir campaign_results/v11/smoke_local
```

### V11 MigrationBench Main30

Use Docker for real benchmark runs.

```bash
DEEPSEEK_API_KEY=$(grep DEEPSEEK_API_KEY .env | cut -d= -f2) \
V11_OUT_DIR=campaign_results/v11/migrationbench_main30_targetaware_full_llmtraces \
V11_WORKSPACE_ROOT=workspaces/migrationbench_v11_targetaware_full_llmtraces \
V11_MIGRATION_SUBSET=fixtures/migrationbench/subsets/main_30.jsonl \
V11_OFFICIAL_EVAL=true \
V11_USE_LLM_PROVIDERS=true \
V11_B6_FALLBACK_POLICY=guarded_only \
docker compose -f docker-compose.campaign.yml up --build v11-migrationbench-main30
```

The service writes:

- `<out_dir>/B2_branching_repair/summary.json`
- `<out_dir>/B5_stigmergic_scheduler/summary.json`
- `<out_dir>/B6_operator_search/summary.json`
- `<out_dir>/comparison.json`
- `<out_dir>/v11_readiness_report.json`
- `<out_dir>/<arm>/llm_traces/calls.jsonl`

### V11 Campaign Audit

Run this after a campaign completes:

```bash
uv run python -m scripts.v11.audit_v11_campaign \
  --campaign-root campaign_results/v11/migrationbench_main30_targetaware_full_llmtraces
```

The audit writes:

- `audits/best_observed_funnel.csv`
- `audits/pairwise_best_observed.csv`
- `audits/operator_applied_by_family.csv`
- `audits/operator_unavailable_by_failure_family.csv`
- `audits/operator_helped_harmed_by_instance.csv`
- `audits/llm_trace_calls.csv`
- JSON equivalents and `audits/audit_summary.md`.

## How To Interpret Campaign Results

Report these separately:

- Strict benchmark success: only `strict_success_count`.
- Mechanism safety: `replacement_count_too_low_total`, `validation_error_total`.
- Causal activation: `signal_read_total`, `decision_influenced_total`,
  `trajectory_divergence_total`.
- Operator surface: `operator_invoked_total`, `operator_applied_total`,
  `operator_unavailable`.
- Search quality: best-observed funnel and pairwise deltas from audits.
- LLM behavior: `llm_traces` calls, parse errors, duplicate drops, empty/invalid drops.

Do not claim that B6 is better than B5 unless pairwise best-observed or strict
success supports it. The current evidence says B6 is safer, not stronger.

## Known Current Follow-Ups

Prioritize these for V12:

1. Run the V12.3 targeted subset and audit `v12_readiness_report.json`.
2. Inspect `llm_traces/` and `audits/tool_trace_calls.csv` before changing
   agent prompts or tools.
3. Only consider V12 `main_30` after targeted readiness gates are clean.
4. Keep S2 and V12 on identical tools, budgets, models, instances and verifier
   contracts.
5. Keep B6 operators out of the active V12 agent loop.

## Code Style

- Python 3.11+.
- Type hints on public functions and methods.
- Keep edits scoped; prefer existing local abstractions.
- Use structured APIs/parsers where practical.
- Comments and code docs should be in English.
- Do not add unrelated refactors while fixing benchmark behavior.

## Git And Workspace Safety

- Branch prefix: `codex/`.
- Commit convention: `type(scope): description`.
- The worktree may already be dirty. Never revert user changes or unrelated
  generated outputs.
- Do not commit `campaign_results/` unless explicitly asked; they are often
  large generated evidence.
- Keep commits atomic by concern.

## Documentation Requirements

When changing project direction or benchmark interpretation, update the relevant
artifact/ADR, not only code:

- `documentation/redisgn_v2/phase_07_artifact.md`
- `documentation/decisions/20260506-v11-stigmergic-medium-kernel.md`
- `documentation/redisgn_v2/phase_08_artifact.md`
- `documentation/decisions/20260507-v12-autonomous-agents-over-medium.md`
- `documentation/construction_log.md` when the broader build narrative changes

Do not resurrect old V7 or Sprint 9 instructions as current guidance.

## Knowledge Loop

At the end of each task:

1. Add exactly one capture entry in `.codex/knowledge/captures.md`.
2. Update the matching pattern in `.codex/knowledge/playbook.md`.
3. Append one decision in `.codex/knowledge/decision_log.md`.

Knowledge entries should use English metadata and the repo slug convention:
`<sanitized-repo-name>-<sha1(path)[:6]>`.
