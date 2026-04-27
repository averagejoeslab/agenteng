# The TAO loop

Module 3 built a one-shot workflow — two predetermined LLM calls with tool execution between them. This module wraps that workflow in a loop and adds a terminal REPL so the user can have a conversation. The shift turns the workflow into an **agent**: the model decides when to keep calling tools and when to stop.

## From workflow to agent

The single change that matters: instead of your code deciding *"call the model exactly twice,"* your code says *"keep calling the model until it stops asking for tools."* The stop condition moves from your code (a fixed count) to the model (its own decision based on what it observes).

Per the [taxonomy](../../../../README.md#types-of-agentic-systems), that's the workflow → agent transition. The model now directs the flow.

## The TAO loop's shape

Each iteration of the loop has three phases:

1. **THINK** — the LLM runs; it emits text and (optionally) tool requests
2. **ACT** — your code executes the tools the model requested
3. **OBSERVE** — the results are appended to the conversation

The loop repeats until the model emits no `tool_use` blocks. A single user prompt can trigger many LLM calls; the model decides how many.

> [!NOTE]
> This loop is commonly known as the **ReAct loop** — after the 2022 paper [*ReAct: Synergizing Reasoning and Acting in Language Models*](https://arxiv.org/abs/2210.03629) by Yao et al. The ReAct acronym drops observation; TAO keeps it visible. (The paper itself includes observation — it's the acronym that's lossy.)

## The environment

An agent doesn't run in a vacuum — it needs somewhere to read input, produce output, and act. The simplest environment is a **terminal REPL**: read a prompt, run the TAO loop, show the response, repeat. The REPL is the outer loop; the TAO loop is the inner one.

```mermaid
flowchart TB
    Start([Start]) --> Read[Read user input]
    Read --> Quit{/q or exit?}
    Quit -->|yes| End([Quit])
    Quit -->|no| Think[THINK<br/>LLM call]
    Think --> Branch{Tool call?}
    Branch -->|yes| Act[ACT<br/>Execute tool]
    Act --> Observe[OBSERVE<br/>Result into context]
    Observe --> Think
    Branch -->|no| Print[Display response]
    Print --> Read
```

## The code

Wrap Module 3's two-call sequence in a `while True` that exits when no `tool_use` blocks come back, then wrap that in an outer REPL loop:

```python
import os
import asyncio
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()

client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


# The tool (unchanged from Module 3)
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

Three changes from Module 3:

1. **The two `messages.create` calls became one inside `while True`.** The same call runs every iteration; the inner loop stops when no `tool_use` blocks come back. The number of calls is now whatever the model needs.
2. **An outer REPL `while True`.** Reads from stdin, breaks on `/q` or `exit`. `messages` lives outside both loops so the conversation persists across user turns.
3. **A `dispatch(call)` function** picks the tool by name and awaits it. With one tool the branching is trivial — Part 2 replaces it with a registry once we have several tools.

`input()` stays sync. It blocks the event loop while waiting for you to type, but there's nothing else running to block — the REPL *is* the whole program. Trading it for an async input library would add complexity without buying anything.

## Running it

```bash
uv run main.py
```

A session (run it from your project directory so the relative paths work):

```
❯ What's in pyproject.toml?
I'll check the file.
Your pyproject.toml declares a project named "agent" with Python 3.13+ and anthropic and python-dotenv as dependencies.
❯ Does main.py import python-dotenv?
Let me look.
Yes — main.py imports load_dotenv from dotenv and calls it before creating the Anthropic client.
❯ /q
```

(Exact phrasing varies — models are non-deterministic.)

The TAO loop now runs **multiple iterations per user turn** when the task needs it:

1. **THINK** — model sees the question, emits `tool_use: read(path="pyproject.toml")`
2. **ACT** — `asyncio.gather` dispatches the call; `read("pyproject.toml")` returns the file contents
3. **OBSERVE** — result appended to messages
4. **THINK (again)** — model has the file contents, produces summary text
5. No more tool requests → break out of the TAO loop, return to REPL

For simple questions the loop runs once (no tool needed). For multi-step questions ("does X import Y?") the loop iterates until the model is done.

## Why this is now an agent

By the [Anthropic definition](https://www.anthropic.com/engineering/building-effective-agents) the README started with: *"agents are systems where LLMs dynamically direct their own path through the control flow."*

In Module 3, the control flow was your code's two-call sequence. In Module 4, the model's `tool_use` decisions drive the loop — keep going by emitting more tool calls, stop by emitting just text. **The model controls how many iterations happen and what each iteration does.** That's autonomy over control flow.

Not a chatbot (has tools), not a workflow (the model directs the sequence). This is an agent.

## What just changed

- **The TAO loop iterates.** Module 3 ran tool execution exactly once. Now it runs as many times as the model requests.
- **The model directs the flow.** Your code didn't decide to call `read` twice, or in what order — the model did. Your code just executed what was asked for.
- **Conversation persists.** `messages` lives outside the REPL loop so the model remembers earlier turns.
- **Parallel tool calls are still free.** If the model asks for two reads at once, both run concurrently — same as Module 3.

## What's next

The agent works, but it's minimal:

- **Only one tool.** It can read, but it can't write, edit, search, or run anything. A real coding agent needs a toolkit.
- **The dispatch is ad-hoc.** The `dispatch(call)` function's `if call.name == "read"` branch doesn't scale past a handful of tools.
- **The error-return pattern is there but underspecified.** Errors come back as strings; in Part 2 we'll formalize this as the model's self-correction channel and pull the `try/except` out of every tool into a single executor.
- **No memory across sessions.** The conversation resets every time you restart the REPL.

Part 2 (Tool Design) addresses the first three: a proper tool registry, dispatching executor, error-message design, and a multi-tool toolkit (`read`, `write`, `edit`, `bash`, `grep`, `glob`). Part 3 (Memory and Context) handles the fourth.

## Prompt your coding agent

If you want your coding agent to write this for you, paste:

```
Extend main.py from the previous module to wrap the two-call workflow in a TAO loop and a terminal REPL.

1. Replace the hardcoded user message and fixed two `messages.create` calls with two nested `while True` loops inside `async def main()`:
   - Outer loop (REPL / terminal environment): read user input with `input("❯ ")`, break if "/q" or "exit", otherwise append as a user message.
   - Inner loop (TAO loop): await client.messages.create(...) with messages and tools; append the response to messages; print any text blocks; break if there are no tool_use blocks; otherwise execute every tool with `outputs = await asyncio.gather(*(dispatch(c) for c in tool_calls))`, append tool_result blocks as a user message, continue.
2. Factor tool execution into `async def dispatch(call)` that picks the tool by name and awaits it, returning "error: unknown tool {name}" for unknown names. With one tool today it just routes to read; Part 2 replaces this with a registry.
3. The messages list should live inside main() but outside both loops so the conversation persists across user turns.
4. Do not change the read function or the tools schema — they carry over from Module 3.
```

The prompt tells your agent *what* to write. The module explains *why* — read it first.

---

**Next:** [Module 5: Tool design](../../../part-02/modules/05-tool-design/)
