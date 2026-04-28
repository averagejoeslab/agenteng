# production-agent

The final agent in the curriculum. Adds **structured prompt design** and a unified **`assemble()` function** that brings memory, recall, prompt, and budget together at one call site.

The curriculum's destination — the final reference in [Module 10: Add performance](../../modules/10-add-performance/).

- **Structured prompt design** — the system prompt now has named sections (Role, Tools, Working style, Completion criteria) instead of a one-liner.
- **`assemble()` as a single function** — `assemble(user_input, messages, recall_entries)` returns `{system, tools, messages}` ready for the LLM call. The previously ad-hoc per-turn assembly logic is now one named function.

## Run it

Requires Docker.

From the `agents/` directory:

```bash
uv run production-agent/main.py
```

## State files

- `~/.production-agent/messages.json`, `recall.json`, `traces.jsonl`

## What's new vs. optimized-agent

- **Structured system prompt.** Sections for role, tools, working style, completion criteria. The model parses structure better than narrative; behavioral consistency improves.
- **`assemble()` as a single function.** All context-shaping decisions (system + recalled memories + tools + trimmed messages) live in one place. New context concerns (more memory sources, dynamic prompts) plug in here.
- **Cleaner main loop.** The TAO loop uses the assembled context directly; no inline construction of system blocks.

## What this completes

production-agent ships everything the curriculum builds:

- Async TAO loop with parallel tool dispatch (Modules 3–4)
- Persistence, token budget, semantic recall (Module 5)
- Docker sandbox (Module 6)
- Approval gates, loop bounds, retry/backoff (Module 8)
- Structured tracing (Module 9)
- Prompt caching, tool output caching, threading, streaming, structured prompt + `assemble()` (Module 10)

Plus the eval suite at `evals/` (Module 7) tests this and any other agent.

This is the curriculum's destination.
