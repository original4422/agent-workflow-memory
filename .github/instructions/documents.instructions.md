---
applyTo: '**'
---
## Documentation & Logging Protocols (MANDATORY)

**Scope Constraint (CRITICAL):**
The following actions apply **ONLY** to the specific target folder where code modifications actually occurred in the current turn.
- **Do NOT** update the `README.md` or `CHANGELOG` of other target folders if no code was changed inside them.
- **Example:** If you modified files in `./webarena/demo/task_generate`, you must ONLY update the docs in `./webarena/demo/task_generate`. Ignore `./webarena/task_generate`.

**Target Folders:** Only the 3 folders: `./webarena/demo/task_generate`, `./webarena/demo/webarena`, `./webarena/task_generate`

### 1. Sync README.md
- **Requirement:** Ensure the `README.md` **inside the modified target folder** is up-to-date.
- **Action:** Update that specific `README.md` to reflect the latest changes in flow, usage, or file structure immediately after coding.

### 2. Update CHANGELOG
- **Location:** Look for a `CHANGELOG` folder **inside the modified target folder**. If missing, create it there.
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