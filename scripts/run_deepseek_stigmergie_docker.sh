#!/bin/bash
# Campagne scientifique finale — stigmergie C3 sous DeepSeek V3
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

echo "=== CAMPAGNE DEEPSEEK × STIGMERGIE C3 ==="
echo "Seed: $SEED"
echo "Adapt train split: $ADAPT_START → $ADAPT_END | Eval validation split: $EVAL_START → $EVAL_END"

# Pre-flight: fail fast if the API key is missing or the import graph is broken
if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
    echo "FATAL: DEEPSEEK_API_KEY is empty — check .env and docker-compose env mapping." >&2
    exit 2
fi
python -c "import main" || { echo "FATAL: main.py import failed." >&2; exit 2; }

clean_args=()
if [[ "$CLEAN_RESULTS" == "true" ]]; then
    clean_args+=(--clean)
fi

python scripts/run_travelplanner_c3_refactor_campaign.py \
    --out-dir campaign_results \
    --adapt-config config/travelplanner_c3_full_adapt_deepseek.yaml \
    --eval-config config/travelplanner_c3_full_eval_deepseek.yaml \
    --seed "$SEED" \
    --adapt-start "$ADAPT_START" \
    --adapt-queries "$ADAPT_QUERIES" \
    --eval-start "$EVAL_START" \
    --eval-queries "$EVAL_QUERIES" \
    --expected-provider deepseek \
    --expected-model deepseek-chat \
    --expected-namespace coordination_protocol::travelplanner::travelplanner_c3_deepseek_seed42_v1 \
    --expect-compiler enabled \
    "${clean_args[@]}"

echo ""
echo "=== CAMPAGNE DEEPSEEK × STIGMERGIE C3 TERMINÉE ==="
