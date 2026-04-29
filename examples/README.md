# examples

Runnable checkpoints for the [agenteng curriculum](../README.md). Each script is the cumulative end state of one module — read the module first, then run the script to see it in action. The filename describes what the system has *become* at that point.

Each is one self-contained file with no imports between scripts. Code is duplicated across files on purpose: a reader can open any script and understand the entire system at that level without jumping around.

## Setup (once)

```bash
cp .env.example .env          # paste your Anthropic API key
uv sync                        # install deps into ./.venv
```

The `uv sync` pulls in `sentence-transformers` (used by `stateful_chatbot.py` and later) which downloads ~2GB of PyTorch. The first run of any memory-using script also downloads the embedding model itself (~80MB).

## Run a script

```bash
uv run llm_call.py            # or any other script
```

Run from `examples/` — the `.env` and `.venv` are resolved relative to this directory.

## Checkpoints

Each script is a strict superset of the previous one's capabilities.

| # | Script | Module | Adds |
|---|---|---|---|
| 1 | [`llm_call.py`](./llm_call.py) | [2](../modules/02-an-llm-call/) | One LLM call — request in, response out |
| 2 | [`stateless_chatbot.py`](./stateless_chatbot.py) | [3](../modules/03-add-a-loop/) | A loop around the API call → multi-turn conversation, in-memory only |
| 3 | [`stateful_chatbot.py`](./stateful_chatbot.py) | [4](../modules/04-add-memory/) | Persistence + token budget eviction + semantic recall |
| 4 | [`agent.py`](./agent.py) | [5](../modules/05-add-tools/) | Tools + TAO loop + async parallel dispatch — stateful agent |
| 5 | [`sandbox_agent.py`](./sandbox_agent.py) | [6](../modules/06-add-sandboxing/) | Docker-isolated `bash` |
| 6 | [`safe_agent.py`](./safe_agent.py) | [7](../modules/07-add-guardrails/) | Approval gates + loop bounds + retry/backoff |
| 7 | [`traced_agent.py`](./traced_agent.py) | [8](../modules/08-add-observability/) | Structured tracing emitted as JSONL spans |
| 8 | [`production_agent.py`](./production_agent.py) | [10](../modules/10-add-performance/) | Prompt caching + tool caching + threading + structured prompts + `assemble()` — the curriculum's destination |

(Module 9 — Evaluation — ships at [`evals/`](../evals/) at the repo root, since it tests the scripts here rather than being one.)

## Picking which one to run

- **Reading the curriculum?** Run each script as you finish its module.
- **Want a chat companion that remembers across sessions?** `stateful_chatbot.py`.
- **Want a coding agent?** `agent.py` minimum; `safe_agent.py` if you want sandboxing + approval gates.
- **Debugging a behavior issue?** `traced_agent.py`. Every action ends up in `~/.traced-agent/traces.jsonl`.
- **Want the full production-shaped artifact?** `production_agent.py`.

## Dockerfile

`Dockerfile.sandbox` lives here. The `sandbox_agent.py`, `safe_agent.py`, `traced_agent.py`, and `production_agent.py` scripts all build and use it on first run. Requires Docker to be running.

## State files

Stateful scripts persist to `~/.<name>/` directories:

- `~/.stateful-chatbot/` — `messages.json`, `recall.json`
- `~/.agent/` — same shape as stateful-chatbot
- `~/.sandbox-agent/` — same plus the sandbox container survives between runs
- `~/.safe-agent/` — adds approval/loop-bound state
- `~/.traced-agent/` — adds `traces.jsonl`
- `~/.production-agent/` — same shape as traced
