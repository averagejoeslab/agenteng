# Tool design

By the end of Part 1 you had one tool and an ad-hoc `if call.name == "read"` dispatch in the TAO loop. That pattern doesn't scale. Before adding more tools, we need to understand what a tool *is* structurally, and what makes one good.

This module is conceptual.

## The components of a function tool

A **function tool** has four parts. The model needs all four to use the tool; your code needs all four to run it. These parts are language-agnostic — they exist in any stack that talks to a modern LLM API.

| Part | Lives in | Who reads it |
|---|---|---|
| **Function** | Your code | Your executor (runs the function) |
| **Name** | The tool's schema | The model (picks the tool by name) |
| **Description** | The tool's schema | The model (decides when to use it) |
| **Schema** | The tool's schema | The model (figures out what to pass) |

Concretely (Python expressing the function side, JSON Schema for the rest):

```python
def read(path: str) -> str:           # the function
    with open(path) as f:
        return f.read()

{
    "name": "read",                   # the name
    "description": "Read a file",     # the description
    "input_schema": {                 # the schema
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
}
```

Designing a tool = getting each of those four parts right. The rest of this module is how.

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

If the file doesn't exist, the runtime raises an error. The loop crashes — unless something catches it. (Every language has some version of this: Python raises exceptions, Go returns `error`, Rust returns `Result::Err`. The problem is the same regardless of mechanism: an unhandled failure tears the agent loop down.)

The right pattern: the model sees a string describing the failure.

```
"error: [Errno 2] No such file or directory: 'foo.txt'"
```

It reads the error, reasons about it ("oh, maybe I meant `foo.md`"), and tries again. **The error message is a self-correction channel.**

*Where* the error catching lives (Python's `try`/`except`, JavaScript's `try`/`catch`, Rust's `?` + `Result` mapping — same idea, different syntax) is a design decision. Two choices:

- **In each tool.** Every tool catches its own failures. Simple, but the same pattern repeats everywhere.
- **In the executor.** One central function catches failures for all tools. DRY; tools stay thin.

Module 3 put the catch in the tool, and Module 4's loop kept it there.

## Descriptions and naming

The model reads the `name` and `description` when deciding which tool to use. Both matter.

**Names** — pick canonical ones the model already knows:

- Good: `read`, `write`, `edit`, `bash`, `grep`, `glob`
- Avoid: `fileReader`, `textWriter`, `contentSearcher`, `doFileStuff`

Short, command-line-style names let the model map user requests ("search for TODOs") directly to tools.

**Descriptions** — state what the tool does in one sentence:

- Good: *"Read the contents of a file"*
- Good: *"Search file contents for a regex pattern under a directory"*
- Avoid: *"Does stuff with files"* (vague)
- Avoid: *"Read, search, or list files"* (overloaded — should be three tools)

Rule of thumb: if you removed the tool's name and kept only the description, could the model still know when to use it? If yes, the description is good.

## Schema design

The `input_schema` is a [JSON Schema](https://json-schema.org/) dict. Two fields drive behavior:

**`properties`** — each argument's type and description. Put a description on *each* property; the model reads those too.

```python
"properties": {
    "path": {"type": "string", "description": "Relative path to the file"},
    "offset": {"type": "integer", "description": "Line to start at (0-indexed)"},
    "limit": {"type": "integer", "description": "Maximum lines to return"},
}
```

**`required`** — which arguments the model *must* provide. Keep this minimal. If a parameter has a sensible default, make it optional so the model can omit it.

```python
"required": ["path"]   # offset and limit are optional
```

Pitfall: too many required fields force the model to guess values (e.g., `offset=0`) when it doesn't care. Let it omit them; use defaults in your function.

## The tools we'll build

Six tools following these principles:

| Tool | Purpose |
|---|---|
| `read` | Read file contents (already exists from Module 3) |
| `write` | Create or overwrite a file |
| `edit` | Find-and-replace in a file |
| `grep` | Search file contents for a regex |
| `glob` | Find files by pattern |
| `bash` | Run a shell command |

Six tools cover most of what a coding agent does: examine files, change files, find things, run things.

---

**Next:** [Module 6: The tool registry](../06-the-tool-registry/)
