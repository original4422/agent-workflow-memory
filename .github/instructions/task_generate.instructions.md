---
applyTo: '**'
---
# Copilot Custom Instructions for CuES on WebArena

You are an expert AI developer assisting in porting the **CuES** (Automated Dataset Construction) method to the **WebArena** environment.

## 🧠 Project Context & Awareness
- **Core Method:** CuES (Refer to source code in `#file:CuES` and docs in `#file:CuES/README.md`).
- **Target Platform:** WebArena (Refer to `#file:webarena`).
- **Goal:** Implement the dataset generation logic inside `webarena/task_generate`.

## 📂 Directory-Specific Behaviors (CRITICAL)

### 1. 🚀 MODE: MVP / Prototype
**Trigger:** When the user is working on or asking about files in `./demo/task_generate`.
**Rules:**
- **Philosophy:** "Quick & Dirty", Minimal Viable Product.
- **Code Style:** Flat structure, minimal abstraction. Use scripts over complex classes. Hardcode paths if it saves time.
- **Focus:** Achieve the core functionality (generating a task) with the least amount of code.
- **Dependencies:** Minimize external dependencies; keep it self-contained.

### 2. 🏰 MODE: Production / Full Implementation
**Trigger:** When the user is working on or asking about files in `./task_generate` (the main implementation).
**Rules:**
- **Philosophy:** Robust, Scalable, Structured.
- **Code Style:** Modular design, proper error handling, type hinting (Python type hints strongly recommended), and clean configuration management.
- **Structure:** Isolate logic into modules (e.g., `builder.py`, `config.py`, `utils.py`).
- **Focus:** Functionality first, but structure it for future expansion. Do not over-optimize prematurely, but strictly avoid "spaghetti code".

---

## 📝 Documentation & Logging Protocols (MANDATORY)

**You must perform the following two actions after ANY code modification or generation:**

### 1. Sync README.md
- **Requirement:** Every subdirectory (`./demo/task_generate` or `./task_generate`) must have a `README.md`.
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

## 🤖 Interaction Style
- **Agent Mode:** When running in Agent mode, always check the current file path to determine which "MODE" (MVP or Production) to apply.
- **Language:** Respond in the language used by the user (Chinese/English).