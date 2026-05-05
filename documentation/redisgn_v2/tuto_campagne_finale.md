# Tutoriel — Campagne scientifique finale (V10, 2026-04-23)

Nouveau protocole post-analyse V9 :

- **Adapt** sur `train[0:45]` du split officiel TravelPlanner (plus de contamination train/test).
- **Eval** sur `validation[0:180]` complet (comparable directement à SwarmAgentic, MetaGPT, TravelPlanner officiel).
- `skills.db` et `protocols.db` réellement actifs en phase adapt (écriture), read-only en C3.
- `delivery_rate` corrigé côté agrégation (plus de faux positifs "No travel plan generated").
- `CLEAN_RESULTS=true` par défaut : chaque campagne repart de zéro.

Tous les blocs sont copiables d'un seul coup. **Ne découpe pas les blocs.**

---

## 🚀 LANCE TOUT MAINTENANT

```bash
set -a; source .env; set +a
export OPENROUTER_API_KEY_2=$(grep ^OPENROUTER_API_KEY .env.key2 | head -1 | cut -d= -f2)
echo "Keys: OR=${#OPENROUTER_API_KEY} OR2=${#OPENROUTER_API_KEY_2} DS=${#DEEPSEEK_API_KEY}"
docker compose -f docker-compose.campaign.yml up -d gemma-baselines deepseek-stigmergie gemma-stigmergie
docker compose -f docker-compose.campaign.yml ps
```

Attendu :

- `Keys: OR=73 OR2=73 DS=35` (longueurs non nulles).
- 3 containers `Up` dans le `ps`.

---

## 📊 SUIVRE LA PROGRESSION

```bash
echo "=== GEMMA-STIGMERGIE ==="
echo "  adapt train:      $(ls campaign_results/gemma-stigmergie/adapt/*.json 2>/dev/null | wc -l) / 45"
echo "  c3 validation:    $(ls campaign_results/gemma-stigmergie/c3/*.json 2>/dev/null | wc -l) / 180"
echo "=== DEEPSEEK-STIGMERGIE ==="
echo "  adapt train:      $(ls campaign_results/deepseek-stigmergie/adapt/*.json 2>/dev/null | wc -l) / 45"
echo "  c3 validation:    $(ls campaign_results/deepseek-stigmergie/c3/*.json 2>/dev/null | wc -l) / 180"
echo "=== GEMMA-BASELINES ==="
for fw in solo_direct solo_cot solo_self_refine planner_executor metagpt_sequential langgraph_supervisor; do
    n=$(ls campaign_results/gemma-baselines/$fw/*.json 2>/dev/null | wc -l)
    printf "  %-22s %s / 180\n" "$fw" "$n"
done
```

Logs en direct :

```bash
docker compose -f docker-compose.campaign.yml logs -f --tail=50
```

`Ctrl+C` stoppe seulement le stream, pas les containers.

---

## 🛑 ARRÊTER TOUT

```bash
docker compose -f docker-compose.campaign.yml down
```

---

## 📈 AGRÉGATION APRÈS CAMPAGNE

```bash
uv run python scripts/aggregate_campaign_comparison.py --gemma campaign_results/gemma-stigmergie --deepseek campaign_results/deepseek-stigmergie --baselines campaign_results/gemma-baselines --qwen-fixture output/travelplanner_framework_compare/v6c_retry_20260420_seed42/v6_C/seed42/benchmark_summary.json
```

Produit `output/final_campaign/` :

- `per_query_summary.csv` — 1 ligne par (model, framework, query_idx), avec `official_delivered` et `artifact_delivered` séparés.
- `matrix_A.csv` — effet orchestration (Gemma constant, 7 frameworks).
- `matrix_B.csv` — effet modèle (stigmergie C3 constante, Qwen 23.9 % + Gemma + DeepSeek).
- `aggregates.json` — agrégats + tests McNemar appariés.

---

## ⚙️ CE QUI A CHANGÉ VS V9

| Aspect | V9 (abandonnée) | V10 (actuelle) |
| --- | --- | --- |
| Split adapt | validation[0:90] | **train[0:45]** |
| Split eval | validation[90:180] | **validation[0:180]** |
| Contamination train/test | Oui (même split) | Non (splits officiels disjoints) |
| `skills.db` écrit | Non (cross_run off en adapt) | **Oui** (cross_run on en adapt write) |
| `protocols.db` écrit | Non | **Oui** en adapt, read-only en C3 |
| `delivery_rate` | Trompeur (faux positifs) | Corrigé (`official_delivery_rate`) |
| Promotion lessons | Bloquée sur `terminal` | Autorisée sur `terminal` réussi |
| Baselines évaluées | 90 queries | **180 queries** |

---

## 🔄 SI TU DOIS RELANCER À ZÉRO

Les scripts ont `CLEAN_RESULTS=true` par défaut, ils suppriment automatiquement les anciens résultats au démarrage. Mais si tu veux aussi nettoyer côté host :

```bash
docker compose -f docker-compose.campaign.yml down --remove-orphans
rm -rf campaign_results/deepseek-stigmergie campaign_results/gemma-baselines campaign_results/gemma-stigmergie
```

Puis rebuild si tu as modifié du code Python :

```bash
docker compose -f docker-compose.campaign.yml build --no-cache
```

Et re-lance depuis le bloc **🚀 LANCE TOUT MAINTENANT**.

---

## 🔬 SMOKE TESTS (OPTIONNEL, ~5 MIN)

Si tu veux valider chaque chemin avant la campagne complète.

### Smoke DeepSeek API (10s)

```bash
docker compose -f docker-compose.campaign.yml run --rm deepseek-stigmergie python scripts/smoke_deepseek.py
```

Attendu : `SUCCESS` + `content: '{"ok": true}'`.

### Smoke DeepSeek × stigmergie sur 1 query train (~1-2 min)

```bash
docker compose -f docker-compose.campaign.yml run --rm deepseek-stigmergie bash -c 'mkdir -p campaign_results/adapt pheromones && python main.py --adapter travelplanner --objective "Query 0" --config config/travelplanner_adapt_scientific_deepseek.yaml --query-idx 0 --seed 42'
```

Attendu : JSON final avec `"final_pass"` défini, `"tokens_used"` > 5000, `"stop_reason"` cohérent (`all_terminal` ou `idle_cycles` selon la query).

### Smoke Gemma × stigmergie sur 1 query train

```bash
docker compose -f docker-compose.campaign.yml run --rm gemma-stigmergie bash -c 'mkdir -p campaign_results/adapt pheromones && python main.py --adapter travelplanner --objective "Query 0" --config config/travelplanner_adapt_scientific.yaml --query-idx 0 --seed 42'
```

### Smoke Gemma baselines sur 1 query validation

```bash
docker compose -f docker-compose.campaign.yml run --rm gemma-baselines bash -c 'mkdir -p campaign_results/solo_direct && python scripts/run_travelplanner_solo_query_export.py --objective "Query 0" --query-idx 0 --config config/travelplanner_eval_baseline_gemma.yaml --seed 42'
```

### Smoke MetaGPT

```bash
docker compose -f docker-compose.campaign.yml run --rm gemma-baselines bash -c 'mkdir -p campaign_results/metagpt_sequential && python scripts/run_travelplanner_metagpt_query_export.py --objective "Query 0" --query-idx 0 --config config/travelplanner_eval_baseline_gemma.yaml --seed 42'
```

---

## 💰 BUDGET ESTIMÉ

| Campagne | Queries | Tokens | Coût |
| --- | --- | --- | --- |
| Gemma × stigmergie (adapt 45 + C3 180) | 225 | ~18 M | ~$5-7 |
| DeepSeek × stigmergie (adapt 45 + C3 180, cache ~50 %) | 225 | ~18 M | ~$3-5 |
| Gemma × 6 baselines × 180 queries | 1080 | ~12-16 M | ~$4-6 |
| **Total** | — | — | **~$12-18** |

Durée parallèle sur 3 containers : **10-15 h** (contrainte = `gemma-baselines` qui fait 6 frameworks séquentiels sur 180 queries).

---

## 🆘 TROUBLESHOOTING

### `RuntimeError: LLM client is unavailable`

Clés pas exportées. Refais le bloc `set -a; source .env; set +a; export OPENROUTER_API_KEY_2=...`.

### `ValueError: Unsupported llm.provider=deepseek`

Image pas rebuild. Fais `docker compose -f docker-compose.campaign.yml build --no-cache`.

### `Invalid max_tokens value, the valid range of max_tokens is [1, 8192]`

Ne devrait plus arriver, le code cap à 8000. Si ça arrive, vérifie `_dynamic_max_response_tokens` dans `adapters/travelplanner/tools.py`.

### Containers qui crashent immédiatement

```bash
docker compose -f docker-compose.campaign.yml logs --tail=200 <service>
```

Regarde la dernière exception Python.

### Disque plein

```bash
docker system prune -a --volumes
```

### Copie-colle qui casse

Les blocs `bash -c '...'` sont en **une seule ligne logique** (même si le markdown les wrap visuellement). Colle tout d'un coup, pas ligne par ligne.

---

## 📝 NOTES MÉTHODOLOGIQUES POUR LE MÉMOIRE

- **Train/test split** : `train_45.jsonl` (45 queries) pour l'adaptation, `validation.jsonl` (180 queries) pour l'évaluation. Protocole identique à SwarmAgentic (Hong et al. 2025), MetaGPT (Hong et al. 2023), TravelPlanner officiel (Xie et al. 2024).
- **1 seed par modèle** : limitation assumée, à documenter en "Threats to validity".
- **Modèle principal** : Gemma (`google/gemma-4-31b-it`).
- **Modèle fort (stigmergie seule)** : DeepSeek V3 (`deepseek-chat`).
- **Modèle stress-test (fixture pré-calculée)** : Qwen 3.5 9B — 23.9 % sur 180 validation, `output/travelplanner_framework_compare/v6c_retry_20260420_seed42/v6_C/seed42/`.
- **Baselines** (Gemma, 180 queries chacune) : `solo_direct`, `solo_cot`, `solo_self_refine`, `planner_executor`, `metagpt_sequential`, `langgraph_supervisor`.
- **Stigmergie** : configuration C3 uniquement (`skills` + `protocols` read-only en eval, `cross_run` read-only).
- Décisions structurantes consignées dans `documentation/redisgn_v2/decision_log_model_switch.md` et `documentation/redisgn_v2/v9_campaign_behavior_analysis.md`.
