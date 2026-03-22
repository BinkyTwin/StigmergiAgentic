"""Patch a cloned SwarmAgentic TravelPlanner workspace for OpenRouter runs."""

from __future__ import annotations

import argparse
from pathlib import Path


MODEL_HELP_BLOCK = """    parser.add_argument('--model', type=str, default='gpt-4o-mini',
                       choices=['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo-2024-04-09', 'gpt-3.5-turbo-0125'],
                       help='LLM model to use')
"""

MODEL_HELP_REPLACEMENT = """    parser.add_argument('--model', type=str, default='openai/gpt-4o',
                       help='LLM model to use (for OpenRouter, prefer fully qualified ids such as openai/gpt-4o)')
    parser.add_argument('--extract_model', type=str, default=None,
                       help='Optional extraction model override; defaults to --model when omitted')
"""

MAIN_CALL_BLOCK = """        particle_idx=args.particle_idx,
        model=args.model,
        save_dir=args.save_dir,
        start_index=args.start_index,
        end_index=args.end_index,
        max_workers=args.max_workers,
        dataset_path=args.dataset,
        ref_info_path=args.ref_info,
        aggregate_folder=args.aggregate_folder
    ))
"""

MAIN_CALL_REPLACEMENT = """        particle_idx=args.particle_idx,
        model=args.model,
        save_dir=args.save_dir,
        start_index=args.start_index,
        end_index=args.end_index,
        max_workers=args.max_workers,
        dataset_path=args.dataset,
        ref_info_path=args.ref_info,
        aggregate_folder=args.aggregate_folder,
        extract_model=args.extract_model
    ))
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Patch SwarmAgentic TravelPlanner test.py for controlled OpenRouter use"
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        required=True,
        help="Path to a cloned SwarmAgenticCode repository",
    )
    return parser.parse_args()


def patch_test_script(test_path: Path) -> None:
    text = test_path.read_text(encoding="utf-8")

    if "def resolve_model_name(model_name: str) -> str:" not in text:
        anchor = "from eval import evaluate, get_scores\n"
        helper = """

def resolve_model_name(model_name: str) -> str:
    alias_map = {
        "gpt-4o": "openai/gpt-4o",
        "gpt-4o-mini": "openai/gpt-4o-mini",
        "gpt-4-turbo-2024-04-09": "openai/gpt-4-turbo",
        "gpt-3.5-turbo-0125": "openai/gpt-3.5-turbo-0125",
    }
    return alias_map.get(model_name, model_name)
"""
        if anchor not in text:
            raise ValueError(f"Unable to locate import anchor in {test_path}")
        text = text.replace(anchor, anchor + helper, 1)

    old_signature = """async def main(particle_idx=-1, model='gpt-4o-mini', save_dir='evaluation/test', 
               start_index=0, end_index=None, max_workers=16,
               dataset_path=r'data/validation.jsonl',
               ref_info_path=r'data/validation_ref_info.jsonl',
               aggregate_folder=None):
"""
    new_signature = """async def main(particle_idx=-1, model='openai/gpt-4o', save_dir='evaluation/test', 
               start_index=0, end_index=None, max_workers=16,
               dataset_path=r'data/validation.jsonl',
               ref_info_path=r'data/validation_ref_info.jsonl',
               aggregate_folder=None, extract_model=None):
"""
    if old_signature in text:
        text = text.replace(old_signature, new_signature, 1)

    text = text.replace(
        "    llm_role = ChatOpenAI(model=model, temperature=0.001)\n"
        '    llm_extract = ChatOpenAI(model="gpt-4o-mini")  # Fixed model for extraction\n',
        "    llm_role = ChatOpenAI(model=resolve_model_name(model), temperature=0.001)\n"
        "    llm_extract = ChatOpenAI(\n"
        "        model=resolve_model_name(extract_model or model),\n"
        "        temperature=0.001,\n"
        "    )\n",
        1,
    )

    if MODEL_HELP_BLOCK in text:
        text = text.replace(MODEL_HELP_BLOCK, MODEL_HELP_REPLACEMENT, 1)
    if MAIN_CALL_BLOCK in text:
        text = text.replace(MAIN_CALL_BLOCK, MAIN_CALL_REPLACEMENT, 1)

    test_path.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.expanduser().resolve()
    test_path = repo_root / "travelplanner" / "swarm" / "test.py"
    if not test_path.exists():
        raise FileNotFoundError(f"SwarmAgentic TravelPlanner test.py not found: {test_path}")

    patch_test_script(test_path)
    print(f"patched {test_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
