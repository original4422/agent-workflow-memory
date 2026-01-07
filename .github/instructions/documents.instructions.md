---
applyTo: '**'
---
## Documentation & Logging Protocols (MANDATORY)

**You must perform the following two actions after ANY code modification or generation:**

**Target Folder**：webarena/demo/task_generate, webarena/demo/webarena, webarena/task_generate

### 1. Sync README.md
- **Requirement:** Every subdirectory (`./webarena/demo/task_generate`, `webarena/demo/webarena`, `./webarena/task_generate`) must have a `README.md`.
- **Action:** Update the `README.md` to reflect the latest changes in flow, usage, or file structure immediately after coding.

### 2. Update CHANGELOG
- **Location:** Look for a `CHANGELOG` folder in the current working directory. If missing, create it.
- **Filename:** Create/Update a markdown file named by today's date: `CHANGELOG/YYYY-MM-DD.md` (e.g., `2024-05-20.md`).
- **Content Format:**
  - **Header:** If the file is new, add a `summary` section at the top overviewing the day's goals.
  - **Entries:** Append changes sequentially.
  - **Format Example:**
    ```markdown
    ## Summary
    Today's focus was on implementing the initial prompt generator for WebArena.

    ## Changes
    1. [Feature] Added `gen_prompt.py` to handle prompt construction.
    2. [Fix] Resolved path issue in `config.yaml`.
    3. [Docs] Updated main README with usage instructions.
    ```
