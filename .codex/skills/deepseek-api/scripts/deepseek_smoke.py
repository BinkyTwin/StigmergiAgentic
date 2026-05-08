#!/usr/bin/env python3
"""Secret-safe DeepSeek API smoke tests for this repository."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_MODEL = "deepseek-v4-flash"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a DeepSeek API smoke test.")
    parser.add_argument("--mode", choices=("ping", "tool-call"), default="tool-call")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--trace-dir", type=Path, default=None)
    args = parser.parse_args()

    api_key = _load_secret("DEEPSEEK_API_KEY")
    if not api_key:
        _emit({"ok": False, "error": "DEEPSEEK_API_KEY unavailable"})
        return 2

    if args.mode == "tool-call":
        base_url = "https://api.deepseek.com/beta"
        payload = _tool_call_payload(args.model)
    else:
        base_url = "https://api.deepseek.com"
        payload = _ping_payload(args.model)

    result = _post_chat_completion(
        base_url=base_url,
        payload=payload,
        api_key=api_key,
        timeout=args.timeout,
    )
    if args.trace_dir is not None:
        args.trace_dir.mkdir(parents=True, exist_ok=True)
        (args.trace_dir / "deepseek_smoke.json").write_text(
            json.dumps(_redact(result), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    _emit(_summarize(result, mode=args.mode, base_url=base_url, model=args.model))
    return 0 if result.get("ok") else 1


def _load_secret(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    env_path = Path(".env")
    if not env_path.exists():
        return ""
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        if key.strip() == name:
            return raw_value.strip().strip('"').strip("'")
    return ""


def _ping_payload(model: str) -> dict[str, Any]:
    return {
        "model": model,
        "thinking": {"type": "disabled"},
        "messages": [
            {"role": "system", "content": "Return a short plain-text smoke response."},
            {"role": "user", "content": "Reply with ok."},
        ],
        "max_tokens": 16,
    }


def _tool_call_payload(model: str) -> dict[str, Any]:
    return {
        "model": model,
        "thinking": {"type": "disabled"},
        "messages": [
            {"role": "system", "content": "Return exactly one native function tool call."},
            {"role": "user", "content": "Choose inspect_pom for this smoke test."},
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "choose_next_action",
                    "strict": True,
                    "description": "Choose the next repository inspection action.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["inspect_pom", "read_file"],
                            },
                            "rationale": {"type": "string"},
                        },
                        "required": ["action", "rationale"],
                        "additionalProperties": False,
                    },
                },
            }
        ],
        "tool_choice": "required",
        "parallel_tool_calls": False,
        "temperature": 0,
        "max_tokens": 128,
    }


def _post_chat_completion(
    *,
    base_url: str,
    payload: dict[str, Any],
    api_key: str,
    timeout: float,
) -> dict[str, Any]:
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        return {"ok": True, "response": data}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[-2000:]
        return {"ok": False, "http_status": exc.code, "error": body}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}:{exc}"}


def _summarize(
    result: dict[str, Any],
    *,
    mode: str,
    base_url: str,
    model: str,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "ok": bool(result.get("ok")),
        "mode": mode,
        "model": model,
        "base_url": base_url,
    }
    if not result.get("ok"):
        summary["error"] = str(result.get("error", ""))[:500]
        if "http_status" in result:
            summary["http_status"] = result["http_status"]
        return summary
    response = result["response"]
    choice = (response.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    tool_calls = message.get("tool_calls") or []
    summary.update(
        {
            "response_model": response.get("model"),
            "finish_reason": choice.get("finish_reason"),
            "tool_call_count": len(tool_calls),
            "usage_total_tokens": (response.get("usage") or {}).get("total_tokens"),
        }
    )
    if tool_calls:
        function = tool_calls[0].get("function") or {}
        try:
            arguments = json.loads(function.get("arguments") or "{}")
        except json.JSONDecodeError:
            arguments = {}
        summary["tool_name"] = function.get("name")
        summary["argument_keys"] = sorted(arguments)
    else:
        summary["content"] = str(message.get("content") or "")[:200]
    return summary


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]"
            if str(key).lower() in {"authorization", "api_key", "token", "password"}
            else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    sys.exit(main())
