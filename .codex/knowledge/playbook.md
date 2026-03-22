# Project Playbook

## Repo
- `repo_slug`: `stigmergiagentic-33b989`

## Active Practices

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
