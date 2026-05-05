# Phase 6 — Audit campagne budget=5/1/5 (partielle, A3 crashée à 25/30)

**Date** : 2026-05-05
**Subset** : `fixtures/migrationbench/subsets/main_30.jsonl`
**Seed** : 42
**LLM** : DeepSeek `deepseek-chat`
**Budget** : `max_candidates=5`, `max_repair_rounds=1`, `max_repairs_per_candidate=5`
**Service Docker** : `ablation-a3-vs-a4-budget`
**Out** : `campaign_results/v10/ablation_a3_vs_a4_budget5/`
**Statut** : **A3 a crashé à l'instance 26/30 (`packtpublishing`)** avec
`shutil.Error: [Errno 23] Too many open files in system`. **A4 jamais lancé.**

## 1. Ce qui a fonctionné — fix bug repair_provider validé

Le fix livré juste avant la campagne (`_attach_live_files` qui passe les
fichiers de la branche parente au repair_provider au lieu du base
workspace) **fonctionne et résout 79 % des échecs Phase 6 budget=2**.

### Comparaison failure types pre-fix vs post-fix

| Failure type | Phase 6 budget=2 (avant fix) | budget=5 (post-fix) |
|---|---|---|
| `replacement_count_too_low:pom.xml:actual=0` | **58/73 (79 %)** | **4/198 (2 %)** |
| `dependency_resolution_error` | 5 | **78 (39 %)** |
| `compile_error` | 5 | 32 (16 %) |
| `class_version_error` | 2 | 26 (13 %) |
| `test_failure` | 0 (n/a) | 18 (9 %) |
| `build_failure` | 6 | 17 (9 %) |

Lecture : avant le fix, 79 % des échecs étaient des hallucinations du LLM
sur le `pom.xml` (le LLM voyait le pom du base workspace, pas la branche
parente, et re-proposait `1.8 → 17` alors que la branche avait déjà `17`).
Après le fix, ce résiduel tombe à 2 % et les **vrais blocages
émergent** : Spring Boot ancien (deps qui ne résolvent plus), plugins
Maven obsolètes, classes compilées en Java 8 incompatibles avec Java 17.

C'est exactement le diagnostic que la pré-registration ADR Phase 5 v2
prévoyait, mais qui était masqué par le bug repair-provider.

## 2. Métriques A3 budget=5 sur 25 instances

```
Phase 6 budget=2 (réf, 30 inst)   →   budget=5 partiel (25 inst, +5 à venir)
  total candidats        80                 183  (~220 extrapolé sur 30)
  apply_ok               80                 172
  validated              4                  8 (+100%)
  strict_success         1/30               0/25  (mais comic_con jamais testé)
  instances finalisées   3/30               4/25  (artur, citymonstret, dickchesterwood, mtuhide)
```

Nouvelle instance qui finalise grâce au budget élargi :
**`dickchesterwood__fleetman__webapp`** (n'apparaissait pas dans les
résultats Phase 6 budget=2).

**Concurrence d'hypothèses validées (matière pour A4 quand il tournera)** :

| Instance | Phase 6 budget=2 | budget=5 |
|---|---|---|
| citymonstret | 2 validés | **4 validés** |
| mtuhide__cocotemp | 0 | **2 validés** |
| dickchesterwood | 0 | 1 validé (nouveau) |
| artur | 1 | 1 |
| comic_con | 1 (strict !) | non testé (crash) |

A4 aurait probablement émis plusieurs `signal.applied finalize_tiebreak`
sur ces instances. Mais on ne saura pas tant qu'on relance pas.

## 3. Bug critique n°2 — ENFILE (Too many open files in system)

**Trace d'erreur** (depuis `/tmp/phase6_budget5_log.txt`) :

```
File "/app/adapters_v10/migrationbench/workspace.py", line 146,
  in branch_workspace
    shutil.copytree(self.repo_dir, branch.repo_dir)
shutil.Error: [
  ('/app/workspaces/migrationbench_v10/packtpublishing__.../repo/...',
   '/app/workspaces/migrationbench_v10/packtpublishing__.../branches/c1_llm/repo/...',
   "[Errno 23] Too many open files in system: '...'")
]
```

**Cause racine** :

- `errno=23` = `ENFILE` = limite **système (kernel)** de FDs ouverts
  atteinte. Différent de `EMFILE` (limite par-process).
- À budget=5, chaque instance peut générer jusqu'à `5 + 1×5 = 10`
  branches via `shutil.copytree` du repo entier.
- À chaque `verify`, le verifier crée un répertoire `_verify/<cand_id>/`
  qui est encore une copie complète.
- Sur 25 instances cumulées, on a probablement plusieurs centaines de
  copies sur disque, et Maven sub-processes en cours qui maintiennent
  des FDs ouverts.
- Aucun cleanup intermédiaire des `_verify/` ou des branches
  abandonnées entre les instances.

**Impact** :

- A3 stop à 25/30 instances ;
- A4 jamais lancé → **comparaison A3 vs A4 budget=5 impossible** ;
- les 5 instances manquantes incluent `comic_con__museum` (la seule en
  strict_success en Phase 6) → la régression A4 < A3 sur cette instance
  ne peut pas être vérifiée à budget=5.

**Solutions par ordre de coût** :

| Solution | Effort | Robustesse |
|---|---|---|
| Cleanup `_verify/<cand_id>` après chaque `VerifierReport` produit | 30 min code + tests | Élimine la cause à la source |
| Ajouter `ulimits` au service Docker (`nofile`, `nproc`) | 5 min | Repousse la limite sans la résoudre |
| `shutil.ignore_patterns` pour exclure `target/`, `.git/` lors du `copytree` | 20 min | Réduit la pression I/O |
| Forcer `gc.collect()` + `shutil.rmtree` des branches après score.completed | 30 min | Hygiène de cycle |

Recommandation : **A1+A3 combinés** (cleanup `_verify` propre + skip
`target/`/`.git/`) pour une solution durable. A2 (ulimits) en parallèle
comme ceinture-bretelle.

## 4. Anomalies à investiguer (4 instances)

Quatre instances ont **tous leurs candidats appliqués mais aucun verdict
de validation enregistré** (val_pass=val_fail=0) :

| Instance | cands | apply_ok | val_pass | val_fail |
|---|---|---|---|---|
| `bjoernkw__oauth2__with__jira` | 7 | 7 | 0 | 0 |
| `jaroslavtulach__heapdump` | 6 | 6 | 0 | 0 |
| `runtimetools__javametrics` | 6 | 6 | 0 | 0 |
| `jodaorg__joda__beans` | 11 | 11 | 0 | 0 |

Hypothèses :

1. **Validation timeout** (`workspace_timeout_seconds=600`) — le `mvn
   verify` traîne et est tué avant d'écrire un event. Mais on aurait
   dû voir `validation.completed` avec status `error`.
2. **Status `error` non compté** par mon script d'analyse (qui filtre
   sur `passed/failed/error`) — possible faux négatif côté audit.
3. **Crash silencieux du Maven sub-process** — le verifier produit un
   `VerifierReport` mais l'event `validation.completed` n'est pas écrit.

À vérifier avec un grep sur les events de ces 4 instances.

## 5. Verdict avant relance

**Ne pas lancer budget=10** :

1. Bug ENFILE non corrigé → budget=10 = ~2× plus de copies → crash plus tôt.
2. A4 jamais testé à budget=5 → la question H2 reste ouverte.
3. Le verrou réel post-fix est `dependency_resolution_error` (39 %)
   et `compile_error/class_version_error` (29 %) → c'est le repo cassé,
   pas le LLM. Multiplier le budget LLM ne le réparera pas.
4. Les 4 anomalies de validation events doivent être comprises avant.

## 6. Plan recommandé

| Étape | Action | Effort estimé |
|---|---|---|
| **A** | Fix bug ENFILE : cleanup `_verify` post-VerifierReport + ignore_patterns sur copytree + ulimits container | 1-2 h |
| **B** | Relancer budget=5 **complète** (A3 + A4 sur 30 instances) | ~3 h Docker + audit |
| **C** | Investiguer les 4 instances avec val_pass=val_fail=0 | 30 min |
| **D** | Décider budget=10 sur la base du résultat budget=5 complet (A4 émet-il enfin des `signal.applied` significatifs ?) | dépend B |

Alternative à considérer : **skip budget=10 et pivoter vers Phase 8
Memory A6** (cross-run signal accumulation) si budget=5 confirme que
l'effet stigmergique reste marginal. C'est en Phase 8 que la stigmergie
prend toute sa puissance (une instance résolue dépose un SUPPORT qui
guide les 29 suivantes).
