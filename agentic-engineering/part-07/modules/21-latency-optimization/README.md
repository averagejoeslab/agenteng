# Latency optimization

Module 20 reduced cost. This module reduces wall time. The goals are different — same model, same eval scores, just less time staring at the prompt before the answer arrives.

Three levers, in order of impact: **make blocking tools not block**, **stream the final response**, and **parallelize what's actually parallelizable**.

## Where the wall time goes

Module 16's traces tell you. Sum the `duration_ms` of LLM calls vs tool calls in a typical turn:

```bash
jq -s '
  [.[] | select(.name == "llm.call")] | map(.duration_ms) | add as $llm |
  [.[] | select(.name == "tool.call")] | map(.duration_ms) | add as $tool |
  {llm: $llm, tool: $tool, total: ($llm + $tool)}
' ~/.coding-agent/traces.jsonl
```

Two patterns emerge:

- **Read-heavy turns** (look at this file, summarize it): LLM time dominates. ~2-4s per call, 1-3 calls per turn. Tool time negligible.
- **Tool-heavy turns** (search the codebase, run a test, edit a file): tool time can match or exceed LLM time. A `bash` shelling out for 10s shows up clearly here.

Different turns benefit from different optimizations. Profile first, optimize second.

## Lever 1: `asyncio.to_thread` for blocking tools

Module 6 made the tool dispatch async. But the tool *bodies* — the actual `subprocess.run`, `open`, `os.walk` — are still synchronous. When the agent dispatches one tool, the event loop runs that tool's blocking code on the main thread, and *every other concurrent coroutine waits*.

For a single-tool turn this is invisible. For parallel dispatch (`asyncio.gather` over multiple tool calls), it matters. Three reads gathered concurrently still execute serially because each blocks the event loop in turn.

The fix: wrap the tool body in `asyncio.to_thread`, which runs the synchronous code in a thread pool, freeing the event loop to schedule the next coroutine.

```python
import asyncio


async def read(path: str) -> str:
    return await asyncio.to_thread(_read_sync, path)


def _read_sync(path: str) -> str:
    with open(path, "r") as f:
        return f.read()
```

Or wrap inline at the executor boundary so individual tool functions stay clean:

```python
async def execute_tool(name: str, input: dict, ...) -> str:
    tool = TOOLS.get(name)
    if tool is None:
        return f"error: unknown tool {name}"
    # ... approval, span ...
    fn = tool["fn"]
    if iscoroutinefunction(fn):
        result = await fn(**input)
    else:
        result = await asyncio.to_thread(fn, **input)
    return result if isinstance(result, str) else str(result)
```

For most file tools the per-call savings are small (microseconds). For `bash` (multi-second commands) and `grep` (file walks across thousands of files) the savings are real, especially when multiple are dispatched in parallel.

## Lever 2: Stream the final response

Module 2 showed streaming for one-call UX. Module 4 noted the agent can't stream tool-using responses because the agent needs the full response to detect `tool_use` blocks. That's true *except for the final response* — the one with no tool_use, which is what the user actually sees.

Pattern: when the model's response is text-only (no tool_use), stream it. Otherwise (it has tool_use), wait for the full response and dispatch as before.

```python
# In the inner TAO loop, replace messages.create with stream when checking the final response

while True:
    # Use streaming so we can decide whether to stream-display or buffer
    async with client.messages.stream(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system=system,
        messages=messages,
        tools=TOOL_SCHEMAS,
    ) as stream:
        full_response = None
        async for event in stream:
            if event.type == "content_block_delta" and event.delta.type == "text_delta":
                # We don't yet know if the final response has tool_use.
                # Buffer the text deltas; print them only after we confirm no tool_use.
                pass
        full_response = await stream.get_final_message()

    messages.append({"role": "assistant", "content": full_response.content})

    tool_calls = [b for b in full_response.content if b.type == "tool_use"]
    if not tool_calls:
        # Final response — print all the text we received
        for block in full_response.content:
            if block.type == "text":
                print(block.text)
        break

    # Tool path: dispatch and continue
    # ...
```

The honest version of streaming-with-tools is more complex than this sketch — you'd want to print text deltas as they arrive *unless* a tool_use appears in the same response, then erase the partial print. SDK helpers can detect the response shape early. For curriculum purposes, the above structure communicates the idea: stream when safe, buffer when not.

For tool-heavy workflows (lots of tool calls, brief final answer), streaming barely helps. For research-style workflows (one tool call, long synthesis), it cuts perceived latency dramatically.

## Lever 3: Parallelism beyond gather

Module 6 already gives `asyncio.gather` for tool dispatch. Two further parallelism opportunities:

**Parallel LLM calls** — when multiple iterations of the agent could run in parallel (e.g., the agent decides to search for two different things and pull both into context). The agent isn't doing this today — the model emits one batch of tools, gets results, decides next batch. But for compositional tasks ("for each of these 5 files, summarize it"), spawning N independent sub-agents in parallel makes sense.

**Tool prefetching** — predict which tool the agent will call next based on the current turn shape, dispatch it speculatively. Risky: wrong predictions waste compute. Done well, it's how some interactive coding agents feel snappy.

Both of these are advanced and not critical. Mention, don't implement.

## Putting it together

For a typical coding agent session, the latency improvement from this module:

| Lever | Improvement |
|---|---|
| `asyncio.to_thread` for blocking tools | 30-60% on parallel-tool turns |
| Streaming the final response | Time-to-first-token drops to ~200ms (was full-response wait) |
| Parallelism beyond gather | Variable; only helps specific workloads |

Stack with Module 20's cost optimizations and you have an agent that's both cheaper and faster.

## Trade-offs to know

**`asyncio.to_thread` overhead.** Thread pool dispatch costs ~milliseconds. For tools that complete in microseconds, that's overhead. Only use for tools that genuinely take time.

**Streaming complexity.** The "stream when safe, buffer when not" logic in the inner loop adds branching that Module 16's tracing has to keep up with. Trace each streamed-vs-buffered call appropriately.

**Eval impact of streaming.** The eval harness from Module 19 captures stdout. If the agent streams tokens to stdout incrementally, the harness sees them eventually but timing-sensitive evals may need adjustment.

**Parallelism doesn't compose linearly.** Doubling parallelism doesn't halve wall time — there's coordination overhead, and most workloads have serial bottlenecks. Profile first, parallelize where data shows it helps.

## What this didn't address

- **Server-side latency.** The Anthropic API has its own response time which you can't optimize. You can pick faster models (Haiku is faster than Sonnet is faster than Opus) but that's a quality/cost/latency tradeoff, not a free win.
- **Network latency.** Edge deployment, regional API endpoints, persistent connections — relevant for production but specialized.
- **Token-budget effects.** Longer context = slower inference. Module 12's eviction directly reduces latency too. Already covered.

## Prompt your coding agent

If you want your coding agent to write this for you, paste:

```
Add latency optimizations to main.py.

1. Wrap blocking tool bodies with asyncio.to_thread:
   - In the executor (execute_tool), if the tool function is not a coroutine (use inspect.iscoroutinefunction), dispatch it via asyncio.to_thread(fn, **input) instead of calling it directly.
   - Tools written as async def stay as-is.

2. Stream the final assistant response:
   - Replace the inner-loop client.messages.create call with client.messages.stream(...) inside `async with`.
   - After the stream completes, await stream.get_final_message() to get the full response (with tool_use blocks if any).
   - If the final message has no tool_use blocks, print text from the streamed events as they arrived (or print the final text if you didn't capture deltas).
   - If it has tool_use blocks, treat as before — don't stream-print, just append and dispatch.

3. Update the trace span for llm.call to record streaming=True/False so you can compare latency in the trace.

Don't change tool functions, registry, or eval logic. Run the eval suite to confirm no regression.
```

The prompt tells your agent *what* to write. The module explains *why* — read it first.

---

**Next:** [Module 22: Prompt design](../../../part-08/modules/22-prompt-design/)
