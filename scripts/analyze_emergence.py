"""Analyse des comportements émergents à partir des résultats de benchmark.

Usage:
    python scripts/analyze_emergence.py output/travelplanner_framework_compare/v5_full/seed42
    python scripts/analyze_emergence.py run1/ run2/ run3/   # compare plusieurs runs
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean, stdev


EMERGENCE_KEYS = [
    "convergence_tick",
    "collaboration_density",
    "pressure_entropy",
    "colony_specialization",
    "action_switching_rate",
    "parallel_utilization",
    "lock_contention_rate",
    "specialization_entropy",
]


def load_queries(run_dir: Path) -> list[dict]:
    queries_dir = run_dir / "queries"
    results = []
    for f in sorted(queries_dir.glob("query_*.json")):
        try:
            results.append(json.loads(f.read_text()))
        except Exception:
            pass
    return results


def extract_metrics(queries: list[dict]) -> dict:
    emergence: dict[str, list] = {k: [] for k in EMERGENCE_KEYS}
    stop_reasons: dict[str, int] = {}
    total_ticks: list[int] = []
    final_passes = 0

    for q in queries:
        summary = q.get("summary", {})

        # stop reason
        reason = str(summary.get("stop_reason", "unknown"))
        stop_reasons[reason] = stop_reasons.get(reason, 0) + 1

        # ticks
        ticks = summary.get("total_ticks")
        if isinstance(ticks, int):
            total_ticks.append(ticks)

        # emergence metrics
        em = summary.get("emergence", {})
        for k in EMERGENCE_KEYS:
            v = em.get(k)
            if isinstance(v, (int, float)):
                emergence[k].append(float(v))

        # final pass
        if q.get("final_pass"):
            final_passes += 1

    n = len(queries)
    return {
        "n_queries": n,
        "final_pass_rate": round(final_passes / n * 100, 1) if n else 0,
        "stop_reasons": stop_reasons,
        "ticks": {
            "mean": round(mean(total_ticks), 1) if total_ticks else 0,
            "max": max(total_ticks) if total_ticks else 0,
            "min": min(total_ticks) if total_ticks else 0,
            "stdev": round(stdev(total_ticks), 1) if len(total_ticks) > 1 else 0,
        },
        "emergence": {
            k: {
                "mean": round(mean(v), 4) if v else None,
                "stdev": round(stdev(v), 4) if len(v) > 1 else None,
                "min": round(min(v), 4) if v else None,
                "max": round(max(v), 4) if v else None,
            }
            for k, v in emergence.items()
            if v
        },
    }


def print_report(label: str, metrics: dict) -> None:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  Queries analysées : {metrics['n_queries']}")
    print(f"  Final pass rate   : {metrics['final_pass_rate']}%")

    print(f"\n  Stop reasons :")
    for reason, count in sorted(metrics["stop_reasons"].items(), key=lambda x: -x[1]):
        pct = round(count / metrics["n_queries"] * 100, 1)
        print(f"    {reason:<30} {count:>4}  ({pct}%)")

    t = metrics["ticks"]
    print(f"\n  Ticks par query :")
    print(f"    moyenne={t['mean']}  min={t['min']}  max={t['max']}  écart-type={t['stdev']}")

    print(f"\n  Métriques d'émergence :")
    em = metrics["emergence"]
    labels = {
        "convergence_tick":       "Tick de convergence      ",
        "collaboration_density":  "Densité collaboration    ",
        "pressure_entropy":       "Entropie des pressions   ",
        "colony_specialization":  "Spécialisation colonie   ",
        "action_switching_rate":  "Taux de changement action",
        "parallel_utilization":   "Utilisation parallèle    ",
        "lock_contention_rate":   "Contention verrous       ",
        "specialization_entropy": "Entropie spécialisation  ",
    }
    for k, lbl in labels.items():
        if k in em:
            v = em[k]
            print(f"    {lbl}  moy={v['mean']:<8}  σ={v['stdev']}")


def print_comparison(runs: dict[str, dict]) -> None:
    if len(runs) < 2:
        return

    print(f"\n{'='*60}")
    print("  COMPARAISON ENTRE RUNS")
    print(f"{'='*60}")

    labels_short = list(runs.keys())
    # header
    col = 28
    header = "  Métrique" + " " * (col - 9)
    for lbl in labels_short:
        short = lbl[-18:] if len(lbl) > 18 else lbl
        header += f"  {short:>18}"
    print(header)
    print("  " + "-" * (col + 20 * len(labels_short)))

    # final pass
    row = f"  {'final_pass_rate':<{col}}"
    for m in runs.values():
        row += f"  {m['final_pass_rate']:>17.1f}%"
    print(row)

    # ticks moyen
    row = f"  {'ticks (moyenne)':<{col}}"
    for m in runs.values():
        row += f"  {m['ticks']['mean']:>18}"
    print(row)

    # stop reasons
    all_reasons = set()
    for m in runs.values():
        all_reasons.update(m["stop_reasons"].keys())
    for reason in sorted(all_reasons):
        row = f"  {('stop:' + reason):<{col}}"
        for m in runs.values():
            count = m["stop_reasons"].get(reason, 0)
            pct = round(count / m["n_queries"] * 100, 1)
            row += f"  {str(count) + ' (' + str(pct) + '%)':>18}"
        print(row)

    # emergence metrics
    all_em_keys = set()
    for m in runs.values():
        all_em_keys.update(m["emergence"].keys())
    for k in EMERGENCE_KEYS:
        if k not in all_em_keys:
            continue
        short_label = {
            "convergence_tick": "convergence_tick",
            "collaboration_density": "collaboration_density",
            "pressure_entropy": "pressure_entropy",
            "colony_specialization": "colony_specialization",
            "action_switching_rate": "action_switching_rate",
            "parallel_utilization": "parallel_utilization",
            "lock_contention_rate": "lock_contention_rate",
            "specialization_entropy": "specialization_entropy",
        }.get(k, k)
        row = f"  {short_label:<{col}}"
        for m in runs.values():
            em = m["emergence"].get(k)
            val = f"{em['mean']}" if em else "N/A"
            row += f"  {val:>18}"
        print(row)


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print("Usage: python scripts/analyze_emergence.py <run_dir> [run_dir2 ...]")
        print("Example: python scripts/analyze_emergence.py output/travelplanner_framework_compare/v5_full/seed42")
        sys.exit(1)

    runs: dict[str, dict] = {}
    for arg in args:
        path = Path(arg)
        if not path.is_dir():
            print(f"[WARN] Dossier introuvable : {path}")
            continue
        queries = load_queries(path)
        if not queries:
            print(f"[WARN] Aucune query trouvée dans : {path}")
            continue
        label = path.name
        metrics = extract_metrics(queries)
        runs[label] = metrics
        print_report(label, metrics)

    if len(runs) >= 2:
        print_comparison(runs)


if __name__ == "__main__":
    main()
