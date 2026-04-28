# Async and parallel tool dispatch

Module 5 produced a working sync agent with one tool. The REPL reads input, the TAO loop iterates as the model requests tools, the conversation flows. It's correct. It's also slower than it needs to be when the model fans out tool calls.

This module addresses that limitation with a refactor to async.

## What's slow about the sync agent

Look at Module 5's ACT phase:

```python
results = []
for c in tool_calls:
    results.append({
        "type": "tool_result",
        "tool_use_id": c.id,
        "content": dispatch(c),
    })
```

The `for` loop runs each tool call in turn. If the model emits a single `tool_use` block, that's one tool call — no problem, sequential is fine.

But the model can emit **multiple** `tool_use` blocks in a single response. *"Read `a.py` and `b.py` and `c.py`"* is one response, three tool calls. Or with several tools: *"grep for X, read file Y, run a bash command Z"* — three independent operations the model wants to do at once.

In sync code those operations run one after another. Each waits for the previous to finish, even though they don't depend on each other. For one fast file read the difference is invisible. For a `grep` across thousands of files or a `bash` command that shells out, it's the difference between *"wait once for the slowest"* and *"wait for each in turn."*

The agent loop multiplies this cost. Across many iterations of a multi-step task, the wasted waits stack up.

## The pattern: fan out, wait for all, ordered results

What we want: dispatch every requested tool concurrently, wait for all of them to finish, get an ordered list of results back. Every mainstream language has a primitive for this:

- **Python:** `asyncio.gather`
- **JavaScript:** `Promise.all`
- **Go:** goroutines + `sync.WaitGroup`
- **Rust:** `futures::join_all`

The name changes; the shape doesn't. Two properties matter:

- **Concurrency.** The runtime schedules all N operations together so their waits overlap.
- **Order preservation.** Results come back in the same order as the inputs — `outputs[i]` is the result of `tool_calls[i]` — which is what lets us pair each result back to its originating tool call.

> [!NOTE]
> Module 2 introduced async for streaming — same `async`/`await` syntax, different motivation. Async is a generic primitive: streaming and parallel dispatch are two distinct uses.

## Refactoring to async

The diff is small but each piece matters:

1. **`Anthropic` → `AsyncAnthropic`.** The async-flavored client; same API, awaitable methods.
2. **`def read` → `async def read`.** Tool functions become coroutines so the executor can `await` them. The body stays synchronous file I/O — the async-ness is about *scheduling*, not the work inside.
3. **`def dispatch` → `async def dispatch`.** Routes by name, awaits the chosen tool.
4. **Wrap the script body in `async def main()`** and start it with `asyncio.run(main())`.
5. **Replace the sync `for` loop with `await asyncio.gather(...)`.** All requested tools fan out concurrently.

## The full async code

```python
import os
import asyncio
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()

client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


# The tool
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
        # The terminal environment: read a user prompt
        user_input = input("❯ ")
        if user_input.lower() in ("/q", "exit"):
            break

        messages.append({"role": "user", "content": user_input})

        # The TAO loop: iterate until the model stops requesting tools
        while True:
            # THINK: call the model
            response = await client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=1024,
                system="You are a helpful coding assistant. Use the read tool when you need to examine file contents.",
                messages=messages,
                tools=tools,
            )
            messages.append({"role": "assistant", "content": response.content})

            # Display any text the model produced
            for block in response.content:
                if block.type == "text":
                    print(block.text)

            # If the model didn't ask for tools, we're done with this turn
            tool_calls = [b for b in response.content if b.type == "tool_use"]
            if not tool_calls:
                break

            # ACT: execute every requested tool in parallel
            outputs = await asyncio.gather(*(dispatch(c) for c in tool_calls))

            # OBSERVE: append results as the next user message
            messages.append({
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": c.id, "content": o}
                    for c, o in zip(tool_calls, outputs)
                ],
            })


asyncio.run(main())
```

## What `asyncio.gather` did

The sync version:

```python
results = []
for c in tool_calls:
    results.append({"type": "tool_result", "tool_use_id": c.id, "content": dispatch(c)})
```

The async version:

```python
outputs = await asyncio.gather(*(dispatch(c) for c in tool_calls))
messages.append({
    "role": "user",
    "content": [
        {"type": "tool_result", "tool_use_id": c.id, "content": o}
        for c, o in zip(tool_calls, outputs)
    ],
})
```

`asyncio.gather` takes the list of coroutines and runs them concurrently. The `await` returns once every result is in. `outputs` is in the same order as the input — that's why we can `zip` it with `tool_calls` to pair each result back to its originating request.

`input()` stays sync. It blocks the event loop while waiting for you to type, but there's nothing else running to block — the REPL is the whole program.

## Why this isn't streaming

Streaming (Module 2) gives the user tokens as they're generated. It only works when you can display partial output as it arrives.

The agent here can't do that. Before it can show the user any answer, it has to know whether the response includes `tool_use` blocks. If there are tool calls to dispatch, the agent isn't done — it can't print a "final answer" yet. It has to wait for the whole response, dispatch tools, send results back, and call the model again.

Streaming applies when the response is the final output. In an agent loop, intermediate responses aren't the final output — they're decisions about what to do next. So we wait for the full response and use async for parallel dispatch instead.

## Running it

```bash
uv run main.py
```

Same conversation as Module 5. The behavior is identical for any single-tool turn (one tool, no parallelism to exploit). The difference shows when the model fans out — and once you have multiple tools (Part 2), it does that often.

## What just changed

- **The agent is async.** All function definitions and the entry point use `async`/`await`.
- **Multiple tool calls run concurrently.** When the model emits two or more `tool_use` blocks in one response, they fan out via `asyncio.gather` instead of running in a sequential `for` loop.
- **Order preservation lets us pair results to requests.** `outputs[i]` corresponds to `tool_calls[i]`.
- **Conversation behavior is unchanged.** Same REPL, same TAO loop, same model interactions — the agent acts the same; it just doesn't waste wall time on independent tool calls.

This is the **end state of Part 1** — the basic-agent.

## What this didn't address

- **Only one tool.** It can read, but it can't write, edit, search, or run anything.
- **Ad-hoc dispatch.** The `dispatch(call)` function's `if call.name == "read"` branch doesn't scale past a handful of tools.
- **Errors caught in the tool.** Every new tool will repeat the same `try/except` block.
- **No memory across sessions.** The conversation resets every time you restart the REPL.

## Prompt your coding agent

If you want your coding agent to write this for you, paste:

```
Refactor main.py from the previous module to async with parallel tool dispatch.

1. Switch from `Anthropic` to `AsyncAnthropic`.
2. Make `read`, `dispatch`, and `main` async; wrap the entry point in `asyncio.run(main())`.
3. Inside the inner TAO loop, replace the sequential `for` over tool_calls with parallel dispatch:
   - `outputs = await asyncio.gather(*(dispatch(c) for c in tool_calls))`
   - Build the tool_result blocks by zipping tool_calls with outputs (tool_use_id from c, content from o).
4. `await client.messages.create(...)` on the API call.
5. `input()` stays synchronous — the REPL has nothing else to do while waiting.

Don't change the tool body or the tools schema — only the scheduling model changes.
```

The prompt tells your agent *what* to write. The module explains *why* — read it first.

---

**Next:** [Module 7: Tool design](../../../part-02/modules/07-tool-design/)
