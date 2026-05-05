# V7.1 MigrationBench — Handoff d'implémentation

> Destinataire : agent d'implémentation. Tu n'as PAS besoin de re-faire l'audit, c'est terminé.
> Lis le diagnostic, applique les fixes dans l'ordre exact, vérifie chaque étape avec la procédure indiquée.
> Tout doit rester opt-in : V6 (`stigmergic_v6_static`) ne bouge pas, seul le bras `stigmergic_v7_repair_colony` est touché.

## Statut d'implémentation 2026-05-02

V7.1 est implémentée côté code et unitaires ciblés :
- Le modèle reste `deepseek-v4-flash`.
- La télémétrie V7 assigne réellement `branch_count`, `repair_cycles`, `failure_taxonomy`, `caps_hit`, `llm_calls` et les métriques du pool élastique au lieu de laisser les valeurs vides du contrat.
- Le parser d'édition accepte les variantes LLM courantes (`file/content`, `old/new`, `replace`) puis revalide strictement en `TypedEditSet`.
- `RunBuildValidationTool` calcule une validation official-like et impose `compiled_major_version_ok == (class_versions == {61})` pour Java 17.
- `select_patch_candidate` reste strict : sélection normale seulement si `build_success=True`; les patchs partiels ne sortent que via `best_partial_finalization=True` avec raison explicite.
- Les lessons sont explicitement désactivées pour `workflow: v7_repair_colony` via `lessons.enabled: false` et une garde runtime.
- `--force` nettoie les DB/audit/artifacts par instance via un helper léger, et `scripts/migrationbench_smoke_gate.py` vérifie les gates techniques avant `main_30`.

Validation locale : `uv run pytest tests/unit/test_migrationbench_v7_repair_colony.py tests/unit/test_orchestrator.py -q` -> **29 passed** ; `uv run pytest tests/unit/test_migrationbench_adapter.py tests/unit/test_migrationbench_workspace.py tests/unit/test_migrationbench_evaluator.py -q` -> **6 passed** ; `uv run python -m py_compile ...` -> OK.

---

## 0. Contexte (lecture obligatoire avant tout commit)

Campagne courante (`campaign_results/migrationbench/migrationbench_v6v7/stigmergic_v7_repair_colony/` — DeepSeek, subset `main_30`) : **0/30 strict_success, 0/30 official_success, ~9/30 patchs livrés/applicables, 20/30 `missing_final_patch`, 1/30 timeout**, 7M tokens, 1228 LLM calls.

Vérité terrain extraite de `markers.db` d'une instance "missing_final_patch" : 162 markers `patch_hypothesis` créés (b1→b40+), 86 lessons, 6 tasks, **historique typique `[created, pending->planning, planning->terminal]`**, `failure_taxonomy=class_version_error`, `eligible_actions=[classify_build_failure]`, build Maven a tourné mais `Unsupported class file major version 61` (Spring Boot 1.x → ASM ne lit pas le bytecode Java 17).

**Le framework tourne mécaniquement. Il ment sur ce qu'il a fait, et il n'a pas de porte de sortie quand aucun build ne passe.**

Causes racines (par ordre de priorité d'impact) :

| # | Cause | Fichier:lignes |
|---|---|---|
| C1 | Le contract de sortie ment : `branch_count`, `repair_cycles`, `failure_taxonomy`, `caps_hit`, `dynamic_agents_*` retombent à 0/"" dès que `finalize_evaluated_patch` n'a pas tourné, à cause d'un `setdefault` sur des clefs déjà pré-remplies par `empty_output_contract`. | `scripts/run_migrationbench_query_export.py:191-242` |
| C2 | Schéma d'édition mismatch : DeepSeek émet souvent `{"file":..., "content":...}` ou `{"replace":...}`, notre Pydantic `TypedEdit` exige `{"type":"replace_text","path":...,"old":...,"new":...}`. Pydantic raise → exception silencieusement catchée → fallback `deterministic_java17_pom_edits` qui ne match que 8 strings littéraux → `empty_typed_edits` → `patch_apply_error`. | `adapters/migrationbench/tools.py:67-81` (`parse_typed_edit_set`), `adapters/migrationbench/schemas.py` (TypedEdit) |
| C3 | Pas de retry après ValidationError Pydantic ; on tombe direct sur le fallback déterministe. | `adapters/migrationbench/tools.py:294-307, 430-447, 711-732` |
| C4 | `evaluate_run` n'accepte un marker `::finalize_evaluated_patch` que si `"strict_success" in payload`. Le chemin "cap atteint" pose un marker sans cette clef → ignoré → `failure_reason="missing_final_patch"` masque un vrai `repair_cap_reached:<taxonomy>`. | `adapters/migrationbench/adapter.py:210-235`, `adapters/migrationbench/tools.py:973-995` (`_final_marker_from_payload`) |
| C5 | Pas d'écope "best partial patch" quand le cap est atteint sans qu'aucune branche ne passe le build. La fonction `_best_patch_payload` existe mais n'est jamais appelée. | `adapters/migrationbench/tools.py:231-244, 627-678` |
| C6 | `run_build_validation` confond compile-passe / tests-passent : `mvn clean verify` échoue sur des deps tierces incompatibles Java 17 (ASM ancien, Spring Boot 1.x, lombok ancien) alors que le code source migre proprement. Pas de chemin "compile OK + tests KO sur dep tierce → quand même candidat". | `adapters/migrationbench/tools.py:577-624` |
| C7 | `_feedback_digest` retourne les 12k derniers chars bruts du log Maven → 90% de lignes `Progress (n): X kB | Y/Z kB`. Le `[ERROR]` réel n'arrive PAS au LLM de repair → le repair ne corrige rien. | `adapters/migrationbench/tools.py:150-153` |
| C8 | `RepairPatchCandidateTool` n'envoie pas l'historique des branches déjà tentées au LLM → la LLM réémet des variantes proches → 24 branches identiques → cap atteint sans diversité. | `adapters/migrationbench/tools.py:681-764` |
| C9 | Pool d'agents élastique inerte (`dynamic_agents=2`) : `_unblocked_marker_count` exclut les markers `state="planning"` (pourtant du travail réservé), donc target=2 toujours. | `core/orchestrator.py:381-393` |
| C10 | Poids `pressures.default_weights` font préférer `propose_patch_candidate` (1.0) à `apply_patch_candidate` (0.9) → backlog non appliqué. | `config/migrationbench_v7_repair_colony_deepseek.yaml` (section `pressures`) |
| C11 | À vérifier empiriquement : potentielle pollution de `markers.db` (deux `objective_id` distincts dans une même DB). `MarkerStore` est instancié `session_isolation=False`, et `--force` ne nettoie pas `markers.db` / `audit_log.jsonl` / `branches/`. | `scripts/run_migrationbench_query_export.py:153-159`, `adapters/migrationbench/workspace.py:153-169` |
| C12 | Bruit lesson : 86 markers `lesson` par instance créés via `_maybe_promote_to_skill` → compétition d'attention agent à chaque tick. | `core/environment.py:223-236` |

**Principe à NE PAS violer** (voir `CLAUDE.md` § Design Principles) : *Role-free agents: same agent logic, specialization through pressures, local sensing, and marker availability*. Donc **PAS d'agents typés** (pas de `schema_repair_agent`, pas de `pom_repair_agent`). La spécialisation reste émergente via les poids, l'intensité, et `eligible_actions` des markers. Si tu veux pousser la spécialisation, ajuste les poids et la formule de pression — pas le pool d'agents.

---

## 1. Phase 0 — Restaurer la télémétrie (BLOQUANT, à faire EN PREMIER)

Sans ça, tu ne sauras pas si tes corrections suivantes ont marché.

### 1.1 Réparer le contract de sortie

**Fichier** : `scripts/run_migrationbench_query_export.py`, lignes 191–242.

État actuel :
```python
contract = empty_output_contract(...)  # pré-remplit branch_count=0, repair_cycles=0, etc.
contract["runtime_seconds"] = ...
# ...
contract.setdefault("branch_count", len({...}))   # ← no-op : la clef existe déjà
contract.setdefault("repair_cycles", max([...]))  # ← no-op
contract.setdefault("failure_taxonomy", "")
contract.setdefault("caps_hit", {})
```

Cible :
- Calculer ces métriques DEPUIS `result.final_snapshot.markers` (extraire les `patch_hypothesis`, dériver `branch_count` = nombre de `branch_id` distincts non vides, `repair_cycles` = max `attempt`, `failure_taxonomy` = taxonomie du marker patch_hypothesis le plus récent ayant `attempt == repair_cycles`).
- **Assigner inconditionnellement** (`contract["branch_count"] = ...`), pas `setdefault`. Idem pour `dynamic_agents_*` extraits de `result.emergence_summary["agent_pool"]`.
- Ajouter dans `contract["summary"]` un sous-champ `markers_by_type` = `Counter(marker.marker_type for marker in result.final_snapshot.markers)` pour audit visuel.

### 1.2 Réparer `evaluate_run`

**Fichier** : `adapters/migrationbench/adapter.py`, lignes 210–235.

État actuel :
```python
if (
    marker_type == "task"
    and (...marker_id endswith finalize...)
    and "strict_success" in payload
):
    final_payload = payload
```

Cible : remplacer `"strict_success" in payload` par toujours accepter le marker `::finalize_*` ; lire `payload.get("strict_success", False)` à la place.

### 1.3 Réparer `_final_marker_from_payload`

**Fichier** : `adapters/migrationbench/tools.py`, lignes 973–995.

Cible : toujours injecter `strict_success=False`, `official_success=False`, `patch_applies=<bool depuis payload>`, `failure_reason=<reason>` dans le payload du marker final, quel que soit le chemin (cap, classification finale, succès).

### 1.4 Vérification phase 0

```bash
uv run python -m pytest tests/unit/test_migrationbench_v7_repair_colony.py -q
```

Puis re-export d'un instance EXISTANTE de la campagne actuelle (sans rerun, juste pour vérifier que la nouvelle logique extraie bien `branch_count > 0` depuis l'ancienne `markers.db`) :

```bash
# Script ad-hoc à écrire ou un test ciblé
uv run python -c "
import json
from pathlib import Path
from core.marker_store import MarkerStore
db = Path('campaign_results/migrationbench/migrationbench_v6v7/stigmergic_v7_repair_colony/instances/15093015999__ejserver_artifacts/markers.db')
store = MarkerStore(db_path=db, session_isolation=False)
markers = store.snapshot().markers
patch = [m for m in markers if m.marker_type == 'patch_hypothesis']
print('patch_hypothesis count:', len(patch))
print('distinct branch_id:', len({m.payload.get('branch_id','') for m in patch if m.payload.get('branch_id')}))
print('max attempt:', max([m.payload.get('attempt',0) for m in patch] or [0]))
"
```

Sortie attendue : `patch_hypothesis count: 162, distinct branch_id: ~40, max attempt: ~40`. Si oui, la télémétrie est récupérable côté code → tu peux procéder.

---

## 2. Phase 1 — Schéma d'édition robuste

### 2.1 Normaliser les clefs LLM

**Fichier** : `adapters/migrationbench/tools.py`, fonction `parse_typed_edit_set` (lignes 67–81).

Avant le `TypedEditSet.model_validate(json.loads(text))`, normaliser le dict :
- Si `edit` contient `file` mais pas `path` → renommer.
- Si `edit` contient `content` mais pas `new` ou n'est pas `write_file` → mapper en `type="write_file"`, `path=path`, `content=content`.
- Si `edit` contient `replace` (string) sans `type` → traiter comme `type="replace_text"`.
- Si `edit` contient `old`/`new` sans `type` → forcer `type="replace_text"`.
- Si `edit` contient `expected_replacements` absent → défaut 1.

Garder le résultat strictement compatible avec `TypedEdit` Pydantic (cf. `adapters/migrationbench/schemas.py`).

### 2.2 Retry après ValidationError

**Fichier** : `adapters/migrationbench/tools.py`, `ProposePatchCandidateTool.execute` (lignes 415–490) et `RepairPatchCandidateTool.execute` (lignes 689–764).

Encapsuler l'appel LLM dans une boucle :

```python
for attempt in range(2):  # 1 retry max
    try:
        response = await llm_client.acall(prompt=prompt, system=SYSTEM_*, response_schema=TypedEditSet)
        parsed = response.parsed if response.parsed is not None else response.content
        edits = parse_typed_edit_set(parsed)  # normalisation + validation
        break
    except (ValidationError, json.JSONDecodeError) as exc:
        if attempt == 0:
            # Re-prompt avec l'erreur injectée
            prompt = f"{prompt}\n\nYour previous response failed schema validation: {exc}\nReturn STRICT JSON matching the schema, no prose."
            continue
        llm_failure = f"{type(exc).__name__}:{exc}"
        edits = deterministic_java17_pom_edits(workspace)
```

Logger `llm_failure` dans le payload même en cas de succès au retry (pour télémétrie).

### 2.3 Validateur "le patch doit modifier au moins un fichier pertinent"

Avant de créer la `patch_hypothesis`, vérifier que `edits.edits` n'est pas vide ET qu'au moins un edit cible un fichier réellement présent dans `workspace.list_targets()` (pom.xml ou *.java sous `src/`). Sinon, ne pas créer la branche : marquer le marker source `failure_taxonomy="empty_or_irrelevant_edits"` et déposer une `ValidationResult` qui demande un retry de propose (pas un repair classique).

### 2.4 Vérification phase 1

Tests unitaires à ajouter dans `tests/unit/test_migrationbench_v7_repair_colony.py` :
- `test_parse_typed_edit_set_normalizes_file_to_path`
- `test_parse_typed_edit_set_normalizes_content_to_write_file`
- `test_propose_patch_retries_after_pydantic_error`
- `test_propose_patch_rejects_empty_edits_with_taxonomy`

```bash
uv run python -m pytest tests/unit/test_migrationbench_v7_repair_colony.py -q
```

---

## 3. Phase 2 — Validation alignée MigrationBench officiel

### 3.1 Décomposer `RunBuildValidationTool`

**Fichier** : `adapters/migrationbench/tools.py`, lignes 577–624.

Cible : remplacer le single `mvn clean verify` par une séquence avec champs séparés dans le payload :
- `dependency_resolution` : `mvn dependency:resolve` (timeout court 300s)
- `compile` : `mvn clean compile`
- `test` : `mvn -DskipTests=false test`
- `class_version_check` : pour chaque `target/classes/**/*.class` produit par le repo (pas par les deps), vérifier `javap -verbose` et exiger exactement `{61}` pour Java 17.
- `test_count` : parser `target/surefire-reports/TEST-*.xml` et stocker `tests_run_count`. Comparer au `tests_run_count` du commit base (si stocké dans `instance.stats.num_test_cases`, sinon stocker au premier passage).

Champs résultants dans `payload` :
- `dependency_resolution_success: bool`
- `compile_success: bool`
- `test_success: bool`
- `compiled_major_version_ok: bool` (ensemble des major versions compilées exactement égal à `{61}`)
- `test_count_non_decreasing: bool`
- `build_success: bool` = AND des 5

### 3.2 Sélection stricte

**Fichier** : `adapters/migrationbench/tools.py`, `RunBuildValidationTool` et `SelectPatchCandidateTool`.

`eligible_actions` après `run_build_validation` :
- Si `build_success=True` (patch applies, verify OK, class versions exactement `{61}`, test count non-régressif si connu) → `["select_patch_candidate"]`, `quality_score=0.85`.
- Sinon → `["classify_build_failure"]`.

`SelectPatchCandidateTool` : refuser normalement tout patch dont `build_success=False`. Seule exception : un marker explicitement créé par la porte de sortie `best_partial_finalization=True`, avec `failure_reason` tracé.

### 3.3 Vérification phase 2

Test ciblé : mocker `run_maven`, `_class_major_versions` et `_surefire_test_count` pour vérifier séparément le chemin `class_versions == {61}` (sélection possible) et `class_versions == {52, 61}` (sélection refusée).

---

## 4. Phase 3 — Écope cap + repair de qualité

### 4.1 Porte de sortie "best partial patch"

**Fichier** : `adapters/migrationbench/tools.py`, `ClassifyBuildFailureTool` (lignes 627–678).

Quand `attempt >= _repair_cap(environment)` :
- Appeler `_best_patch_payload(environment)` pour récupérer le payload de la meilleure branche existante (score = `quality_score` + bonus `compile_success` + bonus `patch_applies`).
- Si `_best_patch_payload` retourne non vide ET `compile_success` ou `patch_applies` est vrai sur cette branche : créer un nouveau marker `select_patch_candidate` avec `selected_for_official_eval=True`, `eligible_actions=["finalize_evaluated_patch"]`, `failure_taxonomy="repair_cap_reached:<original_taxonomy>"`. Cela force `FinalizeEvaluatedPatchTool` à tourner sur la moins-pire branche.
- Sinon : créer le marker final avec `failure_reason="repair_cap_reached:no_buildable_branch"`.

Dans tous les cas, le contract final sera lisible (plus de `missing_final_patch` masqué).

### 4.2 Digest Maven utile

**Fichier** : `adapters/migrationbench/tools.py`, fonction `_feedback_digest` (lignes 150–153).

Remplacer le tail brut par une extraction ciblée :
1. Extraire tous les blocs commençant par `[ERROR]`, garder jusqu'à la prochaine ligne vide ou max 30 lignes.
2. Extraire toutes les lignes `Caused by:` et les 5 lignes suivantes.
3. Extraire la ligne `Tests run: N, Failures: F, Errors: E, Skipped: S`.
4. Extraire la ligne `BUILD FAILURE` et les 3 lignes suivantes.
5. Extraire la dernière ligne du log brut (souvent l'exit message).

Concaténer dans cet ordre, cap final à 4 000 caractères. Si rien ne match (build OK), retourner les 1 000 derniers chars.

### 4.3 Historique des tentatives dans le prompt repair

**Fichier** : `adapters/migrationbench/tools.py`, `RepairPatchCandidateTool.execute` (lignes 681–764).

Avant `build_edit_prompt`, calculer :
```python
previous = sorted(_patch_markers(environment), key=lambda m: int(m.payload.get('attempt', 0)))
history = []
for m in previous[-8:]:
    p = m.payload
    history.append({
        "branch_id": p.get("branch_id"),
        "attempt": p.get("attempt"),
        "taxonomy": p.get("failure_taxonomy", ""),
        "files_modified": list((p.get("edit_application") or {}).get("files_modified", []))[:5],
        "key_error": _feedback_digest(p.get("build_feedback_digest", ""), max_chars=400),
    })
```

Injecter `previous_attempts` dans `prompt` (sérialisé JSON, < 6000 chars). Ajouter dans `SYSTEM_REPAIR_EDIT` une instruction explicite : *"Do not repeat an edit pattern already tried in `previous_attempts` if it produced the same `taxonomy`. Try a structurally different fix (e.g., bump dependency version instead of changing source)."*

### 4.4 Anti-loop : stop branche après 2 repairs identiques

Dans `RepairPatchCandidateTool` : si `failure_taxonomy` actuel == celui du parent ET `files_modified` actuel ⊆ `files_modified` du parent → ne pas créer de nouvelle branche, marquer le marker en `state="terminal"` avec `failure_taxonomy="anti_loop_repeated_repair"`.

---

## 5. Phase 4 — Orchestration & poids

### 5.1 Élargir `_unblocked_marker_count`

**Fichier** : `core/orchestrator.py`, lignes 381–393.

Compter aussi les markers `state="planning"` avec `eligible_actions` non vides (= travail réservé / en cours mais agent assigné) en plus des `pending` non lockés. La formule cible du pool reflète alors la demande réelle.

```python
def _unblocked_marker_count(self, snapshot: EnvironmentSnapshot) -> int:
    terminal_ids = {m.id for m in snapshot.markers if m.state in TERMINAL_STATES}
    pending_unblocked = [
        m for m in snapshot.markers
        if m.state == "pending" and m.lock_owner is None
    ]
    in_flight = [
        m for m in snapshot.markers
        if m.state == "planning" and m.payload.get("eligible_actions")
    ]
    return len(unblocked_markers(markers=pending_unblocked, terminal_ids=terminal_ids)) + len(in_flight)
```

### 5.2 Rééquilibrer les poids

**Fichier** : `config/migrationbench_v7_repair_colony_deepseek.yaml`, section `pressures.default_weights`.

```yaml
pressures:
  formula: "aco"
  alpha: 1.0
  beta: 2.0
  default_weights:
    inspect_repository: 1.0
    localize_migration_surface: 1.0
    propose_patch_candidate: 0.9
    apply_patch_candidate: 1.0       # ← monté
    run_build_validation: 0.95       # ← monté
    classify_build_failure: 0.95
    repair_patch_candidate: 0.9      # ← légèrement baissé
    select_patch_candidate: 1.0
    finalize_evaluated_patch: 1.0
    think: 0.2
```

Logique : on préfère faire avancer une branche existante (apply → build → classify → select → finalize) plutôt que d'en empiler de nouvelles (propose / repair).

### 5.3 Désactiver la promotion lesson pour V7

**Option A (config + garde runtime, retenue)** : ajouter dans `config/migrationbench_v7_repair_colony_deepseek.yaml` :
```yaml
lessons:
  enabled: false
```
`reinforcement.enabled=false` ne suffit pas : `core/environment.py` doit vérifier `lessons.enabled` et désactiver par défaut les lessons quand `migrationbench.workflow == "v7_repair_colony"`.

**Option B (fallback)** : garder aussi le flag `skill_library.enabled=false` pour éviter toute promotion cross-run.

### 5.4 Aligner le modèle DeepSeek

**Fichier** : `config/migrationbench_v7_repair_colony_deepseek.yaml`, section `llm.model`.

Conserver `"deepseek-v4-flash"`. Ne pas basculer vers les anciens alias `deepseek-chat` ou `deepseek-reasoner` pour ce bras : la campagne MigrationBench V7.1 utilise l'ID DeepSeek V4 Flash direct.

---

## 6. Phase 5 — Isolation & gates

### 6.1 Hard-clean avec `--force`

**Fichier** : `scripts/run_migrationbench_query_export.py`, autour des lignes 130–170 (création de `markers.db`, `audit_log.jsonl`, workspace).

Quand `args.force` est vrai :
- Avant `MarkerStore(...)`, supprimer `markers.db`, `markers.db-wal`, `markers.db-shm`.
- Supprimer `audit_log.jsonl` du même dir.
- `MigrationBenchWorkspace.prepare(force=True)` doit aussi nettoyer `branches/` et `verification/` (vérifier `workspace.py:153-169`).

### 6.2 Vérifier l'isolation `markers.db`

Vérifier empiriquement avec :
```bash
for db in campaign_results/migrationbench/migrationbench_v6v7/stigmergic_v7_repair_colony/instances/*_artifacts/markers.db; do
  echo "$db"
  sqlite3 "$db" "SELECT DISTINCT json_extract(payload_json,'\$.objective_id') FROM markers WHERE marker_type='patch_hypothesis';"
done | head -40
```

Si une DB contient plus d'un `objective_id` distinct → le harness pollue. Dans ce cas, passer `session_isolation=True` à `MarkerStore` dans `run_migrationbench_query_export.py:153-159`. Vérifier que ça n'empêche pas `query_markers(marker_type="patch_hypothesis")` de retourner les markers nécessaires (la session_id étant unique par run, OK).

### 6.3 Gate `smoke_5` (NOUVEAU script)

**Fichier à créer** : `scripts/migrationbench_smoke_gate.py`.

Lance la campagne sur `fixtures/migrationbench/subsets/smoke_5.jsonl` et vérifie ces gates AVANT d'autoriser un `main_30` :

| Gate | Condition | Action si faux |
|---|---|---|
| Télémétrie | Pour chaque instance, le contract a `branch_count > 0` SI `markers.db` contient des `patch_hypothesis`. | Échec, exit 1 |
| Schéma | Aucun fichier de log ne contient `pydantic.ValidationError` ou `JSONDecodeError` non rattrapé. | Échec |
| Isolation | Chaque `markers.db` contient exactement 1 `objective_id` distinct. | Échec |
| Chemin chaud | Au moins 1 instance sur 5 a un marker `select_patch_candidate` élu (chemin complet parcouru). | Échec |
| Logs propres | `_feedback_digest` dans les payloads patch_hypothesis fait < 4500 chars. | Warning |

**Ne PAS gater sur `strict_success` ou `official_success`** — le bench est dur, ces métriques restent l'objectif scientifique, pas un critère technique. Sinon le gate bloque indéfiniment.

Lancement :
```bash
DEEPSEEK_API_KEY=$(grep DEEPSEEK_API_KEY .env | cut -d= -f2) \
  uv run python scripts/migrationbench_smoke_gate.py \
    --config config/migrationbench_v7_repair_colony_deepseek.yaml \
    --subset fixtures/migrationbench/subsets/smoke_5.jsonl \
    --out-dir campaign_results/migrationbench_v7_smoke_gated
```

Exit 0 si tous les gates passent, exit 1 sinon avec rapport détaillé sur stderr.

---

## 7. Tests unitaires obligatoires

Ajoutés dans `tests/unit/test_migrationbench_v7_repair_colony.py` :

1. `test_parse_typed_edit_set_normalizes_file_key`
2. `test_parse_typed_edit_set_normalizes_content_to_write_file`
3. `test_propose_patch_retries_on_pydantic_error`
4. `test_propose_patch_rejects_empty_edits`
5. `test_build_validation_requires_exact_java17_class_major_version`
6. `test_build_validation_selects_only_when_official_like_checks_pass`
7. `test_select_patch_candidate_rejects_unvalidated_patch`
8. `test_select_patch_candidate_allows_explicit_best_partial_patch`
9. `test_repair_patch_avoids_repeated_taxonomy_with_same_files`
10. `test_feedback_digest_extracts_error_blocks`
11. `test_v7_lessons_are_disabled_by_workflow_default`
12. `test_force_clean_removes_marker_audit_and_artifacts`

Et étendre `tests/unit/test_orchestrator.py` :

13. `test_elastic_pool_counts_planning_markers_with_eligible_actions`

Validation systématique :
```bash
uv run python -m pytest \
  tests/unit/test_migrationbench_v7_repair_colony.py \
  tests/unit/test_orchestrator.py \
  tests/unit/test_migrationbench_adapter.py \
  tests/unit/test_migrationbench_workspace.py \
  tests/unit/test_migrationbench_evaluator.py \
  -q
```

Cible locale actuelle : **29 tests** sur V7.1 + orchestrateur, puis **6 tests** MigrationBench adapter/workspace/evaluator.

---

## 8. Tests d'intégration Docker

Une fois les unitaires verts :

```bash
# Smoke gate (5 instances)
DEEPSEEK_API_KEY=$(grep DEEPSEEK_API_KEY .env | cut -d= -f2) \
MIGRATION_CONFIG=config/migrationbench_v7_repair_colony_deepseek.yaml \
MIGRATION_FRAMEWORKS="stigmergic_v7_repair_colony" \
MIGRATION_OUT_DIR=campaign_results/migrationbench_v7_smoke \
MIGRATION_SUBSET=fixtures/migrationbench/subsets/smoke_5.jsonl \
MIGRATION_FORCE=true \
  docker compose -f docker-compose.campaign.yml up migrationbench-campaign

uv run python scripts/migrationbench_smoke_gate.py \
  --report campaign_results/migrationbench/migrationbench_v7_smoke
```

Si tous les gates passent → autoriser le rerun `main_30` (commande dans `CLAUDE.md` § *MigrationBench V7*).

---

## 9. Périmètre — ce qu'il NE FAUT PAS toucher

- Le contrat `Marker` (`core/marker.py`) — pas d'ajout de champ.
- L'API `MarkerStore` (`core/marker_store.py`) — pas de nouvelle méthode.
- Le state machine global — les transitions actuelles suffisent.
- La branche V6 (`stigmergic_v6_static`) : 0 régression, vérifier avec `tests/unit/test_migrationbench_adapter.py` (V6 cases).
- L'évaluateur officiel (`adapters/migrationbench/evaluator.py`) : sa commande `mvn clean verify` reste intouchée — la décomposition compile/test est INTERNE au bras V7.
- Pas d'agents typés. Spécialisation = poids + intensité + `eligible_actions`. Si tu te surprends à écrire `class SchemaRepairAgent`, arrête-toi : tu as raté le brief.

---

## 10. Position scientifique (pour le mémoire)

Cette V7.1 ne sera PAS présentée comme "preuve que la stigmergie surperforme sur MigrationBench". Elle sera présentée comme :

1. *V1 de la colonie de réparation* sur un bench dur (Java 8→17 build complet).
2. *Diagnostic d'ingénierie* : la V7 initiale était cassée à 3 endroits (télémétrie, schéma LLM, porte de sortie). La V7.1 corrige et relivre.
3. *Comparaison équitable* : V7.1 vs V6 vs Agentless / SD-Feedback / SWE-agent dans les conditions strictes du gate `official_like_validation`.

Sources alignées (à citer dans le commit final et le sprint artifact) :
- MigrationBench (https://arxiv.org/abs/2505.09569)
- Self-Debugging (https://arxiv.org/abs/2304.05128)
- SWE-agent (https://arxiv.org/abs/2405.15793)
- Agentless (https://arxiv.org/abs/2407.01489)
- ReAct (https://arxiv.org/abs/2210.03629)
- Tree of Thoughts (https://arxiv.org/abs/2305.10601)
- LATS (https://arxiv.org/abs/2310.04406)
- Voyager (https://arxiv.org/abs/2305.16291)
- Stigmergic MARL (https://arxiv.org/abs/2105.03546)
- ACO review (https://arxiv.org/abs/1908.08007)

---

## 11. Ordre d'exécution résumé

1. **Phase 0** (télémétrie) → vérification 1.4
2. **Phase 1** (schéma) → tests 2.4
3. **Phase 2** (validation officielle-like) → test 3.3
4. **Phase 3** (cap escape + digest + repair history + anti-loop) → tests intégrés
5. **Phase 4** (orchestration + poids + lesson + model) → unitaires
6. **Phase 5** (isolation + gate) → smoke Docker
7. **Mise à jour doc** : `CLAUDE.md`, `AGENTS.md`, `documentation/redisgn_v2/sprint_09_artifact.md` (addendum V7.1).
8. **Capture knowledge** : `.codex/knowledge/captures.md`, `playbook.md`, `decision_log.md` — 1 entrée chacun.

---

## 12. Critères de done

- ✅ `pytest` ciblé passe : V7.1 + orchestrateur, puis adapter/workspace/evaluator.
- ✅ Smoke gate `smoke_5` Docker passe les 4 gates obligatoires.
- ✅ Sur l'ancienne `markers.db` de la campagne actuelle, le re-export montre `branch_count` et `repair_cycles` cohérents avec la DB (vérification rétroactive de la phase 0).
- ✅ Aucun `pydantic.ValidationError` non rattrapé dans les logs Docker.
- ✅ Au moins 1 instance smoke avec un marker `select_patch_candidate` élu.
- ✅ V6 inchangé : `tests/unit/test_migrationbench_adapter.py` (cases V6) verts.
- ✅ Documentation mise à jour (CLAUDE.md, AGENTS.md, sprint artifact).

Une fois ces 7 critères validés, la campagne `main_30` peut être relancée pour produire les chiffres scientifiques V7.1.
