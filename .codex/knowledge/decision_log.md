# Decision Log

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
