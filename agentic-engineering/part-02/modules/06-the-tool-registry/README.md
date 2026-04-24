# The tool registry

Module 4's agent has an `if call.name == "read"` dispatch inside an ad-hoc `dispatch(call)` function. It worked for one tool. It won't scale:

```python
# This doesn't scale:
async def dispatch(call):
    if call.name == "read":
        return await read(**call.input)
    elif call.name == "write":
        return await write(**call.input)
    elif call.name == "grep":
        return await grep(**call.input)
    # ...
    return f"error: unknown tool {call.name}"
```

Every new tool adds an `elif` branch AND a separate schema dict at the top of the file. Two places to keep in sync — easy to forget one.

This module replaces that with a **tool registry**: one data structure that stores each tool's function and metadata together, plus a **factory** that derives the API-shaped schemas from the registry.

## The registry

A tool registry is a dict mapping tool name to metadata:

```python
TOOLS = {
    "read": {
        "fn": read,
        "description": "Read the contents of a file",
        "params": {"path": "Path to the file to read"},
    },
    # more tools here
}
```

Three fields per tool — matching the components from [Module 5](../05-tool-design/):

- `fn` — the async function that does the work
- `description` — what the model reads to pick the tool
- `params` — a dict mapping each parameter name to a short description

`params` is a dict, not a list, because Module 5's rule *"put a description on each property"* needs somewhere to put them. The key is the parameter name; the value is the text the model will read when deciding how to call the tool.

One structure, one source of truth. Adding a tool means adding one entry.

## The schema factory

The Anthropic API expects schemas in a specific JSON Schema shape. Instead of hand-writing them, derive them from the registry:

```python
def build_tool_schemas(tools):
    schemas = []
    for name, meta in tools.items():
        properties = {
            p: {"type": "string", "description": desc}
            for p, desc in meta["params"].items()
        }
        schemas.append({
            "name": name,
            "description": meta["description"],
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": list(meta["params"]),
            },
        })
    return schemas
```

Every parameter is a `string` for now, and every parameter is required. That's enough for the tools Module 7 adds. When a tool needs richer types (numbers, booleans) or optional params, extend the registry entry with a type per parameter or a separate `optional` list — the factory is the only place that needs to change.

Call this once at startup and pass the result to `client.messages.create(tools=...)`.

## Dispatching by name

A small async function looks up a tool in the registry and awaits it:

```python
async def execute_tool(name: str, input: dict) -> str:
    tool = TOOLS.get(name)
    if tool is None:
        return f"error: unknown tool {name}"
    return await tool["fn"](**input)
```

Two things this does:

- Handles unknown tool names (returns an error string).
- Unpacks `input` as kwargs and awaits the tool's function.

What it *doesn't* do: catch exceptions from the tool itself. Each tool handles its own errors with `try/except` (as `read` already does from Module 4). Module 8 will centralize that — the executor becomes the single place that wraps every call.

## Refactoring main.py

Here's the full refactored agent — still just `read` (toolkit arrives in Module 7):

```python
import os
import asyncio
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()

client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


# --- Tools ---

async def read(path: str) -> str:
    try:
        with open(path, "r") as f:
            return f.read()
    except Exception as e:
        return f"error: {e}"


TOOLS = {
    "read": {
        "fn": read,
        "description": "Read the contents of a file",
        "params": {"path": "Path to the file to read"},
    },
}


def build_tool_schemas(tools):
    schemas = []
    for name, meta in tools.items():
        properties = {
            p: {"type": "string", "description": desc}
            for p, desc in meta["params"].items()
        }
        schemas.append({
            "name": name,
            "description": meta["description"],
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": list(meta["params"]),
            },
        })
    return schemas


async def execute_tool(name: str, input: dict) -> str:
    tool = TOOLS.get(name)
    if tool is None:
        return f"error: unknown tool {name}"
    return await tool["fn"](**input)


TOOL_SCHEMAS = build_tool_schemas(TOOLS)


# --- The loop ---

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
                tools=TOOL_SCHEMAS,
            )
            messages.append({"role": "assistant", "content": response.content})

            for block in response.content:
                if block.type == "text":
                    print(block.text)

            tool_calls = [b for b in response.content if b.type == "tool_use"]
            if not tool_calls:
                break

            outputs = await asyncio.gather(
                *(execute_tool(c.name, c.input) for c in tool_calls)
            )

            messages.append({
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": c.id, "content": o}
                    for c, o in zip(tool_calls, outputs)
                ],
            })


asyncio.run(main())
```

Three changes from Module 4:

1. The hand-written `tools` list literal is gone. Replaced by the `TOOLS` dict + `build_tool_schemas()`.
2. The inline `dispatch(call)` function with its `if call.name == "read"` branch is gone. Replaced by `execute_tool(call.name, call.input)` — same role, but driven by the registry instead of hand-written branches.
3. `tools=TOOL_SCHEMAS` in the API call (computed once at startup).

Error handling still lives in `read` itself — unchanged from Module 4. That stays that way through Module 7.

## Running it

```bash
uv run main.py
```

Same behavior as Module 4. The refactor doesn't add features — it *prepares* for them. Module 7 plugs in five more tools.

## Prompt your coding agent

If you want your coding agent to write this for you, paste:

```
Refactor main.py from the previous module to use a tool registry pattern:

1. Define a TOOLS dict mapping tool name to {fn, description, params}. For now it has one entry for "read" with params={"path": "Path to the file to read"}. The fn is an async function. params is a dict so each parameter can carry a description the model will read.
2. Write build_tool_schemas(TOOLS) that generates the JSON Schema list the Anthropic API expects. All parameters are string type with the description from params; all are required.
3. Write `async def execute_tool(name, input)` that looks up the tool and awaits its fn with unpacked input. If the name isn't in TOOLS, return an error string. Do NOT wrap the call in try/except — the tool handles its own errors for now.
4. Replace the ad-hoc dispatch function in the TAO loop with a call to execute_tool, still using asyncio.gather for parallel dispatch.
5. Compute TOOL_SCHEMAS = build_tool_schemas(TOOLS) once at startup and pass it as the tools parameter to messages.create.
```

The prompt tells your agent *what* to write. The module explains *why* — read it first.

---

**Next:** [Module 7: Building the toolkit](../07-building-the-toolkit/)
