# POC V0.2 — Stigmergie Distribuee avec Agents Generalistes

## Contexte

Le POC V0.1 (Sprints 1-5) fonctionne mais viole trois principes fondamentaux de la stigmergie biologique :

1. **Monopole du Scout** : Seul le Scout cree des taches. Chez les fourmis, **toute fourmi** depose des pheromones.
2. **Roles fixes** : 4 agents specialises avec un round-robin impose. Chez les fourmis, les individus sont **homogenes** — la division du travail **emerge** de l'environnement, elle n'est pas codee en dur.
3. **Execution sequentielle** : Un seul agent agit a la fois. Dans une colonie, **des centaines de fourmis agissent simultanement**, comme quand elles deplacent une feuille ensemble.

V0.2 passe a des **agents generalistes** executant en **parallele** : chaque agent possede toutes les capacites, est guide par les pressions phermonales, et travaille simultanement avec les autres. L'objectif commun est derive du prompt initial — le systeme est concu pour etre **generaliste** (migration Py2->Py3 est un cas d'usage, pas une limitation).

---

## Fondation Scientifique (2025-2026)

| Reference | Contribution cle | Impact sur V0.2 |
|---|---|---|
| Rodriguez (2026) arXiv:2601.08129 | Pressure fields + temporal decay : 48.5% vs 1.5% hierarchique. **Agents role-free** | Modele direct : agents generalistes + pressions |
| PFACO (2026) arXiv:2601.07597 | Toute fourmi depose des pheromones (deposition symetrique) | Tout agent cree des taches |
| MacNet (ICLR 2025) | Scaling law collaboratif : topologies irregulieres > regulieres | Justifie l'execution parallele adaptive |
| Emergent Collective Memory (2025) arXiv:2512.10166 | Intelligence collective emergente. **Seuil critique de densite** (phase transition) | Motive l'etude du nombre d'agents optimal |
| Lessons Learned (IBM, NeurIPS 2025) arXiv:2505.23946 | Agents apprennent des traces des autres | Lesson bank dans quality.json |
| LocAgent (ACL 2025) | Graphe de code + multi-hop reasoning = 92.7% localisation | Import graph pour priorisation |
| Hydra (2026) arXiv:2602.11671 | Indexation structure-aware >> NLP chunking | Valide AST > regex |
| TransAgent (2024) arXiv:2409.19894 | 4 agents code translation (communication directe) | Comparaison : meme tache, coordination differente |
| Environment-in-the-Loop (ICSE 2026) | Migration incomplete sans interaction environnement | Le test + validation = partie du medium |
| EvoMAC (ICLR 2025) | Feedback environnemental evolue les comportements | Reinforcement/evaporation evolue la colonie |

---

## Architecture V0.2 : Agents Generalistes Paralleles

### Principe

```
    +--------------------------------------------------------------+
    |                OBJECTIF COMMUN (du prompt)                    |
    |  "Migrer cette codebase Python 2 vers Python 3"              |
    |  (ou tout autre objectif — le systeme est generaliste)       |
    +------------------------------+-------------------------------+
                                   |
    +------------------------------v-------------------------------+
    |              ENVIRONNEMENT (Champ Pheromonale)               |
    |  tasks.json    (pheromones de tache)                          |
    |  status.json   (pheromones de statut + scope locks)           |
    |  quality.json  (pheromones de qualite + lessons)              |
    |  target_repo/  (artefact — TOUT fichier, pas juste .py)      |
    |  audit_log.jsonl (trace d'audit)                             |
    +------------------------------+-------------------------------+
                                   |
    +------------------------------v-------------------------------+
    |              CHAMP DE PRESSIONS (calcule)                    |
    |  P_discover   = f(fichiers non decouverts)                   |
    |  P_transform  = f(fichiers pending)                          |
    |  P_test       = f(fichiers transformed)                      |
    |  P_validate   = f(fichiers tested)                           |
    +------------------------------+-------------------------------+
                                   |
    ===============================|================================
              EXECUTION PARALLELE (threading / async)
    ===============================|================================
         |          |          |          |          |
    +----v--+ +----v--+ +----v--+ +----v--+ +----v--+
    |Agent 1| |Agent 2| |Agent 3| |Agent 4| |  ...  |
    |discov.| |transf.| |transf.| | test  | |Agent N|
    +-------+ +-------+ +-------+ +-------+ +-------+
         |          |          |          |          |
         +----------+----------+----------+----------+
                    Scope locks empechent les conflits
                    Chaque agent peut faire N'IMPORTE quoi
```

**Analogie biologique** : Plusieurs fourmis deplacent une grande feuille en meme temps. Elles sont coordonnees par les forces physiques (= pressions phermonales) sans se parler. Chacune ajuste sa contribution en temps reel.

### Objectif Commun

Le prompt initial (`--repo <url>` ou toute instruction) est decompose en un **objectif** partage stocke dans l'environnement (`objective.json`). Les agents ne recoivent pas d'instructions individuelles — ils lisent l'objectif dans l'environnement et agissent en consequence. Pour la migration Py2->Py3, l'objectif est : "Migrer tous les fichiers Python 2 vers Python 3 avec tests et validation". Mais le systeme pourrait traiter n'importe quel objectif decomposable en taches.

### Determination de N (nombre d'agents)

| Strategie | Description |
|---|---|
| **Fixe (defaut)** | `num_agents: 4` dans config. Simple, reproductible. |
| **Proportionnel** | `N = ceil(total_files / files_per_agent)`. Ex: 23 fichiers / 6 = 4 agents. |
| **Adaptatif** | Demarre avec N_min. Ajoute un agent quand la pression moyenne > seuil. Retire quand tous idle. Borne par N_max. |

Pour le POC, on implemente le mode **fixe** avec le mode **proportionnel** en option. Le mode adaptatif est note pour V0.3.

### Parallelisme et Coordination

Les agents s'executent en **parallele** (threads Python ou asyncio) au sein de chaque tick :

```python
# Chaque tick :
with ThreadPoolExecutor(max_workers=num_agents) as pool:
    futures = [pool.submit(agent.run) for agent in agents]
    results = [f.result() for f in futures]
```

**Coordination sans collision** :
- **Scope lock** (existant dans pheromone_store) : `fcntl.flock` assure qu'un seul agent modifie un fichier JSON a la fois
- **Status lock** (existant) : un agent acquiert `in_progress` sur un fichier -> les autres le voient et choisissent un autre fichier
- **Ordre de perception** : chaque agent percoit l'environnement AU DEBUT du tick (snapshot). Les actions paralleles modifient l'environnement, mais les decisions sont basees sur le snapshot d'entree du tick
- **Conflict resolution** : si deux agents tentent le meme fichier, le premier a acquerir le scope lock gagne, l'autre passe au fichier suivant

### Permissions — Tout agent, toute pheromone

Plus de table de permissions par role. Le **scope lock** est le seul garde-fou. Un agent travaillant sur `utils.py` empeche tout autre agent de modifier `utils.py`.

### Machine a Etats — Inchangee

Les etats et transitions restent identiques a V0.1. C'est l'environnement qui est stable — ce sont les agents qui changent.

---

## Plan de Sprints

### Sprint 6 : Extraction des Capacites (3 jours)

**Objectif** : Extraire la logique des 4 agents V0.1 en 4 modules de capacite reutilisables, sans changer le comportement. Refactoring pur.

**Fichiers a creer** :
- `agents/capabilities/__init__.py`
- `agents/capabilities/discover.py` — Extrait de `scout.py` : detection patterns (regex + AST + LLM), scoring, normalisation. Regarde **tout fichier** du repo, pas juste `.py`. Fonction : `discover_files(store, repo_path, llm_client, config) -> list[dict]`
- `agents/capabilities/transform.py` — Extrait de `transformer.py` : selection fichier, few-shot, appel LLM, syntax gate. Fonction : `transform_file(store, repo_path, llm_client, file_key, config) -> dict`
- `agents/capabilities/test.py` — Extrait de `tester.py` : pytest, fallback adaptatif, confidence. Fonction : `test_file(store, repo_path, file_key, config) -> dict`
- `agents/capabilities/validate.py` — Extrait de `validator.py` : commit/revert/escalade. Fonction : `validate_file(store, repo_path, file_key, config, dry_run) -> dict`
- `tests/test_capabilities.py` — 4 tests (une capacite = une fonction testable en isolation)

**Fichiers a modifier** :
- `agents/scout.py` -> wrapper mince -> `capabilities.discover`
- `agents/transformer.py` -> wrapper mince -> `capabilities.transform`
- `agents/tester.py` -> wrapper mince -> `capabilities.test`
- `agents/validator.py` -> wrapper mince -> `capabilities.validate`

**Contrainte** : tous les tests V0.1 existants passent sans modification. Zero regression.

**Livrable** : Capacites decoupees, reutilisables par n'importe quel agent.

---

### Sprint 7 : Agent Generaliste + Execution Parallele (5 jours)

**Objectif** : Creer le `StigmergicAgent` generaliste, le scheduler reactif, et l'execution parallele. C'est le coeur de V0.2.

**Fichiers a creer** :
- `agents/stigmergic_agent.py` — Agent generaliste :
  ```python
  class StigmergicAgent(BaseAgent):
      """Generalist agent — any ant can do any task."""

      def __init__(self, name, config, store, repo_path, llm_client, objective):
          self.capabilities = {
              "discover": DiscoverCapability(...),
              "transform": TransformCapability(...),
              "test": TestCapability(...),
              "validate": ValidateCapability(...),
          }
          self.objective = objective  # Objectif commun lu depuis l'environnement

      def perceive(self) -> dict:
          """Snapshot complet de l'environnement : tasks, status, quality, files."""

      def decide(self, perception: dict) -> dict:
          """Calcule pressions par action, choisit la plus haute.
          Selectionne un fichier disponible (non locke) pour l'action choisie."""

      def execute(self, action: dict) -> dict:
          """Dispatch vers la capacite choisie."""

      def deposit(self, result: dict) -> None:
          """Depose traces. Tout agent ecrit dans toute pheromone."""
  ```

- `stigmergy/scheduler.py` — Scheduler + parallelisme :
  ```python
  def run_tick_parallel(agents, store, config) -> dict:
      """Execute tous les agents en parallele au sein d'un tick.

      1. Snapshot environnement (point de perception commun)
      2. Chaque agent decide independamment (basee sur snapshot)
      3. Execution parallele (ThreadPoolExecutor)
      4. Depot sequentiel des resultats (fcntl locking)
      5. Retourne metriques du tick
      """
  ```

- `tests/test_stigmergic_agent.py` — 9 tests
- `tests/test_scheduler.py` — 6 tests dont tests de concurrence

**Fichiers a modifier** :
- `stigmergy/loop.py` — Nouveau mode `"stigmergic_v2"` avec `run_tick_parallel()` :
  ```python
  if mode == "stigmergic_v2":
      agents = [StigmergicAgent(f"ant_{i}", ...) for i in range(N)]
      for tick in range(max_ticks):
          maintain_status(store)
          apply_decay(store)
          tick_result = run_tick_parallel(agents, store, config)
          record_tick(tick, tick_result)
          if check_stop(store, config, tick_result): break
  ```
- `agents/base_agent.py` — Proprietes `pressure`, `chosen_action`, `active_file`
- `metrics/collector.py` — Nouveaux champs par tick :
  - `agent_actions`: `{"ant_0": "discover", "ant_1": "transform", "ant_2": "transform", "ant_3": "test"}`
  - `agent_files`: `{"ant_0": "utils.py", "ant_1": "main.py", "ant_2": "cli.py", "ant_3": "config.py"}`
  - `pressures`: `{"discover": 0.3, "transform": 0.6, "test": 0.2, "validate": 0.1}`
  - `parallel_utilization`: `0.75` (agents actifs / total agents)
- `main.py` — Args `--scheduler-mode stigmergic_v2 --num-agents N`
- `stigmergy/config.yaml` :
  ```yaml
  scheduler:
    mode: "stigmergic_v2"       # "round_robin" (V0.1) | "stigmergic_v2" (V0.2)
    num_agents: 4               # N agents generalistes
    num_agents_mode: "fixed"    # "fixed" | "proportional"
    files_per_agent: 6          # Pour mode proportional : N = ceil(total/fpa)
    activation_threshold: 0.01
    pressure_weights:
      discover: 1.0
      transform: 1.2
      test: 1.0
      validate: 1.0
  ```

**Tests Sprint 7** :
- `test_agent_perceives_full_environment`
- `test_agent_selects_highest_pressure_action`
- `test_agent_discovers_new_files` (pas juste .py)
- `test_agent_transforms_pending_file`
- `test_two_agents_parallel_different_files` : 2 agents en parallele, fichiers differents, pas de conflit
- `test_parallel_scope_lock_prevents_collision` : 2 agents tentent le meme fichier -> un seul reussit
- `test_emergent_ordering` : premier tick = surtout discover, ticks suivants = transform, etc.
- `test_round_robin_backward_compat`
- `test_pressure_all_zero_empty_repo`
- `test_proportional_num_agents` : 23 fichiers / 6 = 4 agents
- `test_parallel_execution_faster_than_sequential` : 4 agents en parallele terminent en moins de ticks

**Livrable** : N agents generalistes travaillant en parallele, coordonnes par l'environnement.

---

### Sprint 8 : Lesson Banking + Import Graph (3 jours)

**Objectif** : Enrichir l'environnement : lessons des migrations passees (IBM NeurIPS 2025) + graphe d'imports pour priorisation (LocAgent ACL 2025).

#### Partie A : Lesson Banking

- `agents/capabilities/test.py` — Extraire `lessons` structurees apres chaque test
- `agents/capabilities/transform.py` — Lire le lesson bank pour enrichir le few-shot (stigmergie cognitive)
- Format quality.json etendu (additif) : champ `lessons: [{pattern, resolution, effectiveness, source_file}]`

#### Partie B : Import Graph Simple

- `agents/code_graph.py` — Graphe AST imports seulement : `build()`, `get_reverse_deps()`, `get_migration_order()`, `get_impact_set()`
- `agents/capabilities/discover.py` — Scoring enrichi par reverse deps (fichiers hub = priorite haute)
- Toggle `graph.enabled: true` dans config

**Tests** : 9 tests (5 graph + 4 lessons)

**Livrable** : Environnement enrichi avec intelligence collective.

---

### Sprint 9 : Docker Benchmarks Paralleles + Metriques d'Emergence (4 jours)

**Objectif** : Benchmarks 100% Docker, execution parallele des configurations, metriques d'emergence riches.

#### Partie A : Infrastructure Docker

**Fichiers a creer/modifier** :
- `docker-compose.benchmark.yml` — Compose file dedie benchmarks :
  ```yaml
  services:
    bench-stigmergic-v1:
      build: .
      command: python main.py --repo ${REPO} --repo-ref ${REF} --scheduler-mode round_robin
      volumes: [./metrics/output/v1_run_${RUN}:/app/metrics/output]
      deploy: { resources: { limits: { cpus: '2' } } }

    bench-stigmergic-v2:
      build: .
      command: python main.py --repo ${REPO} --repo-ref ${REF} --scheduler-mode stigmergic_v2 --num-agents 4
      volumes: [./metrics/output/v2_run_${RUN}:/app/metrics/output]

    bench-single-agent:
      build: .
      command: python baselines/single_agent.py --repo ${REPO} --repo-ref ${REF}
      volumes: [./metrics/output/sa_run_${RUN}:/app/metrics/output]

    bench-sequential:
      build: .
      command: python baselines/sequential.py --repo ${REPO} --repo-ref ${REF}
      volumes: [./metrics/output/seq_run_${RUN}:/app/metrics/output]
  ```

- `scripts/benchmark_parallel.sh` — Lance les 4 configurations x 5 runs en parallele :
  ```bash
  #!/bin/bash
  # Lance 4 conteneurs en parallele pour chaque run
  for RUN in 1 2 3 4 5; do
    REPO=$1 REF=$2 RUN=$RUN docker compose -f docker-compose.benchmark.yml up -d
    # Attend que les 4 conteneurs finissent
    docker compose -f docker-compose.benchmark.yml wait
  done
  # Agrege les resultats
  python metrics/pareto.py --input-dir metrics/output --output metrics/output/pareto_v2.png \
    --require-baselines stigmergic_v1,stigmergic_v2,single_agent,sequential
  ```

- `Makefile` — Cibles `make benchmark`, `make benchmark-parallel`

#### Partie B : Metriques d'Emergence

| Metrique | Type | Ce qu'on observe |
|---|---|---|
| `action_distribution` | Dict[agent_id -> Dict[action -> count]] | Chaque agent fait-il tout ou se specialise-t-il ? |
| `emergent_specialization` | Float (entropie Shannon) | 1.0 = parfait generaliste, 0.0 = specialiste pur |
| `specialization_per_agent` | List[Float] | Entropie par agent — certains se specialisent-ils plus ? |
| `task_source_distribution` | Dict[agent_id -> count] | Qui cree le plus de taches ? |
| `collaboration_density` | Float | Combien de fichiers sont touches par >1 agent ? (fourmis sur la feuille) |
| `parallel_utilization` | Float per tick | % d'agents actifs par tick (idle = fourmi au repos) |
| `action_switching_rate` | Float per agent | Combien de fois un agent change d'action type entre ticks ? |
| `pheromone_read_write_ratio` | Float | Lectures vs ecritures — le systeme converge-t-il ? |
| `convergence_tick` | Int | Tick ou 80% des fichiers sont terminaux |
| `lesson_reuse_rate` | Float | % de transforms qui utilisent des lessons |
| `graph_hub_first_rate` | Float | Les hubs sont-ils migres en premier ou en dernier ? |
| `scope_lock_contention` | Int per tick | Combien de tentatives de lock echouent (indicateur de congestion) |

**Export** : CSV par tick + JSON summary + dashboard PNG (matplotlib multi-panel).

#### Partie C : Pareto V0.2

- `metrics/pareto.py` — 4 configurations : `stigmergic_v1`, `stigmergic_v2`, `single_agent`, `sequential`
- Nouveau: Pareto par N agents (N=2, 4, 8) pour etudier le scaling law
- Export JSON enrichi avec toutes les metriques d'emergence

**Tests** :
- `test_benchmark_docker_compose_valid` : docker compose config valide
- `test_pareto_supports_v2_names`
- `test_metrics_include_emergence_fields`

**Livrable** : Benchmarks reproductibles Docker, metriques d'emergence, analyse Pareto V0.1 vs V0.2.

---

## Resume des Fichiers

### Nouveaux Fichiers (14)

| Fichier | Sprint | Objectif |
|---|---|---|
| `agents/capabilities/__init__.py` | 6 | Package capacites |
| `agents/capabilities/discover.py` | 6 | Capacite decouverte (ex-Scout) |
| `agents/capabilities/transform.py` | 6 | Capacite transformation (ex-Transformer) |
| `agents/capabilities/test.py` | 6 | Capacite test (ex-Tester) |
| `agents/capabilities/validate.py` | 6 | Capacite validation (ex-Validator) |
| `agents/stigmergic_agent.py` | 7 | Agent generaliste V0.2 |
| `stigmergy/scheduler.py` | 7 | Scheduler reactif + parallelisme |
| `agents/code_graph.py` | 8 | Graphe d'imports AST |
| `docker-compose.benchmark.yml` | 9 | Compose benchmarks paralleles |
| `scripts/benchmark_parallel.sh` | 9 | Script lancement benchmarks |
| `tests/test_capabilities.py` | 6 | Tests capacites |
| `tests/test_stigmergic_agent.py` | 7 | Tests agent generaliste |
| `tests/test_scheduler.py` | 7 | Tests scheduler + concurrence |
| `tests/test_code_graph.py` | 8 | Tests graphe |

### Fichiers Modifies

| Fichier | Sprint(s) | Changements |
|---|---|---|
| `agents/scout.py` | 6 | Wrapper mince -> capabilities.discover |
| `agents/transformer.py` | 6 | Wrapper mince -> capabilities.transform |
| `agents/tester.py` | 6 | Wrapper mince -> capabilities.test |
| `agents/validator.py` | 6 | Wrapper mince -> capabilities.validate |
| `agents/base_agent.py` | 7 | Proprietes pressure, chosen_action, active_file |
| `stigmergy/loop.py` | 7 | Mode stigmergic_v2 + run_tick_parallel |
| `stigmergy/config.yaml` | 7,8,9 | Sections scheduler, graph, lessons |
| `metrics/collector.py` | 7,9 | Champs emergence, pressions, actions paralleles |
| `metrics/pareto.py` | 9 | Noms V0.2, scheduler_mode, scaling analysis |
| `baselines/single_agent.py` | 9 | Champ architecture |
| `baselines/sequential.py` | 9 | Champ architecture |
| `main.py` | 7 | Args --scheduler-mode, --num-agents |
| `Dockerfile` | 9 | Optimiser pour benchmarks |
| `Makefile` | 9 | Cibles benchmark |

---

## Backward Compatibility

| Config | Comportement |
|---|---|
| `scheduler.mode: "round_robin"` | V0.1 exact : 4 agents specialises, sequentiel |
| `scheduler.mode: "stigmergic_v2"` | V0.2 : N agents generalistes, paralleles |
| `graph.enabled: false` | Scoring V0.1 |

Pheromones V0.1 lisibles par V0.2 (champs additifs).

---

## Verification

Pour chaque sprint :
1. `uv run pytest tests/ -v` — zero regression
2. `docker compose run --rm test` — tests en Docker
3. Run E2E depot synthetique

Sprint 9 :
4. `make benchmark-parallel` — 4x5 runs en Docker
5. Pareto V0.1 vs V0.2 + analyse emergence
6. Tests scaling N=2, 4, 8

---

## Sequencage

| Sprint | Duree | Risque |
|---|---|---|
| Sprint 6 (Capabilities) | 3 jours | Faible : refactoring pur |
| Sprint 7 (Agent + Parallelisme) | 5 jours | Haut : concurrence + scope locks |
| Sprint 8 (Lessons + Graph) | 3 jours | Faible : additif |
| Sprint 9 (Docker Benchmarks) | 4 jours | Moyen : infra Docker |

**Total** : ~15 jours de dev.

---

## V0.3 — Vision Future (note)

**Roles generes dynamiquement** : A chaque lancement, le systeme analyse l'objectif et genere automatiquement les roles/capacites necessaires. Au lieu de 4 capacites hardcodees (discover/transform/test/validate), le LLM decompose l'objectif en N capacites ad hoc et les assigne dynamiquement. Le systeme de validation/test est completement repense pour etre domain-agnostic. Le nombre d'agents N est determine par un mecanisme adaptatif avec phase transition (Emergent Collective Memory, 2025).
