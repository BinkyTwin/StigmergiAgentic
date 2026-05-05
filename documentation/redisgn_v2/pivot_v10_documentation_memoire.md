# Du framework V3 au pivot V10 — Documentation du changement de direction pour le mémoire

> Document destiné à intégrer le mémoire de thèse EMLV. Rédigé le 3 mai 2026, à la suite de la décision de pivoter le projet StigmergiAgentic depuis l'architecture V3 (Sprint 9 complet) vers une refonte V10 *from scratch*. Le plan technique canonique est `documentation/redisgn_v2/plan_v10_from_scratch_rebuild.md`. Le présent document explique le **pourquoi** scientifique et méthodologique de ce changement, avec un niveau de détail compatible avec une section « Évolution du dispositif expérimental » d'un mémoire de master recherche.

---

## 1. Problématique de départ et ambition initiale (contexte 2025–début 2026)

### 1.1 Motivation initiale du projet

Le projet StigmergiAgentic est né d'une intuition issue de la littérature en intelligence en essaim et de la robotique collective : les colonies d'agents simples, coordonnés *indirectement* via des traces laissées dans un environnement partagé (mécanisme de **stigmergie** au sens de Grassé puis Theraulaz et al.), produisent des solutions complexes à des problèmes combinatoires sans planification centralisée ni communication directe. Les algorithmes d'optimisation par colonies de fourmis (Ant Colony Optimization) ou les essaims particulaires (Particle Swarm Optimization) en sont les concrétisations historiques.

Avec l'émergence des grands modèles de langage (LLM) capables de produire des décisions complexes en langage naturel, l'hypothèse fondatrice de StigmergiAgentic était la suivante :

> **Hypothèse initiale (H_origine)** : *Une colonie d'agents LLM homogènes, sans rôle prédéfini, coordonnés par un médium stigmergique partagé (un store de marqueurs persistants avec décroissance temporelle, intensité, inhibition), peut résoudre des tâches de raisonnement long-horizon (planification de voyages, migration de code) avec une qualité supérieure ou comparable à des architectures master-slave explicites, tout en offrant une meilleure traçabilité et une meilleure résilience.*

Cette hypothèse s'inscrivait dans une lignée scientifique cohérente : transposer aux LLM les principes de coordination indirecte qui ont fait leurs preuves dans les essaims biologiques et artificiels.

### 1.2 Architecture V3 (Sprint 9) — l'expression maximale de cette hypothèse

Le développement entre les Sprints 1 et 9 a matérialisé cette hypothèse à travers un framework comportant :

- un **store de marqueurs SQLite WAL transactionnel** (`core/marker_store.py`) avec audit JSONL append-only ;
- une **machine à états** sur les marqueurs (`pending → active → completed → verified → terminal`, plus chemins d'échec et d'escalade) ;
- une couche de **décroissance temporelle** (`core/decay.py`) et de **renforcement par fréquentation** (`core/reinforcement.py`) ;
- une **sélection d'actions basée sur les pressions** (formule ACO α/β, `core/pressure.py`) ;
- un **orchestrateur tick-based parallèle** (`core/orchestrator.py`) avec arbitrage de verrous et cycles de récupération ;
- des **agents homogènes role-free** (`core/agent.py`) avec sensing local optionnel et profils d'affinité ;
- une couche d'**émergence** (`core/emergence.py`) calculant des métriques (entropie de spécialisation, densité de collaboration, contention) pour boucler sur la configuration ;
- au Sprint 9, une **bibliothèque de skills** et un **compilateur de protocoles cross-run** (`core/schemas.py:ProtocolSpec`) destinés à matérialiser un apprentissage inter-runs.

Trois adaptateurs ont été développés pour mettre cette architecture à l'épreuve : `AssistantAdapter` (cas didactique), `TravelPlannerAdapter` (banc académique de planification, ICML 2024), et `MigrationBenchAdapter` (banc Amazon de migration Java 8 → 17, publié fin 2025).

Trois ablations conditionnelles (notées C1, C2, C3 dans la documentation interne) ont été conçues pour mesurer l'apport progressif des skills, des protocoles cross-run, et de leur combinaison.

### 1.3 Question de recherche initiale

> *Dans quelle mesure une coordination stigmergique d'agents LLM homogènes role-free peut-elle, par scaling du nombre d'agents et activation de mécanismes d'apprentissage cross-run, atteindre ou dépasser les performances de baselines mono-agents et d'orchestrations master-slave sur des tâches LLM long-horizon vérifiables ?*

---

## 2. Diagnostic des résultats V3/V7 — ce qui a effectivement été observé

L'évaluation expérimentale de l'architecture V3 (Sprint 9 complet, 307 tests passés, code reproductible sur la branche `archive/v3-sprint9`) a produit des résultats convergents qui ont, après plusieurs cycles d'analyse, conduit à remettre en cause l'hypothèse fondatrice elle-même.

### 2.1 Résultats quantitatifs principaux

**TravelPlanner** (banc OSU-NLP-Group, 1225 requêtes, métrique principale = `final_pass`) :

- Configuration C1 (skills uniquement) sur Gemma 3 31B : ~21 % `final_pass`.
- Configuration C3 (skills + protocoles + cross-run) sur Gemma 3 31B : ~56 % `final_pass`.
- Stress-test Qwen 3.5 9B (résultat pré-calculé) : 23,88 % `final_pass`.

Pour mémoire, l'état de l'art académique sur TravelPlanner reste très bas (les évaluations originales rapportaient 0,6 % pour GPT-4 en 2024) ; les valeurs ci-dessus sont donc *honorables* mais ne démontrent pas la supériorité de la coordination stigmergique : les gains observés entre V5 et V6 viennent essentiellement du *continuation control* (paramétrage de la boucle de poursuite), pas des mécanismes stigmergiques eux-mêmes.

**MigrationBench** (banc Amazon, sous-ensemble main_30, métrique principale = `strict_success` = compilation + tests + évaluation officielle Maven) :

| Bras | Configuration | strict_success | patch_applies | artifact_delivery | Coût LLM/instance |
|---|---|---:|---:|---:|---:|
| V6 static (référence) | DeepSeek V4 Flash, sans repair colony | 1/30 (3,3 %) | 23/30 (76,7 %) | — | ~0,004 USD |
| V7.1 repair colony | DeepSeek V4 Flash, durci | 1/30 (3,3 %) | 5/30 (16,7 %) | — | ~0,36 USD |
| V7.2 best_partial | DeepSeek V4 Flash, fallback diagnostique | 0/30 (0 %) | 27/30 (90 %) | 5/30 (16,7 %) | ~0,34 USD |

Quel que soit le bras (V6 statique, V7 repair colony, V7.1 durci, V7.2 avec fallback diagnostique), le taux de `strict_success` est resté à 0 ou 1 sur 30 instances. Pour mémoire, l'état de l'art sur des bancs cousins (SWE-Bench Verified, mai 2026) atteint 77 % à 93 % avec des architectures de type SWE-agent ou OpenHands sous Claude Sonnet 4.5 ou Claude Mythos Preview.

### 2.2 Diagnostic qualitatif — trois constats convergents

**Constat 1 — la stigmergie pure ne se traduit pas en performance**. Les configurations qui ajoutent davantage d'agents, qui activent des mécanismes de décroissance et de renforcement plus sophistiqués, ou qui scalent le nombre de cycles, ne produisent pas de gain monotone. Sur MigrationBench, V7 (repair colony à 40 cycles, agents élastiques jusqu'à 12, anti-loop signature) régresse même sur certaines métriques par rapport à V6 statique. La littérature 2025-2026 confirme indépendamment ce constat : *Romera et al.* (arXiv 2506.14496, *« LLM-Powered Swarms: A New Frontier or a Conceptual Stretch? »*) montrent qu'une simulation d'essaim de Boids avec agents LLM coûte 300 fois plus en calcul qu'un équivalent classique, sans gain de qualité. Le pari du « plus d'agents stigmergiques = plus d'intelligence » est explicitement contesté dans la communauté.

**Constat 2 — la télémétrie du framework V3 ment**. L'analyse fine des artefacts de campagne a révélé qu'une partie des métriques rapportées dans les `benchmark_summary.json` est mécaniquement fausse. Exemple central : V7.2 affiche `patch_applies=90 %` mais `artifact_delivery=16,7 %` — un écart de 73 points. La cause racine est un mécanisme de *fallback diagnostique* (`_synthesize_best_partial_payload`) qui copie le payload d'un marqueur indiquant `patch_applies=True` (positionné par le validateur local) sans déclencher la chaîne effective de finalisation : pas d'export du diff, pas de `git apply --check` sur un workspace propre, pas d'invocation de l'évaluateur Maven officiel. Le candidat est compté comme « appliqué » alors qu'il n'est jamais soumis à l'évaluation. Ce bug n'est qu'un symptôme : la classe entière des erreurs de timeout subprocess produit des stubs de sortie avec compteurs à zéro alors que les `markers.db` sur disque contiennent des dizaines de patch_hypothesis. Reconstruire la vérité du run impose une post-analyse manuelle systématique des bases SQLite.

**Constat 3 — l'apprentissage cross-run du Sprint 9 ne s'est jamais déclenché**. Le compilateur de protocoles et la bibliothèque de skills, qui devaient matérialiser un apprentissage inter-runs cohérent avec les promesses de la stigmergie biologique (les fourmis renforcent les pistes utiles d'une expédition sur la suivante), ont produit *zéro promotion* sur plus de 1000 runs cumulés. Les protocoles compilés par LLM passent la validation syntaxique mais ne sont jamais ré-appliqués cross-run ; les leçons textuelles ne sont jamais créditées comme cause d'un succès et donc jamais promues en skills.

### 2.3 Lecture scientifique des constats

Ces trois constats, lus ensemble, invalident l'hypothèse fondatrice initiale dans sa formulation forte. Plus précisément :

- **Ce qui est invalidé** : l'idée qu'une *colonie d'agents LLM homogènes role-free*, coordonnée par une *stigmergie pure* (marqueurs + décroissance + pressions sans coordinateur explicite), suffise par scaling à atteindre des performances comparables à des baselines mono-agents fortes ou à des orchestrations master-slave simples. Cette formulation, qui est précisément celle que le framework V3 cherchait à défendre, ne tient pas empiriquement.

- **Ce qui reste ouvert et défendable** : la stigmergie comme *mécanisme de coordination* — c'est-à-dire la modification du comportement futur des agents par des traces persistantes et structurées dans un médium partagé — reste un objet d'étude pertinent et insuffisamment exploré dans le contexte LLM. Mais elle doit être étudiée *à côté* d'autres primitives de coordination explicite (blackboards typés, verifier loops, graphes d'hypothèses), pas en remplacement de celles-ci.

- **Ce qui est méthodologiquement critique** : sans un dispositif expérimental garantissant l'honnêteté des métriques (télémétrie reconstruite depuis une source de vérité unique, replay déterministe, séparation stricte des statuts de validation), aucune comparaison entre architectures n'est défendable. Le diagnostic 2 (télémétrie qui ment) impose une refonte de l'instrumentation *avant* toute nouvelle campagne expérimentale.

---

## 3. Le pivot V10 — reformulation et nouvelle architecture

### 3.1 Reformulation de la question de recherche

À la lumière des constats précédents, la question de recherche est reformulée :

> *Quelle hybridation entre coordination explicite (blackboard typé, verifier loop, graphe d'hypothèses) et coordination indirecte (signaux stigmergiques de support, inhibition, renforcement, décroissance posés sur le médium partagé) maximise la performance, la traçabilité et la transférabilité cross-run sur des tâches LLM long-horizon vérifiables ?*

Le déplacement par rapport à la formulation initiale est triple :

1. **De la défense d'une stigmergie pure à l'étude d'une hybridation mesurable.** On n'oppose plus la stigmergie aux autres formes de coordination ; on cherche la combinaison productive.

2. **De « plus d'agents = plus d'intelligence » à « médium structuré = coordination productive ».** Le sujet n'est plus la population d'agents mais la qualité du médium qui structure leurs interactions. Cette reformulation est cohérente avec la définition de la stigmergie chez Heylighen (« coordination par traces dans un médium ») et la distingue clairement d'un simple *swarming* d'agents LLM, dont la communauté a déjà documenté les limites.

3. **De la performance comme seul critère à la performance + traçabilité + transférabilité.** Un système qui produit un résultat mais dont on ne peut ni rejouer la trajectoire, ni expliquer la sélection finale, ni transférer les apprentissages, n'est pas scientifiquement défendable même s'il atteint des scores honorables.

### 3.2 Hypothèses opérationnelles testables

La reformulation se décline en quatre hypothèses opérationnelles, chacune associée à un protocole expérimental précis (ablation ladder décrit en section 3.4) :

| ID | Hypothèse | Protocole de test |
|---|---|---|
| H1 | Un runtime *verifier-first* (toute hypothèse passe par une validation typée avant finalisation) avec graphe d'hypothèses explicite surpasse les architectures V3/V7 et les baselines mono-agents simples. | Comparaison A1/A2 vs V3/V7 archive et solo_cot. |
| H2 | L'ajout d'une couche stigmergique (signaux de support, inhibition, renforcement, décroissance, affinité) au-dessus d'un blackboard typé apporte un gain mesurable lorsque plusieurs hypothèses concurrentes coexistent, à budget LLM constant. | Comparaison A4 vs A3 (branching simple sans stigmergie). |
| H3 | Une mémoire procédurale *verifier-gated* (skill promue uniquement après k succès vérifiés) produit un transfert cross-run réel, contrairement à la promotion textuelle non-vérifiée du Sprint 9. | Comparaison A6 vs A5 avec séparation stricte train/eval. |
| H4 | Le blackboard typé réduit les erreurs de coordination et les incohérences de métriques par rapport à la « soupe de marqueurs » V3. | Mesure de cohérence télémétrique, taux de succès du replay, comptage des fuites d'adapter. |

H2 est explicitement le **cœur identitaire du mémoire** : si H2 est invalidée, la contribution scientifique propre du dispositif s'effondre — il faudra alors publier honnêtement le résultat négatif et discuter les conditions sous lesquelles la stigmergie n'apporte pas. Cette possibilité d'échec scientifique attestable est *le* critère de défensibilité d'un mémoire de recherche.

### 3.3 Décision architecturale — refonte *from scratch* en `core_v10/`

Plutôt que de patcher V3 (chemin qui aurait conservé un couplage fort avec les abstractions invalidées), la décision a été prise d'ouvrir une nouvelle ligne de code dans `core_v10/`, indépendante du `core/` legacy. Justifications :

- **Cohérence conceptuelle** : la nouvelle architecture place l'EventLog et le HypothesisGraph au centre, le blackboard comme projection, le verifier comme arbitre, et la stigmergie comme couche de signaux opt-in. Cette pile ne se déduit pas naturellement de l'architecture V3 (markers → pressions → verrous → outils → markers).
- **Honnêteté méthodologique** : un nouveau noyau permet de garantir que les comparaisons V10 vs V3 sont des comparaisons d'architectures, pas des comparaisons de versions du même code.
- **Reproductibilité** : la branche `archive/v3-sprint9` reste exécutable indéfiniment ; les chiffres publiés sur V3 restent vérifiables ; les chiffres V10 sont produits par un dispositif distinct et explicitement nommé.

Les briques V3 mathématiquement séparables (décroissance, pressions, renforcement) sont *recopiées* et *adaptées* dans `core_v10/stigmergic_layer.py` lorsque pertinent, sans import depuis `core/` legacy. Cette cloison étanche évite que la nouvelle architecture devienne, à l'usage, « V3 renommée avec un blackboard ».

### 3.4 Méthodologie expérimentale — l'ablation ladder

L'évaluation procède par une séquence d'ablations cumulative, chaque palier ajoutant une primitive et mesurant le gain incrémental :

| Bras | Mécanisme | Question scientifique |
|---|---|---|
| A0 — `direct` | LLM direct sans verifier | Niveau brut du modèle. Floor. |
| A1 — `verifier_loop` | Candidat unique + verifier obligatoire + boucle de feedback | Le verifier-first corrige-t-il les incohérences de métriques ? |
| A2 — `typed_blackboard` | A1 + blackboard typé + auto-élection par capability | Le blackboard améliore-t-il la coordination vs un workflow linéaire ? |
| A3 — `branching_repair` | A2 + plusieurs branches concurrentes + selector déterministe | L'exploration concurrente seule (sans signaux stigmergiques) aide-t-elle ? |
| **A4 — `stigmergic_blackboard`** | A3 + signaux de support, inhibition, renforcement, décroissance, affinité | **Cœur thèse — la couche stigmergique apporte-t-elle un gain mesurable ?** |
| A5 — `verifier_guided_search` | A4 + tree-search verifier-guided (MCTS-light) | La recherche guidée par reward fait-elle mieux ou différent ? |
| A6 — `verifier_gated_memory` | A5 + mémoire épisodique/sémantique/procédurale verifier-gated | La mémoire transfère-t-elle entre runs sans contamination ? |

Trois principes méthodologiques structurent cette séquence :

1. **MCTS arrive *après* la stigmergie**, pas avant. Sinon un éventuel gain de A5 vs A2 pourrait être attribué soit à la recherche guidée, soit à la stigmergie, sans pouvoir trancher. Insérer A4 comme palier intermédiaire isole précisément la contribution stigmergique.

2. **Chaque comparaison se fait à budget LLM constant.** Le coût en appels LLM, en tokens, en USD et en temps CPU est tracé dans l'EventLog ; les comparaisons rapportent toujours les paires `(performance, coût)`.

3. **Un échec scientifique est un résultat valide.** Si A4 ≤ A3 sur l'ensemble des bancs, H2 est infirmée et la contribution du mémoire devient l'identification *des conditions* sous lesquelles la stigmergie n'apporte pas. Cette possibilité d'infirmation est consignée explicitement dans le protocole, pas découverte après coup.

### 3.5 Comparaisons externes obligatoires

L'évaluation finale (Phase 9 du plan technique) inclut des baselines externes implémentées via le même `BenchHarness` unifié, ce qui garantit l'équité de comparaison :

- baselines mono-agents : `solo_direct`, `solo_cot`, `solo_self_refine` ;
- baseline master-slave : `planner_executor` ;
- baseline workflow externe : `LangGraph supervisor` ;
- baseline event-stream externe : `OpenHands-like` (port simplifié de l'architecture event-stream).

Ces comparaisons positionnent V10 par rapport à l'état de l'art académique et industriel, et matérialisent la threat-to-validity « peut-être que tout LLM-orchestrator simple fait aussi bien ». Sans ces baselines, aucune contribution architecturale ne peut être affirmée.

---

## 4. Threats to validity et limites assumées

Le mémoire devra discuter explicitement les limites suivantes, déjà identifiées :

- **Modèle unique par bras.** Les résultats publiés mobilisent un seul LLM par configuration (DeepSeek V4 Flash pour la stigmergie, Gemma 3 31B pour les baselines). La variance inter-modèles n'est pas mesurée. Mitigation : le `BenchHarness` est paramétré par modèle ; un sous-ensemble de bras pourra être ré-exécuté sur un second modèle si le budget le permet.
- **Seed unique.** Une seule seed par bras est exécutée. La variance intra-modèle n'est pas mesurée. Mitigation : documenter la limitation, exécuter A4 et A6 sur deux seeds si le budget le permet.
- **Subset limité.** MigrationBench main_30 = 30 instances ; TravelPlanner C3 = 180 requêtes. Statistiquement faible. Mitigation : reporter les intervalles de confiance binomiaux plutôt que des taux ponctuels.
- **Dépendance à des APIs externes.** DeepSeek et OpenRouter peuvent changer leurs modèles ou leurs prix. Mitigation : geler les versions de modèles utilisées, documenter dans chaque manifest de run.
- **Infrastructure de validation officielle MigrationBench instable.** La chaîne `mvn clean verify` dépend de Maven Central et de dépendances tierces parfois indisponibles. Mitigation : cache Maven local Docker, classification `infra_failed` séparée de `failed`.
- **Possibilité d'invalidation de H2.** Comme indiqué en 3.4, l'échec de H2 est un résultat scientifique acceptable mais doit être anticipé par une trame de discussion préparée à l'avance.

---

## 5. Lien entre ce pivot et la trame du mémoire

Le pivot V10 affecte plusieurs sections du mémoire de manière structurante :

- **Introduction** : la motivation initiale (stigmergie biologique → stigmergie LLM) reste valide comme point de départ historique du projet, mais la formulation forte (« plus d'agents = plus d'intelligence ») doit être présentée comme une *hypothèse à éprouver*, pas comme un acquis.
- **État de l'art** : ajouter les références publiées en 2025-2026 sur les blackboards LLM (arXiv 2510.01285), les swarms LLM (arXiv 2506.14496), Voyager et la promotion vérifiée des skills, OpenHands et SWE-agent comme architectures event-stream, ReST-MCTS et la recherche guidée par process reward.
- **Problématique** : reformuler en intégrant la nouvelle question de recherche (section 3.1 ci-dessus).
- **Hypothèses** : passer de l'hypothèse unique d'origine aux quatre hypothèses opérationnelles H1/H2/H3/H4.
- **Méthodologie** : décrire l'ablation ladder A0..A6 et la comparaison externe comme dispositif expérimental complet.
- **Évolution du dispositif expérimental** : intégrer une version du présent document, qui justifie pourquoi les résultats publiés viennent de V10 et non de V3, tout en présentant les résultats V3 comme baseline historique.
- **Résultats** : matrice complète A0..A6 + baselines externes, sur MigrationBench main_30 et TravelPlanner C3.
- **Discussion** : positionnement honnête sur ce qui est démontré, ce qui ne l'est pas, et ce qui aurait nécessité davantage de ressources.
- **Volet managérial** : l'expérience du pivot (diagnostic d'un dispositif qui ne tient pas, décision de refonte plutôt que de patch successif) est en soi un cas d'étude managérial sur la conduite de projet R&D, à mobiliser dans la section dédiée.

---

## 6. Calendrier et livrables

Le plan technique canonique (`documentation/redisgn_v2/plan_v10_from_scratch_rebuild.md`) découpe l'exécution en 9 phases, chacune livrable indépendamment. Le mémoire peut être rédigé à partir de la fin de la **Phase 6** (StigmergicBlackboard A4 mesuré contre A3 — H2 testée) avec un dispositif scientifique défendable. Les Phases 7 (A5), 8 (A6) et 9 (comparaisons externes) enrichissent la matrice de résultats sans être indispensables à la défensibilité.

Le délai est explicitement libre côté projet personnel ; la cadence sera dictée par la disponibilité de l'infrastructure (Docker, APIs LLM, budget) et la coordination avec les jalons académiques EMLV.

---

## 7. Synthèse en une phrase pour la soutenance

> *Le projet StigmergiAgentic est parti de l'hypothèse qu'une colonie d'agents LLM coordonnés par stigmergie pure suffirait à résoudre des tâches long-horizon vérifiables ; les résultats des bancs TravelPlanner et MigrationBench ont infirmé cette hypothèse forte ; le pivot V10 reformule la contribution scientifique autour de l'hybridation mesurable entre un blackboard typé verifier-first et une couche stigmergique opt-in, dont l'apport propre devient l'objet central et testable du mémoire.*

---

## Sources clés intégrées au pivot

- *LLM-based Multi-Agent Blackboard System for Information Discovery in Data Science*, arXiv 2510.01285 — pattern blackboard typé, gains 13-57 % vs master-slave.
- *LLM-Powered Swarms: A New Frontier or a Conceptual Stretch?*, arXiv 2506.14496 — justifie l'abandon de la stigmergie pure scaling.
- *SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering*, arXiv 2405.15793 — interface agent/machine propre.
- *Agentless: Demystifying LLM-based Software Engineering Agents*, arXiv 2407.01489 — boucle minimale `localize → repair → validate` comme baseline forte.
- *OpenHands: An Open Platform for AI Software Developers as Generalist Agents*, arXiv 2407.16741 — event-stream architecture inspirant `EventLog`.
- *Voyager: An Open-Ended Embodied Agent with Large Language Models*, arXiv 2305.16291 — promotion verifier-gated des skills exécutables.
- *ReST-MCTS\*: LLM Self-Training via Process Reward Guided Tree Search*, arXiv 2406.03816 — recherche guidée par verifier (palier A5).
- *MigrationBench: Repository-Level Code Migration Benchmark from Java 8*, arXiv 2505.09569 — banc cible principal.
- *Building Effective Agents*, Anthropic Engineering — workflows prévisibles avant agents ouverts.
- *Stigmergy as a universal coordination mechanism II: Varieties and evolution*, Cognitive Systems Research, Heylighen — fondement théorique de la stigmergie comme coordination par traces dans un médium.
