#!/bin/bash
# Campagne scientifique finale — 6 baselines sous Gemma (1 seed).
# NE PAS LANCER DIRECTEMENT — utilise docker compose.
#
# Produit:
#   campaign_results/solo_direct/query_${i}.json
#   campaign_results/solo_cot/query_${i}.json
#   campaign_results/solo_self_refine/query_${i}.json
#   campaign_results/planner_executor/query_${i}.json
#   campaign_results/metagpt_sequential/query_${i}.json
#   campaign_results/langgraph_supervisor/query_${i}.json

set -euo pipefail

SEED=${SEED:-42}
EVAL_START=${EVAL_START:-0}
EVAL_QUERIES=${EVAL_QUERIES:-180}
EVAL_END=$((EVAL_START + EVAL_QUERIES - 1))
BASELINE_CONFIG=${BASELINE_CONFIG:-config/travelplanner_eval_baseline_gemma.yaml}
CLEAN_RESULTS=${CLEAN_RESULTS:-true}

echo "=== CAMPAGNE BASELINES × GEMMA ==="
echo "Seed: $SEED | Eval: $EVAL_START → $EVAL_END"
echo "Config: $BASELINE_CONFIG"

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
    echo "FATAL: OPENROUTER_API_KEY is empty — check .env.key2 and docker-compose env mapping." >&2
    exit 2
fi
python -c "import main" || { echo "FATAL: main.py import failed." >&2; exit 2; }

run_baseline () {
    local name=$1
    local script=$2
    echo ""
    echo "--- Baseline: $name ---"
    mkdir -p "campaign_results/${name}"
    if [[ "$CLEAN_RESULTS" == "true" ]]; then
        rm -f "campaign_results/${name}"/query_*.json
    fi
    for i in $(seq $EVAL_START $EVAL_END); do
        echo "[$name] Q$i"
        python "$script" \
            --objective "Query $i" \
            --query-idx "$i" \
            --config "$BASELINE_CONFIG" \
            --seed "$SEED" \
            > "campaign_results/${name}/query_${i}.json" 2>/dev/null || true
    done
}

run_baseline "solo_direct"         "scripts/run_travelplanner_solo_query_export.py"
run_baseline "solo_cot"            "scripts/run_travelplanner_cot_query_export.py"
run_baseline "solo_self_refine"    "scripts/run_travelplanner_self_refine_query_export.py"
run_baseline "planner_executor"    "scripts/run_travelplanner_planner_executor_query_export.py"
run_baseline "metagpt_sequential"  "scripts/run_travelplanner_metagpt_query_export.py"
run_baseline "langgraph_supervisor" "scripts/run_travelplanner_langgraph_query_export.py"

echo ""
echo "=== CAMPAGNE BASELINES × GEMMA TERMINÉE ==="
