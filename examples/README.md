# examples

Runnable checkpoints for the [agenteng curriculum](../README.md). Each script is the cumulative end state of one module — read the module first, then run the script to see it in action.

Each is one self-contained file with no imports between scripts. Code is duplicated across files on purpose: a reader can open any script and understand the entire system at that level without jumping around.

## Setup (once)

```bash
cp .env.example .env          # paste your Anthropic API key
uv sync                        # install deps into ./.venv
```

The `uv sync` pulls in `sentence-transformers` (used by `memory_agent.py` and later) which downloads ~2GB of PyTorch. The first run of any memory-using script also downloads the embedding model itself (~80MB).

## Run a script

```bash
uv run llmcall.py             # or any other script
```

Run from `examples/` — the `.env` and `.venv` are resolved relative to this directory.

## Checkpoints

Each script is a strict superset of the previous one's capabilities.

| # | Script | Module | Adds |
|---|---|---|---|
| 1 | [`llmcall.py`](./llmcall.py) | [2](../modules/02-an-llm-call/) | One LLM call — request in, response out |
| 2 | [`chatbot.py`](./chatbot.py) | [3](../modules/03-add-a-loop/) | A loop around the API call → multi-turn conversation |
| 3 | [`agent.py`](./agent.py) | [4](../modules/04-add-tools/) | Tools + TAO loop + async parallel dispatch — first agent |
| 4 | [`memory_agent.py`](./memory_agent.py) | [5](../modules/05-add-memory/) | Persistent state + token budget eviction + semantic recall |
| 5 | [`safe_agent.py`](./safe_agent.py) | [6](../modules/06-add-sandboxing/), [8](../modules/08-add-guardrails/) | Docker-sandboxed `bash` + approval gates + loop bounds + retry |
| 6 | [`traced_agent.py`](./traced_agent.py) | [9](../modules/09-add-observability/) | Structured tracing emitted as JSONL spans |
| 7 | [`production_agent.py`](./production_agent.py) | [10](../modules/10-add-performance/) | Prompt caching + tool caching + threading + streaming + structured prompts + `assemble()` — the curriculum's destination |

(Module 7 — Evaluation — ships at [`evals/`](../evals/) at the repo root, since it tests the scripts here rather than being one.)

## Picking which one to run

- **Reading the curriculum?** Run each script as you finish its module.
- **Want a coding companion that remembers across sessions?** `memory_agent.py`.
- **Going to deploy or run on shared infra?** `safe_agent.py` minimum — sandboxes the `bash` tool.
- **Debugging a behavior issue?** `traced_agent.py`. Every action ends up in `~/.traced-agent/traces.jsonl`.
- **Want the full production-shaped artifact?** `production_agent.py`.

## Dockerfile

`Dockerfile.sandbox` lives here. The `safe_agent.py`, `traced_agent.py`, and `production_agent.py` scripts all build and use it on first run. Requires Docker to be running.

## State files

Stateful scripts persist to `~/.<name>/` directories:

- `~/.memory-agent/` — `messages.json`, `recall.json`
- `~/.safe-agent/` — same plus the sandbox container survives between runs
- `~/.traced-agent/` — adds `traces.jsonl`
- `~/.production-agent/` — same shape as traced
