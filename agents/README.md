# agents

Reference agents built across the agenteng content. One shared venv, one shared `.env`, one shared `pyproject.toml` — each agent is a subdirectory with its own `main.py`.

## Setup (once)

```bash
cp .env.example .env          # paste your Anthropic API key
uv sync                        # install deps into ./.venv
```

## Run an agent

```bash
uv run basic-agent/main.py
```

Run this from `agents/` — the `.env` and `.venv` are resolved relative to this directory.

## Agents

- **[basic-agent](./basic-agent/)** — minimal coding agent. Terminal REPL + TAO loop + one tool (`read`). Built across Part 1 of the content.

Future parts of the content will either evolve `basic-agent/` or add new sibling agents.
