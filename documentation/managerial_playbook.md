# Playbook managérial — StigmergiAgentic

**Statut** : Draft v1 pour relecture expert — 2026-04-17
**Public cible** : Décideurs, managers SI, architectes logiciels, responsables de programmes de transformation
**Temps de lecture** : ~15 minutes
**Document compagnon** : `documentation/implications_manageriales_et_pratiques.md` (argumentaire académique détaillé)

---

## B.1 — One-pager exécutif

### Le problème

Les organisations déploient des systèmes multi-agents IA pour automatiser des tâches complexes (migration de code, workflows métier, support opérationnel). La majorité de ces systèmes adoptent une architecture hiérarchique : un agent « chef » distribue les tâches, des agents « exécutants » les réalisent. Cette approche intuitive produit des résultats contre-intuitifs : les analyses MAST (Cemri et al., 2025) documentent 41% à 86,7% d'échecs pour les architectures multi-agents hiérarchiques, avec des surcoûts en tokens de 4x à 220x.

### La contribution

StigmergiAgentic est un framework d'orchestration multi-agents inspiré de la biologie (coordination par traces indirectes, comme les fourmis avec les phéromones). Les agents n'ont pas de rôle assigné, ne se parlent pas directement, et se coordonnent via un environnement partagé observable. Le framework intègre des guardrails (budget, audit trail, verrous temporels) et produit une traçabilité complète par construction.

### Les résultats

Sur le benchmark TravelPlanner (180 queries, 3 seeds, scorer officiel, même backbone pour tous les bras) :

| Architecture | Final Pass | Lecture |
| --- | --- | --- |
| **StigmergiAgentic** | **21%** | Coordination indirecte, pas de chef |
| Self-Refine Solo | 8,3% | Agent unique itératif (critique → révise) |
| CoT Solo | 5,8% | Agent unique avec raisonnement guidé |
| Direct Solo | 4,0% | Agent unique, prompt direct |
| Graph Supervisor | 2,2% | Workflow hiérarchique à graphe |
| Planner-Executor | 0,9% | Agent chef + agents exécutants |

La stigmergie bat significativement les deux architectures centralisées (McNemar p < 0,05). L'observation clé : **les architectures les plus centralisées sont les pires en qualité, malgré un volume de production élevé.**

### La recommandation

Pour les tâches complexes avec enjeux de qualité et de conformité, la coordination stigmergique surpasse les approches centralisées tout en préservant l'auditabilité. Pour les tâches simples et bien définies, un agent unique suffit.

---

## B.2 — Arbre de décision : quelle architecture pour mon cas ?

```
                    La tâche est-elle complexe
                    et multi-étapes ?
                    /                  \
                  Non                  Oui
                  /                      \
         Direct Solo               Y a-t-il des enjeux de
         ou CoT Solo               conformité / auditabilité ?
         (low cost,                /                        \
         suffisant)              Non                        Oui
                                 /                            \
                        Self-Refine Solo              Le workflow est-il
                        (itératif, bon                pré-défini et stable ?
                        ratio coût/qualité)          /                   \
                                                   Oui                   Non
                                                   /                       \
                                          Graph Supervisor         StigmergiAgentic
                                          (rigide mais              (adaptatif +
                                          contrôlé)                 traçable)
```

### Quand ne pas utiliser StigmergiAgentic

- La tâche est simple et peut être accomplie par un seul prompt bien formulé
- L'organisation n'a pas la maturité IA pour opérer un système multi-agents
- La vitesse de production brute est le seul critère (pas la qualité)
- Le budget compute est très contraint et un seul appel LLM suffit

### Quand l'utiliser

- Tâches multi-étapes avec des sous-tâches interdépendantes
- Enjeux de conformité / auditabilité (EU AI Act, compliance interne)
- Besoin de résilience (si un agent échoue, un autre reprend)
- La qualité de livraison est le critère de succès, pas le volume

---

## B.3 — Check-list de déploiement stigmergique

### Avant le pilote

- [ ] **Guardrails minimaux configurés**
  - Budget maximal en tokens et en coût monétaire
  - Nombre maximal de retries par tâche
  - TTL (Time-to-Live) sur les verrous d'agents
  - Audit trail activé (journal JSONL)

- [ ] **Paramétrabilité utilisateur en place**
  - Les opérateurs peuvent ajuster les seuils de pression (phéromones)
  - Les niveaux d'autonomie des agents sont configurables
  - Les critères de validation automatique sont modifiables
  - *Pourquoi : la paramétrabilité réduit l'aversion algorithmique (Dietvorst et al., 2018)*

- [ ] **Périmètre pilote défini**
  - 5-10 tâches représentatives sélectionnées
  - Équipe volontaire de 3-5 personnes identifiée
  - Durée définie : 3-4 semaines
  - Quick wins identifiés (tâches où le gain est attendu rapidement)

- [ ] **Mécanisme de rollback documenté et testé**
  - Procédure de retour à l'approche précédente écrite
  - Rollback testé au moins une fois avant le pilote
  - *Pourquoi : réduit les coûts d'incertitude perçus (Kim & Kankanhalli, 2009)*

### Pendant le pilote

- [ ] **Points de contrôle humains identifiés**
  - 2-3 moments dans le processus où le jugement humain est irremplaçable
  - Ces points ne sont pas cosmétiques (pas un bouton « approve » automatique)
  - *Pourquoi : préserve l'agentivité professionnelle (García-Ruiz & Rocchi, 2025)*

- [ ] **Formation à la lecture de l'audit trail**
  - Les superviseurs savent interpréter les logs de coordination
  - Les métriques d'émergence sont comprises (spécialisation, contention, convergence)
  - *Pourquoi : construit une confiance calibrée (Lee & See, 2004)*

- [ ] **Monitoring continu en place**
  - Coordination overhead (coût de la coordination vs coût de l'exécution)
  - Coût par succès (pas par tâche — par tâche *correctement accomplie*)
  - Drift d'émergence (les patterns de spécialisation changent-ils ?)
  - Satisfaction utilisateur (feedback équipe pilote)

### Après le pilote

- [ ] **Résultats communiqués**
  - Métriques de performance comparées à l'approche précédente
  - Retour qualitatif de l'équipe pilote
  - *Pourquoi : l'aversion diminue avec l'expérience (Turel & Kalhan, 2023)*

- [ ] **Conformité Article 14 EU AI Act vérifiée** (si applicable)
  - Mode HOTL (Human-on-the-loop) configuré
  - Cinq obligations Fink 2025 vérifiées :
    1. Compréhension des capacités et limitations ✓
    2. Conscience du biais d'automation ✓
    3. Interprétation correcte des outputs ✓
    4. Capacité d'override (reprendre le contrôle) ✓
    5. Capacité d'arrêt ✓

- [ ] **Communication interne préparée**
  - Présenter la structure décisionnelle : « les agents proposent → le système filtre → l'humain valide les cas complexes » (Shrestha et al., 2019)
  - Désamorcer l'anxiété du remplacement : les agents augmentent, ils ne remplacent pas
  - Expliquer l'évolution des rôles : du « distributeur de tâches » au « configurateur d'environnement » (Uhl-Bien et al., 2007)

---

## B.4 — Trois scénarios sectoriels

### 1. BPM agentique — Automatiser le routage de processus

**Contexte** : une organisation avec des workflows métier formalisés (support client, gestion d'incidents, onboarding) cherche à automatiser les décisions de routage sans rigidifier les processus.

**Approche** : chaque étape du processus est un marker dans l'environnement. Les agents évaluent les markers disponibles et choisissent le routage optimal en fonction du contexte, au lieu de suivre un chemin pré-défini.

**Jalon** : automatiser 30% des décisions de routage via markers stigmergiques, avec mesure de la réduction du temps de traitement et du taux d'erreur de routage.

**Pré-requis** : processus formalisés (BPMN ou équivalent), équipe familière avec les concepts de workflow, volonté de passer du prescriptif à l'adaptatif.

### 2. Migration logicielle — Tracer chaque transformation

**Contexte** : une entreprise doit migrer une codebase (langage, framework, architecture) avec des exigences de traçabilité (conformité, auditabilité, rollback).

**Approche** : chaque module à migrer est un marker. Les agents traitent les modules dans l'ordre de leurs dépendances, émergeant du graphe de markers. Chaque transformation est tracée dans l'audit trail.

**Jalon** : migrer un module de 500 fichiers avec traçabilité complète. Comparer le coût, le temps et la qualité à une migration manuelle.

**Pré-requis** : codebase modularisée, tests automatisés existants, équipe technique formée.

### 3. Support opérationnel — Coordonner les outils de monitoring

**Contexte** : une équipe ops coordonne plusieurs outils (monitoring, ticketing, alerting) en réagissant aux traces laissées par chaque outil. Cette coordination est déjà « stigmergique » de fait, mais manuelle et lente.

**Approche** : formaliser et automatiser cette coordination existante. Les artefacts partagés (tickets, alertes, logs) deviennent des markers. Les agents automatisent les réponses de premier niveau et escaladent les cas complexes.

**Jalon** : réduire le MTTR (Mean Time to Resolution) de 40% sur un échantillon de 50 incidents, en mesurant aussi la satisfaction des opérateurs.

**Pré-requis** : artefacts de coordination déjà en place, équipe ops ouverte à l'automatisation, monitoring outillé.

---

## B.5 — FAQ managers

### 1. C'est quoi la différence avec CrewAI, AutoGen, LangGraph ?

Les frameworks existants assignent des rôles fixes aux agents (« toi tu cherches, toi tu rédiges ») et un orchestrateur central décide qui fait quoi. StigmergiAgentic n'assigne aucun rôle au départ. Les agents se spécialisent naturellement en réagissant aux traces dans l'environnement. Et il n'y a pas de chef : la coordination passe uniquement par l'espace partagé. Résultat empirique : les architectures avec chef (Planner-Executor, Graph Supervisor) produisent les pires résultats en qualité.

### 2. Pourquoi pas un seul agent qui fait tout ?

Un seul agent peut suffire pour des tâches simples. Mais quand la tâche est complexe — plusieurs étapes interdépendantes, contraintes transversales, besoin de parallélisme — un seul agent atteint ses limites. Le multi-agents stigmergique gère la complexité par le collectif. Et le coût peut rester maîtrisé : on utilise des modèles plus petits en parallèle plutôt qu'un seul gros modèle.

### 3. L'EU AI Act impose quoi concrètement ?

L'Article 14 exige un contrôle humain significatif : comprendre ce que le système fait, pouvoir intervenir, avoir une vue d'ensemble des décisions. StigmergiAgentic produit un journal d'audit traçant chaque décision (quel agent, quelle action, quel état avant/après). Côté organisation, il faut définir qui lit ce journal, quand intervenir, et quels processus mettre en place. Le framework gère la partie technique ; la partie organisationnelle reste de la responsabilité du décideur.

### 4. Comment les agents choisissent quoi faire ?

Chaque tâche dans l'environnement a une « intensité » — plus elle est élevée, plus elle attire les agents. C'est inspiré des colonies de fourmis : les phéromones les plus fortes attirent plus de passage. Il y a aussi une part de stochasticité contrôlée pour que les agents explorent des pistes moins évidentes. Et avec le temps, l'intensité décroît si personne ne s'en occupe — les tâches abandonnées finissent par disparaître.

### 5. Les agents apprennent au fil du temps ?

Pendant une session, oui : les agents développent une affinité pour certains types de tâches basée sur leurs succès et échecs récents. Entre les sessions, non : l'isolation inter-sessions est activée par défaut pour garantir la reproductibilité. C'est un choix de design pour la rigueur scientifique. Dans un déploiement production, cette isolation pourrait être relâchée pour permettre un apprentissage cumulatif.

### 6. Ça coûte combien à opérer ?

Le coût dépend du backbone LLM et du nombre de queries. Nos benchmarks utilisent qwen3.5-9b (modèle open-source, ~$0.15 par 180 queries via OpenRouter). Avec un modèle plus puissant (GPT-4, Claude), le coût par query augmente mais les résultats peuvent s'améliorer. Le framework mesure le coût par succès (pas par appel) — l'overhead de coordination est compensé par la réduction des échecs et des retries inutiles.

### 7. Que se passe-t-il si un agent fait une erreur ?

Plusieurs garde-fous s'activent. Un budget maximal empêche les boucles infinies. Un nombre maximal de retries par tâche évite qu'un agent s'acharne. Un système de verrous avec durée de vie fait qu'un agent bloqué trop longtemps libère sa tâche pour un autre. Et l'audit trail enregistre chaque erreur pour diagnostic post-mortem. Si un agent produit un résultat incorrect, le marker associé reste dans l'environnement et un autre agent peut le reprendre — c'est la résilience par coordination indirecte.

### 8. Ça fonctionne avec GPT-4 / Claude / modèles locaux ?

Le framework est agnostique au backbone LLM. Il a été évalué avec qwen3.5-9b (open-source, 9B paramètres), mais peut être branché sur n'importe quel modèle via API (OpenRouter, OpenAI, Anthropic) ou localement. Le choix du backbone est un paramètre de configuration, pas une contrainte architecturale.

### 9. Comment je sais si ça fonctionne dans mon contexte ?

Lancez un pilote de 3-4 semaines sur un périmètre limité (5-10 tâches, équipe de 3-5 personnes). Mesurez : le taux de réussite des tâches, le coût par succès, la satisfaction de l'équipe, et l'évolution de la confiance au fil du temps. Comparez à votre approche actuelle. Si le pilote est concluant, étendez progressivement.

### 10. Quel est le risque principal ?

Le risque n°1 est l'empoisonnement de l'espace partagé : un marker malveillant ou erroné peut influencer le comportement de tous les agents. Les contre-mesures sont l'authentification des traces (chaque marker est attribué à un agent identifié), la validation d'intégrité (les payloads sont vérifiés), et la détection d'anomalies (des patterns de coordination anormaux déclenchent des alertes). Le risque n°2 est l'aversion des utilisateurs après une erreur visible — ce risque est géré par la paramétrabilité et les phases pilotes (voir check-list B.3).

---

*Ce playbook est un complément opérationnel à la section « Implications managériales et pratiques » du mémoire. Pour l'argumentaire académique détaillé, les citations et les justifications théoriques, se référer au document compagnon.*
