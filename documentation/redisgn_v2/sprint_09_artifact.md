# Sprint 09 — Persistent Skills, Protocol Artifacts, and Protocol Compiler Artifact

## Sprint scope

Sprint 9 implements the three thesis-facing claims on top of the Sprint 8 V6 runtime:

1. **C1 — Objective-conditioned protocol generation** (`T3`)
   - `DomainAdapter.compile_protocol()` optional contract
   - `ProtocolSpec` schema + `SYSTEM_PROTOCOL_COMPILER` prompt
   - `AssistantAdapter.compile_protocol()` and `TravelPlannerAdapter.compile_protocol()`
   - Fallback to `initial_markers()` when compilation fails or is disabled

2. **C2 — Cross-run skill accumulation** (`T1`)
   - `skills_store` (`pheromones/skills.db`) separate from session-isolated run store
   - `Environment._maybe_promote_to_skill()` promotes lesson markers to skill markers when `quality_score >= lesson_threshold` and `usage_count >= promotion_min_uses`
   - `Agent._recall_skills()` reads top-k persistent skills from the cross-run snapshot
   - Config surface: `skill_library.enabled`, `skill_library.read_only`, `reinforcement.promotion_min_uses`

3. **C3 — Cross-run coordination improvement** (`T2`)
   - `protocols_store` (`pheromones/protocols.db`) with three slots per namespace: `baseline`, `latest`, `best`
   - `MarkerStore.save_protocol_marker()` / `load_protocol_marker()`
   - `compute_protocol_score()` and `clamp_cross_run_adaptations()` (helpers already present) now wired in `main.py`
   - `_persist_protocol()` saves `latest`, creates immutable `baseline`, and updates `best` only when score improves
   - `_maybe_apply_cross_run_protocol()` loads `best` and applies clamped adaptations before each run

## Current artifact behavior

### Skill Library (C2)

When `skill_library.enabled=true` and `read_only=false`:
- `Environment.apply_action_result()` calls `_maybe_promote_to_skill()` after each successful action.
- The method inspects `ActionResult.metadata["credited_lesson_ids"]`.
- For each credited lesson, it increments `usage_count` on the lesson marker in the run store.
- When `usage_count >= promotion_min_uses` and `quality_score >= lesson_threshold`, a `skill` marker is upserted into `skills_store`.
- Skill ID format: `skill::{adapter_name}::{lesson_id}`.
- Skill payload carries: `skill_text`, `context_fingerprint`, `quality_score`, `usage_count`, `domain`.
- Skill intensity is initialized from `quality_score` and uses the very low `decay_rates_by_type.skill` (default 0.005).

Agents receive skills through `EnvironmentSnapshot.skills`, populated by `Environment.snapshot()` when `skill_library.enabled=true`.

### Protocol Artifacts (C3)

When `protocol.enabled=true` and `emergence.cross_run.enabled=true`:
- At startup, `main.py` calls `_maybe_apply_cross_run_protocol(config, protocol_store, namespace)`.
- It loads `coordination_protocol::{adapter}::{config_hash}::best` and `::baseline`.
- Adaptations are clamped with `clamp_cross_run_adaptations(adaptations, baseline["config"], max_total_delta)`.
- Clamped values are written back into the live `config` dict via dotted-path `_set_config_path()`.
- After the run, `_persist_protocol()` computes `compute_protocol_score(evaluation)` and saves:
  - `latest` — always overwritten
  - `baseline` — created once, never updated
  - `best` — updated only if current score > best score

### Protocol Compiler (C1)

When `agents.protocol_compiler.enabled=true`:
- `main.py` calls `adapter.compile_protocol(objective, config, llm_client)` before seeding markers.
- The adapter sends a structured compiler prompt to the LLM and expects a `ProtocolSpec`.
- The spec is validated (allowed actions, DAG acyclicity) and converted to seed markers.
- On validation failure or missing LLM, the runtime falls back to `adapter.initial_markers()` without raising.
- Both `AssistantAdapter` and `TravelPlannerAdapter` implement `compile_protocol()`.

## Public interfaces and contracts

### Config surfaces

- `skill_library.enabled` (bool, default false)
- `skill_library.read_only` (bool, default false)
- `skill_library.db_path` (str, default `"pheromones/skills.db"`)
- `protocol.enabled` (bool, default false)
- `protocol.read_only` (bool, default false)
- `protocol.db_path` (str, default `"pheromones/protocols.db"`)
- `reinforcement.promotion_min_uses` (int, default 2)
- `reinforcement.lesson_threshold` (float, default 0.7)
- `emergence.cross_run.enabled` (bool, default false)
- `emergence.cross_run.read_only` (bool, default false)
- `emergence.cross_run.max_total_delta` (float, default 0.15)
- `markers.decay_rates_by_type.skill` (float, default 0.005)
- `markers.decay_rates_by_type.coordination_protocol` (float, default 0.01)

### Core runtime additions

- `core.marker_store.MarkerStore`
  - `save_protocol_marker(slot, namespace, payload, agent_id)` -> `Marker`
  - `load_protocol_marker(slot, namespace)` -> `dict | None`
- `core.environment.Environment`
  - `__init__(..., skills_store: MarkerStore | None, adapter_name: str)`
  - `_maybe_promote_to_skill(agent_id, result, quality_score)`
  - `_build_skill_context_fingerprint(lesson)`
- `core.agent.StigmergicAgent`
  - `_recall_skills(snapshot, top_k)` -> `list[dict]`
  - `perceive_and_decide()` now includes skills in `Decision.lesson_markers`
- `core.tool_registry.ActionResult`
  - `metadata` may contain `credited_lesson_ids: list[str]` (convention now documented in dataclass)

### Main.py runtime wiring

- `_maybe_build_skills_store(config)` -> `MarkerStore | None`
- `_maybe_build_protocol_store(config)` -> `MarkerStore | None`
- `_build_protocol_namespace(config, adapter_name)` -> `str`
- `_maybe_apply_cross_run_protocol(config, protocol_store, namespace)` -> `bool`
- `_persist_protocol(result, evaluation, config, protocol_store, namespace, session_id)` -> `None`
- `_set_config_path(config, path, value)` -> `None`

## Guardrails and constraints

- All Sprint 9 features are **opt-in** and **disabled by default**; Sprint 8 behavior is preserved when configs are absent or false.
- `skill_library.read_only=true` prevents skill promotion but still allows skill recall.
- `emergence.cross_run.read_only=true` prevents protocol persistence but still allows loading.
- `MarkerStore(session_isolation=False)` is used for both `skills_store` and `protocol_store` to guarantee cross-run visibility.
- Baseline protocol markers are append-only semantics: once written, they are never overwritten by `_persist_protocol()`.
- `clamp_cross_run_adaptations` enforces `max_total_delta` per config path to prevent runaway drift.

## Known limits / not executed in this session

- No benchmark campaign was executed in this session (operator-run next step).
- Pareto instrumentation aligned with V2 runtime is still pending.
- CodeMigration adapter (V2) and SWE-bench adapter are not implemented.
- Full 3-seed paired validation for V5-full vs V6-base is still operator-run.
- `langgraph` dependency is optional; the supervisor baseline test is skipped when absent.

## Addendum 2026-04-30 — MigrationBench V7 (repair colony, opt-in)

Le bras `stigmergic_v7_repair_colony` étend MigrationBench sans toucher V6 :
- `adapters/migrationbench/adapter.py` — `_is_v7_colony()` aiguille `register_tools` et `initial_markers` vers le pipeline en boucle fermée (`inspect_repository → localize_migration_surface → propose_patch_candidate → apply_patch_candidate → run_build_validation → classify_build_failure → repair_patch_candidate → select_patch_candidate → finalize_evaluated_patch`). V6 (`propose_patch / run_build / finalize_patch`) reste le chemin par défaut.
- `adapters/migrationbench/workspace.py` — `branch_workspace` et `fork_branch_workspace` créent un workspace candidat isolé par branche (`branches/<branch_id>/repo`).
- `adapters/migrationbench/tools.py` — taxonomie d'échecs typée `pom_parse_error`, `dependency_resolution_error`, `compile_error`, `test_failure`, `class_version_error`, `patch_apply_error`, `official_eval_failed` ; les outils émettent des markers `patch_hypothesis` parents/enfants reliés via `branch_id` / `parent_branch_id` / `attempt`. `FinalizeEvaluatedPatchTool` calcule `repair_cycles`, `branch_count`, `caps_hit`, `failure_taxonomy` et les inclut dans le contrat strict.
- `core/orchestrator.py` — `agents.num_agents_mode: elastic` active un pool homogène redimensionné chaque tick (`min_agents`, `max_agents`, `markers_per_agent`, `scale_up_utilization`, `scale_down_contention`, `scale_down_idle_utilization`). Chaque resize est audité (`agent_pool_resize`) et résumé dans `OrchestratorResult.emergence_summary["agent_pool"]` (`dynamic_agents_min/max/avg`, `resize_events`, `observations`).
- `config/migrationbench_v7_repair_colony_deepseek.yaml` — preset DeepSeek + safety caps (`max_tokens_per_instance`, `max_runtime_per_instance_seconds`, `max_llm_calls_per_instance`, `max_repair_cycles_per_instance`).
- `docker-compose.campaign.yml` — service `migrationbench-campaign` accepte les nouvelles variables `MIGRATION_CONFIG` et `MIGRATION_FRAMEWORKS` ; même service utilisé pour V6 et V7.
- `scripts/run_migrationbench_query_export.py` — branche `stigmergic_v7_repair_colony` sur `run_stigmergic_runtime`, ajoute `branch_count`, `repair_cycles`, `failure_taxonomy`, `caps_hit`, `dynamic_agents_*` au contrat de sortie.

Validation 2026-04-30 :
- `python -m pytest tests/unit/test_migrationbench_v7_repair_colony.py tests/unit/test_orchestrator.py tests/unit/test_migrationbench_adapter.py tests/unit/test_migrationbench_workspace.py -q` → **21 passed**.
- `python -m py_compile core/orchestrator.py adapters/migrationbench/{adapter,tools,workspace}.py` → OK.
- Smoke local précédemment validé par l'agent V7 : `stigmergic_v7_repair_colony` avec `--skip-official-eval` s'arrête en `all_terminal` sans boucle infinie sur `official_eval_not_run`.

Limitations à documenter pour la campagne :
- Une seule seed par bras (cohérent avec la campagne scientifique TravelPlanner).
- L'environnement local de validation rapide (`uv run pytest`) hang sur la collection des modules `tests/unit/test_migrationbench_baselines.py` et `tests/unit/test_migrationbench_campaign_runner.py` (problème environnement, non-V7) ; faire tourner ces deux modules dans Docker pour la non-régression.
- Les caps de sécurité (`safety_caps`) doivent être suivis via `caps_hit` pour distinguer succès/échecs imputables au budget.

Lancement campagne : voir `CLAUDE.md` et `AGENTS.md` (section *MigrationBench V7 repair colony*).

## Addendum 2026-05-02 — MigrationBench V7.1 hardening

V7.1 durcit le bras `stigmergic_v7_repair_colony` après le diagnostic `main_30` :
- `adapters/migrationbench/tools.py` — normalisation des sorties LLM en edits typés (`file/content`, `old/new`, `replace`), retry après erreur de schéma, rejet des edits vides ou hors surface Maven/Java, digest Maven ciblé, historique de repair, anti-loop, sélection stricte et porte de sortie `best_partial_finalization`.
- `RunBuildValidationTool` — validation official-like explicite : `mvn dependency:resolve`, `mvn clean compile`, `mvn clean verify`, `mvn test`, test count non-régressif si connu, et class versions exactement `{61}` pour Java 17.
- `core/environment.py` — nouveau flag `lessons.enabled`; les lessons sont désactivées par défaut pour `migrationbench.workflow == "v7_repair_colony"` afin de ne pas polluer les runs de repair.
- `core/orchestrator.py` — le pool élastique compte aussi les markers `planning` avec actions éligibles, ce qui évite de sous-estimer la demande pendant les branches de patch.
- `scripts/migrationbench_cleanup.py` + `scripts/run_migrationbench_query_export.py` — `--force` nettoie DB, WAL/SHM, audit et artefacts de patch par instance.
- `scripts/migrationbench_smoke_gate.py` — gate technique `smoke_5` avant `main_30` : télémétrie, absence d'exceptions JSON/Pydantic non récupérées, isolation `objective_id`, chemin `select/finalize`, digest < 4500 chars en warning.
- `config/migrationbench_v7_repair_colony_deepseek.yaml` — conserve `llm.model: deepseek-v4-flash`, désactive `lessons`, et rééquilibre les poids pour faire avancer les branches existantes avant d'empiler de nouvelles propositions.

Validation 2026-05-02 :
- `uv run pytest tests/unit/test_migrationbench_v7_repair_colony.py tests/unit/test_orchestrator.py -q` → **29 passed**.
- `uv run pytest tests/unit/test_migrationbench_adapter.py tests/unit/test_migrationbench_workspace.py tests/unit/test_migrationbench_evaluator.py -q` → **6 passed**.
- `uv run python -m py_compile adapters/migrationbench/tools.py scripts/run_migrationbench_query_export.py scripts/migrationbench_cleanup.py scripts/migrationbench_smoke_gate.py core/environment.py core/orchestrator.py` → OK.

## Validation evidence

- Sprint 8 non-regression: `uv run pytest tests/unit/test_config.py tests/unit/test_marker_store.py tests/unit/test_environment.py tests/unit/test_agent.py tests/unit/test_orchestrator.py tests/unit/test_travelplanner_tools.py -q` -> **81 passed** (threshold ≥ 77)
- Sprint 9 existing tests: `uv run pytest tests/unit/test_emergence.py tests/unit/test_protocol_compiler.py -q` -> **14 passed**
- Sprint 9 new unit tests: `uv run pytest tests/unit/test_environment_skill_promotion.py tests/unit/test_protocol_persistence.py -q` -> **13 passed**
- Sprint 9 integration tests: `uv run pytest tests/integration/test_skill_persistence.py tests/integration/test_protocol_cross_run.py tests/integration/test_protocol_compiler_integration.py -q` -> **18 passed**
- **Full suite** (excluding optional langgraph): **307 passed**

## Files created or modified

- `core/tool_registry.py` — document `credited_lesson_ids` convention
- `core/environment.py` — add `skills_store`, `_maybe_promote_to_skill()`, `_build_skill_context_fingerprint()`
- `core/agent.py` — add `_recall_skills()`, include skills in decision context
- `core/marker_store.py` — add `save_protocol_marker()`, `load_protocol_marker()`
- `main.py` — wire skills_store, protocol_store, cross-run apply/persist helpers
- `adapters/travelplanner/adapter.py` — implement `compile_protocol()`
- `tests/unit/test_environment_skill_promotion.py` — new
- `tests/unit/test_protocol_persistence.py` — new
- `tests/integration/test_skill_persistence.py` — new
- `tests/integration/test_protocol_cross_run.py` — new
- `tests/integration/test_protocol_compiler_integration.py` — new

# Sprint 9 — État d'avancement et travail restant

> Commit de référence : `5c3c5a8` — `feat(sprint9): scaffold persistence and protocol compiler seams`  
> Date : 2026-04-21  
> **Ce document est destiné à l'agent suivant. Lire intégralement avant de coder.**

---

## Résumé exécutif

Le sprint 9 est **partiellement implémenté**. Le scaffolding (config, helpers, T3) est en place. T1 et T2 — le cœur fonctionnel du sprint — sont entièrement à implémenter.

| Tâche | Critère | État | Ce qui reste |
|-------|---------|------|-------------|
| T3 — Protocol Compiler | C1 | ✅ ~80% | Tests d'intégration (voir §T3) |
| Config scaffolding | — | ✅ 100% | Rien |
| Helpers T2 | C3 | ✅ 100% | Rien (fonctions existent, pas branchées) |
| **T1 — Skill Library** | **C2** | **❌ 0%** | **Tout à faire** |
| **T2 — Protocol Artifacts** | **C3** | **❌ 10%** | **Persistence + branchement main.py** |

---

## Ce qui existe déjà (ne pas recréer)

### Config (`config/default.yaml`)
Toutes les clés sont posées et validées :
```yaml
skill_library:
  enabled: false
  read_only: false
  db_path: "pheromones/skills.db"

protocol:
  enabled: false
  read_only: false
  db_path: "pheromones/protocols.db"

reinforcement:
  promotion_min_uses: 2       # seuil promotion lesson→skill
  lesson_threshold: 0.7

markers:
  decay_rates_by_type:
    skill: 0.005              # très faible decay pour les skills
    coordination_protocol: 0.01

emergence:
  cross_run:
    enabled: false
    read_only: false
    max_total_delta: 0.15
```

Presets créés : `config/travelplanner_adapt.yaml`, `config/travelplanner_eval.yaml`

### Helpers dans `core/emergence.py`
- `compute_protocol_score(evaluation) -> float` (lignes 126–137)
- `clamp_cross_run_adaptations(adaptations, baseline_config, max_total_delta) -> dict` (lignes 140–168)

Ces deux fonctions sont **implémentées et testées** mais **jamais appelées** — il faut les brancher depuis `main.py`.

### T3 — Protocol Compiler (`adapters/assistant/adapter.py:129`)
- `DomainAdapter.compile_protocol()` méthode optionnelle dans `adapters/base.py`
- `ProtocolSpec` dans `core/schemas.py`
- `SYSTEM_PROTOCOL_COMPILER` + `build_protocol_compiler_prompt()` dans `llm/prompts.py`
- `AssistantAdapter.compile_protocol()` implémenté
- Fallback dans `main.py` via `_select_initial_markers()`
- Tests dans `tests/unit/test_protocol_compiler.py` (131 lignes, 32 passed)

### Convention documentée
`core/tool_registry.py:77` — commentaire indiquant que `ActionResult.metadata` peut contenir `credited_lesson_ids`. **C'est un commentaire uniquement**, pas une implémentation.

---

## T1 — Skill Library (C2) — À implémenter entièrement

### Objectif
Les lesson markers réussis (quality ≥ threshold, réutilisés ≥ `promotion_min_uses` fois) sont promus en **skill markers** persistants dans une DB séparée (`pheromones/skills.db`). Les agents les consultent au démarrage de chaque run. La performance s'améliore cross-run.

### Fichiers à modifier

#### 1. `core/tool_registry.py`
Ajouter `credited_lesson_ids` dans `ActionResult` (pas juste en commentaire) :

```python
@dataclass(slots=True)
class ActionResult:
    action_type: str
    marker_updates: list[Marker] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    # metadata peut contenir : credited_lesson_ids: list[str]
    # Utilisé par environment._maybe_promote_to_skill()
```
→ Aucun changement de signature nécessaire, juste documenter la convention dans le dataclass.

#### 2. `core/environment.py`
Ajouter la méthode `_maybe_promote_to_skill()` appelée depuis `apply_action_result()`.

La méthode doit :
1. Lire `result.metadata.get("credited_lesson_ids", [])` — si vide, sortir
2. Vérifier `quality_score ≥ config.reinforcement.lesson_threshold`
3. Pour chaque `lesson_id` crédité :
   - Lire le lesson marker depuis `self.store`
   - Incrémenter `payload["usage_count"]` (ou créer à 1)
   - Si `usage_count >= config.reinforcement.promotion_min_uses` :
     - Créer/upsert un marker `skill` dans `self.skills_store` (voir §main.py)
     - ID : `f"skill::{adapter_name}::{lesson_id}"` (adapter_name depuis config)
     - Payload : `{skill_text, context_fingerprint, quality_score, usage_count, domain}`
     - Intensité = `quality_score`, decay = 0.005 (déjà dans config)

```python
def _maybe_promote_to_skill(
    self,
    *,
    agent_id: str,
    result: ActionResult,
    decision_context: str,
) -> None:
    """Promote credited lesson markers to persistent skill markers."""
    if self.skills_store is None:
        return
    skill_cfg = dict(self.config.get("skill_library", {}))
    if not bool(skill_cfg.get("enabled", False)):
        return
    if bool(skill_cfg.get("read_only", False)):
        return
    ...
```

`Environment.__init__` doit accepter `skills_store: MarkerStore | None = None` et le stocker.

#### 3. `core/agent.py`
Étendre `_recall_lessons()` pour lire aussi le `skills_store` cross-run.

Ajouter méthode `_recall_skills()` :
```python
def _recall_skills(
    self,
    *,
    snapshot: EnvironmentSnapshot,
    top_k: int,
    skills_store: MarkerStore | None = None,
) -> list[dict[str, Any]]:
    """Read persistent skill markers from cross-run skills_store."""
    if skills_store is None:
        return []
    skill_cfg = dict(self.config.get("skill_library", {}))
    if not bool(skill_cfg.get("enabled", False)):
        return []
    # Lire tous les markers skill depuis skills_store
    # Trier par intensité décroissante
    # Retourner top_k au format dict (comme lesson_markers)
    ...
```

Modifier `perceive_and_decide()` pour appeler `_recall_skills()` et inclure le résultat dans `Decision.lesson_markers` (ou un nouveau champ `skill_markers`).

#### 4. `main.py`
Ajouter juste avant `environment = Environment(...)` :

```python
SKILLS_DB_PATH = Path("pheromones/skills.db")

def _maybe_build_skills_store(config: dict[str, Any]) -> MarkerStore | None:
    skill_cfg = dict(config.get("skill_library", {}))
    if not bool(skill_cfg.get("enabled", False)):
        return None
    db_path = Path(str(skill_cfg.get("db_path", "pheromones/skills.db")))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return MarkerStore(
        db_path=db_path,
        session_isolation=False,   # CRITIQUE : pas d'isolation → cross-run
        traceability=False,
    )
```

Passer `skills_store` à `Environment(...)` et aux agents.

### Tests à écrire

`tests/unit/test_environment_skill_promotion.py` :
- Pas de promotion sans `credited_lesson_ids`
- Pas de promotion si `usage_count < promotion_min_uses`
- Promotion exactement au seuil

`tests/integration/test_skill_persistence.py` :
- Run 1 avec `skill_library.enabled: true` → crée lesson → `usage_count = 1`
- Run 2 sur même `skills_store` → réutilise lesson → `usage_count = 2` → skill promu
- Run 3 → lit le skill depuis `skills_store`

---

## T2 — Protocol Artifacts (C3) — Persistence à implémenter

### Objectif
Les métriques d'émergence en fin de run sont persistées comme marker `coordination_protocol` dans `pheromones/protocols.db`. Le run suivant charge le meilleur protocole (`best`) et applique ses adaptations à la config via `clamp_cross_run_adaptations()` (déjà implémenté).

### Slots de persistance
Trois markers dans `protocols.db` :
- `coordination_protocol::baseline` — config initiale de la campagne, **jamais mis à jour**
- `coordination_protocol::latest` — résultat du dernier run
- `coordination_protocol::best` — meilleur run selon `compute_protocol_score()` (déjà implémenté)

Namespace complet : `f"coordination_protocol::{adapter}::{config_hash}::{slot}"`
`config_hash` = `hashlib.md5(json.dumps({alpha, beta, model, preset}, sort_keys=True).encode()).hexdigest()[:8]`

### Fichiers à modifier

#### 1. `core/marker_store.py`
Ajouter deux méthodes publiques :

```python
def save_protocol_marker(
    self,
    *,
    slot: str,           # "baseline" | "latest" | "best"
    namespace: str,      # f"coordination_protocol::{adapter}::{config_hash}"
    payload: dict[str, Any],
    agent_id: str = "system_protocol",
) -> None:
    """Upsert a coordination protocol marker in the persistent store."""
    marker_id = f"{namespace}::{slot}"
    ...

def load_protocol_marker(
    self,
    *,
    slot: str,
    namespace: str,
) -> dict[str, Any] | None:
    """Load one protocol slot. Returns None if absent."""
    marker_id = f"{namespace}::{slot}"
    marker = self.get_marker(marker_id)
    if marker is None:
        return None
    return dict(marker.payload)
```

#### 2. `main.py`
Ajouter trois fonctions et les brancher dans `main()` :

```python
PROTOCOLS_DB_PATH = Path("pheromones/protocols.db")

def _build_protocol_namespace(config: dict[str, Any], adapter_name: str) -> str:
    """Stable namespace key for this (adapter, config) combination."""
    import hashlib, json
    key = {"adapter": adapter_name, "model": config.get("llm", {}).get("model", ""),
           "alpha": config.get("pressures", {}).get("alpha", 1.0),
           "beta": config.get("pressures", {}).get("beta", 1.0)}
    h = hashlib.md5(json.dumps(key, sort_keys=True).encode()).hexdigest()[:8]
    return f"coordination_protocol::{adapter_name}::{h}"

def _maybe_build_protocol_store(config: dict[str, Any]) -> MarkerStore | None:
    proto_cfg = dict(config.get("protocol", {}))
    if not bool(proto_cfg.get("enabled", False)):
        return None
    db_path = Path(str(proto_cfg.get("db_path", "pheromones/protocols.db")))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return MarkerStore(db_path=db_path, session_isolation=False, traceability=False)

def _maybe_apply_cross_run_protocol(
    config: dict[str, Any],
    protocol_store: MarkerStore | None,
    namespace: str,
) -> None:
    """Apply best protocol adaptations to config before run."""
    cross_run_cfg = dict(config.get("emergence", {}).get("cross_run", {}))
    if not bool(cross_run_cfg.get("enabled", False)):
        return
    if protocol_store is None:
        return
    # Charger baseline (jamais modifiée) pour le clamp
    baseline = protocol_store.load_protocol_marker(slot="baseline", namespace=namespace)
    best = protocol_store.load_protocol_marker(slot="best", namespace=namespace)
    if best is None or baseline is None:
        return
    adaptations = dict(best.get("adaptations", {}))
    if not adaptations:
        return
    max_delta = float(cross_run_cfg.get("max_total_delta", 0.15))
    clamped = clamp_cross_run_adaptations(adaptations, baseline["config"], max_total_delta=max_delta)
    for path, value in clamped.items():
        _set_config_path(config, path, value)   # helper dotted-path à ajouter

def _persist_protocol(
    result: Any,            # OrchestratorResult
    evaluation: dict[str, Any],
    config: dict[str, Any],
    protocol_store: MarkerStore | None,
    namespace: str,
    session_id: str,
) -> None:
    """Persist protocol state after run. Update best if score improved."""
    cross_run_cfg = dict(config.get("emergence", {}).get("cross_run", {}))
    if not bool(cross_run_cfg.get("enabled", False)):
        return
    if protocol_store is None:
        return
    if bool(cross_run_cfg.get("read_only", False)):
        return

    metrics = dict(result.emergence_summary)
    adaptations = compute_adaptations(metrics, config)
    score = compute_protocol_score(evaluation)

    payload_latest = {"metrics": metrics, "adaptations": adaptations,
                      "score": score, "session_id": session_id}
    protocol_store.save_protocol_marker(slot="latest", namespace=namespace, payload=payload_latest)

    # Sauvegarder baseline au premier run (jamais écrasée)
    if protocol_store.load_protocol_marker(slot="baseline", namespace=namespace) is None:
        protocol_store.save_protocol_marker(
            slot="baseline", namespace=namespace,
            payload={"config": dict(config), "session_id": session_id}
        )

    # Mettre à jour best uniquement si meilleur score
    current_best = protocol_store.load_protocol_marker(slot="best", namespace=namespace)
    if current_best is None or score > float(current_best.get("score", -1e9)):
        protocol_store.save_protocol_marker(slot="best", namespace=namespace, payload=payload_latest)
```

Ajouter `_set_config_path(config, path, value)` helper (applique un chemin pointé, ex: `"agents.selection_temperature"`) :

```python
def _set_config_path(config: dict[str, Any], path: str, value: Any) -> None:
    keys = [k for k in str(path).split(".") if k]
    if not keys:
        return
    cursor: Any = config
    for key in keys[:-1]:
        if not isinstance(cursor, dict) or key not in cursor:
            return
        cursor = cursor[key]
    if isinstance(cursor, dict):
        cursor[keys[-1]] = value
```

Dans `main()`, appeler dans cet ordre :
1. `protocol_store = _maybe_build_protocol_store(config)` — avant `environment`
2. `namespace = _build_protocol_namespace(config, args.adapter)` — avant environment
3. `_maybe_apply_cross_run_protocol(config, protocol_store, namespace)` — après `_build_config`, avant `environment`
4. `_persist_protocol(result, evaluation, config, protocol_store, namespace, session_id)` — après `evaluation`

### Tests à écrire

`tests/unit/test_protocol_persistence.py` :
- `save_protocol_marker` / `load_protocol_marker` round-trip
- `best` non écrasé si score inférieur
- `baseline` jamais écrasé au second appel

`tests/integration/test_protocol_cross_run.py` :
- 2 runs successifs en mode `cross_run.enabled: true`
- Run 2 : au moins une clé de config modifiée par rapport au run 1

---

## T3 — Protocol Compiler (C1) — Ce qui reste

T3 est à ~80%. Ce qui manque :

1. **`TravelPlannerAdapter.compile_protocol()`** — l'implémentation existe dans `AssistantAdapter` mais pas dans `TravelPlannerAdapter`. À implémenter dans `adapters/travelplanner/adapter.py` (même pattern que AssistantAdapter).

2. **Test d'intégration** `tests/integration/test_protocol_compiler_integration.py` :
   - Objectif novel domain → protocole valide → au moins 1 marker `completed`
   - Output LLM invalide → fallback `initial_markers()` sans exception

---

## Ordre d'implémentation recommandé

```
1. T1 core/environment.py  (_maybe_promote_to_skill)
2. T1 core/agent.py        (_recall_skills)
3. T1 main.py              (_maybe_build_skills_store + branchement)
4. T1 tests                (unit + integration)

5. T2 core/marker_store.py (save/load_protocol_marker)
6. T2 main.py              (4 fonctions + _set_config_path)
7. T2 tests                (unit + integration)

8. T3 adapters/travelplanner/adapter.py  (compile_protocol)
9. T3 tests/integration                  (test novel domain)
```

---

## Gate de validation finale

```bash
# Non-régression Sprint 8 — doit rester ≥ 77 passed
uv run pytest tests/unit/test_config.py tests/unit/test_marker_store.py \
  tests/unit/test_environment.py tests/unit/test_agent.py \
  tests/unit/test_orchestrator.py tests/unit/test_travelplanner_tools.py -q

# Tests Sprint 9 existants — doit passer
uv run pytest tests/unit/test_emergence.py tests/unit/test_protocol_compiler.py -q

# Nouveaux tests Sprint 9 (à écrire)
uv run pytest tests/unit/test_environment_skill_promotion.py \
  tests/unit/test_protocol_persistence.py \
  tests/integration/test_skill_persistence.py \
  tests/integration/test_protocol_cross_run.py -q

# Smoke test end-to-end adapt mode
uv run python main.py --adapter travelplanner \
  --config config/travelplanner_adapt.yaml --objective "Query 0"
# JSON de sortie doit contenir :
# - emergence_summary présent
# - (si 2ème run) coordination_protocol_applied: true
```

---

## Références fichiers clés

| Fichier | Rôle |
|---------|------|
| `core/environment.py` | Ajouter `skills_store` param + `_maybe_promote_to_skill` |
| `core/agent.py` | Ajouter `_recall_skills` |
| `core/marker_store.py` | Ajouter `save/load_protocol_marker` |
| `main.py` | Brancher skills_store, protocol_store, 4 nouvelles fonctions |
| `core/tool_registry.py` | Convention `credited_lesson_ids` (commentaire déjà en place) |
| `core/emergence.py` | `compute_protocol_score`, `clamp_cross_run_adaptations` — **déjà implémentés** |
| `core/schemas.py` | `ProtocolSpec` — **déjà implémenté** |
| `llm/prompts.py` | `SYSTEM_PROTOCOL_COMPILER` — **déjà implémenté** |
| `adapters/base.py` | `compile_protocol()` — **déjà implémenté** |
| `adapters/assistant/adapter.py` | `compile_protocol()` — **déjà implémenté** |
| `config/default.yaml` | Toutes les clés Sprint 9 — **déjà en place** |
| `config/travelplanner_adapt.yaml` | Preset apprentissage — **déjà créé** |
| `config/travelplanner_eval.yaml` | Preset évaluation figée — **déjà créé** |
