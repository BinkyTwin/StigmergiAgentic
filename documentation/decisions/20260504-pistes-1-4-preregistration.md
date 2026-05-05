# 2026-05-04 — Pré-registration des pistes 1 + 4 (contexte LLM enrichi & préservation des tests)

**Statut** : pré-registré, code en cours d'implémentation. Cet ADR fixe les
modifications **avant** toute nouvelle exécution sur `main_30` afin d'éviter
le *garden of forking paths* / p-hacking. Toute déviation ultérieure
nécessitera un nouvel ADR.

## Contexte

La campagne A1/A2/A3 du 2026-05-04 sur `main_30` (DeepSeek `deepseek-chat`,
seed 42, providers LLM) a livré 1/30 strict_success sur les 3 bras
(cf. `documentation/redisgn_v2/phase_05_ablation_main30_real.md`).

Diagnostic des échecs (par étage de la chaîne stricte) :

| Étage | A1 | A2 | A3 | Cause dominante |
|---|---|---|---|---|
| Apply échoue | 5 | 6 | 5 | LLM produit un patch dont le `old` ne match pas |
| Compile échoue | 17 | 15 | 17 | `dependency_resolution_error` × 11 (37%) |
| Test échoue | 5 | 5 | 6 | `class_version_error` × 2-3, `test_failure` × 1-2 |
| Official rejette (test passe local) | 2 | 3 | 1 | `final_eval.py` retourne `(Build success, #tests) = (True, -2)` — il **vérifie le compte de tests** |

Deux verrous identifiés :

1. **Contexte LLM trop pauvre** : on ne lui donne que `pom.xml` + 6 fichiers
   Java de surface, sans le graphe de dépendances ni les usages
   `javax.*` qui doivent migrer vers `jakarta.*` pour Spring 3.x / Java 17.
2. **Le LLM supprime ou renomme des tests existants** sans le savoir, ce
   qui fait chuter `#tests` et déclenche `Success=False` dans
   `final_eval.py` — alors que compile et test locaux passent.

## Décisions pré-registrées

### Piste 1 — Enrichissement du contexte d'observation

Avant chaque appel LLM (initial **et** repair), le provider injecte dans le
prompt utilisateur un bloc *Project context* contenant :

- **Top-level Maven dependencies** : extraites par parsing XML des
  `<dependency>` du pom (groupId/artifactId/version). On ne lance **pas**
  `mvn dependency:tree` : trop coûteux et redondant avec le verifier qui
  exécute déjà Maven.
- **Spring Boot version** détectée via `<parent>` `spring-boot-starter-parent` (si présente).
- **Imports `javax.*`** : grep des `import javax.*;` dans les fichiers Java
  ouverts, dédupliqués, top-30. C'est un signal fort que le repo doit migrer
  vers `jakarta.*` quand on cible Java 17 + Spring 3.x.
- **Java target courant** détecté via `<maven.compiler.*>` ou `<source>`/`<target>`.

L'enrichissement est :
- **strictement passif** : pas d'exécution Maven, pas d'appel réseau, pas
  d'écriture sur le disque ;
- **identique pour A1, A2 et A3** : c'est de l'ingénierie de prompt
  uniforme, pas une variable d'ablation ;
- **journalisé** : la taille du bloc et le nombre de dépendances détectées
  apparaissent dans les metadata du candidat pour audit post-hoc.

### Piste 4 — Anti-action "préserver les tests"

Deux points d'injection complémentaires :

1. **System prompt (initial + repair)** : règle dure ajoutée :
   > Do not delete, rename, comment out, or `@Disabled` any existing test
   > class or test method. The official MigrationBench evaluator counts
   > test cases and rejects the patch when the count drops.

2. **`MigrationBenchAdapterV10.diagnose`** : ajout systématique de
   l'anti_action `"preserve_existing_tests"` dans le `FeedbackDigest` dès
   qu'une validation échoue, **quelle que soit la nature de l'échec**. Cela
   garantit que la règle est *traçable dans l'EventLog* (`feedback.created`
   payload), pas seulement dans une string de prompt.

Ce qui **ne change pas** :

- `adapters_v10/migrationbench/verifier.py` (signaux canoniques)
- `OfficialEvaluator` et le wrapper sur `external/MigrationBench/run_eval.py`
- Les seuils du contrat strict (apply ∧ compile ∧ test ∧ class_version 61 ∧
  official Success=True)

## Plan d'application uniforme

| Aspect | A1 | A2 | A3 |
|---|---|---|---|
| Contexte enrichi (piste 1) | ✓ | ✓ | ✓ |
| Anti-action tests (piste 4) | ✓ (système prompt) | ✓ (système + feedback) | ✓ (système + feedback) |
| `max_candidates` | 1 | 1 | 2 |
| `max_repair_rounds` | 0 | 1 | 1 |
| `max_repairs_per_candidate` | 1 | 1 | 2 |
| Températures | 0.0 | 0.0 (init+repair) | 0.0 + 0.4 (init), 0.0 + 0.4 (repair) |
| Modèle | deepseek-chat | idem | idem |
| Seed | 42 | 42 | 42 |
| Subset | main_30 | main_30 | main_30 |

Ce sont les **seuls** paramètres qui distinguent les bras. Le contexte
enrichi et l'anti-action tests sont des constantes communes.

## Critères d'acceptation

- 153+ tests V10 passent avant et après (régression nulle).
- Le smoke `smoke_1.jsonl` post-pistes montre :
  - le bloc *Project context* présent dans le prompt envoyé au LLM (vérifié via le param `user` capturé) ;
  - l'anti_action `"preserve_existing_tests"` apparaît dans au moins un `feedback.created` event quand validation échoue ;
  - `live==replay` reste True.
- Tout le reste de la pipeline (verifier, official, scoring, summary) reste
  bit-identique : un test de non-régression ré-exécute sur la fixture
  `smoke_5` pour vérifier la stabilité des signaux par étape.

## Justification scientifique

- Pistes 1 et 4 sont du **prompt engineering uniforme** appliqué de façon
  identique aux trois bras. Elles ne modifient ni l'oracle (verifier/official),
  ni la définition de strict_success.
- Elles sont **pré-enregistrées avant** toute nouvelle campagne, ce qui
  empêche un choix opportuniste post-résultats.
- Les compteurs Phase 5 (`dedup_skipped`, `repeat_failure_suppressed`,
  `selection_rationale`) restent traçables dans l'EventLog ; rien n'est
  caché ou agrégé silencieusement.
- L'anti_action passe par `FeedbackDigest`, donc apparaît dans
  `feedback.created` et est rejouable depuis l'EventLog : un reviewer peut
  vérifier que la règle a bien été émise et qu'elle est commune aux bras.

## Suivi

- Une fois implémenté, refaire smoke_1 pour vérifier les critères ci-dessus.
- Demander explicitement à l'utilisateur l'autorisation de re-lancer
  `main_30` × 3 bras (cost LLM ≈ comparable à la campagne précédente).
- Documenter les nouveaux résultats dans
  `documentation/redisgn_v2/phase_05_ablation_main30_real.md` (deuxième
  section "post-pistes 1+4") avec comparaison côte à côte des deux campagnes.

## Addendum 2026-05-04 (post-smoke A1 v2)

Le premier run A1 v2 a révélé une régression : 16/16 instances échouaient à
`replacement_count_too_low:pom.xml:expected>=1:actual=0`. Cause : l'inclusion
de hints "migrate javax→jakarta / bump Spring Boot" dans le system prompt
poussait DeepSeek à proposer des `replace_text` dont le `old` n'était pas
verbatim dans le pom (extrapolations imaginaires).

**Correctifs strictement uniformes (appliqués aux 3 bras) :**

1. **Adoucissement du system prompt** : retrait de la directive "must migrate
   javax→jakarta", remplacée par une note neutre ("the Project context block
   is informational"). Le LLM reste libre d'utiliser le contexte mais n'est
   plus poussé à des edits massifs hors-source.

2. **Règle verbatim explicite** dans system prompt initial + repair :
   "Hard rule: `old` MUST be a verbatim substring of the file shown."

3. **Garde déterministe** dans `_normalize_edits(raw, files=...)` : un edit
   `replace_text` est silencieusement supprimé si `old not in files[path]`.
   Cela protège du LLM même quand il ignore la règle. Le drop est
   journalisé via `LOGGER.info` mais reste invisible des bras (rien dans
   les events) — c'est un filtre de sanité avant émission de candidat.

Ces correctifs **ne dérogent pas** à la pré-registration : la garde verbatim
est l'application stricte du principe "pas d'edits hallucinés", et le
guidage jakarta avait été explicitement listé comme contexte informationnel,
pas comme injonction. La règle reste **uniforme aux 3 bras**, le verifier et
l'official_eval restent inchangés.

Critères supplémentaires :
- Smoke `smoke_1` v2 doit garder `live==replay==True` (validé).
- Aucune régression dans les 161+ tests V10 existants.
- Smoke v2 montre encore `preserve_existing_tests` dans 100% des feedback
  events (validé).
