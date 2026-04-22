#!/bin/bash
# Sprint 9 — Campagne Scientifique avec Google/Gemma-4-31B-it
# Tourne dans Docker avec la deuxième clé API
#
# Usage (depuis l'hôte):
#   OPENROUTER_API_KEY_2=$(grep OPENROUTER_API_KEY .env.key2 | cut -d= -f2) docker compose run --rm gemma-campaign

set -euo pipefail

SEED=${SEED:-42}
API_KEY=${OPENROUTER_API_KEY:-}

ADAPT_START=${ADAPT_START:-0}
ADAPT_QUERIES=${ADAPT_QUERIES:-90}
EVAL_START=${EVAL_START:-90}
EVAL_QUERIES=${EVAL_QUERIES:-90}

if [ -z "$API_KEY" ]; then
    echo "ERREUR: OPENROUTER_API_KEY non définie"
    exit 1
fi

ADAPT_END=$((ADAPT_START + ADAPT_QUERIES - 1))
EVAL_END=$((EVAL_START + EVAL_QUERIES - 1))

echo "========================================"
echo "SPRINT 9 CAMPAGNE GEMMA 4 31B"
echo "Seed: $SEED | Modèle: google/gemma-4-31b-it"
echo "Adaptation: $ADAPT_START → $ADAPT_END"
echo "Évaluation: $EVAL_START → $EVAL_END"
echo "========================================"

# Nettoyage
rm -f pheromones/skills.db pheromones/protocols.db
rm -rf campaign_results
mkdir -p campaign_results/{adapt,c2,c3,baseline}

# ==========================================
# PHASE 1 : ADAPTATION (avec Gemma)
# ==========================================
echo ""
echo "=== PHASE 1 : ADAPTATION ($ADAPT_QUERIES queries) ==="
echo "Config: config/travelplanner_adapt_gemma.yaml"

for i in $(seq $ADAPT_START $ADAPT_END); do
    echo "[Adapt] Query $i ..."
    OPENROUTER_API_KEY="$API_KEY" \
        python main.py \
        --adapter travelplanner \
        --objective "Query $i" \
        --config config/travelplanner_adapt_gemma.yaml \
        --query-idx "$i" \
        --seed "$SEED" \
        > "campaign_results/adapt/query_${i}.json" 2>/dev/null || true
    echo "  done"
done

# ==========================================
# PHASE 2 : C2 ÉVALUATION
# ==========================================
echo ""
echo "=== PHASE 2 : C2 ÉVALUATION ($EVAL_QUERIES queries) ==="
for i in $(seq $EVAL_START $EVAL_END); do
    echo "[C2] Query $i ..."
    OPENROUTER_API_KEY="$API_KEY" \
        python main.py \
        --adapter travelplanner \
        --objective "Query $i" \
        --config config/travelplanner_eval_c2_gemma.yaml \
        --query-idx "$i" \
        --seed "$SEED" \
        > "campaign_results/c2/query_${i}.json" 2>/dev/null || true
    echo "  done"
done

# ==========================================
# PHASE 3 : C3 ÉVALUATION
# ==========================================
echo ""
echo "=== PHASE 3 : C3 ÉVALUATION ($EVAL_QUERIES queries) ==="
for i in $(seq $EVAL_START $EVAL_END); do
    echo "[C3] Query $i ..."
    OPENROUTER_API_KEY="$API_KEY" \
        python main.py \
        --adapter travelplanner \
        --objective "Query $i" \
        --config config/travelplanner_eval_c3_gemma.yaml \
        --query-idx "$i" \
        --seed "$SEED" \
        > "campaign_results/c3/query_${i}.json" 2>/dev/null || true
    echo "  done"
done

# ==========================================
# PHASE 4 : BASELINE
# ==========================================
echo ""
echo "=== PHASE 4 : BASELINE ($EVAL_QUERIES queries) ==="
for i in $(seq $EVAL_START $EVAL_END); do
    echo "[Baseline] Query $i ..."
    OPENROUTER_API_KEY="$API_KEY" \
        python main.py \
        --adapter travelplanner \
        --objective "Query $i" \
        --config config/travelplanner_eval_baseline_gemma.yaml \
        --query-idx "$i" \
        --seed "$SEED" \
        > "campaign_results/baseline/query_${i}.json" 2>/dev/null || true
    echo "  done"
done

echo ""
echo "=== CAMPAGNE GEMMA TERMINÉE ==="
echo "Résultats dans campaign_results/"
