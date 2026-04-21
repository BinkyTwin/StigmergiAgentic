#!/usr/bin/env python3
"""Sprint 9 — TravelPlanner Evaluation Campaign (script pur, no notebook).

Usage:
    uv run python scripts/run_sprint9_campaign.py

Configuration (édite directement dans ce fichier):
    QUERY_START = 0
    QUERY_END   = 5   # ← mets 180 pour la campagne complète
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

# ==========================================
# CONFIGURATION
# ==========================================

REPO_ROOT = Path(__file__).resolve().parents[1]
SEEDS = [42, 43]
QUERY_START = 0
QUERY_END = 5  # ← Ajuste ici (max 180)

CONFIG_ADAPT = "config/travelplanner_adapt.yaml"
CONFIG_EVAL = "config/travelplanner_eval.yaml"


def _load_key(env_file: str) -> str:
    path = REPO_ROOT / env_file
    for line in path.read_text().splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise ValueError(f"OPENROUTER_API_KEY not found in {env_file}")


API_KEYS = {
    SEEDS[0]: _load_key(".env"),
    SEEDS[1]: _load_key(".env.key2"),
}


# ==========================================
# FONCTION DE RUN (process-isolée)
# ==========================================


def run_campaign_for_seed(
    seed, config_path, api_key, query_start, query_end, markers_db_name
):
    """Run a batch of TravelPlanner queries in one process with a dedicated markers DB."""
    import io
    import contextlib

    os.environ["OPENROUTER_API_KEY"] = api_key
    os.environ["PYTHONWARNINGS"] = "ignore"

    sys.path.insert(0, str(REPO_ROOT))
    import main

    main.DEFAULT_DB_PATH = REPO_ROOT / "pheromones" / markers_db_name

    results = []
    for query_idx in range(query_start, query_end):
        argv = [
            "--adapter",
            "travelplanner",
            "--objective",
            f"Query {query_idx}",
            "--config",
            str(config_path),
            "--query-idx",
            str(query_idx),
            "--seed",
            str(seed),
        ]

        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                exit_code = main.main(argv)
        except Exception as e:
            exit_code = 1
            print(f"[ERROR] Query {query_idx} seed {seed} failed: {e}")
            traceback.print_exc()

        output = buf.getvalue()

        # Extraire le dernier JSON du stdout (pretty-printed sur plusieurs lignes)
        summary = None
        text = output.strip()
        for idx_char in range(text.rfind("}"), -1, -1):
            if text[idx_char] == "{":
                try:
                    summary = json.loads(text[idx_char:])
                    break
                except json.JSONDecodeError:
                    continue

        results.append(
            {
                "query_idx": query_idx,
                "seed": seed,
                "config": Path(config_path).name,
                "exit_code": exit_code,
                "summary": summary,
            }
        )
        print(
            f"  [seed {seed}] Query {query_idx} → exit={exit_code}, summary={'OK' if summary else 'MISSING'}"
        )

    return results


# ==========================================
# MAIN (wrappé pour macOS multiprocessing)
# ==========================================

if __name__ == "__main__":
    os.chdir(REPO_ROOT)

    # Nettoyage
    print("=== NETTOYAGE DES DB DE SESSION ===")
    for seed in SEEDS:
        for suffix in ["", "_eval"]:
            db = REPO_ROOT / f"pheromones/markers_seed{seed}{suffix}.db"
            if db.exists():
                db.unlink()
                print(f"  Removed {db}")

    print(f"\nConfiguration :")
    print(f"  Seeds   : {SEEDS}")
    print(f"  Queries : {QUERY_START} → {QUERY_END - 1}")
    print(f"  API keys: {len(set(API_KEYS.values()))} unique\n")

    # Phase 1
    print("=== PHASE 1 : ADAPTATION ===")
    adapt_results: dict[int, list] = {}
    with ProcessPoolExecutor(max_workers=2) as executor:
        futures = {
            seed: executor.submit(
                run_campaign_for_seed,
                seed,
                CONFIG_ADAPT,
                API_KEYS[seed],
                QUERY_START,
                QUERY_END,
                f"markers_seed{seed}.db",
            )
            for seed in SEEDS
        }
        for seed, future in futures.items():
            adapt_results[seed] = future.result()
            print(f"Seed {seed} adapt done : {len(adapt_results[seed])} queries\n")

    # Phase 2
    print("=== PHASE 2 : EVALUATION FIGÉE ===")
    eval_results: dict[int, list] = {}
    with ProcessPoolExecutor(max_workers=2) as executor:
        futures = {
            seed: executor.submit(
                run_campaign_for_seed,
                seed,
                CONFIG_EVAL,
                API_KEYS[seed],
                QUERY_START,
                QUERY_END,
                f"markers_seed{seed}_eval.db",
            )
            for seed in SEEDS
        }
        for seed, future in futures.items():
            eval_results[seed] = future.result()
            print(f"Seed {seed} eval done : {len(eval_results[seed])} queries\n")

    # Analyse
    print("=== ANALYSE ===")

    def flatten(results: dict[int, list]) -> list[dict]:
        rows = []
        for seed, queries in results.items():
            for q in queries:
                row = {
                    "seed": q["seed"],
                    "query_idx": q["query_idx"],
                    "config": q["config"],
                    "exit_code": q["exit_code"],
                }
                summary = q.get("summary") or {}
                row["stop_reason"] = summary.get("stop_reason", "N/A")
                row["passed"] = summary.get("evaluation", {}).get("passed", False)
                row["score"] = summary.get("evaluation", {}).get("score", 0.0)
                row["ticks"] = summary.get("ticks", 0)
                em = summary.get("emergence_summary", {})
                row["parallel_utilization"] = em.get("parallel_utilization", 0.0)
                row["convergence_tick"] = em.get("convergence_tick", 0)
                rows.append(row)
        return rows

    rows_all = flatten(adapt_results) + flatten(eval_results)

    from collections import defaultdict

    agg = defaultdict(
        lambda: {"queries": 0, "passed": 0, "score_sum": 0.0, "ticks_sum": 0}
    )
    for row in rows_all:
        key = (row["seed"], row["config"])
        agg[key]["queries"] += 1
        agg[key]["passed"] += 1 if row["passed"] else 0
        agg[key]["score_sum"] += row["score"]
        agg[key]["ticks_sum"] += row["ticks"]

    print(
        f"{'Seed':>6} | {'Config':>25} | {'Queries':>8} | {'Pass':>6} | {'Pass%':>6} | {'AvgScore':>8} | {'AvgTicks':>8}"
    )
    print("-" * 90)
    for (seed, config), data in sorted(agg.items()):
        q = data["queries"]
        p = data["passed"]
        print(
            f"{seed:>6} | {config:>25} | {q:>8} | {p:>6} | {100 * p / q:>5.1f}% | "
            f"{data['score_sum'] / q:>8.3f} | {data['ticks_sum'] / q:>8.1f}"
        )

    # Inspection skills/protocols
    print("\n=== SKILLS ACCUMULÉS ===")
    sys.path.insert(0, str(REPO_ROOT))
    from core.marker_store import MarkerStore

    skills_store = MarkerStore(
        db_path=REPO_ROOT / "pheromones/skills.db",
        session_isolation=False,
        traceability=False,
    )
    skills = skills_store.query_markers(marker_type="skill")
    print(f"Total skills : {len(skills)}")
    for sk in skills[:5]:
        print(
            f"  - {sk.id} (intensity={sk.intensity:.3f}, uses={sk.payload.get('usage_count', 0)})"
        )

    print("\n=== PROTOCOLS PERSISTÉS ===")
    protocol_store = MarkerStore(
        db_path=REPO_ROOT / "pheromones/protocols.db",
        session_isolation=False,
        traceability=False,
    )
    protocols = protocol_store.query_markers(marker_type="coordination_protocol")
    print(f"Total protocols : {len(protocols)}")
    for p in protocols:
        print(f"  - {p.id} (score={p.payload.get('score', 'N/A')})")

    # Export JSON
    export_path = REPO_ROOT / "notebooks/sprint9_campaign_results.json"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    with open(export_path, "w") as f:
        json.dump(
            {
                "adapt": {str(k): v for k, v in adapt_results.items()},
                "eval": {str(k): v for k, v in eval_results.items()},
            },
            f,
            indent=2,
            default=str,
        )

    print(f"\nRésultats exportés vers {export_path}")
