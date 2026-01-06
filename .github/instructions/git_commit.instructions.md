---
applyTo: '**'
---
## Git Commit Protocol

**Trigger:** When asked to generate, suggest, or write a git commit message.

### 1. Standard Format (Conventional Commits)
You must strictly follow this structure:
```text
<type>(<scope>): <subject>

<body>

<footer>

```

* **Types:**
* `feat`: A new feature
* `fix`: A bug fix
* `docs`: Documentation only changes
* `style`: Changes that do not affect the meaning of the code (white-space, formatting, etc)
* `refactor`: A code change that neither fixes a bug nor adds a feature
* `perf`: A code change that improves performance
* `test`: Adding missing tests or correcting existing tests
* `chore`: Changes to the build process or auxiliary tools and libraries


* **Scope:** The specific module or file affected (e.g., `CuES`, `WebArena`, `task_generate`, `demo`).
* **Subject:** Brief summary, imperative mood, no period at the end (max 50 chars).

### 2. Content Requirements (Detailed & Structured)

* **The Body:**
* **Mandatory:** Must be included for all non-trivial changes.
* **Format:** Use bullet points (`- `) for each distinct change.
* **Content:** Explain **what** changed and **why** (motivation), not just *how*.
* **Reference:** Mention relevant issue numbers or config changes if applicable.


* **Scope Handling:**
* **Specific Files:** If the user specifies a file list or scope (e.g., "commit changes in `utils.py`"), **ONLY** analyze and describe changes in those specific files. Ignore other staged files in the context.
* **Default:** If no files are specified, analyze all staged/modified changes provided in the context.



### 3. Branch Strategy

* **Default Behavior:** Always assume the commit is intended for the **currently checked-out branch**. Do not suggest switching branches, creating new branches, or merging unless explicitly requested.
* **Explicit Override:** Only deviate from the current branch if the user explicitly specifies a target branch (e.g., "commit this to a new feature branch" or "commit to `dev`").

### 4. Writing Style Guidelines (Best Practices)

* **Imperative Mood:** Use "Add" instead of "Added", "Fix" instead of "Fixed".
* **Language:** Write the commit message in **English** (standard convention) unless the user explicitly asks for Chinese.
* **Breaking Changes:** If the code change breaks backward compatibility (especially in `task_generate`), add `BREAKING CHANGE:` in the footer describing the migration path.

### 5. Example Output

```text
feat(task_generate): implement MVP prompt builder for WebArena

- Create `gen_prompt.py` to handle initial template filling.
- Add configuration parsing logic in `config.py`.
- Update `README.md` to reflect new usage of the prompt builder.

Closes #123

```