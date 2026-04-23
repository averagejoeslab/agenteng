# basic-agent

The minimal coding agent Part 1 produces. Terminal REPL wrapping a TAO (Think, Act, Observe) loop, with `read` as its single tool.

Built step by step across Modules 2–4:

- **[Module 2](../../agentic-engineering/modules/02-a-single-llm-call/)** — a single LLM call
- **[Module 3](../../agentic-engineering/modules/03-the-tao-loop/)** — the TAO loop + terminal environment
- **[Module 4](../../agentic-engineering/modules/04-first-tool/)** — the first tool (this agent's end state)

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

- `main.py` — the agent (~70 lines, built across Modules 2–4)

Dependencies, venv, and `.env` live at the `agents/` level.
