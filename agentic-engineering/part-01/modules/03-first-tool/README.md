# First tool

This module gives the LLM its first tool — but not yet a loop. What you'll build is a **one-shot workflow**: the model sees a question, requests a single round of tool calls, your code executes them, and the model produces a final response. Two predetermined LLM calls with tool execution between them.

That shape — fixed sequence of LLM calls and code steps — is a workflow per the [taxonomy](../../../../README.md#types-of-agentic-systems) at the top of the repo. The point of building it here is to make the **tool-use protocol** concrete in code, separate from any loop that would wrap it.

## The tool-use protocol

When an LLM has tools available, it can emit `tool_use` blocks in its response. Each is a structured request:

- **`id`** — unique identifier for this specific call
- **`name`** — which tool to run
- **`input`** — the arguments (a dict matching the tool's schema)

Your code runs the tool with those arguments and feeds the result back as a `tool_result` block, matched by `tool_use_id`. The model then produces its next message.

A single response can contain **multiple** `tool_use` blocks. The model can ask to read two files at once, or run three independent commands. They're independent — no reason to run them sequentially.

```mermaid
sequenceDiagram
    participant User
    participant Code as Your code
    participant LLM
    participant Tool as read

    User->>Code: "What's in pyproject.toml?"
    Code->>LLM: messages + tool schemas
    LLM-->>Code: tool_use: read(path="pyproject.toml")
    Code->>Tool: read("pyproject.toml")
    Tool-->>Code: [file contents]
    Code->>LLM: tool_result + history
    LLM-->>Code: "Your pyproject.toml declares..."
    Code->>User: display response
```

## Defining a tool

A tool is two pieces, same as Module 1: an **implementation** and a **schema**. The implementation is a function in whatever language you're using; the schema is JSON Schema (LLM industry standard). Both sides in Python:

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

The tool returns a string. The `try/except` catches errors (missing file, permission denied) and returns them as strings — so the model can read the error and try again instead of crashing the program. The pattern to remember is *errors are strings the model can read*.

## The two-call workflow

Here's the full code. It's a fixed two-call sequence — first call to receive tool requests, second call (after executing them) to receive the final text. The user's question is hardcoded.

```python
import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


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


messages = [{"role": "user", "content": "What's in pyproject.toml?"}]

# First call: model sees the tools and may emit tool_use blocks
response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    system="You are a helpful coding assistant. Use the read tool when you need to examine file contents.",
    messages=messages,
    tools=tools,
)
messages.append({"role": "assistant", "content": response.content})

# Execute every requested tool
tool_calls = [b for b in response.content if b.type == "tool_use"]
if tool_calls:
    results = []
    for c in tool_calls:
        results.append({
            "type": "tool_result",
            "tool_use_id": c.id,
            "content": read(**c.input),
        })
    messages.append({"role": "user", "content": results})

    # Second call: model has tool results and produces final text
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system="You are a helpful coding assistant. Use the read tool when you need to examine file contents.",
        messages=messages,
        tools=tools,
    )

# Print the final text
for block in response.content:
    if block.type == "text":
        print(block.text)
```

Three things to notice:

1. **Two `messages.create` calls in fixed order.** Your code decides when each call happens. The model isn't choosing whether to keep going.
2. **Tool execution lives between the two calls.** Your code runs the tools and stitches their results into the message history.
3. **Each `tool_use` block is executed in turn.** The `for` loop runs them sequentially and collects the `tool_result` blocks for the second call.

## Running it

```bash
uv run main.py
```

A run (from your project directory so the relative path works):

```
Your pyproject.toml declares a project named "agent" with Python 3.13+ and anthropic and python-dotenv as dependencies.
```

(Exact phrasing varies — models are non-deterministic.)

## Why this is a workflow, not an agent

Look back at the code. Your code is in charge of the sequence: call the model, run tools, call the model again, print. The whole shape is fixed in advance — the model fills in text and tool requests at each stop, but it doesn't direct the flow.

That's a workflow per the [taxonomy](../../../../README.md#types-of-agentic-systems) — predetermined code paths. The model is on rails.

What if the model's first response asks to read three files, and after seeing them it decides it needs a fourth? In this code, that fourth read can never happen — the second `messages.create` call is the last thing your code does. The model can't change its mind.

## What's missing

- **No iteration.** One round of tool use, then done. The model can't react to what it sees by calling more tools.
- **No conversation.** The user's prompt is hardcoded. No interactive REPL.
- **The agent's autonomy.** Your code decides when to stop, not the model.

## Prompt your coding agent

If you want your coding agent to write this for you, paste:

```
Extend main.py from the previous module by adding a single tool called "read" and the tool-use protocol — but no loop yet, just one round of tool calls.

1. Define `def read(path: str) -> str` that opens the file at `path`, returns its contents, and catches any exception returning the error as a string.
2. Define a `tools` list with one entry:
   - name: "read"
   - description: "Read the contents of a file"
   - input_schema: JSON Schema dict with property "path" (string with a short description), required
3. Use a hardcoded user message (e.g., "What's in pyproject.toml?"). Make the first messages.create call with tools=tools.
4. Append the assistant's response to messages, then collect tool_use blocks. If any:
   - Run each tool in turn with a `for` loop, collecting tool_result blocks (matching tool_use_id, content=read(**c.input)).
   - Append the tool_result blocks as a single user message.
   - Make a second messages.create call (still with tools=tools) so the model can produce its final text.
5. Print any text blocks from the final response.

Do NOT add a while True loop or a REPL.
```

The prompt tells your agent *what* to write. The module explains *why* — read it first.

---

**Next:** [Module 4: The TAO loop](../04-the-tao-loop/)
