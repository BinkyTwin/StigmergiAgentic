# DeepSeek API Reference Notes

Use this file only when the task needs DeepSeek-specific details beyond the main workflow.

## Official Sources

- Models and pricing: https://api-docs.deepseek.com/quick_start/pricing/
- Chat completions API: https://api-docs.deepseek.com/api/create-chat-completion/
- Tool calls and strict mode: https://api-docs.deepseek.com/guides/tool_calls
- Thinking mode: https://api-docs.deepseek.com/guides/thinking_mode

## Current Project Defaults

- Current StigmergiAgentic model: `deepseek-v4-flash`.
- Current V12.2 tool-choice mode: non-thinking, strict beta native tool calls.
- Current strict base URL: `https://api.deepseek.com/beta`.
- Current regular OpenAI-format base URL: `https://api.deepseek.com`.

## Model Selection

DeepSeek currently documents `deepseek-v4-flash` and `deepseek-v4-pro` as the primary OpenAI-format models. The legacy names `deepseek-chat` and `deepseek-reasoner` are compatibility aliases for V4 Flash non-thinking and thinking modes respectively, and are documented as future-deprecated.

Use `deepseek-v4-flash` unless the user explicitly asks for `deepseek-v4-pro`.

## Thinking Mode

Thinking mode defaults to enabled. Disable it for deterministic tool-choice smoke tests and V12.2 required tool selection:

```json
{
  "thinking": {"type": "disabled"}
}
```

With the OpenAI SDK, pass this inside `extra_body`.

Thinking mode does not honor sampling parameters such as `temperature`; avoid relying on temperature to control output when thinking is enabled.

## Strict Native Tool Calls

Strict mode is beta and requires the beta base URL. For every function tool:

- set `strict: true`;
- use only supported schema shapes;
- make every object property required;
- set `additionalProperties: false` on every object;
- avoid unsupported strict-schema keywords such as `minLength`, `maxLength`, `minItems`, and `maxItems`.

When V12 requires exactly one tool call, send `tool_choice: "required"` and `parallel_tool_calls: false`, then locally validate that exactly one known tool call was returned.

## Pricing Notes

The official pricing page quotes prices per 1M tokens and may change. As of the checked 2026-05-07 docs:

- `deepseek-v4-flash`: cache-hit input `$0.0028`, cache-miss input `$0.14`, output `$0.28` per 1M tokens.
- `deepseek-v4-pro`: cache-hit input `$0.003625`, cache-miss input `$0.435`, output `$0.87` per 1M tokens during the documented discount window.

Do not hard-claim pricing without checking the official page again.
