# Roadmap post-mémoire — Skills généralistes et extension AssistantAdapter

> Notes de réflexion pour la publication du framework au-delà du mémoire EMLV.
> Sujet : passer d'une logique « 180 queries homogènes TravelPlanner » à un
> Assistant généraliste qui apprend à travers des conversations hétérogènes.
> Statut : notes exploratoires, non-normatives, à consolider avant implémentation.

---

## 1. Contexte et problème

### 1.1 Rappel du fonctionnement actuel des skills

Dans le framework V3 Sprint 9, le cycle d'apprentissage cross-run est :

```
Action réussie (quality ≥ 0.6) → Marker "lesson::..." créé
                                       ↓
                  Next query : agent rappelle cette lesson via AgentMemory.recall
                                       ↓
                  Si l'action qui suit réussit → use_count++
                                       ↓
                  use_count ≥ promote_min_uses (2) → promotion → skills.db
                                       ↓
                  Prochaine query : skill chargé au démarrage (read-only en eval)
```

Cela fonctionne **très bien sur TravelPlanner** parce que les 180 queries sont structurellement similaires : toujours un voyage de N jours entre M villes avec un budget. Une lesson comme *« quand budget serré sur 3 jours, privilégier Airbnb vs hôtel étoile »* est réutilisable d'une query à l'autre.

### 1.2 Structure d'une skill aujourd'hui

Une skill est un marker avec `marker_type="skill"`, stocké dans `skills.db`. Payload typique :

```python
{
    "skill": "Reduce daily restaurant spending when budget < 150€/day/person",
    "source_marker": "lesson::plan_day_3::abc123",
    "trigger_conditions": {
        "marker_type": "plan_itinerary",
        "context_keywords": ["budget_tight", "restaurant"]
    },
    "applicable_actions": ["plan_itinerary"],
    "quality_score": 0.85,
    "use_count": 7,
    "success_rate": 0.82
}
```

Le matching actuel pour choisir quelles skills injecter dans le prompt d'un agent est **lexical** :

```python
def relevant_skills_for(self, marker, all_skills):
    scores = []
    for skill in all_skills:
        score = 0.0
        if skill.payload["trigger_conditions"]["marker_type"] == marker.marker_type:
            score += 0.5
        target_tokens = tokenize(marker.target + str(marker.payload))
        skill_keywords = skill.payload["trigger_conditions"]["context_keywords"]
        overlap = len(set(target_tokens) & set(skill_keywords)) / max(1, len(skill_keywords))
        score += 0.3 * overlap
        score += 0.2 * skill.payload["quality_score"]
        scores.append((skill, score))
    return sorted(scores, key=lambda x: -x[1])[:top_k]
```

Les top-k skills (typiquement 3) sont injectées dans `SYSTEM_PROMPT_V3` via le placeholder `{lesson_context}`.

### 1.3 Pourquoi ça casse sur Assistant généraliste

Imaginons 50 queries successives hétérogènes sur un Assistant :

1. « Fais-moi une étude de cas sur le marché du data foot »
2. « Analyse les performances de mon portefeuille boursier »
3. « Écris un script Python qui scrape Reddit »
4. « Résume ces 3 PDFs »
5. « Crée une roadmap produit pour mon SaaS »
6. ...

Ces queries n'ont **presque aucun recouvrement lexical**. Une lesson issue de la query 1 (*« toujours vérifier les chiffres de marché sur 2 sources indépendantes »*) ne matchera jamais la query 4 par tokens communs.

**Conséquence** :
- Les lessons s'accumulent dans `skills.db` sans être rappelées.
- `use_count` reste à 0, aucune promotion.
- Le mécanisme C2 devient mort en pratique.

---

## 2. Trois axes d'amélioration

### 2.1 Axe A — Abstraction méta-procédurale des skills

Le vrai savoir réutilisable n'est pas *« pour ce voyage précis »* mais **méta-procédural**.

| Skill concrète (query-spécifique) | Skill abstraite (méta-procédurale) |
|---|---|
| « Vérifier le budget du jour 3 » | « Toujours vérifier une contrainte numérique après sa définition » |
| « Scraper Reddit avec l'API JSON » | « Préférer une API officielle avant le scraping HTML » |
| « Ajouter des citations à l'étude data foot » | « Toute affirmation factuelle dans un rapport exige une source » |

L'extraction actuelle est passive : la lesson copie l'exécution qui a réussi. Il faut un `LessonAbstractionTool` dédié qui appelle le LLM avec un prompt du type :

```text
System: Extract a reusable META-lesson from this successful execution.
The lesson must be:
- Independent of specific entities (cities, files, people, numbers)
- Formulated as a conditional rule ("when X, prefer Y because Z")
- Applicable across domains

User: [trace d'exécution : marker + decision + action + result]
```

**Impact** : élevé.
**Coût** : faible (1 appel LLM supplémentaire par lesson créée, ~50 lignes à changer).

### 2.2 Axe B — Matching sémantique via embeddings

Remplacer le matching lexical par un matching par embedding cosine. Chaque skill stocke son embedding (calculé à la création). Pour chaque marker actif, l'agent calcule l'embedding du contexte et cherche les skills par similarité.

Implémentation minimale :

```python
# À la création d'une lesson
skill.payload["embedding"] = embedding_model.encode(skill.payload["skill"])

# Au recall
current_embedding = embedding_model.encode(
    marker.target + " " + marker.payload.get("description", "")
)
scores = [
    (s, cosine(current_embedding, s.payload["embedding"]))
    for s in skills
]
top_k = sorted(scores, key=lambda x: -x[1])[:3]
```

**Options** :
- API : `text-embedding-3-small` à 0.02$/M tokens (très bon marché).
- Local : `sentence-transformers` (gratuit, latence ~10ms CPU).

**Effet attendu** : la skill « vérifier numeric constraint » (stockée avec son embedding) matchera des queries diverses parlant de chiffres, budgets, deadlines, quotas, KPIs, etc.

**Impact** : élevé.
**Coût** : modéré (~200 lignes pour un nouveau module `core/skill_retrieval.py`).

### 2.3 Axe C — Hiérarchie de skills par niveau d'abstraction

Plutôt qu'un bac plat `skills.db`, structurer en niveaux :

```
skills/
  level_0_domain_specific/    (ex: "Transfermarkt API returns null for clubs < L2")
  level_1_task_pattern/       (ex: "Market research needs cross-source validation")
  level_2_meta_procedural/    (ex: "Always verify claims with 2 independent sources")
```

Chaque lesson est classée à sa création par le LLM. Au recall, l'agent cherche dans l'ordre inverse :
1. Les `level_2` (universels, s'appliquent presque toujours).
2. Les `level_1` (pattern de tâche, pertinents si le type de marker match).
3. Les `level_0` (domaine, pertinents uniquement si le contexte match fortement).

Ça évite que 200 skills domain-specific noient les 10 meta-procédurales qui sont vraiment utiles partout.

**Impact** : modéré.
**Coût** : modéré (modifier le schema `skills.db`, prompt de classification, logique de recall).

---

## 3. Question de fond : runs indépendants vs agent persistant

### 3.1 Le design actuel

Le Sprint 9 suppose **une série de runs courts sur un même domaine** (= 180 queries TravelPlanner identiques structurellement). Les skills capitalisent par similarité de forme.

### 3.2 Le design cible pour Assistant en production

Un **agent persistant** qui accumule du savoir au fil de conversations hétérogènes. Ça change trois choses :

#### 3.2.1 Identité de l'utilisateur

Si tu as un utilisateur unique (ou un set d'utilisateurs connus), une lesson comme *« cet utilisateur préfère les réponses concises »* est précieuse.

**Ajout requis** : champ `user_id` dans le payload de skill, partitionnement du recall par `user_id`.

#### 3.2.2 Temporalité

Une lesson de 2024 sur l'API Twitter devient fausse en 2025. Le framework a déjà `decay_rates_by_type.skill: 0.005` (décroissance lente) mais pas de notion explicite d'expiration.

**Ajout requis** : champ `validity_horizon` (date d'expiration optionnelle) + vérification au chargement.

#### 3.2.3 Oubli actif

Le design actuel a le `frequentation_boost` sur succès mais pas le pendant négatif explicite : si une skill est rappelée et que l'action **échoue**, rien ne diminue sa réputation automatiquement.

**Ajout requis** :

```python
if action_failed and skill_was_credited:
    skill.payload["success_rate"] = recompute(skill)
    if skill.payload["success_rate"] < threshold:
        demote(skill)  # retour en lesson, perd son statut skill
```

Le champ `metadata["credited_lesson_ids"]` dans `ActionResult` existe déjà (`core/tool_registry.py:79`) — il suffit d'ajouter la logique de démotion dans `Environment.apply_action_result`.

---

## 4. Roadmap priorisée

| Phase | Objectif | Impact | Coût | Prérequis |
|---|---|:---:|:---:|---|
| 1 | Abstraction méta-procédurale des lessons | ⭐⭐⭐⭐ | ⭐ | aucun |
| 2 | Matching sémantique via embeddings | ⭐⭐⭐⭐ | ⭐⭐ | Phase 1 utile mais pas bloquant |
| 3 | Hiérarchie de skills par niveau | ⭐⭐⭐ | ⭐⭐ | Phase 1 |
| 4 | Multi-utilisateurs | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Phases 1+2 |
| 5 | Oubli actif + expiration | ⭐⭐⭐ | ⭐⭐ | aucun (mais utile après Phase 2) |

### 4.1 Phase 1 — Abstraction

- Créer `tools/abstract_lesson.py` (ou étendre `tools/think.py`).
- Modifier `core/environment.py` pour appeler ce tool au lieu de copier passivement le contenu.
- Prompt dédié dans `llm/prompts.py` (`SYSTEM_LESSON_ABSTRACTION`).
- Tests dans `tests/unit/test_lesson_abstraction.py`.

### 4.2 Phase 2 — Embeddings

- Nouveau module `core/skill_retrieval.py`.
- Dépendance : `sentence-transformers` (local) ou client OpenAI embeddings.
- Champ `embedding` ajouté au payload de skill.
- Cache les embeddings pour éviter le recalcul (petit LRU en mémoire).
- Intégration dans `AgentMemory.recall` ou dans un nouveau `SkillRetriever` injecté dans l'agent.

### 4.3 Phase 3 — Hiérarchie

- Champ `skill_level` ∈ {0, 1, 2} dans payload.
- Prompt de classification au moment de la création (peut être combiné avec l'abstraction Phase 1).
- Modifier le recall pour parcourir les niveaux dans l'ordre décroissant.
- Métriques d'émergence dérivées : ratio level_2 / level_0 (indicateur de maturité du système).

### 4.4 Phase 4 — Multi-utilisateurs

- Migration schema `skills.db` : ajout colonne `user_id TEXT`.
- Partitionnement du recall : `WHERE user_id = ? OR user_id IS NULL` (skills globales + utilisateur).
- UI / CLI pour introspecter sa propre bibliothèque (`uv run python -m scripts.inspect_skills --user alice`).
- Considérer la question vie privée : skills d'un utilisateur ne doivent pas fuir vers un autre.

### 4.5 Phase 5 — Oubli actif

- Logique de démotion dans `Environment.apply_action_result`.
- Seuil `success_rate_demotion_threshold` dans config (défaut 0.4).
- Expiration : au chargement de skill, filtrer celles dont `validity_horizon < now`.
- Option : au lieu de supprimer, marquer `state="skipped"` pour garder la trace historique.

---

## 5. Ce qui reste inchangé

Toutes ces améliorations peuvent s'ajouter **sans toucher au core stigmergique** :

- `core/marker.py`, `core/marker_store.py`, `core/orchestrator.py`, `core/agent.py`, `core/pressure.py`, `core/emergence.py` — **pas modifiés**.
- Les améliorations viennent comme nouveaux `Tool` (`AbstractLessonTool`) ou nouveaux modules (`core/skill_retrieval.py`) ou ajouts dans `llm/prompts.py`.

C'est la force du design : le Sprint 9 a posé les rails (persistance, promotion, chargement cross-run) ; les améliorations d'apprentissage viennent par-dessus sans remettre en cause la stigmergie elle-même.

---

## 6. Insight à retenir

Le framework actuel a le **substrat** pour gérer les skills généralistes :

- stores SQLite séparés (`skills.db`, `protocols.db`) ;
- markers typés avec payload extensible ;
- décay différencié par type ;
- recall mécanisé via `AgentMemory` ;
- injection prompt via placeholders `SYSTEM_PROMPT_V3`.

Ce qui manque n'est pas **architectural**, c'est **comportemental** :

1. Comment le LLM **abstrait** une leçon (Phase 1).
2. Comment on **retrouve** une leçon par sens et non par mot (Phase 2).
3. Comment on **oublie** les leçons fausses (Phase 5).
4. Comment on **organise** un grand nombre de skills (Phases 3, 4).

Ces quatre choses sont des ajouts propres, locaux, testables isolément. Elles constituent un **chantier de 6-12 semaines** pour passer d'un framework de benchmark TravelPlanner à un véritable agent généraliste déployable.

---

## 7. Pistes connexes identifiées

Les réflexions parallèles à ne pas oublier pour la publication :

- **Profondeur de décomposition dynamique** : remplacer `max_depth=3` hardcodé par un critère d'arrêt piloté par le LLM (atomicité) + garde-fous budget/convergence. Voir `tools/decompose.py`.
- **Agent pool élastique** : remplacer `num_agents=6` fixe par un spawn adaptatif basé sur `unblocked_markers`, `lock_contention_rate`, `parallel_utilization`. Intégration naturelle dans `core/emergence.py::compute_adaptations`.
- **Repair markers dans Assistant** : aujourd'hui le contrat `RepairRequest` est présent dans `core/tool_registry.py` mais n'est exploité que par `ValidateConstraintsTool` de TravelPlanner. Étendre à d'autres tools Assistant (ex: `FileWriteTool` qui détecte une erreur de syntaxe dans le fichier écrit → repair).
- **Evaluator Assistant** : actuellement absent. Pour évaluer la qualité d'une réponse généraliste, piste via LLM-as-judge ou via des métriques automatiques (cohérence, complétude par rapport à l'objective).

---

*Document à relire et consolider avant implémentation. Les décisions finales devront être formalisées en ADR (`documentation/decisions/`).*
