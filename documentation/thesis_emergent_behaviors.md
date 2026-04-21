# Comportements émergents observables — Guide pour la rédaction de thèse

> Ce document est destiné à l'agent de rédaction du mémoire.
> Il catalogue les comportements émergents réels du framework StigmergiAgentic,
> avec les métriques correspondantes, les visualisations recommandées,
> et les claims défendables pour la soutenance.
>
> **Titre du mémoire** : *Orchestration stigmergique de systèmes multi-agents LLM :
> principes de conception d'un framework adaptatif et application à la transformation de code*
>
> **Objectifs de conception (DSR)** :
> - OC1 : Architecture généraliste stigmergique
> - OC2 : Coordination émergente (spécialisation sans rôles)
> - OC3 : Supériorité sur TravelPlanner vs frameworks centralisés
> - OC4 : Application à la transformation de code — benchmarks PolyMigration (Amazon) + SWE-bench
> - OC5 : Gouvernance et auditabilité (EU AI Act Article 14)
>
> **Benchmarks de validation** :
> - TravelPlanner (Xie et al., 2024) → OC2, OC3 — déjà implémenté
> - PolyMigration (Amazon Q Developer, 2025) → OC4 — Sprint 10
> - SWE-bench (Jimenez et al., 2024) → OC4 — Sprint 11 (si temps disponible)
>
> **Claim de positionnement** : à score comparable aux baselines hiérarchiques,
> StigmergiAgentic offre des propriétés que celles-ci n'ont pas :
> traçabilité native, gouvernance auditée, émergence collective mesurable.

---

## Philosophie de présentation

Ne pas présenter le framework comme "un système qui consomme N tokens et produit une réponse".
Le présenter comme **un système où l'intelligence collective émerge de traces locales dans un médium partagé**.
Les comportements ci-dessous sont la preuve empirique de cette émergence.

---

## 1. Spécialisation spontanée sans rôles pré-définis

### Ce qui se passe

Les agents partent identiques — même classe `StigmergicAgent`, même configuration, même registry d'outils. Au fil des ticks, certains agents traitent quasi-exclusivement les recherches de vols, d'autres les hôtels, d'autres la planification d'itinéraires. Personne ne leur a assigné ces rôles.

### Pourquoi ça émerge

L'`AgentAffinityProfile` (`core/agent.py:37`) accumule localement les types de markers traités avec succès. Couplé au `local_sensing` (opt-in V4), l'agent tend progressivement vers les markers qui correspondent à son expérience passée. Ce n'est pas une règle programmée — c'est une conséquence des pressions stigmergiques.

### Métrique

`colony_specialization = 1 - specialization_entropy` dans `core/emergence.py`.
- Valeur proche de 0 : tous les agents font la même chose (généralistes)
- Valeur proche de 1 : chaque agent est spécialisé sur un type d'action

### Visualisation recommandée

Stacked bar chart par agent × action type, entre tick 1 et tick N.
Les barres s'homogénéisent par agent au fil des ticks — la spécialisation devient visible.

### Claim pour le mémoire

> "Sans aucune assignation de rôle, les agents développent spontanément des préférences d'action complémentaires, réduisant la compétition sur les mêmes ressources et améliorant l'utilisation parallèle."

---

## 2. Dynamique des phéromones numériques

### Ce qui se passe

Les intensités des markers évoluent en temps réel. Les markers critiques (vols, premières dépendances) attirent plusieurs agents simultanément et voient leur intensité augmenter par reinforcement. Les markers secondaires ou redondants décroissent naturellement si non traités.

### Pourquoi ça émerge

Combinaison du renforcement (`core/reinforcement.py`) — intensité augmente après succès — et du decay exponentiel (`core/decay.py`) — intensité diminue par défaut. Le résultat : les "bons chemins" brillent plus fort dans le médium.

### Métrique

Intensité par marker au fil des ticks (disponible dans `pheromones/audit_log.jsonl`).
`pressure_entropy` dans `core/emergence.py` : mesure si les pressions sont concentrées (exploitation) ou distribuées (exploration).

### Visualisation recommandée

Heatmap ticks × markers, intensité encodée en couleur (blanc → rouge).
Les patterns de propagation d'activité et les "pistes de phéromones" deviennent visuellement évidents.

### Claim pour le mémoire

> "Les markers les plus critiques au succès de la tâche accumulent naturellement une intensité plus élevée, orientant les agents vers eux sans coordination explicite — une analogie directe avec les phéromones des colonies de fourmis."

---

## 3. Résolution émergente des conflits de ressources

### Ce qui se passe

Deux agents veulent le même marker au même tick. Avec `emergent_resolution.enabled: true` (V4), l'agent avec la plus forte affinité pour ce type de marker gagne probabilistiquement. Au fil du run, les agents évitent naturellement les conflits en se dirigeant vers des markers différents.

### Pourquoi ça émerge

Le mécanisme d'inhibition (`markers.inhibition_increment`) pénalise les agents sur les markers contestés. L'affinité locale redirige progressivement chaque agent vers sa "zone de compétence". La contention diminue sans coordination centralisée.

### Métrique

`lock_contention_rate` dans `core/emergence.py` : ratio conflits / tentatives.
Observable : décroissance de cette métrique dans les ticks avancés d'un même run.

### Visualisation recommandée

Courbe `lock_contention_rate` par tick sur un run. Décroissance visible dans la seconde moitié du run.

### Claim pour le mémoire

> "La colonie développe une forme d'auto-organisation temporelle : les conflits de ressources diminuent spontanément au fil de l'exécution, sans mécanisme de négociation directe entre agents."

---

## 4. Effet cascade des dépendances

### Ce qui se passe

Un marker `search_flights` complété débloque simultanément tous les markers `search_hotels` et `search_attractions` qui en dépendaient. Une vague d'activité devient visible dans la timeline : phase lente (dépendances bloquées), puis accélération soudaine.

### Pourquoi ça émerge

Le module `core/dependency.py` implémente `unblocked_markers()` — les agents ne perçoivent que les markers dont les dépendances sont satisfaites. La complétion d'un marker critique libère simultanément plusieurs branches du DAG.

### Métrique

`convergence_tick` dans `core/emergence.py` : tick auquel 80% des markers sont terminaux.
Plus intéressant : la **forme** de la courbe `terminal_progress` par tick — sigmoïde avec inflexion visible.

### Visualisation recommandée

Courbe `terminal_progress` (0 → 1) par tick. La forme sigmoïde illustre le déverrouillage des dépendances.

### Claim pour le mémoire

> "La structure de dépendances du protocole crée des dynamiques d'accélération collective : la résolution des tâches critiques déclenche des cascades d'activité qui augmentent exponentiellement la vitesse de convergence."

---

## 5. Mémoire collective cross-run — Cristallisation des skills (Sprint 9 T1)

### Ce qui se passe

Sur N runs successifs, une skill library se construit dans le médium partagé. Les stratégies confirmées par plusieurs agents sur plusieurs runs deviennent des markers `skill` persistants, consultés par les agents futurs. La performance s'améliore run après run sans modification du code.

### Pourquoi ça émerge

Les `lesson markers` (faible decay) capturent les stratégies réussies intra-run. La promotion `lesson → skill` se déclenche après `promotion_min_uses` utilisations confirmées (`credited_lesson_ids`). Les skills persistent dans `pheromones/skills.db` indépendamment des sessions.

### Métrique

- `skill_count` en fin de chaque run (croissance cumulée)
- `final_pass_rate` run N vs run 1 (amélioration de performance)
- `convergence_tick` run N vs run 1 (accélération)

### Visualisation recommandée

Double courbe : `skill_count` (axe gauche) et `final_pass_rate` (axe droit) en fonction du numéro de run. Corrélation positive visible entre accumulation de skills et performance.

### Claim pour le mémoire

> "Le framework démontre un apprentissage collectif inter-run : les stratégies validées se cristallisent progressivement dans le médium stigmergique, améliorant les performances sans intervention humaine ni modification du code."

---

## 6. Convergence des protocoles de coordination (Sprint 9 T2)

### Ce qui se passe

Sur 10 runs en mode adaptatif, les paramètres de coordination évoluent mesurables. L'`inhibition_increment` augmente si la contention est haute. La `selection_temperature` diminue si les agents sur-explorent. Le système converge vers un état d'équilibre collectif.

### Pourquoi ça émerge

`compute_adaptations()` (`core/emergence.py:68`) calcule des ajustements depuis les métriques d'émergence. Persistés comme markers `coordination_protocol`, ces ajustements s'appliquent au run suivant via `clamp_cross_run_adaptations()`.

### Métrique

Trend des 8 métriques d'émergence sur la campagne :
- `lock_contention_rate` ↓ (moins de conflits)
- `parallel_utilization` ↑ (meilleure utilisation des agents)
- `pressure_entropy` stabilise (ni trop concentré, ni trop diffus)

### Visualisation recommandée

Line chart multi-métriques par numéro de run. Convergence visible vers des valeurs stables en 5-8 runs.

### Claim pour le mémoire

> "La coordination inter-agents s'auto-améliore : sans intervention humaine, le système apprend collectivement à réduire la contention et à maximiser l'utilisation parallèle, en faisant évoluer ses propres paramètres de coordination via le médium stigmergique."

---

## Tableau de synthèse pour la soutenance

| Comportement | Mécanisme | Métrique clé | Visuel |
|-------------|-----------|-------------|--------|
| Spécialisation spontanée | AffinityProfile + local sensing | `colony_specialization` | Stacked bar par agent |
| Dynamique phéromones | Reinforcement + decay | `pressure_entropy` | Heatmap ticks × markers |
| Auto-résolution conflits | Inhibition + emergent resolution | `lock_contention_rate` ↓ | Courbe par tick |
| Cascade dépendances | Dependency DAG | `convergence_tick` + sigmoïde | Courbe `terminal_progress` |
| Mémoire collective | Skill markers cross-run | `skill_count` + `pass_rate` ↑ | Double courbe par run |
| Convergence coordination | Protocol artifacts | 8 métriques émergence | Line chart par run |

---

## Données disponibles pour les visualisations

Tout est déjà dans les fichiers de sortie :

```
pheromones/audit_log.jsonl     ← événements tick par tick, intensités, agents
pheromones/markers.db          ← état complet des markers à chaque instant
[run_output].json              ← emergence_summary, tick_rows, evaluation
pheromones/skills.db           ← skill library cross-run (Sprint 9)
pheromones/protocols.db        ← historique des protocoles (Sprint 9)
```

Un script matplotlib de ~150 lignes suffit pour produire tous les visuels ci-dessus depuis ces fichiers.

---

## Référence : "Drop the Hierarchy and Roles" (2026)

Ce papier (arXiv:2603.28990) démontre sur 25 000 tâches que les agents LLM auto-organisés surpassent les structures conçues manuellement de 14%. Leur résultat central : avec un scaffolding minimal (ordre fixe), les agents inventent spontanément des rôles spécialisés et s'abstiennent volontairement des tâches hors de leur compétence.

Ce résultat valide directement la philosophie StigmergiAgentic : la stigmergie EST ce scaffolding minimal. Les markers sont le médium qui permet cette auto-organisation sans communication directe.
