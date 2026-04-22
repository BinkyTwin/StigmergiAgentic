#!/bin/bash
# Campagne Gemma dans Docker — tourne dans le conteneur gemma-campaign
# NE PAS LANCER DIRECTEMENT — utilise docker compose

set -euo pipefail

SEED=${SEED:-42}
ADAPT_START=${ADAPT_START:-0}
ADAPT_QUERIES=${ADAPT_QUERIES:-90}
EVAL_START=${EVAL_START:-90}
EVAL_QUERIES=${EVAL_QUERIES:-90}

ADAPT_END=$((ADAPT_START + ADAPT_QUERIES - 1))
EVAL_END=$((EVAL_START + EVAL_QUERIES - 1))

echo "=== CAMPAGNE GEMMA 4 31B ==="
echo "Seed: $SEED"
echo "Adapt: $ADAPT_START → $ADAPT_END | Eval: $EVAL_START → $EVAL_END"

# Nettoyage
rm -f pheromones/skills.db pheromones/protocols.db

# PHASE 1: Adaptation
echo ""
echo "--- Phase 1: ADAPTATION ---"
for i in $(seq $ADAPT_START $ADAPT_END); do
    echo "[Adapt] Q$i"
    python main.py \
        --adapter travelplanner \
        --objective "Query $i" \
        --config config/travelplanner_adapt_gemma.yaml \
        --query-idx "$i" \
        --seed "$SEED" \
        > "campaign_results/adapt/query_${i}.json" 2>/dev/null || true
done

# PHASE 2: C2
echo ""
echo "--- Phase 2: C2 ---"
for i in $(seq $EVAL_START $EVAL_END); do
    echo "[C2] Q$i"
    python main.py \
        --adapter travelplanner \
        --objective "Query $i" \
        --config config/travelplanner_eval_c2_gemma.yaml \
        --query-idx "$i" \
        --seed "$SEED" \
        > "campaign_results/c2/query_${i}.json" 2>/dev/null || true
done

# PHASE 3: C3
echo ""
echo "--- Phase 3: C3 ---"
for i in $(seq $EVAL_START $EVAL_END); do
    echo "[C3] Q$i"
    python main.py \
        --adapter travelplanner \
        --objective "Query $i" \
        --config config/travelplanner_eval_c3_gemma.yaml \
        --query-idx "$i" \
        --seed "$SEED" \
        > "campaign_results/c3/query_${i}.json" 2>/dev/null || true
done

# PHASE 4: Baseline
echo ""
echo "--- Phase 4: BASELINE ---"
for i in $(seq $EVAL_START $EVAL_END); do
    echo "[Base] Q$i"
    python main.py \
        --adapter travelplanner \
        --objective "Query $i" \
        --config config/travelplanner_eval_baseline_gemma.yaml \
        --query-idx "$i" \
        --seed "$SEED" \
        > "campaign_results/baseline/query_${i}.json" 2>/dev/null || true
done

echo ""
echo "=== CAMPAGNE GEMMA TERMINÉE ==="
echo "Résultats dans /app/campaign_results/"
