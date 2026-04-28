# Add performance

> [!NOTE]
> **Coming soon.** This module is stubbed.

A correct agent is the floor; a fast and cheap one is the bar. Long-running agents repeat work — the same system prompt, the same tool schemas, the same files. Caching, parallelism, and streaming claw that cost back without changing what the agent does.

## What this module will cover

- **Anthropic prompt caching.** Marking the system prompt and tool schemas with `cache_control` to amortize the input cost of long-lived prefixes across many turns. When it's worth it, when it isn't.
- **Tool output caching.** A read of the same file twice in one turn shouldn't pay twice. A small content-addressed cache around `read`, `grep`, `glob`.
- **Moving blocking work off the event loop.** When a tool does CPU work (regex over a big tree, embedding inference), it should run on a thread or worker so concurrent tool calls aren't serialized behind it.
- **Streaming the final answer.** From Module 2: streaming doesn't fit *during* the TAO loop (the agent needs full responses to dispatch tools), but it fits the *final* user-facing message — and that's where the latency win matters.
- **Structured prompts and `assemble()`.** A single function that brings system prompt, recalled memories, tool schemas, and trimmed messages together — turning context-shaping into one named call site instead of inline construction in the loop.

## References: optimized-agent and production-agent

Two reference agents cover this module's content:

- [`agents/optimized-agent`](../../agents/optimized-agent/) — prompt caching, tool output caching, threading, and streaming the final response.
- [`agents/production-agent`](../../agents/production-agent/) — adds the structured prompt and `assemble()` function. The curriculum's destination.

```bash
cd agents
uv run production-agent/main.py
```

Both require Docker (they include the Module 6 sandbox).

---

You've reached the end of the curriculum. Back to the [root README](../../README.md).
