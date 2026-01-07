# WebArena Demo (webarena/demo/webarena)

This folder contains a minimal runnable demo script to load a generated WebArena task config and launch `ScriptBrowserEnv`.

## Files

- `test.py`: Demo runner that loads a task config JSON and resets `ScriptBrowserEnv`.

## Usage

1. Ensure your task config JSON exists (a single task dict or a list of task dicts).
2. (Optional) Select a task:
   - `TASK_ID=<int>` selects by `task_id`.
   - `TASK_INDEX=<int>` selects by list index (default: `0`).
3. Run the demo:

```bash
/Users/original/Project/LLM/LLM_agent/memory/agent-workflow-memory/myenv/webarena/bin/python webarena/demo/webarena/test.py
```

## Auto login (storage_state)

If the selected task references a missing `.auth/*_state.json` in `storage_state` (some generators also set `require_login=true`), the script automatically generates it via WebArena's built-in `auto_login`:

- Enabled by default
- Disable with `AUTO_LOGIN=0`

The `auto_login` module requires site URL environment variables.
This repo commonly uses `WA_*` variables, which the script maps to WebArena's expected names.

Examples:

```bash
export WA_SHOPPING_ADMIN='http://.../admin'
AUTO_LOGIN=1 /Users/original/Project/LLM/LLM_agent/memory/agent-workflow-memory/myenv/webarena/bin/python webarena/demo/webarena/test.py
```
