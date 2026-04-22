#!/bin/bash
# Sprint 9 — Campagne Scientifique (1 seed, split train/test 90/90)
#
# Méthodologie:
#   Phase 1 (Adapt)   : queries 0-89  → accumulation skills + protocols
#   Phase 2 (C2)      : queries 90-179 → évaluation figée avec skills (read-only)
#   Phase 3 (C3)      : queries 90-179 → évaluation figée avec skills + cross-run protocol
#   Phase 4 (Baseline): queries 90-179 → évaluation sans skills ni cross-run
#
# Usage:
#   SEED=42 API_KEY=$(grep OPENROUTER_API_KEY .env | cut -d= -f2) bash scripts/run_sprint9_scientific_campaign.sh

set -euo pipefail

SEED=${SEED:-42}
API_KEY=${API_KEY:-}

ADAPT_START=${ADAPT_START:-0}
ADAPT_QUERIES=${ADAPT_QUERIES:-90}
EVAL_START=${EVAL_START:-90}
EVAL_QUERIES=${EVAL_QUERIES:-90}

if [ -z "$API_KEY" ]; then
    echo "ERREUR: exporte API_KEY avant de lancer"
    echo "  Ex: API_KEY=$(grep OPENROUTER_API_KEY .env | cut -d= -f2) bash $0"
    exit 1
fi

ADAPT_END=$((ADAPT_START + ADAPT_QUERIES - 1))
EVAL_END=$((EVAL_START + EVAL_QUERIES - 1))

echo "========================================"
echo "SPRINT 9 CAMPAGNE SCIENTIFIQUE"
echo "Seed: $SEED"
echo "Adaptation: $ADAPT_START → $ADAPT_END"
echo "Évaluation: $EVAL_START → $EVAL_END"
echo "========================================"

# ==========================================
# NETTOYAGE PROPRE
# ==========================================
echo ""
echo "=== NETTOYAGE ==="
rm -f pheromones/skills.db pheromones/protocols.db
rm -rf campaign_results
mkdir -p campaign_results/adapt
mkdir -p campaign_results/c2
mkdir -p campaign_results/c3
mkdir -p campaign_results/baseline
echo "  DB et résultats précédents supprimés"
echo "  Dossiers créés:"
ls -la campaign_results/

# ==========================================
# PHASE 1 : ADAPTATION (0-89)
# ==========================================
echo ""
echo "=== PHASE 1 : ADAPTATION ($ADAPT_QUERIES queries) ==="
echo "Config: config/travelplanner_adapt_scientific.yaml"
echo "Objectif: accumuler skills et protocols"

mkdir -p campaign_results/adapt
for i in $(seq $ADAPT_START $ADAPT_END); do
    echo "[Adapt] Query $i ..."
    OPENROUTER_API_KEY="$API_KEY" \
        uv run python main.py \
        --adapter travelplanner \
        --objective "Query $i" \
        --config config/travelplanner_adapt_scientific.yaml \
        --query-idx "$i" \
        --seed "$SEED" \
        > "campaign_results/adapt/query_${i}.json" 2>/dev/null || true
    echo "  done"
done

echo ""
echo "--- Skills accumulés ---"
python3 -c "
import sys
sys.path.insert(0, '.')
from core.marker_store import MarkerStore
from pathlib import Path
store = MarkerStore(db_path=Path('pheromones/skills.db'), session_isolation=False, traceability=False)
skills = store.query_markers(marker_type='skill')
print(f'Total skills: {len(skills)}')
for sk in skills[:5]:
    print(f'  - {sk.id}')
" || echo "  (erreur lecture skills)"

echo ""
echo "--- Protocols persistés ---"
python3 -c "
import sys
sys.path.insert(0, '.')
from core.marker_store import MarkerStore
from pathlib import Path
store = MarkerStore(db_path=Path('pheromones/protocols.db'), session_isolation=False, traceability=False)
protocols = store.query_markers(marker_type='coordination_protocol')
print(f'Total protocols: {len(protocols)}')
for p in protocols:
    print(f'  - {p.id}')
" || echo "  (erreur lecture protocols)"

# ==========================================
# PHASE 2 : C2 ÉVALUATION (90-179, skills read-only)
# ==========================================
echo ""
echo "=== PHASE 2 : C2 ÉVALUATION ($EVAL_QUERIES queries) ==="
echo "Config: config/travelplanner_eval_c2.yaml"
echo "Objectif: évaluer avec skills accumulés (read-only), sans cross-run"

mkdir -p campaign_results/c2
for i in $(seq $EVAL_START $EVAL_END); do
    echo "[C2] Query $i ..."
    OPENROUTER_API_KEY="$API_KEY" \
        uv run python main.py \
        --adapter travelplanner \
        --objective "Query $i" \
        --config config/travelplanner_eval_c2.yaml \
        --query-idx "$i" \
        --seed "$SEED" \
        > "campaign_results/c2/query_${i}.json" 2>/dev/null || true
    echo "  done"
done

# ==========================================
# PHASE 3 : C3 ÉVALUATION (90-179, skills + cross-run)
# ==========================================
echo ""
echo "=== PHASE 3 : C3 ÉVALUATION ($EVAL_QUERIES queries) ==="
echo "Config: config/travelplanner_eval_c3.yaml"
echo "Objectif: évaluer avec skills + cross-run protocol (read-only)"

mkdir -p campaign_results/c3
for i in $(seq $EVAL_START $EVAL_END); do
    echo "[C3] Query $i ..."
    OPENROUTER_API_KEY="$API_KEY" \
        uv run python main.py \
        --adapter travelplanner \
        --objective "Query $i" \
        --config config/travelplanner_eval_c3.yaml \
        --query-idx "$i" \
        --seed "$SEED" \
        > "campaign_results/c3/query_${i}.json" 2>/dev/null || true
    echo "  done"
done

# ==========================================
# PHASE 4 : BASELINE (90-179, sans rien)
# ==========================================
echo ""
echo "=== PHASE 4 : BASELINE ($EVAL_QUERIES queries) ==="
echo "Config: config/travelplanner_eval_baseline.yaml"
echo "Objectif: évaluer sans skills ni cross-run"

mkdir -p campaign_results/baseline
for i in $(seq $EVAL_START $EVAL_END); do
    echo "[Baseline] Query $i ..."
    OPENROUTER_API_KEY="$API_KEY" \
        uv run python main.py \
        --adapter travelplanner \
        --objective "Query $i" \
        --config config/travelplanner_eval_baseline.yaml \
        --query-idx "$i" \
        --seed "$SEED" \
        > "campaign_results/baseline/query_${i}.json" 2>/dev/null || true
    echo "  done"
done

# ==========================================
# ANALYSE
# ==========================================
echo ""
echo "=== ANALYSE STATISTIQUE ==="

python3 - << 'PYEOF'
import json
from pathlib import Path
from collections import defaultdict

def parse_results(phase_dir):
    results = {}
    for f in sorted(Path(phase_dir).glob("query_*.json")):
        text = f.read_text()
        for idx in range(text.rfind("}"), -1, -1):
            if text[idx] == "{":
                try:
                    data = json.loads(text[idx:])
                    q = int(f.stem.split("_")[1])
                    results[q] = data
                    break
                except:
                    continue
    return results

def summarize(results, label):
    if not results:
        print(f"{label}: Aucun résultat")
        return None
    
    passed = sum(1 for d in results.values() if d.get("evaluation", {}).get("passed", False))
    total = len(results)
    scores = [d.get("evaluation", {}).get("score", 0.0) for d in results.values()]
    avg_score = sum(scores) / len(scores) if scores else 0
    
    stop_reasons = defaultdict(int)
    for d in results.values():
        sr = d.get("stop_reason", "unknown")
        stop_reasons[sr] += 1
    
    # Émergence
    pu = [d.get("emergence_summary", {}).get("parallel_utilization", 0) for d in results.values()]
    ct = [d.get("emergence_summary", {}).get("convergence_tick", 0) for d in results.values()]
    avg_pu = sum(pu) / len(pu) if pu else 0
    avg_ct = sum(ct) / len(ct) if ct else 0
    
    # Delivery rate
    delivered = sum(1 for d in results.values() 
                   if any(qr.get("delivered", False) for qr in d.get("evaluation", {}).get("query_results", [])))
    
    print(f"\n{'='*50}")
    print(f"{label}")
    print(f"{'='*50}")
    print(f"  Queries évaluées : {total}")
    print(f"  Pass rate        : {passed}/{total} ({100*passed/total:.1f}%)")
    print(f"  Delivery rate    : {delivered}/{total} ({100*delivered/total:.1f}%)")
    print(f"  Score moyen      : {avg_score:.3f}")
    print(f"  Parallel util.   : {avg_pu:.3f}")
    print(f"  Convergence tick : {avg_ct:.1f}")
    print(f"  Stop reasons     : {dict(stop_reasons)}")
    
    return {
        "label": label,
        "total": total,
        "passed": passed,
        "pass_rate": passed / total,
        "delivery_rate": delivered / total if total else 0,
        "avg_score": avg_score,
        "avg_parallel_utilization": avg_pu,
        "avg_convergence_tick": avg_ct,
        "stop_reasons": dict(stop_reasons),
    }

# Parse toutes les phases
adapt = parse_results("campaign_results/adapt")
c2 = parse_results("campaign_results/c2")
c3 = parse_results("campaign_results/c3")
baseline = parse_results("campaign_results/baseline")

# Summarize
summarize(adapt, "PHASE 1 : ADAPTATION (queries d'entraînement)")
summarize(c2, "PHASE 2 : C2 ÉVALUATION (skills read-only)")
summarize(c3, "PHASE 3 : C3 ÉVALUATION (skills + cross-run)")
summarize(baseline, "PHASE 4 : BASELINE (sans skills ni cross-run)")

# Comparaison directe sur le même test set
print(f"\n{'='*50}")
print("COMPARAISON C2 vs C3 vs BASELINE (même test set)")
print(f"{'='*50}")

common_queries = sorted(set(c2.keys()) & set(c3.keys()) & set(baseline.keys()))
if common_queries:
    c2_wins = 0
    c3_wins = 0
    baseline_wins = 0
    
    for q in common_queries:
        c2_pass = c2[q].get("evaluation", {}).get("passed", False)
        c3_pass = c3[q].get("evaluation", {}).get("passed", False)
        base_pass = baseline[q].get("evaluation", {}).get("passed", False)
        
        if c2_pass and not c3_pass and not base_pass:
            c2_wins += 1
        elif c3_pass and not c2_pass and not base_pass:
            c3_wins += 1
        elif base_pass and not c2_pass and not c3_pass:
            baseline_wins += 1
    
    print(f"  Queries où C2 gagne seul : {c2_wins}")
    print(f"  Queries où C3 gagne seul : {c3_wins}")
    print(f"  Queries où Baseline gagne seul : {baseline_wins}")
    
    # Queries où C3 bat C2
    c3_beats_c2 = sum(1 for q in common_queries 
                      if c3[q].get("evaluation", {}).get("passed", False) 
                      and not c2[q].get("evaluation", {}).get("passed", False))
    c2_beats_c3 = sum(1 for q in common_queries 
                      if c2[q].get("evaluation", {}).get("passed", False) 
                      and not c3[q].get("evaluation", {}).get("passed", False))
    print(f"\n  C3 bat C2 sur : {c3_beats_c2} queries")
    print(f"  C2 bat C3 sur : {c2_beats_c3} queries")

# Export JSON final
export = {
    "adapt": {str(k): v for k, v in adapt.items()},
    "c2": {str(k): v for k, v in c2.items()},
    "c3": {str(k): v for k, v in c3.items()},
    "baseline": {str(k): v for k, v in baseline.items()},
}
with open("campaign_results/sprint9_scientific_results.json", "w") as f:
    json.dump(export, f, indent=2, default=str)
print(f"\nRésultats exportés : campaign_results/sprint9_scientific_results.json")

PYEOF

echo ""
echo "=== CAMPAGNE SCIENTIFIQUE TERMINÉE ==="
echo "Résultats bruts dans campaign_results/"
echo "Analyse dans campaign_results/sprint9_scientific_results.json"
