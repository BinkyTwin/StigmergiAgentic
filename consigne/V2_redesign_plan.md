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
| **Repo** | Branche `codex/v2-redesign-sprint1` dans le repo actuel | Garde historique Git, PDFs, revue de litt |
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

## Non-goals

Les elements suivants sont explicitement exclus du perimetre du framework V2 :

1. **Le framework n'est pas un lanceur de benchmarks** : Les benchmarks sont un mecanisme de validation pour la these, pas l'objectif principal. Le framework fonctionne comme un systeme d'orchestration stigmergique generaliste.
2. **Les adaptateurs de domaine ne sont pas requis pour le fonctionnement de base** : Le framework doit etre utilisable sans adaptateur de domaine au-dela du mode assistant general.
3. **Pas de fine-tuning LLM** : Le framework utilise des API LLM standard via le `LLMClient` existant.
4. **Pas de streaming temps reel** : Toutes les interactions LLM sont en mode requete-reponse.
5. **Pas de multi-tenancy ni d'infrastructure de deploiement** : Le framework s'execute comme un processus local ou un conteneur Docker.
6. **Pas de GUI ni d'interface web** : L'interaction se fait via CLI (`main.py`) et API programmatique.
7. **Pas de communication directe agent-a-agent** : Les agents se coordonnent UNIQUEMENT via l'environnement de markers (stigmergie).
8. **Les resultats de benchmark ne sont pas des outils d'infrastructure** : Le harness d'evaluation, l'analyse Pareto, et les metriques d'emergence vivent dans `benchmarks/`, separes de la couche d'outils runtime.
9. **Pas de persistance cross-session** : Chaque execution de l'orchestrateur demarre de zero.
10. **Pas de marketplace de plugins ni de chargement dynamique d'outils** : Les outils sont enregistres programmatiquement via `ToolRegistry`.

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

### Vue d'ensemble (4 couches)

```
+-------------------------------------------------------------------+
|  COUCHE 4 : HARNESS DE BENCHMARK / EVALUATION                     |
|  benchmarks/harness.py  |  benchmarks/runners/  |                 |
|  benchmarks/analysis/                                              |
|  [Kapoor et al. 2024: reproductibilite; DSR: protocole evaluation] |
+-------------------------------------------------------------------+
|  COUCHE 3 : ADAPTATEURS DE DOMAINE (pluggable, optionnel)         |
|  adapters/travelplanner/ | adapters/codemigration/ |              |
|  adapters/swebench/      | adapters/assistant/                    |
|  [Carriero & Gelernter 1992: orthogonalite calcul/coordination]   |
+-------------------------------------------------------------------+
|  COUCHE 2 : OUTILS D'INFRASTRUCTURE (generiques, toujours dispo)  |
|  tools/file_read.py  |  tools/file_write.py  |  tools/bash_exec.py|
|  tools/web_search.py |  tools/think.py       |  tools/decompose.py|
|  [Ricci et al. 2007: primitives generiques de manipulation        |
|   d'artefacts]                                                     |
+-------------------------------------------------------------------+
|  COUCHE 1 : CORE FRAMEWORK (FAIT — Sprints 1+2)                   |
|  core/marker.py  |  core/marker_store.py  |  core/orchestrator.py |
|  core/agent.py   |  core/pressure.py      |  core/environment.py  |
|  core/guardrails.py  |  core/audit.py  |  core/tool_registry.py   |
|  [Rodriguez 2026; Heylighen 2016; Bonabeau et al. 1999]           |
+-------------------------------------------------------------------+
```

**Separation cle** : La Couche 2 (Outils d'Infrastructure) se place entre le core et les adaptateurs de domaine. Les adaptateurs de domaine enregistrent leurs propres outils specifiques ET peuvent aussi enregistrer les outils d'infrastructure. Le mode assistant general est simplement un adaptateur minimal qui n'enregistre que les outils d'infrastructure.

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

Chaque adaptateur enregistre ses outils de domaine ET peut appeler `register_infrastructure_tools(registry)` pour ajouter les outils generiques d'infrastructure.

### Pattern Outils d'Infrastructure (Couche 2)

Les outils d'infrastructure implementent le meme `Tool` ABC que les outils de domaine :

```python
# tools/__init__.py
def register_infrastructure_tools(registry: ToolRegistry, config: dict) -> None:
    """Enregistre tous les outils generiques d'infrastructure.

    [Ricci et al. 2007: primitives generiques de manipulation d'artefacts]
    """
    registry.register(FileReadTool(config=config))
    registry.register(FileWriteTool(config=config))
    registry.register(BashExecTool(config=config))
    registry.register(WebSearchTool(config=config))
    registry.register(ThinkTool(config=config))
    registry.register(DecomposeTool(config=config))
```

**Eligibilite** : Les outils d'infrastructure utilisent `marker.payload` pour determiner l'eligibilite. Par exemple, `FileReadTool.is_eligible(marker)` retourne `True` quand `marker.payload.get("eligible_actions")` inclut `"file_read"`.

**Execution** : Les outils d'infrastructure accedent a `environment.workspace` pour leurs operations.

**Decision architecturale** : Chaque adaptateur decide quels outils d'infrastructure inclure via `register_tools()`. C'est l'adaptateur qui constitue la frontiere de securite.

### Mode Assistant General

Le mode assistant general est un adaptateur minimal (`adapters/assistant/`) qui :
- `create_workspace` : retourne un `LocalWorkspace` pointe sur le repertoire de travail de l'utilisateur
- `create_objective` : convertit un prompt utilisateur en `Objective`
- `register_tools` : enregistre UNIQUEMENT les outils d'infrastructure
- `define_state_machine` : utilise le `StateMachine()` par defaut
- `initial_markers` : utilise le LLM pour decomposer l'objectif en sous-taches (markers)
- `evaluate_run` : retourne des metriques basiques de completion (pas de scoring benchmark)

Cela prouve que le framework fonctionne comme un systeme d'orchestration generaliste, independamment de tout benchmark.

### Baselines de Comparaison (Kapoor et al., 2024)

Pour chaque domaine, 4 configurations :
1. **Single Agent** : 1 agent, tous les outils, sequentiel
2. **Sequential Pipeline** : Pipeline fixe (style V0.1)
3. **Centralized Supervisor** : 1 LLM "manager" dispatche aux "workers"
4. **Stigmergic V2** : N agents homogenes, paralleles, pression-driven

Meme modele LLM, temperature, outils, prompts, workspace, >= 5 runs, CI95.

Les baselines vivent dans `benchmarks/runners/` et sont alignees sur les contrats V2.

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
| Pareto analysis | `metrics/pareto.py` | Port et generalise dans `benchmarks/analysis/pareto.py` |
| Docker infrastructure | `Dockerfile`, `docker-compose.yml` | Adapte pour V2 |

### Ce qu'on jette

- `agents/scout.py`, `transformer.py`, `tester.py`, `validator.py` — roles fixes
- `agents/capabilities/discover.py` (19 regex patterns) — hardcoded domain
- `environment/pheromone_store.py` — JSON + fcntl, 3 types hardcodes
- `stigmergy/loop.py` — round-robin sequentiel
- Tous les prompts Py2->3
- `baselines/` (V0.1) — non aligne avec les contrats V2
- `metrics/` (V0.1) — non cable sur V2

---

## Structure du Projet

```
stigmergy-v2/
    core/                           # L1: Framework generique (domain-agnostic)
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

    tools/                          # L2: Outils d'infrastructure generiques
        __init__.py                 # register_infrastructure_tools() helper
        file_read.py                # FileReadTool : lecture de fichier
        file_write.py               # FileWriteTool : ecriture/patch de fichier
        bash_exec.py                # BashExecTool : execution commande, stdout/stderr, timeout
        web_search.py               # WebSearchTool : recherche web via API
        think.py                    # ThinkTool : raisonnement/planification LLM
        decompose.py                # DecomposeTool : decomposition tache en sous-markers

    adapters/                       # L3: Adaptateurs de domaine
        __init__.py
        base.py                     # DomainAdapter ABC, Workspace ABC, Objective dataclass
        assistant/                  # Mode assistant general (outils infra uniquement)
            __init__.py
            adapter.py              # AssistantAdapter
            workspace.py            # LocalWorkspace (filesystem-rooted)
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

    benchmarks/                     # L4: Harness de benchmark / evaluation
        __init__.py
        harness.py                  # BenchmarkHarness : run N configs x M runs
        runners/
            __init__.py
            single_agent.py         # 1 agent, tous outils, pas de parallelisme
            sequential.py           # Pipeline fixe
            centralized.py          # Superviseur-workers
            stigmergic.py           # Runner stigmergique V2
        analysis/
            __init__.py
            emergence.py            # Metriques d'emergence (entropie, specialisation)
            pareto.py               # Analyse Pareto (port + generalisation)
            export.py               # CSV/JSON/PNG export

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
            test_llm_client.py
            test_file_tools.py
            test_bash_tool.py
            test_assistant_adapter.py
            test_emergence.py
        integration/
            test_assistant_run.py
            test_travelplanner.py
            test_codemigration.py
            test_swebench.py
            test_baselines.py
            test_full_run.py
        conftest.py
        fixtures/

    config/
        default.yaml                # Config framework par defaut
        assistant.yaml              # Overrides mode assistant
        travelplanner.yaml          # Overrides TravelPlanner
        codemigration.yaml          # Overrides code migration
        swebench.yaml               # Overrides SWE-bench

    documentation/                  # Documentation DSR par iteration
        construction_log.md
        decisions/                  # ADRs
        redesign_v2/                # Artifacts par sprint
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

# Outils d'infrastructure (Couche 2)
tools:
  sandbox_root: "."                 # Racine du workspace (securite)
  allowed_commands:                 # Commandes bash autorisees (whitelist)
    - "python"
    - "pytest"
    - "git"
    - "pip"
    - "uv"
  bash_timeout_seconds: 120         # Timeout execution bash
  max_file_size_bytes: 1048576      # 1 MB max par fichier lu/ecrit
  web_search_provider: "none"       # "none" | "tavily" | "serper" (configurable)
  web_search_max_results: 5         # Resultats max par recherche
```

---

## Sprints Detailles

### Sprint 1 : Core — Markers, Store, Decay, Guardrails, Audit — DONE

**Statut** : FAIT. Voir `documentation/redesign_v2/sprint_01_artifact.md`.

**Resume** : Couche environnement generique construite. MarkerStore SQLite WAL, machine a etats configurable, decay exponentiel/lineaire, guardrails (budget, retry, scope lock TTL, tracabilite), audit JSONL append-only.

**Modules** : `core/marker.py`, `core/marker_store.py`, `core/decay.py`, `core/guardrails.py`, `core/audit.py`, `core/config.py`, `config/default.yaml`

**Tests** : 31 tests unitaires passes.

---

### Sprint 2 : Core — Agent, Pression, Orchestrateur, Outils — DONE

**Statut** : FAIT. Voir `documentation/redesign_v2/sprint_02_artifact.md`.

**Resume** : Agent generaliste, calcul de pression, execution parallele, registre d'outils, LLM client. Mock adapter tourne 10 ticks avec 4 agents.

**Modules** : `core/tool_registry.py`, `core/pressure.py`, `core/environment.py`, `core/agent.py`, `core/orchestrator.py`, `adapters/base.py`, `llm/client.py`, `llm/prompts.py`

**Tests** : 61 tests unitaires passes (cumul).

**Theorie tracee** :
- `agent.py` -> Rodriguez (2026) role-free agents, Heylighen (2016) universal stimulus
- `pressure.py` -> Rodriguez (2026) Eq. 3, Bonabeau et al. (1999) Eq. 2.1
- `orchestrator.py` -> Serugendo et al. (2005) self-organization, Gelernter (1985) temporal decoupling
- `tool_registry.py` -> Carriero & Gelernter (1992) separation calcul/coordination

---

### Sprint 3 : Outils d'Infrastructure + Mode Assistant General (5 jours)

**Objectif** : Construire la couche d'outils generiques et un adaptateur assistant minimal. Apres ce sprint, le framework peut fonctionner comme un assistant multi-agents generaliste avec lecture/ecriture de fichiers, execution bash, et recherche web.

**Fichiers a creer** :

| Fichier | Contenu |
|---|---|
| `tools/__init__.py` | `register_infrastructure_tools()` helper |
| `tools/file_read.py` | `FileReadTool` : lecture de contenu fichier, retour dans marker payload |
| `tools/file_write.py` | `FileWriteTool` : ecriture/patch fichier, retour marker mis a jour |
| `tools/bash_exec.py` | `BashExecTool` : execution commande, capture stdout/stderr, timeout |
| `tools/web_search.py` | `WebSearchTool` : recherche web via API, retour resultats dans payload |
| `tools/think.py` | `ThinkTool` : raisonnement/planification LLM, retourne une analyse |
| `tools/decompose.py` | `DecomposeTool` : decompose une tache en sous-markers via LLM |
| `adapters/assistant/__init__.py` | Exports |
| `adapters/assistant/adapter.py` | `AssistantAdapter` : adaptateur minimal utilisant uniquement les outils d'infrastructure |
| `adapters/assistant/workspace.py` | `LocalWorkspace` : workspace enracine dans le filesystem |
| `config/assistant.yaml` | Overrides de config pour le mode assistant |
| `main.py` | CLI entrypoint : `--adapter assistant --objective "..."` |
| `tests/unit/test_file_tools.py` | 8 tests : lecture, ecriture, patch, permissions, limites |
| `tests/unit/test_bash_tool.py` | 6 tests : execution, timeout, whitelist, stderr |
| `tests/unit/test_assistant_adapter.py` | 6 tests : workspace, objective, markers initiaux |
| `tests/integration/test_assistant_run.py` | 4 tests : run end-to-end avec mock LLM |

**Tests d'acceptance** :
1. `pytest tests/unit/ -v` — 81+ tests passent
2. L'adaptateur assistant cree des markers a partir d'un objectif utilisateur
3. Les outils d'infrastructure s'executent dans la boucle de ticks complete
4. Run end-to-end de l'assistant avec mock LLM

**Theorie tracee** :
- Outils d'infrastructure -> Ricci et al. (2007) : primitives generiques de manipulation d'artefacts
- Adaptateur assistant -> Carriero & Gelernter (1992) : orthogonalite entre calcul generique et coordination stigmergique
- Decomposition de taches -> Heylighen (2016) : decomposition stigmergique de taches complexes

---

### Sprint 4 : Adaptateur TravelPlanner — Iteration DSR 1 (5 jours)

**Objectif** : Implementer l'adaptateur TravelPlanner en utilisant les outils d'infrastructure comme fondation. Valider OC1 (generaliste) et OC3 (battre SwarmAgentic 32.2%).

> **Note** : TravelPlanner est un benchmark de validation DSR, pas une dependance runtime. Le framework fonctionne deja sans lui grace au mode assistant general (Sprint 3).

**Prerequis** : Telecharger les donnees TravelPlanner (bases de donnees vols/hotels/attractions + queries de validation).

**Fichiers a creer** :

| Fichier | Contenu |
|---|---|
| `adapters/travelplanner/__init__.py` | Exports |
| `adapters/travelplanner/adapter.py` | `TravelPlannerAdapter` : workspace, objective, tools, FSM, evaluation. Appelle `register_infrastructure_tools()` en plus de ses outils de domaine. |
| `adapters/travelplanner/workspace.py` | `TravelPlannerWorkspace` : lecture des bases de donnees, items = queries |
| `adapters/travelplanner/tools.py` | 6 outils : `SearchFlightsTool`, `SearchHotelsTool`, `SearchAttractionsTool`, `PlanDayTool`, `ValidateConstraintsTool`, `RefinePlanTool` |
| `adapters/travelplanner/evaluator.py` | Metriques : final_score, hard_constraint_macro, soft_constraint, commonsense |
| `config/travelplanner.yaml` | Config specifique (poids de pression, noms d'actions) |
| `tests/integration/test_travelplanner.py` | 10 tests (mock LLM + fixture queries) |

**Machine a etats TravelPlanner** :
```
pending -> searching -> planning -> validating -> terminal
                    \-> searching (recherche supplementaire)
          planning -> planning (raffinement)
          validating -> planning (echec contraintes -> re-planifier)
```

**Tests d'acceptance** :
1. `pytest tests/ -v` — 91+ tests
2. Dry run sur 5 queries TravelPlanner (mock LLM) — valide le pipeline
3. Run reel sur validation set — mesurer final_score, comparer a SwarmAgentic

**Livrable DSR Iteration 1** :
- Resultats quantitatifs TravelPlanner
- Metriques d'emergence (specialisation, collaboration)
- Lecons de conception documentees

---

### Sprint 5 : Metriques d'Emergence + Baselines + Harness de Benchmark (4 jours)

**Objectif** : Construire l'infrastructure d'evaluation : metriques d'emergence, baselines alignees V2, analyse Pareto, et le harness de benchmark. Tout vit dans `benchmarks/`, separe du runtime.

**Fichiers a creer** :

| Fichier | Contenu |
|---|---|
| `benchmarks/__init__.py` | Exports |
| `benchmarks/harness.py` | `BenchmarkHarness` : orchestration N configs x M runs, collecte resultats |
| `benchmarks/runners/__init__.py` | Exports |
| `benchmarks/runners/single_agent.py` | 1 agent, tous outils, pas de parallelisme (aligne V2) |
| `benchmarks/runners/sequential.py` | Pipeline fixe (aligne V2) |
| `benchmarks/runners/centralized.py` | LLM superviseur dispatche les taches aux workers (aligne V2) |
| `benchmarks/runners/stigmergic.py` | Runner stigmergique V2 standard |
| `benchmarks/analysis/__init__.py` | Exports |
| `benchmarks/analysis/emergence.py` | 8 metriques (voir tableau ci-dessous) |
| `benchmarks/analysis/pareto.py` | Port V0.1 + generalisation (N configurations, N domaines) |
| `benchmarks/analysis/export.py` | CSV par tick, JSON summary, PNG dashboard |
| `tests/unit/test_emergence.py` | 8 tests (une par metrique) |
| `tests/integration/test_baselines.py` | 6 tests (2 par baseline runner) |

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
1. `pytest tests/ -v` — 105+ tests
2. Pareto plot genere pour TravelPlanner : 4 configs x 5 runs
3. Dashboard emergence PNG genere

---

### Sprint 6 : Adaptateur Code Migration — Iteration DSR 2 (5 jours)

**Objectif** : Implementer l'adaptateur migration de code. Valider OC4 sur PolyMigration (ou docopt comme repo de reference).

**Fichiers a creer** :

| Fichier | Contenu |
|---|---|
| `adapters/codemigration/__init__.py` | Exports |
| `adapters/codemigration/adapter.py` | `CodeMigrationAdapter` : GitWorkspace, objective, tools, FSM. Appelle `register_infrastructure_tools()`. |
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
1. `pytest tests/ -v` — 115+ tests
2. Run sur `docopt/docopt@0.6.2` — success rate >= 85%
3. Comparaison V2 generaliste vs V0.1 specialise sur meme repo

**Livrable DSR Iteration 2** :
- Resultats code migration
- Comparaison avec V0.1 (precision, cout, emergence)
- Lecons de conception documentees

---

### Sprint 7 : SWE-bench + Docker + Gouvernance — Iteration DSR 3 (5 jours)

**Objectif** : Implementer l'adaptateur SWE-bench, benchmarks 100% Docker, analyse Pareto finale, validation OC5 (gouvernance).

**Fichiers a creer/modifier** :

| Fichier | Contenu |
|---|---|
| `adapters/swebench/__init__.py` | Exports |
| `adapters/swebench/adapter.py` | `SWEBenchAdapter`. Appelle `register_infrastructure_tools()`. |
| `adapters/swebench/workspace.py` | `SWEBenchWorkspace` : clone repo, appliquer issue context |
| `adapters/swebench/tools.py` | 5 outils : `LocalizeBugTool`, `GeneratePatchTool`, `RunTestSuiteTool`, `ValidatePatchTool`, `RefineLocalizationTool` |
| `adapters/swebench/evaluator.py` | Resolution rate, cost per issue |
| `config/swebench.yaml` | Config specifique |
| `Dockerfile` | Image de benchmark |
| `docker-compose.yml` | Environnement de dev |
| `docker-compose.benchmark.yml` | 4 configs x N runs en parallele |
| `scripts/benchmark_all.sh` | Lancement automatise |
| `Makefile` | Cibles : test, benchmark, export |
| `tests/integration/test_swebench.py` | 8 tests |
| `documentation/construction_log.md` | Log de construction complet |

**Metriques de gouvernance (OC5)** :

| Metrique | Cible | Reference |
|---|---|---|
| Audit completeness | >= 99.5% transitions loggees | EU AI Act Art. 14 |
| Decision traceability | 100% state transitions avec before/after | Grisold et al. (2025) |
| Budget compliance | 0 depassements | Deep norm |
| Human escalation | Tous items ambigus escalades | Grisold et al. (2025) |

**Tests d'acceptance** :
1. `pytest tests/ -v` — 123+ tests
2. Run sur SWE-bench Lite subset (10-20 issues)
3. Pareto cross-domaine : TravelPlanner + CodeMigration + SWE-bench
4. Audit completeness >= 99.5%
5. `docker compose -f docker-compose.benchmark.yml up` — reproductible

**Livrables DSR Iteration 3 + Final** :
- Resultats SWE-bench
- Analyse cross-domaine
- Extraction des principes de conception (format Gregor et al., 2020)
- Benchmarks reproductibles Docker
- Pareto plots pour these (3 domaines x 4 configs x 5 runs)
- Dashboard emergence
- Construction log complet

---

## Resume des Sprints

| Sprint | Duree | Objectif | Tests cumules | Couche | DSR |
|---|---|---|---|---|---|
| Sprint 1 : Core Environment | FAIT | Markers, Store, Decay, Guardrails, Audit | 31 | L1 | Foundation |
| Sprint 2 : Core Agents | FAIT | Agent, Pression, Orchestrateur, Outils, LLM | 61 | L1 | Foundation |
| Sprint 3 : Infrastructure Tools | 5 jours | Outils generiques + Mode Assistant General | 81+ | L2 + L3 | Enablement |
| Sprint 4 : TravelPlanner | 5 jours | Premier adaptateur de domaine + validation | 91+ | L3 | Iteration 1 (OC1, OC3) |
| Sprint 5 : Metrics + Baselines | 4 jours | Emergence, Pareto, harness de benchmark | 105+ | L4 | Evaluation |
| Sprint 6 : Code Migration | 5 jours | Deuxieme adaptateur de domaine + PolyMigration | 115+ | L3 | Iteration 2 (OC4) |
| Sprint 7 : SWE-bench + Docker + Gouvernance | 5 jours | Troisieme adaptateur, reproductibilite, OC5 | 123+ | L3 + L4 | Iteration 3 (OC4, OC5) |

**Total restant : ~24 jours de dev** (5 sprints)

---

## Verification End-to-End

Pour chaque sprint :
1. `uv run pytest tests/ -v` — zero regression
2. Type checking : `mypy core/ adapters/ tools/` (optionnel mais recommande)

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

## Notes pour les Agents IA

Ce plan est concu pour etre execute par des agents IA (Claude Code). Chaque sprint :
1. Lire le sprint concerne dans ce document
2. Creer les fichiers listes avec les signatures de classes decrites
3. Implementer la logique en tracant chaque decision a la theorie indiquee
4. Ecrire les tests d'acceptance listes
5. Executer `uv run pytest tests/ -v` et corriger jusqu'a 100% pass
6. Mettre a jour `documentation/construction_log.md` avec les decisions et resultats
7. Commit avec convention : `feat(core): implement MarkerStore with SQLite WAL`

### Decisions architecturales cles (pour implementation)

**ADR-001 : Outils d'infrastructure comme implementations du Tool ABC**
- Decision : Les outils generiques (file I/O, bash, web search) implementent le meme `Tool` ABC que les outils de domaine
- Raison : Selection uniforme par pression ; pas de traitement special dans l'orchestrateur
- Compromis : Les outils d'infrastructure doivent encoder l'eligibilite via `marker.payload`

**ADR-002 : Mode assistant general comme DomainAdapter minimal**
- Decision : Le mode assistant est une sous-classe de `DomainAdapter`, pas un chemin de code separe
- Raison : Respecte le contrat ABC existant ; l'orchestrateur n'a pas besoin de savoir s'il execute un benchmark ou une session assistant
- Compromis : Necessite une decomposition de taches par LLM dans `initial_markers()`

**ADR-003 : Harness de benchmark separe des adaptateurs**
- Decision : `benchmarks/` possede le protocole d'experimentation ; `adapters/` possede uniquement la logique de domaine
- Raison : Le `evaluate_run()` de l'adaptateur fournit le scoring de domaine ; le harness possede l'orchestration N-config x M-run

**ADR-004 : Outils d'infrastructure enregistres par les adaptateurs, pas globalement**
- Decision : Le `register_tools()` de chaque adaptateur decide quels outils d'infrastructure inclure
- Raison : Certains adaptateurs peuvent restreindre l'acces aux outils pour la securite ; l'adaptateur est la frontiere de securite
- Compromis : Leger boilerplate attenue par le helper `register_infrastructure_tools()`
