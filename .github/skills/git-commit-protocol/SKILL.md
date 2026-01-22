---
name: git-commit-protocol
description: Generate git commit messages and provide safe git commands using the repository's Conventional Commits rules (scope, body, quoting, and branch strategy). Use this when the user asks to generate/suggest/write a commit message or perform git operations.
---

# Git Commit Protocol
This skill help you follow a strict, repeatable workflow for git commit messaging and git operations.

## When to use
Use this skill when the user asks to:
- generate/suggest/write a git commit message
- perform git operations related to commits (staging, committing, switching branches)

If the user is *not* asking for commit-related work, do not apply these rules.

## Commit message format (MANDATORY)
Use Conventional Commits:

```text
<type>(<scope>): <subject>

<body>

<footer>

```

- **Types:**
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

## Body requirements (MANDATORY for non-trivial changes)
- Always include a body for non-trivial changes.
- Use bullet points (`- `) per distinct change.
- Explain **what changed** and **why** (motivation), not just how.
- If relevant, mention issue numbers or config changes.

## Scope handling
- If the user specifies a file list or scope (e.g., "commit changes in `utils.py`"), ONLY describe/analyze those files.
- Otherwise, describe all staged/modified changes that are in context.

## Branch strategy & commands (STRICT)
- Use `git switch <branch>` to change branches.
- Use `git switch -c <branch>` to create and switch.
- DO NOT use `git checkout` for branch operations.
- Assume commit is intended for the current branch unless explicitly told otherwise.

## Language & formatting
- Commit message MUST be in English unless the user explicitly requests Chinese.
- In commit message text, wrap file names, paths, symbols, and code values in backticks.

## Shell safety (CRITICAL)
When providing a CLI command (e.g., `git commit -m ...`), you **MUST** wrap the commit message in **single quotes** (`'...'`) instead of double quotes.
- *Reason:* Double quotes allow the shell to interpret backticks (```) as command execution, which causes errors. Single quotes treat backticks as literal text.
- *Correct:* git commit -m 'feat: update `gen_prompt.py` logic'
- *Incorrect:* git commit -m "feat: update `gen_prompt.py` logic"

Examples:

```sh
git commit -m 'feat(task_generate): add `gen_prompt.py` builder'
```

If the commit message contains an apostrophe `'`, escape it so the shell command remains valid.

## Output template (use as default)
```text
<type>(<scope>): <subject>

- <bullet 1>
- <bullet 2>

<optional footer>

```

### Example Output

```text
feat(task_generate): implement MVP prompt builder for WebArena

- Create `gen_prompt.py` to handle initial template filling logic.
- Add configuration parsing in `config.py` to support dynamic `DATA_PATH`.
- Update `README.md` to reflect the new usage of the `Builder` class.

Closes #123

```
