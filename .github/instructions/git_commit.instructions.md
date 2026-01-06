---
applyTo: '**'
---
## Git Commit Protocol

**Trigger:** When asked to generate, suggest, or write a git commit message, or perform git operations.

### 1. Standard Format (Conventional Commits)
You must strictly follow this structure:
```text
<type>(<scope>): <subject>

<body>

<footer>

```

* **Types:**
  - `feat`: A new feature
  - `fix`: A bug fix
  - `docs`: Documentation only changes
  - `style`: Changes that do not affect the meaning of the code (white-space, formatting, etc)
  - `refactor`: A code change that neither fixes a bug nor adds a feature
  - `perf`: A code change that improves performance
  - `test`: Adding missing tests or correcting existing tests
  - `chore`: Changes to the build process or auxiliary tools and libraries


- **Scope:** The specific module or file affected (e.g., `CuES`, `WebArena`, `task_generate`, `demo`).
- **Subject:** Brief summary, imperative mood, no period at the end (max 50 chars).

### 2. Content Requirements (Detailed & Structured)

- **The Body:**
  - **Mandatory:** Must be included for all non-trivial changes.
  - **Format:** Use bullet points (`- `) for each distinct change.
  - **Content:** Explain **what** changed and **why** (motivation), not just *how*.
  - **Reference:** Mention relevant issue numbers or config changes if applicable.


- **Scope Handling:**
  - **Specific Files:** If the user specifies a file list or scope (e.g., "commit changes in `utils.py`"), **ONLY** analyze and describe changes in those specific files. Ignore other staged files in the context.
  - **Default:** If no files are specified, analyze all staged/modified changes provided in the context.



### 3. Branch Strategy & Command Preference (STRICT)

- **Modern Commands:** STRICTLY use `git switch <branch>` to change branches and `git switch -c <branch>` to create & switch to new branches.
  - **FORBIDDEN:** Do **NOT** use `git checkout` for branch operations.
- **Default Behavior:** Always assume the commit is intended for the **currently checked-out branch**. Do not suggest switching branches unless explicitly requested.
-  **Explicit Override:** Only deviate from the current branch if the user explicitly specifies a target branch.

### 4. Writing Style Guidelines (Best Practices)

- **Code Formatting (MANDATORY):** Always enclose **file names**, **paths**, **function names**, **variables**, and **code values** in backticks (```).
  - *Example:* Update logic in `gen_prompt.py`.


- **Imperative Mood:** Use "Add" instead of "Added", "Fix" instead of "Fixed".
- **Language:** Write the commit message in **English** (standard convention) unless the user explicitly asks for Chinese.
- **Breaking Changes:** If the code change breaks backward compatibility, add `BREAKING CHANGE:` in the footer.

### 5. Shell Safety & Execution (CRITICAL)

* **Quote Wrapping:** When providing a CLI command (e.g., `git commit -m ...`), you **MUST** wrap the commit message in **single quotes** (`'...'`) instead of double quotes.
* *Reason:* Double quotes allow the shell to interpret backticks (```) as command execution, which causes errors. Single quotes treat backticks as literal text.
* *Correct:* `git commit -m 'feat: update `gen_prompt.py` logic'`
* *Incorrect:* `git commit -m "feat: update `gen_prompt.py` logic"`


* **Internal Quotes:** If the commit message itself contains a single quote (apostrophe), escape it properly so the shell command remains valid.

### 6. Example Output

```text
feat(task_generate): implement MVP prompt builder for WebArena

- Create `gen_prompt.py` to handle initial template filling logic.
- Add configuration parsing in `config.py` to support dynamic `DATA_PATH`.
- Update `README.md` to reflect the new usage of the `Builder` class.

Closes #123

```