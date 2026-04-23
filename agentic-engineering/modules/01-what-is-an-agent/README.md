# What is an agent?

An agent is an LLM within a loop where it can think, act, and observe within an environment. This module breaks that down into basic components and shows what each looks like; the next three modules build them.

## Basic components of an agent

An agent has three moving parts:

1. **An LLM call** — the reasoning engine
2. **A TAO loop** (Think, Act, Observe) — the structure that turns single calls into sustained work
3. **Tools** — the agent's means of acting on its environment

## Show an LLM call

An LLM call is an HTTP POST to the model provider's API. The response comes back as a list of content blocks — text, and optionally tool requests.

```python
response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    messages=[{"role": "user", "content": "What is 2 + 2?"}],
)
print(response.content[0].text)
```

One prompt in, one response out. Module 2 builds this from scratch.

## Show a TAO loop

Each iteration has three phases: **Think, Act, Observe**.

1. **THINK** — the LLM runs; it emits reasoning text and (optionally) tool requests
2. **ACT** — your code executes the tools the model requested
3. **OBSERVE** — the results are appended to the conversation

The cycle repeats: Think → Act → Observe → Think → ... until the model produces no more tool requests. That's the end of the turn.

```python
while True:
    # THINK: call the model
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        messages=messages,
        tools=tools,
    )
    messages.append({"role": "assistant", "content": response.content})

    # If no tool_use blocks, the model is done
    tool_calls = [b for b in response.content if b.type == "tool_use"]
    if not tool_calls:
        break

    # ACT: run each tool the model requested
    results = [execute(call) for call in tool_calls]

    # OBSERVE: append results as the next user message
    messages.append({"role": "user", "content": results})
```

Module 3 wraps this loop around an LLM call inside a terminal REPL environment.

> [!NOTE]
> This loop is commonly known as the **ReAct loop** — after the 2022 paper [*ReAct: Synergizing Reasoning and Acting in Language Models*](https://arxiv.org/abs/2210.03629) by Yao et al. The ReAct acronym drops observation; TAO keeps it visible. (The paper itself includes observation — it's the acronym that's lossy.)

## Show a tool

A tool is a Python function plus a JSON schema describing its inputs. The schema tells the model how to call it.

```python
def add(a: int, b: int) -> str:
    return str(a + b)

tools = [
    {
        "name": "add",
        "description": "Add two numbers",
        "input_schema": {
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["a", "b"],
        },
    }
]
```

The tool returns a string — numbers, JSON, free text, whatever the model needs to read. Module 4 wires this into the loop so the model can request it.

## Putting it together

All three components assembled into a minimal agent:

```python
import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# A minimal tool
def add(a: int, b: int) -> str:
    return str(a + b)

tools = [
    {
        "name": "add",
        "description": "Add two numbers",
        "input_schema": {
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["a", "b"],
        },
    }
]

messages = [{"role": "user", "content": "What is 2 + 2?"}]

while True:
    # THINK: the LLM runs; it emits text + optional tool requests
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system="You are a helpful assistant. Use the add tool when you need to add two numbers.",
        messages=messages,
        tools=tools,
    )
    messages.append({"role": "assistant", "content": response.content})

    # No tool requests → the model is done
    tool_calls = [b for b in response.content if b.type == "tool_use"]
    if not tool_calls:
        break

    # ACT: execute the tools the model requested
    results = []
    for call in tool_calls:
        output = add(**call.input)
        results.append({
            "type": "tool_result",
            "tool_use_id": call.id,
            "content": output,
        })

    # OBSERVE: append the results to the conversation
    messages.append({"role": "user", "content": results})

# Print the final text from the model
for block in response.content:
    if block.type == "text":
        print(block.text)
```

Setup (API key, `uv`, dependencies) comes in [Module 2](../02-a-single-llm-call/); the pieces — LLM call, loop, environment, tools — are built up one at a time across Modules 2–4.

```mermaid
flowchart LR
    Start[User input] --> Think[THINK<br/>LLM call]
    Think --> Branch{Tool call?}
    Branch -->|yes| Act[ACT<br/>Execute tool]
    Act --> Observe[OBSERVE<br/>Result into context]
    Observe --> Think
    Branch -->|no| End[Response to user]
```

A concrete trace:

```
User: "Find and summarize the TODOs in this codebase"

[THINK]    I'll search for TODO comments
[ACT]      grep("TODO", ".")
[OBSERVE]  src/auth.ts:42:  // TODO: session expiration
           src/auth.ts:87:  // TODO: rate limiting
           src/db.ts:14:    // TODO: connection pooling
           [...44 more matches]
[THINK]    Most are in src/auth.ts — I'll read that file for context
[ACT]      read("src/auth.ts")
[OBSERVE]  [full file contents]
[THINK]    I have enough to summarize
[STOP]     "You have 47 TODOs across 12 files, concentrated in auth..."
```

The model chose every action, read every result, and decided when to stop.

## What we'll build

The next three modules add one piece at a time:

| Module | Added | What it becomes |
|---|---|---|
| 2 | LLM call | A one-shot script |
| 3 | TAO loop + terminal environment | An interactive REPL running the loop |
| 4 | First tool | **A minimal agent** |

By Module 4 you'll have a minimal working coding agent in Python. Each module ends with something that runs.

## What you'll need

- [Python 3.13 or newer](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/) for dependency management
- An Anthropic API key from [console.anthropic.com](https://console.anthropic.com)

---

**Next:** [Module 2: A single LLM call](../02-a-single-llm-call/)
