# production-agent

The Part 8 end state — and the final agent in the curriculum. Adds **structured prompt design** and a unified **`assemble()` function** that brings memory, recall, prompt, and budget together at one call site.

Built across Modules 22–23:

- **[Module 22: Prompt design](../../agentic-engineering/part-08/modules/22-prompt-design/)** — System prompt now has named sections (Role, Tools, Working style, Completion criteria) instead of a one-liner.
- **[Module 23: Context assembly](../../agentic-engineering/part-08/modules/23-context-assembly/)** — `assemble(user_input, messages, recall_entries)` returns `{system, tools, messages}` ready for the LLM call. The previously ad-hoc per-turn assembly logic is now one named function.

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

production-agent ships everything from Parts 1-8:

- Async TAO loop with parallel tool dispatch (Parts 1-2)
- Persistence, token budget, semantic recall (Part 3)
- Sandbox, approval gates, loop bounds (Part 4)
- Structured tracing (Part 5)
- Prompt caching, tool output caching, threading, streaming (Part 7)
- Structured prompt design + unified context assembly (Part 8)

Plus the eval suite at `evals/` (Part 6) tests this and any other agent.

This is the curriculum's destination.
