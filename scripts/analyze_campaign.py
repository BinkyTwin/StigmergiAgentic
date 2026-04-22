#!/usr/bin/env python3
"""Analyse les résultats d'une campagne Sprint 9.

Usage:
    uv run python scripts/analyze_campaign.py [campaign_dir]

Exemple:
    uv run python scripts/analyze_campaign.py campaign_results
    uv run python scripts/analyze_campaign.py docker_results
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path


def parse_results(phase_dir: Path) -> dict[int, dict]:
    """Parse all query JSON files from one phase directory."""
    results = {}
    if not phase_dir.exists():
        return results
    for f in sorted(phase_dir.glob("query_*.json")):
        text = f.read_text()
        # Find last JSON block in file
        for idx in range(text.rfind("}"), -1, -1):
            if text[idx] == "{":
                try:
                    data = json.loads(text[idx:])
                    q = int(f.stem.split("_")[1])
                    results[q] = data
                    break
                except (json.JSONDecodeError, ValueError, IndexError):
                    continue
    return results


def summarize(results: dict[int, dict], label: str) -> dict | None:
    if not results:
        print(f"\n{label}: Aucun résultat")
        return None

    passed = sum(
        1
        for d in results.values()
        if d.get("evaluation", {}).get("final_pass_rate", 0) > 0
    )
    total = len(results)
    scores = [
        d.get("evaluation", {}).get("final_pass_rate", 0.0) for d in results.values()
    ]
    avg_score = sum(scores) / len(scores) if scores else 0

    stop_reasons = defaultdict(int)
    for d in results.values():
        sr = d.get("stop_reason", "unknown")
        stop_reasons[sr] += 1

    pu = [
        d.get("emergence_summary", {}).get("parallel_utilization", 0)
        for d in results.values()
    ]
    ct = [
        d.get("emergence_summary", {}).get("convergence_tick", 0)
        for d in results.values()
    ]
    avg_pu = sum(pu) / len(pu) if pu else 0
    avg_ct = sum(ct) / len(ct) if ct else 0

    delivered = sum(
        1
        for d in results.values()
        if any(
            qr.get("delivered", False)
            for qr in d.get("evaluation", {}).get("query_results", [])
        )
    )

    print(f"\n{'=' * 60}")
    print(label)
    print(f"{'=' * 60}")
    print(f"  Queries évaluées : {total}")
    print(f"  Pass rate        : {passed}/{total} ({100 * passed / total:.1f}%)")
    print(f"  Delivery rate    : {delivered}/{total} ({100 * delivered / total:.1f}%)")
    print(f"  Score moyen      : {avg_score:.3f}")
    print(f"  Parallel util.   : {avg_pu:.3f}")
    print(f"  Convergence tick : {avg_ct:.1f}")
    print(f"  Stop reasons     : {dict(stop_reasons)}")

    # Détail par query
    print("  Détail par query:")
    for q in sorted(results.keys())[:10]:  # Limit to first 10
        d = results[q]
        p = d.get("evaluation", {}).get("final_pass_rate", 0) > 0
        s = d.get("evaluation", {}).get("final_pass_rate", 0.0)
        sr = d.get("stop_reason", "N/A")
        t = d.get("total_ticks", 0)
        print(f"    Q{q}: pass={p}, score={s:.2f}, stop={sr}, ticks={t}")
    if len(results) > 10:
        print(f"    ... et {len(results) - 10} autres queries")

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


def main() -> int:
    campaign_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("campaign_results")

    print(f"=== ANALYSE CAMPAGNE: {campaign_dir} ===")

    adapt = parse_results(campaign_dir / "adapt")
    c2 = parse_results(campaign_dir / "c2")
    c3 = parse_results(campaign_dir / "c3")
    baseline = parse_results(campaign_dir / "baseline")

    summarize(adapt, "PHASE 1 : ADAPTATION (queries d'entraînement)")
    summarize(c2, "PHASE 2 : C2 ÉVALUATION (skills read-only)")
    summarize(c3, "PHASE 3 : C3 ÉVALUATION (skills + cross-run)")
    summarize(baseline, "PHASE 4 : BASELINE (sans skills ni cross-run)")

    # Comparaison directe
    print(f"\n{'=' * 60}")
    print("COMPARAISON C2 vs C3 vs BASELINE (même test set)")
    print(f"{'=' * 60}")

    common_queries = sorted(set(c2.keys()) & set(c3.keys()) & set(baseline.keys()))
    if common_queries:
        print("\nDétail par query:")
        for q in common_queries[:10]:
            c2_pass = c2[q].get("evaluation", {}).get("final_pass_rate", 0) > 0
            c3_pass = c3[q].get("evaluation", {}).get("final_pass_rate", 0) > 0
            base_pass = baseline[q].get("evaluation", {}).get("final_pass_rate", 0) > 0
            c2_score = c2[q].get("evaluation", {}).get("final_pass_rate", 0.0)
            c3_score = c3[q].get("evaluation", {}).get("final_pass_rate", 0.0)
            base_score = baseline[q].get("evaluation", {}).get("final_pass_rate", 0.0)
            winner = (
                "C2"
                if c2_pass and not c3_pass and not base_pass
                else "C3"
                if c3_pass and not c2_pass and not base_pass
                else "Base"
                if base_pass and not c2_pass and not c3_pass
                else "Multiple/Aucun"
            )
            print(
                f"  Q{q}: C2={c2_pass}({c2_score:.2f}) | C3={c3_pass}({c3_score:.2f}) | Base={base_pass}({base_score:.2f}) → {winner}"
            )
        if len(common_queries) > 10:
            print(f"  ... et {len(common_queries) - 10} autres queries")

        c3_beats_c2 = sum(
            1
            for q in common_queries
            if c3[q].get("evaluation", {}).get("final_pass_rate", 0) > 0
            and not c2[q].get("evaluation", {}).get("final_pass_rate", 0) > 0
        )
        c2_beats_c3 = sum(
            1
            for q in common_queries
            if c2[q].get("evaluation", {}).get("final_pass_rate", 0) > 0
            and not c3[q].get("evaluation", {}).get("final_pass_rate", 0) > 0
        )
        base_beats_both = sum(
            1
            for q in common_queries
            if baseline[q].get("evaluation", {}).get("final_pass_rate", 0) > 0
            and not c2[q].get("evaluation", {}).get("final_pass_rate", 0) > 0
            and not c3[q].get("evaluation", {}).get("final_pass_rate", 0) > 0
        )
        print(f"\n  C3 bat C2 seul : {c3_beats_c2} queries")
        print(f"  C2 bat C3 seul : {c2_beats_c3} queries")
        print(f"  Base bat les 2 : {base_beats_both} queries")

    # Export JSON
    export_path = campaign_dir / "sprint9_scientific_results.json"
    export_data = {
        "adapt": {str(k): v for k, v in adapt.items()},
        "c2": {str(k): v for k, v in c2.items()},
        "c3": {str(k): v for k, v in c3.items()},
        "baseline": {str(k): v for k, v in baseline.items()},
    }
    with open(export_path, "w") as f:
        json.dump(export_data, f, indent=2, default=str)
    print(f"\nRésultats exportés : {export_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
