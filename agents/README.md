# agents

Reference agents built across the agenteng curriculum. Each is a self-contained snapshot of the agent at the end of one Part — runnable on its own, readable in a single file. Each builds on the previous Part's features, cumulatively.

## Setup (once)

```bash
cp .env.example .env          # paste your Anthropic API key
uv sync                        # install deps into ./.venv
```

The `uv sync` pulls in `sentence-transformers` (used by `memory-agent` and later) which downloads ~2GB of PyTorch. The first run of any memory-using agent also downloads the embedding model itself (~80MB).

## Run an agent

```bash
uv run basic-agent/main.py     # or any other agent
```

Run from `agents/` — the `.env` and `.venv` are resolved relative to this directory.

## Agents

Each is the cumulative end state of one Part — a strict superset of the previous one's features.

| # | Agent | Part | Adds |
|---|---|---|---|
| 1 | [`basic-agent`](./basic-agent/) | Part 1 | REPL + TAO loop + one tool (read), async with parallel dispatch |
| 2 | [`coding-agent`](./coding-agent/) | Part 2 | Tool registry + six tools (write/edit/grep/glob/bash) + centralized executor |
| 3 | [`memory-agent`](./memory-agent/) | Part 3 | Persistent state + token budget eviction + semantic recall |
| 4 | [`safe-agent`](./safe-agent/) | Part 4 | Docker-sandboxed bash + approval gates + loop bounds + retry |
| 5 | [`traced-agent`](./traced-agent/) | Part 5 | Structured tracing emitted as JSONL spans |
| 6 | [`optimized-agent`](./optimized-agent/) | Part 7 | Prompt caching + tool output caching + threading + streaming |
| 7 | [`production-agent`](./production-agent/) | Part 8 | Structured prompts + the `assemble()` function — the curriculum's destination |

(Part 6 — Evaluation — ships at [`evals/`](../evals/) at the repo root, since it tests other agents rather than being one.)

## Picking which agent to run

- **Learning the basics?** `basic-agent` or `coding-agent`. Smallest, easiest to read.
- **Want a real coding companion that remembers across sessions?** `memory-agent`.
- **Going to deploy or run on shared infra?** `safe-agent` minimum; sandboxes the `bash` tool.
- **Debugging a behavior issue?** `traced-agent`. Every action ends up in `~/.traced-agent/traces.jsonl`.
- **Want the full production-shaped artifact?** `production-agent`.

## Dockerfile

`Dockerfile.sandbox` lives here. The `safe-agent`, `traced-agent`, `optimized-agent`, and `production-agent` all build and use it on first run. Requires Docker to be running.

## Self-contained code

Each agent is one `main.py`, no imports from sibling agents. Code is duplicated across agents on purpose — readers can read one file end-to-end and understand the entire system at that level. The cost is more files to maintain; the benefit is teaching clarity.
