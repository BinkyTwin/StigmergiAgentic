#!/usr/bin/env python3
"""Run the local PaperBanana pipeline for a memoir figure."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[2]
PAPERBANANA_DIR = ROOT / "vendor" / "PaperBanana"
LATEX_IMAGES_DIR = REPO_ROOT / "documentation" / "memoire" / "latex" / "images"
RECORDS_DIR = ROOT / "records"
FRANCESTUDENT_BASE_URL = "https://api.francestudent.org/v1"


def load_dotenv(path: Path, env: dict[str, str]) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in env:
            env[key] = value.strip().strip('"').strip("'")


def paperbanana_env() -> dict[str, str]:
    env = dict(os.environ)
    load_dotenv(REPO_ROOT / ".env", env)
    api_key = env.get("IMAGEN") or env.get("FRANCESTUDENT_API_KEY") or env.get("OPENAI_API_KEY")
    if api_key:
        env["OPENAI_API_KEY"] = api_key
    env.setdefault("OPENAI_BASE_URL", FRANCESTUDENT_BASE_URL)
    env.setdefault("OPENAI_TEXT_ENDPOINT", "responses")
    env.setdefault("MAIN_MODEL_NAME", "gpt-5.5")
    env.setdefault("IMAGE_GEN_MODEL_NAME", "gpt-image-2")
    env.setdefault("PAPERBANANA_DIAGRAM_REF_LIMIT", "40")
    env.setdefault("PAPERBANANA_SKIP_CYBER_REFERENCES", "1")
    return env


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a memoir figure with PaperBanana.")
    parser.add_argument("--name", required=True, help="Output stem, e.g. boucle_stigmergique")
    parser.add_argument("--content", default="", help="Method/context text to visualize")
    parser.add_argument("--content-file", default="", help="Path to a Markdown/text context file")
    parser.add_argument("--caption", required=True, help="Figure caption / visual intent")
    parser.add_argument("--task", choices=["diagram", "plot"], default="diagram")
    parser.add_argument("--aspect-ratio", choices=["21:9", "16:9", "3:2"], default="16:9")
    parser.add_argument("--num-candidates", type=int, default=1)
    parser.add_argument("--max-critic-rounds", type=int, default=1)
    parser.add_argument("--retrieval-setting", choices=["auto", "manual", "random", "none"], default="none")
    parser.add_argument("--exp-mode", choices=["demo_full", "demo_planner_critic"], default="demo_full")
    parser.add_argument("--main-model-name", default="gpt-5.5")
    parser.add_argument("--image-gen-model-name", default="gpt-image-2")
    parser.add_argument("--output-dir", default=str(LATEX_IMAGES_DIR))
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--diagram-ref-limit", type=int, default=40)
    parser.add_argument("--skip-cyber-references", choices=["0", "1"], default="1")
    return parser.parse_args()


def paperbanana_python() -> Path:
    local_python = PAPERBANANA_DIR / ".venv" / "bin" / "python"
    if local_python.exists():
        return local_python
    return Path(sys.executable)


def main() -> int:
    args = parse_args()
    if not PAPERBANANA_DIR.exists():
        print(
            "PaperBanana is not installed locally. Run "
            "python3 documentation/memoire/image_generation/setup_paperbanana_francestudent.py",
            file=sys.stderr,
        )
        return 1

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{args.name}.png"

    command = [
        str(paperbanana_python()),
        str(PAPERBANANA_DIR / "skill" / "run.py"),
        "--caption",
        args.caption,
        "--task",
        args.task,
        "--output",
        str(output_path),
        "--aspect-ratio",
        args.aspect_ratio,
        "--max-critic-rounds",
        str(args.max_critic_rounds),
        "--num-candidates",
        str(args.num_candidates),
        "--retrieval-setting",
        args.retrieval_setting,
        "--exp-mode",
        args.exp_mode,
        "--main-model-name",
        args.main_model_name,
        "--image-gen-model-name",
        args.image_gen_model_name,
    ]
    if args.content_file:
        command.extend(["--content-file", str(Path(args.content_file).resolve())])
    else:
        command.extend(["--content", args.content])

    env = paperbanana_env()
    env["PAPERBANANA_DIAGRAM_REF_LIMIT"] = str(args.diagram_ref_limit)
    env["PAPERBANANA_SKIP_CYBER_REFERENCES"] = args.skip_cyber_references

    process = subprocess.Popen(
        command,
        cwd=PAPERBANANA_DIR,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    stdout_chunks: list[str] = []
    try:
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="")
            stdout_chunks.append(line)
        returncode = process.wait(timeout=args.timeout_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        timeout_line = f"\nERROR: PaperBanana timed out after {args.timeout_seconds} seconds.\n"
        print(timeout_line, end="")
        stdout_chunks.append(timeout_line)
        returncode = 124

    RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    record_path = RECORDS_DIR / f"{args.name}.json"
    record = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "name": args.name,
        "caption": args.caption,
        "content_file": str(Path(args.content_file).resolve()) if args.content_file else "",
        "output_path": str(output_path),
        "task": args.task,
        "aspect_ratio": args.aspect_ratio,
        "num_candidates": args.num_candidates,
        "max_critic_rounds": args.max_critic_rounds,
        "retrieval_setting": args.retrieval_setting,
        "exp_mode": args.exp_mode,
        "main_model_name": args.main_model_name,
        "image_gen_model_name": args.image_gen_model_name,
        "diagram_ref_limit": args.diagram_ref_limit,
        "skip_cyber_references": args.skip_cyber_references,
        "returncode": returncode,
        "stdout": "".join(stdout_chunks),
    }
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Record: {record_path}")
    if output_path.exists():
        print(f"Image: {output_path}")
    return returncode


if __name__ == "__main__":
    sys.exit(main())
