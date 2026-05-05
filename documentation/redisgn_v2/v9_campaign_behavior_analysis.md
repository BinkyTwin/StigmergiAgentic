# V9 Campaign Behavioral Analysis

- Date: 2026-04-23
- `repo_slug`: `stigmergiagentic-33b989`
- Scope: post-hoc readout of the current `campaign_results/` V9/Sprint 9 TravelPlanner campaign artifacts.

## Data Completeness

Current usable artifacts are mixed. The two C3 stigmergic evaluation sets are complete and parseable, but some supporting phases are partial:

| Cell | Files | Parseable | Notes |
| --- | ---: | ---: | --- |
| Gemma stigmergy adapt | 90 | 21 | Queries `21-89` are empty files. |
| Gemma stigmergy C3 | 90 | 90 | `.err` files are mostly Hugging Face unauthenticated warnings, not run failures. |
| DeepSeek stigmergy adapt | 90 | 90 | Complete. |
| DeepSeek stigmergy C3 | 90 | 90 | Complete. |
| Gemma `solo_direct` | 90 | 90 | Complete. |
| Gemma `solo_cot` | 90 | 90 | Complete. |
| Gemma `solo_self_refine` | 90 | 90 | Complete. |
| Gemma `planner_executor` | 90 | 90 | Complete. |
| Gemma `metagpt_sequential` | partial | partial | Still changing during analysis; do not cite until complete/stable. |
| Gemma `langgraph_supervisor` | 0 | 0 | Missing. |

The generated aggregate snapshot in `output/final_campaign_v9_check/` is useful. The aggregation script now exports both `artifact_delivery_rate` and `official_delivery_rate`; the backward-compatible `delivery_rate` column is the official value. This fixes the previous issue where 32/90 no-plan C3 runs per model had `query_results[0].delivered == true` even though the top-level response was `No travel plan generated.` and `evaluation.evaluated_queries == 0`.

## Training/Evaluation Split Check

The current campaign protocol is methodologically weaker than the SwarmAgentic-style TravelPlanner protocol because it splits the validation set manually:

| Protocol | Adapt / train source | Evaluation source | Contamination risk |
| --- | --- | --- | --- |
| Current V9 campaign | `validation[0:90]` | `validation[90:180]` | Medium: both phases come from the same benchmark split. |
| SwarmAgentic-style protocol | `train_45.jsonl` sampled with `sample_step=5` (9 effective examples) | full `validation.jsonl` (180 queries) | Low: train and validation are separate TravelPlanner splits. |
| Recommended Sprint 9 protocol | TravelPlanner `train` split, preferably all 45 queries for stronger adaptation evidence | full TravelPlanner `validation` split, 180 queries | Low, and directly comparable to official 180-query validation results. |

Local evidence confirmed this before the fix:

- SwarmAgentic artifacts under `output/travelplanner_framework_compare/.../swarm/data/` contain `train_45.jsonl` with 45 lines and `validation.jsonl` with 180 lines.
- SwarmAgentic `pso.py` defaults to `dataset_path='data/train_45.jsonl'` and `sample_step=5`, yielding 9 effective training examples.
- The local wrapper `scripts/run_swarmagentic_benchmark.py` records the same protocol: `train_file=train_45.jsonl`, `sample_step=5`, `effective_train_queries=9`, `validation_queries=180`.
- Before implementation, the Sprint 9 shell scripts defaulted to `ADAPT_START=0`, `ADAPT_QUERIES=90`, `EVAL_START=90`, `EVAL_QUERIES=90`, and the default TravelPlanner config set `dataset_split: "validation"`.

The replacement has now been applied:

- Adapt phase: `travelplanner.dataset_split: "train"`, queries `0-44` (or a deliberate SwarmAgentic-compatible subset such as every fifth item).
- Eval phase: `travelplanner.dataset_split: "validation"`, queries `0-179`.
- Baselines: full validation `0-179`, same scorer and same model/backbone conditions.
- Final Docker scripts default to `ADAPT_QUERIES=45`, `EVAL_START=0`, and `EVAL_QUERIES=180`.
- Adapt/eval output folders are cleaned by default through `CLEAN_RESULTS=true` so stale 90-query artifacts do not pollute the next 180-query run.

This does not eliminate the intended adapt-to-eval transfer; it makes it legitimate by moving adaptation to the benchmark train split. The important distinction is:

- `emergence.cross_run` controls whether persistent protocol adaptations are read/written across independent runs.
- The adapt-to-C3 handoff through `skills.db` / `protocols.db` is the training mechanism inside one campaign.
- Disabling `cross_run` alone does not solve validation contamination if the handoff artifacts were learned from `validation[0:90]`; only switching adaptation to `train` fixes that.

## Headline Scores

On the 90-query final evaluation slice:

| Model / Framework | Final pass | Notes |
| --- | ---: | --- |
| Gemma C3 stigmergy | 19/90 = 21.1% | 58 plan responses, 32 no-plan idle stops. |
| DeepSeek C3 stigmergy | 20/90 = 22.2% | 58 plan responses, 32 no-plan idle stops. |
| Gemma `solo_direct` | 16/90 = 17.8% | Cheapest complete baseline. |
| Gemma `solo_cot` | 15/90 = 16.7% | No paired wins over Gemma C3. |
| Gemma `solo_self_refine` | 15/90 = 16.7% | More tokens without net gain. |
| Gemma `planner_executor` | 11/90 = 12.2% | Worst complete baseline. |
| Gemma `metagpt_sequential` | partial | Not comparable until complete/stable. |
| Qwen C3 fixture | 23.9% | Uses a different 180-query fixture. |

Gemma C3 beats complete Gemma baselines in paired comparisons, but the effect is modest and expensive:

| Baseline | C3-only wins | Baseline-only wins | Shared pass |
| --- | ---: | ---: | ---: |
| `solo_direct` | 5 | 2 | 14 |
| `solo_cot` | 4 | 0 | 15 |
| `solo_self_refine` | 6 | 2 | 13 |
| `planner_executor` | 9 | 1 | 10 |

## Behavioral Findings

### 1. C3 did not actually exercise Sprint 9 persistence

Both persistent stores are empty for both model campaigns:

| Store | Gemma | DeepSeek |
| --- | ---: | ---: |
| `skills.db` markers | 0 | 0 |
| `protocols.db` markers | 0 | 0 |

Every parseable adapt and C3 row reports `skills_promoted == 0` and `coordination_protocol_applied == false`. This means the final campaign behaves mostly like the runtime baseline plus C3 config labels, not like an empirical validation of cross-run skill accumulation or protocol persistence.

Likely causes from the current configuration/runtime contract:

- `agents.protocol_compiler.enabled` is false in the scientific adapt/eval configs, so no objective-conditioned protocol is compiled.
- Adapt configs set `emergence.cross_run.enabled: false`, so no cross-run protocol adaptation is persisted during adaptation.
- Skill promotion requires credited lesson IDs, but TravelPlanner tool results do not appear to emit `credited_lesson_ids`; additionally, automatic lesson creation is gated on `completed` / `verified` state transitions while TravelPlanner domain tools mostly use `terminal`.

### 2. There are two failure regimes, not one

C3 failures split cleanly into:

| Model | Pass | No-plan idle | Plan emitted but invalid |
| --- | ---: | ---: | ---: |
| Gemma C3 | 19 | 32 | 39 |
| DeepSeek C3 | 20 | 32 | 38 |

No-plan idle behavior is strongly associated with larger topologies:

| Segment | Gemma no-plan | DeepSeek no-plan |
| --- | ---: | ---: |
| 3-day / 1-city | 1/20 = 5% | 0/20 = 0% |
| 5-day / 2-city | 11/30 = 37% | 12/30 = 40% |
| 7-day / 3-city | 20/40 = 50% | 20/40 = 50% |

Average emergence profile also separates regimes:

| Regime | Gemma avg tokens | Gemma ticks | Gemma parallel utilization | Gemma lock contention |
| --- | ---: | ---: | ---: | ---: |
| Pass | 18.1k | 22.3 | 0.502 | 0.498 |
| No-plan idle | 19.1k | 25.6 | 0.429 | 0.489 |
| Invalid plan | 28.8k | 21.0 | 0.469 | 0.531 |

The no-plan regime is not simply "too few tokens"; it uses fewer tokens than invalid-plan failures and runs more ticks with lower realized parallelism. This looks like decomposition/search exhaustion rather than final validator weakness.

### 3. Once a plan is emitted, hard constraints dominate

For the 58 parsed C3 plan responses per model, commonsense is mostly solved and hard constraints dominate failure:

| Constraint family on emitted C3 plans | Gemma false count | DeepSeek false count |
| --- | ---: | ---: |
| Budget | 36 | 36 |
| Cuisine | 5 | 6 |
| Room type | 1 | 0 |
| Room rule | 0 | 2 |
| Transportation | 0 | 0 |
| Within current city / sandbox | 3 / 3 | 2 / 2 |

The same budget bottleneck appears across complete Gemma baselines:

| Framework | Top validation failure |
| --- | --- |
| `solo_direct` | `hard:valid_cost` in 54/90 |
| `solo_cot` | `hard:valid_cost` in 55/90 |
| `solo_self_refine` | `hard:valid_cost` in 52/90 |
| `planner_executor` | `hard:valid_cost` in 55/90 |

This points to a common planner behavior: itinerary construction chooses valid-looking hotels/restaurants/transports but does not perform budget-first constrained selection or post-plan cost repair.

### 4. Stronger model swap barely changes the frontier

DeepSeek C3 improves only +1 query over Gemma C3 on the same 90-query slice. They share 14 passing queries; Gemma-only passes are `[97, 100, 103, 148, 151]`, DeepSeek-only passes are `[109, 110, 114, 121, 132, 154]`.

This suggests the dominant bottlenecks are orchestration/adapter constraints rather than raw model strength.

## Improvement Queue

Implementation status on 2026-04-23:

- Train/eval split fixed in the final campaign scripts and TravelPlanner adapt/eval presets.
- C3 persistence activation fixed for the scientific adapt configs: adapt now writes train-only `skills.db` and `protocols.db`; C3 eval remains read-only.
- Runtime robustness moved closer to the V6_C settings for C3/adapt: 6 agents, local sensing, emergent lock resolution, recovery controller, dynamic idle, targeted repair, time decay, and frequentation.
- TravelPlanner lesson production now treats successful `terminal` markers as reusable lessons, while failed validation results and unvalidated terminal plans cannot promote skills.
- Agents now credit recalled lesson IDs on successful tool executions, enabling the existing promotion path to populate `skills.db`.
- The aggregate exporter now separates `artifact_delivery_rate` from `official_delivery_rate`.
- Budget behavior now has a first-pass fix: prompt-level budget emphasis and lower-cost candidate ordering before context truncation.

1. Fix the train/eval protocol before the next final campaign.
   - Status: implemented in `scripts/run_gemma_stigmergie_c3_docker.sh`, `scripts/run_deepseek_stigmergie_docker.sh`, `scripts/run_gemma_baselines_docker.sh`, `docker-compose.campaign.yml`, and the TravelPlanner adapt/eval configs.
   - Next run should report the final table on all 180 validation queries so results are comparable with SwarmAgentic, TravelPlanner official, and the Qwen V6_C fixture.

2. Fix Sprint 9 activation before using this campaign as evidence for C1/C2/C3.
   - Status: C3 activation implemented. Adapt-side cross-run writes are enabled in the scientific configs; evaluation consumes artifacts read-only.
   - Status: lesson/skill flow implemented for TravelPlanner terminal successes and recalled lesson credits.
   - C1 protocol compilation is still intentionally separate from C3 configs; use a dedicated C1 config/run if the next experiment needs to isolate objective-conditioned protocol compilation.

3. Fix the metric/export inconsistency.
   - Status: implemented in `scripts/aggregate_campaign_comparison.py`.
   - `evaluated_queries == 0` and `assistant_response == "No travel plan generated."` are not official delivery.

4. Split the next improvement work by failure regime.
   - Status: first-pass implemented. C3 configs now enable dynamic idle/recovery/targeted repair, and planning context now prioritizes lower-cost candidates.
   - Remaining deeper work: if the next 180-query run still shows high no-plan or budget failures, add explicit per-city planning markers and a dedicated cost-repair planner pass.

5. Complete the missing baselines only after the metric fix and split correction.
   - Status: campaign defaults are ready for full validation, but the missing baseline artifacts still need to be regenerated.
   - `metagpt_sequential` and `langgraph_supervisor` should not be cited until their 180 validation outputs are complete and stable.
