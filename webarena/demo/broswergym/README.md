# BrowserGym Demo (Custom Task)

This folder contains a minimal, quick-and-dirty demo showing how to run a **custom BrowserGym task** without touching BrowserGym's global registry.

## What it does

- Opens Bing
- Asks you to manually search for: `WebArena code quality`
- The task succeeds when the current URL contains `/search` and the query param `q` matches the target query

## Requirements

- Python env: `myenv/webarena` (already in this repo)
- Packages:
  - `browsergym`
  - `gymnasium`
  - `playwright` (and browsers installed)

If Playwright browsers are missing:

```bash
/Users/original/Project/LLM/LLM_agent/memory/agent-workflow-memory/myenv/webarena/bin/python -m playwright install
```

## Run

From repo root:

```bash
/Users/original/Project/LLM/LLM_agent/memory/agent-workflow-memory/myenv/webarena/bin/python webarena/demo/broswergym/test.py
```

You should see a browser window. Manually perform the search. The script polls reward/done and prints success once the URL query matches.

## Key implementation notes

- The demo uses `BrowserEnv(task_entrypoint=MySimpleSearchTask, ...)` directly.
  - Do **not** use `gym.make("browsergym/openended", task_entrypoint=...)`.
  - Reason: the `browsergym/openended` env is registered in a way that already supplies a default `task_entrypoint`, and passing it again triggers a `multiple values for argument 'task_entrypoint'` error.
- The loop uses `action = None` as a valid no-op.
- `use_raw_page_output=True` is enabled to avoid DOM/AXTree extraction instability during rapid navigation.

## Changelog

See the `CHANGELOG/` folder for recent updates. Latest entries:

- 2026-01-08: Initial demo and `README.md` added.
- 2026-01-09: Refined BrowserGym demo and documentation.

## Test

Run `test.py` to launch a manual browser-based run of the demo task (see instructions above).
