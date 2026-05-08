# Project Playbook

## Repo
- `repo_slug`: `stigmergiagentic-33b989`

## Active Practices

### V12 Autonomous-Agent Stigmergy Standard
- Implement active V12 work under `core_v12/`; reuse V10/V11 verifier, event-log, guarded-edit, and migration-context primitives only as substrate.
- Keep the medium guidance-only: it may expose pheromones, supported tools/actions, inhibited tools/actions, hot files, and feedback history, but it must never create patches or tool parameters.
- Keep proposal tools non-mutating and target-aware; a tool whose advice depends on Java target version must reject missing migration context rather than defaulting to Java 17.
- Compare S2 and V12 with identical tool registries, budgets, models, instances, and verifier contracts so any measured gain is attributable to the stigmergic local view.
- Treat V11/B6 deterministic operators as archived baseline/diagnostic code and keep them out of the active V12 agent loop.

### External Agent Repo Thesis-Triage Standard
- Classify a third-party agent repo as related work, thesis artifact tooling, or an experimental baseline before integrating it into the narrative.
- Treat domain-specific multi-agent pipelines as comparison context, not stigmergic evidence, unless they expose replayable shared-medium causality and ablation-ready telemetry.
- For thesis diagrams, use generative figure tools as draft accelerators and verify/redraw final figures when arrows, labels, or causal mechanisms carry the argument.
- Keep full third-party figure generators in a documentation-local workspace with ignored vendor code, tracked setup scripts, and no secrets in generated config.
- For FranceStudent-backed PaperBanana runs, prefer `IMAGEN`, use text-only string payloads for `/responses`, and force `gpt-image-2` to `1024x1024`.
- When replacing an existing thesis figure, score generated alternatives on two axes: presentation quality and exact semantic/label fidelity.
- For rigid grid figures with precise labels, test direct `gpt-image-2` against PaperBanana before assuming the agentic pipeline is better.
- For stigmergy illustrations, require both environmental write/modification arrows and read/perception arrows from the shared artifact.
- Compare direct-vs-agentic figure generation with a fixed prompt and report wall-clock time; PaperBanana quality claims are weaker when `retrieval_setting=none`.
- Before trusting PaperBanana `auto`, verify `top10_references` is non-empty; if FranceStudent returns 502 on retrieval, reduce the reference pool or avoid claiming retrieval benefits.
- To reuse PaperBanana in another memoir repo, copy only the tracked helper scripts/skill and keep the cloned vendor plus generated records ignored; adapt the target repo's LaTeX image output directory and check API-key presence without copying or printing secrets.

### V11 Causal Medium Standard
- Do not count `signal.emitted` as stigmergic evidence by itself; require at least `signal.read`, worker activation, `decision.influenced`, and `trajectory.diverged` before claiming causal coordination.
- Convert verifier feedback into affordances before selecting workers; a signal should become an actionable gradient, not only prompt context.
- Keep typed operators guarded: prove old spans or insertion anchors exist before emitting a candidate edit, and log operator invocation/application through EventLog.

### Official-In-Loop Repair Standard
- Treat official benchmark rejection as validation feedback while repair budget remains; do not wait until finalization to discover a benchmark-contract failure.
- If local compile/test/class-version pass but official evaluation fails, classify the candidate as a repairable partial and preserve the official log in `raw_output`/metadata.
- Prompts should distinguish test deletion from test-summary parsing failures when a benchmark reports sentinel values such as `#tests=-2`.
- Stigmergic digest injection is a signal application: when prior signals are attached to a repair prompt, record `signal.applied` and include a compact digest that the provider actually reads.

### External Review Handoff Standard
- Give external reviewers a falsification-oriented prompt that asks for architecture risks, metric validity, benchmark comparability, telemetry integrity, and thesis narrative gaps.
- Distinguish GitHub-visible evidence from local-only artifacts: `documentation/` and tracked `output/` files are shareable through GitHub, while ignored `campaign_results/` runs must be summarized, uploaded, or copied explicitly.
- Never present a currently running or manifest-only campaign as final evidence; label it as in-progress and direct review toward completed, versioned summaries.
- For memoir/thesis review, include `documentation/memoire/latex/main.tex`, chapter sources, annexes, bibliography, and planning Markdown so reviewers can test whether the manuscript's claims match the implementation evidence.
- When raw campaign review is needed, use allowlisted `campaign_results/` exceptions plus a local README; do not unignore legacy campaign trees with large SQLite/audit artifacts or active retry runs.
- When pushing a handoff branch for GPT/GitHub review, stage code, tests, docs, memoir sources, and repo-local skills first; leave generated campaign outputs and local workspaces unstaged unless the user explicitly asks to publish them.

### V10 Branching Runtime Standard
- Keep branching lineage and workspace lineage identical: every repair candidate with a parent must be applied from the parent hypothesis workspace.
- Reject duplicate hypothesis IDs in a run instead of reusing nodes, because duplicate IDs corrupt parentage, validation history, and selection.
- Build blackboards as reconstructible projections from EventLog plus graph state; when possible, support event-only reconstruction for crash/replay cases.
- Finalize validated candidates by verifier score order and continue to the next validated candidate if artifact contract or adapter score fails.

### V10 Bootstrap Runtime Standard
- Build new runtime foundations in `core_v10/` and `adapters_v10/` with explicit import-boundary tests so legacy `core/` and benchmark adapters cannot leak into the new architecture.
- Treat `apply -> validate -> finalize` workspace continuity as a hard invariant; if apply returns a branch/sandbox workspace, all downstream verifier actions must use that workspace.
- Keep early EventLog and artifact contracts mechanical and testable: append under a file lock, replay from JSONL, reject empty required artifacts, and compute logged strict success from both adapter score and artifact contract.
- Reset hypothesis graphs per run unless a future strategy explicitly models cross-run state through a versioned memory layer.

### From-Scratch Framework Pivot Standard
- For major pivots after an empirically failed architecture, create a new core namespace and archive the old runtime before optimizing or cleaning it.
- Make append-only events and explicit hypothesis graphs the first-class truth layers; treat blackboards, dashboards, and active signals as reconstructible projections.
- Place domain-specific verifiers behind adapter contracts, and keep strict success impossible without a verifier-backed artifact contract.
- In ablation ladders, test the core thesis mechanism before adding generic search optimizers or memory systems that can mask attribution.

### V10 Verified-Resolution Runtime Planning Standard
- Rebuild agent frameworks around stable adapter contracts, event logs, hypothesis graphs, and replayable artifact contracts before adding new agent roles or memory.
- Define the stigmergic mechanism as indirect coordination through shared, inspectable traces with reinforcement, inhibition, novelty, and validation signals; do not use agent count as the evidence of colony behavior.
- Require an ablation ladder where each added mechanism can be removed independently and measured against a strong workflow-first baseline.

### MigrationBench Strict-Success Contract Standard
- Treat `strict_success` as unreachable unless a candidate has one concrete exported `patch.diff`, a successful fresh `git apply` check, and an official evaluator result in the same output contract.
- Best-partial fallbacks must execute the same finalization/evaluation path as normal selected patches; marker payload synthesis alone is telemetry, not benchmark delivery.
- Target repair retries at the root patch hypothesis when the current marker is itself a repair marker, and strip repair bookkeeping from newly generated branch payloads.

### MigrationBench Repair-Colony Hardening Standard
- Normalize model edit outputs (`file`, `content`, `replace`, `old/new`) into a strict typed edit contract before any workspace mutation; never ask the LLM for unified diffs as the primary artifact.
- Make official-like validation explicit and auditable before final selection: patch applies, Maven verify, exact Java target class versions, and non-regressed test count when known.
- Use smoke gates for mechanics, not scientific success: require clean telemetry, one objective per marker DB, schema-error recovery, selected/finalize paths, and bounded feedback digests before rerunning `main_30`.

### MigrationBench Handoff Review Standard
- Block MigrationBench implementation on an official evaluator preflight over a tiny requested subset before adding prompt optimization, V7 controls, or C3 mechanisms.
- Keep the instance schema, patch artifact contract, and denominator semantics identical across baselines and stigmergic arms; `requested_instances` is the scientific denominator, not parsed output count.
- Treat patch workspace isolation as part of evaluation validity: each instance/arm/run needs a clean checkout, deterministic base commit, captured diff, apply check, and typed failure if any step is missing.
- After revising a handoff, normalize stale master-plan references to the chosen schema/model/arm names before implementation starts.

### Thesis Framework Documentation Standard
- Start framework documentation with the runtime signal flow and coordination philosophy before module inventory; in this repo the anchor model is `markers -> pressure -> lock -> tool -> deposited markers`.
- Separate memory/adaptation layers explicitly: agent episodic memory is in-run and local, `lesson` markers are in-run stigmergic artifacts, `skill` markers are cross-run artifacts, and `coordination_protocol` markers adapt runtime configuration.
- Include operational diagnostics beside architecture: summary JSON, `markers.db`, `audit_log.jsonl`, `skills.db`, and `protocols.db` are the minimum artifacts a reader needs to verify a run.

### Stigmergic Self-Optimization Design Standard
- Persist self-improvement as medium-level artifacts (`skill`, `coordination_protocol`, similar markers) instead of manual specialist templates whenever the goal is to preserve role-free stigmergic philosophy.
- Split `adaptation` and `evaluation` into separate configs or run modes when persistent memory or cross-run feedback is enabled.
- Frame automatic generation claims at the right abstraction level: protocol generation over a fixed substrate is often defensible where full system generation is not.

### Sprint 9 Groundwork Standard
- When introducing cross-run stigmergic learning, land the contract layer first: config keys, schemas, prompts, adapter/runtime seams, and fallback paths before wiring persistence.
- Keep every Sprint 9 surface opt-in by default so Sprint 8 benchmark behavior remains reproducible while new capabilities are developed behind explicit flags.
- If a new prompt/schema path only needs lightweight utilities, avoid package-level imports that pull the full LLM client stack; use lazy exports to keep targeted tests and local tooling responsive.

### Sprint 9 Completion Standard
- Use separate `MarkerStore` instances with `session_isolation=False` for cross-run artifacts (`skills.db`, `protocols.db`) instead of mixing scopes in the session-isolated run store.
- Enforce immutable `baseline` protocol slots so clamped adaptations always have a stable reference point.
- Place promotion side-effects in `Environment.apply_action_result()` rather than in agents to keep the policy global and role-free.

### Sprint 9 Campaign Readout Standard
- Verify `skills.db`, `protocols.db`, `skills_promoted`, and `coordination_protocol_applied` before claiming C2/C3 evidence from a campaign.
- Report `official_delivery_rate` separately from any nested artifact `delivered` flag; no-plan idle rows must not count as delivered just because a compatibility field says true.
- Split TravelPlanner C3 failures into `no-plan idle` vs `invalid emitted plan` before choosing improvements, because they map to different levers: decomposition/continuation vs validator-guided cost repair.

### TravelPlanner Train/Eval Hygiene Standard
- Use the published TravelPlanner `train` split for adaptation whenever artifacts are persisted into `skills.db` or `protocols.db`; do not adapt on one slice of validation and evaluate on another slice as the final thesis protocol.
- Evaluate final comparison tables on the full 180-query validation split when cost permits, because this aligns with SwarmAgentic, official TravelPlanner reporting, and prior V6_C evidence.
- Treat `cross_run` as orthogonal to split hygiene: it controls protocol reuse across runs, while adapt-to-eval contamination is governed by which split produced the persisted artifacts.

### Final Campaign Implementation Standard
- Change campaign split defaults in scripts, Docker Compose, and YAML presets together; also clean per-query output folders by default when the query denominator changes.
- Keep C3 evaluation stores read-only, but ensure the adapt phase actually writes train-only `skills.db` and `protocols.db` before treating the campaign as Sprint 9 evidence.
- Export both artifact-level and official-level delivery metrics whenever legacy fields can overstate delivery.

### Cross-Run Adaptation Evaluation Standard
- Never enable persistent agent memory or cross-run emergence feedback in the main benchmark-evaluation preset unless the protocol explicitly separates adaptation/training runs from frozen held-out evaluation runs.
- When proposing objective-based specialization, verify that the seeded signal matches the runtime’s real decision features; in the current codebase `AgentAffinityProfile` acts on `marker_type` and target semantics, not directly on action names.
- Prefer bounded protocol adaptation over manual role templates when the thesis claim concerns stigmergic self-organization; otherwise the implementation quietly shifts toward hand-designed specialization.

### Anti-Stagnation Outcome Readout Standard
- After any anti-stagnation or recovery-controller experiment, report the trio `{idle stop rate, all_terminal pass rate, final_pass_given_delivery}` before interpreting the aggregate pass-rate delta.
- If failures move from `idle_cycles` to `all_terminal` without proportional pass gains, treat the new frontier as `repair quality` rather than `search continuation`.
- In TravelPlanner stigmergic runs, use `action_switching_rate`, `parallel_utilization`, and `coordination_overhead` as the primary indicators of coordination quality; higher collaboration density alone is not evidence of better emergence.

### Benchmark-Freeze Planning Standard
- Before proposing a new benchmark-driven improvement cycle, freeze the scorer, benchmark runner semantics, validation split, and comparison baseline in the plan itself.
- Separate `framework-general` workstreams from `adapter-specific` workstreams explicitly; otherwise review feedback will correctly question whether gains come from the system or from task-fitting.
- Require an ablation ladder from the frozen baseline for every major improvement plan so the eventual article can attribute gains causally.

### Query-Type Failure-Regime Readout Standard
- For TravelPlanner benchmark analysis, stratify results at least by `(days, visiting_city_number, level)` before interpreting emergence, because `3/1`, `5/2`, and `7/3` queries fail through different mechanisms.
- Treat `3-day / 1-city` hard-query failures as `constraint-repair` problems when plans are still delivered, but treat `5-day / 2-city` and `7-day / 3-city` empty-plan + `idle_cycles` patterns as `search/decomposition` problems.
- Check explicit constraint families separately: `no self-driving`, `private room`, `pets`, and `4 cuisines` are useful stress buckets because they expose planner weaknesses that are not visible in aggregate pass rate alone.

### Emergence-First Validation Readout Standard
- When a benchmark export already contains `summary.emergence`, analyze emergence directly from `runs.json` before adding any new logging or instrumentation.
- Prioritize `pressure_entropy`, `parallel_utilization`, `convergence_tick`, and `action_switching_rate` in post-hoc readouts; in the current TravelPlanner V5-full preset these metrics explain pass/fail separation better than raw collaboration density alone.
- Read `idle_cycles` together with emergence: a late `convergence_tick` plus weak `parallel_utilization` is a stagnation signature, not productive exploration.

### Scientific Baseline Transport-Fallback Standard
- When a scientific baseline already relies on the shared `LLMClient` retries, add any extra resilience at the baseline node boundary rather than forking provider logic into the client.
- For Self-Refine, allow `critic` to fall back to compact validator feedback and allow `reviser` to fall back to the last successful draft when provider calls fail after retries.
- If the initial `draft` still cannot be produced, return a scorer-compatible empty-plan payload with explicit step-trace fallback instead of crashing the whole seed.

### Query-Level Failure Taxonomy Standard
- Persist TravelPlanner operational failure causes on markers themselves (`failure_reason`, `last_failure_reason`, `failure_history`) so adapters can recover per-query outcomes after the run without core-runtime changes.
- Promote adapter-level `failure_reason` to the top level of single-query benchmark artifacts (`query_XXX.json` / `runs.json`) instead of forcing post-hoc reconstruction from empty plans and stop reasons alone.
- Treat `non-empty plan evaluated normally` as `ok` in runtime taxonomy even when the official scorer returns `final_pass=false`; reserve failure labels for workflow or synthesis breakdowns.

### Pure V4 Ablation Preset Standard
- Keep the TravelPlanner V4-only ablation preset in a dedicated config file that flips only the five V4 gates (`local_sensing`, `time_decay`, `frequentation`, `emergent_resolution`, `feedback_loop`).
- Preserve `alpha`, `beta`, `selection_temperature`, `num_agents`, `max_ticks`, and `session_isolation` when preparing a pure correction-only preset.
- Validate the preset at config-load level and treat live LLM smoke runs as optional environment-dependent confirmation, not as the only correctness check.

### Scientific-Plan Sanity Check Standard
- Before executing a benchmark-improvement plan, check every proposed task against the current repo state so the plan does not duplicate already-implemented runtime fields, retries, or exports.
- Separate `ablation`, `stability fixes`, and `performance optimization` into distinct experiment tracks; combining them in one preset weakens causal interpretation.
- If the dominant benchmark failure is an adapter representation bottleneck, schedule adapter redesign ahead of pressure heuristics, prompt enrichment, or agent-count scaling.

### TravelPlanner Failure-Regime Analysis Standard
- Segment TravelPlanner results first by `(days, visiting_city_number)` and by `plan empty vs non-empty` before interpreting aggregate pass rates; this distinguishes synthesis collapse from constraint-level quality loss.
- If `dest` is the only city bound into search markers, fallback payload injection, and routing context, classify the adapter as single-destination and expect structural failure on state-level multi-city queries until routing is upgraded.
- Surface `empty_plan_after_max_attempts` and related planner-terminal reasons in exported `query_XXX.json` summaries; a `status=ok` wrapper around `final_plan=[]` is not scientifically diagnostic.

### Structured Output Resilience Standard
- In benchmark graphs, treat malformed JSON as a separate failure class from network/provider transport errors and retry schema parsing explicitly.
- Remove explanatory fields from intermediate node contracts unless they are directly analyzed downstream; compact outputs reduce truncation risk on hosted models.
- Add deterministic fallbacks for non-terminal orchestration nodes so one malformed structured response degrades quality locally instead of killing the whole benchmark batch.

### Live Notebook Command Standard
- In Jupyter benchmark notebooks, stream stdout/stderr live for long-running commands such as `docker compose build` and containerized batch runs; buffered capture makes healthy progress look like a hang.
- Cache Docker image rebuild decisions on dependency-level inputs when the repo source is volume-mounted into the runtime container.
- Fail early with a clear environment message when a required CLI like Docker is missing from the notebook kernel PATH.

### Reproducible Baseline Replacement Standard
- If a third-party benchmark baseline cannot be run reproducibly under the thesis protocol, replace it in the principal table with an in-repo baseline that preserves the controlled dimensions (`backbone`, `split`, `official scorer`, `output contract`).
- Implement the replacement baseline behind the same `runs.json -> official_eval.json` pipeline as the existing methods so comparison tooling and notebooks stay unchanged downstream.
- For benchmark-domain baselines, reuse existing domain prompt, normalization, and evaluator helpers instead of creating a second scoring dialect.

### Environment-First Guardrail Enforcement
- Keep governance rules in `environment/guardrails.py` so every writer path is mediated by one policy layer.
- Enforce lock ownership with status metadata (`lock_owner`, `lock_acquired_tick`) for scope safety.
- Apply TTL release before normal processing to avoid zombie `in_progress` states.

### Artifact Traceability Standard
- Treat `tasks.json`, `status.json`, `quality.json` as current state only.
- Record all mutations as append-only events in `pheromones/audit_log.jsonl`.
- Include agent signature and timestamp on every write/update path.

### Runtime Reproducibility Standard
- Bootstrap with `uv` and pinned Python 3.11.
- Use `uv run` for all python/test commands.
- Keep dependency source of truth in `requirements.txt` for current sprint.

### Agent Handoff Validation Standard
- Validate each specialized agent in isolation before enabling chained handoffs.
- Use pheromone state transitions as the single integration contract across agents.
- Keep one optional `live_api` smoke test separate from blocking acceptance to preserve deterministic local runs.

### Adaptive Fallback Quality Standard
- Run fallback in two phases: compile/import baseline first, then global pytest classification.
- Classify runtime/import failures into `related` vs `inconclusive`; reserve hard failures for syntax and migration-related import regressions.
- Keep confidence mapping explicit in config (`compile_import_fail`, `related_regression`, `pass_or_inconclusive`) and align validator thresholds against it.

### Docker Mountpoint Reliability Standard
- Treat mounted working directories as persistent mountpoints: clear contents, not mount roots.
- For git URL sources on mounted targets, clone into a temp path then copy into the mountpoint.
- Use a named Docker volume for high-churn target repositories to avoid host bind-mount deadlocks on macOS.

### Cost-Aware LLM Budgeting Standard
- Keep `max_response_tokens <= 0` to avoid hard truncation on reasoning-heavy tasks.
- Use `max_tokens_total` as deterministic safety ceiling and `max_budget_usd` as optional spend ceiling.
- Read `usage.cost` when available; fallback to pricing-based token estimation for pre-call checks and cost continuity.

### No-Output-Cap Runtime Policy
- Never send `max_tokens` in LLM chat completion payloads for migration runs.
- Treat `llm.max_response_tokens` as deprecated/ignored to prevent accidental regressions from config changes.
- Rebuild Docker runtime image before gate runs after any LLM client policy change.

### Sprint Closure Audit Standard
- Mark sprint status explicitly as `tooling complete` only after targeted + full pytest passes.
- Mark sprint status as `evidence complete` only after protocol checks pass (fairness constraints, repeated runs, reproducible artifacts).
- Validate quality gates (`ruff`, `black --check`, `mypy`) separately from functional tests so debt is visible and not masked by green pytest results.
- For Pareto analysis, verify multi-baseline input coverage before interpretation (`>=1 summary per baseline`, and thesis runs should use `>=5` runs per mode).

### Pareto Evidence Integrity Standard
- Export and persist both raw run points and baseline aggregates in the same summary payload.
- Fail analysis commands when expected baselines are missing instead of silently plotting partial data.
- Distinguish bounded benchmark snapshots from unconstrained thesis campaigns in documentation headers and regeneration commands.

### Benchmark Runtime Stability Standard
- Configure explicit provider request timeouts in `LLMClient` (`llm.request_timeout_seconds`) for long multi-run campaigns.
- Cap sequential per-stage actions per tick (`loop.sequential_stage_action_cap`) to avoid unbounded `while stage_runner.run()` cycles.
- Re-run focused baseline/LLM unit tests after stability guardrail changes before restarting benchmark batches.

### Parallel Benchmark Isolation Standard
- Run concurrent benchmark processes from isolated temporary workspace copies to prevent shared-state interference.
- Share only the final `--output-dir`; keep runtime working artifacts (`target_repo`, `pheromones`, temporary clone paths) local to each worker.
- Track campaign completeness by counting `summary` files per baseline and only then generate aggregate analytics.

### Multi-Provider LLM Wiring Standard
- Route provider differences (`env var`, `base_url`, pricing support) through `LLMClient` initialization, not agent code paths.
- Keep one explicit provider selector in config (`llm.provider`) and allow `llm.base_url` override for endpoint variants (for example coding-plan vs general endpoint).
- Run a live smoke check immediately after provider/model switch before launching long benchmark or migration jobs.

### Rate-Limit Resilience Standard
- Add a minimum inter-call interval in the shared LLM client for burst control during iterative loops.
- Apply a dedicated backoff floor for HTTP 429 and merge with provider-provided `Retry-After` when available.
- Add retry jitter to avoid synchronized retry spikes in repeated benchmark batches.
- Tune defaults per provider: keep pacing disabled (`0`) when throughput is priority and provider stability allows it.

### Opt-In Stigmergic Adaptivity Standard
- Introduce theory-alignment runtime changes behind explicit config flags first, and prove backward compatibility with a full unchanged test sweep before enabling anything by default.
- Keep temporal semantics on a dedicated activity timestamp (`last_active_at`) instead of reusing generic mutation timestamps when system maintenance also writes to the same rows.
- Wire perception-side telemetry at the orchestrator boundary so agents stay role-free while the environment/store can still reuse read traces for later reinforcement.

### Curated Run-Set Standard
- If execution control changes mid-batch (interrupt/restart), preserve raw outputs but build a curated directory for the exact requested sample.
- Include only complete triplets (`manifest`, `summary`, `ticks`) per selected run id in curated sets.
- Generate benchmark plots/JSON from curated sets to keep reported `n` aligned with user intent.

### V2 Core Reset Baseline Standard
- During redesign pivots, enforce a branch-level hard reset of obsolete runtime modules before implementing new core primitives.
- Use a transaction-first store contract (`SQLite WAL` + explicit immediate transactions) for stigmergic markers to avoid partial updates under contention.
- Require append-only audit with `before/after` mutation payloads as part of every state write path.

### Per-Sprint Artifact-State Documentation Standard
- At every sprint closure, write/update `documentation/redisgn_v2/sprint_XX_artifact.md`.
- Keep sections fixed: scope, behavior, interfaces, guardrails, limits, validation evidence.
- Mirror the rule in both agent instruction files to keep future contributors aligned.

### Sprint 2 Runtime Contract Standard
- Model orchestration as `snapshot -> decision -> lock -> execute -> deposit -> maintain` to keep coordination medium explicit and testable.
- Keep tool APIs narrow (`is_eligible`, async `execute`) and treat environment as the single mutation gate for store writes and guardrails.
- For concurrency tests, use one minimal mock adapter with staged marker transitions to validate lock arbitration and stop reasons without domain noise.

### Assistant Tool-Layer Standard
- Register infrastructure actions through one helper (`register_infrastructure_tools`) to keep adapter wiring explicit and consistent.
- Keep tool payload contracts structured (for example `write.mode/path/content`) and validate early to make failures traceable in marker metadata.
- Treat optional external providers (`web_search`) as explicit no-op defaults in local/dev mode to preserve deterministic baseline behavior.

### Assistant Eligibility and Response Standard
- Keep `eligible_actions` as an optional allowlist; if absent, infer eligibility from marker payload prerequisites to preserve flexibility without blind tool execution.
- Restrict `decompose` by marker context (`not decomposed` and `no parent_id`) so decomposition happens once at root unless explicitly overridden.
- Synthesize CLI assistant output from concrete execution payloads (`last_read`, `last_bash`, `last_write`, `last_search`) and include `last_thought` as complementary context.

### Think-Then-Act Progression Standard
- Treat `active` subtasks as execution-only by default: planner tools should not advance active work items without concrete artifact/tool outputs.
- Keep a narrow root-marker exception path after decomposition so orchestration metadata markers can still converge to terminal states.
- Ensure CLI entrypoints load `.env` proactively so provider keys are consistent between notebook and terminal runs.

### Emergent Decomposition and Hinting Standard
- Do not inject default `subtask_count` during objective or seed-marker creation; only propagate it when explicitly provided by input.
- Build planner JSON schemas from available tool capabilities and include optional fields only for registered/declared execution tools.
- Avoid local heuristic fallback hints in `think`; if the model does not emit structured hints, keep marker active and let subsequent ticks/agents resolve execution.
- Read all intensity decrements/floors from `markers.*` config keys (`intensity_step_think`, `intensity_step_tool`, `intensity_step_decompose`, `child_intensity_offset`, `intensity_floor`).

### V3 Structured-Async Runtime Standard
- Add schema-backed `acall(..., response_schema=...)` at the LLM boundary and keep typed parsing close to tool execution (`think`, `decompose`) for deterministic downstream behavior.
- Enforce dependency readiness in agent candidate filtering (`unblocked_markers`) so orchestration order is controlled by marker graph state, not agent timing.
- Isolate runtime sessions at storage level and surface `session_id` in CLI/output summaries to keep experiments traceable and collision-free.

### Cognitive-Emergence Runtime Standard
- Keep agent episodic memory local and bounded (`capacity`, `decay_rate`) and pass recalled context through `Decision` payload fields instead of adding DB/schema coupling.
- Compute emergence metrics from `TickRow` aggregates and audit events at run end; avoid embedding metric state in marker persistence paths.
- Materialize high-quality reusable knowledge as `lesson` markers with low decay to bridge short-term memory and long-term stigmergic coordination.

### Domain Adapter Vertical-Slice Standard
- Implement domain adapters as a strict vertical slice: `workspace` (data access), `tools` (stateful actions), `adapter` (DAG/state machine wiring), `evaluator` (metrics), and adapter-specific config.
- Keep planner output structured with schema validation and always include a deterministic fallback path to avoid LLM-format deadlocks.
- For benchmark domains, define evaluation metrics as first-class outputs in adapter `evaluate_run` so CLI summaries remain comparable across runs.

### Three-Layer Thesis Audit Standard
- Evaluate thesis readiness across three distinct layers: `review/theory`, `plan/roadmap`, and `repo/runtime evidence`.
- Do not count legacy or removed artifacts as proof for the current runtime unless the same capability is revalidated in V3 code/tests/docs.
- Mark config flags, planned metrics, and placeholder states as non-capabilities until they are surfaced by runtime behavior, exported outputs, or explicit tests.

### Colab vLLM Notebook Standard
- Split Colab benchmark notebooks into `install -> runtime restart -> execution` phases whenever `torch` or `vllm` is upgraded.
- On Tesla T4, start with auto-detected AWQ loading and conservative memory parameters (`max_model_len <= 4096`, `max_num_seqs = 1`) before forcing backend or quantization-specific flags.
- Write vLLM server output to a log file and show the log tail on startup timeout so notebook debugging reveals the actual initialization error.

### Colab Repo-Benchmark Standard
- For Colab notebooks that run repository CLIs, write a temporary local config override instead of mutating checked-in YAML defaults.
- Resume benchmark loops from a JSON checkpoint and persist it after every expensive query-sized unit of work.
- When a hosted-provider client is redirected to a local OpenAI-compatible server, inject the expected provider API key as a harmless dummy value in the notebook environment.

### Local Benchmark Feasibility Notebook Standard
- Make the notebook answer a benchmark decision, not only a startup question, by using explicit `GO`, `CONDITIONAL GO`, and `NO-GO` rules.
- Split evaluation into `minimal viability` and `repeated stability` so one successful call is never treated as benchmark credibility.
- Export provenance, failure events, and thesis-use interpretation in the same JSON summary as latency and JSON-validity metrics.

### External CLI Drift Standard
- When official docs and the installed CLI disagree on command names or flags, treat local `--help` output as the operational source of truth and the docs as conceptual guidance.
- Encode the drift explicitly in the skill or runbook so later turns do not fall back to deprecated examples.
- If a required capability exists in the product docs but not in the installed CLI, use the provider console or API instead of inventing unsupported flags.

### Repo-Local Infra Skill Standard
- Keep infrastructure `SKILL.md` files short and task-oriented; move command matrices and repo-specific workflows into `references/`.
- For remote benchmark environments, document durable storage, SSH access, and artifact retrieval separately from ad-hoc transfer commands.

### Research Loop Integration Standard
- Treat external autonomous research repos as orchestration patterns; port the loop into a domain adapter instead of importing repo-specific file assumptions.
- Define one immutable evaluator and one mutable canonical artifact per research run (for example `draft.md`, `evidence.json`, or `literature_map.md`) so keep/discard iteration stays deterministic.
- Extend generic web search with scholarly retrieval and citation validation before using the loop for thesis or literature-review workflows.

### Objective Autoresearch Skill Standard
- For bounded autonomous loops, force every iteration to relock the objective, evaluator, mutable surface, and stop conditions before acting.
- Keep hybrid skills narrow by selecting one primary mode from the final deliverable and treating other activities as support only.
- Encode drift resistance explicitly: immutable evaluator files, one-hypothesis iterations, and a finite reframe-then-stop policy.

### Lightweight Home AGENTS Standard
- Keep the home-level `AGENTS.md` operational and lightweight; avoid long governance prose when one short locality rule is enough.
- Prefer repo-local instructions and skills for repository-specific behavior instead of centralizing too much policy in `~/.codex/AGENTS.md`.
- When simplifying instruction files, preserve the actionable constraint and remove the framing overhead first.

### RunPod Branch-Pinned Pod Workflow Standard
- For remote pod execution, use a pushed Git branch or tag as the only source of truth and never assume the current local working tree should be mirrored to the pod.
- Bootstrap empty pods from a raw GitHub script first, then run subsequent smoke and packaging scripts from the cloned repository.
- Keep remote operations split into `create -> bootstrap -> smoke -> package` scripts so provisioning, runtime validation, and artifact retrieval stay independently repeatable.

### OpenRouter Baseline Cleanup Standard
- Keep one checked-in hosted-provider baseline across `config`, runtime fallback defaults, and test fixtures; experimental model/provider variants belong in temporary overrides, not the default path.
- Surface `llm_provider` and `llm_model` in CLI JSON summaries and make smoke scripts assert them so baseline drift is visible without reading config files.
- When simplifying a research repo back to a stable execution path, remove notebooks, pod workflows, and session artifacts from the main surface but keep the scorer-backed evaluation bridge that validates outputs.
- For strict JSON generation on OpenRouter reasoning-capable models, pass reasoning controls via `extra_body`, disable reasoning on the stable runtime path when needed, and combine that with an explicit response-token cap.
- Compact benchmark prompts before touching model settings: remove duplicate raw dataset blobs, inject only the needed workspace slices, and keep schema coercion tolerant to `null` string fields from live provider output.

### TravelPlanner Scorer-Alignment Standard
- Align workspace search results with the official evaluator's filtered inventory, not only the raw CSVs, before trusting a candidate to be sandbox-valid.
- For TravelPlanner transport and city fields, give the planner canonical strings to copy verbatim, including `from <origin> to <dest>` route wording and exact flight-number forms when flights are selected.
- Feed official evaluator failure messages back into replanning alongside constraint names so the next pass can repair the exact field that broke scorer semantics.
- Expose outbound and return route legs as explicit search artifacts, including ground-transport alternatives, when the scorer expects closed-circle itineraries.
- Filter or prioritize hotel candidates by stay length, occupancy, and declared room/house constraints before prompting the model; treat those as task-state constraints, not post-hoc fixes.
- Prompt the planner with an exact day-count contract when the scorer evaluates a fixed number of itinerary rows; extra days can invalidate an otherwise plausible closed-circle plan.
- Before interpreting aggregate TravelPlanner scores, break results down by `(days, visiting_city_number)` to detect regime shifts between single-destination and multi-city planning.
- If delivery is strong only on `3 days / 1 city`, audit the adapter search markers and fallback search payloads for hidden single-destination assumptions (`org <-> dest` only).
- For framework-vs-framework TravelPlanner comparisons, lock provider, routed model, split, and official scorer first; document any remaining uncontrolled training or optimization phases explicitly instead of implying a fully matched benchmark.
- When adapting an external TravelPlanner repo to OpenRouter, patch only model-id/provider compatibility and output normalization, then score both methods through the same local official-eval script.
- Add a solo baseline arm on the exact same routed model whenever comparing orchestration frameworks; otherwise framework gains can be confounded with raw model capability.
- For cross-repo benchmark comparisons, keep method interoperability scripts at the repo edge and convert every method into the same `runs.json -> official_eval.json` pipeline before rendering tables.

### Dockerized Benchmark Smoke Standard
- Treat the containerized smoke path as the only benchmark evidence path once the repo declares Dockerized validation; host-local smokes are debugging aids, not benchmark results.
- Enter Docker at the top-level script boundary and run the rest of the workflow unchanged inside the container so one command remains ergonomic without mixing environments.
- Mount the repository into the smoke service when live benchmark runs must write logs and outputs back to the working tree during iterative development.

### Notebook-Driven Full Benchmark Campaign Standard
- Keep benchmark notebooks as orchestration and analysis surfaces only; execute every expensive benchmark step through the repository's canonical Docker service rather than the host kernel.
- Checkpoint long benchmark campaigns query by query with one per-query JSON plus an aggregate `runs.json` so partial progress survives notebook interruption or kernel restarts.
- Separate generation and official scoring into two Docker steps that share the same mounted output directory; this keeps the final score reproducible while preserving intermediate artifacts for debugging.

### Docker Python Entrypoint Standard
- Any Docker-invoked repository script that may run as `python /app/scripts/<name>.py` should add `REPO_ROOT` to `sys.path` before importing local packages such as `core`, `adapters`, or `llm`.
- Before launching a long benchmark campaign, validate the exact container entrypoint with one `--help` call and one cheap real invocation so import-path bugs surface immediately.
- Treat identical per-query runtime failures as an orchestration-path issue first; inspect the first query log before changing prompts, models, or benchmark settings.

### External Optimizer Resilience Standard
- When adapting third-party optimization loops to hosted LLM providers, checkpoint state after each completed iteration before any next-step mutation phase.
- Convert transient provider/runtime failures into per-task degraded outputs and continue the run, instead of letting one failed structured-output call abort the full optimizer batch.
- For notebook reruns against external repos, default to reusing the existing clone and virtualenv, and start with conservative worker counts on smaller routed models.

### Benchmark Review Hygiene Standard
- Before citing a notebook in thesis text, verify that every visible output cell belongs to the same run identifier; if multiple run tags appear, rerender or clear stale outputs first.
- For same-model framework comparisons, report the paired query win/loss count, the official aggregate metrics, and the token/cost delta together so quality gains are not detached from budget.
- If an external baseline needed behavior-changing patches beyond provider/model wiring, label it as a patched variant and scope the claim accordingly instead of presenting it as the untouched upstream method.

### Mode-Based Baseline Benchmark Standard
- For fragile third-party baselines, move benchmark control flow into a dedicated repository script and let the notebook only trigger modes such as `preflight`, `pilot`, and `full`.
- Emit mode-specific `benchmark_status.json`, `reproducibility.md`, and `context.md` artifacts so provider outages, partial checkpoints, and paper-reference numbers remain visible outside notebook cell output.
- If the repository `.venv` is unstable, prefer the healthy interpreter for local benchmark scripts and keep isolated virtualenv usage scoped to the external cloned baseline only.

### Dedicated Baseline Notebook Standard
- If one comparison arm is much more failure-prone than the others, create a baseline-specific notebook that reruns only that arm and reuses existing reference artifacts for the stable arms.
- Store the reference `official_eval.json` and `runs.json` paths as overridable environment-backed defaults so the notebook stays strict by default but portable across future reruns.
- Put the aggregate official table and the paired per-query comparison in the same notebook so a failed rerun cannot silently produce a table without comparative context.

### Notebook Interpreter Selection Standard
- Any notebook that shells out to repo scripts should resolve a concrete interpreter first and verify it can import the notebook's required modules before launching setup/eval commands.
- Prefer the kernel interpreter when it satisfies the imports, but probe fallback interpreters explicitly instead of assuming bare `python` is valid.
- Once selected, reuse that interpreter for all local repository scripts inside the notebook to avoid mixed-environment failures.

### External Baseline Watchdog Standard
- For long-running external baseline processes, emit heartbeat lines on a fixed interval and persist the same state to a file-backed `live_monitor.json` so notebook users and post-mortem debugging share the same truth source.
- Trigger stall recovery from `no child output and no watched-artifact movement` rather than from raw wall-clock alone, then classify the outcome separately from model-quality scores.
- Version local patches applied to external clones and refresh clones automatically when the patch revision changes, so reruns do not silently reuse stale reliability behavior.

### Organization-Philosophy Benchmark Standard
- When the research question targets coordination philosophy, define benchmark arms as organizational forms (`direct`, `CoT`, `self-refine`, `planner-executor`, `graph supervisor`, `stigmergic`) and treat concrete libraries only as implementation backends.
- Run publication-grade studies through an explicit `preflight -> pilot -> full` matrix script that persists one registry row per `stage x arm x seed`, so failures and gating decisions remain auditable outside notebook output.
- Generate a separate scientific pack from persisted `runs.json`, `official_eval.json`, and run summaries, including `mean ± sd` tables, paired canonical-seed statistics, reproducibility notes, and threats-to-validity text.

### Vendored Evaluator Path Safety Standard
- If vendored benchmark code accesses resources through relative paths, guard both module import and runtime evaluation calls with the expected working directory instead of assuming `subprocess cwd` is enough.
- For repo-global symlinks consumed by third-party subprocesses, verify or recreate the target on every invocation so stale temp-directory links cannot poison later long runs.
- Add at least one regression test that intentionally corrupts the vendored evaluator state before calling the bridge, then assert the bridge repairs it and returns a valid score.

### Non-Invasive Benchmark Monitoring Standard
- For active notebook benchmarks, inspect `run_registry.csv`, per-arm `official_eval.json`, and newest query artifact mtimes before reading logs or touching the running kernel.
- Report partial results only for seeds with completed official scoring files; everything else should be labeled explicitly as `in progress`, `partial_success`, or `failed`.
- When a study is multi-seed, avoid saying an arm is "finished" until all intended seeds are complete or invalidated.

### Structured-Output Baseline Recovery Standard
- For multi-step benchmark baselines, allow intermediate structured-output stages to degrade into deterministic local fallbacks when the final scored itinerary can still be produced.
- Keep planner prompts output-minimal by requesting only non-empty day entries and reconstructing omitted defaults in post-processing.
- If a planner blueprint fails to parse, prefer deriving a compact blueprint from a valid fallback itinerary rather than terminating the whole seed.

### Scientific Plan Executability Standard
- Before approving a benchmark-improvement plan, verify that each proposed hook or override matches an actual extension point in the current codebase.
- Separate task-representation fixes from optimization work; if the adapter encodes the domain too narrowly, repair that representation before prompts, heuristics, or hyperparameter tuning.
- When a runner already persists per-query artifacts, robustness improvements should add failure classification and resume semantics rather than a second parallel checkpoint mechanism.

### Partial-Scoring Semantics Standard
- For continue-on-error benchmark plans, verify whether the official scorer treats missing predictions as absent examples, subset evaluation, or empty failed outputs under the full denominator.
- Do not call an official score "partial" unless the scorer is actually restricted to a reduced query index set.
- Pair resilience-oriented runner summaries with scorer semantics explicitly, so `failed_queries` counts and official rates cannot be misread as different denominators.

### Research Plan Wording Precision Standard
- When a plan changes benchmark resilience behavior, update the acceptance criteria language to reflect the scorer's true denominator semantics.
- Use `documented failures under full evaluation` rather than `partial official score` when missing predictions are still counted over the full query range.
- Prefer small wording corrections early in plan review, because ambiguous measurement language can propagate into ADRs, notebooks, and thesis text.

### TravelPlanner Multi-City Expansion Standard
- Infer TravelPlanner `city_sequence` from local city/state data plus route feasibility, because multi-city queries often store a state-like `dest` rather than an ordered list of cities.
- Keep single-city result keys stable, but make prompt-building and payload-compaction logic accept dynamic `search_<type>_<city-or-leg>` keys by prefix so adapter growth does not force a full downstream rewrite.
- Encode multi-city routing as alternating route and city-search dependencies, which keeps the execution graph explicit, testable, and fully contained inside `adapters/travelplanner/`.

### Batch Benchmark Continue-on-Error Standard
- When one query export can fail without invalidating the whole benchmark seed, persist a failed per-query artifact with `query_idx`, empty-plan outputs, and a machine-readable `failure_reason` instead of aborting the batch.
- Keep `runs.json` complete for the requested query range so downstream official scoring preserves its original denominator semantics while the runner remains resumable.
- Store failure tolerance metadata and scorer semantics directly in `benchmark_summary.json` so campaign resilience cannot be misread as a denominator change or a custom scoring mode.

### Adapter-Local Benchmark Hardening Standard
- When an experiment plan forbids runtime-core edits, implement execution steering through adapter-local marker updates, prompt shaping, and benchmark-script coordination instead of leaking benchmark-specific behavior into generic orchestration code.
- For train-only optimization of a validation-facing preset, run the optimizer against generated temporary configs that flip only the split and tuned scalars, then write back just the winning scalar values to the reusable preset.
- If the scorer supports subset bounds, forward the exact requested index window from the runner so official metrics and requested query ranges stay aligned even when the runner CLI uses inclusive `--start/--end` semantics.

### Framework Plan Executability and Attribution Standard
- Before endorsing a framework-level improvement plan, trace each proposed intervention to the current runtime surfaces so "simple tweaks" do not hide schema or control-plane redesign work.
- If the runtime already adapts exploration, inhibition, or temperature, extend that single feedback mechanism first instead of adding a second overlapping controller in parallel.
- Treat mixed-seed benchmark tables as directional only; promote them to decision-driving evidence only after rerunning the compared configs on the same seed set.

### Short Branching Ablation Standard
- When a roadmap starts turning into a long additive ladder, collapse phase 1 into a shared baseline plus a small number of branching arms so attribution stays readable.
- Put lightweight control-plane improvements in the first ablation wave, and defer representation-contract redesigns to a second scoped plan.
- Allow confirmatory combination runs only after one or more individual branches have already shown a clear positive signal.

### Opt-In Runtime Control-Plane Standard
- When a benchmark baseline must stay frozen, ship new runtime steering mechanisms behind explicit config gates and new ablation presets rather than mutating the incumbent reference preset.
- Measure contention from explicit lock-attempt events, then inject the aggregated signal back into snapshots so both controllers and agents consume the same source of truth.
- Keep generic targeted repair split across two layers: adapters generate validation feedback and target choice, while the runtime materializes repair markers and execution bookkeeping.

### Live Campaign Monitoring Standard
- For sequential multi-framework benchmark scripts, confirm the execution order in the driver script before interpreting empty result folders as failures.
- In `zsh`, prefer null-safe counting (`find`, Python, or `setopt null_glob`) during live monitoring, because unmatched `*.json` globs emit misleading `no matches found` noise.
- When a campaign appears paused, verify active work with `docker stats` and `docker top` before concluding that output counts have stalled.

### Cross-Run Skill Audit Standard
- Audit cross-run memory features end to end: a recalled artifact is only real memory if a downstream tool actually reads it and the success path can credit or refresh it.
- Avoid promoting raw objectives as reusable skills; prefer short normalized heuristics plus optional provenance fields for the original example.
- When grouping skills by fingerprint, keep the canonical text and target independent from the first example-specific lesson, or the stored artifact becomes an arbitrary exemplar instead of a reusable pattern.

### TravelPlanner Artifact-Aware Scoring Standard
- Treat `final_pass` as valid only when paired with a delivered structured itinerary or a non-empty rendered plan; empty-plan evaluator passes must be classified as false positives.
- Publish three separate columns for final campaign analysis: raw evaluator pass, delivered artifact rate, and strict delivered-pass rate.
- If a run summary omits `final_plan`, use `assistant_response == "No travel plan generated."` plus per-query failure reasons as a minimum guard before counting a success.

### Cross-Run Learning Campaign Validity Standard
- Persist or explicitly configure the cross-run namespace used for adapt/eval phases; do not derive it from fields that intentionally differ between train and validation.
- Add a campaign preflight that prints effective `llm.provider`, `llm.model`, `protocol_compiler.enabled`, `skill_library` mode, and expected protocol namespace for every phase before launching Docker services.
- A memory/skill mechanism is not experimentally active until recalled artifacts are injected into the downstream action prompt and their reuse can be credited or penalized by the final artifact outcome.

### C3 Refactor Rerun Standard
- Treat raw evaluator pass, artifact delivery, and strict delivered pass as separate persisted metrics in every TravelPlanner campaign artifact.
- Run C3 ablations through a single Python runner that owns preflight, isolated DB paths, per-query logs, JSON extraction, and manifest generation instead of ad hoc shell loops.
- Promote reusable skills only from strict successful delivered runs, and store them as short action/constraint guidance cards rather than objective fragments.

### Baseline Artifact Validity Standard
- Count completed benchmark queries by parsing valid JSON artifacts, not by counting `query_*.json` files.
- Never redirect per-query stderr to `/dev/null` in a publication-grade campaign; store query logs and classify non-zero exits.
- When legacy folders contain zero-byte query files, repair by rerunning those exact indices or report them explicitly as full-denominator failures.

### C3 Smoke Interpretation Standard
- Treat nonzero token usage as provider-path validation only; require artifact delivery before considering a mechanism healthy.
- If `protocol_compiler.used=true` coincides with very low marker counts and `empty_plan_from_llm`, stop compiler/full-C3 and test V6 clean or non-compiler arms separately.
- Force query indices at the campaign-runner layer so failed compiled runs remain aligned with the requested validation denominator.

### Final Artifact Extraction Standard
- Prefer non-empty delivered artifacts over empty terminal markers when exporting benchmark summaries.
- If `evaluation.query_results` reports delivered strict pass but top-level `final_plan` is empty, treat it as an exporter bug until marker payloads prove otherwise.
- Validate exporter fixes with one real-provider query before rerunning a smoke/full campaign.

### Negative Baseline Interpretation Standard
- When an orchestration framework costs more but only matches a solo baseline, report the result as controlled negative evidence rather than forcing a win narrative.
- Pair aggregate score with paired per-query wins/losses and cost/runtime deltas.
- Preserve delivered-artifact rates separately from strict pass rates to distinguish execution reliability from constraint satisfaction.

### External Code-Migration Benchmark Standard
- Use an official execution-based benchmark as the primary evidence source for code-migration claims; keep toy fixtures for tests and smoke debugging only.
- Include strong anti-agent baselines, especially deterministic migration scripts and agentless self-debug pipelines, before claiming that multi-agent orchestration adds value.
- Pre-register repository subsets, budget limits, output contracts, and full-denominator failure semantics before running publication-grade migration campaigns.

### Management CFP Framing Standard
- Start from the CFP vocabulary, then map repository mechanisms to recognizable constructs such as epistemic practices, organizational memory, exploration/exploitation, and governance.
- Treat the artifact as an illustrative design-science case unless campaign evidence is strong enough to support empirical performance claims.
- Convert technical lifecycle controls such as decay, reinforcement, audit, and locks into learning legitimacy controls: what is remembered, forgotten, attributed, evaluated, and authorized.
- For pre-empirical conceptual abstracts, soften novelty and regulatory claims while keeping the central mechanism concrete and memorable.

### Elastic Colony Runtime Standard
- Preserve hard caps for safety, but expose adaptive stop/continue reasons when evaluating tick-based agent runtimes.
- Size the active agent pool from unblocked work, utilization, contention, and budget pressure rather than choosing one fixed population for every task.
- Introduce dynamic ticks, elastic agents, progressive decomposition, and specialization as separate ablation arms before combining them into a full architecture.

### External AI Research Packet Standard
- When another AI system has repository access, publish a concise documentation-only brief that lists the exact branch, files, diagnosis, research questions, and expected deliverables.
- Prefer committing only the brief and any plan documents it references; avoid bundling unrelated local implementation changes into context-sharing commits.
- Tell the external agent to treat the brief and plan as source-of-truth if older repository files conflict with recent local context.

### External Research Integration Standard
- Integrate external research by converting it into explicit gates, claim boundaries, baseline requirements, or metric changes rather than appending broad prose.
- Keep benchmark-specific claims separate from general framework claims, especially when the benchmark covers one language, ecosystem, or task family.
- Do not let opaque internal scalar scores select or validate self-optimizing mechanisms on the same split used for final evaluation.

### Evaluator-First Agent Architecture Standard
- Design scientific agent systems around the official evaluator, artifact schema, baselines, and campaign runner before introducing adaptive colony mechanisms.
- Keep domain adapters capability-oriented and move scheduling, population, tick budgeting, and decomposition policy into the runtime controller.
- Put cross-run knowledge behind an offline, versioned, split-aware knowledge plane rather than applying learned state implicitly during final evaluation.

### Implementation Handoff Standard
- When a research plan exceeds a few pages, create a separate handoff file with ordered read-list, files to create, mandatory guardrails, and a first-pass definition of done.
- Include explicit "not yet" constraints for mechanisms that are scientifically tempting but would break attribution if implemented too early.
- Define first-pass success as artifact validity, evaluator compatibility, and baseline comparability before optimizing model prompts or adaptive runtime policies.

### Patch Benchmark Campaign Hardening Standard
- Run official evaluator and official reference baselines before local adapter or local baseline claims.
- Make aggregators manifest-driven and synthesize failed rows for missing artifacts so file presence never changes the denominator.
- Generate patches from harness-applied edits, then verify `git apply` on a clean checkout before invoking official evaluation.

### LLM Campaign Monitoring Standard
- If a high-budget campaign intentionally avoids per-instance hard caps, make that choice explicit as `monitor_only` in the manifest rather than leaving limits ambiguous.
- Always record tokens, cost, runtime, LLM calls, repair cycles, last progress time, and manual abort reason so uncapped runs remain comparable across arms.
- Do not use an LLM-as-judge as a hidden automatic stopper; reserve it for post-hoc stagnation classification or optional telemetry.

### Typed Edit Schema Standard
- Prefer JSON edit primitives such as `replace_text` and `write_file` over LLM-generated unified diffs for repository-level patch benchmarks.
- Require repository-relative paths, non-empty search text, and expected replacement counts so edit failures are typed and reproducible.
- Let the harness compute and verify the final patch, and force every baseline/framework arm through the same edit contract.

### MigrationBench Harness Implementation Standard
- Split the implementation into official preflight, one-instance exporter, batch runner, and aggregator so setup mortality, patch generation, and comparison statistics stay independently debuggable.
- Persist `campaign_manifest.json` before running instances and treat it as the denominator source; missing or invalid instance outputs become synthetic failures.
- Keep the official evaluator wrapper conservative: if the patch is empty, inapplicable, or the evaluator is unavailable, strict success is false and the failure reason is explicit.

### Docker Compose Campaign Command Standard
- Use exec-form `command` with a literal block for multi-line campaign commands instead of folded shell strings.
- Escape variables that must be resolved inside the container as `$$VARIABLE` or `$${VARIABLE}`.
- Call `/opt/venv/bin/python` explicitly when login-shell behavior could reset `PATH`.
- Run a zero-limit or no-op smoke after changing service command wiring.

### Official Benchmark Preflight Standard
- Gate environment readiness on clone/checkout success, evaluator importability, evaluator process return code, and required toolchain availability.
- Report base or no-op benchmark success separately when the base artifact is not expected to satisfy the final task contract.
- Include official benchmark Python dependencies and package path configuration in the Docker image before interpreting benchmark failures.

### Docker Desktop Benchmark Smoke Standard
- If Docker bind mounts trigger filesystem errors, remove source/config bind mounts and rebuild immutable campaign images.
- Run deterministic no-LLM arms first, then one-instance LLM and framework arms before launching a full subset.
- Treat smoke success as pipeline validity: JSON summaries, patch artifacts, patch applicability, official evaluator execution, and telemetry must all be present.

### Patch Benchmark Workspace Cleanliness Standard
- A `no_change` arm must deliver zero artifacts; any nonzero artifact delivery means the workspace is dirty or the output contract is wrong.
- Force-clean per-framework workspaces for clean campaign launches, especially after smoke tests or aborted runs.
- Do not reuse a result directory after a contamination signal; relaunch into a fresh `out-dir`.

### No-Op Baseline Contract Standard
- Implement no-op baselines by writing an explicit empty artifact and explicit no-delivery stats.
- Never use raw workspace diffs to infer no-op behavior, because checkout normalization can create parasite diffs.
- Treat disagreement between `failure_reason=empty_patch` and nonzero artifact delivery as a contract bug.

### MigrationBench Timeout Guard Standard
- Wire timeout controls through every layer: Docker Compose, campaign runner, framework runner, manifest, and per-instance failure rows.
- Kill process groups, not only parent Python processes, when enforcing timeouts around tools that can spawn Maven or official evaluators.
- Set main-campaign timeouts from observed official-eval/runtime tails; keep very short values for smoke tests only.

### Marker Final-Contract Extraction Standard
- Select final benchmark contracts by marker type and required schema fields, not by marker ID suffix alone.
- Reject or rerun any benchmark arm where `runs.json` contains more rows than requested instances.
- Keep framework-internal learning artifacts such as lessons, skills, or protocols out of benchmark result rows.

### Docker Benchmark Cache Hygiene Standard
- Treat benchmark workspaces as disposable cache when debugging contamination, stale checkouts, or reruns after extraction fixes.
- Exclude mounted benchmark directories from image contexts, especially `workspaces/` and `external/`.
- If Docker Desktop stalls on repository context loading, build a tagged campaign image from a minimal temporary context and run Compose with `--no-build`.

### Patch Benchmark Completion Triage Standard
- Confirm container exit code, requested denominator, recorded rows, and result file presence before interpreting rates.
- Report the artifact funnel in order: delivered patch, clean `git apply`, official evaluation, strict success.
- Distinguish valid negative results from infrastructure failures by checking official evaluator return codes and per-instance failure reasons.

### Repository Migration Control-Loop Standard
- Do not finalize a migration patch from proposal alone; finalization should depend on build/test feedback or an explicit no-repair decision.
- Treat compile/test logs as first-class context for the next edit proposal, not as passive telemetry.
- Flag small POM-only patches as a weak baseline unless they pass official evaluation or trigger a repair loop.

### Stigmergic Repair-Colony Implementation Standard
- Model every candidate patch as a branch-scoped marker with typed edits, attempt number, failure taxonomy, validation status, and quality score.
- Convert build, patch-apply, and official-eval failures into repair markers with compact feedback; do not silently continue from failed telemetry.
- Keep dynamic agent pools opt-in and trace min/max/avg active agents so adaptivity is measurable rather than cosmetic.

### Ablation Treatment-Activation Standard
- Before interpreting an ablation score, verify that each arm actually activated the mechanism it claims to test: candidate fan-out for branching, non-empty repair proposals for repair loops, and blackboard events for typed coordination.
- Report execution validity separately from scientific validity; Docker `exit 0`, full denominators, and replay parity prove the harness, not the treatment.
- Align local verifier gates with official benchmark semantics, then keep stricter local-only checks as diagnostics rather than pre-official blockers unless the benchmark contract explicitly requires them.

### Budgeted Branch-Search Workspace Hygiene Standard
- Exclude generated build outputs when copying candidate branches; keep VCS metadata only when patch export still depends on it.
- Delete disposable verification workspaces immediately after their verdict is serialized, and scrub branch build outputs before repairs fork from them.
- Keep strict-success metrics score-derived, but add separate apply/validation counters so partial progress remains visible in failed or non-finalized runs.

### Causal Medium Replay Standard
- Reconstruct active medium state from lifecycle events, not just aggregate counters; consumed, expired, inhibited, retired, and decayed records need replay tests.
- Score affordance-worker pairs rather than selecting workers against a single top affordance.
- Make deterministic smoke scripts idempotent by cleaning only their owned output subtrees before each run.

### Home Skill Retirement Standard
- Remove retired skills from `/Users/lotfi/.codex/AGENTS.md` active trigger lists before relying on automatic skill discovery.
- Check the project `AGENTS.md` for stale duplicates, but keep the edit scoped to the file that actually declares the removed skill.

### Main Campaign Launch Gate Standard
- Scope every multi-arm workspace and artifact root by arm id before running the first instance.
- Treat replay parity, full denominator, and owned-output cleanup as launch gates, not post-hoc nice-to-haves.
- Require causal activation only for instances or arms with repairable validation failures; no-repair local-green paths should remain launch-valid.

### OpenAI-Compatible Proxy API Test Standard
- Test third-party OpenAI-compatible keys against their provider base URL before calling `api.openai.com`.
- Use `POST /responses` for text models when the provider warns that Chat Completions is unsupported.
- If the proxy rejects the Responses `image_generation` tool, test GPT Image models through `POST /images/generations` with the same base URL.
- Keep secrets in environment variables or local `.env` parsing and redact any diagnostic output that could expose credentials.
- Save one-off image generations under `output/francestudent_api_tests/` with the raw response beside the decoded PNG when the user wants to inspect the result.

### Repo-Local Provider Skill Standard
- Create project-specific API skills under `.codex/skills/` so they are versionable with the project and do not pollute home-level skill discovery.
- Keep `SKILL.md` as the operational routing layer, with provider-specific parameter lists in `references/`.
- Add a small CLI when the workflow needs secret-safe, repeatable HTTP calls and local artifact decoding.

### Repo-Local Docker No-Cache Skill Standard
- Put benchmark Docker launch rules in `.codex/skills/` when they are project-specific and easy to forget under time pressure.
- Build Compose services with `docker compose build --no-cache --pull --progress=plain <service>` before running them; do not rely on `docker compose run --build`.
- Keep secrets out of CLI arguments, gate paid or full-denominator campaigns on explicit user intent, and record the compose file, service, env knobs, and output directory after each run.

### Live Benchmark Mechanism Audit Standard
- Watch treatment-specific activation counters while a long benchmark is still running; zero mechanism events in a treatment arm is a bug signal even if candidates and validations are flowing.
- Resolve branch-local files through adapter-owned metadata paths before falling back to generic workspace roots.
- After fixing a live-campaign bug, archive flawed partial outputs, relaunch only the invalidated arm, and rebuild aggregate reports from replayed EventLogs.

### Guarded LLM Fallback Standard
- Never let a free-form LLM edit candidate reach adapter validation until every `replace_text.old` span has been checked against the real parent branch workspace.
- Simulate edit application sequentially per file inside the guard, because duplicate or overlapping spans can pass initial-file checks and still fail in the adapter.
- Treat invalid guarded edits as causal events: reject the candidate, inhibit the unsafe origin/action, and support a safer worker/operator path.
- Drive repair-frontier choices from best observed funnel progress, while reporting strict benchmark success only from the official final contract.
- Audit guarded campaigns on two axes: final strict success for claims, and `replacement_count_too_low`/best-observed funnel for mechanism quality.

### FranceStudent Oversized Prompt Triage Standard
- For `/responses` 502s, measure the serialized JSON body, input characters/bytes, system-instruction size, and rough token estimate before escalating.
- In PaperBanana auto retrieval, treat the default 200 diagram references as too large for proxy debugging unless the provider confirms a very large context path.
- Prefer lowering `RetrieverAgent.ref_limit` and verifying non-empty `top10_references` over rerunning the same multi-megabyte retrieval prompt.

### PaperBanana Proxy-Safe Retrieval Standard
- Cap diagram retrieval references before calling hosted `/responses` proxies with documented input-token ceilings.
- Filter unrelated cyber/security benchmark examples from generic reference corpora when the user's task is non-cyber and the provider enforces cyber-safety gates.
- Make retriever parsing tolerant of equivalent JSON keys such as `top10_diagrams`, `top10_references`, and `ids`, then log selected IDs for auditability.

### Same-Prompt Figure Comparison Standard
- Keep one canonical direct prompt file for image-model comparisons, then reuse it unchanged across providers.
- When PaperBanana needs a separate caption or visual intent, append that caption only for direct model UIs that accept a single prompt field.
- Preserve explicit negative constraints in the prompt so generated figures do not contain source lines, captions, or paragraph text inside the image.

### Memoir Figure Swap Standard
- Prefer swapping only the `\includegraphics` target when the surrounding caption and source attribution remain scientifically valid.
- Verify the new image file exists under the LaTeX image root and check logs for missing-graphic errors after a compile attempt.
- Do not rename or delete superseded figure assets unless the user explicitly asks for cleanup.

### Figure Generation Cost Comparison Standard
- Count direct image generation as one useful image prompt per successful output, and separately note failed technical attempts such as unsupported sizes.
- Count PaperBanana `demo_full` with one critic round as five useful calls when no revision is requested: retriever, planner, stylist, visualizer, and critic.
- Include approximate user-prompt tokens and retriever-prompt tokens, because retrieval-heavy workflows can be much more expensive than the visible prompt suggests.

### Mixed Figure Workflow Integration Standard
- When comparing multiple image workflows, integrate the best output per figure rather than forcing one workflow across a whole section.
- Keep the figure source/caption stable when the replacement is an adapted rendering of the same conceptual content.
- Verify every selected image exists under `documentation/memoire/latex/images/` before changing the LaTeX include path.

### Local Figure Sizing Standard
- Resize acceptable figure assets at the LaTeX call site with `width=<fraction>\linewidth,keepaspectratio`.
- Use local sizing for page-balance tweaks so global `\includegraphics` behavior stays stable for the rest of the memoir.
- Keep captions and alt text unchanged when only the rendered scale changes.

### Operator-Unavailable Coverage Standard
- Build the coverage backlog from `operator.unavailable` events joined with raw verifier output, feedback evidence, affordance metadata, and best-observed stage.
- Add only the smallest set of typed operators that covers the dominant failure families, using feasibility and scoped-edit risk to break frequency ties.
- Prefer exact block-scoped POM upgrades for benchmark operators; leave internal snapshot dependencies, broad source rewrites, and ambiguous official-eval failures as explicit non-covered families until they recur enough to justify risk.

### Target-Aware Migration Operator Standard
- Introduce a typed migration context at the adapter boundary and fail fast when benchmark target fields are absent.
- Keep operator names action-oriented and target-neutral; select Java/Maven/JAXB/Lombok thresholds from compatibility profiles keyed by target version.
- Test prompts, deterministic fallbacks, and affordance metadata for non-default targets so removed hardcodes do not survive in secondary paths.

### Targeted Operator Coverage Regression Standard
- Promote `operator.unavailable` rows into specific affordances before changing operators; this keeps scheduler decisions auditable.
- Keep diagnostic-only families explicit when a safe typed patch would require private repositories, broad framework upgrades, or complex source rewrites.
- Re-run a small Docker subset built from the unavailable families and require replay parity plus zero `replacement_count_too_low` before relaunching main campaigns.

### Benchmark Workspace Relaunch Standard
- Reset reused base checkouts to their registered base commit before generating observations or validating guarded edits.
- Purge stale candidate branch directories at adapter setup, then preserve branches only within the current run for apply/validate/finalize continuity.
- When a stale workspace contaminates a live campaign, archive partial outputs, commit the workspace fix, rebuild Docker, and relaunch only the invalidated arm.

### LLM Provider Trace Audit Standard
- Persist every provider-level LLM call before candidate filtering can erase evidence of invalid, duplicate, or empty generations.
- Include system prompt, user prompt, raw response, parsed JSON, normalized edits, usage metadata, candidate emission status, and drop reason; omit API keys and provider headers.
- Write traces under the arm output directory so restored/recomposed benchmark campaigns keep their LLM evidence beside EventLogs, summaries, and artifacts.

### V11 Campaign Audit Artifact Standard
- Generate campaign-local `audits/` outputs from replayable artifacts rather than ad hoc terminal snippets.
- Reconstruct best-observed funnel progress from all validation events, then compare treatment/control arms pairwise by instance.
- Attribute operator impact by joining `operator.*`, `candidate.created`, `affordance.created`, `feedback.created`, and validation-score events before labeling helped, harmed, or neutral.

### Agent Handoff Refresh Standard
- Keep root handoff docs focused on the active architecture and mark legacy stacks as historical rather than documenting them as current scope.
- Include the latest benchmark interpretation, not only commands, so future agents do not overclaim or optimize the wrong metric.
- Link to canonical ADRs/artifacts for history and keep active commands, invariants, and ownership boundaries in the handoff itself.

### B6 Trace-Driven Repair Hardening Standard
- When `calls.jsonl` shows a useful LLM/source repair but B6 chooses a generic POM operator, first add the verifier-referenced source file to live repair context.
- Add exact source operators only for narrow patterns whose old span is present and whose semantic preconditions are checkable locally.
- Emit `operator.rejected` plus inhibition when an operator child scores below its parent, and classify it as blocked regression in follow-up audits.

### V12 Agentic Tool Guardrail Audit Standard
- Add negative tests with buggy registered handlers so `ToolExecutor` proves the `ToolSpec` mutation/proposal contract centrally, not only by convention.
- Reject agent-provided shell control in verifier commands, and require official-eval commands to come from trusted workspace metadata.
- Redact raw LLM response strings as well as structured fields, but keep non-secret metrics such as token counts visible for auditability.

### V12 Native Tool-Call Provider Standard
- Expose each agent tool as a separate native function with strict provider-facing schemas; do not wrap tools in a generic `call_tool`.
- Add a required `rationale` argument to every native schema so traces preserve why the agent chose the tool.
- Send `tool_choice="required"` whenever the scientific contract requires a native tool call; prompt wording alone is not a sufficient provider boundary.
- Keep model defaults provider-scoped: DeepSeek may use the repo default, but OpenAI/OpenRouter-style routes must fail fast unless the benchmark config names an explicit model.
- For DeepSeek V4 tool-choice calls, use `deepseek-v4-flash` with thinking disabled; the legacy `deepseek-chat` alias is non-thinking compatibility and should not be the long-term default.
- Prefer direct HTTP with explicit timeout for DeepSeek smoke/campaign tool-choice calls if the OpenAI-compatible SDK path hangs locally.
- Use the repo-local `.codex/skills/deepseek-api` skill before changing DeepSeek provider code or running live DeepSeek smoke tests.
- Parse string booleans in benchmark extras before constructing provider configs so `"false"` cannot accidentally enable LLM providers, strict tools, or tracing.
- Retry only malformed or schema-invalid provider tool calls; once a valid tool executes and returns `rejected` or `failed`, feed that outcome back through the medium instead of making an automatic replacement LLM call.

### V12 Tool Annotation Autonomy Standard
- Show the full non-forbidden domain toolbox to the LLM; never use medium support or inhibition as a hidden shortlist.
- Encode stigmergic influence as per-tool annotations with support, inhibition, risk, recommendation, reason, evidence, and recent outcomes.
- Audit autonomy by comparing followed, overridden, inhibited, forbidden, successful-override, and harmful-override tool choices.

### V12 Agentic Campaign Runner Standard
- Create candidate branches lazily after a valid LLM-selected mutating tool call; keep read/search/inspect tools on the active parent workspace.
- Record S2/V12 tool registry names in each arm manifest and fail readiness if they differ.
- Produce `comparison.json`, `v12_readiness_report.json`, best-observed funnel, pairwise deltas, tool trace calls, and medium-attribution CSVs from EventLogs before interpreting any V12 campaign.

### V12 Medium Outcome-Guided Annotation Standard
- Record tool outcomes in the medium and expose them as annotation evidence; do not use outcomes to hide non-forbidden tools.
- After successful proposal or repeated inspection evidence, increase support for guarded edit tools and add caution to repeated non-mutating tools.
- Compare V12 against S2 after every annotation change; a useful medium should improve or match S2 while keeping `medium_created_patch_count == 0`.

### V12.4 SD-Feedback Patch Proposal Standard
- Use SD-Feedback as the verifier-gated loop of truth: LLM proposes a patch, the harness guards/applies/verifies, then accepts or reverts.
- Keep S2 and V12 read-only perception tools identical; the only treatment difference should be compact stigmergic feedback augmentation.
- Treat invalid patch syntax/old-span failures as syntactic feedback and no-progress verifier outcomes as semantic feedback; do not spend benchmark validation slots on unguarded patch attempts.

### UV Environment Recovery Standard
- Rebuild `.venv` with `uv venv --python <version>` and `uv pip install -r requirements.txt`, then run `uv pip check` before assuming dependency conflicts remain.
- If Python imports hang on macOS, check candidate source files with `ls -lO@`; a `dataless` file can block reads and should be rehydrated or recreated before rerunning tests.
- Use `PYTHONPATH=.` plus focused `--confcutdir` pytest runs when validating active V12 modules so legacy root test fixtures do not obscure the environment signal.
