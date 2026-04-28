# optimized-agent

Adds **cost and latency optimizations** to the traced-agent. Part of the end state of [Module 10: Add performance](../../modules/10-add-performance/).

- **[Module 10: Add performance](../../modules/10-add-performance/)** — Anthropic prompt caching with `cache_control` on system + tool schemas, idempotent tool-output caching with mutation invalidation, cheap-model routing (`claude-haiku-4-5`) for summaries, `asyncio.to_thread` for blocking sync tool bodies, and streaming the final response.

## Run it

Requires Docker.

From the `agents/` directory:

```bash
uv run optimized-agent/main.py
```

## State files

- `~/.optimized-agent/messages.json`, `recall.json`, `traces.jsonl`

## What's new vs. traced-agent

- **Prompt caching:** `cache_control` markers on the system prompt and the last tool schema cache the full prefix server-side. ~85% input-token savings on cached portions within a session.
- **Tool output caching:** `read`, `glob`, `grep` results are memoized in-process by `(name, input)` hash. Cache invalidates on `write`, `edit`, `bash` calls.
- **`asyncio.to_thread` for sync tool bodies:** when the model fans out parallel tool calls, blocking I/O genuinely runs concurrently instead of serializing on the event loop.
- **Streaming:** the agent uses `messages.stream` and prints text only when the response has no `tool_use` blocks. Mid-loop responses don't stream-print (we need the full response to dispatch tools); the final response does.

## What this didn't address

- The system prompt is still a one-liner — see `production-agent` for structured prompts and the `assemble()` function.
