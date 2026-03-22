# Audit d'alignement OC1-OC5 du framework V3

Date: 2026-03-06

## Objet

Ce document audite l'alignement entre trois niveaux distincts:

1. le niveau theorique attendu par la revue de litterature DSR (`consigne/revue_litterature_v2_DSR.tex`);
2. le niveau promis par le plan V3 (`consigne/V3_improvement_plan.md`);
3. le niveau effectivement implemente et prouve dans le runtime V3 courant (code, tests, ADR, artifacts V3).

Hypotheses retenues:

- la revue fait foi pour exprimer les "envies" de recherche;
- un element n'est considere comme prouve que s'il est relie au runtime V3 courant;
- les anciens artefacts retires ou non alignes V3 ne servent que de contexte historique;
- une metrique configuree mais non reliee au runtime n'est pas une capacite acquise.

## Methode

La lecture s'appuie sur:

- `consigne/revue_litterature_v2_DSR.tex`;
- `consigne/V3_improvement_plan.md`;
- `core/*`, `adapters/*`, `llm/*`, `tools/*`, `main.py`;
- `documentation/decisions/20260304-sprint4-v3-runtime-overhaul.md`;
- `documentation/decisions/20260304-sprint5-v3-memory-emergence-lessons.md`;
- `documentation/decisions/20260305-sprint6-travelplanner-adapter-and-fidelity-eval.md`;
- `documentation/redisgn_v2/sprint_06_artifact.md`;
- `tests/` et le point de controle local `pytest -q` -> `209 passed`.

## Verdict executif

Verdict: **le plan V3 correspond partiellement a la vision du memoire**.

Le plan est **fortement aligne** avec la revue sur le noyau stigmergique V3:
contexte workspace, structured outputs, async, DAG, reinforcement, memoire episodique,
metriques d'emergence et garde-fous environnementaux sont coherents avec OC1 et OC2.

En revanche, il n'est **que partiellement aligne a l'echelle de la these** car la revue
demande davantage qu'un bon runtime:

- une validation comparative rigoureuse contre des baselines single-agent et hierarchiques;
- une etude de cas open source reproductible;
- une specialisation explicite aux taches de migration de code;
- une gouvernance organisationnelle et une evaluation par experts;
- une preuve empirique, et pas seulement une roadmap, pour OC3 a OC5.

Autrement dit: **le coeur V3 est convaincant, mais le dispositif de preuve DSR/FEDS reste incomplet**.

## Matrice d'alignement

| Axe | Souhaite par la revue | Promis par le plan V3 | Preuves V3 actuelles | Verdict |
|---|---|---|---|---|
| OC1 - Architecture generaliste | Framework stigmergique generaliste, applicable a plusieurs domaines | Core V3 generic + assistant + TravelPlanner + roadmap CodeMigration/SWE-bench | Contrats `adapters/base.py`, runtime generic (`core/*`), assistant + TravelPlanner implementes, ADR Sprint 6 | **Partiel** |
| OC2 - Coordination emergente | Specialisation emergente sans roles explicites, mesurable | Memoire agent, lesson markers, 8 metriques d'emergence | `core/agent.py`, `core/emergence.py`, `core/orchestrator.py`, tests `test_agent_memory.py`, `test_emergence.py` | **Aligne** |
| OC3 - Superiorite sur TravelPlanner | Surpasser les frameworks centralises avec comparaison rigoureuse | Sprint 6 TravelPlanner puis Sprint 7 baselines + harness + CI95 | Adaptateur/evaluateur TravelPlanner implementes et testes; pas de harness V3 ni baselines V3 ni campagne comparative stockee | **Non prouve** |
| OC4 - Specialisation code migration | Adapter le framework a PolyMigration et SWE-bench avec resultats competitifs | Sprint 8 CodeMigration, Sprint 9 SWE-bench | Aucun adaptateur `codemigration` ou `swebench` dans le repo courant | **Non prouve** |
| OC5 - Gouvernance et auditabilite | Trace complete, conformite, supervision humaine, validation par experts | Guardrails, audit trail, escalation, audit completeness, experts en Sprint 9 | Audit JSONL, traceability, budget, TTL OK; pas de calcul runtime `audit_completeness`, pas de vrai workflow d'escalade humaine, pas de panel d'experts | **Partiel** |
| DSR / FEDS | 3 episodes: benchmarks, etude de cas, evaluation experts | Sprints benchmark + gouvernance, mais focalises implementation | Benchmark technique seulement prepare partiellement; etude de cas open source et evaluation experts absentes | **Partiel** |
| Gouvernance organisationnelle | Human-in-the-loop, accountability, acceptabilite, meaningful human control | Guardrails environnementaux + escalation + audit | Gouvernance technique presente; gouvernance organisationnelle et validation humaine pas encore operationnalisees | **Partiel** |

## Analyse detaillee par objectif

### OC1 - Architecture generaliste

**Lecture revue**

La revue demande une architecture generaliste de coordination stigmergique, validee d'abord
sur TravelPlanner puis specialisee vers la transformation de code.

**Lecture plan**

Le plan V3 est bien structure pour cela:

- core V3 domain-agnostic;
- couche d'adaptateurs;
- TravelPlanner comme premiere validation;
- CodeMigration et SWE-bench comme extensions.

**Etat repo**

Les preuves sont solides sur la genericite du noyau:

- `adapters/base.py` separe `Workspace`, `Objective`, `DomainAdapter`;
- `core/orchestrator.py`, `core/environment.py`, `core/marker_store.py` restent generiques;
- `main.py` supporte deja `assistant|travelplanner`;
- `documentation/redisgn_v2/sprint_06_artifact.md` confirme la portabilite vers un premier domaine non-assistant.

**Diagnostic**

Le plan est coherent avec la revue, mais la preuve reste encore limitee a deux modes:

- un mode assistant generique;
- un seul benchmark specialise (TravelPlanner).

TravelPlanner seul ne suffit pas a clore la these sur la generalite. La revue attend une
generalite demontree au-dela d'un domaine unique.

### OC2 - Coordination emergente

**Lecture revue**

La revue exige une specialisation emergente mesurable, sans assignation explicite de roles.

**Lecture plan**

Le plan V3 repond tres bien a cette attente:

- memoire cognitive par agent;
- reinforcement et lesson markers;
- instrumentation d'emergence native;
- mesure de specialisation/collaboration/parallele.

**Etat repo**

Les preuves sont reelles et coherentes:

- `core/agent.py` implemente une memoire episodique locale;
- `core/emergence.py` calcule 8 metriques de run;
- `core/orchestrator.py` exporte un `emergence_summary`;
- `documentation/decisions/20260304-sprint5-v3-memory-emergence-lessons.md` explicite l'intention these-grade;
- les tests `tests/unit/test_agent_memory.py` et `tests/unit/test_emergence.py` valident la mecanique.

**Diagnostic**

OC2 est aujourd'hui **le mieux aligne** entre theorie, plan et repo.  
La seule reserve est epistemique: les metriques montrent des signaux d'emergence,
mais elles ne remplacent pas encore une analyse de cas interpretable sur des runs reels.

### OC3 - Superiorite sur TravelPlanner

**Lecture revue**

La revue exige une comparaison rigoureuse contre des approches centralisees/hierarchiques
sur TravelPlanner, avec mesures de precision, cout, temps et overhead.

**Lecture plan**

Le plan V3 prevoit bien:

- un adaptateur TravelPlanner;
- des baselines `single_agent`, `sequential`, `centralized`;
- un harness reproductible;
- CI95 et analyse Pareto.

**Etat repo**

Le repo ne prouve aujourd'hui que la moitie amont:

- oui: `adapters/travelplanner/*` existe;
- oui: `adapters/travelplanner/evaluator.py` expose les metriques de benchmark;
- oui: `tests/integration/test_travelplanner.py` valide le DAG, les metriques et le flux global;
- non: il n'existe pas de `benchmarks/harness.py` ni `benchmarks/runners/*` V3;
- non: aucune campagne comparee V3 stockee n'atteste un depassement de 32.2%;
- non: le repo lui-meme documente cette absence dans `documentation/redisgn_v2/sprint_06_artifact.md`.

**Diagnostic**

Le plan est bien aligne a la revue, mais **OC3 n'est pas demontre**.  
Il faut distinguer clairement:

- `plan bien aligne`: oui;
- `repo pret a prouver OC3`: non.

### OC4 - Specialisation a la transformation de code

**Lecture revue**

La transformation de code n'est pas un exemple secondaire dans la revue: c'est le domaine
principal de validation empirique du memoire, via PolyMigration et SWE-bench.

**Lecture plan**

Le plan V3 integre explicitement:

- `adapters/codemigration/*`;
- `adapters/swebench/*`;
- une iteration DSR 2 et une iteration DSR 3.

**Etat repo**

Aucune de ces briques n'est presente dans le runtime courant:

- pas d'adaptateur `codemigration`;
- pas d'adaptateur `swebench`;
- pas de config dediee;
- pas de tests d'integration associes.

**Diagnostic**

OC4 est aujourd'hui une **roadmap theorique defendable**, mais pas une capacite existante.  
Comme la revue fait de la transformation de code le domaine principal, cet ecart limite
fortement la cohesion entre le memoire et l'artefact actuel.

### OC5 - Gouvernance et auditabilite

**Lecture revue**

La revue demande plus qu'un journal d'audit:

- supervision humaine effective;
- accountability organisationnelle;
- meaningful human control;
- evaluation par experts;
- gouvernance des zones grises et des escalades.

**Lecture plan**

Le plan V3 va dans la bonne direction:

- guardrails environnementaux;
- traceability;
- audit completeness;
- escalation;
- validation d'experts.

**Etat repo**

La gouvernance technique existe partiellement:

- `core/audit.py` fournit un audit append-only JSONL;
- `core/guardrails.py` enforce budget, retry ceiling, TTL, traceability;
- `core/marker_store.py` journalise `before/after` pour les mutations;
- `config/default.yaml` declare `audit_completeness: true`.

Mais plusieurs promesses ne sont pas operationnalisees:

- `audit_completeness` est configure, mais non calcule dans le runtime V3 courant;
- le state `escalated` existe dans les automates, mais aucun workflow humain explicite n'est branche pour le piloter ou le mesurer;
- aucune sortie runtime n'expose un compteur ou protocole d'escalade humaine;
- aucun dispositif d'evaluation par experts n'est encore implemente.

**Diagnostic**

OC5 est **partiellement aligne**.  
Le repo satisfait la tracabilite technique de base, mais pas encore la gouvernance
organisationnelle exigee par la revue.

## Lecture DSR / FEDS

La revue formalise un design de recherche en trois episodes:

1. benchmarks techniques;
2. etude de cas sur projet open source;
3. evaluation par experts.

Le plan V3 couvre correctement le premier episode dans son intention, mais reste incomplet
sur les deux autres:

- l'etude de cas open source n'est pas planifiee explicitement comme livrable autonome;
- l'evaluation par experts apparait tardivement, mais sans protocole detaille;
- la distinction entre `implementation du runtime` et `preuve DSR` n'est pas assez nette.

Le risque academique principal est le suivant: **sur-vendre le niveau de validation alors
que l'artefact courant prouve surtout une maturite runtime, pas encore une maturite de
recherche complete**.

## Priorites

### Must fix in plan

1. **Ajouter explicitement le protocole FEDS complet.**  
   Le plan doit distinguer implementation, benchmark compare, etude de cas open source, et evaluation par experts.

2. **Redefinir OC1 comme double preuve.**  
   D'un cote genericite du noyau; de l'autre portabilite empirique sur plusieurs domaines. TravelPlanner seul ne suffit pas.

3. **Reformuler OC5 pour separer gouvernance technique et gouvernance organisationnelle.**  
   Audit trail, traceability et budget control ne couvrent pas a eux seuls meaningful human control, accountability et acceptabilite.

4. **Rendre explicites les baselines par episode de validation.**  
   La revue parle de comparaisons single-agent et hierarchiques; le plan doit preciser a quels benchmarks et avec quels criteres de fairness elles s'appliquent.

5. **Ajouter un garde-fou de langage dans le plan.**  
   Tout element "FAIT" au niveau runtime doit etre distingue d'un objectif "valide" au niveau memoire.

### Must implement

1. **Baselines et harness V3.**  
   `benchmarks/harness.py` et `benchmarks/runners/*` manquent encore pour prouver OC3.

2. **Campagne TravelPlanner reproductible.**  
   Il faut une campagne comparee stockee avec repetitions, intervalles de confiance et resultat face au seuil de 32.2%.

3. **Adaptateur CodeMigration.**  
   C'est la condition minimale pour faire correspondre l'artefact au domaine principal du memoire.

4. **Adaptateur SWE-bench + protocole Docker reproductible.**  
   Sans cela, OC4 reste theorique.

5. **Calcul runtime d'`audit_completeness`.**  
   La config seule ne suffit pas; il faut un calcul et une sortie verifiable.

6. **Vraie escalation humaine.**  
   Le state `escalated` doit etre lie a une politique, une sortie observable et un protocole de revue.

7. **Evaluation par experts.**  
   Meme un protocole minimal, un guide d'entretien ou une grille d'evaluation manque actuellement pour OC5.

8. **Etude de cas open source.**  
   Elle est requise par le design de recherche de la revue et absente du repo courant.

### Nice to strengthen

1. **Ajouter une table de tracabilite theorie -> module -> preuve.**  
   Cela renforcerait la defensabilite DSR devant le jury.

2. **Documenter les limites epistemiques des metriques d'emergence.**  
   Les presenter comme signaux descriptifs, non comme preuve definitive d'emergence.

3. **Ajouter des sorties CLI orientees gouvernance.**  
   Exemple: items escalades, transitions auditees, ratio d'items avec preuve `before/after`.

4. **Formaliser une analyse des patterns emergents sur logs reels.**  
   Pas seulement des scores aggregates, mais des exemples interpretes de coordination.

5. **Distinguer plus clairement le plan de recherche du plan d'implementation.**  
   Cela evitera de melanger maturite logicielle et validite scientifique.

## Conclusion synthetique

Les constats visibles dans le repo confirment les intuitions suivantes:

- **OC1 et OC2 sont les plus avances** cote runtime. Le noyau V3 est credibilement stigmergique, generic et instrumente.
- **OC3 est prepare mais pas demontre**. TravelPlanner existe, mais pas encore la preuve comparative these-grade.
- **OC4 reste une roadmap** tant que CodeMigration et SWE-bench n'existent pas dans le repo courant.
- **OC5 est partiel**. Audit trail et guardrails existent, mais `audit_completeness`, escalation humaine reelle et panel d'experts ne sont pas operationnalises.

Conclusion DSR:

- le plan raconte bien la refonte du runtime;
- il raconte trop vite la validation globale du memoire;
- il doit etre reformule pour distinguer ce qui est deja prouve, ce qui est seulement prevu, et ce qui releve encore du protocole de recherche.

En l'etat, la meilleure formulation defendable est:

> **Le framework V3 est deja un bon artefact de coordination stigmergique generaliste au niveau runtime, mais la these ne pourra soutenir pleinement OC3 a OC5 qu'apres la mise en place des baselines V3, des adaptateurs code, d'une etude de cas open source et d'une vraie couche de gouvernance/evaluation humaine.**
