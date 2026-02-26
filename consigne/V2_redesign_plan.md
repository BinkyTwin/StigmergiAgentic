# Plan V2.0 : Framework Stigmergique Generaliste — Redesign from Scratch

## Contexte

Le POC V0.1 (Sprints 1-6) fonctionne mais viole les principes fondamentaux de la stigmergie :
- **Agents contraints** : 19 patterns regex hardcodes, roles fixes (Scout/Transformer/Tester/Validator)
- **Orchestration hierarchique** : round-robin sequentiel = le code impose l'ordre, pas l'environnement
- **Couple au domaine** : chaque fichier (prompts, capabilities, config) est lie a Python 2->3
- **Pas de parallelisme** : un seul agent agit par tick, contrairement aux fourmis reelles

La nouvelle revue de litterature DSR definit 5 objectifs de conception (OC1-OC5) et 3 iterations de validation sur des benchmarks distincts. Le framework doit etre **generaliste**, **decentralise**, et **fonde theoriquement**.

### Decisions confirmees

| Decision | Choix | Raison |
|---|---|---|
| **Iteration 1** | TravelPlanner | Force la generalite — evite de re-coupler au code |
| **Repo** | Branche `v2/main` dans le repo actuel | Garde historique Git, PDFs, revue de litt |
| **Timeline** | Pas de contrainte — beaucoup de temps et d'agents IA | Ambition maximale sur les 3 iterations DSR |
| **Marker Store** | SQLite (WAL mode) | ACID, requetes, lectures concurrentes, robuste en parallele |

### Objectifs de conception (DSR)

| OC | Objectif | Benchmark de validation |
|---|---|---|
| OC1 | Architecture generaliste applicable a des taches variees | TravelPlanner + Code Migration |
| OC2 | Specialisation emergente sans assignation explicite de roles | Metriques d'emergence (entropie Shannon) |
| OC3 | Surpasser les frameworks centralises sur TravelPlanner | >= 32.2% score final (baseline SwarmAgentic) |
| OC4 | Competitivite sur transformation de code | PolyMigration + SWE-bench |
| OC5 | Gouvernance et auditabilite (EU AI Act Art. 14) | Panel d'experts + audit completeness |

---

## Architecture

### Philosophie : Chaque decision tracee a une theorie

| Principe | Source theorique |
|---|---|
| Coordination indirecte via traces environnementales | Grasse (1959), Heylighen (2016a) |
| Agents homogenes, roles emergents | Rodriguez (2026), Heylighen (2016b) |
| Artefacts inspectables et controlables | Ricci et al. (2007) - Agents & Artifacts |
| Champs de pression pour selection d'action | Rodriguez (2026) arXiv:2601.08129 |
| Selection probabiliste basee sur intensite | Bonabeau et al. (1999) |
| Depot symetrique (tout agent depose) | PFACO (2026) arXiv:2601.07597 |
| Separation calcul / coordination | Carriero & Gelernter (1992) |
| Deep norms (stables) + surface norms (emergentes) | Grisold et al. (2025) |
| Evaporation et decroissance temporelle | Parunak et al. (2005) |
| Auto-organisation par feedback local | Serugendo et al. (2005) |
| Frontiere de Pareto cout-precision | Kapoor et al. (2024) |
| Audit complet pour supervision humaine | EU AI Act Art. 14, Fink (2025) |

### Vue d'ensemble (5 couches)

```
+-------------------------------------------------------------------+
|  COUCHE ADAPTATEUR (domain-specific)                               |
|  TravelPlanner | CodeMigration | SWE-bench | custom               |
|  [Carriero & Gelernter 1992: orthogonalite calcul/coordination]    |
+-------------------------------------------------------------------+
|  COUCHE ORCHESTRATEUR (tick loop parallele)                        |
|  Snapshot -> Decide -> Lock -> Execute -> Deposit -> Decay         |
|  [Serugendo et al. 2005: auto-organisation par regles locales]     |
+-------------------------------------------------------------------+
|  COUCHE AGENTS (N agents homogenes)                                |
|  perceive -> compute_pressures -> select_action -> execute ->      |
|  deposit                                                           |
|  [Rodriguez 2026: agents role-free; Heylighen 2016: any ant]       |
+-------------------------------------------------------------------+
|  COUCHE ENVIRONNEMENT (MarkerStore + Workspace + Guardrails)       |
|  Markers dynamiques, audit JSONL, scope locks, decay               |
|  [Ricci et al. 2007: Agents & Artifacts; Gelernter 1985: tuples]   |
+-------------------------------------------------------------------+
|  COUCHE INFRASTRUCTURE                                             |
|  LLM client, tool registry, file I/O, Git, Web                    |
+-------------------------------------------------------------------+
```

### Modele de Markers (Pheromones Generiques)

Remplace les 3 fichiers JSON (tasks/status/quality) par un store unifie :

```python
@dataclass
class Marker:
    """Pheromone generique — toute trace deposee dans l'environnement.

    Combine stigmergie quantitative (intensity, Theraulaz & Bonabeau 1999)
    et stigmergie qualitative (marker_type -> reponses differentes).
    Implemente la stigmergie basee sur marqueurs (Heylighen 2016b).
    """
    id: str                    # UUID
    marker_type: str           # Dynamique: "task", "progress", "quality", "lesson", etc.
    target: str                # Cible (chemin fichier, id plan, etc.)
    intensity: float           # [0.0, 1.0] — signal quantitatif
    state: str                 # Etat FSM (defini par l'adaptateur)
    payload: dict[str, Any]    # Donnees domain-specific (opaque au framework)

    # Tracabilite (EU AI Act Art. 14)
    created_by: str            # Agent ID
    created_at: str            # ISO-8601
    updated_by: str            # Dernier agent a modifier
    updated_at: str            # Derniere modification

    # Coordination
    lock_owner: str | None     # Scope lock (mutex par item)
    lock_tick: int | None      # Tick d'acquisition
    inhibition: float          # Anti-oscillation gamma (Rodriguez 2026)
    retry_count: int           # Compteur de retries
    history: list[str]         # Journal des transitions d'etat
```

**Machine a etats** : definie par l'adaptateur, pas par le framework. Etats de base :
```
pending -> active -> completed -> verified -> terminal
pending -> active -> failed -> retry -> pending (avec inhibition += 0.5)
any -> skipped (max retries depasse)
any -> escalated (needs human review)
```

**Stockage** : SQLite (WAL mode) pour :
- Transactions ACID (remplace fcntl.flock fragile)
- Requetes SQL (remplace l'implementation custom de query())
- Lectures concurrentes + ecriture unique
- Portable (fichier unique)
- Export JSON pour inspection humaine

### Modele d'Agent (Generaliste)

```python
class StigmergicAgent:
    """Agent homogene guide par les pressions environnementales.

    Tout agent est identique. La specialisation emerge de :
    1. Quelle pression est la plus haute quand l'agent percoit (stochastique)
    2. Quels items sont disponibles (non lockes par d'autres)
    3. Experience accumulee biaisant les selections futures (stigmergie cognitive)

    [Rodriguez 2026: role-free agents; Heylighen 2016: any agent responds
     to any stimulus; Ricci et al. 2007: cognitive stigmergy]
    """

    async def perceive_and_decide(self, snapshot) -> Decision:
        # 1. Calculer les pressions depuis le snapshot
        pressures = compute_pressures(snapshot, self.tools.action_types())
        # 2. Selection probabiliste (Bonabeau et al. 1999)
        action_type = select_action(pressures, temperature=config.selection_temperature)
        # 3. Selectionner le work item le plus intense et non locke
        target = select_target(snapshot.items_eligible_for(action_type))
        return Decision(action_type, target, pressures)

    async def execute(self, decision) -> ActionResult:
        # Le LLM execute la logique domain-specific via l'outil
        tool = self.tools.get(decision.action_type)
        return await tool.execute(self.agent_id, decision.target, self.llm)

    def deposit(self, result, env) -> None:
        # Depot symetrique : tout agent ecrit dans tout marker (PFACO 2026)
        for marker_update in result.marker_updates:
            env.store.upsert(marker_update, agent_id=self.agent_id)
```

**Decision cle** : Le modele de pression selectionne le TYPE d'action, le LLM execute la logique metier. Cela garantit que la coordination reste stigmergique (environment-driven) et non conversationnelle (LLM-driven).

### Modele de Pression (Rodriguez, 2026)

```python
def compute_pressures(snapshot, action_types) -> dict[str, float]:
    """P_a = sum(intensity_i pour items eligibles a l'action a) / total_items

    [Rodriguez 2026, Eq. 3 : pression = signal de demande normalise]
    """

def select_action(pressures, temperature=0.1) -> str:
    """Selection softmax avec temperature.
    temp -> 0 : greedy. temp -> inf : aleatoire.
    [Bonabeau et al. 1999, Eq. 2.1 : suivi probabiliste de piste]
    """
```

### Execution Parallele (par tick)

```
1. Snapshot environnement (lecture partagee, Gelernter 1985)
2. Chaque agent percoit et decide (parallele, aucune ecriture)
3. Resolution de conflits (premier a acquerir le scope lock gagne)
4. Execution parallele (asyncio.gather / ThreadPoolExecutor)
5. Depot sequentiel (SQLite transactions)
6. Decay + maintenance (Parunak et al. 2005)
```

### Pattern Adaptateur (Separation Calcul/Coordination)

```python
class DomainAdapter(ABC):
    """Adaptateur de domaine — le calcul est specifique, la coordination est generique.
    [Carriero & Gelernter 1992: orthogonalite calcul/coordination]
    """
    def create_workspace(self, config) -> Workspace: ...
    def create_objective(self, user_input, config) -> Objective: ...
    def register_tools(self, registry: ToolRegistry) -> None: ...
    def define_state_machine(self) -> StateMachine: ...
    def evaluate_run(self, env) -> EvaluationResult: ...
```

**TravelPlanner** : 6 tools (search_flights, search_hotels, search_attractions, plan_day, validate, refine)
**CodeMigration** : 4 tools (discover, transform, test, validate) — LLM-driven, zero regex
**SWE-bench** : 5 tools (localize, patch, test, validate, refine)

### Baselines de Comparaison (Kapoor et al., 2024)

Pour chaque domaine, 4 configurations :
1. **Single Agent** : 1 agent, tous les outils, sequentiel
2. **Sequential Pipeline** : Pipeline fixe (style V0.1)
3. **Centralized Supervisor** : 1 LLM "manager" dispatche aux "workers"
4. **Stigmergic V2** : N agents homogenes, paralleles, pression-driven

Meme modele LLM, temperature, outils, prompts, workspace, >= 5 runs, CI95.

---

## Stack Technique

| Composant | Choix | Justification |
|---|---|---|
| **Langage** | Python 3.11+ | Ecosysteme LLM, pytest, asyncio |
| **LLM Client** | Port de `stigmergy/llm_client.py` (V0.1) | Provider-agnostic (OpenRouter/Z.ai), retry/budget eprouve |
| **Provider LLM** | OpenRouter (configurable) | Acces multi-modeles, pricing API integree |
| **Modele par defaut** | `qwen/qwen3-235b-a22b-2507` (configurable) | Performant, cout raisonnable |
| **Marker Store** | SQLite (WAL mode) | ACID, requetes SQL, lectures concurrentes, portable |
| **Audit Log** | JSONL append-only | Haut debit d'ecriture, human-readable, EU AI Act |
| **Parallelisme** | `asyncio` + `ThreadPoolExecutor` | asyncio pour I/O LLM, threads pour subprocess (pytest, git) |
| **Testing** | pytest + pytest-cov + pytest-asyncio | Standard, couverture, support async |
| **Config** | YAML | Human-readable, nesting complexe |
| **Container** | Docker + docker-compose | Reproductibilite benchmarks (Kapoor et al., 2024) |
| **Metrics** | pandas + matplotlib | Pareto, emergence plots |
| **Package manager** | uv | Rapide, reproductible, deja utilise en V0.1 |
| **Git** | GitPython | Workspace code migration |
| **Dependencies** | python-dotenv, pyyaml, aiosqlite | Minimum viable |

### Ce qu'on preserve de V0.1

| Composant | Fichier source V0.1 | Utilisation V2 |
|---|---|---|
| LLM client (retry, budget, providers) | `stigmergy/llm_client.py` | Port vers `llm/client.py` |
| Fonctions de decay | `environment/decay.py` | Port vers `core/decay.py` |
| Pattern guardrails (scope lock, TTL, budget) | `environment/guardrails.py` | Generalise dans `core/guardrails.py` |
| Pareto analysis | `metrics/pareto.py` | Port et generalise dans `metrics/pareto.py` |
| Docker infrastructure | `Dockerfile`, `docker-compose.yml` | Adapte pour V2 |

### Ce qu'on jette

- `agents/scout.py`, `transformer.py`, `tester.py`, `validator.py` — roles fixes
- `agents/capabilities/discover.py` (19 regex patterns) — hardcoded domain
- `environment/pheromone_store.py` — JSON + fcntl, 3 types hardcodes
- `stigmergy/loop.py` — round-robin sequentiel
- Tous les prompts Py2->3

---

## Structure du Projet

```
stigmergy-v2/
    core/                           # Framework generique (domain-agnostic)
        __init__.py
        agent.py                    # StigmergicAgent (homogene, role-free)
        environment.py              # Environment (MarkerStore + Workspace + Guardrails)
        marker_store.py             # SQLite-backed MarkerStore (WAL mode)
        marker.py                   # Marker dataclass + StateMachine
        orchestrator.py             # Tick loop avec execution parallele
        pressure.py                 # Calcul de pressions (Rodriguez 2026)
        decay.py                    # Fonctions de decay (Parunak et al. 2005)
        guardrails.py               # Deep norms engine (Grisold et al. 2025)
        audit.py                    # JSONL audit trail
        tool_registry.py            # Registre d'outils + Tool ABC
        config.py                   # Chargement et validation config YAML

    adapters/                       # Adaptateurs de domaine
        __init__.py
        base.py                     # DomainAdapter ABC, Workspace ABC
        travelplanner/
            __init__.py
            adapter.py              # TravelPlannerAdapter
            workspace.py            # Workspace base de donnees TravelPlanner
            tools.py                # 6 outils (search, plan, validate, refine)
            evaluator.py            # Metriques TravelPlanner
        codemigration/
            __init__.py
            adapter.py              # CodeMigrationAdapter
            workspace.py            # GitWorkspace
            tools.py                # 4 outils LLM-driven (discover, transform, test, validate)
            evaluator.py            # Metriques migration
        swebench/
            __init__.py
            adapter.py              # SWEBenchAdapter
            workspace.py            # SWEBenchWorkspace
            tools.py                # 5 outils (localize, patch, test, validate, refine)
            evaluator.py            # Metriques SWE-bench

    llm/                            # Infrastructure LLM
        __init__.py
        client.py                   # LLMClient (port de V0.1, provider-agnostic)
        prompts.py                  # Templates de prompts pour raisonnement agent

    metrics/                        # Mesure et evaluation
        __init__.py
        collector.py                # Collection par tick
        emergence.py                # Metriques d'emergence (entropie, specialisation)
        pareto.py                   # Analyse Pareto (port de V0.1)
        export.py                   # Export CSV/JSON/PNG

    baselines/                      # Baselines de comparaison
        __init__.py
        single_agent.py             # 1 agent, tous les outils
        sequential.py               # Pipeline fixe
        centralized.py              # Superviseur-workers

    tests/                          # Suite de tests
        unit/
            test_marker_store.py
            test_marker.py
            test_agent.py
            test_pressure.py
            test_decay.py
            test_guardrails.py
            test_audit.py
            test_orchestrator.py
            test_emergence.py
        integration/
            test_travelplanner.py
            test_codemigration.py
            test_swebench.py
            test_baselines.py
            test_full_run.py
        conftest.py
        fixtures/

    config/
        default.yaml                # Config framework par defaut
        travelplanner.yaml          # Overrides TravelPlanner
        codemigration.yaml          # Overrides code migration
        swebench.yaml               # Overrides SWE-bench

    documentation/                  # Documentation DSR par iteration
        construction_log.md
        iteration_1/                # TravelPlanner
        iteration_2/                # PolyMigration
        iteration_3/                # SWE-bench

    scripts/
        benchmark_all.sh            # Lancement benchmarks Docker

    main.py                         # CLI entrypoint
    CLAUDE.md
    requirements.txt
    pyproject.toml
    Dockerfile
    docker-compose.yml
    docker-compose.benchmark.yml
    Makefile
```

---

## Configuration par Defaut (`config/default.yaml`)

```yaml
# Framework stigmergique generaliste
framework:
  name: "stigmergy-v2"
  version: "2.0.0"

# Agents
agents:
  num_agents: 4                     # N agents homogenes
  num_agents_mode: "fixed"          # "fixed" | "proportional"
  files_per_agent: 6                # Pour mode proportional
  selection_temperature: 0.1        # Softmax temperature (0=greedy, >0=exploratoire)

# Markers (pheromones)
markers:
  decay_type: "exponential"         # "exponential" | "linear"
  decay_rate: 0.05                  # rho (Parunak et al. 2005)
  inhibition_decay_rate: 0.08       # k_gamma (Rodriguez 2026)
  inhibition_increment: 0.5         # gamma += 0.5 on retry
  inhibition_threshold: 0.1         # Agent attend si gamma >= seuil
  intensity_clamp: [0.1, 1.0]      # Min-max bornes

# Guardrails (deep norms — Grisold et al. 2025)
guardrails:
  max_retry_count: 3                # Apres 3 echecs -> skip
  scope_lock_ttl: 3                 # Ticks avant release zombie
  traceability: true                # Toute ecriture signee + timestampee
  audit_completeness: true          # Log JSONL obligatoire

# Orchestrateur
orchestrator:
  max_ticks: 50
  idle_cycles_to_stop: 2
  parallel: true                    # Execution parallele des agents

# LLM
llm:
  provider: "openrouter"
  model: "qwen/qwen3-235b-a22b-2507"
  temperature: 0.2
  max_tokens_total: 200000
  max_budget_usd: 5.0
  request_timeout_seconds: 300
  retry_attempts: 3
  min_429_backoff_seconds: 8.0

# Pressions (poids par type d'action — Rodriguez 2026)
pressures:
  default_weights: {}               # Poids egaux par defaut
  # Surchargeables par adaptateur :
  # discover: 1.0
  # transform: 1.2
  # test: 1.0
  # validate: 1.0
```

---

## Sprints Detailles

### Sprint 1 : Core — Markers, Store, Decay, Guardrails, Audit (5 jours)

**Objectif** : Construire la couche environnement generique. Aucun agent, aucun adaptateur — juste le moteur de pheromones.

**Fichiers a creer** :

| Fichier | Contenu | Lignes estimees |
|---|---|---|
| `core/__init__.py` | Exports | 5 |
| `core/marker.py` | `Marker` dataclass, `StateMachine` class, `MarkerType` enum | 120 |
| `core/marker_store.py` | `MarkerStore` : SQLite WAL, CRUD, locking, query, decay, snapshot | 350 |
| `core/decay.py` | `decay_intensity()`, `decay_inhibition()` (port V0.1) | 40 |
| `core/guardrails.py` | `GuardrailEngine` : budget, retry, scope lock TTL, traceability | 200 |
| `core/audit.py` | `AuditLog` : JSONL append, `AuditEvent` dataclass | 80 |
| `core/config.py` | `load_config()`, validation, merge defaults | 100 |
| `config/default.yaml` | Config par defaut (voir ci-dessus) | 50 |
| `tests/conftest.py` | Fixtures partagees (tmp_path, mock config) | 60 |
| `tests/unit/test_marker_store.py` | 12 tests : CRUD, lock, concurrent read, decay, query, snapshot | 300 |
| `tests/unit/test_marker.py` | 5 tests : creation, FSM transitions, validation | 100 |
| `tests/unit/test_guardrails.py` | 6 tests : budget, retry, scope lock, TTL, traceability check | 150 |
| `tests/unit/test_decay.py` | 4 tests : exponential, linear, inhibition, clamping | 80 |
| `tests/unit/test_audit.py` | 4 tests : append, read, completeness, before/after | 80 |

**Tests d'acceptance** : `pytest tests/unit/ -v` — 31 tests passent.

**Theorie tracee** :
- `MarkerStore` -> Gelernter (1985) tuple space + Ricci et al. (2007) artifacts
- `decay.py` -> Parunak et al. (2005) evaporation
- `guardrails.py` -> Grisold et al. (2025) deep norms
- `audit.py` -> EU AI Act Art. 14, Santoni de Sio & van den Hoven (2018)

---

### Sprint 2 : Core — Agent, Pression, Orchestrateur, Outils (5 jours)

**Objectif** : Construire l'agent generaliste, le calcul de pression, l'execution parallele, et le registre d'outils. Un mock adapter doit pouvoir tourner 10 ticks avec 4 agents.

**Fichiers a creer** :

| Fichier | Contenu | Lignes estimees |
|---|---|---|
| `core/agent.py` | `StigmergicAgent` : perceive, decide, execute, deposit | 200 |
| `core/pressure.py` | `compute_pressures()`, `select_action()` (softmax) | 80 |
| `core/tool_registry.py` | `Tool` ABC, `ToolRegistry`, `ActionResult`, `Decision` dataclasses | 120 |
| `core/environment.py` | `Environment` : combine MarkerStore + Workspace + Guardrails + Audit | 150 |
| `core/orchestrator.py` | `Orchestrator` : tick loop, parallel execution, conflict resolution, stop conditions | 250 |
| `adapters/__init__.py` | Exports | 5 |
| `adapters/base.py` | `DomainAdapter` ABC, `Workspace` ABC, `Objective` dataclass | 100 |
| `llm/__init__.py` | Exports | 5 |
| `llm/client.py` | Port de V0.1 `stigmergy/llm_client.py` | ~400 (port) |
| `llm/prompts.py` | Templates pour raisonnement agent, prompt systeme stigmergique | 80 |
| `tests/unit/test_agent.py` | 10 tests : perceive, decide, execute, deposit, idle, history | 250 |
| `tests/unit/test_pressure.py` | 6 tests : computation, normalisation, zero, stochastic, weights | 150 |
| `tests/unit/test_orchestrator.py` | 8 tests : parallel exec, conflict resolution, decay, stop conditions | 200 |

**Fichiers a creer (mock adapter pour tests)** :

| Fichier | Contenu |
|---|---|
| `tests/fixtures/mock_adapter.py` | Adaptateur mock avec 3 outils simples (increment/check/finalize) |

**Tests d'acceptance** :
1. `pytest tests/unit/ -v` — 55+ tests passent
2. Mock adapter tourne 10 ticks, 4 agents paralleles, 0 conflits non resolus
3. Metriques par tick collectees (agents actifs, pressions, actions)

**Theorie tracee** :
- `agent.py` -> Rodriguez (2026) role-free agents, Heylighen (2016) universal stimulus
- `pressure.py` -> Rodriguez (2026) Eq. 3, Bonabeau et al. (1999) Eq. 2.1
- `orchestrator.py` -> Serugendo et al. (2005) self-organization, Gelernter (1985) temporal decoupling
- `tool_registry.py` -> Carriero & Gelernter (1992) separation calcul/coordination

---

### Sprint 3 : Adaptateur TravelPlanner — Iteration DSR 1 (5 jours)

**Objectif** : Implementer l'adaptateur TravelPlanner. Valider OC1 (generaliste) et OC3 (battre SwarmAgentic 32.2%).

**Prerequis** : Telecharger les donnees TravelPlanner (bases de donnees vols/hotels/attractions + queries de validation).

**Fichiers a creer** :

| Fichier | Contenu |
|---|---|
| `adapters/travelplanner/__init__.py` | Exports |
| `adapters/travelplanner/adapter.py` | `TravelPlannerAdapter` : workspace, objective, tools, FSM, evaluation |
| `adapters/travelplanner/workspace.py` | `TravelPlannerWorkspace` : lecture des bases de donnees, items = queries |
| `adapters/travelplanner/tools.py` | 6 outils : `SearchFlightsTool`, `SearchHotelsTool`, `SearchAttractionsTool`, `PlanDayTool`, `ValidateConstraintsTool`, `RefinePlanTool` |
| `adapters/travelplanner/evaluator.py` | Metriques : final_score, hard_constraint_macro, soft_constraint, commonsense |
| `config/travelplanner.yaml` | Config specifique (poids de pression, noms d'actions) |
| `main.py` | CLI : `--adapter travelplanner --input <query_file>` |
| `tests/integration/test_travelplanner.py` | 10 tests (mock LLM + fixture queries) |

**Machine a etats TravelPlanner** :
```
pending -> searching -> planning -> validating -> terminal
                    \-> searching (recherche supplementaire)
          planning -> planning (raffinement)
          validating -> planning (echec contraintes -> re-planifier)
```

**Tests d'acceptance** :
1. `pytest tests/ -v` — 65+ tests
2. Dry run sur 5 queries TravelPlanner (mock LLM) — valide le pipeline
3. Run reel sur validation set — mesurer final_score, comparer a SwarmAgentic

**Livrable DSR Iteration 1** :
- Resultats quantitatifs TravelPlanner
- Metriques d'emergence (specialisation, collaboration)
- Lecons de conception documentees

---

### Sprint 4 : Metriques d'Emergence + Baselines (4 jours)

**Objectif** : Instrumenter les metriques d'emergence, construire les 3 baselines, generer les premieres analyses Pareto.

**Fichiers a creer** :

| Fichier | Contenu |
|---|---|
| `metrics/__init__.py` | Exports |
| `metrics/collector.py` | `TickCollector` : collecte par tick (actions, pressions, locks, items) |
| `metrics/emergence.py` | 8 metriques (voir tableau ci-dessous) |
| `metrics/pareto.py` | Port V0.1 + generalisation (N configurations, N domaines) |
| `metrics/export.py` | CSV par tick, JSON summary, PNG dashboard |
| `baselines/single_agent.py` | 1 agent, tous outils, pas de parallelisme |
| `baselines/sequential.py` | Pipeline fixe (action 1 -> action 2 -> ... -> action N) |
| `baselines/centralized.py` | LLM superviseur dispatche les taches aux workers |
| `tests/unit/test_emergence.py` | 8 tests (une par metrique) |
| `tests/integration/test_baselines.py` | 6 tests (2 par baseline) |

**Metriques d'emergence** :

| Metrique | Mesure | Reference |
|---|---|---|
| `specialization_entropy` | Entropie Shannon par agent, normalise [0,1] | Serugendo et al. (2005) |
| `colony_specialization` | Moyenne des entropies de tous les agents | Rodriguez (2026) |
| `collaboration_density` | % d'items touches par >1 agent | Heylighen (2016) |
| `action_switching_rate` | Nb moyen de changements d'action par agent | Bonabeau et al. (1999) |
| `convergence_tick` | Premier tick ou >= 80% items terminaux | Parunak et al. (2005) |
| `lock_contention_rate` | Echecs de lock / tentatives par tick | Ricci et al. (2007) |
| `parallel_utilization` | Agents actifs / total par tick | Rodriguez (2026) |
| `pressure_entropy` | Entropie Shannon de la distribution de pression | Serugendo et al. (2005) |

**Tests d'acceptance** :
1. `pytest tests/ -v` — 79+ tests
2. Pareto plot genere pour TravelPlanner : 4 configs x 5 runs
3. Dashboard emergence PNG genere

---

### Sprint 5 : Adaptateur Code Migration — Iteration DSR 2 (5 jours)

**Objectif** : Implementer l'adaptateur migration de code. Valider OC4 sur PolyMigration (ou docopt comme repo de reference).

**Fichiers a creer** :

| Fichier | Contenu |
|---|---|
| `adapters/codemigration/__init__.py` | Exports |
| `adapters/codemigration/adapter.py` | `CodeMigrationAdapter` : GitWorkspace, objective, tools, FSM |
| `adapters/codemigration/workspace.py` | `GitWorkspace` : clone, branch, list_files, read, write, commit, rollback |
| `adapters/codemigration/tools.py` | 4 outils **LLM-driven, zero regex** : `DiscoverTool` (LLM analyse le fichier et identifie les problemes), `TransformTool` (LLM transforme le code), `TestTool` (execute pytest/py_compile), `ValidateTool` (commit/revert base sur confiance) |
| `adapters/codemigration/evaluator.py` | Metriques : success_rate, rollback_rate, cost_per_file, escalation_rate |
| `config/codemigration.yaml` | Config specifique |
| `tests/integration/test_codemigration.py` | 10 tests |
| `tests/fixtures/synthetic_repo/` | Petit repo Python 2 synthetique pour tests |

**Difference cle avec V0.1** : Le `DiscoverTool` n'a AUCUN regex. Le LLM recoit le fichier + l'objectif et retourne une analyse structuree. C'est de la stigmergie cognitive (Ricci et al., 2007) : l'agent interprete l'artefact.

**Machine a etats Code Migration** :
```
pending -> active -> transformed -> tested -> validated -> terminal
active -> failed -> retry -> pending (avec inhibition)
tested -> escalated (needs human review)
```

**Tests d'acceptance** :
1. `pytest tests/ -v` — 89+ tests
2. Run sur `docopt/docopt@0.6.2` — success rate >= 85%
3. Comparaison V2 generaliste vs V0.1 specialise sur meme repo

**Livrable DSR Iteration 2** :
- Resultats code migration
- Comparaison avec V0.1 (precision, cout, emergence)
- Lecons de conception documentees

---

### Sprint 6 : Adaptateur SWE-bench — Iteration DSR 3 (5 jours)

**Objectif** : Implementer l'adaptateur SWE-bench. Valider OC4 etendu.

**Fichiers a creer** :

| Fichier | Contenu |
|---|---|
| `adapters/swebench/__init__.py` | Exports |
| `adapters/swebench/adapter.py` | `SWEBenchAdapter` |
| `adapters/swebench/workspace.py` | `SWEBenchWorkspace` : clone repo, appliquer issue context |
| `adapters/swebench/tools.py` | 5 outils : `LocalizeBugTool`, `GeneratePatchTool`, `RunTestSuiteTool`, `ValidatePatchTool`, `RefineLocalizationTool` |
| `adapters/swebench/evaluator.py` | Resolution rate, cost per issue |
| `config/swebench.yaml` | Config specifique |
| `tests/integration/test_swebench.py` | 8 tests |

**Tests d'acceptance** :
1. `pytest tests/ -v` — 97+ tests
2. Run sur SWE-bench Lite subset (10-20 issues)
3. Pareto cross-domaine : TravelPlanner + CodeMigration + SWE-bench

**Livrable DSR Iteration 3** :
- Resultats SWE-bench
- Analyse cross-domaine
- Extraction des principes de conception (format Gregor et al., 2020)

---

### Sprint 7 : Docker, Benchmarks Reproductibles, Gouvernance (4 jours)

**Objectif** : Benchmarks 100% Docker, analyse Pareto finale, validation OC5 (gouvernance).

**Fichiers a creer/modifier** :

| Fichier | Contenu |
|---|---|
| `Dockerfile` | Image de benchmark |
| `docker-compose.yml` | Environnement de dev |
| `docker-compose.benchmark.yml` | 4 configs x N runs en parallele |
| `scripts/benchmark_all.sh` | Lancement automatise |
| `Makefile` | Cibles : test, benchmark, export |
| `documentation/construction_log.md` | Log de construction complet |

**Metriques de gouvernance (OC5)** :

| Metrique | Cible | Reference |
|---|---|---|
| Audit completeness | >= 99.5% transitions loggees | EU AI Act Art. 14 |
| Decision traceability | 100% state transitions avec before/after | Grisold et al. (2025) |
| Budget compliance | 0 depassements | Deep norm |
| Human escalation | Tous items ambigus escalades | Grisold et al. (2025) |

**Livrable final** :
- Benchmarks reproductibles Docker
- Pareto plots pour these (3 domaines x 4 configs x 5 runs)
- Dashboard emergence
- Construction log complet
- Principes de conception DSR

---

## Resume des Sprints

| Sprint | Duree | Objectif | Tests cumules | DSR |
|---|---|---|---|---|
| Sprint 1 : Core Environment | 5 jours | Markers, Store, Decay, Guardrails, Audit | 31 | Foundation |
| Sprint 2 : Core Agents | 5 jours | Agent, Pression, Orchestrateur, Outils | 55 | Foundation |
| Sprint 3 : TravelPlanner | 5 jours | Adaptateur + validation generaliste | 65 | Iteration 1 (OC1, OC3) |
| Sprint 4 : Emergence + Baselines | 4 jours | Metriques, Pareto, 3 baselines | 79 | Evaluation |
| Sprint 5 : Code Migration | 5 jours | Adaptateur + validation PolyMigration | 89 | Iteration 2 (OC4) |
| Sprint 6 : SWE-bench | 5 jours | Adaptateur + validation SE | 97 | Iteration 3 (OC4) |
| Sprint 7 : Docker + Gouvernance | 4 jours | Benchmarks, audit, documentation | 97+ | OC5, Finalisation |

**Total : ~33 jours de dev** (7 sprints)

---

## Verification End-to-End

Pour chaque sprint :
1. `uv run pytest tests/ -v` — zero regression
2. Type checking : `mypy core/ adapters/` (optionnel mais recommande)

Pour chaque iteration DSR :
3. Run benchmark complet (5+ runs par configuration)
4. Pareto analysis generee
5. Emergence metrics analysees
6. Construction log mis a jour

Sprint 7 (final) :
7. `docker compose -f docker-compose.benchmark.yml up` — reproductible
8. Audit completeness >= 99.5%
9. Tous les principes de conception documentes (format Gregor et al., 2020)

---

## Premiere Etape d'Implementation

```bash
# Creer la branche V2 dans le repo actuel
git checkout -b v2/main

# Nettoyer : garder uniquement consigne/, documentation/, et les fichiers de config racine
# Le code V0.1 reste accessible via l'historique Git (branches codex/*)

# Commencer Sprint 1 : Core Environment
# -> core/marker.py, core/marker_store.py, core/decay.py, core/guardrails.py, core/audit.py
```

## Notes pour les Agents IA

Ce plan est concu pour etre execute par des agents IA (Claude Code). Chaque sprint :
1. Lire le sprint concerne dans ce document
2. Creer les fichiers listes avec les signatures de classes decrites
3. Implementer la logique en tracant chaque decision a la theorie indiquee
4. Ecrire les tests d'acceptance listes
5. Executer `uv run pytest tests/ -v` et corriger jusqu'a 100% pass
6. Mettre a jour `documentation/construction_log.md` avec les decisions et resultats
7. Commit avec convention : `feat(core): implement MarkerStore with SQLite WAL`
