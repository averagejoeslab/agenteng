# The TAO loop

Module 4 built a one-shot workflow — two predetermined LLM calls with tool execution between them. This module wraps that workflow in a loop and brings back the REPL from Module 3 so the user can have a conversation. The shift turns the workflow into an **agent**: the model decides when to keep calling tools and when to stop.

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

The agent runs inside the REPL from Module 3 — outer loop reads user input; inner TAO loop iterates until the model is done.

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

Wrap Module 4's two-call sequence in a `while True` that exits when no `tool_use` blocks come back, then wrap that in the outer REPL loop:

```python
import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


# The tool (unchanged from Module 4)
def read(path: str) -> str:
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


def dispatch(call):
    if call.name == "read":
        return read(**call.input)
    return f"error: unknown tool {call.name}"


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
        response = client.messages.create(
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

        # ACT: execute each requested tool
        results = []
        for c in tool_calls:
            results.append({
                "type": "tool_result",
                "tool_use_id": c.id,
                "content": dispatch(c),
            })

        # OBSERVE: append results as the next user message
        messages.append({"role": "user", "content": results})
```

Three changes from Module 4:

1. **The two `messages.create` calls became one inside `while True`.** The same call runs every iteration; the inner loop stops when no `tool_use` blocks come back. The number of calls is now whatever the model needs.
2. **The outer REPL `while True` is back** (from Module 3). Reads from stdin, breaks on `/q` or `exit`. `messages` lives outside both loops so the conversation persists across user turns.
3. **A `dispatch(call)` function** picks the tool by name and calls it. With one tool the branching is trivial.

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
2. **ACT** — `dispatch` runs the call; `read("pyproject.toml")` returns the file contents
3. **OBSERVE** — result appended to messages
4. **THINK (again)** — model has the file contents, produces summary text
5. No more tool requests → break out of the TAO loop, return to REPL

For simple questions the loop runs once (no tool needed). For multi-step questions ("does X import Y?") the loop iterates until the model is done.

## Why this is now an agent

By the [Anthropic definition](https://www.anthropic.com/engineering/building-effective-agents) the README started with: *"agents are systems where LLMs dynamically direct their own path through the control flow."*

In Module 4, the control flow was your code's two-call sequence. Here, the model's `tool_use` decisions drive the loop — keep going by emitting more tool calls, stop by emitting just text. **The model controls how many iterations happen and what each iteration does.** That's autonomy over control flow.

Not a chatbot (has tools), not a workflow (the model directs the sequence). This is an agent.

## What just changed

- **The TAO loop iterates.** Module 4 ran tool execution exactly once. Now it runs as many times as the model requests.
- **The model directs the flow.** Your code didn't decide to call `read` twice, or in what order — the model did. Your code just executed what was asked for.
- **Conversation persists.** `messages` lives outside the REPL loop so the model remembers earlier turns.

## What this didn't address

- **Sequential tool dispatch.** When the model emits multiple `tool_use` blocks in one response, the `for` loop runs them one at a time. They're independent — they don't depend on each other — but each waits for the previous to finish.
- **Only one tool.** `read` works, but a real coding agent needs to write, edit, search, and run commands.
- **Ad-hoc dispatch.** The `dispatch(call)` function's `if call.name == "read"` branch doesn't scale past a handful of tools.
- **Errors caught in the tool.** Every new tool will repeat the same `try/except` pattern.
- **No memory across sessions.** The conversation resets every time you restart the REPL.

## Prompt your coding agent

If you want your coding agent to write this for you, paste:

```
Extend main.py from the previous module to wrap the two-call workflow in a TAO loop and restore the REPL from before.

1. Replace the hardcoded user message and fixed two messages.create calls with two nested while True loops:
   - Outer loop (REPL / terminal environment): read user input with input("❯ "), break if "/q" or "exit", otherwise append as a user message.
   - Inner loop (TAO loop): client.messages.create(...) with messages and tools; append the response to messages; print any text blocks; break if there are no tool_use blocks; otherwise execute every tool with a for loop appending tool_result blocks; continue.

2. Factor tool execution into def dispatch(call) that picks the tool by name and calls it, returning "error: unknown tool {name}" for unknown names.

3. The messages list should live outside both loops so the conversation persists across user turns.

4. Don't change the read function or the tools schema — they carry over from Module 4.
```

The prompt tells your agent *what* to write. The module explains *why* — read it first.

---

**Next:** [Module 6: Async and parallel tool dispatch](../06-async-and-parallel-dispatch/)
