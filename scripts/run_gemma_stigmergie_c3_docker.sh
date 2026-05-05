#!/bin/bash
# Campagne scientifique finale — stigmergie C3 sous Gemma
# NE PAS LANCER DIRECTEMENT — utilise docker compose.

set -euo pipefail

SEED=${SEED:-42}
ADAPT_START=${ADAPT_START:-0}
ADAPT_QUERIES=${ADAPT_QUERIES:-45}
EVAL_START=${EVAL_START:-0}
EVAL_QUERIES=${EVAL_QUERIES:-180}
CLEAN_RESULTS=${CLEAN_RESULTS:-true}

ADAPT_END=$((ADAPT_START + ADAPT_QUERIES - 1))
EVAL_END=$((EVAL_START + EVAL_QUERIES - 1))

echo "=== CAMPAGNE GEMMA × STIGMERGIE C3 ==="
echo "Seed: $SEED"
echo "Adapt train split: $ADAPT_START → $ADAPT_END | Eval validation split: $EVAL_START → $EVAL_END"

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
    echo "FATAL: OPENROUTER_API_KEY is empty — check .env and docker-compose env mapping." >&2
    exit 2
fi
python -c "import main" || { echo "FATAL: main.py import failed." >&2; exit 2; }

clean_args=()
if [[ "$CLEAN_RESULTS" == "true" ]]; then
    clean_args+=(--clean)
fi

python scripts/run_travelplanner_c3_refactor_campaign.py \
    --out-dir campaign_results \
    --adapt-config config/travelplanner_c3_full_adapt_gemma.yaml \
    --eval-config config/travelplanner_c3_full_eval_gemma.yaml \
    --seed "$SEED" \
    --adapt-start "$ADAPT_START" \
    --adapt-queries "$ADAPT_QUERIES" \
    --eval-start "$EVAL_START" \
    --eval-queries "$EVAL_QUERIES" \
    --expected-provider openrouter \
    --expected-model google/gemma-4-31b-it \
    --expected-namespace coordination_protocol::travelplanner::travelplanner_c3_gemma_seed42_v1 \
    --expect-compiler enabled \
    "${clean_args[@]}"

echo ""
echo "=== CAMPAGNE GEMMA × STIGMERGIE C3 TERMINÉE ==="
