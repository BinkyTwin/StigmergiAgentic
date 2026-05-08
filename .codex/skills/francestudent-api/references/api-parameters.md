# FranceStudent API Parameters

This reference focuses on the OpenAI-compatible parameters useful with
`https://api.francestudent.org/v1` and the local `IMAGEN` key. FranceStudent may
support a subset of the official OpenAI API. When an option fails, retry with the
minimal payload and add options one by one.

## Common Settings

- `base_url`: default `https://api.francestudent.org/v1`.
- `api_key_env`: default lookup order `IMAGEN`, then `FRANCESTUDENT_API_KEY`, then `OPENAI_API_KEY`.
- `timeout`: use 60 seconds for text, 180 seconds for image generation.
- Headers: `Authorization: Bearer <key>`, `Content-Type: application/json`, `Accept: application/json`, and a normal `User-Agent`.

## Responses API (`POST /responses`)

Minimal payload:

```json
{
  "model": "gpt-5.5",
  "input": "Réponds en une phrase."
}
```

Core request fields:

- `model`: text-capable model ID. Tested: `gpt-5.5`.
- `input`: string or structured input array. For simple tests, use a string.
- `instructions`: optional high-level instruction string.
- `max_output_tokens`: integer output cap.
- `metadata`: object for your own tracking.
- `previous_response_id`: string for multi-turn continuity when supported.
- `store`: boolean; omit unless persistence is needed.
- `stream`: boolean; use only if the provider supports streaming.
- `temperature`: number, when supported by the model/provider.
- `top_p`: number, when supported by the model/provider.
- `parallel_tool_calls`: boolean.
- `tools`: array of tools. FranceStudent rejected `image_generation` through `/responses` in local tests.
- `tool_choice`: `"auto"`, `"none"`, `"required"`, or an object selecting a tool, when supported.
- `reasoning`: object for reasoning models.
- `text`: object for output text configuration.
- `truncation`: `"auto"` or `"disabled"`.
- `safety_identifier`: stable non-PII user identifier, max 64 chars.
- `prompt_cache_key`: cache bucketing key.
- `prompt_cache_retention`: `"in-memory"` or `"24h"` when supported.
- `service_tier`: `"auto"`, `"default"`, `"flex"`, or provider-supported tiers.

Useful nested fields:

```json
{
  "reasoning": {
    "effort": "none|minimal|low|medium|high|xhigh",
    "summary": "auto|concise|detailed"
  },
  "text": {
    "format": { "type": "text" },
    "verbosity": "low|medium|high"
  }
}
```

Structured output shape:

```json
{
  "text": {
    "format": {
      "type": "json_schema",
      "name": "result",
      "schema": {
        "type": "object",
        "properties": {
          "answer": { "type": "string" }
        },
        "required": ["answer"],
        "additionalProperties": false
      },
      "strict": true
    }
  }
}
```

Response extraction:

- Prefer top-level `output_text` when present.
- Otherwise concatenate `output[].content[]` entries where `type` is `output_text` or `text`.

## Image Generation API (`POST /images/generations`)

Minimal payload:

```json
{
  "model": "gpt-image-2",
  "prompt": "Dessine un soleil en fond avec un bonhomme qui remercie Louca de France Student",
  "size": "1024x1024"
}
```

Core request fields:

- `model`: image model. Tested: `gpt-image-2`.
- `prompt`: required text prompt.
- `size`: `"1024x1024"`, `"1024x1536"`, `"1536x1024"`, or `"auto"` in official docs. `gpt-image-2` also advertises flexible sizes with constraints; prefer standard sizes unless needed.
- `quality`: `"low"`, `"medium"`, `"high"`, or `"auto"`.
- `output_format`: `"png"`, `"webp"`, or `"jpeg"`.
- `background`: `"opaque"` or `"auto"` for `gpt-image-2`; avoid `"transparent"` unless verified because docs note `gpt-image-2` does not currently support transparent backgrounds.
- `n`: number of images; support may vary by provider/model.
- `moderation`: provider/model-dependent moderation setting.
- `output_compression`: 0-100 for JPEG/WebP where supported.
- `response_format`: legacy option for DALL-E models. GPT image models return `b64_json` by default and do not support URL output in official docs.
- `user`: deprecated; prefer `safety_identifier` where available, but the Images endpoint may still accept `user` on some providers.

Response extraction:

- GPT image models usually return `data[0].b64_json`; decode it to the requested image path.
- DALL-E models may return `data[0].url` if URL response format is used.
- Keep raw JSON for debugging, but never commit secrets.

## Image Editing (`POST /images/edits`)

The local workflow has not been tested against FranceStudent yet. Officially relevant fields include:

- `model`
- `image`: one or more input image files.
- `prompt`
- `mask`: optional mask image for inpainting.
- `size`
- `quality`
- `output_format`
- `background`
- `n`

Use this only after a small smoke test, because proxy support may differ from OpenAI.

## Known FranceStudent Behaviors

- `https://api.openai.com/v1` with `IMAGEN` returned `401 invalid_api_key`.
- `https://api.francestudent.org/v1/responses` with `gpt-5.5` returned `HTTP 200` and `status=completed`.
- `https://api.francestudent.org/v1/responses` with `tools=[{"type":"image_generation"}]` returned `400` saying the local Responses compatibility endpoint does not support `image_generation`.
- `https://api.francestudent.org/v1/images/generations` with `model=gpt-image-2` returned a valid PNG through `b64_json`.

## Official Sources

- Responses create reference: `https://developers.openai.com/api/reference/resources/responses/methods/create`
- Images reference: `https://developers.openai.com/api/reference/resources/images`
- GPT Image 2 model page: `https://developers.openai.com/api/docs/models/gpt-image-2`
- Responses image-generation tool guide: `https://developers.openai.com/api/docs/guides/tools-image-generation`
