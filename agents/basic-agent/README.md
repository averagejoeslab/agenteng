# basic-agent

The minimal coding agent. Terminal REPL wrapping a TAO (Think, Act, Observe) loop, with `read` as its single tool. The end state of [Module 3: Add a loop](../../modules/03-add-a-loop/).

Built across:

- **[Module 2: An LLM call](../../modules/02-an-llm-call/)** — a single LLM call (sync, then async streaming)
- **[Module 3: Add a loop](../../modules/03-add-a-loop/)** — multi-turn → first tool → TAO loop → async refactor for parallel tool dispatch

## Run it

From the `agents/` directory (one level up):

```bash
uv run basic-agent/main.py
```

Then at the `❯` prompt:

```
❯ What's in pyproject.toml?
❯ Does main.py import python-dotenv?
❯ /q
```

The model calls `read(path=...)` when it needs to examine a file. Paths resolve relative to the directory you ran the command from (so run from `agents/` to reach `pyproject.toml`, or from the repo root to reach project-level files).

## Files

- `main.py` — the agent (~70 lines)

Dependencies, venv, and `.env` live at the `agents/` level.
