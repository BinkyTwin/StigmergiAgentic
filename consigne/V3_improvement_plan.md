# Plan V3 : Framework Stigmergique -- Refonte du Runtime et Preuves d'Emergence

## Diagnostic V2 : Pourquoi les resultats sont decevants

### Symptomes observes (4 tests notebook)

| Test | Objectif | Resultat | Probleme |
|------|----------|----------|----------|
| **Londres** | "aller a Londres" | 8 sous-taches, web search OK, contenu correct | 65 markers pour une question simple, 47% terminal, `idle_cycles` |
| **Analyse repo** | "analyse ce repo" | `git clone <repository_url>` -- hallucination | Agents n'ont AUCUN contexte workspace. Marker explosion (72), hallucinations |
| **Snake game** | "code un jeu snake" | Description sans aucun code ecrit | 4 ticks, idle immediatement. Markers du run precedent persistent (73 -> DB pas nettoyee) |
| **Iran** | "rapport sur l'Iran" | Contenu structure, web search fonctionne | Meilleur resultat mais 92 markers, 47% terminal, `max_ticks` |

### Causes racines identifiees

#### CR-1 : Agents deconnectes du workspace (critique)
Les agents ne savent pas ou ils sont ni quels fichiers existent. Le `ThinkTool` raisonne dans le vide. Le `BashExecTool` recoit des commandes generiques hallucinantes (`git clone <repository_url>`). Aucun fichier du workspace n'est injecte dans le contexte LLM.

**Impact** : Tests 2 et 3 sont des echecs complets.

#### CR-2 : Decomposition en cascade non bornee (critique)
Le `DecomposeTool` cree des sous-markers qui a leur tour declenchent `decompose` ou `think`, generant des dizaines de markers non actionnables. Un objectif simple genere 65-92 markers.

**Impact** : Explosion combinatoire, budget dilue, agents idle faute de markers actionnables.

#### CR-3 : Pas de vraie parallelite LLM (bloquant)
`LLMClient.call()` est synchrone (`time.sleep`, `client.chat.completions.create` bloquant). `subprocess.run()` dans `BashExecTool` bloque l'event loop. `asyncio.gather()` dans l'orchestrateur ne produit aucun parallelisme reel.

**Impact** : 2 agents = 2x le temps, pas 2x le debit. La "parallelite" est un mensonge architecturel.

#### CR-4 : Pas de reinforcement positif (fondamental)
`core/decay.py` n'implemente que l'evaporation. Il n'y a aucun mecanisme de depot de pheromone supplementaire quand un agent reussit. La boucle de retroaction positive -- coeur de la stigmergie biologique -- est absente.

**Impact** : Les markers perdent en intensite monotoniquement. Aucune amplification des chemins productifs. Contraire a Bonabeau et al. (1999) et Rodriguez (2026).

#### CR-5 : Pas de dependances inter-markers (structurel)
Aucun moyen d'exprimer "marker B depend de A". Les agents attaquent n'importe quelle tache dans n'importe quel ordre. Le `DecomposeTool` cree des sous-taches independantes sans topologie.

**Impact** : Les agents executent "rediger le rapport" avant "collecter les donnees". Desordre structurel.

#### CR-6 : Prompts et output LLM fragiles (technique)
`llm/prompts.py` demande du "strict JSON" dans le prompt sans utiliser les fonctionnalites natives de structured output. Le parsing echoue silencieusement et l'agent continue avec des donnees corrompues.

**Impact** : Outils non invoquables, hints non extraits, actions perdues.

#### CR-7 : Memoire agent inexistante (emergent)
Les agents n'ont aucune memoire entre les ticks. Chaque decision est 100% reactive au snapshot courant. Un agent peut re-selectionner le meme marker qu'il vient d'echouer.

**Impact** : Pas de stigmergie cognitive (Ricci et al., 2007). Pas d'apprentissage, pas de specialisation emergente.

#### CR-8 : DB partagee entre runs (operationnel)
Le `MarkerStore` SQLite persiste les markers du run precedent. Le test 3 herite de 73 markers du test 2.

**Impact** : Corruption inter-sessions, metriques faussees.

#### CR-9 : Metrics d'emergence absentes (scientifique)
Aucune instrumentation pour mesurer la specialisation (entropie Shannon), la collaboration (markers touches par >1 agent), ou l'efficacite parallele. Impossible de prouver OC2.

---

## Principes de conception V3

### P1 : Contexte d'abord, action ensuite
Avant toute action, l'agent recoit une vue structuree du workspace (arborescence, fichiers cles, README). Le raisonnement est ancre dans la realite, pas dans l'hallucination.

**Source theorique** : Ricci et al. (2007) -- stigmergie cognitive via artefacts instrumentables.

### P2 : Reinforcement symetrique
Le depot de pheromone ne peut pas etre unidirectionnel (evaporation seulement). Chaque execution reussie augmente l'intensite des markers associes. Chaque echec augmente l'inhibition ET propage l'information negative aux dependances.

**Source theorique** : Bonabeau et al. (1999) Eq. 2.1 ; ACO-ToT (Chari et al., 2025) ; Pheromind `repeatedSignalBoost`.

### P3 : Graphe de dependances explicite
Les markers forment un DAG (Directed Acyclic Graph). Un marker ne devient eligible que lorsque tous ses predecesseurs sont terminaux. La decomposition produit un graphe, pas une liste plate.

**Source theorique** : Carriero & Gelernter (1992) ; Prefect v3 data-flow dependencies.

### P4 : Parallelite reelle
Le client LLM est nativement asynchrone. Les appels LLM concurrents sont proteges par un semaphore configurable. Les outils qui executent des subprocess utilisent `asyncio.create_subprocess_exec`.

**Source theorique** : Serugendo et al. (2005) -- auto-organisation par parallelisme reel.

### P5 : Structured output, pas de parsing artisanal
L'interface LLM utilise `response_format={"type": "json_object"}` ou le mode tool-use natif du provider. Les schemas d'output sont derives de Pydantic models. Le parsing ne peut pas echouer.

**Source technique** : OpenAI Structured Outputs (2024) ; Anthropic Tool Use API (2024).

### P6 : Decomposition bornee avec profondeur maximale
La decomposition est limitee a une profondeur configurable (defaut: 2). La redecomposition est interdite sauf escalation explicite. Le nombre de sous-markers par decomposition est borne.

### P7 : Evaporation differentielle par categorie
Les markers de type `dependency` s'evaporent tres lentement. Les markers `anticipatory` s'evaporent tres vite. Les `task` et `progress` suivent le taux standard.

**Source theorique** : Parunak et al. (2005) ; Pheromind `evaporationRates` par categorie.

### P8 : Metriques d'emergence natives
Chaque tick produit les donnees necessaires pour calculer l'entropie de specialisation, la densite de collaboration, le taux de contention de locks, et l'utilisation parallele. Ces metriques sont calculees en temps reel.

**Source theorique** : Rodriguez (2026) ; Serugendo et al. (2005).

### P9 : Isolation des sessions
Chaque run de l'orchestrateur opere sur une base SQLite ephemere (ou prefixee par session). Aucune pollution inter-runs.

---

## Architecture V3 : Vue d'ensemble

```
+-------------------------------------------------------------------+
|  COUCHE 5 : HARNESS DE BENCHMARK / EVALUATION                     |
|  benchmarks/harness.py | benchmarks/runners/ |                     |
|  benchmarks/analysis/                                              |
|  [Kapoor et al. 2024; DSR: protocole evaluation]                   |
+-------------------------------------------------------------------+
|  COUCHE 4 : ADAPTATEURS DE DOMAINE (pluggable, optionnel)          |
|  adapters/travelplanner/ | adapters/codemigration/ |               |
|  adapters/swebench/      | adapters/assistant/                     |
|  [Carriero & Gelernter 1992: orthogonalite calcul/coordination]    |
+-------------------------------------------------------------------+
|  COUCHE 3 : OUTILS D'INFRASTRUCTURE (generiques)                   |
|  tools/file_read  | tools/file_write  | tools/bash_exec            |
|  tools/web_search | tools/think       | tools/decompose             |
|  [Ricci et al. 2007: primitives d'artefacts]                       |
+-------------------------------------------------------------------+
|  COUCHE 2 : AGENT RUNTIME (V3 -- ameliorations majeures)           |
|  core/agent.py  (+ memoire cognitive)                              |
|  core/pressure.py (+ pression ACO alpha/beta)                      |
|  core/reinforcement.py (NOUVEAU -- depot positif)                  |
|  core/dependency.py (NOUVEAU -- DAG de markers)                    |
|  core/schemas.py (NOUVEAU -- Pydantic schemas)                     |
|  core/emergence.py (NOUVEAU -- metriques en temps reel)            |
|  [Rodriguez 2026; ACO-ToT; Bonabeau et al. 1999]                   |
+-------------------------------------------------------------------+
|  COUCHE 1 : CORE ENVIRONMENT (V2 -- ameliorations ciblees)         |
|  core/marker.py (+ depends_on, + category decay)                   |
|  core/marker_store.py (+ session isolation, + pruning)             |
|  core/decay.py (+ evaporation differentielle par categorie)        |
|  core/guardrails.py  | core/audit.py  | core/config.py             |
|  core/environment.py (+ apply_reinforcement)                       |
|  [Heylighen 2016; Parunak et al. 2005; Grisold et al. 2025]       |
+-------------------------------------------------------------------+
|  COUCHE 0 : INFRASTRUCTURE LLM (V3 -- refonte async)               |
|  llm/client.py (AsyncOpenAI + semaphore + structured output)       |
|  llm/prompts.py (contexte workspace + Pydantic schemas)            |
|  [OpenAI Structured Outputs; Anthropic Tool Use]                   |
+-------------------------------------------------------------------+
```

---

## Nouveaux fichiers V3

| Fichier | Contenu | Sprint |
|---------|---------|--------|
| `core/reinforcement.py` | Reinforcement positif + propagation arriere dans le DAG | Sprint 4 |
| `core/dependency.py` | Validation DAG (Kahn), resolution de dependances, topological sort | Sprint 4 |
| `core/schemas.py` | Pydantic models pour tous les outputs LLM (ToolDecision, DecomposeOutput, ThinkOutput) | Sprint 4 |
| `core/emergence.py` | 8 metriques d'emergence en temps reel (entropie, specialisation, collaboration, etc.) | Sprint 5 |
| `tests/unit/test_reinforcement.py` | Tests du module de reinforcement | Sprint 4 |
| `tests/unit/test_dependency.py` | Tests DAG, cycles, resolution | Sprint 4 |
| `tests/unit/test_schemas.py` | Tests validation Pydantic | Sprint 4 |
| `tests/unit/test_emergence.py` | Tests metriques d'emergence | Sprint 5 |

---

## Fichiers modifies V3

| Fichier | Modification | Sprint |
|---------|--------------|--------|
| `llm/client.py` | Refonte : `AsyncOpenAI` + `acall()` + semaphore + `response_format` + streaming-aware budget | Sprint 4 |
| `llm/prompts.py` | Injection contexte workspace + Pydantic schemas + few-shot examples | Sprint 4 |
| `core/marker.py` | Ajout `depends_on: list[str]` dans payload convention + methode `is_dependency_satisfied()` | Sprint 4 |
| `core/marker_store.py` | Session ID prefix + pruning threshold + `query_markers` via SQL WHERE (plus de filtre Python) | Sprint 4 |
| `core/decay.py` | Evaporation differentielle par `marker_type` via config `decay_rates_by_type` | Sprint 4 |
| `core/pressure.py` | Formule ACO : `(intensity^alpha * heuristic^beta)` au lieu de simple somme | Sprint 5 |
| `core/agent.py` | Memoire cognitive (`AgentMemory`) + injection dans prompts + filtre dependances | Sprint 5 |
| `core/environment.py` | `apply_reinforcement()` + integration decay differentiel + pruning apres decay | Sprint 4 |
| `core/orchestrator.py` | Metriques d'emergence par tick + session isolation + async execution reelle | Sprint 4 |
| `tools/think.py` | Injection contexte workspace + utilisation schemas Pydantic | Sprint 4 |
| `tools/decompose.py` | DAG generation + profondeur max + depends_on automatique + borne max sous-taches | Sprint 4 |
| `tools/bash_exec.py` | `asyncio.create_subprocess_exec` au lieu de `subprocess.run` | Sprint 4 |
| `adapters/assistant/adapter.py` | Injection workspace context dans `initial_markers` + isolation session | Sprint 4 |
| `adapters/assistant/workspace.py` | `get_context_summary()` : arborescence + fichiers cles + README | Sprint 4 |
| `main.py` | Session ID generation + nettoyage DB entre runs + output enrichi | Sprint 4 |
| `config/default.yaml` | Sections : `reinforcement`, `decay_rates_by_type`, `decompose`, `emergence`, `async` | Sprint 4 |

---

## Sprints Detailles V3

### Sprint 4 V3 : Runtime Overhaul -- "Le Framework qui Marche Vraiment" (7 jours)

**Objectif** : Corriger les 8 causes racines identifiees pour que l'assistant produise des resultats concrets et utiles. Apres ce sprint, un `python main.py --adapter assistant --objective "analyse ce repo"` doit lire les fichiers du workspace, analyser le code, et produire un rapport factuel.

#### 4.1 Client LLM Asynchrone + Structured Output

**Fichiers** : `llm/client.py`, `core/schemas.py`

**Changements** :
```python
# llm/client.py -- nouvelle interface
class LLMClient:
    def __init__(self, config):
        self.async_client = AsyncOpenAI(
            api_key=..., base_url=...,
            timeout=config["llm"]["request_timeout_seconds"],
        )
        self._semaphore = asyncio.Semaphore(
            config.get("async", {}).get("max_concurrent_llm_calls", 4)
        )
        self._budget_lock = asyncio.Lock()

    async def acall(
        self,
        prompt: str,
        system: str | None = None,
        response_schema: type[BaseModel] | None = None,
    ) -> LLMResponse:
        """Appel LLM non-bloquant avec structured output optionnel."""
        async with self._semaphore:
            # pre-check budget
            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=self._build_messages(prompt, system),
                temperature=self.temperature,
                response_format=(
                    {"type": "json_object"} if response_schema else NOT_GIVEN
                ),
            )
            # validate with Pydantic si schema fourni
            if response_schema:
                parsed = response_schema.model_validate_json(content)
            return LLMResponse(content=content, parsed=parsed, ...)
```

```python
# core/schemas.py -- schemas Pydantic
class ThinkOutput(BaseModel):
    analysis: str
    next_action: str | None = None
    path: str | None = None
    command: str | None = None
    query: str | None = None
    write: dict | None = None

class DecomposeOutput(BaseModel):
    subtasks: list[SubtaskSpec]
    class SubtaskSpec(BaseModel):
        title: str
        description: str = ""
        depends_on_indices: list[int] = []  # reference aux autres subtasks
        eligible_actions: list[str] = []

class ToolResult(BaseModel):
    success: bool
    output: str
    artifacts: dict = {}
```

**Tests** : 6 tests (`test_schemas.py`) : validation, rejection invalide, defaults, nested.

#### 4.2 Session Isolation + Pruning

**Fichiers** : `core/marker_store.py`, `main.py`

**Changements** :
- Chaque run genere un `session_id = uuid4()`. La DB est creee sous `pheromones/{session_id}/markers.db`.
- `apply_decay()` supprime les markers dont `intensity < prune_threshold` (defaut: 0.05).
- `query_markers()` utilise des SQL WHERE au lieu du filtre Python O(N).

**Config** :
```yaml
markers:
  prune_threshold: 0.05  # supprime les markers evapores
  session_isolation: true
```

**Tests** : 4 tests : isolation, pruning, query SQL.

#### 4.3 Contexte Workspace dans les Prompts

**Fichiers** : `adapters/assistant/workspace.py`, `llm/prompts.py`, `tools/think.py`

**Changements** :
```python
# adapters/assistant/workspace.py
class LocalWorkspace:
    def get_context_summary(self, max_depth: int = 3, max_files: int = 50) -> str:
        """Genere un resume structure du workspace pour injection LLM."""
        tree = self._build_tree(self.root, max_depth)
        readme = self._read_if_exists("README.md", max_chars=2000)
        key_files = self._identify_key_files()  # setup.py, pyproject.toml, etc.
        return f"""## Workspace Context
Root: {self.root}
### File Tree
{tree}
### Key Files
{key_files}
### README (excerpt)
{readme}"""
```

```python
# llm/prompts.py -- nouveau prompt system
SYSTEM_PROMPT_V3 = """You are a stigmergic worker agent operating in a shared environment.
You have access to the following workspace:

{workspace_context}

Your role is to complete the assigned task by using the available tools.
Always ground your reasoning in the actual files and content of the workspace.
Never hallucinate file paths, URLs, or commands -- use only what exists.

Available tools: {available_tools}

Return your response as strict JSON matching the provided schema."""
```

**Tests** : 3 tests : `get_context_summary` avec filesystem reel, injection dans prompt.

#### 4.4 Reinforcement Positif

**Fichiers** : `core/reinforcement.py`, `core/environment.py`

**Changements** :
```python
# core/reinforcement.py
def reinforce_on_success(
    marker: Marker,
    reinforcement_rate: float,
    quality_score: float = 1.0,
    max_intensity: float = 1.0,
) -> float:
    """Sigmoid reinforcement : renforce plus quand l'intensite est basse."""
    boost = reinforcement_rate * (max_intensity - marker.intensity) * quality_score
    return min(max_intensity, marker.intensity + boost)

def propagate_backward(
    completed_marker_id: str,
    all_markers: list[Marker],
    propagation_factor: float = 0.5,
) -> list[tuple[str, float]]:
    """Propage le reinforcement vers les markers dependants."""
    ...
```

Integration dans `Environment.apply_action_result()` :
- Si le marker passe a `completed`/`verified` : appeler `reinforce_on_success()`
- Si dependances existent : propager en arriere avec `propagate_backward()`

**Config** :
```yaml
reinforcement:
  enabled: true
  rate: 0.15            # taux de renforcement sigmoid
  propagation_factor: 0.5  # attenuation par hop dans le DAG
  max_intensity: 1.0
```

**Tests** : 5 tests : renforcement basique, sigmoid, propagation arriere, clamping.

#### 4.5 Dependances Inter-Markers (DAG)

**Fichiers** : `core/dependency.py`, `core/agent.py`, `tools/decompose.py`

**Changements** :
```python
# core/dependency.py
def validate_dag(markers: list[Marker]) -> bool:
    """Verifie qu'il n'y a pas de cycle via Kahn's algorithm."""
    ...

def unblocked_markers(
    markers: list[Marker],
    terminal_ids: set[str],
) -> list[Marker]:
    """Retourne les markers dont toutes les dependances sont satisfaites."""
    return [
        m for m in markers
        if all(dep in terminal_ids for dep in m.payload.get("depends_on", []))
    ]
```

Integration dans `StigmergicAgent._candidate_markers()` : les markers avec des dependances non-satisfaites sont filtres.

Integration dans `DecomposeTool` :
```python
# tools/decompose.py -- V3
class DecomposeOutput(BaseModel):
    subtasks: list[SubtaskSpec]

# Le LLM produit des indices de dependance :
# subtask[2].depends_on_indices = [0, 1]  => subtask 2 depend de 0 et 1
# Convertis en marker IDs lors du depot
```

**Config** :
```yaml
decompose:
  max_depth: 2              # profondeur max de decomposition
  max_subtasks: 8           # max sous-taches par decomposition
  allow_redecompose: false  # interdit la re-decomposition sauf escalation
```

**Tests** : 6 tests : DAG valide, detection cycle, filtre candidats, decomposition avec depends_on.

#### 4.6 Evaporation Differentielle

**Fichiers** : `core/decay.py`, `core/environment.py`

**Changements** :
```python
# core/decay.py -- V3
def decay_intensity_by_type(
    value: float,
    marker_type: str,
    decay_rates: dict[str, float],
    default_rate: float,
    clamp: tuple[float, float] = (0.0, 1.0),
) -> float:
    rate = decay_rates.get(marker_type, default_rate)
    return max(clamp[0], min(clamp[1], value * math.exp(-rate)))
```

**Config** :
```yaml
markers:
  decay_rates_by_type:
    task: 0.05          # standard
    progress: 0.05      # standard
    quality: 0.03       # persiste plus longtemps
    lesson: 0.01        # quasi-permanent (stigmergie cognitive)
    dependency: 0.01    # structurel, ne s'evapore presque pas
    anticipatory: 0.15  # volatile
  default_decay_rate: 0.05
```

**Tests** : 3 tests : decay differentiel par type, fallback defaut.

#### 4.7 Execution Async Reelle (Bash + Tools)

**Fichiers** : `tools/bash_exec.py`, `core/orchestrator.py`

**Changements** :
```python
# tools/bash_exec.py -- V3
async def execute(self, agent_id, marker, environment, llm_client):
    proc = await asyncio.create_subprocess_exec(
        *cmd_parts,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(workspace.root),
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=self.timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        ...
```

L'orchestrateur utilise deja `asyncio.gather()` -- mais maintenant les appels sous-jacents sont veritablement async.

**Tests** : 3 tests : execution async, timeout async, parallelisme reel.

#### 4.8 Correction des Outils

**Fichiers** : `tools/think.py`, `tools/decompose.py`, `tools/file_read.py`

**Changements** :
- `ThinkTool` : utilise `ThinkOutput` Pydantic schema. Injecte le contexte workspace dans le prompt. Ne peut plus generer des hints sans fondement.
- `DecomposeTool` : utilise `DecomposeOutput` schema. Borne a `max_subtasks` sous-taches, `max_depth` niveaux. Genere un DAG avec `depends_on`.
- Tous les outils : `STATE_PROGRESS` factorise dans une constante partagee.
- `FileReadTool` : peut lire l'arborescence du workspace (mode `tree`) en plus de fichiers individuels.

#### Tests d'acceptance Sprint 4

1. `uv run pytest tests/ -v` -- 100+ tests passent (85 existants + 30 nouveaux)
2. `python main.py --adapter assistant --objective "analyse ce repo"` produit un rapport base sur les fichiers reels
3. `python main.py --adapter assistant --objective "code un snake en python"` ecrit effectivement du code
4. Les 2 agents executent des LLM calls reellement en parallele (mesurable via timestamps)
5. Aucune pollution inter-sessions
6. Les markers forment un DAG sans cycles
7. L'intensite des markers reussis augmente (reinforcement mesurable)

**Theorie tracee** :
- Reinforcement -> Bonabeau et al. (1999) Eq. 2.1, Theraulaz & Bonabeau (1999)
- DAG dependances -> Carriero & Gelernter (1992), Prefect v3
- Contexte workspace -> Ricci et al. (2007) stigmergie cognitive
- Evaporation differentielle -> Parunak et al. (2005), Pheromind swarmConfig
- Structured output -> OpenAI (2024), Anthropic (2024) -- best practices industrielles

---

### Sprint 5 V3 : Emergence & Memoire Cognitive -- "Les Agents qui Apprennent" (5 jours)

**Objectif** : Ajouter la memoire cognitive par agent et les metriques d'emergence. Apres ce sprint, on peut mesurer la specialisation emergente et la collaboration entre agents.

#### 5.1 Memoire Cognitive par Agent

**Fichiers** : `core/agent.py` (modification), nouveau module interne

**Concept** : Chaque agent maintient un buffer memoire borné de (contexte, action, resultat, score). Ce buffer est injecte dans le prompt LLM comme contexte episodique. Les entrees reussies sont renforcees, les ratees s'evaporent.

**Changements** :
```python
# Dans core/agent.py
class AgentMemory:
    """Memoire episodique bornee -- stigmergie cognitive locale."""
    
    def __init__(self, capacity: int = 20, decay_rate: float = 0.1):
        self._entries: list[MemoryEntry] = []
        self.capacity = capacity
        self.decay_rate = decay_rate
    
    def remember(self, context: str, action: str, result: str, score: float):
        """Stocke une experience."""
        entry = MemoryEntry(context=context, action=action, 
                           result=result, relevance=score)
        if len(self._entries) >= self.capacity:
            self._evict_weakest()
        self._entries.append(entry)
    
    def recall(self, current_context: str, k: int = 3) -> list[MemoryEntry]:
        """Rappelle les k experiences les plus pertinentes."""
        # Tri par relevance * recency, keyword overlap
        ...
    
    def reinforce(self, entry_id: str, boost: float = 0.1):
        """Renforce une memoire qui s'est averee utile."""
        ...
    
    def decay_all(self):
        """Applique la courbe d'oubli."""
        for e in self._entries:
            e.relevance *= (1.0 - self.decay_rate)
        self._entries = [e for e in self._entries if e.relevance > 0.05]

class StigmergicAgent:
    def __init__(self, ...):
        ...
        self.memory = AgentMemory(
            capacity=config.get("agents", {}).get("memory_capacity", 20),
            decay_rate=config.get("agents", {}).get("memory_decay_rate", 0.1),
        )
    
    async def perceive_and_decide(self, snapshot):
        # 1. Rappeler experiences pertinentes
        context_summary = self._summarize_snapshot(snapshot)
        memories = self.memory.recall(context_summary, k=3)
        
        # 2. Injecter dans le prompt
        memory_context = self._format_memories(memories)
        
        # 3. Decider avec memoire
        ...
```

**Impact sur l'emergence** : Les agents qui executent souvent `file_read` accumulent des memoires "file_read a marche pour X", ce qui biaise leurs decisions futures vers `file_read`. C'est de la specialisation emergente -- aucun role n'est assigne, le biais emerge de l'experience.

**Tests** : 6 tests : remember, recall, eviction, decay, integration avec agent.

#### 5.2 Formule de Pression ACO

**Fichiers** : `core/pressure.py`

**Changements** :
```python
# core/pressure.py -- V3 ACO-style
def compute_pressures_aco(
    markers: list[Marker],
    action_types: list[str],
    weights: dict[str, float],
    alpha: float = 1.0,      # poids pheromone
    beta: float = 2.0,       # poids heuristique
    heuristic_fn: Callable | None = None,
    inhibition_threshold: float = 0.1,
) -> dict[str, float]:
    """P(action) = sum( intensity^alpha * heuristic^beta ) / Z
    
    [ACO-ToT (Chari et al., 2025) + Rodriguez (2026)]
    """
    pressures = {a: 0.0 for a in action_types}
    for marker in markers:
        if marker.state in TERMINAL_STATES or marker.inhibition >= inhibition_threshold:
            continue
        pheromone = marker.intensity ** alpha
        for action in _eligible_actions(marker, action_types):
            heuristic = (heuristic_fn(marker, action) if heuristic_fn 
                        else weights.get(action, 1.0))
            pressures[action] += pheromone * (heuristic ** beta)
    
    total = sum(pressures.values())
    if total > 0:
        pressures = {a: p / total for a, p in pressures.items()}
    return pressures
```

**Config** :
```yaml
pressures:
  formula: "aco"        # "simple" (V2) | "aco" (V3)
  alpha: 1.0            # poids pheromone
  beta: 2.0             # poids heuristique
  default_weights:
    think: 1.0
    decompose: 0.8
    file_read: 1.2
    file_write: 1.0
    bash_exec: 1.0
    web_search: 1.0
```

**Tests** : 4 tests : formule ACO, alpha/beta effects, comparaison avec simple.

#### 5.3 Metriques d'Emergence Natives

**Fichiers** : `core/emergence.py` (nouveau)

**8 metriques calculees a chaque tick** :

| Metrique | Formule | Reference |
|----------|---------|-----------|
| `specialization_entropy` | H(agent) = -sum(p_a * log(p_a)) pour chaque agent, normalisee [0,1] | Serugendo et al. (2005) |
| `colony_specialization` | 1 - mean(H(agent_i)) : 0=generaliste, 1=ultra-specialise | Rodriguez (2026) |
| `collaboration_density` | items touches par >1 agent / total items | Heylighen (2016) |
| `action_switching_rate` | changements d'action / total decisions par agent | Bonabeau et al. (1999) |
| `convergence_tick` | premier tick ou >= 80% markers terminaux | Parunak et al. (2005) |
| `lock_contention_rate` | echecs lock / tentatives par tick | Ricci et al. (2007) |
| `parallel_utilization` | agents actifs / agents totaux par tick | Rodriguez (2026) |
| `pressure_entropy` | H(pressures) : diversite de la distribution de pression | Serugendo et al. (2005) |

```python
# core/emergence.py
@dataclass
class EmergenceMetrics:
    specialization_entropy: dict[str, float]  # par agent
    colony_specialization: float
    collaboration_density: float
    action_switching_rate: dict[str, float]
    lock_contention_rate: float
    parallel_utilization: float
    pressure_entropy: float

def compute_emergence_metrics(
    tick_history: list[TickRow],
    current_tick: int,
) -> EmergenceMetrics:
    """Calcule les metriques d'emergence a partir de l'historique des ticks."""
    ...
```

Integration dans `Orchestrator.run()` : `EmergenceMetrics` calcule a chaque tick et stocke dans `TickRow`.

**Tests** : 8 tests (1 par metrique) avec donnees synthetiques.

#### 5.4 Markers de type `lesson`

Quand un agent complete un marker avec succes et que le resultat est de haute qualite (score > seuil), il depose un marker `lesson` dans l'environnement. Ce marker a un taux d'evaporation tres bas (`0.01`) et contient une synthese de ce qui a marche.

Les autres agents peuvent lire ces `lesson` markers lors de `perceive_and_decide` pour beneficier de l'apprentissage collectif. C'est de la stigmergie cognitive partagee (Ricci et al., 2007).

#### Tests d'acceptance Sprint 5

1. `uv run pytest tests/ -v` -- 130+ tests passent
2. Les metriques d'emergence sont calculees et non-triviales (specialisation > 0)
3. La memoire cognitive produit un biais de specialisation mesurable
4. Les markers `lesson` sont deposes et lus par d'autres agents
5. La formule ACO produit des distributions de pression differentes de la formule simple
6. Dashboard textuel des metriques d'emergence en sortie CLI

**Theorie tracee** :
- Memoire cognitive -> Ricci et al. (2007) stigmergie cognitive, CoALA episodic memory
- Formule ACO -> Bonabeau et al. (1999) Eq. 2.1, Chari et al. (2025) ACO-ToT
- Metriques emergence -> Rodriguez (2026), Serugendo et al. (2005)
- Markers lesson -> Heylighen (2016b) stigmergie basee sur marqueurs

---

### Sprint 6 V3 : Adaptateur TravelPlanner -- Iteration DSR 1 (5 jours)

**Objectif** : Premier adaptateur de benchmark. Valider OC1 (generaliste) et OC3 (battre SwarmAgentic 32.2% sur TravelPlanner).

**Fichiers a creer** : (identique au V2 plan Sprint 4 mais avec les ameliorations V3)

| Fichier | Contenu |
|---------|---------|
| `adapters/travelplanner/adapter.py` | `TravelPlannerAdapter` avec DAG de markers, reinforcement, metriques |
| `adapters/travelplanner/workspace.py` | Acces aux databases TravelPlanner (vols, hotels, attractions) |
| `adapters/travelplanner/tools.py` | 6 outils : search flights/hotels/attractions, plan day, validate constraints, refine |
| `adapters/travelplanner/evaluator.py` | Final score, hard constraint macro, soft constraint, commonsense |
| `config/travelplanner.yaml` | Config avec poids de pression optimises, decay rates specifiques |
| `tests/integration/test_travelplanner.py` | 10 tests avec mock LLM + fixture queries |

**Machine a etats TravelPlanner V3** :
```
pending -> searching -> planning -> validating -> terminal
                    \-> searching (recherche supplementaire)
          planning -> planning (raffinement -- bounded)
          validating -> planning (echec contraintes -> re-planifier, max 2 retries)
```

**DAG typique** :
```
search_flights --|
search_hotels  --|--> plan_itinerary --> validate_constraints --> finalize
search_attractions--|
```

**Tests d'acceptance** :
1. `uv run pytest tests/ -v` -- 140+ tests
2. Dry run sur 5 queries TravelPlanner (mock LLM)
3. Run reel sur validation set >= 10 queries
4. Final score mesure et compare a SwarmAgentic (cible: >= 32.2%)
5. Metriques d'emergence calculees et analysees

**Livrable DSR Iteration 1** :
- Resultats quantitatifs TravelPlanner
- Metriques d'emergence (specialisation, collaboration)
- Lecons de conception documentees
- Sprint artifact : `documentation/redesign_v2/sprint_06_artifact.md`

---

### Sprint 7 V3 : Baselines + Harness de Benchmark (4 jours)

**Objectif** : Construire les 3 baselines de comparaison (single-agent, sequential, centralized) et le harness de benchmark pour des runs reproductibles.

**Fichiers a creer** :

| Fichier | Contenu |
|---------|---------|
| `benchmarks/harness.py` | `BenchmarkHarness` : N configs x M runs, collecte resultats, CI95 |
| `benchmarks/runners/single_agent.py` | 1 agent, tous outils, sequentiel |
| `benchmarks/runners/sequential.py` | Pipeline fixe (style V0.1) |
| `benchmarks/runners/centralized.py` | LLM superviseur dispatche aux workers |
| `benchmarks/runners/stigmergic.py` | Runner stigmergique V3 standard |
| `benchmarks/analysis/pareto.py` | Analyse Pareto (precision vs cout) |
| `benchmarks/analysis/export.py` | CSV/JSON/PNG export |
| `tests/integration/test_baselines.py` | 6 tests |

**Contraintes de rigueur (Kapoor et al., 2024)** :
- Meme modele LLM, meme temperature, memes outils
- >= 5 runs par configuration
- Intervalles de confiance 95%
- Frontiere de Pareto cout-precision

**Tests d'acceptance** :
1. `uv run pytest tests/ -v` -- 150+ tests
2. 4 configs x 5 runs sur TravelPlanner (20 runs minimum)
3. Pareto plot genere
4. CSV/JSON resultats exportes
5. Reproductibilite verifiee (2 runs identiques avec meme seed)

---

### Sprint 8 V3 : Adaptateur Code Migration -- Iteration DSR 2 (5 jours)

**Objectif** : Deuxieme adaptateur de domaine. Valider OC4 sur code migration.

**Fichiers a creer** :

| Fichier | Contenu |
|---------|---------|
| `adapters/codemigration/adapter.py` | `CodeMigrationAdapter` avec DAG, reinforcement, metriques |
| `adapters/codemigration/workspace.py` | `GitWorkspace` : clone, branch, list_files, read, write, commit |
| `adapters/codemigration/tools.py` | 4 outils LLM-driven ZERO REGEX : Discover, Transform, Test, Validate |
| `adapters/codemigration/evaluator.py` | Success rate, rollback rate, cost per file |
| `config/codemigration.yaml` | Config specifique |
| `tests/integration/test_codemigration.py` | 10 tests |
| `tests/fixtures/synthetic_repo/` | Petit repo Python 2 synthetique |

**Difference cle V3 vs V2** : Le `DiscoverTool` beneficie de la memoire cognitive. Les agents qui ont deja decouvert des patterns dans d'autres fichiers appliquent cette connaissance aux fichiers suivants -- specialisation emergente en action.

**DAG typique code migration** :
```
discover_file_1 --> transform_file_1 --> test_file_1 --> validate_file_1
discover_file_2 --> transform_file_2 --> test_file_2 --> validate_file_2
                                                          |
                                                          v
                                                    integration_test
```

**Tests d'acceptance** :
1. `uv run pytest tests/ -v` -- 160+ tests
2. Run sur repo synthetique Python 2 -> Python 3
3. Success rate >= 85% sur repo synthetique
4. Comparaison V3 stigmergique vs baselines sur meme repo
5. Metriques d'emergence montrant specialisation agent

**Livrable DSR Iteration 2** :
- Resultats code migration
- Comparaison avec baselines
- Metriques d'emergence
- Lecons de conception
- Sprint artifact

---

### Sprint 9 V3 : SWE-bench + Docker + Gouvernance -- Iteration DSR 3 (5 jours)

**Objectif** : Troisieme adaptateur, Docker reproductibilite, validation OC5 gouvernance.

**Fichiers a creer** :

| Fichier | Contenu |
|---------|---------|
| `adapters/swebench/adapter.py` | `SWEBenchAdapter` |
| `adapters/swebench/workspace.py` | Clone repo + apply issue context |
| `adapters/swebench/tools.py` | 5 outils : localize, patch, test, validate, refine |
| `adapters/swebench/evaluator.py` | Resolution rate, cost per issue |
| `config/swebench.yaml` | Config specifique |
| `Dockerfile` | Image de benchmark |
| `docker-compose.yml` | Dev environment |
| `docker-compose.benchmark.yml` | 4 configs x N runs |
| `tests/integration/test_swebench.py` | 8 tests |

**Metriques de gouvernance (OC5)** :

| Metrique | Cible | Verification |
|----------|-------|-------------|
| Audit completeness | >= 99.5% transitions loggees | `audit_log.jsonl` vs `markers.db` diff |
| Decision traceability | 100% transitions avec before/after | Champ `history` + audit events |
| Budget compliance | 0 depassements | Guardrail + test |
| Human escalation | Tous items ambigus escalades | State `escalated` + compteur |

**Tests d'acceptance** :
1. `uv run pytest tests/ -v` -- 170+ tests
2. Run sur SWE-bench Lite subset (10-20 issues)
3. Pareto cross-domaine : TravelPlanner + CodeMigration + SWE-bench
4. Audit completeness >= 99.5%
5. `docker compose -f docker-compose.benchmark.yml up` -- reproductible
6. Tous les principes de conception documentes (format Gregor et al., 2020)

**Livrables DSR Iteration 3 + Final** :
- Resultats SWE-bench
- Analyse cross-domaine
- Principes de conception extraits
- Benchmarks Docker reproductibles
- Pareto plots (3 domaines x 4 configs x 5 runs)
- Dashboard emergence complet
- Construction log final

---

## Configuration par Defaut V3 (`config/default.yaml`)

```yaml
# Framework stigmergique V3
framework:
  name: "stigmergy-v3"
  version: "3.0.0"

# Agents
agents:
  num_agents: 4
  num_agents_mode: "fixed"
  selection_temperature: 0.1
  memory_capacity: 20         # NOUVEAU V3 -- entries de memoire cognitive par agent
  memory_decay_rate: 0.1      # NOUVEAU V3 -- taux d'oubli

# Markers
markers:
  decay_type: "exponential"
  default_decay_rate: 0.05
  decay_rates_by_type:        # NOUVEAU V3 -- evaporation differentielle
    task: 0.05
    progress: 0.05
    quality: 0.03
    lesson: 0.01              # quasi-permanent
    dependency: 0.01          # structurel
    anticipatory: 0.15        # volatile
  inhibition_decay_rate: 0.08
  inhibition_increment: 0.5
  inhibition_threshold: 0.1
  intensity_clamp: [0.1, 1.0]
  prune_threshold: 0.05       # NOUVEAU V3 -- supprime markers evapores
  session_isolation: true      # NOUVEAU V3 -- DB ephemere par run

# Reinforcement
reinforcement:                 # NOUVEAU V3
  enabled: true
  type: "sigmoid"              # additive | multiplicative | sigmoid
  rate: 0.15
  propagation_factor: 0.5     # attenuation par hop dans le DAG
  max_intensity: 1.0

# Decomposition
decompose:                     # NOUVEAU V3
  max_depth: 2                 # profondeur max de decomposition
  max_subtasks: 8              # max sous-taches par decomposition
  allow_redecompose: false     # interdit sauf escalation

# Guardrails
guardrails:
  max_retry_count: 3
  scope_lock_ttl: 3
  traceability: true
  audit_completeness: true

# Orchestrateur
orchestrator:
  max_ticks: 50
  idle_cycles_to_stop: 3       # V3 : 3 au lieu de 2 (plus de patience)
  parallel: true

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

# Async
async:                         # NOUVEAU V3
  max_concurrent_llm_calls: 4  # semaphore
  subprocess_timeout: 60

# Pressions
pressures:
  formula: "aco"               # NOUVEAU V3 -- "simple" (V2) | "aco" (V3)
  alpha: 1.0                   # poids pheromone dans formule ACO
  beta: 2.0                    # poids heuristique dans formule ACO
  default_weights:
    think: 1.0
    decompose: 0.8
    file_read: 1.2
    file_write: 1.0
    bash_exec: 1.0
    web_search: 1.0

# Outils d'infrastructure
tools:
  sandbox_root: "."
  allowed_commands: ["python", "pytest", "git", "pip", "uv"]
  bash_timeout_seconds: 60
  max_file_size_bytes: 1048576
  web_search_provider: "none"
  web_search_max_results: 5

# Emergence
emergence:                     # NOUVEAU V3
  enabled: true
  metrics:
    - specialization_entropy
    - colony_specialization
    - collaboration_density
    - action_switching_rate
    - convergence_tick
    - lock_contention_rate
    - parallel_utilization
    - pressure_entropy
```

---

## Resume des Sprints V3

| Sprint | Duree | Objectif | Tests cumules | Couche | DSR |
|--------|-------|----------|---------------|--------|-----|
| Sprint 1-3 V2 | FAIT | Core + Outils + Assistant | 85 | L1-L3 | Foundation |
| **Sprint 4 V3** | **7 jours** | **Runtime Overhaul : async, DAG, reinforcement, contexte, schemas** | **100+** | **L0-L3** | **Enablement** |
| **Sprint 5 V3** | **5 jours** | **Emergence : memoire cognitive, formule ACO, metriques** | **130+** | **L2** | **Emergence** |
| **Sprint 6 V3** | **5 jours** | **TravelPlanner adapter** | **140+** | **L3-L4** | **Iteration 1 (OC1, OC3)** |
| **Sprint 7 V3** | **4 jours** | **Baselines + Harness benchmark** | **150+** | **L5** | **Evaluation** |
| **Sprint 8 V3** | **5 jours** | **Code Migration adapter** | **160+** | **L3-L4** | **Iteration 2 (OC4)** |
| **Sprint 9 V3** | **5 jours** | **SWE-bench + Docker + Gouvernance** | **170+** | **L3-L5** | **Iteration 3 (OC4, OC5)** |

**Total V3 : ~31 jours de dev** (6 sprints)

---

## Mapping Causes Racines -> Corrections V3

| Cause racine | Sprint | Correction |
|-------------|--------|------------|
| CR-1 : Agents deconnectes du workspace | Sprint 4 | `get_context_summary()` + injection prompt |
| CR-2 : Decomposition non bornee | Sprint 4 | `max_depth=2`, `max_subtasks=8`, DAG |
| CR-3 : Pas de parallelite LLM | Sprint 4 | `AsyncOpenAI` + semaphore + async subprocess |
| CR-4 : Pas de reinforcement positif | Sprint 4 | `core/reinforcement.py` + propagation arriere |
| CR-5 : Pas de dependances | Sprint 4 | `core/dependency.py` + `depends_on` |
| CR-6 : Prompts/output fragiles | Sprint 4 | `core/schemas.py` + `response_format` |
| CR-7 : Memoire agent inexistante | Sprint 5 | `AgentMemory` + injection episodique |
| CR-8 : DB partagee entre runs | Sprint 4 | Session isolation via `session_id` |
| CR-9 : Metrics emergence absentes | Sprint 5 | `core/emergence.py` + 8 metriques |

---

## Mapping OC (Objectifs de Conception DSR) -> Sprints

| OC | Description | Sprints de validation |
|----|-------------|----------------------|
| OC1 | Architecture generaliste | Sprint 4-5 (core V3) + Sprint 6 (TravelPlanner) + Sprint 8 (CodeMigration) |
| OC2 | Specialisation emergente | Sprint 5 (metriques) + Sprint 6-8 (mesures sur benchmarks) |
| OC3 | Surpasser SwarmAgentic (>= 32.2%) | Sprint 6 (TravelPlanner) + Sprint 7 (baselines) |
| OC4 | Competitivite code | Sprint 8 (CodeMigration) + Sprint 9 (SWE-bench) |
| OC5 | Gouvernance EU AI Act | Sprint 9 (audit, traceability, escalation) |

---

## Principes de conception generalisables (format Gregor et al., 2020)

A valider empiriquement au cours des sprints :

**DP1 -- Contexte environnemental** : Pour des agents LLM operant sur des artefacts (code, documents, donnees), ancrer chaque decision dans un resume structure du workspace actuel produira des actions plus pertinentes et moins d'hallucinations, parce que la stigmergie cognitive (Ricci et al., 2007) exige que les agents interpretent l'etat reel de l'environnement.

**DP2 -- Renforcement symetrique** : Pour une coordination stigmergique efficace, implementer a la fois l'evaporation ET le renforcement positif des pheromones numeriques produira une convergence vers les chemins productifs, parce que la boucle de retroaction positive est le mecanisme fondamental de l'intelligence en essaim (Bonabeau et al., 1999).

**DP3 -- Decomposition topologique** : Pour des taches complexes decomposees en sous-taches, structurer les dependances comme un DAG explicite produira une execution ordonnee et parallele, parce que la separation calcul/coordination (Carriero & Gelernter, 1992) exige que les dependances soient externalisees dans l'environnement.

**DP4 -- Memoire cognitive emergente** : Pour des agents homogenes sans roles assignes, doter chaque agent d'une memoire episodique locale produira une specialisation emergente mesurable, parce que l'accumulation d'experience biaise les decisions futures sans assignation explicite (stigmergie cognitive, Ricci et al., 2007).

**DP5 -- Evaporation differentielle** : Pour un environnement stigmergique mixte (taches, progres, lecons, dependances), appliquer des taux d'evaporation specifiques par type de marker produira un equilibre entre exploration et exploitation, parce que les signaux structurels (dependances) et les signaux volatils (anticipations) ont des durees de vie biologiquement differentes (Parunak et al., 2005).

**DP6 -- Gouvernance par l'environnement** : Pour satisfaire les exigences de supervision humaine (EU AI Act Art. 14), implementer les guardrails comme contraintes environnementales (deep norms) plutot que comme regles agent produira une gouvernance verifiable et evoluable, parce que la centralisation de la gouvernance dans l'environnement la rend inspectable et auditable independamment des agents (Grisold et al., 2025).

---

## Notes pour les Agents IA

Ce plan V3 corrige les defauts fondamentaux identifies dans le V2 tout en preservant l'architecture de base (markers, store, pressure, orchestrator). Le Sprint 4 est le plus critique car il corrige 7 des 9 causes racines.

**Ordre de developpement recommande pour le Sprint 4** :
1. `core/schemas.py` (pas de dependance)
2. `llm/client.py` refonte async (depend de schemas)
3. `core/dependency.py` (pas de dependance)
4. `core/reinforcement.py` (pas de dependance)
5. `core/marker_store.py` modifications (session, pruning, SQL queries)
6. `core/decay.py` modifications (differentiel)
7. `core/environment.py` modifications (reinforcement, pruning)
8. `adapters/assistant/workspace.py` (context summary)
9. `llm/prompts.py` (injection contexte)
10. `tools/think.py`, `tools/decompose.py` (schemas + contexte)
11. `tools/bash_exec.py` (async subprocess)
12. `core/agent.py` (filtre dependances)
13. `core/orchestrator.py` (session isolation, async)
14. `main.py` (session ID, nettoyage, output enrichi)
15. Tests (en parallele avec chaque module)
16. Integration test end-to-end
