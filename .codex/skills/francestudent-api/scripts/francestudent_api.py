#!/usr/bin/env python3
"""Small CLI for the FranceStudent OpenAI-compatible API.

Reads secrets from the environment or a local .env file. Never pass the API key
as a command-line argument because CLI args are visible in process listings.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://api.francestudent.org/v1"
DEFAULT_OUT_DIR = Path("output/francestudent_api_tests")
KEY_ENV_ORDER = ("IMAGEN", "FRANCESTUDENT_API_KEY", "OPENAI_API_KEY")


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in os.environ:
            continue
        os.environ[key] = value.strip().strip('"').strip("'")


def api_key() -> str:
    load_dotenv(Path(".env"))
    for env_name in KEY_ENV_ORDER:
        value = os.environ.get(env_name)
        if value:
            return value
    raise SystemExit(f"Missing API key. Set one of: {', '.join(KEY_ENV_ORDER)}")


def request_json(base_url: str, path: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "OpenAI/Python 1.0 Codex-FranceStudent",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", "replace")
        try:
            error_payload = json.loads(error_body)
        except json.JSONDecodeError:
            error_payload = {"message": error_body}
        return {
            "error": error_payload.get("error", error_payload),
            "http_status": exc.code,
        }


def output_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    chunks: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"}:
                chunks.append(content.get("text", ""))
    return "".join(chunks).strip()


def command_text(args: argparse.Namespace) -> int:
    payload: dict[str, Any] = {
        "model": args.model,
        "input": args.prompt,
    }
    optional = {
        "instructions": args.instructions,
        "max_output_tokens": args.max_output_tokens,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "truncation": args.truncation,
        "service_tier": args.service_tier,
    }
    payload.update({key: value for key, value in optional.items() if value is not None})
    if args.reasoning_effort or args.reasoning_summary:
        payload["reasoning"] = {
            key: value
            for key, value in {
                "effort": args.reasoning_effort,
                "summary": args.reasoning_summary,
            }.items()
            if value is not None
        }
    if args.text_verbosity:
        payload["text"] = {"verbosity": args.text_verbosity}

    data = request_json(args.base_url, "/responses", payload, args.timeout)
    if "error" in data:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(
        {
            "id": data.get("id"),
            "status": data.get("status"),
            "model": data.get("model"),
            "output_text": output_text(data),
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


def command_image(args: argparse.Namespace) -> int:
    payload: dict[str, Any] = {
        "model": args.model,
        "prompt": args.prompt,
    }
    optional = {
        "size": args.size,
        "quality": args.quality,
        "output_format": args.output_format,
        "background": args.background,
        "n": args.n,
        "moderation": args.moderation,
        "output_compression": args.output_compression,
    }
    payload.update({key: value for key, value in optional.items() if value is not None})

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    data = request_json(args.base_url, "/images/generations", payload, args.timeout)
    response_path = out_dir / f"{args.name}_response.json"
    response_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if "error" in data:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 1

    items = data.get("data") or []
    if not items:
        print(f"No image data found. Raw response: {response_path}")
        return 1
    image = items[0]
    suffix = args.output_format or "png"
    image_path = out_dir / f"{args.name}.{suffix}"
    if image.get("b64_json"):
        image_path.write_bytes(base64.b64decode(image["b64_json"]))
    elif image.get("url"):
        with urllib.request.urlopen(image["url"], timeout=args.timeout) as response:
            image_path.write_bytes(response.read())
    else:
        print(f"No b64_json or url found. Raw response: {response_path}")
        return 1
    print(json.dumps(
        {
            "response_path": str(response_path.resolve()),
            "image_path": str(image_path.resolve()),
            "image_bytes": image_path.stat().st_size,
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Call the FranceStudent OpenAI-compatible API.")
    root.add_argument("--base-url", default=DEFAULT_BASE_URL)
    subcommands = root.add_subparsers(dest="command", required=True)

    text = subcommands.add_parser("text", help="Call POST /responses.")
    text.add_argument("--prompt", required=True)
    text.add_argument("--model", default="gpt-5.5")
    text.add_argument("--instructions")
    text.add_argument("--max-output-tokens", type=int)
    text.add_argument("--temperature", type=float)
    text.add_argument("--top-p", type=float)
    text.add_argument("--reasoning-effort", choices=["none", "minimal", "low", "medium", "high", "xhigh"])
    text.add_argument("--reasoning-summary", choices=["auto", "concise", "detailed"])
    text.add_argument("--text-verbosity", choices=["low", "medium", "high"])
    text.add_argument("--truncation", choices=["auto", "disabled"])
    text.add_argument("--service-tier")
    text.add_argument("--timeout", type=int, default=60)
    text.set_defaults(func=command_text)

    image = subcommands.add_parser("image", help="Call POST /images/generations.")
    image.add_argument("--prompt", required=True)
    image.add_argument("--model", default="gpt-image-2")
    image.add_argument("--size", default="1024x1024")
    image.add_argument("--quality", choices=["low", "medium", "high", "auto"])
    image.add_argument("--output-format", default="png", choices=["png", "webp", "jpeg"])
    image.add_argument("--background", choices=["opaque", "auto", "transparent"])
    image.add_argument("--n", type=int)
    image.add_argument("--moderation")
    image.add_argument("--output-compression", type=int)
    image.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    image.add_argument("--name", default="francestudent_image")
    image.add_argument("--timeout", type=int, default=180)
    image.set_defaults(func=command_image)
    return root


def main() -> int:
    args = parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
