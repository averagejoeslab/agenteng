# The tool registry

Module 4's agent has an `if call.name == "read"` dispatch. It worked for one tool. It won't scale:

```python
# This doesn't scale:
if call.name == "read":
    output = read(**call.input)
elif call.name == "write":
    output = write(**call.input)
elif call.name == "grep":
    output = grep(**call.input)
# ...
else:
    output = f"error: unknown tool {call.name}"
```

Every new tool adds an `elif` branch AND a separate schema dict at the top of the file. Two places to keep in sync — easy to forget one.

This module replaces that with a **tool registry**: one data structure that defines each tool's function and schema together, with automatic dispatch.

## The pattern

A tool registry is a dict mapping tool name to metadata:

```python
TOOLS = {
    "read": {
        "fn": read,
        "description": "Read the contents of a file",
        "params": ["path"],
    },
    # more tools here
}
```

Three fields per tool:

- `fn` — the Python function to call
- `description` — what the model reads
- `params` — list of parameter names

From this one source of truth, we can auto-generate schemas, dispatch calls by name, and list available tools.

## Auto-generating schemas

Instead of hand-writing `input_schema` dicts, generate them from the `params` list:

```python
def build_tool_schemas(tools):
    schemas = []
    for name, meta in tools.items():
        properties = {p: {"type": "string"} for p in meta["params"]}
        schemas.append({
            "name": name,
            "description": meta["description"],
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": meta["params"],
            },
        })
    return schemas
```

Every parameter is a `string` for now. Every parameter is required. Good enough for this module — we'll handle richer types and optionals in Module 7 where the tools need them.

Call this once at startup and pass the result to `client.messages.create(tools=...)`.

## The dispatcher

One function executes any tool by name:

```python
def execute_tool(name: str, input: dict) -> str:
    tool = TOOLS.get(name)
    if tool is None:
        return f"error: unknown tool {name}"
    try:
        return tool["fn"](**input)
    except Exception as e:
        return f"error: {e}"
```

Three things it handles:

1. **Unknown tool names** — returns an error string instead of crashing.
2. **Tool execution** — looks up the function, unpacks `input` as kwargs.
3. **Exceptions** — if the tool raises (e.g., wrong argument types from a model hallucination), the error comes back as a string.

The `try/except` here is a safety net. Individual tools still catch their own errors (like `read` does with file I/O). The dispatcher's `try/except` catches anything tools miss.

## Refactoring main.py

Here's the full refactored agent — still just `read` for now (toolkit arrives in Module 7):

```python
import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
messages = []


# --- Tools ---

def read(path: str) -> str:
    try:
        with open(path, "r") as f:
            return f.read()
    except Exception as e:
        return f"error: {e}"


TOOLS = {
    "read": {
        "fn": read,
        "description": "Read the contents of a file",
        "params": ["path"],
    },
}


def build_tool_schemas(tools):
    schemas = []
    for name, meta in tools.items():
        properties = {p: {"type": "string"} for p in meta["params"]}
        schemas.append({
            "name": name,
            "description": meta["description"],
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": meta["params"],
            },
        })
    return schemas


def execute_tool(name: str, input: dict) -> str:
    tool = TOOLS.get(name)
    if tool is None:
        return f"error: unknown tool {name}"
    try:
        return tool["fn"](**input)
    except Exception as e:
        return f"error: {e}"


TOOL_SCHEMAS = build_tool_schemas(TOOLS)


# --- The loop ---

while True:
    user_input = input("❯ ")
    if user_input.lower() in ("/q", "exit"):
        break

    messages.append({"role": "user", "content": user_input})

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            system="You are a helpful coding assistant.",
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

        results = []
        for call in tool_calls:
            output = execute_tool(call.name, call.input)
            results.append({
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": output,
            })

        messages.append({"role": "user", "content": results})
```

Changes from Module 4:

1. The `tools` list literal is gone. Replaced by `TOOLS` dict + `build_tool_schemas()`.
2. The `if call.name == "read"` dispatch is gone. Replaced by `execute_tool(call.name, call.input)`.
3. `tools=TOOL_SCHEMAS` in the API call (computed once).
4. System prompt simplified — no need to mention specific tools; the model sees them from the schemas.

## Running it

```bash
uv run main.py
```

Same behavior as Module 4. The refactor doesn't add features — it *prepares* for them. Module 7 plugs in the other five tools.

## Prompt your coding agent

If you want your coding agent to write this for you, paste:

```
Refactor main.py from the previous module to use a tool registry pattern:

1. Define a TOOLS dict mapping tool name to {fn, description, params}. For now it has one entry for "read" with params=["path"].
2. Write build_tool_schemas(TOOLS) that generates the JSON Schema list the Anthropic API expects. All parameters are string type; all are required.
3. Write execute_tool(name, input) that looks up the tool in TOOLS, unpacks input as kwargs, and returns the result — or returns an error string if the tool is unknown or raises.
4. Replace the ad-hoc if/elif dispatch in the TAO loop with a call to execute_tool.
5. Compute TOOL_SCHEMAS = build_tool_schemas(TOOLS) once and pass it as the tools parameter to messages.create.
```

The prompt tells your agent *what* to write. The module explains *why* — read it first.

---

**Next:** [Module 7: Building the toolkit](../07-building-the-toolkit/)
