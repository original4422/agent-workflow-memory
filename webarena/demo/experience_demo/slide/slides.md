---
marp: true
paginate: true
size: 16:9
---

# Experience Demo
## Architecture Deep Dive (Code-Level)

**Scope**: `webarena/demo/experience_demo` only

---

## What this demo shows

Two modes on the same WebArena task:

- **Baseline**: no experience retrieval/prompt injection
- **With-Experience**: retrieve top-k "experiences" by goal embedding, inject into system prompt

Outputs:

- BrowserGym experiment artifacts (screenshots/summary)
- Demo-level trace + conversation history
- Simple run report (`report.md` / `report.json`)

---

## Repository layout (key modules)

- `run_demo.py` — CLI entrypoint; runs baseline / with-exp; writes report
- `agent/agent.py` — `ExperienceDemoAgent` (core control loop)
- `agent/prompting.py` — prompt templates (`build_system_prompt`, `build_user_prompt`)
- `agent/actions.py` — `<action>...</action>` extraction + action validation
- `retrieval/embedder.py` — SentenceTransformer embedder + L2 normalization
- `retrieval/index.py` — experience loader + embedding cache + index build/load
- `retrieval/retrieve.py` — cosine retrieval (dot product on normalized vectors)
- `trace/writer.py` + `trace/types.py` — JSONL trace + typed payloads
- `trace/conversation_history.py` — JSON conversation history

---

## External dependencies (runtime)

- **BrowserGym** (`EnvArgs`, `ExpArgs`, `Agent`) orchestrates episodes/steps
- **Playwright** (via BrowserGym) drives the browser
- **Azure OpenAI** client (`openai.AzureOpenAI`) via `cloudgpt_aoai.get_openai_client()`
- **SentenceTransformers** downloads/loads embedding model

---

## High-level runtime (one run)

1. `run_demo.py` parses CLI args
2. Build `EnvArgs` (task/env config) + `ExpArgs`
3. Create `ExperienceDemoAgent` from `ExperienceDemoAgentArgs.make_agent()`
4. `exp_args.run()` starts BrowserGym loop
5. Each step: env -> agent -> action -> env
6. Archive experiment dir and write `report.md`/`report.json`

---

## Entry point: `run_demo.py`

Key responsibilities:

- Parse CLI flags (`--use_experience`, `--top_k`, `--obs_mode`, `--think_prompt`)
- Optionally monkeypatch WebArena task config loading
- Prepare output layout:
  - Temporary exp root: `results/tmp/`
  - Archived run root: `results/<source>/<config_stem>/custom.<task>/<timestamp_model>/runs/<mode>/...`
- Produce report:
  - `report.json` (structured)
  - `report.md` (human-readable)

---

## Agent core: `ExperienceDemoAgent`

`ExperienceDemoAgent(Agent)` ties together:

- LLM calling (Azure OpenAI)
- Observation preprocessing
- Optional retrieval (goal -> top-k experiences)
- Prompt assembly (system + user)
- Action parsing + validation + retry
- Trace logging (retrieval + steps) + conversation history

---

## Observation preprocessing (`obs_preprocessor`)

Inputs (from env):

- `goal`, `url`
- optionally `axtree_object` and/or `dom_object`
- `screenshot` kept for BrowserGym persistence

Outputs (prompt-ready fields):

- `axtree_txt` via `flatten_axtree_to_str(...)` and clipping
- `dom_txt` via `flatten_dom_to_str(...)`, `prune_html(...)`, and clipping

Config switch:

- `obs_mode`: `axtree | html | both`

---

## Retrieval decision points

- Retrieval is enabled if `use_experience == True`
- Retrieval runs once per episode (cached in `self._retrieved`)
- Query used: **task goal** (`goal`)
- Site filter: hard-coded in agent retrieval call: `site="shopping_admin"`

---

## Retrieval pipeline (code-level)

1. `ExperienceDemoAgent._ensure_index()`
2. `build_or_load_index(experiences_path, embedder)`
   - load JSONL experiences
   - compute fingerprint from summaries
   - reuse `.cache/embeddings__<model>.npy` if fingerprint+model match
3. `retrieve_top_k(query=goal, index, embedder, top_k, site=...)`
   - embed query
   - cosine similarity via `embeddings @ q`

---

## Prompting: system prompt (`build_system_prompt`)

Inputs:

- `goal`
- `action_space_hint` (from `action_set.describe(...)`)
- optional `retrieved_experiences_content` (top-k `content`)
- `think_prompt` controls whether `<think>...</think>` is requested

Output contract:

- Must end with a single line wrapped in: `<action>...</action>`
- Optional: short rationale in `<think>...</think>` (when enabled)

---

## Prompting: user prompt (`build_user_prompt`)

Key fields:

- `step` index
- current `url`
- observation excerpt (clipped)

Note:

- This demo clips long observations via a head/tail strategy to stay within a rough character budget.

---

## LLM call + rolling history

LLM call (`_chat`):

- Messages:
  - system prompt
  - rolling `self._chat_history`
  - current user prompt
- Temperature fixed at `0.2`

History:

- Each successful step appends a (user, assistant) pair
- History is capped by `max_history_turns`

---

## Action parsing & validation

Parsing:

- `extract_action_text(raw)` looks for `<action>...</action>`
- If missing/invalid, it is considered invalid

Validation:

- `validate_action(self.action_set, candidate)`
- Uses `action_set.to_python_code(action_text)` as parser/validator

Fallback:

- If all retries fail: `noop(500)`

---

## Retry mechanism (important)

For each attempt:

1. Call LLM
2. Extract `<action>...</action>`
3. Validate via BrowserGym action set
4. If invalid:
   - push the invalid turn into history
   - append a minimal "Correction" instruction and retry

Goal:

- Improve robustness without complex multi-turn prompting.

---

## Tracing: what gets recorded

Two layers:

- **Demo trace**: `TraceWriter` writes JSONL events
  - `retrieval` event: query/top_k/model/results (id/score/summary/content...)
  - `step` event: prompt snippets, llm output, action validity, error
- **Conversation history**: `ConversationHistoryWriter` writes `conversation_history.json`
  - stored as OpenAI-like message objects (role/content)

---

## Data artifacts (where to look)

Per run (archived exp dir):

- BrowserGym outputs: `summary_info.json` etc.
- Demo outputs under `.../logs/` (set by `exp_args.agent_args.log_dir`):
  - `logs/trace/trace.jsonl`
  - `logs/trace/summary.json`
  - `logs/conversation_history/conversation_history.json`

---

## Extension points (common edits)

- Retrieval query:
  - from `goal` -> (goal + site/task metadata)
- Site filtering:
  - `site="shopping_admin"` is currently hard-coded in agent
- Prompt shaping:
  - change experience formatting in `build_system_prompt`
- Logging:
  - add screenshot persistence per step (currently `screenshot_path=None` in `StepTrace`)

---

## Architecture diagrams

See `architecture_diagrams.md` in the same folder for:

- Component diagram (module-level boundaries)
- Runtime sequence diagram (one step loop)

---

## Export slides (Marp)

Option 1: VS Code Marp extension

- Open this file and export to PDF/PPTX.

Option 2: Marp CLI

- `npx @marp-team/marp-cli src/slides.md --pdf`
- `npx @marp-team/marp-cli src/slides.md --pptx`

---

## End

Questions / topics to zoom in:

- Retrieval quality (experience schema + summary/content design)
- Prompt injection strategies (rules vs examples)
- Failure modes (invalid actions, long observations)
