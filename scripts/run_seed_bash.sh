#!/bin/bash
# Sprint 9 — TravelPlanner Campaign (seed isolé, pas de multiprocessing, pas de notebook)
#
# Usage (Terminal 1):
#   SEED=42 API_KEY=$(grep OPENROUTER_API_KEY .env | cut -d= -f2) bash scripts/run_seed_bash.sh
#
# Usage (Terminal 2):
#   SEED=43 API_KEY=$(grep OPENROUTER_API_KEY .env.key2 | cut -d= -f2) bash scripts/run_seed_bash.sh

set -euo pipefail

SEED=${SEED:-42}
QUERIES=${QUERIES:-5}
QUERY_START=${QUERY_START:-0}
API_KEY=${API_KEY:-}

if [ -z "$API_KEY" ]; then
    echo "ERREUR: exporte API_KEY avant de lancer"
    exit 1
fi

echo "=== SEED $SEED ==="
echo "Queries: $QUERY_START → $((QUERY_START + QUERIES - 1))"

# Phase 1 : Adaptation
echo ""
echo "--- Phase 1: ADAPTATION ---"
for i in $(seq $QUERY_START $((QUERY_START + QUERIES - 1))); do
    echo "[seed $SEED] Query $i (adapt)..."
    OPENROUTER_API_KEY="$API_KEY" \
        uv run python main.py \
        --adapter travelplanner \
        --objective "Query $i" \
        --config config/travelplanner_adapt.yaml \
        --query-idx "$i" \
        --seed "$SEED" \
        > "notebooks/seed${SEED}_query${i}_adapt.json" 2>/dev/null || true
    echo "  done"
done

# Phase 2 : Évaluation figée
echo ""
echo "--- Phase 2: EVALUATION FIGÉE ---"
for i in $(seq $QUERY_START $((QUERY_START + QUERIES - 1))); do
    echo "[seed $SEED] Query $i (eval)..."
    OPENROUTER_API_KEY="$API_KEY" \
        uv run python main.py \
        --adapter travelplanner \
        --objective "Query $i" \
        --config config/travelplanner_eval.yaml \
        --query-idx "$i" \
        --seed "$SEED" \
        > "notebooks/seed${SEED}_query${i}_eval.json" 2>/dev/null || true
    echo "  done"
done

echo ""
echo "=== TERMINÉ ==="
echo "Résultats dans notebooks/seed${SEED}_query*.json"
