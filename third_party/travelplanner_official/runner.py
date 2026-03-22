"""Isolated runner for official TravelPlanner evaluation modules."""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from datasets import load_dataset


ROOT = Path(__file__).resolve().parent
EVAL_DIR = ROOT / "evaluation"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Official TravelPlanner evaluation runner")
    sub = parser.add_subparsers(dest="mode", required=True)

    query = sub.add_parser("query")
    query.add_argument("--database-root", type=Path, required=True)
    query.add_argument("--query-path", type=Path, required=True)
    query.add_argument("--plan-path", type=Path, required=True)

    full = sub.add_parser("full")
    full.add_argument("--database-root", type=Path, required=True)
    full.add_argument("--split", type=str, default="validation")
    full.add_argument("--predictions-path", type=Path, required=True)

    return parser.parse_args()


def ensure_database_link(database_root: Path) -> None:
    db_link = ROOT / "database"
    target = database_root.expanduser().resolve()

    if db_link.is_symlink():
        try:
            current_target = db_link.resolve(strict=True)
        except OSError:
            current_target = None
        if current_target == target:
            return
        db_link.unlink(missing_ok=True)

    if db_link.exists() and not db_link.is_symlink():
        normalize_city_state_file(db_link)
        return

    db_link.symlink_to(target, target_is_directory=True)
    normalize_city_state_file(db_link)


def normalize_city_state_file(database_root: Path) -> None:
    city_state_path = database_root / "background" / "citySet_with_states.txt"
    if not city_state_path.exists():
        return

    lines = city_state_path.read_text(encoding="utf-8").splitlines()
    valid = []
    for line in lines:
        text = line.strip()
        if not text:
            continue
        if "\t" not in text:
            continue
        valid.append(text)
    if not valid:
        return
    city_state_path.write_text("\n".join(valid), encoding="utf-8")


def import_official_modules() -> tuple[Any, Any, Any]:
    root_str = str(ROOT)
    eval_str = str(EVAL_DIR)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    if eval_str not in sys.path:
        sys.path.insert(0, eval_str)

    old_cwd = Path.cwd()
    try:
        os.chdir(EVAL_DIR)
        import commonsense_constraint  # noqa: PLC0415
        import eval as eval_mod  # noqa: PLC0415
        import hard_constraint  # noqa: PLC0415
    finally:
        os.chdir(old_cwd)

    return commonsense_constraint, hard_constraint, eval_mod


def normalize_query_data(query_data: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(query_data)

    local_constraint = normalized.get("local_constraint")
    if isinstance(local_constraint, str):
        try:
            local_constraint = ast.literal_eval(local_constraint)
        except Exception:  # noqa: BLE001
            local_constraint = {}
    if not isinstance(local_constraint, dict):
        local_constraint = {}
    normalized["local_constraint"] = local_constraint

    for key in ("days", "visiting_city_number", "people_number", "budget"):
        try:
            normalized[key] = int(normalized.get(key, 0))
        except Exception:  # noqa: BLE001
            normalized[key] = 0

    return normalized


def extract_bool_and_messages(
    raw: dict[str, tuple[bool | None, str | None]] | None,
) -> tuple[dict[str, bool | None], dict[str, str | None]]:
    if not isinstance(raw, dict):
        return {}, {}

    bools: dict[str, bool | None] = {}
    messages: dict[str, str | None] = {}
    for key, value in raw.items():
        if isinstance(value, tuple) and len(value) >= 2:
            bools[key] = value[0]
            messages[key] = value[1]
        elif isinstance(value, tuple) and len(value) == 1:
            bools[key] = value[0]
            messages[key] = None
        else:
            bools[key] = None
            messages[key] = None
    return bools, messages


def macro_pass(raw: dict[str, tuple[bool | None, str | None]] | None) -> bool:
    if not isinstance(raw, dict):
        return False
    for _, value in raw.items():
        if not isinstance(value, tuple) or len(value) < 1:
            continue
        if value[0] is False:
            return False
    return True


def run_query_mode(args: argparse.Namespace) -> dict[str, Any]:
    ensure_database_link(args.database_root)
    commonsense_mod, hard_mod, _ = import_official_modules()

    query_data = json.loads(args.query_path.read_text(encoding="utf-8"))
    plan = json.loads(args.plan_path.read_text(encoding="utf-8"))

    normalized_query = normalize_query_data(query_data)
    delivered = isinstance(plan, list) and len(plan) > 0

    if not delivered:
        return {
            "delivered": False,
            "commonsense": {
                "is_reasonable_visiting_city": False,
                "is_valid_restaurants": False,
                "is_valid_attractions": False,
                "is_valid_accommodation": False,
                "is_valid_transportation": False,
                "is_valid_information_in_current_city": False,
                "is_valid_information_in_sandbox": False,
                "is_not_absent": False,
            },
            "hard": {
                "valid_cuisine": False,
                "valid_room_rule": False,
                "valid_transportation": False,
                "valid_room_type": False,
                "valid_cost": False,
            },
            "commonsense_messages": {},
            "hard_messages": {},
            "commonsense_macro_pass": False,
            "hard_macro_pass": False,
            "final_pass": False,
            "estimated_cost": 0.0,
        }

    commonsense_raw = commonsense_mod.evaluation(normalized_query, plan)
    commonsense_bool, commonsense_messages = extract_bool_and_messages(commonsense_raw)
    commonsense_macro = macro_pass(commonsense_raw)

    hard_raw = None
    hard_bool = {
        "valid_cuisine": None,
        "valid_room_rule": None,
        "valid_transportation": None,
        "valid_room_type": None,
        "valid_cost": None,
    }
    hard_messages: dict[str, str | None] = {}
    hard_macro = False

    if (
        commonsense_raw
        and commonsense_raw.get("is_not_absent", (False, None))[0] is True
        and commonsense_raw.get("is_valid_information_in_sandbox", (False, None))[0] is True
    ):
        hard_raw = hard_mod.evaluation(normalized_query, plan)
        hard_bool, hard_messages = extract_bool_and_messages(hard_raw)
        hard_macro = macro_pass(hard_raw)

    final_pass = bool(delivered and commonsense_macro and hard_raw is not None and hard_macro)

    try:
        estimated_cost = float(hard_mod.get_total_cost(normalized_query, plan))
    except Exception:  # noqa: BLE001
        estimated_cost = 0.0

    return {
        "delivered": True,
        "commonsense": commonsense_bool,
        "hard": hard_bool,
        "commonsense_messages": commonsense_messages,
        "hard_messages": hard_messages,
        "commonsense_macro_pass": commonsense_macro,
        "hard_macro_pass": hard_macro,
        "final_pass": final_pass,
        "estimated_cost": estimated_cost,
    }


def run_full_mode(args: argparse.Namespace) -> dict[str, Any]:
    ensure_database_link(args.database_root)
    _, _, eval_mod = import_official_modules()

    predictions_raw = json.loads(args.predictions_path.read_text(encoding="utf-8"))
    predictions = {int(k): v for k, v in predictions_raw.items() if str(k).lstrip("-").isdigit()}

    dataset = load_dataset("osunlp/TravelPlanner", args.split)[args.split]
    total = len(dataset)

    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as tmp:
        tmp_path = Path(tmp.name)
        for idx in range(total):
            line = {"plan": predictions.get(idx, [])}
            tmp.write(json.dumps(line, ensure_ascii=True) + "\n")

    try:
        scores, detailed_scores = eval_mod.eval_score(args.split, str(tmp_path))
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass

    return {
        "delivery_rate": float(scores.get("Delivery Rate", 0.0)),
        "commonsense_micro": float(scores.get("Commonsense Constraint Micro Pass Rate", 0.0)),
        "commonsense_macro": float(scores.get("Commonsense Constraint Macro Pass Rate", 0.0)),
        "hard_constraint_micro": float(scores.get("Hard Constraint Micro Pass Rate", 0.0)),
        "hard_constraint_macro": float(scores.get("Hard Constraint Macro Pass Rate", 0.0)),
        "final_pass_rate": float(scores.get("Final Pass Rate", 0.0)),
        "evaluated_queries": int(total),
        "official_detailed": detailed_scores,
    }


def main() -> int:
    args = parse_args()
    if args.mode == "query":
        result = run_query_mode(args)
    elif args.mode == "full":
        result = run_full_mode(args)
    else:
        raise ValueError(f"Unsupported mode: {args.mode}")

    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
