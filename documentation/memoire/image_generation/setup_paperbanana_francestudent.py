#!/usr/bin/env python3
"""Prepare a local PaperBanana clone for FranceStudent image generation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PAPERBANANA_REPO = "https://github.com/dwzhu-pku/PaperBanana.git"
PAPERBANANA_DIR = ROOT / "vendor" / "PaperBanana"
FRANCESTUDENT_BASE_URL = "https://api.francestudent.org/v1"


def run(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Expected patch anchor not found in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def ensure_clone() -> None:
    if PAPERBANANA_DIR.exists():
        return
    PAPERBANANA_DIR.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", "--depth", "1", PAPERBANANA_REPO, str(PAPERBANANA_DIR)])


def patch_generation_utils() -> None:
    path = PAPERBANANA_DIR / "utils" / "generation_utils.py"
    text = path.read_text(encoding="utf-8")
    if "PaperBanana-FranceStudent" in text:
        patch_responses_payload_shape(path)
        return

    replace_once(
        path,
        'openai_client = None\nopenrouter_client = None\nopenrouter_api_key = ""\n',
        'openai_client = None\nopenrouter_client = None\nopenai_api_key = ""\nopenai_base_url = ""\nopenai_text_endpoint = ""\nopenrouter_api_key = ""\n\n\n'
        'def get_config_val_any(section, key, env_vars, default=""):\n'
        '    for env_var in env_vars:\n'
        '        val = os.getenv(env_var)\n'
        '        if val:\n'
        '            return val\n'
        '    if section in model_config:\n'
        '        val = model_config[section].get(key)\n'
        '        if val:\n'
        '            return val\n'
        '    return default\n',
    )
    replace_once(
        path,
        '    global gemini_client, anthropic_client, openai_client\n'
        '    global openrouter_client, openrouter_api_key\n',
        '    global gemini_client, anthropic_client, openai_client\n'
        '    global openrouter_client, openrouter_api_key\n'
        '    global openai_api_key, openai_base_url, openai_text_endpoint\n',
    )
    replace_once(
        path,
        '    key = get_config_val("api_keys", "openai_api_key", "OPENAI_API_KEY", "")\n'
        '    if key:\n'
        '        openai_client = AsyncOpenAI(api_key=key)\n'
        '        print("Initialized OpenAI Client with API Key")\n'
        '        initialized.append("OpenAI")\n'
        '    else:\n'
        '        openai_client = None\n',
        '    key = get_config_val_any(\n'
        '        "api_keys",\n'
        '        "openai_api_key",\n'
        '        ("OPENAI_API_KEY", "IMAGEN", "FRANCESTUDENT_API_KEY"),\n'
        '        "",\n'
        '    )\n'
        '    if key:\n'
        '        openai_api_key = key\n'
        '        openai_base_url = get_config_val_any(\n'
        '            "api_settings",\n'
        '            "openai_base_url",\n'
        '            ("OPENAI_BASE_URL", "FRANCESTUDENT_BASE_URL"),\n'
        '            "",\n'
        '        )\n'
        '        openai_text_endpoint = get_config_val_any(\n'
        '            "api_settings",\n'
        '            "openai_text_endpoint",\n'
        '            ("OPENAI_TEXT_ENDPOINT",),\n'
        '            "chat_completions",\n'
        '        )\n'
        '        if openai_base_url:\n'
        '            openai_client = AsyncOpenAI(api_key=key, base_url=openai_base_url)\n'
        '            print(f"Initialized OpenAI-compatible Client with base URL: {openai_base_url}")\n'
        '        else:\n'
        '            openai_client = AsyncOpenAI(api_key=key)\n'
        '            print("Initialized OpenAI Client with API Key")\n'
        '        if "francestudent" in openai_base_url and openai_text_endpoint == "chat_completions":\n'
        '            openai_text_endpoint = "responses"\n'
        '        initialized.append("OpenAI-compatible")\n'
        '    else:\n'
        '        openai_api_key = ""\n'
        '        openai_base_url = ""\n'
        '        openai_text_endpoint = ""\n'
        '        openai_client = None\n',
    )
    replace_once(
        path,
        '    response_text_list = []\n\n'
        '    # --- Preparation Phase ---\n',
        '    if openai_text_endpoint == "responses":\n'
        '        return await call_openai_responses_with_retry_async(\n'
        '            model_name=model_name,\n'
        '            contents=contents,\n'
        '            config=config,\n'
        '            max_attempts=max_attempts,\n'
        '            retry_delay=retry_delay,\n'
        '            error_context=error_context,\n'
        '        )\n\n'
        '    response_text_list = []\n\n'
        '    # --- Preparation Phase ---\n',
    )
    replace_once(
        path,
        '\n\nasync def call_openai_image_generation_with_retry_async(\n',
        '\n\n'
        'def output_text_from_responses(data: dict) -> str:\n'
        '    if isinstance(data.get("output_text"), str):\n'
        '        return data["output_text"]\n'
        '    chunks = []\n'
        '    for item in data.get("output", []):\n'
        '        for content in item.get("content", []):\n'
        '            if content.get("type") in {"output_text", "text"}:\n'
        '                chunks.append(content.get("text", ""))\n'
        '    return "".join(chunks).strip()\n\n\n'
        'def _convert_to_responses_input(contents: List[Dict[str, Any]]) -> list:\n'
        '    converted = []\n'
        '    for item in contents:\n'
        '        if item.get("type") == "text":\n'
        '            converted.append({"type": "input_text", "text": item["text"]})\n'
        '        elif item.get("type") == "image":\n'
        '            source = item.get("source", {})\n'
        '            if source.get("type") == "base64":\n'
        '                media_type = source.get("media_type", "image/jpeg")\n'
        '                data = source.get("data", "")\n'
        '                converted.append({\n'
        '                    "type": "input_image",\n'
        '                    "image_url": f"data:{media_type};base64,{data}",\n'
        '                })\n'
        '            elif "image_base64" in item:\n'
        '                converted.append({\n'
        '                    "type": "input_image",\n'
        '                    "image_url": f"data:image/jpeg;base64,{item[\'image_base64\']}",\n'
        '                })\n'
        '    return [{"role": "user", "content": converted}]\n\n\n'
        'def _responses_input_payload(contents: List[Dict[str, Any]]):\n'
        '    text_parts = [\n'
        '        item["text"]\n'
        '        for item in contents\n'
        '        if item.get("type") == "text" and isinstance(item.get("text"), str)\n'
        '    ]\n'
        '    if len(text_parts) == len(contents):\n'
        '        return "\\n\\n".join(text_parts)\n'
        '    return _convert_to_responses_input(contents)\n\n\n'
        'async def call_openai_responses_with_retry_async(\n'
        '    model_name, contents, config, max_attempts=5, retry_delay=30, error_context=""\n'
        '):\n'
        '    """Call an OpenAI-compatible Responses endpoint, used by FranceStudent."""\n'
        '    if not openai_api_key:\n'
        '        raise RuntimeError("OpenAI-compatible client was not initialized: missing API key.")\n'
        '    system_prompt = config["system_prompt"]\n'
        '    temperature = config["temperature"]\n'
        '    candidate_num = config["candidate_num"]\n'
        '    max_output_tokens = min(config["max_completion_tokens"], 4096)\n'
        '    response_text_list = []\n'
        '    endpoint = (openai_base_url or "https://api.openai.com/v1").rstrip("/") + "/responses"\n'
        '    payload_base = {\n'
        '        "model": model_name,\n'
        '        "input": _responses_input_payload(contents),\n'
        '        "instructions": system_prompt,\n'
        '        "max_output_tokens": max_output_tokens,\n'
        '        "temperature": temperature,\n'
        '    }\n'
        '    headers = {\n'
        '        "Authorization": f"Bearer {openai_api_key}",\n'
        '        "Content-Type": "application/json",\n'
        '        "Accept": "application/json",\n'
        '        "User-Agent": "PaperBanana-FranceStudent",\n'
        '    }\n'
        '    for _candidate_idx in range(candidate_num):\n'
        '        for attempt in range(max_attempts):\n'
        '            try:\n'
        '                async with httpx.AsyncClient(timeout=300) as client:\n'
        '                    resp = await client.post(endpoint, headers=headers, json=payload_base)\n'
        '                resp.raise_for_status()\n'
        '                text = output_text_from_responses(resp.json())\n'
        '                if not text:\n'
        '                    print("Responses endpoint returned empty content, retrying...")\n'
        '                    if attempt < max_attempts - 1:\n'
        '                        await asyncio.sleep(retry_delay)\n'
        '                    continue\n'
        '                response_text_list.append(text)\n'
        '                break\n'
        '            except Exception as e:\n'
        '                context_msg = f" for {error_context}" if error_context else ""\n'
        '                current_delay = min(retry_delay * (2 ** attempt), 60)\n'
        '                print(f"Responses attempt {attempt + 1} failed{context_msg}: {e}. Retrying in {current_delay}s...")\n'
        '                if attempt < max_attempts - 1:\n'
        '                    await asyncio.sleep(current_delay)\n'
        '                else:\n'
        '                    response_text_list.append("Error")\n'
        '    if len(response_text_list) < candidate_num:\n'
        '        response_text_list.extend(["Error"] * (candidate_num - len(response_text_list)))\n'
        '    return response_text_list\n\n\n'
        'async def call_openai_image_generation_with_retry_async(\n',
    )
    patch_responses_payload_shape(path)


def patch_responses_payload_shape(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "_responses_input_payload" not in text:
        replace_once(
            path,
            '    return [{"role": "user", "content": converted}]\n\n\n'
            'async def call_openai_responses_with_retry_async(\n',
            '    return [{"role": "user", "content": converted}]\n\n\n'
            'def _responses_input_payload(contents: List[Dict[str, Any]]):\n'
            '    text_parts = [\n'
            '        item["text"]\n'
            '        for item in contents\n'
            '        if item.get("type") == "text" and isinstance(item.get("text"), str)\n'
            '    ]\n'
            '    if len(text_parts) == len(contents):\n'
            '        return "\\n\\n".join(text_parts)\n'
            '    return _convert_to_responses_input(contents)\n\n\n'
            'async def call_openai_responses_with_retry_async(\n',
        )
    replace_once(
        path,
        '    max_output_tokens = config["max_completion_tokens"]\n',
        '    max_output_tokens = min(config["max_completion_tokens"], 4096)\n',
    )
    replace_once(
        path,
        '        "input": _convert_to_responses_input(contents),\n',
        '        "input": _responses_input_payload(contents),\n',
    )


def patch_model_template() -> None:
    path = PAPERBANANA_DIR / "configs" / "model_config.template.yaml"
    replace_once(
        path,
        'defaults:\n'
        '  main_model_name: "gemini-3.1-pro-preview"\n'
        '  image_gen_model_name: "gemini-3.1-flash-image-preview"\n'
        '  \n'
        '# API Keys. If you are using all gemini models, you can leave the other keys empty.\n',
        'defaults:\n'
        '  main_model_name: "gemini-3.1-pro-preview"\n'
        '  image_gen_model_name: "gemini-3.1-flash-image-preview"\n'
        '\n'
        '# OpenAI-compatible provider settings. Leave empty for the official OpenAI API.\n'
        '# For FranceStudent, use:\n'
        '#   openai_base_url: "https://api.francestudent.org/v1"\n'
        '#   openai_text_endpoint: "responses"\n'
        'api_settings:\n'
        '  openai_base_url: ""\n'
        '  openai_text_endpoint: "chat_completions"\n'
        '  \n'
        '# API Keys. If you are using all gemini models, you can leave the other keys empty.\n',
    )
    replace_once(
        path,
        '  openai_api_key: ""\n',
        '  openai_api_key: "" # May also be provided through OPENAI_API_KEY, IMAGEN, or FRANCESTUDENT_API_KEY.\n',
    )


def patch_skill_runner() -> None:
    path = PAPERBANANA_DIR / "skill" / "run.py"
    replace_once(
        path,
        '    ensure_model_config()\n'
        '    ensure_dataset(args.task)\n',
        '    ensure_model_config()\n'
        '    if args.retrieval_setting != "none":\n'
        '        ensure_dataset(args.task)\n',
    )


def patch_retriever_ref_limit() -> None:
    path = PAPERBANANA_DIR / "agents" / "retriever_agent.py"
    replace_once(path, "import json\nimport random\n", "import json\nimport os\nimport random\n")
    replace_once(path, "import random\nfrom typing", "import random\nimport re\nfrom typing")
    replace_once(
        path,
        '                "ref_limit": 200,  # Limit to first 200\n',
        '                "ref_limit": int(os.getenv("PAPERBANANA_DIAGRAM_REF_LIMIT", "40")),\n',
    )
    replace_once(
        path,
        '            candidate_pool = json.load(f)\n'
        '            if cfg["ref_limit"]:\n',
        '            candidate_pool = json.load(f)\n'
        '            if os.getenv("PAPERBANANA_SKIP_CYBER_REFERENCES", "1") == "1":\n'
        '                before_filter = len(candidate_pool)\n'
        '                candidate_pool = self._filter_cyber_references(candidate_pool)\n'
        '                skipped = before_filter - len(candidate_pool)\n'
        '                if skipped:\n'
        '                    print(f"[Retriever] Skipped {skipped} cybersecurity-sensitive references.")\n'
        '            if cfg["ref_limit"]:\n',
    )
    replace_once(
        path,
        '            if cfg["ref_limit"]:\n'
        '                candidate_pool = candidate_pool[:cfg["ref_limit"]]\n',
        '            if cfg["ref_limit"]:\n'
        '                candidate_pool = candidate_pool[:cfg["ref_limit"]]\n'
        '                print(f"[Retriever] Candidate pool capped at {len(candidate_pool)} references (ref_limit={cfg[\'ref_limit\']}).")\n',
    )
    replace_once(
        path,
        '        raw_response = response_list[0].strip()\n'
        '        return self._parse_retrieval_result(raw_response, cfg["task_name"])\n',
        '        raw_response = response_list[0].strip()\n'
        '        ids = self._parse_retrieval_result(raw_response, cfg["task_name"])\n'
        '        if ids:\n'
        '            print(f"[Retriever] Selected reference IDs: {\', \'.join(ids)}")\n'
        '        return ids\n',
    )
    replace_once(
        path,
        '        return ids\n'
        '    \n'
        '    def _parse_retrieval_result',
        '        return ids\n\n'
        '    def _filter_cyber_references(self, candidate_pool: list) -> list:\n'
        '        """Avoid provider cyber-safety flags from unrelated benchmark examples."""\n'
        '        sensitive_pattern = re.compile(\n'
        '            r"cyber|security|attack|vulnerab|exploit|malware|threat|"\n'
        '            r"adversarial|prompt injection|jailbreak|backdoor|red[- ]?team",\n'
        '            re.IGNORECASE,\n'
        '        )\n'
        '        filtered = []\n'
        '        for item in candidate_pool:\n'
        '            text = f"{item.get(\'visual_intent\', \'\')}\\n{item.get(\'content\', \'\')}"\n'
        '            if not sensitive_pattern.search(text):\n'
        '                filtered.append(item)\n'
        '        return filtered\n'
        '    \n'
        '    def _parse_retrieval_result',
    )
    replace_once(
        path,
        '                temperature=self.exp_config.temperature,\n'
        '                candidate_count=1,\n'
        '                max_output_tokens=50000,\n',
        '                temperature=0.0,\n'
        '                candidate_count=1,\n'
        '                max_output_tokens=2048,\n',
    )
    replace_once(
        path,
        '            # Extract the appropriate field based on task type\n'
        '            if task_name == "plot":\n',
        '            if isinstance(parsed, list):\n'
        '                return [str(item) for item in parsed if str(item).startswith("ref_")]\n'
        '            \n'
        '            # Extract the appropriate field based on task type\n'
        '            if task_name == "plot":\n',
    )
    replace_once(
        path,
        '                return parsed.get("top10_plots", [])\n',
        '                ids = parsed.get("top10_plots") or parsed.get("top10_references") or parsed.get("ids") or []\n',
    )
    replace_once(
        path,
        '                return parsed.get("top10_diagrams", [])\n',
        '                ids = parsed.get("top10_diagrams") or parsed.get("top10_references") or parsed.get("ids") or []\n',
    )
    replace_once(
        path,
        '            else:\n'
        '                raise ValueError(f"Unknown task_name: {task_name}")\n',
        '            else:\n'
        '                raise ValueError(f"Unknown task_name: {task_name}")\n'
        '            if not ids:\n'
        '                for value in parsed.values():\n'
        '                    if isinstance(value, list):\n'
        '                        ids = value\n'
        '                        break\n'
        '            return [str(item) for item in ids if str(item).startswith("ref_")]\n',
    )


def patch_agent_image_sizes() -> None:
    for relative_path in (
        "utils/generation_utils.py",
        "agents/visualizer_agent.py",
        "agents/vanilla_agent.py",
    ):
        path = PAPERBANANA_DIR / relative_path
        replace_once(path, '"1536x1024"', '"1024x1024"')


def patch_no_embedded_captions() -> None:
    replace_once(
        PAPERBANANA_DIR / "agents" / "visualizer_agent.py",
        '                "prompt_template": "Render an image based on the following detailed description: {desc}\\n Note that do not include figure titles in the image. Diagram: ",\n',
        '                "prompt_template": "Render an image based on the following detailed description: {desc}\\n Do not include figure titles, captions, long explanatory sentences, or any bottom caption text inside the image. Keep only short labels inside diagram elements. Diagram: ",\n',
    )
    replace_once(
        PAPERBANANA_DIR / "agents" / "vanilla_agent.py",
        '            prompt_text += "Note that do not include figure titles in the image."\n',
        '            prompt_text += "Do not include figure titles, captions, long explanatory sentences, or any bottom caption text inside the image. Keep only short labels inside diagram elements."\n',
    )


def write_local_config() -> None:
    config_path = PAPERBANANA_DIR / "configs" / "model_config.yaml"
    config_path.write_text(
        '# Local StigmergiAgentic memoir configuration.\n'
        '# No secret is stored here. The FranceStudent key is read from IMAGEN,\n'
        '# FRANCESTUDENT_API_KEY, or OPENAI_API_KEY.\n\n'
        'defaults:\n'
        '  main_model_name: "gpt-5.5"\n'
        '  image_gen_model_name: "gpt-image-2"\n\n'
        'api_settings:\n'
        f'  openai_base_url: "{FRANCESTUDENT_BASE_URL}"\n'
        '  openai_text_endpoint: "responses"\n\n'
        'api_keys:\n'
        '  google_api_key: ""\n'
        '  openai_api_key: ""\n'
        '  anthropic_api_key: ""\n'
        '  openrouter_api_key: ""\n',
        encoding="utf-8",
    )


def main() -> int:
    ensure_clone()
    patch_generation_utils()
    patch_model_template()
    patch_skill_runner()
    patch_retriever_ref_limit()
    patch_agent_image_sizes()
    patch_no_embedded_captions()
    write_local_config()
    print(f"PaperBanana ready at {PAPERBANANA_DIR}")
    print("Secrets are still read from env/.env; none were written to config.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
