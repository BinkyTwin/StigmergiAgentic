"""Smoke test direct pour l'API DeepSeek via LLMClient.

Usage (dans le container):
    python scripts/smoke_deepseek.py

Affiche tout en clair — content, usage, cache_hit_tokens, erreurs.
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from llm.client import LLMClient  # noqa: E402


def main() -> int:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    print(f"DEEPSEEK_API_KEY present: {bool(api_key)} (len={len(api_key or '')})")
    if not api_key:
        print("FATAL: DEEPSEEK_API_KEY is empty.", file=sys.stderr)
        return 1

    config = {
        "llm": {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "max_tokens_total": 100_000,
            "temperature": 0.2,
            "retry_attempts": 1,
        }
    }
    print("Creating LLMClient...")
    try:
        client = LLMClient(config)
    except Exception as exc:
        print(f"FATAL: LLMClient init failed: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 2

    print(f"  base_url={client.base_url}")
    print(f"  model={client.model}")
    print(f"  model_pricing={client.model_pricing}")

    prompt = (
        "Return a JSON object with a single key 'ok' set to true. "
        "Return only strict JSON, no preamble."
    )
    print("\nCalling DeepSeek...")
    try:
        response = client.call(prompt=prompt, max_response_tokens=200)
    except Exception as exc:
        print(f"FATAL: call failed: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 3

    print(f"\nSUCCESS")
    print(f"  content: {response.content!r}")
    print(f"  tokens_used: {response.tokens_used}")
    print(f"  cost_usd: {response.cost_usd}")
    print(f"  cache_hit_tokens: {response.prompt_cache_hit_tokens}")
    print(f"  cache_miss_tokens: {response.prompt_cache_miss_tokens}")
    print(f"  latency_ms: {response.latency_ms}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
