# Guide d'entretien - Entretien exploratoire complémentaire (DSR)

**Cadre méthodologique :** Entretien complémentaire informel au sens de la Source 3 du design de recherche (Venable et al., 2016) — enrichissement de la compréhension du contexte organisationnel.

**Interlocuteur :** Professionnel déjà interviewé en 2025 sur la résistance à l'IA. Profil orienté data/culture IA générale, peu d'expérience directe avec les systèmes multi-agents.

**Durée estimée :** 45-60 min

**Posture :** Semi-directive. Pas un entretien technique — on cherche des intuitions organisationnelles, des retours terrain, et une validation de la pertinence du problème.

---

## Phase 1 — Accroche et mise à jour (5-7 min)

**Objectif :** Renouer le contact, rappeler le contexte de l'entretien précédent, poser le cadre.

1. "Merci encore d'avoir accepté cet échange. On avait échangé l'année dernière sur la résistance à l'IA dans les organisations — ça m'avait beaucoup nourri. Depuis, mon sujet de mémoire a pas mal mûri et j'aimerais te présenter où j'en suis et avoir ton regard."

2. "Pour situer rapidement : mon mémoire porte sur l'orchestration de systèmes multi-agents IA, avec une approche inspirée de la biologie — la stigmergie. L'idée c'est que les agents ne se parlent pas directement, ils laissent des traces dans un environnement partagé, un peu comme les fourmis avec les phéromones."

3. "Est-ce que de ton côté, ta vision sur l'IA en entreprise a évolué depuis notre dernier échange ? Tu as vu des choses nouvelles côté adoption ou résistance ?"

---

## Phase 2 — Le problème de recherche (8-10 min)

**Objectif :** Valider la pertinence du problème auprès d'un praticien, sans rentrer dans les chiffres. Tester si le constat résonne avec son vécu.

4. "Ce que je constate dans mes recherches, c'est que quand on fait collaborer plusieurs agents IA ensemble, les approches actuelles fonctionnent un peu comme dans une entreprise très hiérarchique : il y a un agent chef qui distribue les tâches aux autres. Et en fait, ça marche assez mal — beaucoup d'échecs, des coûts qui explosent. Est-ce que toi, dans ton expérience, tu as vu ce genre de limites avec les approches très centralisées, même en dehors de l'IA ?"

5. "Et il y a un truc assez contre-intuitif qui ressort de la littérature : parfois un seul agent tout seul, sans coordination, fait mieux que tout un système multi-agents sophistiqué, et pour beaucoup moins cher. Comment tu interprètes ça ?"

6. "Et plus largement, dans les organisations que tu connais, la coordination entre équipes ou entre outils autonomes, ça se fait plutôt de manière hiérarchique, ou est-ce qu'il y a des formes de coordination plus naturelles, plus décentralisées ?"

---

## Phase 3 — Présentation de l'approche stigmergique (10-12 min)

**Objectif :** Expliquer l'artefact de recherche de manière accessible. Jauger la réaction.

7. "Du coup moi, ce que je propose, c'est de remplacer cette hiérarchie par quelque chose d'inspiré de la biologie. Ça s'appelle la stigmergie — c'est un concept des années 50, un chercheur français qui observait les termites. En gros, aucun termite ne donne d'ordres à un autre, mais ensemble ils construisent des trucs incroyablement complexes, juste en réagissant aux traces que les autres ont laissées. Moi j'applique ça aux agents IA : au lieu de se parler directement, ils déposent des marqueurs dans un espace partagé, et chacun regarde ce qui est disponible autour de lui pour décider quoi faire."

8. "Et concrètement, j'ai un prototype qui tourne. Les agents n'ont pas de rôle assigné au départ, il y a des garde-fous pour le budget et la traçabilité, et je l'ai testé sur un benchmark de planification de voyage où il s'en sort vraiment bien par rapport à ce qui existe dans la littérature."

9. "Qu'est-ce que ça t'évoque intuitivement ? Est-ce que cette idée de coordination sans chef te semble applicable dans des contextes organisationnels que tu connais ?"

10. "Et un truc que je trouve fascinant dans mes résultats, c'est que les agents finissent par se spécialiser tout seuls. Personne ne leur dit « toi tu fais ça », mais au bout d'un moment certains deviennent meilleurs sur certains types de tâches. Est-ce que tu vois un parallèle avec des dynamiques d'équipe que tu as pu vivre ou observer ?"

---

## Phase 4 — Gouvernance et acceptabilité (10-12 min)

**Objectif :** Explorer les enjeux organisationnels, de gouvernance, et d'acceptabilité — terrain où l'interlocuteur a de l'expertise (résistance à l'IA).

11. "Un des axes de mon mémoire c'est la gouvernance. L'EU AI Act (Article 14) impose un contrôle humain significatif sur les systèmes IA. Dans mon framework, chaque action est tracée dans un journal d'audit avec l'état avant/après. Mais est-ce que tu penses que la traçabilité technique suffit, ou est-ce qu'il faut aussi une gouvernance organisationnelle — des processus, des rôles, des décisions humaines dans la boucle ?"

12. "On avait parlé de résistance à l'IA l'année dernière. Si tu imagines qu'on déploie un système comme celui-là dans une organisation — des agents IA autonomes qui se coordonnent sans intervention humaine directe — quels seraient selon toi les principaux freins à l'acceptation ?"

13. "Comment tu verrais l'articulation entre l'autonomie des agents et le besoin de contrôle humain ? Où placer le curseur ?"

14. "Concrètement, si on déployait ce genre de système dans une boîte, qu'est-ce qui te semblerait indispensable pour que les gens gardent confiance ? Qu'est-ce qu'il faudrait mettre en place pour que ça passe ?"

---

## Phase 5 — Regard prospectif (5-7 min)

**Objectif :** Obtenir des perspectives futures et ouvrir naturellement vers le sujet CIFRE.

15. "Si tu devais imaginer les cas d'usage les plus pertinents pour ce type de coordination stigmergique en entreprise, tu penserais à quoi ?"

16. "Est-ce que tu vois des domaines ou des secteurs où la coordination décentralisée d'agents IA aurait une valeur particulière ?"

17. "Et d'ailleurs, l'année prochaine j'aimerais continuer ce travail dans un cadre plus appliqué, typiquement un contrat CIFRE pour rester entre la recherche et le terrain. Si jamais tu penses à des structures qui bossent sur ces sujets-là, je suis preneur."

---

## Phase 6 — Clôture (3-5 min)

18. "Pour conclure, si tu devais résumer en une phrase ce qui te semble le plus prometteur et le plus risqué dans cette approche, tu dirais quoi ?"

19. "Merci beaucoup pour ton temps et tes retours. Si tu es d'accord, je t'enverrai un résumé de ce qui ressort de notre échange."

---

## Notes pour la conduite de l'entretien

### Posture
- **Écoute active** : laisser l'interlocuteur développer, ne pas couper
- **Relances douces** : "Tu peux préciser ?", "Tu as un exemple en tête ?", "Qu'est-ce qui te fait dire ça ?"
- **Pas de jargon inutile** : adapter le vocabulaire, éviter les termes trop techniques (ACO, DSRM, FEDS...) sauf si l'interlocuteur les amène

### Points clés à capter
- [ ] Sa perception de la pertinence du problème (coordination multi-agents)
- [ ] Ses intuitions sur l'acceptabilité organisationnelle de systèmes autonomes
- [ ] Son regard sur gouvernance technique vs. organisationnelle
- [ ] Ses idées de cas d'usage pertinents
- [ ] Des contacts potentiels pour CIFRE ou évaluation expert
- [ ] Des évolutions dans sa vision de la résistance à l'IA depuis 2025

### Liens avec le cadre DSR
Cet entretien s'inscrit dans la **Source 3** du design de recherche : "entretiens complémentaires informels avec des praticiens du terrain (data scientists, responsables IA, managers de programmes de transformation) pourront enrichir la compréhension du contexte organisationnel et nourrir la discussion" (revue v2 DSR, l. 2097-2100).

Les données collectées alimenteront la **discussion** du mémoire, pas l'évaluation formelle de l'artefact (qui relèvera du panel d'experts FEDS).

### Transition CIFRE
La question 17 introduit le sujet CIFRE de manière organique — après avoir présenté le travail et obtenu un regard prospectif, la mention du CIFRE apparaît comme une suite logique plutôt qu'une demande forcée. Si l'interlocuteur rebondit, approfondir. Sinon, ne pas insister.

---

## Antisèche — Réponses aux questions techniques possibles

### "L'espace partagé, concrètement c'est quoi ?"
C'est une base de données SQLite locale. Chaque marqueur est une ligne dans cette base : il a un type (par exemple "rechercher les vols"), un état (en cours, terminé, échoué...), une intensité qui décroît avec le temps, et des métadonnées. Les agents n'écrivent et ne lisent que dans cette base — c'est leur seul moyen de se coordonner. C'est un peu comme un tableau Kanban partagé, sauf qu'aucun humain ne déplace les cartes : les agents le font eux-mêmes en réagissant à ce qu'ils voient dessus.

### "Les agents, c'est quoi exactement ? Des instances de GPT ?"
Chaque agent, c'est un bout de code qui fait une boucle : il regarde les marqueurs disponibles, il en choisit un, il appelle un LLM (un modèle de langage) pour décider quoi faire, il exécute l'action, et il dépose un nouveau marqueur avec le résultat. Le LLM peut être n'importe quel modèle — dans mes tests j'utilise un modèle open source, Qwen, qui tourne à moindre coût via une API. Mais le framework est agnostique, on pourrait brancher GPT, Claude, ou un modèle local.

### "C'est quoi la différence avec CrewAI, AutoGen, ou les trucs qui existent déjà ?"
Les frameworks existants assignent des rôles fixes aux agents (« toi tu es le chercheur, toi le rédacteur ») et un orchestrateur central décide qui fait quoi. Chez moi, personne n'a de rôle au départ. Les agents se spécialisent naturellement en fonction de ce qui marche — un peu comme dans une équipe auto-organisée. Et surtout il n'y a pas de chef : la coordination passe uniquement par les traces dans l'environnement.

### "Comment les agents choisissent quoi faire ? C'est aléatoire ?"
Non. Chaque marqueur a une intensité — plus il est intense, plus il attire les agents. C'est inspiré des colonies de fourmis : les phéromones les plus fortes attirent plus de passage. Ensuite il y a une part de stochasticité contrôlée (un softmax sur les intensités) pour que les agents explorent aussi des pistes moins évidentes. Et avec le temps, l'intensité décroît naturellement si personne ne s'en occupe — les tâches abandonnées finissent par disparaître.

### "Ça tourne sur quoi ? Il faut un serveur ?"
Non, tout tourne en local sur une machine. La base SQLite est un fichier sur disque, les agents tournent en parallèle dans des tâches Python asynchrones, et les appels LLM passent par une API (OpenRouter dans mon cas). Pas besoin d'infrastructure lourde.

### "Tu dis 100% de réussite sur ton benchmark, c'est pas trop beau ?"
C'est sur un échantillon de 10 requêtes de test du benchmark TravelPlanner. Le résultat publié le plus élevé dans la littérature, c'est 32% avec GPT-4o sur le dataset complet. Moi j'utilise un modèle plus petit (Qwen 3.5 9B) sur un sous-ensemble — donc c'est encourageant mais il faudra valider sur le dataset complet avec des intervalles de confiance pour que ce soit solide scientifiquement. C'est prévu dans la suite du mémoire.

### "Les garde-fous, ça fonctionne comment ?"
Il y a plusieurs niveaux. Un budget maximum en tokens/coût — si on le dépasse, tout s'arrête. Un nombre maximum de retries par tâche — un agent ne peut pas boucler indéfiniment sur un truc qui échoue. Un système de verrous avec durée de vie — si un agent bloque trop longtemps sur une tâche, le verrou expire et un autre agent peut la reprendre. Et chaque action est tracée dans un journal d'audit : on sait quel agent a fait quoi, quand, et quel était l'état avant et après.

### "C'est quoi la stigmergie exactement, ça vient d'où le mot ?"
Le mot vient du grec : stigma (marque, signe) et ergon (travail). C'est Pierre-Paul Grassé, un biologiste français, qui l'a inventé en 1959 en étudiant les termites. L'idée c'est que le travail lui-même laisse des traces qui stimulent le travail suivant. Les termites ne se parlent pas, ils réagissent à ce que les autres ont construit. Et ça donne des structures ultra-complexes sans aucune planification centrale. C'est ce principe-là que j'applique aux agents IA.

### "Pourquoi pas juste un seul agent qui fait tout ?"
C'est une vraie question, et la littérature montre que parfois un seul agent suffit. Mais quand la tâche devient complexe — plusieurs étapes interdépendantes, besoin de parallélisme, domaines variés — un seul agent atteint ses limites. L'intérêt du multi-agents stigmergique, c'est que la complexité est gérée par le collectif, pas par un seul cerveau. Et le coût peut rester maîtrisé parce qu'on utilise des modèles plus petits en parallèle plutôt qu'un seul gros modèle.

### "L'EU AI Act, ça impose quoi concrètement ?"
L'Article 14 exige qu'un humain puisse comprendre ce que le système fait, intervenir si nécessaire, et avoir une vue d'ensemble des décisions prises. Dans mon framework, le journal d'audit permet de retracer chaque décision. Mais c'est la partie technique — la partie organisationnelle (qui regarde le journal, qui décide d'intervenir, quels processus mettre en place), c'est justement un des axes de recherche de mon mémoire.
