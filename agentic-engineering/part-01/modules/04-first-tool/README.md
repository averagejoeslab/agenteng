# First tool

This module adds a single tool to the REPL agent from Module 3. With one tool in place, the TAO loop finally iterates — the model decides when to call it, your code executes it, the result flows back. The system crosses the threshold from "chatbot in a loop" to **minimal agent**.

The tool we're adding is `read`: read the contents of a file. That gives the model its first way to reach out of the LLM and into the environment — in this case, the filesystem it's running next to.

## The tool-use protocol

When the LLM has tools, it can emit `tool_use` blocks in its response. Each is a structured request:

- **`id`** — unique identifier for this specific call
- **`name`** — which tool to run
- **`input`** — the arguments (a dict matching the tool's schema)

Your code runs the tool with those arguments and feeds the result back as a `tool_result` block, matched by `tool_use_id`. That's the contract: the model asks, your code answers, the model keeps going.

```mermaid
sequenceDiagram
    participant User
    participant Agent as REPL + TAO loop
    participant LLM
    participant Tool as read

    User->>Agent: "What's in pyproject.toml?"
    Agent->>LLM: messages + tool schemas
    LLM-->>Agent: tool_use: read(path="pyproject.toml")
    Agent->>Tool: read("pyproject.toml")
    Tool-->>Agent: [file contents]
    Agent->>LLM: tool_result + history
    LLM-->>Agent: "Your pyproject.toml declares..."
    Agent->>User: display response
```

## Defining a tool

A tool is two pieces: a Python function that does the work, and a schema that tells the model how to call it.

```python
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
```

The schema is a [JSON Schema](https://json-schema.org/) dict. Two fields matter for now:

- **`properties`** — what arguments the tool takes and their types
- **`required`** — which arguments are mandatory

The tool returns a string. The `try/except` catches errors (missing file, permission denied) and returns them as strings — so the model can read the error and try again instead of crashing the loop. Part 2 covers error design more thoroughly; for now, the pattern to remember is *errors are strings the model can read*.

## Wiring it into the loop

Extend `main.py` from Module 3:

```python
import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
messages = []

# The tool
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

while True:
    # The terminal environment: read a user prompt
    user_input = input("❯ ")
    if user_input.lower() in ("/q", "exit"):
        break

    messages.append({"role": "user", "content": user_input})

    # The TAO loop: iterate until the model stops requesting tools
    while True:
        # THINK: call the model (now with tools)
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

        # ACT: execute each tool the model requested
        results = []
        for call in tool_calls:
            if call.name == "read":
                output = read(**call.input)
            else:
                output = f"error: unknown tool {call.name}"
            results.append({
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": output,
            })

        # OBSERVE: append results as the next user message
        messages.append({"role": "user", "content": results})
```

Three changes from Module 3:

1. **`tools=tools`** added to the `create()` call — gives the model the schema.
2. **ACT section** fills the stub — executes each requested tool. The `if call.name == "read"` dispatch is minimal for now; Part 2 replaces it with a proper registry.
3. **OBSERVE section** fills the stub — packages results as `tool_result` blocks with matching `tool_use_id`, then appends them as a user message so the model sees them on the next iteration.

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

The TAO loop now runs **multiple iterations per REPL turn**:

1. **THINK** — model sees the question, emits `tool_use: read(path="pyproject.toml")`
2. **ACT** — your code runs `read("pyproject.toml")` → file contents as a string
3. **OBSERVE** — result appended to messages
4. **THINK (again)** — model now has the file contents, produces summary text
5. No more tool requests → break out of the TAO loop, return to REPL

The dashed boxes in Module 3's diagram are now solid.

## What just changed

- **The TAO loop actually iterates.** Before, it ran exactly once per REPL turn (no tools to request). Now every question that requires a file read causes at least one extra iteration.
- **The model directs the flow.** Your code didn't decide to call `read` — the model did. Your code just executed what was asked for.
- **The system has autonomy over its own control flow.** Given a question it can't answer directly, the model reaches for a tool; given the file contents, it decides what to say next.
- **The agent can now see its environment.** The filesystem was always there; now the model has a way to look at it.

By the [Anthropic definition](https://www.anthropic.com/engineering/building-effective-agents) from Module 0, this is an agent. Not a chatbot (has tools), not a workflow (the model directs the sequence).

## What's next

The agent works, but it's minimal:

- **Only one tool.** It can read, but it can't write, edit, search, or run anything. A real coding agent needs a toolkit.
- **The executor is ad-hoc.** The `if call.name == "read"` dispatch doesn't scale past a handful of tools.
- **The error-return pattern is there but underspecified.** Errors come back as strings; in Part 2 we'll formalize this as the model's self-correction channel.
- **No memory across sessions.** The conversation resets every time you restart the REPL.

Part 2 (Tool Design) addresses the first three: a proper tool registry, dispatching executor, error-message design, and a multi-tool toolkit (`read`, `write`, `edit`, `bash`, `grep`, `glob`). Part 3 (Memory and Context) handles the fourth.

## Prompt your coding agent

If you want your coding agent to write this for you, paste:

```
Extend main.py from the previous module by adding a single tool called "read":

1. Define `def read(path: str) -> str` that opens the file at `path`, returns its contents, and catches any exception returning the error as a string (so the model can self-correct instead of crashing the loop)
2. Define a `tools` list with one entry:
   - name: "read"
   - description: "Read the contents of a file"
   - input_schema: JSON Schema dict with property "path" (string with a short description), required
3. Pass tools=tools to the messages.create call
4. Update the system prompt to be a helpful coding assistant that uses the read tool when it needs to examine file contents
5. Fill the ACT stub: for each tool_use block in the response, dispatch on call.name, execute the matching function with call.input, and collect results as tool_result dicts (with matching tool_use_id and content being the function's string output)
6. Fill the OBSERVE stub: append the list of tool_result dicts as a new user message so they feed back into the next iteration of the TAO loop
```

The prompt tells your agent *what* to write. The module explains *why* — read it first.

---

**Next:** Part 2 — Tool Design *(coming soon)*
