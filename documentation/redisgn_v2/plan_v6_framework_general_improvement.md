# Plan V6 — Améliorations générales du framework à partir des signaux d'émergence

**Date** : 2026-04-18  
**Baseline empirique actuelle** : `v5_full` validation, `seed42` + `seed43`, `39/180` et `38/180` final passes  
**Score de référence** : **21.4% final pass combiné** (`77/360` query-runs)  
**Objectif V6** : améliorer le framework **sans modifier le benchmark**, le scorer officiel, ni la séparation entre logique générale et logique TravelPlanner

---

## Pourquoi cette réécriture

Le plan précédent allait globalement dans la bonne direction, mais il mélangeait deux choses :

- une **bonne lecture scientifique** du problème ;
- un **ordre d'exécution trop large** pour garder une attribution propre des gains.

Cette version conserve l'intuition centrale du plan initial, mais la rend plus exécutable :

- on commence par **sécuriser la baseline** avec des comparaisons à seeds appariées ;
- on **fusionne** les leviers de récupération et d'adaptation dynamique dans **un seul plan de contrôle** ;
- on réduit l'ablation à **3 bras V6** au lieu d'une échelle additive longue ;
- on **sort la décomposition persistante** de la première vague, car c'est une refonte de représentation, pas un simple tuning du runtime.

---

## Résumé exécutif

Les résultats `v5_full` corrigés (`max_response_tokens: 2048`) montrent que le problème `empty_plan` a disparu. Le régime d'échec dominant est désormais la **stagnation** (`idle_cycles`), particulièrement sur les queries multi-villes.

Cependant, il faut distinguer deux niveaux :

1. **Ce que les résultats suggèrent déjà**
   - les cas `7j / 3 villes` semblent sensibles à une fenêtre d'exécution plus longue ;
   - les cas `5j / 2 villes` semblent souffrir d'un problème plus structurel que purement temporel ;
   - la contention et le thrashing restent des suspects sérieux.

2. **Ce qu'on peut défendre méthodologiquement aujourd'hui**
   - la comparaison `idle=4` vs `idle=8/16` est **utile mais encore directionnelle**, car elle mélange les seeds ;
   - avant de dériver un cycle V6 complet, il faut **rejouer la baseline et `v6_base` sur les mêmes seeds**.

Conclusion pratique :

- **Phase 1 V6** doit rester centrée sur des leviers runtime **petits, généraux, attribuables** ;
- **Phase 2 V6.2** pourra ouvrir les chantiers plus lourds de représentation de tâche si les `5j` restent bloqués.

---

## Baseline de départ — lecture conservatrice

### Ce que montrent déjà les runs corrigés

| Catégorie | n | Pass% | Empty% | Idle% | Ticks moy |
| --- | ---: | ---: | ---: | ---: | ---: |
| `3j / 1 ville` | 60 | **33.3%** | **0%** | 5.0% | 13.8 |
| `5j / 2 villes` | 60 | **20.0%** | **0%** | 61.7% | 18.6 |
| `7j / 3 villes` | 60 | **11.7%** | **0%** | 83.3% | 25.8 |

Lecture fiable :

- `empty_plan` n'est plus le problème principal ;
- la stagnation augmente fortement avec la complexité ;
- le multi-ville reste le cœur du sujet.

### Expérience idle_cycles — statut méthodologique

| Config | Seed | 3j pass | 5j pass | 7j pass | Global | Ticks moy | Idle% |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `v5_full` `idle=4` | `seed42` | 33.3% | 20.0% | 11.7% | 21.7% | 19.4 | 50.0% |
| `v5_idle8` `idle=8` | `seed44` | 33.3% | 20.0% | 8.3% | 20.6% | 24.6 | 52.8% |
| `v5_idle16` `idle=16` | `seed44` | 31.7% | 16.7% | 20.0% | 22.8% | 34.9 | 42.8% |

Interprétation autorisée à ce stade :

- `idle=16` est **prometteur** pour les `7j` ;
- `idle=16` **ne règle pas mécaniquement** les `5j` ;
- ces chiffres **ne suffisent pas encore** à eux seuls pour fixer une causalité, car les seeds ne sont pas appariées.

### Signaux d'émergence structurants

| Métrique | Niveau observé | Lecture |
| --- | ---: | --- |
| `parallel_utilization` | ~0.18 à 0.25 | peu d'agents réellement actifs |
| `lock_contention_rate` | ~0.73 à 0.77 | contention très élevée |
| `action_switching_rate` | ~0.69 à 0.73 | thrashing important |
| `colony_specialization` | ~0.11 à 0.13 | très faible différenciation |
| `collaboration_density` | ~0.92 à 0.95 | collaboration élevée, mais pas suffisante pour converger |

Observation stable :

- le problème n'est probablement **pas** le nombre d'agents ;
- le problème est plus probablement un mélange de :
  - récupération de stagnation insuffisante ;
  - contention non résolue ;
  - faible stabilité de ligne de travail ;
  - représentation de tâche trop plate sur certains cas.

---

## Contraintes absolues de crédibilité scientifique

### Interdits

- Ne pas modifier `third_party/travelplanner_official/`
- Ne pas modifier `scripts/eval_travelplanner_official.py`
- Ne pas modifier la sémantique de `scripts/run_travelplanner_framework_benchmark.py`
- Ne pas changer le split `validation`, son dénominateur, ni la liste des queries
- Ne pas injecter de few-shots, mémoire, heuristique, exemples, ou règles dérivés du split `validation`
- Ne pas coder de règles TravelPlanner dans `core/`
- Ne pas modifier `config/ablation/v5_full.yaml`

### Autorisé

- Modifier `core/*` si la logique est réellement générique
- Ajouter des configs d'ablation V6 dédiées
- Ajouter instrumentation, métriques, logs, et tests
- Garder les optimisations métier TravelPlanner dans `adapters/travelplanner/*`

### Règle de lecture

Le benchmark reste un **thermomètre**.  
On améliore le framework, pas l'instrument de mesure.

---

## Problèmes de conception à corriger avant exécution

### P1 — La preuve `idle=16` doit être consolidée

Le plan précédent utilisait correctement les résultats disponibles, mais les tableaux mélangeaient les seeds.  
La première étape V6 doit donc être un **rejeu à seeds appariées**.

### P2 — T1 et T5 ne doivent pas devenir deux contrôleurs concurrents

Le runtime actuel adapte déjà `selection_temperature` et `inhibition_increment` via la boucle de feedback d'émergence.

Implication :

- la récupération anti-stagnation ;
- l'idle dynamique ;
- l'ajustement de température ;
- l'adaptation d'inhibition

doivent vivre dans **un seul plan de contrôle**.

### P3 — `marker_reads` n'est pas un proxy suffisant de contention

`marker_reads` capture la perception des agents, pas les tentatives de lock ratées par marker.

Donc, avant toute logique de dispersion de charge, il faut ajouter une **instrumentation explicite** :

- tentatives de lock par marker ;
- conflits de lock par marker ;
- tick de dernier conflit ;
- éventuellement gagnants/perdants de contention.

### P4 — La décomposition persistante est un chantier de représentation

Le runtime actuel sait décomposer, mais pas maintenir nativement une couverture persistante de sous-objectifs.  
Le passage à `remaining_subgoals` n'est pas une petite optimisation : c'est une évolution du contrat entre runtime, adapter, et toolchain.

Conclusion :

- **à ne pas mettre dans la première ablation V6** ;
- à traiter comme **track V6.2** si le `5j` reste le point dur après la phase 1.

### P5 — La réparation guidée existe déjà partiellement côté TravelPlanner

TravelPlanner possède déjà un pattern `validate -> feedback -> replan` local.  
Un contrat runtime générique de réparation ciblée reste intéressant, mais ce n'est pas le premier levier à tester si l'objectif immédiat est de réduire l'ambiguïté d'attribution.

---

## Hypothèses V6 révisées

### H1 — Le framework manque d'une récupération active de stagnation dans son plan de contrôle existant

Hypothèse forte et actionnable.  
C'est le meilleur premier levier framework-général.

### H2 — Le framework manque d'une stabilité locale de ligne de travail quand du progrès récent existe

Hypothèse plausible.  
À tester seulement après introduction d'une récupération propre, pour éviter de confondre exploration et inertie.

### H3 — Les échecs `3j` peuvent bénéficier d'une réparation ciblée plus générique

Hypothèse utile, mais secondaire après H1/H2.

### H4 — Les échecs `5j` peuvent exiger une refonte de représentation des sous-objectifs

Hypothèse crédible, mais trop coûteuse pour la première ablation V6.  
À ouvrir seulement si les leviers de contrôle ne suffisent pas.

---

## Plan d'exécution révisé

### T0 — Freeze méthodologique et baseline à seeds appariées

- **Priorité** : P0
- **But** : verrouiller les comparaisons avant toute nouvelle conclusion

Actions :

1. Geler définitivement `config/ablation/v5_full.yaml`
2. Créer `config/ablation/v6_base.yaml` comme copie de `v5_full.yaml` avec `idle_cycles_to_stop: 16`
3. Rejouer `v5_full` et `v6_base` sur **les mêmes seeds**
4. Utiliser ces résultats comme vraie baseline V6

Acceptation :

- `v5_full.yaml` inchangé
- `v6_base.yaml` valide et exécutable
- tableau comparatif `v5_full` vs `v6_base` produit sur seeds appariées

---

### T1 — Contrôleur unifié de récupération de stagnation

- **Priorité** : P0
- **Nature** : framework-général
- **Remplace** : ancien T1 + partie pertinente de T5

Principe :

- on n'ajoute **pas** un deuxième contrôleur autonome ;
- on enrichit le **plan de contrôle existant** du runtime.

Travail minimal visé :

1. Ajouter instrumentation de contention par marker
2. Définir une signature de stagnation générique :
   - pas de progrès terminal récent ;
   - travail pending restant ;
   - contention élevée ;
   - cooldown respecté
3. Déclencher une récupération bornée :
   - légère hausse temporaire de température ;
   - léger relâchement temporaire d'inhibition ;
   - priorité vers des markers moins récemment contestés
4. Journaliser chaque activation avec le signal déclencheur

Important :

- la dispersion se base sur des **signaux de lock réels**, pas sur `marker_reads` seuls ;
- l'idle dynamique, s'il existe, reste dans ce même contrôleur.

Config cible :

```yaml
orchestrator:
  recovery_controller:
    enabled: true
    stagnation_ticks: 5
    contention_threshold: 0.6
    recovery_cooldown_ticks: 8
    temperature_boost: 0.1
    temperature_boost_duration: 3
    inhibition_relief: 0.2
    dynamic_idle:
      enabled: true
      node_per_idle_cycle: 6
      max_extra_idle_cycles: 8
```

Acceptation :

- tests unitaires `stagnation -> recovery`
- tests unitaires `recent progress -> no recovery`
- audit events explicites
- baisse de `idle_cycles_rate` sur `7j` sans hausse nette sur `3j`

---

### T2 — Stabilité locale de ligne de travail à horizon court

- **Priorité** : P1
- **Nature** : framework-général
- **Correspond à** : version resserrée de l'ancien T4

Principe :

- si un agent vient de contribuer à une ligne productive, on lui donne un **léger bonus de continuité** ;
- ce bonus disparaît vite dès que la ligne devient stérile ;
- si le contrôleur de récupération T1 est actif, T2 ne s'applique pas.

Travail visé :

1. Suivre le progrès récent par agent
2. Ajouter un bonus de stickiness de faible amplitude
3. Désactiver ce bonus en absence de progrès court terme
4. Vérifier explicitement l'exclusion mutuelle T1/T2

Acceptation :

- baisse de `action_switching_rate`
- pas d'effondrement de `pressure_entropy`
- pas de centralisation excessive

---

### T3 — Contrat générique de réparation ciblée

- **Priorité** : P1
- **Nature** : framework-général
- **Correspond à** : version réduite de l'ancien T3

Principe :

- ne pas généraliser immédiatement tout le cycle TravelPlanner ;
- introduire seulement un contrat runtime minimal permettant à un validateur structuré d'indiquer :
  - statut ;
  - cibles à réparer ;
  - feedback compact.

Travail visé :

1. Étendre `ActionResult` avec un contrat de validation/réparation
2. Permettre au runtime de déposer un marker de repair ciblé
3. Borner les cycles de repair
4. Brancher TravelPlanner sur ce contrat sans déplacer sa logique métier dans `core/`

Acceptation :

- scénario de test `validate -> repair -> revalidate`
- aucun hardcoding TravelPlanner dans `core/`
- amélioration attendue surtout sur les cas `3j` contraints

---

### T4 — Décomposition persistante orientée couverture de sous-objectifs

- **Priorité** : différée
- **Nature** : redesign de représentation
- **Statut** : hors première ablation V6

Décision explicite :

- **ne pas inclure T4 dans la première vague V6** ;
- ouvrir ce chantier seulement si :
  - `V6-A` réduit la stagnation sans résoudre les `5j`, ou
  - les métriques montrent encore un DAG trop étroit malgré T1/T2.

Ce chantier devient alors un plan distinct :

- `V6.2 — Persistent Subgoal Coverage`

---

## Protocole d'ablation révisé — 3 bras V6

Cette version abandonne l'échelle additive longue.  
On privilégie une ablation **courte et lisible**, avec un noyau commun puis des branches.

### Configurations

| Config | Fichier | Rôle |
| --- | --- | --- |
| `V5-full` | `v5_full.yaml` | Référence absolue figée |
| `V6-base` | `v6_base.yaml` | Baseline V6 = `V5-full` + `idle=16` |
| `V6-A` | `v6_A.yaml` | `V6-base` + T1 contrôleur unifié de récupération |
| `V6-B` | `v6_B.yaml` | `V6-A` + T2 stabilité locale |
| `V6-C` | `v6_C.yaml` | `V6-A` + T3 réparation ciblée |

### Philosophie

- `V6-A` teste le levier framework principal
- `V6-B` teste si la stabilité courte ajoute quelque chose au-dessus de `V6-A`
- `V6-C` teste si la réparation ciblée aide surtout les cas `3j`

Conséquence :

- pas de ladder `A -> B -> C -> D -> E`
- pas d'accumulation de changements qui rendrait l'attribution floue

### Combinaison éventuelle

Si `V6-B` et `V6-C` montrent tous deux un signal positif net, on pourra lancer **après coup** :

- `V6-BC` = combinaison confirmatoire

Mais ce run n'appartient **pas** à l'ablation principale.

---

## Règles d'exécution

- même benchmark
- même scorer
- même split `validation`
- mêmes seeds par campagne comparative
- minimum 2 seeds par config pour décision interne
- 3 seeds pour toute communication de résultat stabilisé

---

## Métriques à reporter

### Globales

- `final_pass`
- `delivery_rate`
- `tokens`
- `runtime`
- `coordination_overhead`

### Stratifiées

- `3j / 1 ville`
- `5j / 2 villes`
- `7j / 3 villes`

### Émergence / contrôle

- `convergence_tick`
- `pressure_entropy`
- `parallel_utilization`
- `action_switching_rate`
- `lock_contention_rate`

### Structurelles

- `idle_cycles_rate`
- `all_terminal_rate`
- déclenchements T1 par run
- fréquence d'activation de stickiness
- fréquence et issue des repairs ciblés

---

## Critères de succès minimaux

### Pour `V6-base`

- confirmer ou infirmer proprement le signal `idle=16` sur seeds appariées

### Pour `V6-A`

- amélioration globale vs `V6-base`, ou
- baisse claire de `idle_cycles_rate` sur `7j`, sans hausse problématique sur `3j`

### Pour `V6-B`

- baisse de `action_switching_rate`
- pas de hausse forte de contention
- pas de collapse de diversité

### Pour `V6-C`

- amélioration sur les cas `3j` à contraintes dures
- nombre de cycles de repair borné et traçable

### Pour la phase 1 dans son ensemble

- au moins un bras V6 montre un gain attribuable, interprétable, et publiable

---

## Pistes TravelPlanner à garder séparées

Ces pistes restent potentiellement utiles, mais ne doivent pas contaminer le verdict sur le framework.

### A1 — Filtrage métier plus strict

- `private room`
- `pets`
- `children under 10`
- `transportation`

### A2 — Prompting plus structuré par ville / leg / budget

### A3 — Heuristiques train-only ciblées

Règle :

- publier ces pistes comme **adapter improvements**
- ne pas les mélanger au verdict du framework

---

## Ordre d'exécution recommandé

1. `T0` — geler la baseline et rejouer `V5-full` / `V6-base` sur seeds appariées
2. `T1` — implémenter `V6-A`
3. lancer l'ablation `V6-base` vs `V6-A`
4. `T2` — implémenter `V6-B`
5. `T3` — implémenter `V6-C`
6. comparer `V6-A`, `V6-B`, `V6-C`
7. seulement ensuite décider si `T4` mérite un plan `V6.2`

---

## Ce qu'il ne faut surtout pas faire

- ne pas modifier le scorer
- ne pas modifier le runner pour rendre les scores plus favorables
- ne pas introduire un second contrôleur adaptatif concurrent du feedback loop existant
- ne pas utiliser `marker_reads` seul comme mesure de contention
- ne pas lancer T4 dans la première vague juste parce que les `5j` sont faibles
- ne pas accumuler 5 ou 6 changements dans une seule chaîne additive

---

## Verdict de review

Le bon cap V6 n'est pas "plus de changements".  
Le bon cap V6 est :

- **moins de leviers à la fois** ;
- **meilleure attribution** ;
- **une seule boucle de contrôle** ;
- **une séparation stricte entre optimisation runtime et refonte de représentation**.

Si cette discipline est tenue, les gains V6 pourront être défendus comme des améliorations réelles du framework stigmergique. Si elle n'est pas tenue, on risque d'obtenir un meilleur score sans pouvoir expliquer proprement d'où il vient.
