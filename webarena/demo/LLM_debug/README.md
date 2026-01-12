# LLM Debug (WebArena Demo)

This folder contains a tiny, practical harness to sanity-check an LLM chat backend with a simple prompt stack.
It is intended for quick iteration on prompts and connectivity (Azure/OpenAI-compatible) without running the full WebArena pipeline.

## What it does

- Loads a **system** prompt from `prompt/system_prompt.txt`.
- Loads a list of **user** prompts from `prompt/user/user_prompt.json`.
- Sends them sequentially as one conversation to an LLM backend.
- Writes the full conversation (system/user/assistant messages) to a timestamped folder under `result/`.

## Directory layout

```text
webarena/demo/LLM_debug/
  main.py                 # runner
  llm_client.py            # minimal client wrapper (azure or OpenAI-compatible)
  requirements.txt         # demo deps
  prompt/
    system_prompt.txt
    user/
      user_prompt.json
  result/
    <timestamp>/
      conversation_history.json
```

## Requirements

- Python 3.10+ recommended.
- Install deps:

```bash
pip install -r webarena/demo/LLM_debug/requirements.txt
```

Notes:

- For `--api-type azure`, this demo uses the repo helper `webarena/cloudgpt_aoai`, which in turn relies on Azure Identity / your local Azure authentication setup.
- `requirements.txt` only pins `openai>=1.0.0`. If you want to use Azure in a clean environment, make sure the broader WebArena dependencies are available in the same interpreter.

## Quick start

From the repo root:

```bash
python webarena/demo/LLM_debug/main.py --api-type azure --model gpt-4o-mini
```

Defaults:

- Prompts are read from `webarena/demo/LLM_debug/prompt/`.
- Outputs are written to `webarena/demo/LLM_debug/result/`.

## Configuration (CLI only)

This demo runner does not read any environment variables. All config is passed via CLI.

### Azure (CloudGPT)

```bash
python webarena/demo/LLM_debug/main.py \
  --api-type azure \
  --model gpt-4o-mini \
  --temperature 0.2 \
  --max-tokens 1024
```

Notes:

- This demo wrapper does not accept Azure-specific keys via CLI.
- Authentication is handled by `webarena/cloudgpt_aoai` (Azure Identity). In most setups this means you should already have a working login context (for example via `az login`, device code flow, or an identity broker depending on your environment).

### OpenAI-compatible (openai / kimi / glm)

OpenAI official endpoint (base URL optional):

```bash
python webarena/demo/LLM_debug/main.py \
  --api-type openai \
  --model gpt-4o-mini \
  --api-key <API_KEY>
```

OpenAI with a custom OpenAI-compatible gateway (optional):

```bash
python webarena/demo/LLM_debug/main.py \
  --api-type openai \
  --model gpt-4o-mini \
  --api-key <API_KEY> \
  --base-url <BASE_URL>
```

Kimi (base URL recommended):

```bash
python webarena/demo/LLM_debug/main.py \
  --api-type kimi \
  --model <MODEL_NAME> \
  --api-key <API_KEY> \
  --base-url <BASE_URL>
```

GLM (base URL recommended):

```bash
python webarena/demo/LLM_debug/main.py \
  --api-type glm \
  --model <MODEL_NAME> \
  --api-key <API_KEY> \
  --base-url <BASE_URL>
```

Token limit note:

- The client uses `max_completion_tokens` for Azure models that look like GPT-5 (`gpt-5` / `gpt5*`). Other models use `max_tokens`.

## Prompt files

### System prompt

- File: `prompt/system_prompt.txt`
- Content: plain text, sent as the first message with role `system`.

### User prompts

- File: `prompt/user/user_prompt.json`
- Format:

```json
{
  "user_prompt": [
    "Say hello.",
    "Now summarize what you just said in one sentence."
  ]
}
```

Each string becomes a new message with role `user`. After each user message, the script calls the LLM once and appends a role `assistant` response.

## Outputs

- Console: prints a short preview per assistant turn:
  - `[i/n] assistant: <first 200 chars>`
- File output: a timestamped directory under `result/`, e.g. `result/20260112_153012/`.
  - `conversation_history.json`: JSON list of messages in OpenAI Chat format:

```json
[
  {"role": "system", "content": "..."},
  {"role": "user", "content": "..."},
  {"role": "assistant", "content": "..."}
]
```

## CLI options

- `--prompt-dir`: directory containing:
  - `system_prompt.txt`
  - `user/user_prompt.json`
- `--result-dir`: base directory to store timestamped results

LLM client options:

- `--api-type`: `azure` | `openai` | `kimi` | `glm` (required)
- `--model`: model name (required)
- `--api-key`: required when `--api-type != azure`
- `--base-url`: optional; recommended for `kimi` / `glm`
- `--temperature`: float, default `0.2`
- `--max-tokens`: int, default `1024`

Example:

```bash
python webarena/demo/LLM_debug/main.py \
  --api-type azure \
  --model gpt-4o-mini \
  --prompt-dir webarena/demo/LLM_debug/prompt \
  --result-dir webarena/demo/LLM_debug/result
```

## Troubleshooting

- `model is required (pass --model)`: pass `--model <MODEL_NAME>` (for example `--model gpt-4o-mini`).
- `--api-key is required when --api-type != azure`: pass `--api-key <KEY>` when using `--api-type openai|kimi|glm`.
- Azure auth failures: ensure your Azure identity context is available and Azure-related dependencies are installed in the active environment.
