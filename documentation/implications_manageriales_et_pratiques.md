# Implications managériales et pratiques

**Statut** : Draft v1 pour relecture expert — 2026-04-17
**Auteur** : Abdelatif DJEDDOU
**Position dans le mémoire** : Section à insérer après « Design de recherche » et avant la Conclusion
**Résultats de référence** : Campagne TravelPlanner v5.1 (qwen3.5-9b, 3 seeds × 180 queries × 6 bras, scorer officiel)

---

## A.1 — Introduction et posture

Les sections précédentes ont présenté les fondements théoriques de la coordination stigmergique, conçu l'artefact selon une démarche de Design Science Research, et évalué ses performances empiriques sur le benchmark TravelPlanner. Cette section opère un changement de registre : elle traduit les résultats de l'évaluation en recommandations actionnables pour les décideurs, managers de systèmes d'information, architectes logiciels et responsables de programmes de transformation.

Ce changement de registre n'est pas un exercice rhétorique. La septième ligne directrice de Hevner et al. (2004) exige explicitement que la recherche DSR communique ses résultats auprès d'une double audience : technique (réplicabilité des résultats, spécifications de l'artefact) et managériale (implications organisationnelles, conditions d'adoption, valeur pour les décideurs). Ce chapitre honore cette exigence.

La posture adoptée est celle d'une **lecture managériale des résultats empiriques**. Nous ne parlons pas de markers SQLite, de fonctions de pression ACO ou de decay temporel. Nous parlons de philosophies de coordination, de redistribution du pouvoir décisionnel, de gouvernance de systèmes émergents et de conduite du changement. Les concepts techniques sont traduits en termes organisationnels grâce au cadre conceptuel trois piliers posé dans la revue de littérature : le pilier managérial (coordination organisationnelle, capacités dynamiques, routines, affordances), le pilier conceptuel (stigmergie cognitive, coordination par artefacts) et le pilier évaluation (Meaningful Human Control, conformité réglementaire).

Les implications présentées ici sont des **inférences théoriquement ancrées** à partir de résultats de benchmark contrôlé — pas des observations de terrain. Cette limite est assumée et discutée en section A.8. Les recommandations ne prétendent pas à l'universalité : elles s'appliquent aux contextes où la tâche est complexe, la qualité de livraison prime sur la vitesse, et un besoin d'auditabilité existe.

---

## A.2 — Lecture managériale des résultats empiriques

### L'inversion de hiérarchie : un résultat contre-intuitif

L'intuition managériale classique, héritée des théories de l'organisation depuis Weber et Fayol, associe la coordination centralisée à l'efficacité. Un chef de projet distribue les tâches, supervise l'exécution, corrige les écarts : plus la coordination est structurée, meilleurs sont les résultats. Les résultats empiriques du benchmark TravelPlanner invalident cette intuition dans le contexte des systèmes multi-agents LLM.

Le tableau ci-dessous présente les résultats de la campagne d'évaluation, comparant six philosophies d'organisation à backbone constant (qwen3.5-9b via OpenRouter) sur le split validation de TravelPlanner (180 queries, 3 seeds, scorer officiel).

| Philosophie d'organisation | Delivery Rate | CS Macro | HC Micro | HC Macro | **Final Pass** |
| --- | --- | --- | --- | --- | --- |
| Direct Solo | 57,9 ± 0,6% | 15,0 ± 0,6% | 19,8 ± 0,8% | 12,2 ± 0,6% | **4,0 ± 0,6%** |
| CoT Solo | 51,0 ± 0,6% | 17,6 ± 0,8% | 21,4 ± 0,6% | 11,8 ± 0,6% | **5,8 ± 0,3%** |
| Self-Refine Solo | 56,4 ± 0,4% | 18,3 ± 0,0% | 20,9 ± 1,1% | 12,2 ± 0,8% | **8,3 ± 0,0%** |
| Central Planner-Executor | 58,5 ± 0,3% | 1,1 ± 0,6% | 20,6 ± 0,6% | 14,8 ± 0,9% | **0,9 ± 0,3%** |
| Central Graph Supervisor | 56,8 ± 2,3% | 8,9 ± 0,6% | 18,8 ± 0,6% | 12,4 ± 1,2% | **2,2 ± 0,0%** |
| **StigmergiAgentic** | — | — | — | — | **21%** |

*Note : Les résultats StigmergiAgentic correspondent à la campagne v5.1 en cours (corrections multi-city, ablation incrémentale). Les chiffres définitifs seront consolidés à la fin de la campagne. Les résultats des baselines sont issus de la campagne de référence du 2026-04-09.*

Le classement **Final Pass** (la métrique la plus exigeante, qui évalue la qualité globale du plan en intégrant toutes les contraintes) est :

**StigmergiAgentic (21%) > Self-Refine (8,3%) > CoT (5,8%) > Direct (4,0%) > Graph Supervisor (2,2%) > Planner-Executor (0,9%)**

La hiérarchie est **inversée** par rapport à la complexité de coordination. Les architectures les plus centralisées — Central Planner-Executor et Central Graph Supervisor — produisent les pires résultats en qualité, alors qu'elles emploient les mécanismes de coordination les plus élaborés (un agent planificateur qui distribue les tâches, un graphe de workflow qui orchestre l'exécution). C'est un résultat qui mérite une lecture managériale approfondie.

### Le paradoxe Planner-Executor : throughput sans valeur

Le cas du Central Planner-Executor est particulièrement instructif. Avec 58,5% de Delivery Rate, c'est l'architecture qui **livre le plus de plans**. Mais avec 0,9% de Final Pass et un Commonsense Macro de seulement 1,1%, ces plans sont **presque tous incorrects**. En termes managériaux : cette architecture maximise la **vitesse de production** mais pas la **valeur livrée**.

Ce paradoxe a un nom dans la littérature. Cemri et al. (2025), dans leur analyse MAST des échecs des systèmes multi-agents, identifient le mode d'échec « Disobey Task Specification » : le système produit un résultat qui ne respecte pas les spécifications de la tâche, non par incapacité technique, mais par perte de contexte dans la chaîne de délégation. Dans le cas Planner-Executor, l'agent planificateur décompose la tâche en sous-tâches, mais la décomposition perd les contraintes transversales (budget, cohérence entre étapes, respect du bon sens). L'agent exécuteur, privé de cette vision d'ensemble, exécute fidèlement des sous-tâches mal spécifiées.

L'analogie organisationnelle est immédiate. Un manager qui distribue des tâches sans contexte partagé obtient de l'exécution rapide mais mal ciblée. Les équipes livrent, mais ce qu'elles livrent ne correspond pas au besoin réel. C'est le syndrome du « tout le monde est occupé mais rien n'avance » que tout manager de projet connaît. La centralisation de la coordination crée un goulot de transfert de connaissances : tout le contexte doit transiter par un seul point (le planificateur), qui ne peut pas tout transmettre sans perte.

### Coordination overhead versus valeur livrée

La coordination stigmergique n'est pas gratuite. Elle consomme des cycles de coordination supplémentaires : les agents consultent l'environnement partagé, évaluent les pressions, déposent des traces. Cet overhead de coordination est un investissement dont le rendement doit être évalué.

Kapoor et al. (2024) formalisent cette évaluation par les frontières de Pareto coût-précision : un système est sur la frontière s'il n'est possible d'améliorer sa précision qu'en augmentant son coût, et réciproquement. Les résultats montrent que StigmergiAgentic se positionne favorablement sur cette frontière : son overhead de coordination est compensé par une qualité de livraison significativement supérieure.

Le message managérial est clair : **investir dans la coordination indirecte est rentable quand la qualité de livraison est le critère de succès, pas la vitesse de livraison.** Si l'objectif est de maximiser le nombre de livrables produits par unité de temps, une architecture simple (Direct Solo) peut suffire. Si l'objectif est de maximiser le nombre de livrables *corrects*, l'investissement dans la coordination stigmergique se justifie.

### La parité Self-Refine : une nuance honnête

Self-Refine Solo (8,3% Final Pass dans la campagne de référence) constitue un point de comparaison important. Self-Refine est un pattern itératif (critique → révise → critique → révise) qui ne repose pas sur une coordination hiérarchique mais sur une boucle réflexive individuelle. La stigmergie bat les architectures centralisées, mais pas nécessairement les approches itératives.

Cette nuance est scientifiquement importante. Elle suggère que le gain de la stigmergie ne vient pas simplement du « plus d'agents » ou du « plus de coordination », mais de la **nature indirecte de la coordination**. Les approches itératives (Self-Refine) et stigmergiques partagent une propriété : l'absence de planification centrale. Self-Refine itère sur sa propre production, la stigmergie itère sur un environnement partagé. Les deux évitent le goulot du transfert de connaissances centralisé.

Pour un décideur, cela signifie que le choix entre Self-Refine et StigmergiAgentic dépend de la nature de la tâche. Si la tâche peut être améliorée par itération réflexive individuelle (un rapport, une analyse, un plan simple), Self-Refine peut suffire à moindre coût. Si la tâche requiert la coordination de sous-tâches interdépendantes avec des contraintes transversales (planification multi-ville, migration multi-fichier, workflow multi-étapes), la coordination stigmergique apporte la dimension collaborative que Self-Refine n'a pas.

### Tests statistiques et significativité

Les comparaisons pairwise par test de McNemar exact sur les données de la campagne de référence montrent que StigmergiAgentic est :
- **Hautement significativement supérieur** au Central Planner-Executor (p = 0,0005, CI 95% [+3,3pp, +10,6pp])
- **Significativement supérieur** au Central Graph Supervisor (p = 0,0213, CI 95% [+1,7pp, +10,0pp])
- En avantage non significatif face à Direct Solo et CoT Solo
- À parité avec Self-Refine Solo (p = 1,0)

Ces résultats doivent être interprétés avec la rigueur méthodologique appropriée. Les tests McNemar exact sont le choix canonique pour des métriques binaires (pass/fail) appariées par query. La significativité face aux deux architectures centralisées valide la thèse principale : **la coordination stigmergique surpasse la coordination hiérarchique dans ce contexte**. La non-significativité face aux solos et Self-Refine montre les limites de la revendication — la stigmergie n'est pas universellement supérieure.

---

## A.3 — Implications pour la gouvernance et le contrôle humain

### Une gouvernance structurellement différente

La coordination stigmergique produit une gouvernance qui diffère structurellement de celle des systèmes hiérarchiques. Dans un système Planner-Executor, le flux de contrôle est explicite : le planificateur ordonne, l'exécuteur obéit, la chaîne de responsabilité est linéaire. Dans un système stigmergique, le flux de contrôle est émergent : les agents réagissent à l'environnement, les décisions collectives résultent d'interactions locales, et la chaîne de responsabilité est distribuée.

Cette différence a des conséquences profondes pour la gouvernance organisationnelle. Elle ne rend pas la gouvernance plus difficile — elle la rend *différente*. Et, paradoxalement, elle peut la rendre plus transparente, car tout le processus de coordination est matérialisé dans un environnement observable (l'espace partagé de markers), contrairement aux échanges directs entre agents d'un système centralisé, qui sont souvent opaques.

### L'EU AI Act et le choix HITL / HOTL / HIC

L'Article 14 de l'EU AI Act impose un contrôle humain significatif sur les systèmes IA à haut risque. Holmström et al. (2023) identifient trois modèles de supervision :

- **Human-in-the-loop (HITL)** : chaque décision requiert une approbation humaine. Ce modèle est incompatible avec un système multi-agents en temps réel — le coût de supervision par décision est prohibitif quand des dizaines d'agents prennent des centaines de décisions par cycle.
- **Human-on-the-loop (HOTL)** : le système opère de manière autonome avec surveillance et capacité d'intervention humaine. C'est le mode naturel pour un système stigmergique : les agents opèrent, les superviseurs humains monitent les artefacts partagés (l'audit trail, les métriques d'émergence, les patterns de coordination) et interviennent quand des seuils sont dépassés.
- **Human-in-command (HIC)** : les humains maintiennent un contrôle stratégique sans intervenir dans les décisions opérationnelles individuelles. Ce modèle est adapté aux déploiements matures où la confiance dans le système est établie.

Pour un déploiement organisationnel, nous recommandons une **progression HOTL → HIC** : démarrer en mode HOTL pendant la phase pilote (surveillance active, intervention fréquente), puis évoluer vers HIC une fois la confiance calibrée.

Fink (2025) détaille les cinq obligations de l'Article 14(4) que tout déploiement doit satisfaire :
1. **Compréhension** des capacités et limitations du système
2. **Conscience** du biais d'automation (ne pas faire confiance aveuglément)
3. **Interprétation correcte** des outputs
4. **Capacité d'override** (reprendre le contrôle)
5. **Capacité d'arrêt** (stopper le système)

Un système stigmergique satisfait ces obligations par construction technique (audit trail exhaustif, guardrails configurables, budget d'arrêt automatique), mais la satisfaction technique ne suffit pas. Il faut aussi définir **qui** dans l'organisation est responsable de chaque obligation, **comment** les alertes sont acheminées, et **quels processus** sont mis en place pour l'override et l'arrêt. C'est la distinction entre traçabilité technique et gouvernance organisationnelle.

### Meaningful Human Control : tracking et tracing

Santoni de Sio et van den Hoven (2018) proposent deux conditions nécessaires pour un contrôle humain significatif :

- La condition de **tracking** : le système répond de manière appropriée aux raisons morales identifiées par les humains. Dans un système stigmergique, cette condition est satisfaite par la configuration des guardrails environnementaux. Quand un humain configure un budget maximal, un nombre de retries, un TTL de verrous ou des critères de validation, il inscrit ses raisons morales (maîtrise des coûts, prévention des boucles infinies, respect des délais, qualité minimale) dans l'environnement lui-même. Les agents, en réagissant aux contraintes environnementales, « trackent » ces raisons sans communication directe.

- La condition de **tracing** : il est possible de remonter les résultats du système à au moins un humain responsable. L'audit trail stigmergique (journal JSONL avec état avant/après de chaque action, identifiant de l'agent, horodatage) satisfait cette condition par construction. Chaque décision peut être retracée à la configuration environnementale qui l'a rendue possible, et cette configuration remonte à un humain identifiable.

Pour un décideur, ces deux conditions signifient que le contrôle humain ne s'exerce pas en *supervisant chaque action* (ce qui est impossible à l'échelle) mais en *configurant l'environnement* dans lequel les agents opèrent. C'est un changement de paradigme managérial : du contrôle direct au design des conditions de l'action.

### Responsabilité distribuée et Distributed Moral Actions

Floridi (2016) introduit le concept de Distributed Moral Actions (DMAs) : des actions moralement significatives résultant d'interactions locales individuellement neutres. Ce cadre est essentiel pour comprendre la responsabilité dans un système stigmergique. Quand un agent dépose un marker de résultat erroné, qu'un second agent le lit et prend une décision suboptimale basée dessus, et qu'un troisième agent amplifie l'erreur en la propageant, la responsabilité morale est distribuée sur la chaîne causale. Aucun agent individuel n'a pris de décision « immorale » — mais le résultat collectif peut l'être.

Mukherjee et Chang (2025) proposent le framework d'Operational Agency pour tracer l'intention et la responsabilité dans ces chaînes distribuées. En pratique, pour un décideur, cela signifie que la responsabilité ne repose pas sur l'agent individuel mais sur **celui qui a conçu l'environnement** : le concepteur des guardrails, le configurateur des paramètres, le responsable de la supervision. C'est un argument pour investir dans la qualité de la configuration environnementale plutôt que dans la surveillance individuelle des agents.

### Risques de sécurité spécifiques

L'environnement partagé, qui est la force de la coordination stigmergique, en est aussi la vulnérabilité principale. Chen et al. (2024) documentent AgentPoison, la première attaque backdoor ciblant les bases de connaissances et mémoires persistantes des agents LLM, avec un taux de succès d'au moins 80% pour un taux de poison inférieur à 0,1%. L'espace de markers stigmergiques, en tant qu'environnement partagé persistant, constitue une surface d'attaque analogue : un marker empoisonné peut influencer le comportement de tous les agents qui le lisent.

Lee et Tiwari (2024) documentent le Prompt Infection, injection de prompts LLM-to-LLM se propageant silencieusement entre agents. Dans un système stigmergique, cette propagation peut être amplifiée par le mécanisme de renforcement : un marker populaire (lu par de nombreux agents) voit son intensité augmenter, et s'il contient une injection, cette injection gagne en influence.

Pour un décideur, ces risques imposent trois exigences de sécurité :
1. **Authentification des traces** : chaque marker doit être attribuable à un agent identifié
2. **Validation d'intégrité** : les payloads des markers doivent être validés avant utilisation
3. **Détection d'anomalies** : des patterns de coordination anormaux (renforcement excessif d'un marker, convergence rapide vers un seul chemin d'exécution) doivent déclencher des alertes

---

## A.4 — Implications pour le rôle managérial

### Du leadership directif au leadership enabling

L'adoption d'un système de coordination stigmergique transforme profondément le rôle managérial. Uhl-Bien, Marion et McKelvey (2007), dans leur Complexity Leadership Theory (CLT), proposent un cadre pour comprendre cette transformation. La CLT distingue trois fonctions de leadership interdépendantes :

**Le leadership administratif** définit les structures, la planification et l'allocation de ressources. Dans un déploiement stigmergique, c'est le rôle le plus familier pour un manager traditionnel : définir les guardrails environnementaux (budget maximal, seuils de qualité, contraintes de conformité), allouer les ressources (nombre d'agents, backbone LLM, infrastructure), et superviser les indicateurs de performance. Grisold et al. (2025) appellent ces contraintes les « guardrails environnementaux » et insistent sur leur intégration dès la conception, pas a posteriori.

**Le leadership adaptatif** reconnaît et exploite les comportements émergents plutôt que de les supprimer. C'est la fonction la plus contre-intuitive pour un manager formé au command-and-control. Quand les agents se spécialisent spontanément sur certains types de tâches (un comportement observé empiriquement dans le framework), le reflexe managérial classique est d'intervenir pour « rationaliser » cette spécialisation : assigner formellement des rôles, figer les affectations, optimiser la répartition. La CLT argumente l'inverse : si l'émergence produit un pattern efficace, le manager doit le préserver et le renforcer, pas l'écraser par une réorganisation prescriptive. Winfield et al. (2025) le formulent ainsi : « dans les systèmes swarm, l'émergence est une propriété désirée plutôt qu'un bug ».

**Le leadership enabling** crée les conditions (infrastructure technique, culture organisationnelle, formation, autonomie psychologique) qui permettent la coordination stigmergique efficace. C'est la fonction la moins intuitive et la plus importante. Un manager enabling ne dirige pas — il cultive. Il ne contrôle pas les résultats — il conçoit l'environnement dans lequel les résultats émergent. La métaphore biologique est éclairante : un jardinier ne commande pas aux plantes de pousser, il crée les conditions (sol, eau, lumière) dans lesquelles la croissance émerge.

### La redistribution du pouvoir

Markus (1983) établit que les échecs d'implémentation de systèmes d'information ne résultent pas principalement de déficiences techniques, mais émergent lorsque le SI redistribue pouvoir et contrôle au sein de l'organisation. L'orchestration stigmergique redistribue fondamentalement trois dimensions :

1. **Qui décide** : dans un workflow hiérarchique, les décisions de conception (quoi faire, dans quel ordre, avec quelle priorité) sont prises par des développeurs seniors, des architectes ou des chefs de projet. Dans un système stigmergique, ces décisions sont prises par les algorithmes de pression et l'état de l'environnement. Les développeurs seniors peuvent percevoir cette redistribution comme une perte de compétence distincte.

2. **Qui est évalué** : la coordination stigmergique rend la performance collective visible via des métriques automatisées (taux de succès, coût par tâche, overhead de coordination). Cette transparence peut être vécue comme une surveillance accrue ou comme une objectivation bienvenue, selon la culture organisationnelle.

3. **Qui contrôle le processus** : la coordination passe des chefs de projets humains aux mécanismes environnementaux. Le rôle du chef de projet évolue : il ne distribue plus les tâches — il configure l'environnement et interprète les patterns émergents.

Markus (1983) conclut que la gouvernance doit inclure un travail explicite sur les enjeux de pouvoir et la re-légitimation des rôles humains. Pour un déploiement stigmergique, cela signifie que le manager doit **explicitement communiquer** comment les rôles humains évoluent (pas « disparaissent ») et quelle valeur distincte les humains apportent dans le nouveau paradigme (configuration, supervision, jugement dans les cas ambigus, décisions éthiques).

### Préserver l'agentivité professionnelle

García-Ruiz et Rocchi (2025) avertissent que le management algorithmique peut éroder le sens du travail (meaningful work) en réduisant le rôle humain à celui d'exécutant de prescriptions automatisées. Leur analyse, ancrée dans la philosophie des vertus de MacIntyre, argumente que le travail significatif requiert l'exercice de l'agentivité morale : la capacité de prendre des décisions délibérées reflétant des valeurs et un jugement professionnel.

Pour un déploiement stigmergique, cette analyse implique que la conformité à l'AI Act ne suffit pas. Il faut également identifier des **points de contrôle critiques** où l'intervention humaine n'est pas seulement autorisée mais véritablement significative. Ces points ne doivent pas être cosmétiques (un bouton « approve » qu'on clique machinalement) mais des moments où le jugement professionnel humain apporte une valeur que l'automatisation ne peut fournir :
- La validation finale d'un plan complexe avant déploiement
- L'arbitrage entre deux solutions techniques concurrentes avec des implications éthiques différentes
- La décision de continuer ou d'arrêter quand les métriques d'émergence montrent un pattern inhabituel
- L'interprétation de résultats ambigus que les agents ne peuvent pas contextualiser

### Structures décisionnelles humain-IA

Shrestha, Ben-Menahem et von Krogh (2019) proposent trois structures décisionnelles humain-IA :

1. **Délégation complète** à l'IA : l'IA prend la décision de manière autonome. Adapté aux tâches routinières, bien définies et à faible enjeu éthique.
2. **Décision séquentielle hybride** : l'IA propose, l'humain valide (ou inversement). Adapté aux tâches complexes avec enjeux modérés.
3. **Décision agrégée** : l'humain et l'IA contribuent simultanément, et le résultat agrège les deux perspectives. Adapté aux tâches à haut enjeu nécessitant jugement expert.

La stigmergie opérationnalise naturellement la **décision séquentielle hybride** : les agents proposent des résultats via les markers, les guardrails environnementaux filtrent automatiquement les propositions non conformes, et les humains arbitrent les cas complexes ou critiques. Cette structure à trois étages (proposition → filtrage → arbitrage) doit être communiquée explicitement aux équipes pour désamorcer l'anxiété du « remplacement ». Les agents ne remplacent pas le jugement humain — ils génèrent des options que le système filtre et que l'humain valide.

Shrestha et al. (2019) identifient cinq facteurs contingents qui déterminent le choix de la structure décisionnelle : la prévisibilité de la tâche, la disponibilité des données, les enjeux éthiques, la vitesse requise et l'expertise disponible. Ces facteurs sont repris dans la cartographie décisionnelle (section A.6) pour guider le choix d'architecture.

---

## A.5 — Implications pour l'adoption et la conduite du changement

### L'adoption comme programme de transformation

L'adoption d'un système de coordination stigmergique n'est pas un déploiement technique (installer un logiciel, former les utilisateurs, basculer en production). C'est un **programme de transformation organisationnelle** qui touche aux routines, aux rôles, à la distribution du pouvoir et à la culture de coordination. Six cadres théoriques convergent vers cette conclusion et fournissent les leviers d'une adoption réussie.

### Les coûts perçus du changement

Kim et Kankanhalli (2009) modélisent la résistance des utilisateurs par la théorie du biais de statu quo. Ils identifient trois catégories de coûts perçus du changement :

- **Coûts de transition** : apprentissage des nouveaux outils, adaptation des routines de travail, période de productivité réduite pendant la montée en compétence. Pour un déploiement stigmergique, ces coûts incluent la compréhension du fonctionnement de l'espace partagé, l'interprétation des métriques d'émergence, et l'apprentissage du rôle de « configurateur d'environnement » plutôt que « distributeur de tâches ».

- **Coûts d'incertitude** : imprévisibilité des résultats. Ces coûts sont particulièrement saillants pour la stigmergie car le comportement émergent est, par définition, moins prévisible qu'un workflow hiérarchique pré-défini. Un manager habitué à savoir exactement quelle tâche est assignée à quel développeur à quel moment peut trouver inconfortable un système où les agents choisissent dynamiquement leur travail.

- **Coûts de submersion** (sunk costs) : investissements dans les pratiques existantes (workflows configurés, templates de tickets, routines d'estimation, outils de suivi) qui deviennent obsolètes.

Kim et Kankanhalli identifient aussi deux biais cognitifs amplificateurs : l'**aversion aux pertes** (la perte de contrôle perçue est ressentie plus fortement que le gain de qualité) et l'**illusion de contrôle** (le sentiment que l'on maîtrise mieux un processus hiérarchique, même si les résultats objectifs sont inférieurs).

**Recommandations** : (1) Phases d'adoption graduelles avec périmètre croissant. (2) Quick wins identifiés et communiqués rapidement — montrer que le système produit de la valeur avant de demander un changement de routine complet. (3) Mécanismes de rollback documentés et testés — réduire le risque perçu en garantissant la réversibilité.

### La confiance calibrée

Lee et See (2004) proposent un modèle de confiance calibrée en l'automation qui éclaire une dimension complémentaire. Leur cadre distingue deux pathologies :

- **Sur-confiance (complacency)** : supervision insuffisante. Particulièrement dangereuse quand les agents LLM produisent des hallucinations convaincantes — un plan de voyage plausible mais factuellement incorrect, un code compilant mais logiquement erroné. La sur-confiance est amplifiée par la fluidité linguistique des LLM, qui masque les erreurs derrière une prose professionnelle.

- **Sous-confiance (disuse)** : rejet de systèmes performants. Si un manager a vu le système produire une erreur visible (un plan manifestement aberrant), il peut rejeter le système entier et revenir aux pratiques manuelles, annulant les gains de productivité.

La stigmergie possède une propriété structurelle qui favorise la calibration : les artefacts partagés (markers, logs de coordination) rendent le processus observable. Un superviseur peut voir *comment* le système est arrivé à un résultat, pas seulement le résultat final. Cette transparence du processus, distinctive par rapport aux systèmes centralisés où les échanges inter-agents sont souvent opaques, permet d'ajuster la confiance sur une base factuelle.

**Recommandations** : (1) Former les superviseurs à lire l'audit trail, pas seulement les résultats. (2) Mettre en place des métriques de performance visibles en temps réel. (3) Ne pas cacher les erreurs — les documenter et les analyser ouvertement pour construire une confiance fondée.

### L'algorithm aversion et son antidote

Dietvorst, Simmons et Massey (2015) documentent l'algorithm aversion : la tendance systématique à rejeter les algorithmes après avoir observé même une seule erreur, tout en tolérant des taux d'erreur supérieurs chez les décideurs humains. Ce biais est particulièrement pertinent pour les systèmes multi-agents où les erreurs sont visibles (un commit incorrect, un plan de voyage erroné) et attribuables au système algorithmique.

Dans une étude complémentaire, Dietvorst et al. (2018) démontrent que **permettre aux utilisateurs de modifier même légèrement les outputs algorithmiques** réduit significativement l'aversion, même lorsque cette modification n'améliore pas objectivement les résultats. Ajuster un paramètre de 2% suffit à restaurer le sentiment de contrôle.

Cette découverte a des implications directes pour le design des guardrails stigmergiques. **Les paramètres du système doivent être accessibles et modifiables par les opérateurs** : seuils de phéromones, critères de validation automatique, niveaux d'autonomie des agents, budget maximal par tâche. Même si les valeurs par défaut sont optimales, donner aux utilisateurs la possibilité de les ajuster réduit considérablement le rejet.

### L'aversion transitoire

Turel et Kalhan (2023) approfondissent l'analyse en montrant que l'aversion algorithmique fonctionne comme un préjugé implicite mesurable, mais — et c'est le résultat encourageant — **cette aversion est transitoire et diminue significativement avec l'expérience d'utilisation**. Les individus qui utilisent le système pendant une période suffisante développent une confiance calibrée qui remplace l'aversion initiale.

Ce résultat justifie scientifiquement l'investissement dans des **phases pilotes**. Un pilote de 3-4 semaines sur un périmètre limité (5-10 tâches, équipe volontaire) permet de traverser la période d'aversion initiale et d'atteindre la phase où l'expérience remplace le préjugé. Le pilote ne doit pas être évalué uniquement sur les métriques de performance — il doit aussi mesurer l'évolution de l'acceptabilité perçue au fil du temps.

### Synthèse opérationnelle : un programme d'adoption en trois phases

Les six perspectives convergent vers un programme structuré :

**Phase 1 — Pilote limité (3-4 semaines)**
- Périmètre : 5-10 tâches, équipe volontaire de 3-5 personnes
- Guardrails paramétrables par les utilisateurs (Dietvorst)
- Quick wins identifiés et communiqués (Kim & Kankanhalli)
- Rollback documenté et testé (Kim & Kankanhalli)
- Formation à la lecture de l'audit trail (Lee & See)

**Phase 2 — Extension progressive (2-3 mois)**
- Extension du périmètre aux tâches plus complexes
- Monitoring continu de la confiance calibrée (Lee & See)
- Recalibration des paramètres basée sur le retour d'expérience
- Communication des résultats quantifiés (réduction de l'aversion — Turel & Kalhan)
- Identification des points de contrôle humains significatifs (García-Ruiz)

**Phase 3 — Institutionnalisation**
- Intégration dans les processus standard de l'organisation
- Transition HOTL → HIC sur les tâches routinières (Holmström)
- Re-légitimation formelle des rôles humains (Markus)
- Documentation des pratiques émergentes comme nouvelles routines organisationnelles (Feldman & Pentland)
- Évaluation continue et ajustement (capacités dynamiques — Teece)

---

## A.6 — Cartographie décisionnelle : quelle architecture pour quel contexte ?

### Principe

Le choix d'architecture multi-agents n'est pas universel. Il dépend du contexte organisationnel : complexité de la tâche, enjeux de conformité, maturité de l'organisation, budget disponible. Cette cartographie croise les six formes organisationnelles évaluées empiriquement avec huit critères issus de la littérature, fournissant aux décideurs un outil de décision argumenté.

### Tableau décisionnel

| Critère | Direct Solo | CoT Solo | Self-Refine | Planner-Executor | Graph Supervisor | StigmergiAgentic |
| --- | --- | --- | --- | --- | --- | --- |
| **Tâche prévisible et bien définie** (Shrestha) | ++ | ++ | + | + | ++ | 0 |
| **Tâche complexe multi-étapes** (Shrestha) | -- | - | + | - | 0 | ++ |
| **Disponibilité des données** (Shrestha) | 0 | 0 | 0 | 0 | 0 | 0 |
| **Enjeux éthiques élevés** (Shrestha) | - | 0 | 0 | -- | - | + |
| **Maturité IA faible** (Shrestha) | ++ | + | 0 | -- | - | - |
| **Auditabilité requise** (Santoni de Sio, EU AI Act) | - | - | 0 | - | 0 | ++ |
| **Résilience aux échecs individuels** (benchmark) | -- | - | + | -- | 0 | ++ |
| **Réversibilité / rollback facile** (Kim & Kankanhalli) | ++ | ++ | + | 0 | 0 | + |

**Légende** : ++ = très adapté, + = adapté, 0 = neutre, - = peu adapté, -- = inadapté

### Justifications des verdicts

**Tâche prévisible et bien définie** : quand la tâche est simple et bien spécifiée, l'overhead de coordination de StigmergiAgentic n'est pas justifié. Direct Solo et CoT Solo suffisent avec un coût minimal. Le Graph Supervisor est aussi très adapté car le workflow pré-défini correspond bien à une tâche prévisible.

**Tâche complexe multi-étapes** : c'est le terrain de prédilection de la stigmergie. Les sous-tâches interdépendantes avec contraintes transversales bénéficient de la coordination indirecte. Le Planner-Executor échoue ici car le planificateur perd les contraintes transversales dans la décomposition (paradoxe documenté en A.2).

**Enjeux éthiques élevés** : la stigmergie offre une traçabilité par construction (audit trail, Meaningful Human Control). Le Planner-Executor est inadapté car la chaîne de responsabilité est opaque (le planificateur peut déléguer des décisions éthiquement sensibles sans contexte suffisant).

**Maturité IA faible** : une organisation peu mature en IA trouvera plus simple de déployer un agent unique (Direct Solo) qu'un système multi-agents avec environnement partagé. La stigmergie et le Planner-Executor nécessitent des compétences de configuration et d'interprétation plus avancées.

**Auditabilité requise** : la stigmergie produit un audit trail exhaustif par construction. Les architectures Solo ne tracent que l'entrée et la sortie, pas le processus intermédiaire.

**Résilience aux échecs individuels** : dans un système stigmergique, si un agent échoue sur une tâche, un autre agent peut la reprendre (le marker reste dans l'environnement). Dans un Direct Solo ou Planner-Executor, un échec individuel bloque tout le processus.

### Règles de décision synthétiques

À partir du tableau, cinq règles de décision émergent :

1. **Tâches simples, bien définies, sans enjeu de conformité** → **Direct Solo ou CoT Solo**. L'investissement dans une architecture complexe n'est pas justifié. CoT ajoute un raisonnement guidé pour un coût marginal.

2. **Tâches complexes, multi-étapes, sans enjeu fort de conformité** → **Self-Refine Solo**. Le pattern itératif (critique → révise) offre un bon rapport qualité/coût sans overhead de coordination multi-agents.

3. **Tâches complexes avec enjeux de gouvernance, conformité et auditabilité** → **StigmergiAgentic**. La coordination indirecte + l'audit trail par construction font la différence.

4. **Central Planner-Executor** → **À éviter hors prototypage rapide**. Le paradoxe throughput/qualité (58,5% delivery, 0,9% Final Pass) montre que cette architecture produit du volume sans valeur.

5. **Central Graph Supervisor** → **Contextes à workflow pré-défini et stable uniquement**. Adapté quand le processus est connu et ne change pas, mais rigide face aux imprévus.

---

## A.7 — Cas d'usage sectoriels illustratifs

### Agentic BPM et workflows organisationnels

L'Agentic Business Process Management, défini par Vu et al. (2026) et formalisé par Dumas et al. (2026), constitue un terrain d'application naturel. Les workflows traditionnels (BPMN, WfMC) prescrivent un chemin d'exécution rigide : tâche A → décision B → tâche C ou D. L'Agentic BPM propose des agents capables de raisonner sur les objectifs plutôt que de suivre des scripts.

La stigmergie opérationnalise cette vision : les markers sont les « tokens » du workflow, mais sans chemin pré-défini. Chaque agent évalue les markers disponibles et choisit sa prochaine action en fonction de l'état de l'environnement, pas d'un graphe prescrit. Cette flexibilité est précieuse dans les processus à forte variabilité (support client, gestion d'incidents, onboarding) où les cas exceptionnels sont fréquents et les workflows rigides créent des impasses.

**Conditions de déploiement** : organisation mature en BPM (capable de formaliser ses processus), volonté stratégique de passer du prescriptif à l'adaptatif, infrastructure technique pour héberger l'espace partagé.

**Jalon typique** : automatiser 30% des décisions de routage de processus via markers stigmergiques, avec rollback documenté vers le workflow classique.

### Migration et modernisation logicielle

C'est le cas central du mémoire. La transformation de code — qu'il s'agisse de migration cross-langage (COBOL → Java, Python 2 → Python 3), de refactoring architectural (monolithe → microservices) ou d'évolution d'API — est une **capacité dynamique** au sens de Teece (2007) : une compétence organisationnelle stratégique qui permet de s'adapter aux changements de l'environnement technologique.

L'orchestration stigmergique apporte trois avantages distinctifs dans ce contexte :
1. **Migration incrémentale** : chaque fichier ou module est représenté par un marker. Les agents traitent les modules dans l'ordre de leurs dépendances, émergeant du graphe de markers sans planification centralisée.
2. **Traçabilité complète** : chaque transformation est tracée dans l'audit trail, satisfaisant les exigences de conformité et de rollback.
3. **Résilience** : si un agent échoue sur un module complexe, un autre agent peut le reprendre, là où un pipeline séquentiel serait bloqué.

**Conditions de déploiement** : codebase suffisamment modularisée (les dépendances sont identifiables), équipe technique formée aux concepts de coordination indirecte, tests automatisés existants pour valider les transformations.

**Jalon typique** : migrer un module de 500 fichiers avec traçabilité complète, en comparant le coût et la qualité à une migration manuelle ou par pipeline classique.

### Coordination multi-outils / support opérationnel

Dans de nombreuses organisations, la coordination entre outils (monitoring, ticketing, CI/CD, alerting) repose déjà sur des artefacts partagés : tickets Jira, dashboards Grafana, logs centralisés, alertes PagerDuty. Les équipes ops ne se parlent pas toujours directement — elles réagissent aux traces laissées par les autres équipes dans ces systèmes.

Cette pratique existante est une forme de **stigmergie humaine** non formalisée. L'adoption d'une orchestration stigmergique algorithmique formalise et automatise ce pattern déjà en place, ce qui réduit potentiellement la friction de transition : les utilisateurs reconnaissent le modèle de coordination car il ressemble à ce qu'ils font déjà.

**Conditions de déploiement** : artefacts de coordination déjà en place (tickets, logs, dashboards), résistance au changement potentiellement plus faible car le modèle est familier, besoin de réduire le temps moyen de résolution (MTTR) des incidents.

**Jalon typique** : coordonner 3 outils de monitoring via artefacts partagés, mesurer la réduction du MTTR sur un échantillon de 50 incidents.

---

## A.8 — Limites et conditions de généralisation

### Limites empiriques

Les résultats présentés dans ce mémoire reposent sur une campagne d'évaluation contrôlée mais circonscrite :

- **Single backbone** : tous les résultats sont obtenus avec le même modèle LLM (qwen3.5-9b, modèle open-source de 9 milliards de paramètres). Les performances relatives des architectures pourraient varier avec des modèles plus puissants (GPT-4, Claude) ou plus faibles. Le protocole contrôlé (même backbone pour tous les bras) garantit la validité interne de la comparaison, mais pas la généralisation à d'autres backbones.

- **Un benchmark principal à ce stade** : TravelPlanner est un benchmark de planification sous contraintes, pas un benchmark de transformation de code. Les benchmarks de migration (PolyMigration) et de résolution de bugs (SWE-bench) sont en préparation et permettront de tester si les conclusions se transfèrent au domaine applicatif central du mémoire. Les résultats managériaux présentés ici seront renforcés ou nuancés par ces évaluations complémentaires.

- **Interprétation conditionnelle** : les résultats doivent être lus comme « comparaisons de philosophies d'organisation à backbone constant, sur un benchmark de planification sous contraintes, avec un modèle open-source de 9B paramètres ». Pas comme des revendications de supériorité universelle.

### Limites managériales

Les implications managériales de ce mémoire sont des **inférences théoriquement ancrées** à partir de résultats de benchmark, pas des observations de terrain :

- Pas de déploiement en contexte organisationnel réel. Les recommandations sur l'adoption, la résistance au changement et la transformation du rôle managérial sont déduites des cadres théoriques (Markus, Kim & Kankanhalli, Uhl-Bien, etc.) appliqués aux résultats empiriques, pas observées in vivo.

- Le **panel d'experts FEDS** (5-8 professionnels évaluant utilité, faisabilité, gouvernabilité et valeur organisationnelle) est planifié dans le dispositif d'évaluation et renforcera la validation managériale. Ce panel apportera une perspective « terrain » qui complètera les inférences théoriques.

### Conditions de généralisation

Les recommandations de ce mémoire s'appliquent aux contextes réunissant les conditions suivantes :
- La tâche est **complexe et multi-étapes**, avec des sous-tâches interdépendantes et des contraintes transversales
- La **qualité de livraison** prime sur la vitesse de production
- Un besoin d'**auditabilité et de traçabilité** existe (conformité réglementaire, accountability interne)
- L'organisation a une **maturité suffisante en IA** pour comprendre et opérer un système multi-agents

Hors de ces conditions, des architectures plus simples (Direct Solo, CoT Solo) peuvent suffire à moindre coût. Le tableau décisionnel de la section A.6 permet de naviguer ces conditions.

---

*Ce document est un draft pour relecture expert. Les chiffres définitifs de StigmergiAgentic seront consolidés à la fin de la campagne v5.1 en cours. Les benchmarks PolyMigration et SWE-bench enrichiront les sections A.2, A.6 et A.7 quand ils seront disponibles.*
