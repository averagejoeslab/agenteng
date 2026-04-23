# Tool design

In Module 4 you added one tool with an ad-hoc `if call.name == "read"` dispatch. That pattern doesn't scale past a handful of tools. Before adding more, we need principles — what makes a tool *good*, what makes a tool *bad*, what dispatchers should look like.

This module is conceptual. Module 6 applies these principles in a refactor; Module 7 uses them to build a real toolkit.

## Granularity

How do you decide what goes in one tool vs several?

**Extreme 1: one `bash` tool.** The LLM can do anything the shell can do. Maximum flexibility, minimum specification.

**Extreme 2: many focused tools.** Separate tools for `read`, `write`, `edit`, `grep`, `glob`, `ls`, etc. Each tool does one thing with a clear contract.

The tradeoff:

| Fewer coarse tools | More focused tools |
|---|---|
| Flexibility | Clarity |
| Model does shell-craft to get commands right | Model picks the tool for the task |
| Hard to constrain (any shell command is allowed) | Easy to constrain (sandbox per tool) |
| Harder to observe and evaluate | Clear failure modes |

A coding agent typically uses both: many focused tools for common operations (`read`, `write`, `edit`, `grep`, `glob`), plus one `bash` tool for the long tail. The focused tools cover ~95% of cases cleanly; `bash` handles the rest at a cost (safety, observability).

Think of it as factoring: focused tools = well-factored. One `bash` tool alone = an unfactored god-function.

## Errors as self-correction

When a tool fails, what does the model see?

The wrong pattern:

```python
def read(path: str) -> str:
    with open(path) as f:
        return f.read()   # raises FileNotFoundError if file is missing
```

If the file doesn't exist, Python raises an exception. Either your dispatcher catches it — or worse, the whole loop crashes.

The right pattern:

```python
def read(path: str) -> str:
    try:
        with open(path) as f:
            return f.read()
    except Exception as e:
        return f"error: {e}"
```

The function never raises. Errors come back as strings the model can read. It sees `"error: [Errno 2] No such file or directory: 'foo.txt'"` and tries `foo.md` or asks for a directory listing.

**The error message is a self-correction channel.** The model reads it and adjusts. This only works if:

1. Tools don't raise — they return errors as strings.
2. Error messages are informative — they name the specific failure.
3. The dispatcher catches anything that slips through.

This is why Module 4's `read` function already uses `try/except`. It's not defensive coding — it's communication.

## Descriptions: what the model reads

The `description` field in a tool schema isn't optional. The model reads it when deciding which tool to use.

Good descriptions:

- State the one thing the tool does
- Mention non-obvious constraints (e.g., "only reads UTF-8 files")
- Use verbs a user might say ("search", not "pattern-match")

Bad descriptions:

- Vague: *"Does stuff with files"*
- Overloaded: *"Read, search, or list files"* — should be three tools
- Missing: empty string

A good rule: write the description so that if you took away the tool name and function signature, the description alone would be enough for the model to know when to use it.

## Schema design

The `input_schema` is a JSON Schema dict. Two properties to get right:

**`properties`** — each argument's type and description. The `description` for each property matters too — the model reads it.

```python
"properties": {
    "path": {"type": "string", "description": "Relative path to the file"},
    "offset": {"type": "integer", "description": "Line to start at (0-indexed)"},
    "limit": {"type": "integer", "description": "Maximum lines to return"},
}
```

**`required`** — which arguments the model *must* provide. Keep this minimal. If a parameter has a sensible default, make it optional.

```python
"required": ["path"]   # offset and limit are optional
```

Pitfall: too many required fields mean the model has to guess values for things like `offset=0` when it doesn't care. Let it omit them; use defaults in your function.

## Naming

Pick tool names the model will understand. The model knows common command-line names — `read`, `write`, `grep`, `bash` — better than invented names.

- Good: `read`, `write`, `edit`, `bash`, `grep`, `glob`
- Avoid: `fileReader`, `textWriter`, `contentSearcher`

Short, canonical names let the model map user requests ("search for TODOs") to tools directly.

## MCP — a standardization effort

As agents proliferate, the same tools get reimplemented across codebases. [Model Context Protocol (MCP)](https://modelcontextprotocol.io) is an emerging standard for exposing tools to agents — a protocol for tool interoperability.

Module 8 covers MCP in depth. For now: if you design tools well by the principles above, moving them into an MCP server later is straightforward — the shape is the same.

## The tools we'll build

Module 7 builds six tools following these principles:

| Tool | Purpose |
|---|---|
| `read` | Read file contents (already exists from Module 4) |
| `write` | Create or overwrite a file |
| `edit` | Find-and-replace in a file |
| `grep` | Search file contents for a regex |
| `glob` | Find files by pattern |
| `bash` | Run a shell command |

Six tools cover most of what a coding agent does: examine files, change files, find things, run things. Module 6 first refactors the dispatcher so adding them is clean; Module 7 writes them.

---

**Next:** [Module 6: The tool registry](../06-the-tool-registry/)
