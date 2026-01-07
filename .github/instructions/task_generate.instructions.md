---
applyTo: '**'
---
# Copilot Custom Instructions for CuES on WebArena

You are an expert AI developer assisting in porting the **CuES** (Automated Dataset Construction) method to the **WebArena** environment.

## Project Context & Awareness
- **Core Method:** CuES (Refer to source code in `#file:CuES` and docs in `#file:CuES/README.md`).
- **Target Platform:** WebArena (Refer to `#file:webarena`).
- **Goal:** Implement the dataset generation logic inside `webarena/task_generate`.

## Directory-Specific Behaviors (CRITICAL)

### 1. MODE: MVP / Prototype
**Trigger:** When the user is working on or asking about files in `.webarena/demo/task_generate`.
**Rules:**
- **Philosophy:** "Quick & Dirty", Minimal Viable Product.
- **Code Style:** Flat structure, minimal abstraction. Use scripts over complex classes. Hardcode paths if it saves time.
- **Focus:** Achieve the core functionality (generating a task) with the least amount of code.
- **Dependencies:** Minimize external dependencies; keep it self-contained.

### 2. MODE: Production / Full Implementation
**Trigger:** When the user is working on or asking about files in `.webarena/task_generate` (the main implementation).
**Rules:**
- **Philosophy:** Robust, Scalable, Structured.
- **Code Style:** Modular design, proper error handling, type hinting (Python type hints strongly recommended), and clean configuration management.
- **Structure:** Isolate logic into modules (e.g., `builder.py`, `config.py`, `utils.py`).
- **Focus:** Functionality first, but structure it for future expansion. Do not over-optimize prematurely, but strictly avoid "spaghetti code".

---

## Interaction Style
- **Agent Mode:** When running in Agent mode, always check the current file path to determine which "MODE" (MVP or Production) to apply.
- **Language:** Respond in the language used by the user (Chinese/English).