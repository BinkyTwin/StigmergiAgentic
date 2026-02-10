# Patch POC Stigmergique — Synthèse experte + plan d’implémentation

## 1) Résumé exécutif

Le plan actuel est solide (alignement RQ, architecture stigmergique, gouvernance, baselines), mais plusieurs points techniques peuvent être challengés par un jury/expert.  
L’objectif de ce patch est de **sécuriser la crédibilité scientifique** et **fiabiliser l’exécution du POC** sans refonte majeure.

---

## 2) Ce qui est déjà bon (à conserver)

1. **Cohérence globale** entre problématique, architecture et protocole d’évaluation.  
2. **Approche gouvernance-by-design** (audit trail, guardrails, escalade humaine).  
3. **Comparaison structurée** (single-agent / séquentiel / stigmergique) avec logique d’équité.  
4. **Plan de delivery** en sprints avec logique incrémentale.

---

## 3) Points critiques à corriger avant implémentation finale

## 3.1 Boucle retry trop lente (bloquant)

Avec les paramètres actuels:
- incrément retry: `γ += 0.5`
- reprise si: `γ < 0.1`
- decay inhibition: `k_γ = 0.02`
- max ticks: `50`

Formule:
\[
\gamma_t = 0.5 \cdot e^{-0.02t}
\]
On veut `γ_t < 0.1` :
\[
0.5e^{-0.02t}<0.1 \Rightarrow t > \ln(5)/0.02 \approx 80.45
\]
=> Il faut ~81 ticks pour réessayer, mais la boucle s’arrête à 50 ticks.  
**Conséquence:** de nombreux fichiers `retry` ne sont jamais retraités.

---

## 3.2 Risque de starvation (famine) des tâches moyennes

Si `transformer_intensity_min = 0.3` et decay exponentiel `ρ = 0.05`, un item à 0.30 devient:
\[
0.30 \cdot e^{-0.05} \approx 0.285
\]
=> passe sous seuil en 1 tick si non pris immédiatement.  
**Conséquence:** certaines tâches restent bloquées trop longtemps.

---

## 3.3 Parsing Py2 ambigu

Si la détection s’appuie implicitement sur `ast` Python 3, le parsing de vrai code Python 2 peut être instable/incomplet.  
**Conséquence:** détection incorrecte de patterns (`print`, `xrange`, `raw_input`, exceptions, etc.).

---

## 3.4 Métriques de “succès” à clarifier

- `needs_review` peut gonfler artificiellement la perception de complétion.
- `confidence = 0.5` sans tests peut être trop optimiste selon les cas.

---

## 3.5 Revendication scientifique trop affirmative

Remplacer les formulations de type “première étude empirique…” par “**À notre connaissance**…”.

---

## 3.6 Planning un peu optimiste

Ajouter un **buffer risque** (intégration + calibrage + reproductibilité).

---

## 4) Modifications techniques proposées (prêtes à coder)

## 4.1 Config v2 recommandée

```yaml
scheduler:
  max_ticks: 50
  selection_policy: "score_max"

activation:
  transformer_intensity_min: 0.20
  intensity_decay_rho: 0.03
  decay_after_idle_ticks: 3

inhibition:
  gamma_retry_increment: 0.40
  gamma_resume_threshold: 0.10
  gamma_decay_k: 0.08

fairness:
  aging_boost_per_tick: 0.01
  aging_boost_cap: 0.08
  max_idle_ticks_warning: 12

retries:
  max_retries_per_file: 3
  backoff_mode: "stigmergic"

confidence:
  no_tests_base_confidence: 0.35
  static_checks_weight: 0.35
  transform_rationale_weight: 0.20
  prior_pass_history_weight: 0.10
```

**Pourquoi ces valeurs :**
- Avec `k=0.08` et `γ0=0.4`, reprise typique en ~17 ticks pour seuil 0.1 (compatible `max_ticks=50`).
- Seuil d’activation abaissé + decay retardé => moins de starvation.

---

## 4.2 Scoring de sélection anti-starvation (pseudo-code)

```python
def effective_score(item, now_tick):
    base = item.intensity
    aging = min(AGING_BOOST_CAP, AGING_BOOST_PER_TICK * item.idle_ticks)
    inhibition_penalty = item.gamma
    jitter = small_random_noise()  # tie-break
    return base + aging - inhibition_penalty + jitter

def should_decay_intensity(item):
    return item.idle_ticks >= DECAY_AFTER_IDLE_TICKS

def on_tick(items):
    for item in items:
        if should_decay_intensity(item):
            item.intensity *= exp(-RHO)
        item.gamma *= exp(-K_GAMMA)

    eligible = [i for i in items if i.intensity >= INTENSITY_MIN and i.state == "pending"]
    if eligible:
        target = max(eligible, key=lambda x: effective_score(x, now_tick=current_tick()))
        dispatch(target)
```

---

## 4.3 Machine à états explicite (recommandé)

```text
pending -> processing
processing -> validated | retry | needs_review | failed

retry -> pending   (si gamma < threshold ET retries < max_retries)
retry -> failed    (si retries >= max_retries)

needs_review -> validated | failed   (décision humaine)
```

---

## 4.4 Pipeline parsing Py2 robuste

1. Parser principal compatible Py2 (ex: `fissix` / équivalent).
2. Détection pattern par arbre syntaxique (prioritaire).
3. Fallback regex contrôlé (si parse error).
4. Journalisation de la source de détection (`ast|regex`) dans l’audit.

### Patterns minimum à couvrir
- `print ...`
- `xrange(...)`
- `raw_input(...)`
- `dict.iteritems()/iterkeys()/itervalues()`
- `except Exception, e:`
- `long`, `unicode`, `basestring`
- imports déplacés Python 3 (`urllib`, etc. selon scope)

---

## 4.5 Métriques v2 (à ajouter)

## KPI principaux
- `success_rate = validated / total_files`
- `cost_efficiency = validated / total_tokens`
- `median_latency_per_file`
- `retry_resolution_rate = retry_then_validated / retry_total`

## KPI gouvernance
- `needs_review_rate = needs_review / total_files`
- `human_time_per_review_file`
- `audit_completeness = events_with_full_trace / total_events`

## KPI qualité technique
- `tests_pass_delta`
- `coverage_delta` (si dispo)
- `post_validation_reopen_rate` (régressions tardives)

## KPI robustesse coordination
- `deadlock_incidents`
- `max_idle_ticks_distribution`
- `starvation_count` (idle_ticks > threshold)

---

## 4.6 Reproductibilité (obligatoire)

À exporter automatiquement par run:

```json
{
  "run_id": "...",
  "timestamp_utc": "...",
  "target_repo_commit": "...",
  "config_hash": "...",
  "prompt_bundle_hash": "...",
  "model_provider": "...",
  "model_name": "...",
  "model_version_or_date": "...",
  "seed": 12345,
  "python_version": "...",
  "dependency_lock_hash": "...",
  "dataset_split_id": "..."
}
```

---

## 5) Renforcement protocole expérimental

## 5.1 Matrice d’ablation (minimum)

| Variante | Decay | Inhibition | Aging boost | Scope lock | Escalade humaine |
|---|---:|---:|---:|---:|---:|
| Full | ON | ON | ON | ON | ON |
| A1 | ON | OFF | ON | ON | ON |
| A2 | ON | ON | OFF | ON | ON |
| A3 | ON | ON | ON | OFF | ON |
| A4 | ON | ON | ON | ON | OFF |

## 5.2 Runs
- Cible: `>=10 runs` par condition (ou au moins 5 si contrainte forte, mais le signal statistique est plus faible).
- Rapporter: moyenne, médiane, IC95%, distribution des outliers.

## 5.3 Comparabilité baselines
Ajouter explicitement:
- **Single-agent + mêmes guardrails**  
- **Séquentiel strict no-feedback**

Objectif: isoler l’apport de la coordination stigmergique.

---

## 6) Ajustements rédactionnels (section mémoire)

## 6.1 Claim de nouveauté
Remplacer:
> “Cette recherche constitue la première étude empirique…”

Par:
> “À notre connaissance, il existe peu d’évaluations empiriques systématiques de ce mécanisme dans ce périmètre précis…”

## 6.2 Menaces à la validité (structure attendue)
- **Interne:** biais prompts, seuils, stratégie retry.  
- **Externe:** taille/variété des dépôts.  
- **Construction:** proxy de confiance, qualité mesurée indirectement.  
- **Conclusion:** stochasticité LLM, dépendance fournisseur.

---

## 7) Plan projet ajusté (réaliste)

- Sprint 1: Instrumentation + machine à états + audit
- Sprint 2: Scheduler v2 (anti-starvation + retry calibré)
- Sprint 3: Parsing Py2 robuste + transformations cœur
- Sprint 4: Baselines + protocole comparatif
- Sprint 5: Ablations + stats + reproductibilité + buffer risques

---

## 8) Definition of Done (DoD)

- [ ] Un item `retry` peut être retraité avant 50 ticks dans >95% des cas simulés.  
- [ ] Aucun item `pending` n’a `idle_ticks > 12` sans alerte.  
- [ ] Parsing Py2 couvre les fixtures prévues et logge `ast|regex`.  
- [ ] Rapport run inclut config/model/prompt/seed/commit hash.  
- [ ] Dashboard métriques v2 disponible par run et global.  
- [ ] Baselines comparables exécutées avec mêmes contraintes.  
- [ ] Ablation matrix complétée et interprétée.

---

## 9) Prompt prêt à coller à une IA de codage

```text
Tu vas patcher mon POC multi-agent stigmergique selon les spécifications suivantes:

1) Corrige la dynamique retry:
- gamma_retry_increment=0.40
- gamma_resume_threshold=0.10
- gamma_decay_k=0.08
- max_retries_per_file=3
- max_ticks=50 maintenu
But: un item retry doit redevenir éligible en <50 ticks.

2) Implémente anti-starvation:
- transformer_intensity_min=0.20
- intensity_decay_rho=0.03
- decay_after_idle_ticks=3
- aging_boost_per_tick=0.01 cap=0.08
Score de dispatch = intensity + aging_boost - gamma + jitter.

3) Formalise une machine à états:
pending -> processing -> {validated,retry,needs_review,failed}
retry -> pending (si gamma<threshold et retries<max_retries) sinon failed

4) Renforce parsing Py2:
- parser compatible Py2 en priorité
- fallback regex si parse error
- journaliser source de détection (ast|regex)

5) Ajoute métriques v2:
success_rate, cost_efficiency, retry_resolution_rate,
needs_review_rate, audit_completeness,
tests_pass_delta, coverage_delta, post_validation_reopen_rate,
deadlock_incidents, starvation_count.

6) Reproductibilité:
Exporter manifest JSON par run avec:
run_id, timestamp_utc, repo_commit, config_hash, prompt_hash,
provider/model/version, seed, python_version, dependency_lock_hash, dataset_split_id.

7) Expérimentation:
- Ajouter baselines single-agent+guardrails et séquentiel strict no-feedback
- Ajouter matrice d’ablation (4 variantes mini)
- Générer stats: moyenne, médiane, IC95%

8) Tests d’acceptation:
- test_retry_reactivation_before_50_ticks
- test_no_starvation_over_threshold
- test_py2_pattern_detection_with_fallback
- test_run_manifest_completeness
- test_metrics_export_integrity

Livrables:
- code patché
- fichier de config v2
- tests unitaires/intégration
- script d’évaluation
- exemple de rapport run (JSON + markdown)
```
