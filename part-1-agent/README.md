# Part 1 — reference agent

The working agent that Part 1 of the content produces.

A minimal coding agent: a terminal REPL wrapping a TAO (Think, Act, Observe) loop, with one tool — `read` — that lets the model examine files in the working directory.

Built step by step across Modules 2–4:

- **[Module 2](../agentic-engineering/modules/02-a-single-llm-call/)** — a single LLM call
- **[Module 3](../agentic-engineering/modules/03-the-tao-loop/)** — the TAO loop + terminal environment
- **[Module 4](../agentic-engineering/modules/04-first-tool/)** — the first tool (this repo's end state)

## Run it

```bash
cp .env.example .env          # paste your Anthropic API key into .env
uv sync                        # install deps
uv run main.py                 # start the REPL
```

Then at the `❯` prompt:

```
❯ What's in pyproject.toml?
❯ Does main.py import python-dotenv?
❯ /q
```

The model calls `read(path=...)` when it needs to see a file.

## Structure

```
part-1-agent/
├── main.py              # the agent (from Module 4)
├── pyproject.toml       # dependencies
├── .env.example         # copy to .env and fill in
└── .python-version      # 3.13
```

`main.py` is ~70 lines. Every line is explained across Modules 2–4.
