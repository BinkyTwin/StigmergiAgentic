---
name: francestudent-api
description: Use the FranceStudent OpenAI-compatible API when Codex needs to test or call the student-provided IMAGEN key, run text prompts through the Responses API, generate images with gpt-image-2, debug FranceStudent API errors, or produce local image/text artifacts without exposing secrets.
---

# FranceStudent API

## Core Rules

- Use `https://api.francestudent.org/v1` as the base URL for `IMAGEN`.
- Read the API key from env or `.env`; never print it or pass it as a CLI argument.
- Use `POST /responses` for text models such as `gpt-5.5`.
- Use `POST /images/generations` for `gpt-image-2`; the FranceStudent `/responses` compatibility endpoint rejected the hosted `image_generation` tool in local tests.
- Save raw responses and decoded images under `output/francestudent_api_tests/` unless the user requests another path.

## Quick Start

Prefer the bundled CLI for repeatable tests:

```bash
python3 .codex/skills/francestudent-api/scripts/francestudent_api.py text \
  --prompt "Réponds en une phrase: l'API fonctionne." \
  --model gpt-5.5

python3 .codex/skills/francestudent-api/scripts/francestudent_api.py image \
  --prompt "Dessine un soleil en fond avec un bonhomme qui remercie Louca de France Student" \
  --model gpt-image-2 \
  --size 1024x1024
```

The script loads `IMAGEN` by default, supports `FRANCESTUDENT_API_KEY`, and writes artifacts without logging secrets.

## Workflows

### Text Prompt

1. Call `/responses` with `model`, `input`, and optional response parameters.
2. Report `status`, `response_id`, and `output_text`.
3. If the provider returns `401`, verify the base URL is FranceStudent and the env variable is set.
4. If the provider returns `403 error code: 1010` from Python `urllib`, retry with `curl`-like headers or the bundled script.

### Image Generation

1. Call `/images/generations` with `model=gpt-image-2`, `prompt`, and image options.
2. Decode `data[0].b64_json` to a local image file.
3. Return a Markdown image tag with an absolute filesystem path when the user asks to see the image.
4. Keep the JSON response beside the image for debugging.

### Configuration Reference

Read `references/api-parameters.md` when the user asks for available configs, wants a custom parameter, or an API call fails due to an unsupported option.

## Local Notes

- The direct OpenAI base URL returned `invalid_api_key` for `IMAGEN`; this is expected for a FranceStudent-issued key.
- GPT image models return base64 by default on the Images API; `url` output is unsupported for GPT image models in the official docs.
- `gpt-image-2` currently does not support transparent backgrounds in the Responses image tool docs; avoid `background=transparent` unless the provider explicitly adds support.
