# Plan détaillé du mémoire — Orchestration stigmergique de systèmes multi-agents LLM

> **Auteur** : Abdelatif DJEDDOU
> **Programme** : EMLV, Mémoire de fin d'études
> **Méthodologie** : Design Science Research (Hevner et al., 2004 ; Peffers et al., 2007)
> **Date du plan** : 2026-05-03
> **Version code documentée** : V3 Sprint 9 + V7.1 MigrationBench (en itération)
> **Volume cible** : 90 à 120 pages corps de texte, hors annexes et bibliographie

---

## 0. Pages liminaires (≈ 8 pages)

0.1 Page de titre, déclaration de non-plagiat, remerciements
0.2 Résumé français (1 page, 350 mots)
0.3 Abstract anglais (1 page, 350 mots)
0.4 Table des matières automatique
0.5 Liste des figures, tableaux, encadrés
0.6 Glossaire des sigles (DSR, MAS, LLM, ACO, MAST, Agentic BPM, FEDS, etc.)

**Statut** : à rédiger en dernier, le matériel existe (cf `documentation/memoire/framework_pedagogique.md` pour le glossaire).

---

## Chapitre 1, Introduction (≈ 8 pages)

1.1 Contexte industriel et stratégique
   - Migration de code à grande échelle, chiffres Google (Ziftci 2025), Amazon Q, IBM COBOL
   - Diversité des stratégies organisationnelles (monolithe vers microservices, modernisation incrémentale)

1.2 Tension fondamentale, hiérarchies LLM versus complexité réelle
   - Constat MAST (Cemri 2025), 14 modes d'échec, 41 à 86,7 %
   - Agentless (Xia 2024), simplicité bat complexité agentique
   - Gao 2025, gains marginaux décroissants avec frontier models

1.3 La stigmergie comme alternative théorique
   - Origine biologique Grassé 1959, formalisation Bonabeau 1999, extension Heylighen 2016
   - Stigmergie cognitive Ricci 2007

1.4 Problématique de recherche
   - Énoncé exact tel que figé dans le DSR
   - Pourquoi la transformation de code comme cas d'application principal

1.5 Cinq objectifs de conception (OC1 à OC5)
   - Présentation synthétique tableau

1.6 Annonce du plan et de la méthodologie DSR

**Source disponible** : `consigne/revue_litterature_v2_DSR.tex` lignes 73 à 236.
**Statut** : prêt à rédiger, repiquage du DSR, légère mise à jour avec chiffres post-campagne.

---

## Chapitre 2, Revue de littérature (≈ 25 pages)

2.1 Fondements théoriques de la stigmergie
   - Grassé et le paradoxe de la coordination
   - Formalisation algorithmique, intelligence en essaim, ACO
   - Extension aux systèmes numériques, médium stigmergique
   - Épistémologie stigmergique et cognition distribuée
   - Stigmergie cognitive et paradigme Agents & Artifacts
   - Systèmes adaptatifs complexes (Holland)
   - Ancrage managérial, théorie de la coordination de Malone et Crowston, capacités dynamiques, routines organisationnelles

2.2 Coordination multi-agents et systèmes computationnels
   - Définitions agents LLM et MAS
   - Phéromones numériques
   - Espaces de tuples
   - Auto-organisation
   - Stigmergie empirique en open source et Git (Bolici 2016)
   - Bio-inspiration récente
   - Panorama frameworks (MetaGPT, CrewAI, AutoGen, LangGraph)

2.3 Limites des approches multi-agents centralisées
   - Approche Agentless
   - Framework MAST et taxonomie d'échecs
   - Coût-efficacité et érosion de gains
   - Positions industrielles, principe de simplicité

2.4 Migration de code et transformation avec LLM
   - Validation industrielle (Google, Amazon, IBM)
   - Coordination multi-agents codage autonome
   - Traduction cross-language
   - Évolution et refactoring incrémental
   - Transformation du rôle développeur

2.5 Gouvernance, auditabilité et conformité
   - Guardrails pour écologies agentiques
   - Perspective principal-agent
   - EU AI Act Article 14
   - Meaningful Human Control
   - Dimensions organisationnelles, résistance et adoption
   - Responsabilité morale distribuée
   - Sécurité des systèmes agentiques

2.6 Agentic BPM et workflows
   - Définition Agentic BPM
   - Du RPA à l'automatisation cognitive
   - CAS appliqués aux processus
   - Process Mining et LLM

2.7 Benchmarks et évaluation
   - MultiAgentBench, REALM-Bench, TravelPlanner
   - Métriques génération de code
   - Coût-efficacité, frontières de Pareto Kapoor 2024

2.8 Cadre conceptuel et identification du gap
   - Synthèse croisée
   - Gap théorique
   - Relations entre blocs conceptuels
   - Complexity Leadership Theory
   - Cadre conceptuel proposé

**Source disponible** : `consigne/revue_litterature_v2_DSR.tex` lignes 238 à 1912 (intégralité de la revue).
**Statut** : **rédigé à 100 %**, à intégrer tel quel avec relecture finale et mise à jour bibliographique.

---

## Chapitre 3, Méthodologie de recherche (≈ 12 pages)

3.1 Positionnement épistémologique, Design Science Research
   - Pourquoi DSR plutôt que positiviste ou interprétativiste
   - Artefact à trois niveaux (modèle, instanciation, principes de conception)
   - Positionnement Gregor et Hevner, exaptation

3.2 Processus DSRM en six activités (Peffers 2007)
   - Activité 1, identification du problème
   - Activité 2, objectifs de la solution (OC1 à OC5)
   - Activité 3, conception et développement, trois itérations
   - Activité 4, démonstration
   - Activité 5, évaluation FEDS Venable 2016
   - Activité 6, communication

3.3 Conformité aux sept lignes directrices de Hevner et al. (2004)
   - Tableau de conformité G1 à G7

3.4 Champ d'étude
   - Intersection génie logiciel, multi-agents, MIS

3.5 Sources et collecte de données
   - Source 1, données de conception
   - Source 2, métriques quantitatives (TravelPlanner, MigrationBench)
   - Source 3, panel d'experts (5 à 8 personnes)

3.6 Stratégies d'analyse
   - Frontières de Pareto coût-précision
   - Comparaison Agentless
   - Grille MAST pour classifier les modes d'échec
   - Format Gregor 2020 pour formuler les principes de conception

3.7 Limites méthodologiques anticipées
   - Volume de benchmarks
   - Représentativité du panel
   - Évolution rapide des LLM
   - Coûts API
   - Mono-chercheur, pas de triangulation par investigateurs

**Source disponible** : `consigne/revue_litterature_v2_DSR.tex` lignes 1914 à 2155.
**Statut** : **rédigé à 100 %**, à intégrer tel quel.

---

## Chapitre 4, Conception de l'artefact StigmergiAgentic (≈ 18 pages)

4.1 Vue d'ensemble en couches
   - Schéma d'architecture (substrat, moteur de décision, runtime, gouvernance, adapters, tools, LLM)
   - Boucle runtime canonique (snapshot, decide, lock, execute, deposit, maintain, feedback)

4.2 Le substrat de coordination
   - Marker, primitive minimale (id, type, état, intensité, position, payload, history)
   - State machine configurable
   - MarkerStore SQLite WAL, BEGIN IMMEDIATE
   - Audit trail append-only JSONL
   - Tables auxiliaires marker_reads et marker_lock_events

4.3 Le moteur de décision stigmergique
   - Formule de pression de type ACO, intensité, heuristique, alpha/beta
   - Sélection d'action softmax versus greedy
   - Profil d'affinité agent et local sensing
   - Lien aux théories Bonabeau 1999 et Heylighen 2016b

4.4 Le cycle runtime de l'orchestrateur
   - Snapshot et exposition contrôlée du substrat
   - Phase de décision parallèle
   - Arbitrage par verrous TTL
   - Exécution parallèle et dépôt transactionnel
   - Maintain, decay continu et frequentation
   - Conditions d'arrêt (all_terminal, idle_cycles, budget_exhausted, max_ticks)

4.5 Apprentissage et émergence (Sprint 9)
   - Lessons et promotion en skills (C2)
   - Persistance protocols.db slots baseline, latest, best (C3)
   - Protocol compiler optionnel (C1)
   - Métriques d'émergence (specialization, parallel utilization, lock contention, pressure entropy)
   - Feedback runtime adaptation

4.6 Gouvernance intégrée
   - GuardrailEngine, BudgetExceededError, TraceabilityError, ScopeLockError
   - Audit immuable
   - Conformité Article 14 EU AI Act, traçabilité par construction

4.7 Adapters et tools
   - Contrat DomainAdapter
   - AssistantAdapter et LocalWorkspace
   - TravelPlannerAdapter (workspace, tools, evaluator)
   - MigrationBenchAdapter et atelier de repair colony (V7.1)

4.8 Synthèse, principes de conception émergents formulés au format Gregor 2020
   - DP1, primitive marker comme contrat unique de coordination
   - DP2, sensing local et heuristique d'affinité comme moteur de spécialisation
   - DP3, opt-in stigmergic features pour préserver la rétro-compatibilité
   - DP4, gouvernance par le médium (audit JSONL et scope locks)
   - DP5, persistance cross-run sans modification du source agent

**Sources disponibles** :
- `documentation/memoire/framework_pedagogique.md` (matériel pédagogique complet)
- `documentation/redisgn_v2/sprint_01_artifact.md` à `sprint_09_artifact.md`
- ADR `documentation/decisions/*.md`

**Statut** : **prêt à rédiger**, matériel exhaustif disponible. Effort estimé, 5 à 7 jours.

---

## Chapitre 5, Itération 1 et 2, validation généraliste sur TravelPlanner (OC2 + OC3) (≈ 20 pages)

5.1 Justification du benchmark TravelPlanner
   - Pourquoi un benchmark de planification sous contraintes pour valider la généralité
   - Description du dataset (180 queries validation), scorer officiel
   - Difficulté topologique 3 jours / 5 jours / 7 jours

5.2 Protocole expérimental
   - Switch de modèle, journal de décision (Qwen abandonné, Gemma principal, DeepSeek stress positif)
   - Périmètre stigmergie limité à C3 (skills + protocols read-only + cross_run)
   - Baselines reproductibles partageant le même backbone (solo_direct, solo_cot, solo_self_refine, planner_executor, metagpt_sequential, langgraph_supervisor)
   - Split adapt versus eval, switch vers train_45 pour limiter la contamination

5.3 Résultats quantitatifs (Activité 5 FEDS, épisode 1)
   - Tableau headline final_pass_rate par cellule
     - Gemma C3 : 21,1 %
     - DeepSeek C3 : 22,2 %
     - Gemma solo_direct : 17,8 %
     - Gemma solo_cot : 16,7 %
     - Gemma solo_self_refine : 16,7 %
     - Gemma planner_executor : 12,2 %
     - Gemma metagpt_sequential : 14,9 % (partiel)
     - Qwen C3 fixture : 23,9 %
   - Coût par cellule, frontière de Pareto coût-précision
   - Paired wins C3 versus baselines

5.4 Analyse comportementale
   - Deux régimes d'échec, no-plan idle versus plan invalide
   - Corrélation no-plan idle avec topologie 5j/2c et 7j/3c
   - Profil d'émergence par régime (tokens, ticks, parallel utilization, lock contention)

5.5 Discussion honnête, limites de la démonstration cross-run
   - Stores skills.db et protocols.db restés vides
   - Causes (gating sur completed/verified, credited_lesson_ids non émis par TravelPlanner tools, protocol_compiler désactivé)
   - Implication, OC2 partiellement démontré, le mécanisme d'émergence est instrumenté mais pas exercé sur ce benchmark

5.6 Validation OC3
   - Test de la question "la stigmergie bat-elle les baselines hiérarchiques sur planification sous contraintes"
   - Réponse, oui significativement sur planner_executor, marginalement sur solo, négligeable face à self-refine
   - Validation OC2 partielle, spécialisation observée par affinity profile mais pas par accumulation cross-run

**Sources disponibles** :
- `documentation/redisgn_v2/v9_campaign_behavior_analysis.md` (analyse complète)
- `output/final_campaign_v9_check/aggregates.json` (chiffres bruts)
- `campaign_results/gemma-stigmergie/c3/`, `deepseek-stigmergie/c3/`, `gemma-baselines/*`
- `documentation/redisgn_v2/decision_log_model_switch.md`

**Statut** : **prêt à rédiger**, données complètes. À compléter, langgraph_supervisor manquant (à lancer ou à justifier comme abandonné). Effort estimé, 4 à 6 jours.

---

## Chapitre 6, Itération 3, spécialisation à la transformation de code (OC4) (≈ 18 pages)

6.1 Choix du benchmark MigrationBench
   - Pourquoi MigrationBench plutôt que SWE-bench ou PolyMigration (justification empirique)
   - Description du benchmark, migrations Java 8 vers Java 17 sur projets open source réels
   - Métriques officielles, strict_success, official_success, patch_apply_rate

6.2 Conception de l'adapter (V7 repair colony, V7.1 hardening)
   - Boucle fermée inspect → localize → propose → apply → build → classify → repair → retest → finalize
   - Branches isolées par MigrationBenchWorkspace.branch_workspace
   - Taxonomie d'échec (pom_parse_error, dependency_resolution_error, compile_error, test_failure, class_version_error, patch_apply_error)
   - Pool d'agents élastique opt-in
   - V7.1, normalisation typed edits, validation Java 17 stricte (versions {61}), désactivation lessons, smoke gate obligatoire

6.3 Boucle d'itérations DSR (Activité 3)
   - Itération V7 initiale, intégration repair markers
   - V7.1 itération 1, fix anti-loop self-count
   - V7.1 itération 2, signature cryptographique des edits
   - V7.1 itération 3, retry one-shot sur byte-identical
   - V7.1 itération N, à compléter selon avancement
   - Format journal scientifique, symptôme observé, hypothèse, fix, mesure, gain

6.4 Résultats main_30 (Activité 5 FEDS, épisode 1 bis)
   - **À compléter une fois la campagne main_30 lancée**
   - Tableau V6 static versus V7 repair colony
   - Strict success, patch apply, taxonomy distribution, repair_cycles, branch_count
   - Comparaison à l'état de l'art DocAgent, AutoCodeRover (référence académique)

6.5 Étude de cas qualitative (Activité 5, épisode 2)
   - Une instance détaillée, marker trace, branches successives, taxonomie, repair markers, finalisation
   - Mise en évidence de la coordination stigmergique sur cas réel

6.6 Discussion, validation OC4
   - Si V7.1 converge, validation positive et discussion des limites
   - Sinon, présenter comme proof of iterative engineering DSR avec les principes appris

**Sources disponibles** :
- `documentation/redisgn_v2/v7_1_diagnostic_loop.md` (journal d'itérations)
- `documentation/redisgn_v2/v7_1_implementation_handoff.md`
- `documentation/redisgn_v2/migrationbench_implementation_handoff.md`
- `documentation/redisgn_v2/case_study_codemigration_protocol.md`
- `campaign_results/migrationbench/migrationbench_v7_smoke_iter1` à `iter4`

**Statut** : **rédigeable à 60 %** (design + journal d'itérations). Le 40 % restant dépend du résultat main_30. **Recommandation : écrire 6.1 à 6.3 dès maintenant, laisser 6.4 à 6.6 en placeholder structurel**. Effort estimé, 5 à 8 jours pour la partie disponible.

---

## Chapitre 7, Évaluation par experts et validation OC5 (≈ 12 pages)

7.1 Justification du protocole d'évaluation par experts
   - Pourquoi un panel et non des entretiens exploratoires (cadre DSR, FEDS Venable 2016)
   - Profils ciblés, architectes logiciels, managers SI, ingénieurs IA, 5 à 8 personnes

7.2 Protocole de l'évaluation
   - Présentation du concept stigmergique (15 min)
   - Démonstration live (20 min, scénario MigrationBench ou TravelPlanner)
   - Questionnaire Likert (utilité, faisabilité, gouvernabilité, valeur organisationnelle)
   - Questions ouvertes (résistance organisationnelle, conformité, adoption)
   - Adaptation possible du `consigne/guide_entretien_complementaire.md`

7.3 Résultats quantitatifs Likert
   - **À compléter après collecte**, statistiques descriptives, scores moyens par dimension, dispersion

7.4 Résultats qualitatifs
   - Synthèse thématique des questions ouvertes
   - Verbatims représentatifs sur gouvernance, adoption, EU AI Act

7.5 Audit trail et conformité Article 14 EU AI Act
   - Démonstration de la traçabilité par audit JSONL
   - Couverture des exigences MHC (Meaningful Human Control)
   - Gap résiduel identifié

7.6 Validation OC5

**Source disponible** : `consigne/guide_entretien_complementaire.md`, `documentation/managerial_playbook.md`.
**Statut** : **NON démarré** (la collecte panel est le plus gros risque de timeline). À planifier sous 1 à 2 semaines pour avoir les données dans 4 à 6 semaines.

---

## Chapitre 8, Discussion et principes de conception (≈ 12 pages)

8.1 Synthèse des résultats par OC
   - Tableau OC1 à OC5, statut, preuve, force et limite

8.2 Principes de conception généralisables (format Gregor 2020)
   - DP1, médium primitive unique
   - DP2, sensing local et émergence
   - DP3, opt-in features et rétro-compatibilité
   - DP4, gouvernance par le médium
   - DP5, persistance cross-run découplée du source agent
   - DP6 (potentiel), repair colony comme pattern de transformation de code
   - Pour chaque DP, formulation "Pour [contexte], [caractéristique] produira [résultat] parce que [mécanisme]"

8.3 Contributions théoriques
   - Extension de la théorie de la coordination de Malone et Crowston aux agents LLM
   - Opérationnalisation de la stigmergie cognitive Ricci 2007 dans un framework général
   - Lien CAS Holland et workflow agentique

8.4 Implications managériales et pratiques
   - Choix d'architecture (centralisée versus stigmergique)
   - Gouvernance et conformité réglementaire
   - Transformation du rôle des architectes
   - Coût-efficacité versus modèles frontières

8.5 Limites de la recherche
   - Mono-chercheur, pas de triangulation
   - Cross-run skills non démontré empiriquement sur TravelPlanner
   - Volume de benchmarks limité
   - Volatilité des LLM
   - Stress test Qwen ré-utilisé tel quel

8.6 Threats to validity (cadre standard)
   - Validité interne, stochasticité LLM, 1 seed sur la campagne finale
   - Validité externe, généralisation à d'autres domaines
   - Validité de construct, les métriques choisies mesurent bien l'objectif
   - Validité conclusionnelle, faible n sur les baselines partielles

8.7 Pistes de recherche future
   - Cross-run skill accumulation à instrumenter sérieusement (cf `roadmap_post_memoire_skills_assistant.md`)
   - Étude longitudinale de l'adoption en organisation
   - Extension à d'autres domaines (tickets support, plans projets, migrations cloud)

**Sources disponibles** :
- `documentation/implications_manageriales_et_pratiques.md`
- `documentation/managerial_playbook.md`
- `documentation/memoire/roadmap_post_memoire_skills_assistant.md`

**Statut** : **prêt à rédiger** (8.1, 8.2, 8.3, 8.4, 8.5, 8.6 disponibles), dépendance partielle aux résultats OC4 et OC5. Effort estimé, 3 à 5 jours.

---

## Chapitre 9, Conclusion (≈ 5 pages)

9.1 Rappel de la problématique et des cinq objectifs
9.2 Synthèse des contributions (artefact, instanciation, principes de conception)
9.3 Réponse à la problématique de recherche
9.4 Apports théoriques, méthodologiques, managériaux
9.5 Perspectives d'extension et de recherche
9.6 Mot de la fin (positionnement personnel)

**Statut** : à rédiger en dernier.

---

## Annexes (≈ 30 à 50 pages)

A. Glossaire technique étendu (cf `framework_pedagogique.md` partie IX)
B. Bibliographie complète (déjà figée dans le DSR)
C. ADR sélectionnés (sprints 1, 5, 7, 8, 9)
D. Tableau de correspondance OC versus chapitre versus preuve
E. Configurations YAML (`config/ablation/v6_*.yaml`, `config/migrationbench_v7_repair_colony_deepseek.yaml`)
F. Extraits de marker traces commentés (TravelPlanner et MigrationBench)
G. Protocole détaillé du panel d'experts et grille d'entretien
H. Capture des aggregates V9 (`output/final_campaign_v9_check/aggregates.json`)
I. Journal complet des itérations V7.1
J. Reproducibility note (commandes Docker, hashes de configs, modèles utilisés)

---

## Tableau de pilotage rédaction

| Chapitre | État source | Effort restant | Dépendance externe | Priorité |
|---|---|---|---|---|
| 0. Liminaires | matériel partiel | 1 jour | – | basse, fin |
| 1. Introduction | DSR existant | 1 jour | – | haute, démarrer |
| 2. Revue littérature | DSR existant | 1 jour relecture | – | haute, intégration |
| 3. Méthodologie | DSR existant | 1 jour relecture | – | haute, intégration |
| 4. Conception artefact | sprint artifacts | 5 à 7 jours | aucune | **prioritaire** |
| 5. TravelPlanner OC3 | données complètes | 4 à 6 jours | langgraph_supervisor optionnel | **prioritaire** |
| 6. MigrationBench OC4 | partiel | 3 jours design + main_30 ensuite | smoke gate V7.1 | semi bloqué |
| 7. Experts OC5 | non démarré | 4 jours après collecte | recrutement panel, 4 à 6 sem | bloqué externe |
| 8. Discussion | matériel disponible | 3 à 5 jours | OC4 et OC5 partielles | démarrable |
| 9. Conclusion | – | 1 à 2 jours | tout le reste | dernier |

**Volume total estimé** : 90 à 120 pages corps + 30 à 50 pages annexes.

---

## Stratégie de séquençage recommandée

**Semaine 1 et 2** :
1. Intégrer chapitres 1, 2, 3 depuis le DSR (rédigé)
2. Démarrer chapitre 4 (conception artefact) en parallèle de la rédaction du chapitre 5 (TravelPlanner)
3. Lancer le recrutement du panel d'experts (chapitre 7) immédiatement
4. Continuer la boucle V7.1 jusqu'à smoke gate vert puis lancer main_30

**Semaine 3 et 4** :
5. Finaliser chapitres 4 et 5
6. Rédiger 6.1 à 6.3 (design et journal V7.1)
7. Préparer la démo live et le matériel pour le panel d'experts

**Semaine 5 et 6** :
8. Si main_30 disponible, écrire 6.4 à 6.6
9. Mener les entretiens du panel
10. Démarrer chapitre 8 (discussion)

**Semaine 7 et 8** :
11. Synthèse OC5 dans chapitre 7
12. Finaliser chapitre 8
13. Rédiger chapitre 9 (conclusion) et 0 (liminaires)
14. Relecture intégrale, mise en page, génération PDF

**Garde-fous** :
- Si main_30 ne converge pas en semaine 4, repositionner OC4 en "preuve d'engineering DSR itérative" et accepter cette limite explicitement
- Si moins de 5 experts disponibles en semaine 6, accepter un panel de 3 à 4 et le justifier comme limite

---

## Mapping OC versus chapitres

| Objectif | Chapitres | Preuve disponible aujourd'hui |
|---|---|---|
| OC1 architecture généraliste | 4, 5.6, 8.1 | Sprint 9 complet, 307 tests, ADR |
| OC2 coordination émergente | 4.5, 5.4, 5.5, 8.1 | Framework instrumenté, mais cross-run vide en V9 |
| OC3 comparaison TravelPlanner | 5 entier | Données complètes, 1 baseline manquante |
| OC4 transformation de code | 6 entier | Design + journal V7.1, main_30 à venir |
| OC5 gouvernance et experts | 4.6, 7 entier | Code instrumenté, panel à conduire |

---

## Note finale

Ce plan est compatible avec une soutenance dans 8 à 10 semaines en partant d'aujourd'hui. Les chapitres 1 à 5 et 8 sont rédigeables sans bloquant externe. Les chapitres 6 et 7 portent les deux risques majeurs, l'aboutissement de V7.1 et la disponibilité du panel. La méthodologie DSR autorise à présenter une itération non convergée comme contribution, à condition que le journal soit rigoureux. C'est ton matelas de sécurité.
