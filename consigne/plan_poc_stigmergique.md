# Plan detaille — POC Orchestration Stigmergique

**Projet** : Orchestration stigmergique de systemes multi-agents LLM
**Cas d'usage** : Migration Python 2 → Python 3
**Auteur** : Abdelatif Djeddou — Memoire EMLV
**Date** : 8 fevrier 2026
**Provider LLM** : OpenRouter (qwen/qwen3-235b-a22b-2507 pour le dev, modele frontiere pour les resultats finaux)

---

## 1. Vision d'ensemble

### 1.1 Ce qu'on construit

Un systeme ou **4 agents LLM specialises** migrent automatiquement du code Python 2 vers Python 3, coordonnes **uniquement** via un environnement partage (pheromones numeriques). Aucun agent ne communique directement avec un autre. L'environnement (depot Git + fichiers JSON de pheromones) est le seul medium de coordination — c'est le principe stigmergique de Grasse (1959), operationnalise via le paradigme Agents & Artifacts de Ricci et al. (2007).

### 1.2 Ce qu'on veut prouver

| Question de recherche | Ce que le POC doit demontrer |
|---|---|
| **RQ1 — Mecanisme** | Les pheromones numeriques (tache, statut, qualite) suffisent a coordonner des agents LLM sans superviseur central |
| **RQ2 — Performance** | La coordination stigmergique atteint ou depasse le baseline Agentless (Xia et al., 2024) sur un perimetre de migration Py2→Py3, avec un cout maitrise |
| **RQ3 — Gouvernance** | Les traces environnementales permettent l'auditabilite complete (tracking + tracing au sens de Santoni de Sio & van den Hoven, 2018) |

**Positionnement scientifique** : A notre connaissance, ce POC constitue la premiere etude empirique appliquant la stigmergie de Grasse (1959) a la coordination d'agents LLM pour la migration de code. Les frameworks multi-agents existants reposent sur des superviseurs centraux (MetaGPT : SOPs hierarchiques, AutoGen : actor model avec routeur, CrewAI : delegation explicite, LangChain/LangGraph : graphes diriges). Notre approche elimine le superviseur au profit d'un medium environnemental (JSON + Git) qui est a la fois le canal de coordination et la trace d'audit. Ce vide identifie dans la litterature motive la presente etude.

### 1.3 Architecture a 30 000 pieds

```
┌─────────────────────────────────────────────────────┐
│                 BOUCLE PRINCIPALE                    │
│            (round-robin, pas superviseur)            │
│                                                     │
│   ┌──────┐  ┌────────────┐  ┌────────┐  ┌────────┐ │
│   │Scout │  │Transformer │  │Tester  │  │Validator│ │
│   │      │  │            │  │        │  │        │ │
│   └──┬───┘  └─────┬──────┘  └───┬────┘  └───┬────┘ │
│      │            │             │            │      │
│      ▼            ▼             ▼            ▼      │
│  ┌─────────────────────────────────────────────┐    │
│  │      ENVIRONNEMENT PARTAGE (medium)         │    │
│  │                                             │    │
│  │  tasks.json     (pheromones de tache)       │    │
│  │  status.json    (pheromones de statut)      │    │
│  │  quality.json   (pheromones de qualite)     │    │
│  │  target_repo/   (code Git)                  │    │
│  │  guardrails.py  (contraintes env.)          │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

**Principe fondamental** : chaque agent lit → decide → agit → depose une trace. La trace stimule l'agent suivant. C'est la boucle action → trace → stimulus → action.

---

## 2. Structure du projet

```
stigmergic-poc/
│
├── agents/                     # Les 4 agents specialises
│   ├── __init__.py
│   ├── base_agent.py           # Classe abstraite commune
│   ├── scout.py                # Analyse codebase Py2
│   ├── transformer.py          # Generation code Py3
│   ├── tester.py               # Execution tests
│   └── validator.py            # Validation + renforcement
│
├── environment/                # Le medium stigmergique
│   ├── __init__.py
│   ├── pheromone_store.py      # CRUD pheromones (JSON)
│   ├── guardrails.py           # Contraintes environnementales
│   └── decay.py                # Evaporation temporelle
│
├── stigmergy/                  # Orchestration
│   ├── __init__.py
│   ├── loop.py                 # Boucle principale round-robin
│   ├── config.yaml             # Parametres (seuils, decay, budget)
│   └── llm_client.py           # Client OpenRouter unifie
│
├── target_repo/                # Depot Python 2 a migrer (Git)
│   └── (clone dynamiquement)
│
├── pheromones/                 # Store de traces (runtime)
│   ├── tasks.json
│   ├── status.json
│   ├── quality.json
│   └── audit_log.jsonl         # Append-only audit trail (RQ3)
│
├── metrics/                    # Collecte et analyse
│   ├── __init__.py
│   ├── collector.py            # Enregistrement par tick
│   ├── pareto.py               # Analyse cout-precision
│   └── export.py               # Export CSV pour analyse
│
├── baselines/                  # Comparaisons
│   ├── single_agent.py         # 1 seul agent fait tout
│   └── sequential.py           # Pipeline sequentiel (type Agentless)
│
├── tests/
│   ├── test_pheromone_store.py
│   ├── test_agents.py
│   ├── test_guardrails.py
│   └── test_migration.py
│
├── consigne/                   # Specification et revue de litterature
│   └── plan_poc_stigmergique.md
│
├── .gitignore
├── .env.example                # Template variables d'environnement
├── requirements.txt            # Dependances avec versions exactes
├── README.md
└── main.py                     # Point d'entree CLI
```

---

## 3. Specification des pheromones

### 3.1 Pheromones de TACHE (quantitatives)

Deposees par le **Scout**. Indiquent les fichiers a migrer et leur priorite.

```json
{
  "utils.py": {
    "intensity": 0.87,
    "patterns_found": ["print_stmt", "dict_iteritems", "unicode_literals"],
    "pattern_count": 14,
    "dependencies": ["config.py", "helpers.py"],
    "dep_count": 3,
    "created_at": "2026-02-08T10:00:00Z",
    "created_by": "scout"
  }
}
```

**Regle d'intensite** — Normalisation min-max sur le batch de scan :

```
S_i = pattern_count_i × 0.6 + dep_count_i × 0.4
intensity_i = (S_i - S_min) / (S_max - S_min)
```

- Clamp final : `[0.1, 1.0]` (floor a 0.1 pour que tout fichier detecte ait une chance d'etre traite)
- Cas degenere : si `S_max == S_min` → `intensity = 0.5` pour tous les fichiers
- La normalisation se fait sur le batch complet du scan courant

**Note sur l'ordre de migration** : la formule actuelle priorise les fichiers complexes (beaucoup de patterns + beaucoup de dependances). En pratique, les fichiers simples ("feuilles" du graphe d'import) seront traites en premier car le Transformer les prend pendant que les fichiers complexes sont encore en analyse par le Scout ou en attente. Cet ordre de migration est un **comportement emergent** a observer et documenter — c'est un resultat experimental, pas un parametre a forcer. Si l'experience montre que migrer les feuilles d'abord est systematiquement meilleur, on pourrait inverser le poids de `dep_count` (penalite au lieu de bonus) dans une iteration future.

**Evaporation** : decay exponentiel (voir section 3.5)

### 3.2 Pheromones de STATUT (qualitatives)

Deposees par **chaque agent** apres action. Marquent l'etat du fichier dans le pipeline.

```json
{
  "utils.py": {
    "status": "transformed",
    "previous_status": "pending",
    "agent": "transformer",
    "timestamp": "2026-02-08T10:05:00Z",
    "retry_count": 0,
    "inhibition": 0.0,
    "metadata": {
      "tokens_used": 1240,
      "patterns_migrated": ["print_stmt", "dict_iteritems"],
      "diff_lines": 23
    }
  }
}
```

**Etats possibles** : voir section 3.7 (machine a etats complete)

**Champ `inhibition`** (γ) : mecanisme anti-oscillation inspire de Rodriguez (2026). Quand un fichier passe en `retry`, γ est incremente de +0.5. Le Transformer ne reprend le fichier que si `γ < 0.1` (inhibition dissipee). Voir section 3.5 pour la formule de decay de l'inhibition.

### 3.3 Pheromones de QUALITE (quantitatives)

Deposees par le **Tester** et renforcees/evaporees par le **Validator**.

```json
{
  "utils.py": {
    "confidence": 0.92,
    "tests_total": 18,
    "tests_passed": 17,
    "tests_failed": 1,
    "coverage": 0.78,
    "issues": ["test_unicode_handling: AssertionError line 42"],
    "timestamp": "2026-02-08T10:08:00Z"
  }
}
```

**Confidence initiale** : `tests_passed / tests_total`. Si aucun test n'existe pour le fichier → `confidence = 0.5` (neutre).

**Renforcement** : si tests passent → `confidence += 0.1` (plafonne a 1.0)
**Evaporation** : si tests echouent → `confidence -= 0.2` et status → `retry`

**Coverage** : collectee via `pytest-cov` — informationnelle uniquement, n'affecte pas la confidence. Sert de metrique pour l'analyse finale.

**Test discovery** : le Tester cherche les tests dans cet ordre :
1. Fichier `test_{filename}.py` dans le dossier `tests/` du target_repo
2. Fichier `test_{filename}.py` dans le meme repertoire que le fichier source
3. **Fallback** si aucun test n'existe : `py_compile.compile(filepath)` + `python -c "import {module}"` pour verifier au minimum la validite syntaxique et l'importabilite

### 3.4 API du Pheromone Store

Classe `PheromoneStore` dans `environment/pheromone_store.py`. Interface unique pour toutes les operations sur les pheromones.

**Methodes** :

| Methode | Signature | Description |
|---|---|---|
| `read_all` | `(pheromone_type: str) -> dict` | Lit toutes les entrees d'un type (`tasks`, `status`, `quality`) |
| `read_one` | `(pheromone_type: str, file_key: str) -> dict` | Lit l'entree d'un fichier specifique |
| `query` | `(pheromone_type: str, **filters) -> dict` | Filtre par champs (ex: `status="pending"`, `intensity__gt=0.3`) |
| `write` | `(pheromone_type: str, file_key: str, data: dict) -> None` | Ecrit/ecrase l'entree d'un fichier |
| `update` | `(pheromone_type: str, file_key: str, **fields) -> None` | Met a jour des champs specifiques |
| `apply_decay` | `(pheromone_type: str) -> None` | Applique le decay exponentiel a toutes les entrees eligibles |

**Structure JSON** : dictionnaire indexe par nom de fichier (file key). Chaque fichier JSON (`tasks.json`, `status.json`, `quality.json`) suit ce schema.

**File locking** : via `fcntl.flock` (POSIX) pour eviter les corruptions en cas de race condition. Chaque operation acquiert un lock exclusif sur le fichier JSON cible.

**Write path** : chaque appel a `write` ou `update` applique automatiquement :
1. Ajout du `timestamp` (ISO 8601 UTC)
2. Ajout de la signature agent (`created_by` ou `updated_by`)
3. Verification du scope lock (un seul agent par fichier — guardrail)
4. Append dans `pheromones/audit_log.jsonl` (voir section 3.6)

**Proprietes d'artefact** (Ricci et al., 2007 — Agents & Artifacts) :

Les fichiers JSON de pheromones sont des **artefacts** au sens formel du paradigme A&A :
- **Inspectabilite** : tout agent peut lire l'etat courant de n'importe quel fichier JSON via `read_all`, `read_one`, `query`. L'etat de l'environnement est toujours observable.
- **Controlabilite** : les agents modifient l'etat via `write`/`update`, sous contrainte des guardrails. L'environnement accepte ou refuse la modification.
- **Composabilite** : les pheromones se referencent mutuellement. `tasks.json` reference un fichier → `status.json` trace son etat dans le pipeline → `quality.json` stocke sa confidence et ses resultats de tests. Les trois artefacts forment un systeme coherent.

### 3.5 Mecanisme d'evaporation

**Decay exponentiel** (Rodriguez, 2026 — Theorem 5.1 sur la convergence) :

```
intensity^(t+1) = intensity^t × e^(-ρ)    ou ρ = 0.05
```

- 1 tick = 1 cycle round-robin complet (Scout → Transformer → Tester → Validator)
- Le decay est applique au **debut** de chaque tick, avant que les agents n'agissent
- S'applique uniquement aux fichiers en statut `pending` ou `retry` (les fichiers en cours de traitement ne s'evaporent pas)
- Floor a 0.0 : quand l'intensite atteint 0.0, la pheromone de tache est effectivement eteinte
- **Fallback lineaire** : si le decay exponentiel pose probleme (ex: debugging), le decay lineaire `-0.05/tick` reste disponible comme option de configuration

Le decay exponentiel est plus fidele au modele biologique (Grasse, 1959) et offre ~10% de performance supplementaire par rapport au decay lineaire (Rodriguez, 2026).

**Inhibition** (Rodriguez, 2026 — periode d'inhibition) :

Champ `γ` (gamma) dans les pheromones de statut, mecanisme anti-oscillation :

```
γ^(t+1) = γ^t × e^(-k_γ)    ou k_γ = 0.08
```

- Quand un fichier passe en `retry` : `γ += 0.5`
- Le Transformer ne reprend un fichier que si `γ < 0.1` (inhibition dissipee)
- Avec `γ₀ = 0.5` et `k_γ = 0.08`, la reprise est possible apres ~20 ticks (`0.5 × e^(-0.08×20) ≈ 0.10`), compatible avec `max_ticks = 50`
- **Justification du calibrage** : avec `k_γ = 0.02` (valeur initiale), il faudrait ~81 ticks pour dissiper l'inhibition — incompatible avec la limite de 50 ticks. La valeur `k_γ = 0.08` garantit qu'un fichier en retry a au moins une chance d'etre retente avant la fin de la boucle
- Cela espace les re-tentatives et evite les oscillations rapides (`retry → pending → transformed → failed → retry`)

### 3.6 Historique et audit trail

Les fichiers JSON courants (`tasks.json`, `status.json`, `quality.json`) contiennent uniquement l'**etat actuel** — chaque entree est ecrasee par file key.

Le fichier `pheromones/audit_log.jsonl` est un log **append-only** au format JSON Lines. Chaque operation d'ecriture dans le pheromone store genere une ligne :

```json
{"timestamp": "2026-02-08T10:05:00Z", "agent": "transformer", "pheromone_type": "status", "file_key": "utils.py", "action": "update", "fields_changed": {"status": "transformed"}, "previous_values": {"status": "in_progress"}}
```

Ce log satisfait **RQ3** (auditabilite complete) et les exigences de tracabilite de l'EU AI Act Art. 14 (Fink, 2025). Il permet de reconstituer l'historique complet de chaque fichier a travers le pipeline.

### 3.7 Machine a etats complete

```
                    ┌─────────┐
         Scout      │ pending │ ◄──────────────┐
                    └────┬────┘                │
                         │ Transformer         │ Validator
                         │ picks up            │ (retry, γ < 0.1)
                    ┌────▼──────┐              │
                    │in_progress│              │
                    └────┬──────┘              │
                         │ Transformer         │
                         │ completes           │
                    ┌────▼───────┐             │
                    │transformed │             │
                    └────┬───────┘             │
                         │ Tester              │
                         │ runs tests          │
                    ┌────▼────┐                │
                    │ tested  │                │
                    └────┬────┘                │
                         │ Validator           │
              ┌──────────┼──────────┬──────────┘
              │          │          │
         ┌────▼─────┐ ┌─▼────────┐ ┌▼───────┐
         │validated │ │needs_    │ │ failed │
         │(terminal)│ │review    │ │        │
         └──────────┘ │(HOTL)    │ └───┬────┘
                      └──────────┘     │ retry_count <= 3
                                       │
                                  ┌────▼───┐
                                  │ retry  │───► pending (avec γ += 0.5)
                                  └────────┘
                                       │ retry_count > 3
                                  ┌────▼───┐
                                  │skipped │
                                  │(terminal)│
                                  └────────┘
```

**Table des transitions** :

| De | Vers | Agent | Condition | Effet sur les pheromones |
|---|---|---|---|---|
| (nouveau) | `pending` | Scout | Fichier .py detecte avec patterns Py2 | Cree tache + statut |
| `pending` | `in_progress` | Transformer | `intensity > 0.2` ET `γ < 0.1` | Scope lock acquis |
| `in_progress` | `transformed` | Transformer | Transformation terminee | Code Py3 ecrit, tokens enregistres |
| `transformed` | `tested` | Tester | Tests executes | Confidence calculee, issues enregistrees |
| `tested` | `validated` | Validator | `confidence >= 0.8` | Git commit, `confidence += 0.1` |
| `tested` | `needs_review` | Validator | `0.5 <= confidence < 0.8` | Log WARNING, attente intervention humaine |
| `tested` | `failed` | Validator | `confidence < 0.5` | Git revert, `confidence -= 0.2` |
| `failed` | `retry` | Validator | `retry_count <= 3` | `retry_count += 1`, scope lock libere |
| `retry` | `pending` | Systeme | Automatique (debut tick suivant) | `γ += 0.5` (inhibition) |
| `failed` | `skipped` | Validator | `retry_count > 3` | Log WARNING, fichier abandonne |

**Notes** :
- `retry_count` ne se remet **jamais** a zero — c'est un compteur monotone par fichier
- `validated` et `skipped` sont des etats **terminaux** — le fichier ne revient jamais dans le pipeline
- `needs_review` est un etat de **pause** — le fichier attend une intervention humaine (voir section 5.1)

**TTL scope lock (prevention des zombies)** : si un fichier reste en `in_progress` pendant plus de `scope_lock_ttl` ticks (defaut : 3) sans mise a jour, le systeme considere l'agent comme mort et remet le fichier en `pending` avec `retry_count += 1`. Cela evite qu'un crash de l'agent Transformer bloque definitivement un fichier. Le TTL est verifie au debut de chaque tick, avant le decay.

---

## 4. Specification des agents

### 4.1 Base Agent (classe abstraite)

Tous les agents partagent le meme cycle :

```python
class BaseAgent(ABC):
    def __init__(self, name: str, config: dict, pheromone_store: PheromoneStore):
        self.name = name
        self.config = config
        self.store = pheromone_store

    @abstractmethod
    def perceive(self) -> dict:
        """Lit les pheromones pertinentes (filtre par type/seuil)"""

    @abstractmethod
    def should_act(self, perception: dict) -> bool:
        """Decide s'il y a du travail a faire (seuil d'activation)"""

    @abstractmethod
    def decide(self, perception: dict) -> Action:
        """Decide quoi faire (appel LLM si necessaire)"""

    @abstractmethod
    def execute(self, action: Action) -> Result:
        """Execute l'action (modifier fichier, lancer test, etc.)"""

    @abstractmethod
    def deposit(self, result: Result) -> None:
        """Depose les traces dans l'environnement"""

    def run(self) -> bool:
        """Cycle complet. Retourne True si l'agent a agi, False sinon (idle)."""
        perception = self.perceive()
        if not self.should_act(perception):
            return False
        action = self.decide(perception)
        result = self.execute(action)
        self.deposit(result)
        return True
```

**Table de permissions de localite** (Heylighen, 2016 — un agent ne percoit que son voisinage local dans le medium ; Ricci et al., 2007 — Agents & Artifacts) :

| Agent | Lit (perceive) | Ecrit (deposit) |
|---|---|---|
| **Scout** | Fichiers `.py` du target_repo, `status.json` (pour savoir quels fichiers sont deja analyses) | `tasks.json`, `status.json` (→ `pending`) |
| **Transformer** | `tasks.json` (tri par intensite decroissante), `quality.json` (few-shot learning stigmergique), `status.json` (fichiers `pending` avec `γ < 0.1`) | Fichiers `.py` transformes dans target_repo, `status.json` (→ `in_progress`, → `transformed`) |
| **Tester** | `status.json` (fichiers `transformed`), fichiers `.py` transformes dans target_repo | `quality.json`, `status.json` (→ `tested`) |
| **Validator** | `quality.json`, `status.json` (fichiers `tested`) | `status.json` (→ `validated` / `failed` / `needs_review` / `retry` / `skipped`), operations Git (commit/revert) |

**Justification** : le Transformer lit `quality.json` = **stigmergie cognitive** (Ricci et al., 2007). Il lit les traces laissees par d'autres agents (Tester, Validator) dans l'environnement pour ajuster sa strategie. Ce n'est pas une communication directe entre agents — c'est une lecture de l'etat de l'environnement, conforme au paradigme Agents & Artifacts.

### 4.2 Scout

| Propriete | Valeur |
|---|---|
| **Lit** | Fichiers `.py` du target_repo, `status.json` |
| **Seuil d'activation** | Fichiers `.py` sans pheromone de tache existante |
| **Action** | Analyse AST/regex + appel LLM pour identifier les patterns Py2 |
| **Depose** | Pheromones de tache (fichier, patterns, priorite) + statut `pending` |
| **Utilise LLM** | Oui — analyse semantique des patterns complexes |

#### 4.2.1 Detection des patterns Python 2

La detection se fait en **deux phases** :

**Phase 1 — Detection deterministe (AST + regex)** : rapide, sans cout LLM.

| # | Pattern | Exemple Py2 | Equivalent Py3 | Detection |
|---|---|---|---|---|
| 1 | `print_statement` | `print "hello"` | `print("hello")` | AST: `ast.Print` node |
| 2 | `print_chevron` | `print >> sys.stderr, "err"` | `print("err", file=sys.stderr)` | AST: `ast.Print` avec `dest` |
| 3 | `dict_iteritems` | `d.iteritems()` | `d.items()` | Regex: `\.iter(items|keys|values)\(\)` |
| 4 | `dict_iterkeys` | `d.iterkeys()` | `d.keys()` | Regex: idem |
| 5 | `dict_itervalues` | `d.itervalues()` | `d.values()` | Regex: idem |
| 6 | `dict_has_key` | `d.has_key(k)` | `k in d` | Regex: `\.has_key\(` |
| 7 | `xrange` | `xrange(10)` | `range(10)` | Regex: `\bxrange\b` |
| 8 | `unicode_literal` | `u"text"` | `"text"` | Regex: `\bu"` / `\bu'` |
| 9 | `long_literal` | `42L` | `42` | Regex: `\d+L\b` |
| 10 | `raise_syntax` | `raise E, msg` | `raise E(msg)` | AST: `ast.Raise` avec 2+ args |
| 11 | `except_syntax` | `except E, e:` | `except E as e:` | Regex: `except\s+\w+\s*,\s*\w+` |
| 12 | `old_division` | `5 / 2  # == 2` | `5 // 2` ou `from __future__` | AST: `ast.Div` (heuristique) |
| 13 | `raw_input` | `raw_input()` | `input()` | Regex: `\braw_input\b` |
| 14 | `apply_builtin` | `apply(f, args)` | `f(*args)` | Regex: `\bapply\(` |
| 15 | `execfile_builtin` | `execfile("f.py")` | `exec(open("f.py").read())` | Regex: `\bexecfile\(` |
| 16 | `string_module` | `string.atoi("42")` | `int("42")` | AST: Import `string` + appels |
| 17 | `urllib_import` | `import urllib2` | `import urllib.request` | AST: `ImportFrom` / `Import` |
| 18 | `metaclass_syntax` | `__metaclass__ = Meta` | `class C(metaclass=Meta)` | AST: attribution `__metaclass__` |
| 19 | `future_imports` | (absent) | `from __future__ import ...` | Absence detectee |

**Note sur le parsing** : le module `ast` de Python 3 ne peut pas parser certaines syntaxes Python 2 (`print "hello"`, `except E, e:`, `raise E, msg`). Pour ces cas, la Phase 1 s'appuie sur les regex. Le Scout doit journaliser la source de detection (`ast` ou `regex`) dans les pheromones de tache pour tracabilite. Si un fichier ne peut etre parse ni par AST ni par regex, le Scout le signale avec un log WARNING et le marque quand meme comme `pending` (le LLM Phase 2 tentera l'analyse).

**Phase 2 — Analyse semantique (LLM)** : pour les cas ambigus que l'AST/regex ne peut pas resoudre (ex: `5 / 2` — division entiere ou flottante ?).

**Dependencies** : detectees via `ast.Import` et `ast.ImportFrom`. Le `dep_count` d'un fichier = nombre de fichiers du projet qu'il importe.

### 4.3 Transformer

| Propriete | Valeur |
|---|---|
| **Lit** | `tasks.json` (tri par intensite decroissante), `quality.json` (few-shot), `status.json` |
| **Seuil d'activation** | `task.intensity > 0.2` ET `status == "pending"` ET `γ < 0.1` |
| **Action** | Appel LLM pour generer le code Python 3 |
| **Depose** | Code transforme + diff + statut `transformed` + tokens consommes |
| **Utilise LLM** | Oui — generation de code |

#### 4.3.1 Apprentissage stigmergique (few-shot dynamique)

Le Transformer construit un prompt dynamique en lisant les traces de l'environnement :

1. **Exemples positifs** : jusqu'a 3 fichiers deja `validated` avec `confidence >= 0.8` et ayant des patterns en commun avec le fichier cible. Inclut le diff (avant/apres) comme few-shot example.
2. **Contexte retry** : si le fichier est en `retry`, le prompt inclut les `issues` du dernier test echoue (depuis `quality.json`) pour guider la correction.
3. **Pas de communication directe** : le Transformer ne "demande" rien au Tester ni au Validator. Il lit uniquement les traces laissees dans l'environnement.

**Justification theorique** : c'est de la **stigmergie cognitive** au sens de Ricci et al. (2007). Les traces deposees par un agent (Tester, Validator) dans l'environnement modifient le comportement d'un autre agent (Transformer) sans communication directe. L'environnement est le medium de coordination.

### 4.4 Tester

| Propriete | Valeur |
|---|---|
| **Lit** | `status.json` (fichiers `transformed`), fichiers `.py` transformes |
| **Seuil d'activation** | Au moins 1 fichier en statut `transformed` |
| **Action** | Execute `pytest` sur le fichier transforme, verifie la syntaxe Python 3 |
| **Depose** | Pheromones de qualite (tests passes/echoues, coverage) + statut `tested` |
| **Utilise LLM** | Non — cet agent est deterministe |

**Test discovery** (voir section 3.3) : cherche `test_{filename}.py`, fallback vers `py_compile` + `python -c "import {module}"`.

**Coverage** : collectee via `pytest --cov={module}` quand des tests existent. Stockee dans `quality.json` mais n'affecte pas le calcul de confidence.

### 4.5 Validator

| Propriete | Valeur |
|---|---|
| **Lit** | `quality.json`, `status.json` (fichiers `tested`) |
| **Seuil d'activation** | Au moins 1 fichier en statut `tested` |
| **Action — Valide** | `confidence >= 0.8` → Git commit + renforcement `confidence += 0.1` + statut `validated` |
| **Action — Rollback** | `confidence < 0.5` → Git revert + evaporation `confidence -= 0.2` + statut `failed` |
| **Action — Escalade** | `0.5 <= confidence < 0.8` → statut `needs_review` + log WARNING |
| **Depose** | Statut final + metriques de decision |
| **Utilise LLM** | Non — decision par seuils |

### 4.6 Client LLM

Classe `LLMClient` dans `stigmergy/llm_client.py`. Interface unifiee pour les appels a OpenRouter.

```python
@dataclass
class LLMResponse:
    content: str           # Reponse texte du LLM
    tokens_used: int       # Tokens consommes (prompt + completion)
    model: str             # Modele utilise
    latency_ms: int        # Temps de reponse

class LLMClient:
    def __init__(self, config: dict):
        self.api_key = os.environ["OPENROUTER_API_KEY"]
        self.model = config["llm"]["model"]
        self.temperature = config["llm"]["temperature"]
        self.max_tokens = config["llm"]["max_response_tokens"]
        self.total_tokens_used = 0
        self.budget = config["llm"]["max_tokens_total"]

    def call(self, prompt: str, system: str = None) -> LLMResponse:
        """Appel LLM avec retry exponentiel et budget check."""

    def check_budget(self, estimated_tokens: int) -> bool:
        """Verifie si le budget restant permet l'appel."""
```

**Comportements** :
- **Retry exponentiel** : 3 tentatives avec backoff `[1s, 2s, 4s]` pour les erreurs 429/500/502/503
- **Parsing** : extrait le code des fences markdown (` ```python ... ``` `) dans la reponse
- **Token counting** : somme prompt_tokens + completion_tokens depuis la reponse API
- **Budget check** : avant chaque appel, verifie `total_tokens_used + estimated_tokens <= budget`. Si depassement → refuse l'appel et retourne une erreur

**Prompt template Scout** :

```
SYSTEM: You are a Python 2 to Python 3 migration analyst. Identify ALL Python 2
patterns in the given file. For each pattern, specify the type, line number, and
the Python 3 equivalent.

USER: Analyze this Python 2 file:
---
{file_content}
---
List each Python 2 pattern found as JSON:
[{"pattern": "...", "line": N, "py2": "...", "py3": "..."}]
```

**Prompt template Transformer** :

```
SYSTEM: You are a Python 2 to Python 3 migration expert. Convert the given file
to Python 3, preserving exact semantics. Return ONLY the complete converted file.

USER: Convert this Python 2 file to Python 3.
Patterns to address: {patterns_from_task_pheromone}

{few_shot_examples_if_available}

{retry_context_if_retry}

Source file:
---
{file_content}
---
Return the complete Python 3 file:
```

### 4.7 Boucle principale

Fichier `stigmergy/loop.py`. Orchestre le round-robin sans superviseur.

**Criteres d'arret** (4 conditions, OR) :
1. **Tous terminaux** : tous les fichiers sont en statut `validated`, `skipped`, ou `needs_review`
2. **Budget epuise** : `total_tokens_used >= max_tokens_total`
3. **Max ticks atteint** : `tick_count >= max_ticks` (defaut: 50)
4. **Idle** : 2 cycles consecutifs ou aucun agent n'a agi (`run()` retourne `False` pour les 4 agents)

**Pseudocode** :

```python
def run_loop(config, repo_path):
    store = PheromoneStore(config)
    agents = [Scout(...), Transformer(...), Tester(...), Validator(...)]
    metrics = MetricsCollector()
    idle_count = 0

    for tick in range(config["max_ticks"]):
        store.apply_decay("tasks")      # Decay exponentiel au debut du tick
        store.apply_decay_inhibition()   # Decay inhibition γ

        any_acted = False
        for agent in agents:
            acted = agent.run()
            any_acted = any_acted or acted
            metrics.record_tick(tick, agent.name, acted)

        if not any_acted:
            idle_count += 1
        else:
            idle_count = 0

        if idle_count >= 2:
            break  # Arret idle

        if all_terminal(store):
            break  # Tous les fichiers traites

        if llm_client.total_tokens_used >= config["max_tokens_total"]:
            break  # Budget epuise

    metrics.export(config["output_dir"])
    return metrics.summary()
```

### 4.8 Operations Git

Le depot Git du target_repo est le medium stigmergique lui-meme — il fait partie de l'environnement.

**Clone** : `git clone --depth 1 {repo_url} target_repo/`

**Branche** : `git checkout -b stigmergic-migration-{timestamp}` au debut de la migration. Toutes les modifications se font sur cette branche.

**Commit** : **seul le Validator** peut committer. Message format : `[stigmergic] Migrate {filename} to Python 3 (confidence={confidence})`.

**Rollback** : `git checkout HEAD -- {filepath}` — restaure la version precedente du fichier sans affecter les autres fichiers.

**Aucun push automatique** : le POC travaille en local uniquement.

### 4.9 Configuration complete (`stigmergy/config.yaml`)

```yaml
# === Pheromones ===
pheromones:
  task_intensity_weights:
    pattern_count: 0.6
    dep_count: 0.4
  task_intensity_clamp: [0.1, 1.0]
  decay_type: "exponential"        # "exponential" ou "linear"
  decay_rate: 0.05                 # ρ pour decay exponentiel
  inhibition_decay_rate: 0.08     # k_γ pour inhibition (calibre pour reprise en ~20 ticks)
  inhibition_threshold: 0.1       # γ max pour reprendre un fichier

# === Seuils agents (normes profondes — Grisold et al., 2025) ===
thresholds:
  transformer_intensity_min: 0.2   # Intensite min pour activer Transformer (abaisse de 0.3 pour eviter la starvation)
  validator_confidence_high: 0.8   # Auto-validate au-dessus
  validator_confidence_low: 0.5    # Auto-rollback en-dessous
  max_retry_count: 3               # Anti-boucle
  scope_lock_ttl: 3                # Ticks max en in_progress avant release (prevention zombies)

# === LLM ===
llm:
  provider: "openrouter"
  model: "qwen/qwen3-235b-a22b-2507"              # Dev model
  temperature: 0.2
  max_response_tokens: 4096
  max_tokens_total: 100000         # Budget plafond
  retry_attempts: 3
  retry_backoff: [1, 2, 4]        # Secondes

# === Boucle ===
loop:
  max_ticks: 50
  idle_cycles_to_stop: 2

# === Git ===
git:
  shallow_clone: true
  branch_prefix: "stigmergic-migration"
  auto_push: false

# === Metriques ===
metrics:
  output_dir: "metrics/output"
  export_format: "csv"             # "csv" ou "json"
  pareto_plot: true
```

**Distinction normes profondes / normes de surface** (Grisold et al., 2025) :
- **Normes profondes** (stables, fixees dans config.yaml par l'humain) : budget tokens, seuils de confiance (0.5/0.8), max retries (3), score minimum d'activation (0.3), decay rates
- **Normes de surface** (emergentes, dans les pheromones) : intensite des taches (evolue avec decay + scan), confidence des fichiers (evolue avec les resultats de test), inhibition γ (evolue avec les retries)

Les normes profondes sont les parametres du systeme. Les normes de surface **emergent** de l'interaction agents-environnement. C'est la distinction cle qui fait de ce systeme une veritable ecologie stigmergique (pas juste un pipeline configurable).

### 4.10 Interface CLI

Point d'entree : `main.py`

```
python main.py --repo <url>                # Migrer un depot Python 2
python main.py --repo <url> --dry-run      # Simulation sans ecriture
python main.py --resume                    # Reprendre une migration interrompue
python main.py --review                    # Traiter les fichiers needs_review
```

**Arguments** :

| Argument | Type | Defaut | Description |
|---|---|---|---|
| `--repo` | str | requis | URL du depot Python 2 a migrer |
| `--config` | str | `stigmergy/config.yaml` | Fichier de configuration |
| `--max-ticks` | int | 50 | Override max ticks |
| `--max-tokens` | int | 100000 | Override budget tokens |
| `--model` | str | `qwen/qwen3-235b-a22b-2507` | Override modele LLM |
| `--output-dir` | str | `metrics/output` | Dossier de sortie metriques |
| `--verbose` | flag | False | Logging DEBUG |
| `--dry-run` | flag | False | Simulation sans ecriture Git |
| `--review` | flag | False | Mode review : traite les fichiers `needs_review` |
| `--resume` | flag | False | Reprend depuis l'etat des pheromones existant |
| `--seed` | int | None | Seed pour reproductibilite |

### 4.11 Variables d'environnement

**Requis** :
- `OPENROUTER_API_KEY` : cle API OpenRouter

**Fichier `.env.example`** :

```
# OpenRouter API key (required)
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

Le fichier `.env` est lu par `python-dotenv` au demarrage. Il est dans `.gitignore` et ne doit jamais etre committe.

---

## 5. Guardrails (contraintes environnementales)

Implementes dans `environment/guardrails.py`. L'agent ne connait pas les regles — c'est l'environnement qui refuse ou accepte (Grisold et al., 2025).

**Taxonomie normes profondes vs normes de surface** (Grisold et al., 2025) :

Les guardrails se repartissent en deux categories fondamentalement differentes :

**Normes profondes** (fixees par l'humain dans config.yaml, stables) :

| Guardrail | Implem. | Ref. theorique |
|---|---|---|
| **Tracabilite** | Chaque ecriture dans pheromone_store est horodatee et signee par l'agent | Art. 14 EU AI Act (Fink, 2025) |
| **Budget tokens** | `if total_tokens > config.max_tokens: terminated = True` | Kapoor et al. (2024) |
| **Anti-boucle** | `if retry_count > 3: status = "skipped"` | Cursor (2025) lecons apprises |
| **Scope lock** | Un seul agent peut modifier un fichier a la fois (verrou) | Cursor (2025) |
| **TTL scope lock** | Si `in_progress` depuis > 3 ticks sans update → retour `pending` + retry | Prevention zombies |
| **Seuils de confiance** | 0.8 (validate), 0.5 (rollback), entre les deux (escalade) | Configurable |
| **Seuil d'activation** | `intensity > 0.2` pour declencher le Transformer | Configurable |

**Normes de surface** (emergentes, dans les pheromones, dynamiques) :

| Norme | Mecanisme | Comportement emergent |
|---|---|---|
| **Intensite des taches** | Decay exponentiel + normalisation | Les fichiers non traites perdent en priorite → auto-priorisation |
| **Confidence des fichiers** | `+0.1` renforcement / `-0.2` evaporation | Les fichiers bien transformes sont valides plus vite → renforcement positif |
| **Inhibition γ** | `+0.5` a chaque retry, decay lent | Les fichiers problematiques sont espaces → anti-oscillation emergente |
| **Rollback automatique** | `confidence < 0.5` → git revert | Les mauvaises transformations sont annulees → auto-correction |

Les normes profondes sont les regles du jeu. Les normes de surface sont les patterns qui emergent du jeu. C'est cette distinction qui fait la difference entre un pipeline configurable et une ecologie stigmergique.

### 5.1 Escalade humaine

Quand un fichier est en statut `needs_review` (`0.5 <= confidence < 0.8`) :

1. La boucle principale **saute** ce fichier (il ne bloque pas les autres)
2. Un log `WARNING` est emis avec les details (fichier, confidence, issues)
3. Le fichier reste en `needs_review` jusqu'a intervention humaine

**Mode review** (`python main.py --review`) :
- Affiche la liste des fichiers en `needs_review` avec leur confidence et issues
- Pour chaque fichier, l'humain peut : valider manuellement, forcer un retry, ou skipper

**MVP** : edition manuelle de `status.json` pour changer le statut. Le mode `--review` est un CLI interactif simple qui facilite cette operation.

### 5.2 Gestion d'erreurs

Deux categories d'erreurs, deux strategies :

**Erreurs fichier** (non-fatales) — le fichier echoue, la boucle continue :

| Scenario | Erreur | Strategie |
|---|---|---|
| Fichier illisible | `IOError` | Scout: skip fichier, log WARNING |
| AST parse impossible | `SyntaxError` | Scout: analyse regex uniquement |
| LLM retourne code invalide | Parse error | Transformer: status → `failed` |
| LLM timeout | `TimeoutError` | Retry exponentiel (3 tentatives) |
| pytest crash | `subprocess.CalledProcessError` | Tester: confidence = 0.0, issues logged |
| Git conflict | `GitCommandError` | Validator: revert, status → `failed` |
| Budget insuffisant pour un fichier | Budget check | Skip fichier, log WARNING |

**Erreurs systeme** (fatales) — sauvegarde et arret :

| Scenario | Erreur | Strategie |
|---|---|---|
| API key invalide | `401 Unauthorized` | Arret immediat, message clair |
| Budget global epuise | Budget check | Arret propre, export metriques |
| Fichier JSON corrompu | `JSONDecodeError` | Tentative de recovery, sinon arret |
| Disk full | `OSError` | Arret propre, log erreur |

Dans tous les cas : l'etat des pheromones est sauvegarde avant l'arret (les JSON sont toujours dans un etat coherent grace au file locking).

### 5.3 Journalisation

Deux flux de logs distincts :

**1. Log operationnel** (Python `logging` standard) :
- Niveau `INFO` par defaut, `DEBUG` avec `--verbose`
- Format : `{timestamp} {level} [{agent}] {message}`
- Sortie : stdout + fichier rotatif `logs/stigmergic.log`
- Contenu : activite des agents, decisions, erreurs, metriques par tick

**2. Audit trail** (JSONL append-only) :
- Fichier : `pheromones/audit_log.jsonl`
- Contenu : chaque modification de pheromone avec agent, timestamp, valeurs avant/apres
- Usage : satisfait RQ3 (auditabilite EU AI Act Art. 14)
- Immutable : append-only, jamais modifie ni tronque pendant une migration

---

## 6. Metriques et evaluation

### 6.1 Strategie de tests

**Tests unitaires** (9 tests, mocks pour le LLM) :

| Test | Module | Ce qu'il verifie |
|---|---|---|
| `test_pheromone_read_write` | `pheromone_store` | CRUD basique |
| `test_pheromone_locking` | `pheromone_store` | File locking fonctionne |
| `test_decay_exponential` | `decay` | Formule exponentielle correcte |
| `test_decay_inhibition` | `decay` | Inhibition γ fonctionne |
| `test_normalisation` | `scout` | Normalisation min-max correcte |
| `test_scout_patterns` | `scout` | Detection des 19 patterns Py2 |
| `test_transformer_prompt` | `transformer` | Prompt few-shot construit correctement |
| `test_guardrails` | `guardrails` | Chaque guardrail accepte/refuse correctement |
| `test_state_transitions` | `status` | Machine a etats respectee |

**Tests d'integration** (4 tests, avec pheromone store reel) :

| Test | Ce qu'il verifie |
|---|---|
| `test_scout_to_transformer` | Scout depose → Transformer lit et transforme |
| `test_transformer_to_tester` | Transformer depose → Tester lit et teste |
| `test_tester_to_validator` | Tester depose → Validator valide/rollback |
| `test_full_cycle` | 1 fichier simple passe de `pending` a `validated` |

**Test E2E** (1 test, vrais appels API) :

| Test | Ce qu'il verifie |
|---|---|
| `test_e2e_small_repo` | Migration complete du depot synthetique (section 8.1) |

### 6.2 Metriques collectees a chaque tick

| Metrique | Type | Objectif |
|---|---|---|
| `files_migrated` | Compteur | Progression |
| `files_validated` | Compteur | Taux de succes |
| `files_failed` | Compteur | Taux d'echec |
| `files_needs_review` | Compteur | Escalade humaine |
| `total_tokens` | Compteur | Cout |
| `total_ticks` | Compteur | Temps |
| `tokens_per_file` | Ratio | Efficacite |
| `success_rate` | Ratio | `validated / total` |
| `rollback_rate` | Ratio | `failed / (validated + failed)` |
| `human_escalation_rate` | Ratio | `needs_review / total` |
| `retry_resolution_rate` | Ratio | `retry_then_validated / retry_total` (efficacite des retries) |
| `starvation_count` | Compteur | Fichiers avec `idle_ticks > 12` sans traitement (indicateur de famine) |
| `audit_completeness` | Ratio | `events_with_full_trace / total_events` (qualite du trail RQ3) |

### 6.3 Comparaisons (baselines)

| Configuration | Description | Ce qu'on mesure |
|---|---|---|
| **Stigmergique (4 agents)** | Architecture complete du POC | Performance de reference |
| **Single-agent** | 1 seul agent fait scan + transform + test + validate | Est-ce que la coordination apporte quelque chose ? |
| **Sequentiel (Agentless-like)** | Pipeline fixe sans pheromones : scan → transform → test → validate | Surcout de la stigmergie vs pipeline simple |

**Contraintes d'equite** (Kapoor et al., 2024 ; Gao et al., 2025) :

Pour que les comparaisons soient scientifiquement valides, toutes les configurations doivent respecter :

- **Meme modele LLM** : qwen/qwen3-235b-a22b-2507 (dev) ou modele frontiere (resultats), identique pour toutes les configs
- **Meme temperature** : 0.2 pour toutes les configurations
- **Memes prompt templates** : adaptes au format single-agent mais meme contenu semantique
- **Memes guardrails** : budget tokens identique, max retries identique
- **Meme depot de test** : synthetique (section 8.1) puis reel, identique pour toutes les configs
- **>= 5 runs** par configuration pour capturer la variabilite stochastique (Kapoor et al., 2024)
- **Intervalles de confiance** sur toutes les metriques (pas juste des moyennes)
- **Seed fixe** optionnel pour la reproductibilite

### 6.4 Format des metriques

**CSV par tick** : `metrics/output/run_{id}_ticks.csv` — une ligne par tick avec toutes les metriques

**JSON summary** : `metrics/output/run_{id}_summary.json` — metriques finales agregees

**Pareto plot** : `metrics/output/pareto.png` — graphique cout (tokens) vs qualite (success_rate) avec :
- Un point par run (pas juste la moyenne)
- Barres d'erreur (intervalles de confiance 95%)
- Frontiere de Pareto tracee
- Legende : couleur par configuration (stigmergique, single-agent, sequentiel)

### 6.5 Run manifest (reproductibilite)

Chaque run exporte automatiquement un fichier `metrics/output/run_{id}_manifest.json` contenant toutes les informations necessaires pour reproduire l'experience :

```json
{
  "run_id": "stigmergic_001",
  "timestamp_utc": "2026-02-15T14:30:00Z",
  "target_repo_commit": "abc123",
  "config_hash": "sha256:...",
  "prompt_bundle_hash": "sha256:...",
  "model_provider": "openrouter",
  "model_name": "qwen/qwen3-235b-a22b-2507",
  "seed": 42,
  "python_version": "3.11.5",
  "dependency_lock_hash": "sha256:..."
}
```

Ce manifest permet de verifier que deux runs comparees utilisent bien la meme configuration. Il est exporte en debut de run (avant le premier tick).

### 6.6 Analyse Pareto cout-precision

Pour chaque configuration : plot `(cout en tokens, taux de succes)` → identifier la frontiere de Pareto (Kapoor et al., 2024). Si stigmergique est sur la frontiere ou la domine, le mecanisme est justifie.

---

## 7. Plan de sprints

### Sprint 1 — Environnement (3 jours)

**Objectif** : le medium stigmergique fonctionne independamment des agents.

- [ ] `pheromone_store.py` : CRUD JSON (read, write, query par filtre) + file locking
- [ ] `decay.py` : mecanisme d'evaporation exponentiel + inhibition
- [ ] `guardrails.py` : verifications basiques (budget, anti-boucle, scope lock, tracabilite)
- [ ] `config.yaml` : parametres initiaux complets (section 4.9)
- [ ] `tests/test_pheromone_store.py` : tests unitaires du store
- [ ] `tests/test_guardrails.py` : tests des contraintes
- [ ] `.gitignore`, `.env.example`, `requirements.txt` (section 12.1)

**Livrable** : un store de pheromones testable avec `pytest`, decay fonctionnel, guardrails actifs.

### Sprint 2 — Agents unitaires (4 jours)

**Objectif** : chaque agent fonctionne isolement avec l'environnement.

- [ ] `llm_client.py` : client OpenRouter (qwen/qwen3-235b-a22b-2507) avec retry exponentiel et token counting
- [ ] `base_agent.py` : classe abstraite avec le cycle perceive → should_act → decide → execute → deposit
- [ ] `scout.py` : scan d'un fichier Py2 (19 patterns), depot de pheromones de tache (normalisation min-max)
- [ ] `transformer.py` : lecture pheromone de tache, generation Py3 avec few-shot stigmergique, depot du resultat
- [ ] `tester.py` : detection de `transformed`, execution pytest, depot de qualite (confidence initiale, coverage)
- [ ] `validator.py` : lecture qualite, commit/rollback/escalade
- [ ] Creer le depot synthetique Python 2 de test (section 8.1)
- [ ] Tests unitaires de chaque agent en isolation

**Livrable** : chaque agent peut tourner seul sur 1 fichier et deposer ses traces correctement.

### Sprint 3 — Boucle complete + metriques (3 jours)

**Objectif** : les 4 agents tournent ensemble, coordonnes uniquement par les pheromones.

- [ ] `loop.py` : boucle round-robin avec 4 criteres d'arret
- [ ] `main.py` : point d'entree CLI complet (section 4.10)
- [ ] `collector.py` : enregistrement metriques a chaque tick
- [ ] `export.py` : export CSV/JSON des resultats
- [ ] Premier run complet sur le depot synthetique
- [ ] Debug des interactions emergentes (boucles infinies, agents inactifs, conflits)
- [ ] Ajustement des seuils et du decay_rate

**Livrable** : un POC qui migre un petit depot Py2→Py3 de bout en bout, avec logs et metriques exportables.

### Sprint 4 — Baselines + analyse (3 jours)

**Objectif** : comparer stigmergique vs alternatives.

- [ ] `baselines/single_agent.py` : meme tache, 1 agent
- [ ] `baselines/sequential.py` : pipeline fixe sans pheromones
- [ ] Runs multiples (>= 5) pour chaque configuration (variabilite stochastique)
- [ ] `pareto.py` : generation du graphique Pareto cout-precision avec barres d'erreur
- [ ] Analyse des traces de pheromones : quels patterns emergent ?
- [ ] Redaction des resultats quantitatifs

**Livrable** : tableau comparatif des 3 configurations, graphique Pareto, analyse des mecanismes stigmergiques observes.

### Sprint 5 — Robustesse + scale (3 jours, optionnel)

**Objectif** : tester la robustesse et preparer le switch vers un modele frontiere.

- [ ] Test sur un 2e depot plus gros (~50-100 fichiers)
- [ ] Test avec un modele frontiere (Claude Sonnet / GPT-4o via OpenRouter)
- [ ] Comparaison qwen/qwen3-235b-a22b-2507 vs modele frontiere (qualite, cout, comportement emergent)
- [ ] Test de resilience : que se passe-t-il si un agent echoue ? si l'API timeout ?
- [ ] Documentation finale du POC

**Livrable** : resultats a echelle plus realiste, donnees pretes pour la section resultats du memoire.

---

## 8. Depots Python 2 candidats pour les tests

| Depot | Taille | Interet |
|---|---|---|
| **python/mypy** (anciennes versions) | Moyen | Bien documente, tests existants |
| **Un micro-projet GitHub "Python 2 only"** | Petit | Controlable, rapide a iterer |
| **six library test suite** | Petit | Cas d'usage direct Py2/Py3 |
| **Depot synthetique** (recommande) | ~15 fichiers | Couverture controlee de tous les patterns Py2 |

**Recommandation** : commencer par le depot synthetique maitrise (Sprint 2), puis passer a un vrai depot open source (Sprint 4-5).

### 8.1 Depot synthetique

Un depot Python 2 cree sur mesure pour couvrir les 19 patterns de la section 4.2.1.

**Structure** (~15 fichiers) :

```
synthetic_py2_repo/
├── main.py              # print statements, raw_input, xrange
├── utils.py             # dict.iteritems/iterkeys/itervalues, has_key
├── io_handler.py        # print >> stderr, unicode literals
├── math_ops.py          # old division, long literals
├── exceptions.py        # raise E, msg + except E, e syntax
├── compat.py            # future imports absents, apply()
├── file_ops.py          # execfile()
├── string_utils.py      # string module usage
├── network.py           # urllib2 imports
├── meta.py              # __metaclass__ syntax
├── config.py            # Dependance importee par d'autres
├── helpers.py           # Dependance importee par d'autres
├── models.py            # Combinaison de plusieurs patterns
├── cli.py               # raw_input + print statements
├── data_processor.py    # Combinaison complexe (>5 patterns)
├── tests/
│   ├── test_utils.py
│   ├── test_math_ops.py
│   ├── test_string_utils.py
│   ├── test_exceptions.py
│   └── test_io_handler.py
└── README.md
```

**Objectif** : chaque pattern est present dans au moins 2 fichiers. Les 5 fichiers de test couvrent les modules critiques. Cible : >= 80% des fichiers doivent atteindre `validated` apres migration.

**Matrice de couverture des patterns** :

| Pattern | main | utils | io_handler | math_ops | exceptions | compat | file_ops | string_utils | network | meta | models | cli | data_proc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1. print_statement | x | | x | | | | | | | | x | x | |
| 2. print_chevron | | | x | | | | | | | | | | x |
| 3. dict_iteritems | | x | | | | | | | | | x | | x |
| 4. dict_iterkeys | | x | | | | | | | | | | | x |
| 5. dict_itervalues | | x | | | | | | | | | x | | |
| 6. dict_has_key | | x | | | | | | | | | | | x |
| 7. xrange | x | | | | | | | | | | x | | x |
| 8. unicode_literal | | | x | | | | | x | | | | | x |
| 9. long_literal | | | | x | | | | | | | x | | |
| 10. raise_syntax | | | | | x | | | | | | | | x |
| 11. except_syntax | | | | | x | | | | x | | | | x |
| 12. old_division | | | | x | | | | | | | | | x |
| 13. raw_input | x | | | | | | | | | | | x | |
| 14. apply_builtin | | | | | | x | | | | | | | x |
| 15. execfile_builtin | | | | | | | x | | | | | | x |
| 16. string_module | | | | | | | | x | | | x | | |
| 17. urllib_import | | | | | | | | | x | | | | x |
| 18. metaclass_syntax | | | | | | | | | | x | x | | |
| 19. future_imports | | | | | | x | | | | | | | x |

Chaque pattern apparait dans 2-4 fichiers. `data_processor.py` et `models.py` concentrent les combinaisons multi-patterns.

---

## 9. Stack technique

| Composant | Choix | Justification |
|---|---|---|
| **Langage** | Python 3.11+ | Ecosysteme naturel pour le sujet |
| **LLM Provider** | OpenRouter | Flexibilite de modele (gratuit → payant) |
| **LLM Phase dev** | qwen/qwen3-235b-a22b-2507 | Gratuit, suffisant pour valider l'architecture |
| **LLM Phase resultats** | Claude Sonnet / GPT-4o | Resultats publiables |
| **Store pheromones** | Fichiers JSON locaux | Simple, versionnable, inspectable |
| **Tests** | pytest + pytest-cov | Standard Python, output parsable |
| **Versioning** | Git (local) | Le medium stigmergique lui-meme |
| **Config** | YAML | Lisible, modifiable sans code |
| **Metriques** | CSV + matplotlib | Graphiques Pareto pour le memoire |
| **Env vars** | python-dotenv | Gestion securisee des cles API |

---

## 10. Risques identifies et mitigations

| Risque | Probabilite | Impact | Mitigation |
|---|---|---|---|
| qwen/qwen3-235b-a22b-2507 trop faible pour generer du code correct | Haute | Moyen | Valider l'archi d'abord, switcher de modele pour les resultats |
| Boucle infinie (agent retry sans fin) | Moyenne | Haut | Anti-boucle (max 3 retries) + inhibition γ + budget tokens |
| Conflits Git entre agents | Moyenne | Moyen | Scope lock (1 agent par fichier) |
| Latence API degradant l'experience | Moyenne | Faible | Round-robin sequentiel suffit, async optionnel |
| Cout API explosif en phase resultats | Moyenne | Haut | Budget plafond configurable + mesure des Sprint 3 |
| Resultats non significatifs (stigmergie ≈ sequentiel) | Moyenne | Haut | C'est un resultat en soi — le memoire doit discuter honnetement les conditions ou la stigmergie apporte ou non de la valeur |
| Oscillations retry rapides | Moyenne | Moyen | Inhibition γ (Rodriguez, 2026) espace les re-tentatives |

---

## 11. Liens avec le memoire

| Section du memoire | Ce que le POC alimente |
|---|---|
| **RQ1 (Mecanisme)** | Types de pheromones, regles locales, patterns emergents observes |
| **RQ2 (Performance)** | Tableau comparatif, Pareto cout-precision, taux de succes |
| **RQ3 (Gouvernance)** | Logs d'auditabilite (audit_log.jsonl), guardrails en action, escalade humaine |
| **Entretiens** | Le POC sert de demo lors des entretiens semi-directifs |
| **Cadre conceptuel** | Validation empirique des 3 piliers (conceptuel, managerial, technique) |

---

## 12. Checklist avant de coder

- [ ] Creer le repo GitHub `stigmergic-poc`
- [ ] Initialiser l'environnement Python (`requirements.txt`)
- [ ] Configurer `.env` avec la cle API OpenRouter
- [ ] Verifier que qwen/qwen3-235b-a22b-2507 fonctionne sur un prompt simple de migration
- [ ] Preparer le depot synthetique Python 2 de test (section 8.1)
- [ ] Relire les sections 2, 3 et 9 de la revue pour ancrer les choix de design

### 12.1 Fichiers d'infrastructure

**`.gitignore`** :

```
# Environment
.env
__pycache__/
*.pyc
*.pyo

# IDE
.vscode/
.idea/

# Runtime
target_repo/
pheromones/*.json
pheromones/audit_log.jsonl
logs/

# Metrics output
metrics/output/

# OS
.DS_Store
Thumbs.db
```

**`.env.example`** :

```
# OpenRouter API key (required)
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

**`requirements.txt`** :

```
# LLM
openai>=1.12.0           # OpenRouter compatible client
python-dotenv>=1.0.0

# Testing
pytest>=8.0.0
pytest-cov>=4.1.0

# Config
pyyaml>=6.0.1

# Git
gitpython>=3.1.40

# Metrics
matplotlib>=3.8.0
pandas>=2.1.0

# Code analysis
asttokens>=2.4.0
```

---

## References scientifiques integrees dans la spec

| Reference | Concept integre | Section(s) |
|---|---|---|
| Grasse (1959) | Stigmergie biologique, boucle action→trace→stimulus | 1.1, 3.5 |
| Ricci et al. (2007) | Agents & Artifacts, stigmergie cognitive, proprietes artefacts | 3.4, 4.1, 4.3.1 |
| Heylighen (2016) | Definition formelle, localite, types de stigmergie | 4.1 (localite) |
| Rodriguez (2026) | Decay exponentiel, inhibition, convergence Theorem 5.1 | 3.5 |
| Xia et al. (2024) | Agentless baseline (localize→repair→validate) | 6.3 |
| Kapoor et al. (2024) | Pareto cout-qualite, >=5 runs, intervalles de confiance | 6.3, 6.5 |
| Gao et al. (2025) | Defauts node/edge/path dans MAS, equite baselines | 6.3 |
| Grisold et al. (2025) | Normes profondes vs surface, guardrails environnementaux | 4.9, 5 |
| Fink (2025) / EU AI Act Art. 14 | Tracabilite, audit trail | 3.6, 5.3 |
| Santoni de Sio & van den Hoven (2018) | Tracking + tracing pour la gouvernance | 1.2 |

---

*Ce plan est un document vivant — a mettre a jour au fil des sprints.*
