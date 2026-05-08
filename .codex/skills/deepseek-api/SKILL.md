---
name: deepseek-api
description: Use the DeepSeek OpenAI-compatible API safely for chat completions, V4 model selection, thinking-mode control, strict native tool calls, pricing-aware checks, and live smoke tests. Trigger when Codex needs to call or debug DeepSeek, validate DEEPSEEK_API_KEY from env/.env, update DeepSeek provider code, or reason about deepseek-v4-flash/deepseek-v4-pro versus legacy deepseek-chat/deepseek-reasoner aliases.
---

# DeepSeek API

## Core Workflow

1. Load `DEEPSEEK_API_KEY` from `os.environ` first, then repo-local `.env` when present. Never print the key and never pass it as a CLI argument.
2. Prefer current model ids: `deepseek-v4-flash` for normal project work, `deepseek-v4-pro` only when the user explicitly wants the stronger/costlier model.
3. Treat `deepseek-chat` and `deepseek-reasoner` as compatibility aliases, not project defaults.
4. For required native tool choice, use `deepseek-v4-flash` with thinking disabled:
   `thinking={"type": "disabled"}` in HTTP payloads, or `extra_body={"thinking": {"type": "disabled"}}` with the OpenAI SDK.
5. For strict tool schemas, use `https://api.deepseek.com/beta`, set every function `strict: true`, require every object property, and set `additionalProperties: false`.
6. Use direct HTTP with explicit timeout for smoke tests and benchmark-critical tool-choice calls if the OpenAI-compatible SDK path hangs locally.
7. Redact secrets from traces, logs, exceptions, and final reports.

## Script

Use `scripts/deepseek_smoke.py` for repeatable checks:

```bash
uv run python .codex/skills/deepseek-api/scripts/deepseek_smoke.py --mode tool-call
```

Useful modes:

- `--mode ping`: minimal non-thinking chat-completion smoke.
- `--mode tool-call`: strict beta native tool-call smoke, default for V12.2 compatibility.

The script reads `.env` itself, emits compact JSON, and writes no files unless `--trace-dir` is provided.

## References

Read `references/deepseek-api.md` when changing provider code, model defaults, pricing assumptions, thinking mode, strict schemas, or tool-call behavior.
