"""Aggregate MigrationBench campaigns with manifest-driven denominators."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("output/migrationbench_comparison"))
    parser.add_argument("--reference-framework", type=str, default="stigmergic_v6_static")
    return parser.parse_args()


def load_campaign(campaign_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest_path = campaign_dir / "campaign_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    runs_path = campaign_dir / "runs.json"
    runs = json.loads(runs_path.read_text(encoding="utf-8")).get("runs", []) if runs_path.exists() else []
    rows_by_id = {row.get("instance_id"): row for row in runs if isinstance(row, dict)}
    rows: list[dict[str, Any]] = []
    for instance in manifest.get("instances", []):
        instance_id = instance.get("instance_id", "")
        row = rows_by_id.get(instance_id)
        if row is None:
            row = {
                "instance_id": instance_id,
                "framework": manifest.get("framework", ""),
                "provider": manifest.get("provider", ""),
                "model": manifest.get("model", ""),
                "seed": manifest.get("seed", 42),
                "artifact_delivered": False,
                "patch_delivered": False,
                "patch_applies": False,
                "official_success": False,
                "strict_success": False,
                "failure_reason": "missing_output",
                "tokens_total": 0,
                "cost_total_usd": 0.0,
                "runtime_seconds": 0.0,
                "coordination_overhead": 0,
                "instance": instance,
            }
        row.setdefault("framework", manifest.get("framework", ""))
        row.setdefault("provider", manifest.get("provider", ""))
        row.setdefault("model", manifest.get("model", ""))
        row.setdefault("instance", instance)
        rows.append(row)
    return manifest, rows


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    denom = len(rows) or 1
    strict = sum(1 for row in rows if row.get("strict_success"))
    return {
        "requested_instances": len(rows),
        "strict_successes": strict,
        "strict_success_rate": strict / denom,
        "artifact_delivery_rate": sum(1 for row in rows if row.get("artifact_delivered")) / denom,
        "patch_applies_rate": sum(1 for row in rows if row.get("patch_applies")) / denom,
        "official_success_rate": sum(1 for row in rows if row.get("official_success")) / denom,
        "tokens_total": sum(int(row.get("tokens_total", 0) or 0) for row in rows),
        "cost_total_usd": round(sum(float(row.get("cost_total_usd", 0.0) or 0.0) for row in rows), 6),
        "runtime_total_seconds": round(sum(float(row.get("runtime_seconds", 0.0) or 0.0) for row in rows), 4),
        "failure_reasons": dict(sorted(Counter(str(row.get("failure_reason", "ok")) for row in rows).items())),
    }


def paired_counts(reference: list[dict[str, Any]], baseline: list[dict[str, Any]]) -> dict[str, int | float]:
    ref = {row["instance_id"]: bool(row.get("strict_success")) for row in reference}
    base = {row["instance_id"]: bool(row.get("strict_success")) for row in baseline}
    ids = sorted(set(ref) & set(base))
    b = sum(1 for instance_id in ids if ref[instance_id] and not base[instance_id])
    c = sum(1 for instance_id in ids if not ref[instance_id] and base[instance_id])
    both_pass = sum(1 for instance_id in ids if ref[instance_id] and base[instance_id])
    both_fail = sum(1 for instance_id in ids if not ref[instance_id] and not base[instance_id])
    return {
        "paired_instances": len(ids),
        "reference_pass_baseline_fail": b,
        "reference_fail_baseline_pass": c,
        "both_pass": both_pass,
        "both_fail": both_fail,
        "discordant_pairs": b + c,
        "mcnemar_exact_p": mcnemar_exact_p(b, c),
    }


def mcnemar_exact_p(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value via binomial tail."""
    n = int(b) + int(c)
    if n == 0:
        return 1.0
    observed = min(int(b), int(c))
    tail = sum(math.comb(n, k) for k in range(0, observed + 1)) / (2**n)
    return min(1.0, 2.0 * tail)


def bootstrap_ci(rows: list[dict[str, Any]], *, samples: int = 2000, seed: int = 42) -> list[float]:
    if not rows:
        return [0.0, 0.0]
    rng = random.Random(seed)
    n = len(rows)
    rates: list[float] = []
    for _ in range(samples):
        sample = [rows[rng.randrange(n)] for _ in range(n)]
        rates.append(sum(1 for row in sample if row.get("strict_success")) / n)
    rates.sort()
    lo = rates[int(0.025 * (samples - 1))]
    hi = rates[int(0.975 * (samples - 1))]
    return [lo, hi]


def write_rows_csv(rows_by_framework: dict[str, list[dict[str, Any]]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "framework",
        "provider",
        "model",
        "instance_id",
        "strict_success",
        "artifact_delivered",
        "patch_applies",
        "official_success",
        "tokens_total",
        "cost_total_usd",
        "runtime_seconds",
        "failure_reason",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for framework, rows in sorted(rows_by_framework.items()):
            for row in rows:
                writer.writerow({key: row.get(key, "") for key in fieldnames})


def main() -> int:
    args = parse_args()
    campaign_dirs = [
        path
        for path in sorted(args.campaign_root.iterdir())
        if (path / "campaign_manifest.json").exists()
    ]
    rows_by_framework: dict[str, list[dict[str, Any]]] = {}
    manifests: dict[str, dict[str, Any]] = {}
    for campaign_dir in campaign_dirs:
        manifest, rows = load_campaign(campaign_dir)
        framework = str(manifest.get("framework", campaign_dir.name))
        rows_by_framework[framework] = rows
        manifests[framework] = manifest

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_rows_csv(rows_by_framework, args.output_dir / "per_instance.csv")

    aggregates: dict[str, Any] = {}
    for framework, rows in rows_by_framework.items():
        aggregates[framework] = summarize_rows(rows)
        aggregates[framework]["strict_success_bootstrap_95ci"] = bootstrap_ci(rows)

    pairs: dict[str, Any] = {}
    reference_rows = rows_by_framework.get(args.reference_framework, [])
    for framework, rows in rows_by_framework.items():
        if framework == args.reference_framework:
            continue
        pairs[framework] = paired_counts(reference_rows, rows)

    payload = {
        "campaign_root": str(args.campaign_root),
        "reference_framework": args.reference_framework,
        "frameworks": sorted(rows_by_framework),
        "aggregates": aggregates,
        "paired_vs_reference": pairs,
        "interpretation_note": (
            "main_30 is directional and underpowered for small effects; "
            "use discordant pair counts and confidence intervals before claiming improvement."
        ),
        "manifests": manifests,
    }
    (args.output_dir / "aggregates.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["aggregates"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
