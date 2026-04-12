# Decision Log

## 2026-04-12 (V5 Plan Execution Policy)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Treat the proposed V5 plan as a strong draft, but require a pre-execution rewrite that separates pure V4 ablation from tuned-performance work and inserts an explicit TravelPlanner adapter redesign track for multi-city support.
- `rationale`: The current draft mixes causal questions (`what do V4 corrections contribute?`) with optimization changes (`heuristics`, `few-shots`, `max_ticks`, `num_agents`), while the dominant failure mode remains an adapter-level single-destination bottleneck that heuristics alone will not resolve.
- `alternatives_rejected`: Execute the plan unchanged, or reduce V5 to only local tuning without addressing the adapter’s representational limitation.
- `linked_adr`: `N/A (campaign planning rule)`

## 2026-04-11 (TravelPlanner Failure Interpretation)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Interpret the current TravelPlanner scientific comparison as a single-destination-capable benchmark slice, and treat the `5-day / 2-city` and `7-day / 3-city` collapse of `StigmergiAgentic` as a structural adapter limitation until multi-city routing and explicit empty-plan failure export are implemented.
- `rationale`: The analysis of run `20260409_233919` showed that the adapter binds search and routing to one `dest`, while many failed queries terminate with `final_plan=[]` and `No travel plan generated.` under `status=ok`; reading these outcomes as random planner weakness would overstate the current generality of the framework.
- `alternatives_rejected`: Continue discussing the failures as generic LLM instability, or interpret the current TravelPlanner table as evidence of multi-city capability without adapter-level routing support.
- `linked_adr`: `N/A (post-run scientific interpretation rule)`

## 2026-04-09 (LangGraph Robustness)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Handle LangGraph TravelPlanner intermediate-node structured-output failures with parse retries and deterministic fallbacks instead of aborting the batch on the first malformed JSON response.
- `rationale`: Hosted-model runs can return transport-successful but schema-invalid payloads; batch reproducibility is better served by bounded local degradation than by full campaign interruption.
- `alternatives_rejected`: Keep single-shot schema parsing with hard failure, or silently ignore malformed fields without explicit retry/fallback behavior.
- `linked_adr`: `N/A (benchmark runtime hardening)`

## 2026-04-09

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Make the principal TravelPlanner comparison notebook stream Docker command output live and skip redundant `travelplanner-smoke` rebuilds unless tracked build inputs change or a force flag is set.
- `rationale`: The previous setup cell buffered `docker compose build` output entirely, which made legitimate work look frozen and forced unnecessary rebuild time on every notebook rerun.
- `alternatives_rejected`: Keep buffered subprocess capture in the notebook, or remove the explicit build step entirely without any cache or diagnostic layer.
- `linked_adr`: `N/A (notebook execution-path hardening)`

## 2026-04-08

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Retire SwarmAgentic from the principal TravelPlanner benchmark and adopt `LangGraph Supervisor` as the main centralized hierarchical baseline, executed through a Docker-first shared benchmark pipeline.
- `rationale`: SwarmAgentic proved operationally non-reproducible in the controlled Qwen/OpenRouter protocol, while LangGraph enables an explicit, durable, in-repo state-graph baseline that can share the same scorer, split, and artifact contract as `Solo` and `StigmergiAgentic`.
- `alternatives_rejected`: Keep SwarmAgentic in the main comparison table, compare only `Solo` vs `StigmergiAgentic`, or use a generic LangChain agent path without an explicit graph/state-machine baseline.
- `linked_adr`: `N/A (benchmark methodology pivot)`

## 2026-02-10

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Adopt JSON pheromone store with POSIX file locking and append-only audit trail for Sprint 1.
- `rationale`: Aligns with architecture plan artifacts while ensuring concurrency safety and RQ3 traceability.
- `alternatives_rejected`: Plain unlocked JSON store, full SQLite migration in Sprint 1.
- `linked_adr`: `documentation/decisions/20260210-sprint1-environment-medium.md`

## 2026-02-11

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Implement Sprint 2 validation as mock-first tests with optional non-blocking `live_api` smoke coverage.
- `rationale`: Keeps agent behavior tests deterministic while preserving a direct OpenRouter wiring check path.
- `alternatives_rejected`: Fully live API blocking tests, fully mocked suite without any smoke check.
- `linked_adr`: `documentation/decisions/20260210-sprint2-agents-unitaires.md`

## 2026-02-12

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Adopt Sprint 3 adaptive fallback classification and mountpoint-safe Docker execution to satisfy the blocking gate on `docopt/docopt@0.6.2`.
- `rationale`: Preserves adaptive all-file coverage without static scope filtering while eliminating false negatives from script entrypoints, optional dependencies, and host mount deadlocks.
- `alternatives_rejected`: Threshold-only tuning without fallback reclassification, static exclusion of tests/examples/setup files, bind-mounted `target_repo` with direct delete/reclone.
- `linked_adr`: `documentation/decisions/20260212-sprint3-loop-gating-docopt.md`

## 2026-02-12 (Patch)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Remove hard LLM completion cap and add optional USD cost budgeting using OpenRouter pricing + usage-based accounting.
- `rationale`: Hard output caps reduced migration quality on thinking models; USD-level control is required for reliable cost governance and comparability.
- `alternatives_rejected`: Keep `max_response_tokens=4096`, rely only on token-count budgeting, or disable budgeting entirely.
- `linked_adr`: `documentation/decisions/20260212-sprint3-llm-cost-budget-and-uncapped-output.md`

## 2026-02-12 (Patch 2)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Hard-disable `max_tokens` in runtime requests (ignore `llm.max_response_tokens` even when set).
- `rationale`: Prevents accidental reintroduction of output truncation during migrations, especially in stale Docker-image scenarios.
- `alternatives_rejected`: Keep optional `max_response_tokens` passthrough, rely on manual config discipline.
- `linked_adr`: `documentation/decisions/20260212-sprint3-llm-cost-budget-and-uncapped-output.md`

## 2026-02-17

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Treat Sprint 4 as tooling-complete but benchmark-incomplete until fairness runs and Pareto reporting requirements are satisfied.
- `rationale`: Code paths and tests pass, but current evidence is smoke-level and does not yet meet protocol constraints (`>=5 runs/config`, confidence-interval reporting, complete baseline input coverage).
- `alternatives_rejected`: Mark Sprint 4 fully complete based only on single-run snapshot and mean/std-only Pareto output.
- `linked_adr`: `documentation/decisions/TBD-sprint4-benchmark-readiness.md`

## 2026-02-17 (Closure Implementation)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Upgrade Pareto tooling to enforce baseline coverage and export raw+aggregate evidence, then close Sprint 4 with a bounded 5x3 benchmark protocol on `docopt/docopt@0.6.2`.
- `rationale`: Prevents partial-data misinterpretation and provides reproducible closure artifacts when full unconstrained campaigns are too costly for the current iteration.
- `alternatives_rejected`: Keep aggregate-only Pareto output, accept silent missing-baseline inputs, or defer all benchmark execution until a later sprint.
- `linked_adr`: `documentation/decisions/TBD-sprint4-closure-bounded-benchmark-and-pareto-v2.md`

## 2026-02-17 (Benchmark Stability Hardening)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Add explicit LLM request timeout (`llm.request_timeout_seconds`) and sequential stage action cap (`loop.sequential_stage_action_cap`) to reduce benchmark run hangs.
- `rationale`: Repeated baseline runs showed long-running/non-terminating behavior under provider latency and nested stage loops; bounded runtime controls are needed for campaign completion.
- `alternatives_rejected`: Keep SDK default timeout behavior and unbounded stage `while run()` loops.
- `linked_adr`: `documentation/decisions/TBD-benchmark-runtime-stability-timeout-stage-cap.md`

## 2026-02-17 (Unbounded 5x3 Final Batch Execution)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Execute missing Sprint 4 benchmark runs in parallel using isolated temporary workspace copies, then treat `metrics/output/sprint4_20260217_full` as the canonical unbounded 5x3 batch.
- `rationale`: Parallelism reduces wall time, while per-worker workspace isolation avoids race conditions/cross-run contamination on shared runtime artifacts.
- `alternatives_rejected`: Run all remaining jobs serially, or run them in parallel from one workspace with shared `target_repo`/`pheromones`.
- `linked_adr`: `documentation/decisions/TBD-sprint4-unbounded-5x3-final-batch.md`

## 2026-02-19 (Sprint 5 Provider Switch: OpenRouter + Z.ai)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Make `LLMClient` provider-aware and adopt `zai` + `glm-5` as default Sprint 5 frontier configuration while preserving OpenRouter compatibility.
- `rationale`: Sprint 5 requires a frontier model (`glm-5`) and reliable provider switching without touching agent orchestration logic.
- `alternatives_rejected`: Fork a dedicated Z.ai client, or hard-replace OpenRouter paths with Z.ai-only logic.
- `linked_adr`: `documentation/decisions/TBD-sprint5-provider-switch-zai-glm5.md`

## 2026-02-19 (Anti-429 Controls for Z.ai)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Introduce built-in anti-rate-limit controls in `LLMClient` (inter-call pacing + 429-specific backoff floor + jitter), and enable them in default config.
- `rationale`: Repeated Sprint 5 runs encountered frequent Z.ai `429` responses; centralized pacing/backoff is required for stable batch execution.
- `alternatives_rejected`: Handle delays only in shell loops, or raise retries without pacing control.
- `linked_adr`: `documentation/decisions/TBD-sprint5-anti429-llm-pacing.md`

## 2026-02-19 (Provider Default Rollback to OpenRouter)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Restore OpenRouter as default runtime provider/model for Sprint execution (`qwen/qwen3-235b-a22b-2507`) and disable default inter-call pacing.
- `rationale`: User prioritizes faster campaign throughput; current Z.ai rate-limiting profile introduced repeated delays and unstable batch progress.
- `alternatives_rejected`: Keep Z.ai default with long enforced pacing intervals.
- `linked_adr`: `documentation/decisions/TBD-sprint5-openrouter-default-rollback.md`

## 2026-02-19 (GPT-5-nano Pre-Sprint Trial Protocol)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Run the pre-Sprint model trial with `openai/gpt-5-nano` (OpenRouter) as 5 complete stigmergic runs without `--max-tokens`, and report from a curated exact-5 output set.
- `rationale`: The trial needed uncapped completions and strict sample size control (`n=5`) despite an interrupted batch during execution.
- `alternatives_rejected`: Keep the interrupted mixed run set as-is, or rerun everything from scratch serially.
- `linked_adr`: `documentation/decisions/TBD-pre-sprint-gpt5nano-trial-protocol.md`

## 2026-02-26

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Execute V2 Sprint 1 as a hard reset branch and replace JSON pheromone storage with a generic SQLite/WAL marker store plus mandatory append-only audit.
- `rationale`: A clean cut removes legacy role-coupled constraints and provides a stable, domain-agnostic coordination substrate with stronger concurrency and governance guarantees.
- `alternatives_rejected`: Coexistence with V0.1 runtime, or delaying SQLite migration while keeping JSON+file-lock storage.
- `linked_adr`: `documentation/decisions/20260226-sprint1-v2-core-reset-and-sqlite-marker-store.md`

## 2026-02-26 (Documentation Protocol)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Require a per-sprint artifact functioning note in `documentation/redisgn_v2/sprint_XX_artifact.md` for all future sprint closures.
- `rationale`: This creates a stable, sprint-granular trace of runtime behavior and reduces onboarding ambiguity for future agents.
- `alternatives_rejected`: Keeping artifact-state notes only in `construction_log.md`, or relying on ad-hoc sprint summaries.
- `linked_adr`: `N/A (process rule)`

## 2026-02-26 (Sprint 2 V2 Runtime)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Implement Sprint 2 with an async core runtime (`Environment`, `StigmergicAgent`, `Orchestrator`) plus sync test wrapper, pressure-driven selection, and environment-mediated deposits.
- `rationale`: This preserves stigmergic decentralization, keeps mutation/guardrail control centralized, and enables deterministic unit validation without external dependencies.
- `alternatives_rejected`: Fully synchronous orchestrator, direct tool-to-store writes, and deferred LLM client port.
- `linked_adr`: `documentation/decisions/20260226-sprint2-v2-agent-orchestrator-runtime.md`

## 2026-02-26 (Sprint 3 V2 Assistant Runtime)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Implement Sprint 3 as a shared infrastructure-tool layer plus an `assistant` adapter and CLI entrypoint, while keeping adapter scope `assistant`-only for this sprint.
- `rationale`: This enables end-to-end framework usage without coupling to benchmark adapters and preserves a clean path to register the same tools in future domain adapters.
- `alternatives_rejected`: Adding partial TravelPlanner/CodeMigration stubs in Sprint 3, or introducing assistant-specific tool contracts outside `ToolRegistry`.
- `linked_adr`: `documentation/decisions/20260226-sprint3-v2-infrastructure-tools-and-assistant-mode.md`

## 2026-03-04 (Assistant Eligibility Defaults + Execution-Oriented Output)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Remove hardcoded assistant marker allowlists (`decompose`/`think`) and move to context-derived tool eligibility defaults, while preserving explicit `eligible_actions` as an override and enriching final CLI responses with concrete tool outputs.
- `rationale`: Hardcoded allowlists prevented execution-capable tools from participating in normal assistant runs and produced plan-only outputs; context-derived eligibility restores practical execution without losing adapter-level control.
- `alternatives_rejected`: Keep strict allowlists everywhere, or make all tools universally eligible regardless of required payload inputs.
- `linked_adr`: `N/A (runtime behavior refinement in Sprint 3 scope)`

## 2026-03-04 (Think-Then-Act Gate for Active Subtasks)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Enforce a think-then-act lifecycle where active subtasks are progressed by concrete execution tools, while `think` is blocked on generic active markers and only allowed on a decomposed root-marker exception path.
- `rationale`: This prevents plan-only marker completion and aligns terminal progress with artifact-generating actions (read/write/bash/search) rather than repeated reasoning-only loops.
- `alternatives_rejected`: Keep `think` fully eligible on active markers, or force all markers through static hardcoded tool allowlists.
- `linked_adr`: `N/A (runtime execution policy update)`

## 2026-03-04 (Emergent Structure over Fixed Decomposition Defaults)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Remove fixed decomposition defaults and heuristic tool-hint inference by making `subtask_count` optional, using LLM-only structured hints in `think`, and driving intensity decrements from config.
- `rationale`: Fixed `subtask_count=3` and local hint inference introduced non-emergent behavior and planner bias; optional shaping + strict structured outputs better preserve execution-first stigmergic dynamics.
- `alternatives_rejected`: Keep forced default subtask counts, keep `_infer_tool_hints` fallback, or keep hardcoded intensity decrements in tool code.
- `linked_adr`: `N/A (Sprint 3 V2 runtime behavior refinement)`

## 2026-03-04 (Sprint 4 V3 Runtime Overhaul)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Standardize V3 runtime on structured async LLM interactions, dependency-gated marker scheduling, and session-isolated persistence while preserving sync backward compatibility.
- `rationale`: This combination addresses major instability sources (untyped outputs, race-prone concurrency, dependency violations, and cross-run state leakage) without breaking existing sync consumers.
- `alternatives_rejected`: Async-only breaking migration, prompt-only dependency conventions without runtime enforcement, shared single DB path across runs.
- `linked_adr`: `documentation/decisions/20260304-sprint4-v3-runtime-overhaul.md`

## 2026-03-04 (Sprint 5 V3 Memory + Emergence + Lessons)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Extend Sprint 4 V3 with bounded episodic agent memory, schema-neutral emergence telemetry, and automatic high-quality `lesson` marker deposition while keeping marker persistence schema unchanged.
- `rationale`: The thesis runtime needed cognition and observability signals beyond intensity reinforcement, but introducing DB/schema migrations would increase risk and coupling; decision-level memory payloads + audit-log parsing preserve compatibility and traceability.
- `alternatives_rejected`: Persist agent memory directly in marker schema, add dedicated emergence tables, or keep emergence/lesson logic as external post-processing only.
- `linked_adr`: `documentation/decisions/20260304-sprint5-v3-memory-emergence-lessons.md`

## 2026-03-05 (Sprint 6 V3 TravelPlanner Domainization)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Standardize TravelPlanner integration as a dedicated adapter vertical slice (`workspace`, `tools`, `adapter`, `evaluator`) and remove V0.1 legacy runtime/tests in the same sprint.
- `rationale`: This provides a clean domain-validation signal for V3 architecture without core coupling to legacy code paths, while ensuring benchmark scoring remains deterministic and auditable.
- `alternatives_rejected`: Keep mixed V0.1/V3 runtime coexistence; perform LLM-based constraint evaluation; postpone cleanup to a later sprint.
- `linked_adr`: `documentation/decisions/20260305-sprint6-travelplanner-adapter-and-fidelity-eval.md`

## 2026-03-06 (OC1-OC5 Thesis Alignment Audit Method)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Evaluate thesis alignment with a three-layer matrix (`literature intent -> V3 plan promise -> current V3 repo evidence`) and treat only current-runtime-backed evidence as valid proof.
- `rationale`: This prevents mixing roadmap claims, legacy artifacts, and actual V3 capabilities, and makes DSR readiness gaps visible without overstating implementation maturity.
- `alternatives_rejected`: Audit only the plan against the review, or count historical/non-V3 artifacts as current proof.
- `linked_adr`: `documentation/v3_oc1_oc5_alignment_audit.md`

## 2026-03-06 (Colab Qwen3-14B-AWQ Notebook Hardening)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Rebuild the Colab Qwen benchmark notebook around auto-detected AWQ loading, conservative Tesla T4 vLLM settings, and file-backed startup diagnostics instead of forced backend/quantization overrides.
- `rationale`: The previous notebook hid the root cause behind truncated logs and brittle T4-specific assumptions; a restart-aware install flow plus explicit log capture is more stable and debuggable across Colab images.
- `alternatives_rejected`: Keep forcing `FLASHINFER` with `awq_marlin`, or keep the existing timeout path that only surfaces `Engine core initialization failed`.
- `linked_adr`: `N/A (notebook/runbook hardening)`

## 2026-03-06 (TravelPlanner Colab Benchmark Execution Path)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Rebuild the TravelPlanner Sprint 6 notebook to run through a local Colab vLLM server plus a temporary runtime override config, with per-query checkpoints and official scorer evaluation kept inside the notebook flow.
- `rationale`: This keeps the benchmark path reproducible on Colab without changing checked-in runtime defaults, while making long-running local inference resilient to restarts and preemption.
- `alternatives_rejected`: Keep the previous notebook's hosted-LLM assumptions and coarse checkpoint cadence, or hardcode local Colab settings into repo YAML files.
- `linked_adr`: `N/A (notebook/runbook hardening)`

## 2026-03-06 (Colab Feasibility Verdict Protocol)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Frame the root-level Colab Qwen notebook as a thesis-facing feasibility protocol with repeated stability checks and a three-level verdict (`GO`, `CONDITIONAL GO`, `NO-GO`) instead of a single-pass `works/does not work` check.
- `rationale`: The thesis question is about benchmark credibility, not only local execution; repeated load, structured-output reliability, and provenance-aware interpretation are required before replacing or complementing the current backend.
- `alternatives_rejected`: Keep a latency-only smoke notebook, or use a binary startup verdict without repeated benchmark-style requests.
- `linked_adr`: `N/A (benchmark notebook protocol)`

## 2026-03-22 (Sprint 6 V4 Stigmergic Corrections)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Implement local sensing, temporal decay, frequentation reinforcement, emergent contention resolution, and emergence feedback as opt-in runtime features instead of replacing the default Sprint 6 behavior.
- `rationale`: The thesis needed a stronger stigmergic interpretation, but replacing the existing runtime in-place would have broken compatibility, muddied benchmark comparisons, and increased rollout risk.
- `alternatives_rejected`: Hard-switch the runtime to the new behavior by default, or implement only local sensing and leave the other audit findings unresolved.
- `linked_adr`: `documentation/decisions/20260322-sprint6-v4-stigmergic-corrections.md`

## 2026-03-12 (Repo-Local RunPod Operations Skill)

## 2026-03-17 (TravelPlanner Failure-Triage Lens)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Diagnose TravelPlanner benchmark quality primarily through scenario-shape buckets (`3 days/1 city`, `5 days/2 cities`, `7 days/3 cities`) before changing prompts or models.
- `rationale`: The official run shows a regime break by itinerary shape, which is more informative than top-line pass rates and points directly to adapter/search-coverage limitations rather than generic model weakness.
- `alternatives_rejected`: Tune prompts from aggregate scores only, or attribute the low final pass rate primarily to model quality without scenario-level decomposition.
- `linked_adr`: `N/A (analysis decision for benchmark triage)`

## 2026-03-17 (Controlled OpenRouter GPT-4o Framework Comparison Protocol)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Standardize the next TravelPlanner framework comparison on OpenRouter-routed `openai/gpt-4o`, the validation split, and the shared official scorer, with SwarmAgentic adapted only at the provider/model-compatibility layer and result normalization layer.

## 2026-04-01 (SwarmAgentic OpenRouter Fault Tolerance)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Harden the SwarmAgentic OpenRouter adaptation with per-iteration PSO checkpoints, task-level degradation on transient provider failures, and conservative notebook rerun defaults for the Qwen3.5-9B comparison flow.
- `rationale`: OpenRouter `504` responses and null structured outputs were causing full-run loss after long PSO executions; resumable checkpoints and non-fatal task failure handling preserve benchmark progress and reduce wasted wall-clock time.
- `alternatives_rejected`: Keep end-of-run-only checkpointing, rely only on provider retries, or keep the notebook defaults at high concurrency with forced re-clone/reinstall on every rerun.
- `linked_adr`: `N/A (benchmark workflow hardening)`
- `rationale`: This gives a materially stronger framework comparison than mixing published paper numbers and local Qwen runs, while keeping the remaining uncontrolled factor (SwarmAgentic PSO optimization before evaluation) explicit.
- `alternatives_rejected`: Compare local Qwen scores directly to the published GPT-3.5/GPT-4o table, or reimplement SwarmAgentic behavior from scratch inside this repo.
- `linked_adr`: `N/A (experiment protocol decision)`

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Add a repo-local `runpod-ops` skill that prioritizes the installed `runpodctl` command shape over stale documentation examples, while bundling official RunPod product constraints and a StigmergiAgentic-specific Pod workflow.
- `rationale`: RunPod became the likely replacement for Colab in long-running benchmark work, and successful operation depends on precise CLI syntax plus durable Pod/storage guidance; a local skill reduces repeated rediscovery and avoids using deprecated RunPod commands.
- `alternatives_rejected`: Rely on ad-hoc web searches each turn, or write a doc-only note without a reusable skill structure.
- `linked_adr`: `N/A (local skill and workflow enablement)`

## 2026-03-12 (Autoresearch Integration Pattern)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Integrate `karpathy/autoresearch` into V3 as a native research adapter with fixed evaluation and artifact iteration, not by embedding its single-repo training assumptions directly.
- `rationale`: V3 already exposes the right extensibility points (`DomainAdapter`, `ToolRegistry`, evaluator-style scoring, reinforcement), while direct embedding would couple the runtime to `autoresearch`-specific artifacts such as `train.py`, `prepare.py`, and `results.tsv` and would not cover literature-grounding needs.
- `alternatives_rejected`: Run `autoresearch` unchanged as an outer shell around this repo, or overload the generic assistant adapter with ad hoc research behavior.
- `linked_adr`: `N/A (integration strategy note)`

## 2026-03-13 (Repo-Local Objective Autoresearch Skill)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Implement one hybrid repo-local skill, `objective-autoresearch`, instead of splitting framework self-improvement and sourced research into separate skills.
- `rationale`: The user wants one shared mentality centered on objective retention, fixed evaluation, and keep/discard iteration; a single skill with explicit mode selection keeps invocation simple while still preventing drift through narrow trigger rules and mode-specific references.
- `alternatives_rejected`: Create two separate skills, or keep the autoresearch mentality as an informal prompt pattern without reusable skill packaging.
- `linked_adr`: `N/A (repo-local skill implementation)`

## 2026-03-13 (Home AGENTS Simplification)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Remove the `Knowledge Governance` section from `/Users/lotfi/.codex/AGENTS.md` and replace it with one lightweight repo-local skill preference under `Skill Hygiene`.
- `rationale`: The heavier section added policy weight without improving day-to-day execution; a concise locality rule preserves the useful behavior while making the principal AGENTS file easier to read and maintain.
- `alternatives_rejected`: Keep the section as-is, or delete it without preserving any guidance about repo-local vs home-level skills.
- `linked_adr`: `N/A (home instruction cleanup)`

## 2026-03-13 (RunPod TravelPlanner Pod Workflow)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Standardize TravelPlanner remote execution around a branch-pinned RunPod workflow with one local creation script, one raw-fetched bootstrap script, and repo-resident smoke/package scripts.
- `rationale`: The repository is too heavy and too dirty to mirror blindly, while the pod starts empty; a pushed-ref workflow keeps the execution source auditable and lets the pod bootstrap itself from GitHub before running `uv`-based TravelPlanner checks.
- `alternatives_rejected`: Sync the whole local workspace to the pod with `runpodctl send`, clone an unspecified branch ad hoc on the pod, or rely on Docker Compose inside the pod for benchmark execution.
- `linked_adr`: `N/A (ops workflow standardization)`

## 2026-03-13 (OpenRouter Baseline Reset and Local Smoke Standard)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Standardize the checked-in runtime baseline on OpenRouter `qwen/qwen3.5-9b`, expose LLM metadata in CLI JSON summaries, and use one local TravelPlanner smoke script as the default verification path while pruning notebook and pod-workflow detours from the main repo surface. For the stable TravelPlanner path, cap completions, disable OpenRouter reasoning on strict-JSON calls, and compact the itinerary prompt to workspace-backed records.
- `rationale`: A single baseline reduces setup drift and decision fatigue, keeps fixtures aligned with real runtime defaults, and preserves scorer-backed validation without carrying Colab/Kaggle/RunPod workflow complexity in the everyday repository path. The live provider behavior showed that uncapped reasoning-heavy responses were the real blocker, so the runtime now treats strict JSON planning as a bounded, non-reasoning task.
- `alternatives_rejected`: Keep `qwen/qwen3.5-flash-02-23` or older 235B defaults as the baseline, retain the pod-specific smoke flow as the standard path, leave benchmark notebooks and session artifacts in the primary repo surface, or keep reasoning enabled and rely on prompt wording alone to suppress long thought traces.
- `linked_adr`: `N/A (baseline cleanup and workflow narrowing)`

## 2026-03-17 (Docker as the Benchmark Validation Source of Truth)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Run the TravelPlanner smoke workflow through Docker Compose by default and treat the containerized result as the only benchmark-valid evidence path.
- `rationale`: The repository already defines Docker as its reproducible execution contract; validating benchmark runs from the host shell creates ambiguity about environment, dependency source, and artifact provenance. The containerized smoke reproduced the same `final_pass_rate=0.0`, so quality gaps now clearly belong to framework behavior rather than host drift.
- `alternatives_rejected`: Keep using the host-local smoke script as the default benchmark path, or introduce query-specific scorer patches before first aligning execution provenance.
- `linked_adr`: `documentation/decisions/20260212-sprint2.5-docker-infrastructure.md`

## 2026-03-17 (TravelPlanner Scorer-Grounded Planning Standard)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Improve TravelPlanner benchmark performance only through framework-level grounding changes: explicit route-search markers, scorer-aligned serialization, sandbox-aligned inventories, feasibility-aware hotel candidate selection, and replanning from official failure messages.
- `rationale`: These changes preserve the philosophy of the framework by strengthening the adapter's contracts and planner loop instead of inserting query-specific shortcuts or evaluator-side hacks. The resulting Docker smoke reached `final_pass_rate=1.0` on `Query 0` while staying within the benchmark's official search space and scoring semantics.
- `alternatives_rejected`: Hardcode `Query 0` templates, patch the official evaluator, inject post-hoc manual itinerary rows, or keep free-form planner outputs and hope the scorer infers intent from approximate strings.
- `linked_adr`: `N/A (adapter and planning-loop standardization)`

## 2026-03-17 (Notebook as the Dockerized Full-Eval Driver)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Add a notebook driver for the full official TravelPlanner campaign, but keep all benchmark execution and official scoring inside Docker with resumable per-query checkpoints.
- `rationale`: The user needs a convenient cockpit for launching and inspecting the full official benchmark, but moving execution into the host notebook kernel would weaken environment provenance and make results harder to compare with scripted Docker runs. A Docker-driven notebook preserves the benchmark contract while making long campaigns easier to start, resume, and analyze.
- `alternatives_rejected`: Run the full benchmark directly in the notebook kernel, keep only shell scripts with no interactive inspection surface, or embed official evaluation logic directly into the notebook instead of reusing the repository scripts.
- `linked_adr`: `N/A (benchmark notebook orchestration)`

## 2026-03-17 (Explicit Repo Root for Docker Script Entry Points)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Require Docker-invoked repository scripts to inject the repository root into `sys.path` before importing project modules, and apply that rule to `scripts/run_travelplanner_query_export.py`.
- `rationale`: Container entrypoints executed by absolute script path do not reliably inherit the repository root on Python's import path, which can collapse an entire benchmark campaign into uniform runtime failures. Making the entrypoint self-sufficient keeps notebook, shell, and Docker execution paths aligned.
- `alternatives_rejected`: Assume the container working directory will always rescue imports, switch every invocation to `python -m ...`, or debug runtime failures only after a full split has already been attempted.
- `linked_adr`: `N/A (entrypoint robustness rule)`

## 2026-03-22 (Controlled Same-Model Qwen Framework Comparison Protocol)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Standardize TravelPlanner framework comparisons on a three-arm protocol that fixes OpenRouter as provider, `qwen/qwen3.5-9b` as routed model, the official validation split as dataset, and the local official scorer as the only scoring path, with evaluation arms for solo Qwen, SwarmAgentic, and StigmergiAgentic.
- `rationale`: The earlier comparison mixed frameworks and model families, which made any scientific claim about orchestration strength too weak. Holding provider, model, split, and scorer constant while adding a solo-model arm isolates what the orchestration contributes relative to the same base model and makes cross-framework differences interpretable.
- `alternatives_rejected`: Compare against published GPT-3.5 or GPT-4o table values directly, compare only SwarmAgentic versus StigmergiAgentic without a solo baseline, or score each framework through its own native evaluation path.
- `linked_adr`: `N/A (controlled benchmark protocol)`

## 2026-04-02 (TravelPlanner Comparison Reporting Gate)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Treat the current notebook as valid internal evidence for the two completed arms (`solo` and `StigmergiAgentic`) but not yet as a publishable three-way benchmark artifact; require a clean single-run rerender, explicit budget reporting, and a clarified Swarm patch scope before thesis-grade reporting.
- `rationale`: The persisted JSON artifacts support the reported two-arm scores, but the notebook surface currently mixes outputs from multiple run tags and the Swarm preparation layer changes execution behavior beyond simple provider wiring. Without cleaning those issues, a reader could overinterpret the notebook as a fully reproducible and methodologically matched framework comparison.
- `alternatives_rejected`: Cite the notebook as-is in thesis text, hide the budget asymmetry behind aggregate pass rates only, or describe the patched Swarm baseline as an untouched upstream comparison.
- `linked_adr`: `N/A (benchmark review gate)`

## 2026-04-02 (Qwen Swarm Benchmark Modes and Failure Separation)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Run the Qwen SwarmAgentic TravelPlanner baseline through explicit `preflight`, `pilot`, and `full` modes with mode-specific artifacts, classify provider `504` outages as `infra_failure` rather than score `0`, and keep the notebook on the healthy local interpreter for repo scripts while reserving isolated virtualenv use for the cloned Swarm baseline.
- `rationale`: The thesis benchmark needs a fair same-backbone comparison, but the original notebook mixed orchestration, scoring, and baseline setup inside large cells and let provider failures surface as hard crashes. Separating modes and status artifacts makes the Swarm path resumable and auditable, while decoupling local notebook scripts from a broken project `.venv` keeps the experiment runnable without relaxing the isolation of the external baseline.
- `alternatives_rejected`: Keep the monolithic notebook cell, treat `504` as benchmark score failures, or force every local script through the project `.venv` even when that environment is corrupted.
- `linked_adr`: `N/A (benchmark orchestration rule)`

## 2026-04-03 (Standalone Swarm Full Comparison Notebook)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Add a dedicated notebook for the strict full SwarmAgentic Qwen comparison that reruns only SwarmAgentic and compares it against the previously completed Solo and StigmergiAgentic artifacts from a fixed reference run tag by default.
- `rationale`: The unstable part of the thesis comparison is the Swarm baseline, not the already-scored Solo and StigmergiAgentic arms. A baseline-specific notebook shortens rerun cycles, reduces accidental churn on the stable arms, and makes it easier to enforce a scientific gate where the final table appears only if Swarm finishes successfully.
- `alternatives_rejected`: Reuse the large three-arm notebook for every Swarm retry, manually copy paths into ad hoc cells, or compare only aggregate official scores without paired per-query final-pass analysis.
- `linked_adr`: `N/A (dedicated baseline notebook rule)`

## 2026-04-07 (Notebook-Level Python Auto-Resolution)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Make the dedicated Swarm scientific notebook resolve a working interpreter dynamically and run all local repo scripts through that interpreter instead of calling bare `python`.
- `rationale`: The benchmark notebook can execute under a kernel environment that differs from the shell's default `python`, which leads to immediate failures on imports such as `datasets`. Probing interpreters up front and standardizing on one verified interpreter is cheaper and safer than expecting users to manually reconcile environments before each rerun.
- `alternatives_rejected`: Keep hardcoded `python` calls, instruct the user to repair environments manually before notebook use, or pin the notebook to a single absolute interpreter path.
- `linked_adr`: `N/A (notebook runtime robustness rule)`

## 2026-04-07 (SwarmAgentic Watchdog Observability)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Wrap the SwarmAgentic benchmark subprocesses with heartbeat-based monitoring, watched-artifact inactivity timeouts, patch-revision clone refresh, and notebook-visible debug artifacts instead of trusting raw subprocess liveness.
- `rationale`: The Qwen/OpenRouter Swarm baseline can enter long silent stalls where the Python process stays alive, no checkpoint is written, and the notebook appears to "run" for tens of minutes without progress. A watchdog keyed to real progress signals plus file-backed monitor artifacts reduces wasted wall-clock time and makes infra stalls auditable without conflating them with benchmark scores.
- `alternatives_rejected`: Wait indefinitely on living subprocesses, rely only on provider SDK timeouts, or inspect hangs manually from external terminal tools after each failed run.
- `linked_adr`: `N/A (baseline observability and recovery rule)`

## 2026-04-09 (Organization-Philosophy TravelPlanner Benchmark)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Promote the principal TravelPlanner benchmark from a small named-framework comparison to a publication-oriented organization-philosophy study with six controlled arms, three seeds, gated execution (`preflight/pilot/full`), and a generated paper pack of statistical and methodological artifacts.
- `rationale`: The thesis claim is about stigmergic organization quality, not about outperforming one unstable external repo or one orchestration SDK. Reframing the benchmark around organizational forms preserves scientific fairness, aligns better with DSR/FEDS, and makes the comparison auditable and publishable through reproducibility artifacts rather than notebook screenshots.
- `alternatives_rejected`: Keep the three-arm framework-branded comparison only, rely on SwarmAgentic as the main external baseline despite reproducibility failures, or compute publication tables manually outside the repository.
- `linked_adr`: `N/A (scientific benchmark framing rule)`

## 2026-04-09 (TravelPlanner Official Evaluator Runtime Path Repair)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Harden the vendored TravelPlanner official runner by revalidating the repo-global database symlink on every invocation and executing evaluation-time file-IO calls inside the upstream `evaluation/` directory context.
- `rationale`: The LangGraph benchmark failure after roughly 148 completed queries was not a model-quality issue but an integration fault: upstream OSU evaluation code opens `../database/...` paths relative to `evaluation/`, while the bridge subprocess was only importing from that directory and was also vulnerable to a stale symlink left behind by prior temp runs. Repairing both the symlink lifecycle and the runtime cwd removes a class of late-run crashes that can waste hours and invalidate otherwise successful query outputs.
- `alternatives_rejected`: Keep the stale-link check best-effort only, patch each upstream module individually, or accept the late failure as an unavoidable external-benchmark limitation.
- `linked_adr`: `N/A (vendored evaluator integration rule)`

## 2026-04-10 (Artifact-Only Benchmark Status Reads)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Use artifact-only inspection (`run_registry.csv`, `official_eval.json`, query file counts/mtimes) as the default way to answer progress questions on active TravelPlanner studies instead of interacting with the notebook kernel or benchmark subprocess.
- `rationale`: The user often needs reassurance or provisional numbers while a multi-hour Docker benchmark is still running. Reading persisted study artifacts provides accurate status and partial results without risking notebook interruption, TTY side effects, or accidental reruns.
- `alternatives_rejected`: Attach to the running container interactively, inspect notebook cell state only, or infer progress solely from provider dashboards.
- `linked_adr`: `N/A (safe benchmark observability rule)`

## 2026-04-11 (Scientific Baseline Intermediate Fallbacks)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Make the TravelPlanner `Self-Refine` and `Planner-Executor` scientific baselines recover from truncated intermediate JSON by using compact prompts plus deterministic fallback objects instead of aborting the seed.
- `rationale`: The failed study arms were not collapsing on the final scored itinerary schema but on intermediate reviewer/planner schemas that occasionally returned truncated JSON under the shared Qwen/OpenRouter setup. Treating those intermediate artifacts as recoverable preserves the intent of the baseline while turning a benchmark-stopping parse error into a lower-risk local repair path.
- `alternatives_rejected`: Increase token budgets globally, accept those baselines as permanently invalid, or hand-edit partial outputs after the fact.
- `linked_adr`: `N/A (scientific baseline robustness rule)`

## 2026-04-12 (Executable Scientific Plan Gate)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Treat benchmark-improvement plans as approved only after checking that every major task maps to current code extension points, existing runner behavior, and the actual domain representation used by the adapter.
- `rationale`: The revised V5.1 plan is much closer to scientifically sound execution, but review against the live code still surfaced hidden implementation constraints: TravelPlanner currently stores a scalar `dest`, the agent layer does not yet expose an adapter-provided heuristic hook, and the benchmark runner already checkpoints per query. Requiring an executability gate avoids launching long campaigns from plans that are directionally right but still underspecified at the implementation boundary.
- `alternatives_rejected`: Approve plans based on methodology text alone, defer all feasibility checks until implementation starts, or keep tuning and redesign work mixed inside one loosely specified execution plan.
- `linked_adr`: `N/A (scientific plan review rule)`

## 2026-04-12 (Official Scorer Denominator Rule)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Treat missing query outputs in TravelPlanner benchmark runs as full-denominator failures unless the official scorer is explicitly restricted to a subset index range.
- `rationale`: The continue-on-error runner can preserve a seed and write per-query failure artifacts, but the current official scorer iterates across the requested query range and evaluates missing predictions as empty plans. Labeling such outputs as a "partial official score" would blur the denominator and weaken the scientific interpretation of delivery and final-pass rates.
- `alternatives_rejected`: Describe full-range scores with missing predictions as subset scores, hide failed-query counts behind aggregate metrics, or stop the entire seed on first failed query to preserve terminology.
- `linked_adr`: `N/A (scorer semantics rule)`

## 2026-04-12 (Plan Acceptance Criteria Must Match Scorer Semantics)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: When updating benchmark plans, rewrite acceptance criteria to match the actual official scorer behavior even if the underlying implementation idea is already correct.
- `rationale`: The V5.1 T5 design was directionally right, but one sentence still implied subset official evaluation. Tightening that wording preserves methodological clarity without changing the technical plan and prevents later thesis text from overstating what a continue-on-error run means.
- `alternatives_rejected`: Leave the ambiguous wording in place, rely on oral clarification later, or postpone the correction until ADR drafting.
- `linked_adr`: `N/A (plan wording precision rule)`

## 2026-04-12 (TravelPlanner T0 Multi-City Adapter Shape)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Implement V5.1 T0 entirely inside `adapters/travelplanner/` by inferring `city_sequence` in the workspace, expanding the adapter DAG into per-city and per-leg markers, and teaching the planning toolchain to consume dynamic search keys by prefix while keeping single-city keys backward compatible.
- `rationale`: The root bottleneck was not the core stigmergic runtime but the TravelPlanner adapter's single-scalar destination encoding. Keeping the redesign local to the adapter layer fixes the domain representation gap, preserves `core/` invariants, and avoids breaking existing single-city flows or tests that still expect legacy search keys.
- `alternatives_rejected`: Parse `dest` as a list directly, move domain-specific sequencing into `core/`, or replace all legacy search keys with multi-city-only names in one breaking sweep.
- `linked_adr`: `N/A (adapter-local multi-city routing rule)`
