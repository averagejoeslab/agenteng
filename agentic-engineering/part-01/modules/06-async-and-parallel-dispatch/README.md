# Async and parallel tool dispatch

Module 5 produced a working agent: REPL + TAO loop + one tool, all sync. The agent works correctly. This module refactors it to async — not because sync is wrong, but because there's a specific situation where sync wastes time.

## The problem

Look at the ACT phase from Module 5:

```python
# ACT: execute each requested tool
results = []
for c in tool_calls:
    results.append({
        "type": "tool_result",
        "tool_use_id": c.id,
        "content": dispatch(c),
    })
```

The model can emit *multiple* `tool_use` blocks in a single response — *"read `a.py` and `b.py` and `c.py`"*, or with several tools, *"grep for X and read file Y and run a bash command"*. They're independent operations.

In the sync code above, those independent operations run sequentially. Each tool waits for the previous one to finish before starting, even though they don't depend on each other. For one fast file read the difference is invisible. For a `grep` across thousands of files or a `bash` command that shells out, it's the difference between *"wait once"* and *"wait three times."*

The agent loop multiplies the cost. The TAO loop iterates many times across a multi-step task; each iteration may fan tools out. Sequential dispatch in a loop turns small per-iteration savings into significant cumulative wall time.

## The pattern

The pattern every language has for this: **fan out N independent operations, wait for all to finish, receive an ordered list of results.** Python calls it `asyncio.gather`. JavaScript: `Promise.all`. Go: goroutines + `sync.WaitGroup`. Rust: `futures::join_all`. The name changes; the shape doesn't.

Two properties matter:

- **Concurrency.** The runtime schedules all N operations together so their waits overlap.
- **Order preservation.** Results come back in the same order as the inputs — `outputs[i]` is the result of `tool_calls[i]` — which is what lets us pair each result back to its originating tool call.

## Cooperative concurrency

Python's `async`/`await` lets a single thread suspend a pending operation and run another. While one tool is waiting on disk or shelling out, others can be in flight simultaneously. The runtime schedules them.

This is **cooperative** because tasks yield to the runtime voluntarily (at `await` points). Compare to threading, where the OS preempts threads. For I/O-bound work — which is what tool execution mostly is — cooperative concurrency on a single thread is simpler and cheaper than threads.

Other languages have the same idea under different names: JavaScript's `Promise`, Go's goroutines + channels, Rust's `Future`s. Same shape, different syntax.

## Refactoring to async

Switch the SDK client to `AsyncAnthropic`, wrap `main` in a coroutine, make `read` and `dispatch` async, and replace the sequential `for` loop with `asyncio.gather`:

```python
import os
import asyncio
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()

client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


# The tool (async, body unchanged)
async def read(path: str) -> str:
    try:
        with open(path, "r") as f:
            return f.read()
    except Exception as e:
        return f"error: {e}"


tools = [
    {
        "name": "read",
        "description": "Read the contents of a file",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to read"},
            },
            "required": ["path"],
        },
    }
]


async def dispatch(call):
    if call.name == "read":
        return await read(**call.input)
    return f"error: unknown tool {call.name}"


async def main():
    messages = []

    while True:
        user_input = input("❯ ")
        if user_input.lower() in ("/q", "exit"):
            break

        messages.append({"role": "user", "content": user_input})

        while True:
            response = await client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=1024,
                system="You are a helpful coding assistant. Use the read tool when you need to examine file contents.",
                messages=messages,
                tools=tools,
            )
            messages.append({"role": "assistant", "content": response.content})

            for block in response.content:
                if block.type == "text":
                    print(block.text)

            tool_calls = [b for b in response.content if b.type == "tool_use"]
            if not tool_calls:
                break

            # ACT: execute every requested tool in parallel
            outputs = await asyncio.gather(*(dispatch(c) for c in tool_calls))

            messages.append({
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": c.id, "content": o}
                    for c, o in zip(tool_calls, outputs)
                ],
            })


asyncio.run(main())
```

Five changes from the sync version:

1. **`AsyncAnthropic` instead of `Anthropic`.** Same API surface, awaitable methods.
2. **`async def read`.** Body unchanged — still a synchronous file read. The function is `async` because the executor needs to be able to `await` it. Async-ness is about scheduling, not about the work inside.
3. **`async def dispatch`.** Awaits the tool function.
4. **`async def main` + `asyncio.run(main())`.** The whole REPL runs inside the event loop.
5. **`await asyncio.gather(*(dispatch(c) for c in tool_calls))`.** The sequential `for` is gone. All tool calls fan out together; the await returns once every result is in. The `zip` pairs each output back to its `tool_call`.

`input()` stays sync. It blocks the event loop while waiting for you to type, but there's nothing else running to block — the REPL is the whole program.

## What just changed

- **Multiple tool calls per response now run concurrently.** When the model asks for two reads at once, both run together. With one fast tool, you won't notice; once tools include slow operations, you will.
- **The call stack is now async all the way up.** `main` is a coroutine; the LLM call is awaited; tool functions are awaited. This is the production shape — every later concern (streaming, concurrent sessions, advanced parallelization) attaches to async.
- **The agent's behavior is otherwise unchanged.** Same loop, same dispatch logic, same end-of-turn condition. The refactor is mechanical; user experience is identical for simple cases.

## Async beyond parallel dispatch

Parallel tool dispatch is the most concrete reason for async in an agent, but it's not the only one:

- **Streaming.** The Anthropic SDK supports streaming responses (`async with client.messages.stream(...)`) — useful when the user wants to see tokens land in real time. The agent we built doesn't stream because it needs the full response to detect `tool_use` blocks before dispatching, but streaming is a reason async exists.
- **Concurrent sessions.** A server hosting an agent endpoint can handle multiple users on one process by interleaving their async tasks.
- **Async-only SDK features.** Some SDK methods are async-only.

These don't apply to a single-user CLI agent, but they're production reasons async is the default shape for LLM application code.

## What this didn't address

- **Sync tool bodies still block the event loop.** `read`'s body is `with open(path) as f: return f.read()` — when that runs, no other coroutines progress. For fast file I/O it's imperceptible. For a slow `bash` command it matters; the proper fix is `asyncio.to_thread(...)` to offload blocking work to a thread pool. That's a cost/latency optimization, not a correctness issue here.

## Prompt your coding agent

If you want your coding agent to write this for you, paste:

```
Refactor main.py from the previous module from sync to async, so multiple tool calls per response run in parallel.

1. Switch from Anthropic to AsyncAnthropic.
2. Make read, dispatch, and main async (`async def`).
3. Wrap the entry point with `asyncio.run(main())`.
4. Replace the sync `for` loop dispatch:
       results = []
       for c in tool_calls:
           results.append({...})
   with parallel dispatch:
       outputs = await asyncio.gather(*(dispatch(c) for c in tool_calls))
       messages.append({
           "role": "user",
           "content": [
               {"type": "tool_result", "tool_use_id": c.id, "content": o}
               for c, o in zip(tool_calls, outputs)
           ],
       })
5. Await the messages.create call.
6. Don't change the read function's body or the tools schema — they carry over from the previous module.
7. input() stays sync.
```

The prompt tells your agent *what* to write. The module explains *why* — read it first.

---

**Next:** [Module 7: Tool design](../../../part-02/modules/07-tool-design/)
