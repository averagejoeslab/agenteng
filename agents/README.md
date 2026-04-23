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

Each agent is a snapshot of the agent the content builds at the end of a given Part.

- **[basic-agent](./basic-agent/)** — Part 1 end state. Minimal coding agent: REPL + TAO loop + one tool (`read`).
- **[coding-agent](./coding-agent/)** — Part 2 end state. Multi-tool coding agent: same loop + registry-based dispatch + six tools (`read`, `write`, `edit`, `grep`, `glob`, `bash`).

Future Parts will add more agent snapshots as siblings (or evolve an existing one).
