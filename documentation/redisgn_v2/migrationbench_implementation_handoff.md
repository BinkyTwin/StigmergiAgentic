# MigrationBench Implementation Handoff

**Date:** 2026-04-27  
**Audience:** implementation agent  
**Goal:** implement the next scientifically credible evaluation track without rebuilding the whole framework at once.

**Model decision:** primary model is now DeepSeek direct API `deepseek-v4-flash`, not Gemma. Gemma is a stress-test / legacy comparison only.

---

## 1. Read First

Read these files before editing code:

1. `documentation/redisgn_v2/plan_migrationbench_scientific_campaign.md`
2. `documentation/redisgn_v2/deep_research_report_integration.md`
3. `documentation/redisgn_v2/deep_research_brief_for_chatgpt.md`
4. `core/orchestrator.py`
5. `core/agent.py`
6. `tools/decompose.py`
7. `core/emergence.py`
8. `config/default.yaml`
9. `scripts/run_travelplanner_framework_benchmark.py`
10. `scripts/aggregate_campaign_comparison.py`

Treat the plan and this handoff as source of truth if older code comments or docs conflict.

---

## 2. Non-Negotiable Direction

Implement the evaluation track in this order:

```text
official evaluator first
patch artifact first
baseline harness first
V6 static stigmergic run first
V7 ablations later
C3/skills/protocol/compiler last
```

Do not implement full V7 first.  
Do not repair full C3 first.  
Do not enable cross-run learning on the main evaluation split.

Also do not start with prompt optimization. First make the official evaluator, patch contract, workspaces, and baselines mechanically correct.

---

## 2.1 Main Model And Token Policy

Use DeepSeek direct API as the main model:

```yaml
llm:
  provider: "deepseek"
  model: "deepseek-v4-flash"
  base_url: "https://api.deepseek.com"
  max_context_tokens: 1000000
  max_response_tokens: 384000
  max_tokens_total: 500000
  request_timeout_seconds: 600
  retry_attempts: 3
  reasoning:
    mode: "non-thinking"
```

Rationale:

- DeepSeek's current API docs list `deepseek-v4-flash` with 1M context length and 384K maximum output.
- The old Gemma-first plan risks making every arm fail on repo-level Java migration, which would produce no interpretable comparison.
- Unlimited API budget does not mean uncontrolled experiments: all arms must still use the same model, seed, timeout policy, retry policy, and output contract.

Do not use arbitrary low `max_tokens` caps for main runs. If the API/client requires a numeric `max_response_tokens`, set it to the model maximum. If a smaller cap is used for smoke debugging, record it in the manifest and do not mix it with publication-grade results.

### 2.2 Per-Instance Monitoring Policy

"Unlimited API budget" means the main campaign should not be artificially capped before the framework has had enough room to repair hard repositories.

For `main_30`, do not enforce hard per-instance caps on total tokens, wall-clock runtime, number of LLM calls, or number of repair cycles.

Instead, the runner must run in `monitor_only` mode:

```yaml
campaign_monitoring:
  mode: "monitor_only"
  manual_abort_supported: true
  record_tokens_runtime_calls_and_cycles: true
```

Every run summary must still record:

- `tokens_total`
- `cost_total_usd`
- `runtime_seconds`
- `llm_calls`
- `repair_cycles`
- `last_progress_at`
- `manual_abort` and `abort_reason` if the user stops the instance

Manual monitoring is acceptable for this short, high-priority `main_30` campaign. If a run is manually stopped, it remains a full-denominator failure unless it is explicitly rerun from checkpoint.

Do not use an LLM-as-judge as a hidden automatic stopper. It may be useful later to classify stagnation, but it should not silently terminate or continue runs in the main comparison.

---

## 3. First Milestone: Official Preflight First

The first milestone is not "beat baselines" and not "run our adapter".

The first milestone is:

```text
Run the official MigrationBench / JavaMigration evaluation path on 3-5 selected repositories
and produce valid official_eval.json files with logs.
```

A successful milestone produces:

- documented official evaluator command;
- evaluator commit/version;
- Docker image digest or Dockerfile;
- selected repo clone/checkout status;
- baseline build/test status if available;
- `official_eval.json`;
- stdout/stderr logs per repo;
- failure taxonomy for setup failures;
- `campaign_manifest.json`;
- full-denominator `benchmark_summary.json`.

Only after this official preflight passes should the adapter implementation start.

Preflight canary:

```text
If more than 10% of selected repositories fail clone/checkout/evaluator setup before any LLM patching,
do not freeze main_30. Rebuild the subset and document the corpus mortality.
```

---

## 4. Files To Create First

### Fixtures

```text
fixtures/migrationbench/CORPUS.md
fixtures/migrationbench/subsets/smoke_5.jsonl
fixtures/migrationbench/subsets/pilot_20.jsonl
fixtures/migrationbench/subsets/main_30.jsonl
```

Each JSONL row should include at least:

```json
{
  "instance_id": "stable-id",
  "repo_url": "https://github.com/owner/repo",
  "base_commit": "sha",
  "target_java": 17,
  "migration_mode": "minimal",
  "source": "migrationbench_selected",
  "stratum": {
    "repo_size": "small|medium|large",
    "build_complexity": "single-module|multi-module"
  }
}
```

Use `repo_url`, not `github_url`, everywhere.

Do not invent a trivial synthetic toy as evidence. For integration testing, select one concrete small/simple repository from the official selected subset after preflight and document why it was chosen. Synthetic repos are allowed only for unit tests of parser/workspace behavior.

### Adapter

```text
adapters/migrationbench/__init__.py
adapters/migrationbench/schemas.py
adapters/migrationbench/workspace.py
adapters/migrationbench/tools.py
adapters/migrationbench/adapter.py
adapters/migrationbench/evaluator.py
adapters/migrationbench/scientific_baselines.py
adapters/migrationbench/agentless_baseline.py
```

### Scripts

```text
scripts/run_migrationbench_campaign.py
scripts/run_migrationbench_query_export.py
scripts/run_migrationbench_framework_benchmark.py
scripts/aggregate_migrationbench_comparison.py
```

### Config

```text
config/migrationbench_v6_static_deepseek.yaml
```

### Tests

```text
tests/unit/test_migrationbench_workspace.py
tests/unit/test_migrationbench_evaluator.py
tests/unit/test_migrationbench_baselines.py
tests/unit/test_migrationbench_campaign_runner.py
tests/integration/test_migrationbench_toy_repo.py
```

---

## 5. Output Contract

Every arm must emit the same contract:

```json
{
  "instance_id": "owner__repo-id",
  "framework": "stigmergic_v6_static",
  "provider": "deepseek",
  "model": "deepseek-v4-flash",
  "seed": 42,
  "artifact_delivered": true,
  "patch_delivered": true,
  "patch_applies": true,
  "official_success": false,
  "strict_success": false,
  "failure_reason": "tests_failed",
  "migration_mode": "minimal",
  "target_java": 17,
  "build_success": true,
  "test_success": false,
  "compiled_major_version_ok": true,
  "test_count_non_decreasing": true,
  "dependency_policy_ok": null,
  "tokens_total": 0,
  "cost_total_usd": 0.0,
  "runtime_seconds": 0.0,
  "repair_cycles": 0,
  "files_modified_count": 0,
  "patch_lines_added": 0,
  "patch_lines_deleted": 0,
  "markers_created": 0,
  "coordination_overhead": 0
}
```

Strict success is:

```text
artifact_delivered
AND patch_delivered
AND patch_applies
AND official_success
```

Any missing, empty, invalid, inapplicable, or unevaluated patch is a failure.

---

## 6. Mandatory Baselines

Implement these before V7:

1. `no_change`
2. `dependency_only_script`
3. `solo_direct`
4. `solo_cot` or `solo_self_refine`
5. `planner_executor`
6. official `sd_feedback` from `amazon-science/JavaMigration` if runnable
7. `agentless_self_debug` only as fallback if official SD-Feedback cannot run
8. `stigmergic_v6_static`

An agentless/self-debug baseline is mandatory, not optional.

Priority rule:

```text
Run official SD-Feedback directly if possible.
If impossible, document why and only then implement a local agentless_self_debug fallback.
```

Do not accidentally create a weak strawman by reimplementing SD-Feedback naively.

Timebox rule:

```text
Spend at most 1 engineering day trying to make official SD-Feedback run on the smoke/preflight subset.
If it still cannot produce a valid artifact after that, switch to the local fallback and document the blocker as a threat to validity.
```

Do not claim scientific improvement if the framework only beats weak solo baselines.

Minimum budget-cut baseline set for a two-day main_30 attempt:

1. `no_change`
2. `dependency_only_script`
3. `solo_direct`
4. `planner_executor`
5. official `sd_feedback` or documented fallback `agentless_self_debug`
6. `stigmergic_v6_static`

Use `solo_self_refine` instead of `solo_cot` if only one solo structured baseline can be afforded, because migration naturally involves build/test/repair.

---

## 7. Main Eval Guardrails

For smoke, pilot, and main static evaluation:

- `skill_library.enabled: false`
- `protocol.enabled: false`
- `emergence.cross_run.enabled: false`
- `agents.protocol_compiler.enabled: false`
- no best-protocol loading;
- no skill promotion;
- no cross-run config mutation.

Cross-run mechanisms require a separate adaptation split and a held-out evaluation split.

`stigmergic_v6_static` means:

- marker store with explicit task state;
- dependency-aware marker frontier;
- local sensing / pressure-based scheduler;
- ACO-like action pressure and inhibition;
- multiple fixed homogeneous agents;
- audit trail and repair markers;
- no skills, no protocol, no compiler, no cross-run learning, no dynamic V7 population.

This is still stigmergic because agents coordinate through shared environmental traces rather than a central planner assigning every step. It is not C3, and it is not V7.

---

## 7.1 Patch And Workspace Isolation

Each `(framework, instance_id, seed)` must use an isolated clean workspace:

1. clone or restore repository;
2. checkout exact `base_commit`;
3. run baseline setup checks if required;
4. apply candidate edits;
5. export `patch.diff`;
6. verify `patch.diff` applies to a second fresh checkout;
7. run official evaluation only on the fresh patched checkout;
8. delete or archive workspace according to campaign config.

No run may reuse a dirty workspace from another framework, retry, or instance.

Workspace path should include:

```text
workspaces/{campaign_id}/{framework}/{instance_id}/seed{seed}/
```

---

## 7.2 Edit Strategy

Do not ask the LLM to produce raw unified diffs with hunk line numbers.

Preferred strategy:

1. LLM proposes full-file replacements or typed search/replace edits.
2. Harness applies edits to workspace files.
3. Harness computes `patch.diff` using `git diff`.
4. Harness verifies patch applicability on a clean checkout.

This prevents patch failure from being dominated by malformed diff syntax rather than migration quality.

Use one shared typed edit schema for all LLM-based arms:

```json
{
  "edits": [
    {
      "type": "replace_text",
      "path": "pom.xml",
      "old": "<maven.compiler.source>1.8</maven.compiler.source>",
      "new": "<maven.compiler.source>17</maven.compiler.source>",
      "expected_replacements": 1
    },
    {
      "type": "write_file",
      "path": "src/main/java/example/Foo.java",
      "content": "complete file content"
    }
  ]
}
```

Rules:

- `path` must be repository-relative and stay inside the workspace.
- `old` must be non-empty for `replace_text`.
- `expected_replacements` defaults to `1`; mismatch is a typed failure unless `allow_multiple: true`.
- `write_file` writes the complete final file content.
- The harness computes `patch.diff`; the LLM never emits raw `diff --git` output.
- All baselines and the stigmergic arm must use this same schema.

---

## 8. Runner Requirements

The campaign runner must:

- write per-instance stdout/stderr logs;
- checkpoint completed instances;
- resume without duplicates;
- read `campaign_manifest.json` as the denominator source of truth;
- synthesize failed rows for missing/invalid outputs;
- count missing/invalid artifacts as failures;
- write `campaign_manifest.json`;
- write `runs.json`;
- write `official_eval.json`;
- write `benchmark_summary.json`;
- print effective provider/model/seed/config/subset before running.

The runner should call `scripts/run_migrationbench_query_export.py` for one instance at a time. The batch runner owns orchestration, resume, logs, and manifest; the query exporter owns one instance in, artifacts out.

---

## 9. Aggregator Requirements

The aggregator must report:

- strict success rate;
- artifact delivery rate;
- patch applies rate;
- official success rate;
- failure taxonomy;
- paired win/loss tables;
- McNemar vs each baseline;
- bootstrap 95% CI;
- Wilcoxon for cost/tokens/runtime;
- Pareto success vs cost.

The aggregator must be manifest-driven:

```text
requested_instances = campaign_manifest.instances
```

Never infer the denominator from files found on disk.

---

## 9.1 Power Analysis And Interpretation

`main_30` is a credible pilot-sized result, not a high-power proof for small effects.

Rules:

- Do not claim that `main_30` proves a 5-10 point improvement.
- With `n=30`, only large paired differences are likely interpretable.
- If paired discordant cases are low, report the result as inconclusive even if the point estimate is favorable.
- Use pilot results to estimate discordance and decide whether `main_60` is necessary.

Reporting language:

```text
main_30 supports directional evidence and failure analysis.
It is underpowered for small effect-size claims.
```

For the final paper/memoir, include:

- paired win/loss table;
- discordant pair count `(b+c)`;
- McNemar p-value only as secondary evidence;
- bootstrap confidence interval;
- explicit "non-conclusive" label when CI is wide.

---

## 9.2 Official Semantics

Do not define MigrationBench semantics manually when the official evaluator defines them.

In particular:

- `compiled_major_version_ok`;
- multi-module class-version handling;
- test count invariance;
- dependency policy;
- minimal vs maximal migration;
- baseline setup failures.

Read the official evaluator code and mirror its semantics exactly. If local fields are added, they must be labeled as internal telemetry, not official score.

---

## 10. V7 Is Later

Only after V6 static is stable:

```text
v7_dynamic_ticks
v7_elastic_agents
v7_progressive_decompose
v7_specialization
v7_elastic_colony
```

Do not run `v7_elastic_colony` unless at least one isolated V7 arm improves external outcomes or explains a failure reduction.

---

## 11. Definition Of Done For The First Implementation Pass

The first implementation pass is done when:

- MigrationBench official preflight works on 3-5 selected repos before any adapter claims;
- at least one concrete small selected repo is documented for integration testing;
- `no_change` emits valid failures/successes;
- `dependency_only_script` emits applicable patches or typed failures;
- `stigmergic_v6_static` emits a patch-centric run summary;
- aggregator consumes all artifacts without special cases;
- no empty patch can count as success;
- all runs use DeepSeek `deepseek-v4-flash` unless explicitly marked as legacy/stress-test.

Do not optimize prompts before this is true.
