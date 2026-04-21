#!/usr/bin/env python3
"""Run Sprint 9 campaign for ONE seed (no multiprocessing, no notebook).

Usage (Terminal 1):
    OPENROUTER_API_KEY=$(grep OPENROUTER_API_KEY .env | cut -d= -f2) uv run python scripts/run_one_seed.py --seed 42

Usage (Terminal 2):
    OPENROUTER_API_KEY=$(grep OPENROUTER_API_KEY .env.key2 | cut -d= -f2) uv run python scripts/run_one_seed.py --seed 43
"""

from __future__ import annotations

import argparse
import io
import contextlib
import json
import os
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
os.chdir(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT))

import main
from core.marker_store import MarkerStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one seed of Sprint 9 campaign")
    parser.add_argument(
        "--seed", type=int, required=True, help="Random seed (42 or 43)"
    )
    parser.add_argument(
        "--queries", type=int, default=5, help="Number of queries to run"
    )
    parser.add_argument("--query-start", type=int, default=0)
    parser.add_argument(
        "--adapt-config", type=str, default="config/travelplanner_adapt.yaml"
    )
    parser.add_argument(
        "--eval-config", type=str, default="config/travelplanner_eval.yaml"
    )
    return parser.parse_args()


def run_queries(
    seed: int, config_path: str, query_start: int, query_end: int, markers_db_name: str
) -> list[dict]:
    """Run a batch of queries for one seed and config."""
    # Monkey-patch la DB de session pour ce seed
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
            f"  [seed {seed}] Query {query_idx} ({Path(config_path).name}) → exit={exit_code}, summary={'OK' if summary else 'MISSING'}"
        )

    return results


def _run_campaign() -> int:
    args = parse_args()
    seed = args.seed

    # Nettoyage de la DB de session pour ce seed
    db_path = REPO_ROOT / f"pheromones/markers_seed{seed}.db"
    if db_path.exists():
        db_path.unlink()
        print(f"Removed old {db_path}")

    print(f"\n=== SEED {seed} ===")
    print(f"Queries: {args.query_start} → {args.query_start + args.queries - 1}")

    # Phase 1: Adaptation
    print("\n--- Phase 1: ADAPTATION ---")
    adapt_results = run_queries(
        seed,
        args.adapt_config,
        args.query_start,
        args.query_start + args.queries,
        f"markers_seed{seed}.db",
    )

    # Phase 2: Evaluation figée
    print("\n--- Phase 2: EVALUATION FIGÉE ---")
    eval_results = run_queries(
        seed,
        args.eval_config,
        args.query_start,
        args.query_start + args.queries,
        f"markers_seed{seed}_eval.db",
    )

    # Analyse
    print("\n--- RÉSULTATS ---")

    def summarize(results):
        total = len(results)
        passed = sum(
            1
            for r in results
            if (r.get("summary") or {}).get("evaluation", {}).get("passed", False)
        )
        scores = [
            (r.get("summary") or {}).get("evaluation", {}).get("score", 0.0)
            for r in results
        ]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        return total, passed, avg_score

    adapt_total, adapt_passed, adapt_score = summarize(adapt_results)
    eval_total, eval_passed, eval_score = summarize(eval_results)

    print(
        f"Adapt  : {adapt_passed}/{adapt_total} passed ({100 * adapt_passed / adapt_total:.1f}%), avg score = {adapt_score:.3f}"
    )
    print(
        f"Eval   : {eval_passed}/{eval_total} passed ({100 * eval_passed / eval_total:.1f}%), avg score = {eval_score:.3f}"
    )

    # Inspection skills/protocols
    print("\n--- SKILLS ACCUMULÉS ---")
    skills_store = MarkerStore(
        db_path=REPO_ROOT / "pheromones/skills.db",
        session_isolation=False,
        traceability=False,
    )
    skills = skills_store.query_markers(marker_type="skill")
    print(f"Total skills: {len(skills)}")
    for sk in skills[:5]:
        print(
            f"  - {sk.id} (intensity={sk.intensity:.3f}, uses={sk.payload.get('usage_count', 0)})"
        )

    print("\n--- PROTOCOLS PERSISTÉS ---")
    protocol_store = MarkerStore(
        db_path=REPO_ROOT / "pheromones/protocols.db",
        session_isolation=False,
        traceability=False,
    )
    protocols = protocol_store.query_markers(marker_type="coordination_protocol")
    print(f"Total protocols: {len(protocols)}")
    for p in protocols:
        print(f"  - {p.id} (score={p.payload.get('score', 'N/A')})")

    # Export
    export_path = REPO_ROOT / f"notebooks/sprint9_seed{seed}_results.json"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    with open(export_path, "w") as f:
        json.dump(
            {"adapt": adapt_results, "eval": eval_results}, f, indent=2, default=str
        )
    print(f"\nExporté: {export_path}")

    return 0


if __name__ == "__main__":
    sys.exit(_run_campaign())
