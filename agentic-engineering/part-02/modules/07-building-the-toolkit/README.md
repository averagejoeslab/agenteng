# Building the toolkit

This module adds five tools to the registry from Module 6: `write`, `edit`, `grep`, `glob`, `bash`. Together with `read`, they're enough for the model to function as a real coding agent — examine files, make changes, find things, run commands.

Each tool follows Module 5's principles: focused responsibility, errors as strings, clear name and description.

## write

Create or overwrite a file.

```python
def write(path: str, content: str) -> str:
    try:
        with open(path, "w") as f:
            f.write(content)
        return f"wrote {len(content)} chars to {path}"
    except Exception as e:
        return f"error: {e}"
```

Design notes:

- Returns a confirmation with byte count, not the content. The model knows what it wrote.
- Overwrites without prompting. Destructive — safety guards come in Part 6.
- Creates the file if it doesn't exist.

## edit

Find-and-replace in a file.

```python
def edit(path: str, old: str, new: str) -> str:
    try:
        with open(path, "r") as f:
            content = f.read()
        if old not in content:
            return f"error: 'old' string not found in {path}"
        count = content.count(old)
        if count > 1:
            return f"error: 'old' appears {count} times — make it more specific"
        with open(path, "w") as f:
            f.write(content.replace(old, new))
        return "ok"
    except Exception as e:
        return f"error: {e}"
```

Design notes:

- Refuses to edit if `old` appears more than once — safety against ambiguous changes.
- Refuses if `old` isn't found — better error than a silent no-op.
- `new` can be empty (effectively a delete).

## grep

Search file contents for a regex across a directory tree.

```python
import re

def grep(pattern: str, path: str) -> str:
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return f"error: invalid regex: {e}"
    hits = []
    try:
        for root, _, files in os.walk(path):
            if ".git" in root or "__pycache__" in root or ".venv" in root:
                continue
            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath) as f:
                        for i, line in enumerate(f, 1):
                            if regex.search(line):
                                hits.append(f"{fpath}:{i}:{line.rstrip()}")
                except (OSError, UnicodeDecodeError):
                    continue
        return "\n".join(hits[:100]) or "no matches"
    except Exception as e:
        return f"error: {e}"
```

Design notes:

- Regex pattern, not a literal string. The model knows how to write regex.
- Skips binary/unreadable files and common noise directories (`.git`, `__pycache__`, `.venv`) silently — otherwise the result list gets polluted.
- Caps at 100 hits to prevent context blowup on large codebases.
- `path` is required — no implicit current directory.

## glob

Find files matching a shell-style pattern.

```python
import glob as _glob   # shadowed by our tool name below

def glob(pattern: str) -> str:
    try:
        matches = sorted(_glob.glob(pattern, recursive=True))
        return "\n".join(matches) or "no matches"
    except Exception as e:
        return f"error: {e}"
```

Design notes:

- Supports `**` for recursive matches (e.g., `**/*.py`).
- Sorted output is deterministic — easier for the model to reason about.
- We alias the stdlib module as `_glob` so it doesn't collide with our tool function named `glob`.

## bash

Run a shell command.

```python
import subprocess

def bash(cmd: str) -> str:
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30,
        )
        out = result.stdout + result.stderr
        return out.strip() or f"(exit {result.returncode})"
    except subprocess.TimeoutExpired:
        return "error: command timed out after 30s"
    except Exception as e:
        return f"error: {e}"
```

Design notes:

- Captures both stdout and stderr — error output matters.
- 30-second timeout prevents infinite hangs.
- Runs on the host, no sandbox.

> [!WARNING]
> `bash` runs arbitrary commands on your machine with your permissions. In real agents you'd sandbox this (Docker, firejail, seccomp). For this curriculum — running locally in a project you control — it's fine. Part 6 (Safety and Guardrails) covers sandboxing properly.

## Adding them to the registry

Update the `TOOLS` dict:

```python
TOOLS = {
    "read":  {"fn": read,  "description": "Read the contents of a file",
              "params": ["path"]},
    "write": {"fn": write, "description": "Create or overwrite a file",
              "params": ["path", "content"]},
    "edit":  {"fn": edit,  "description": "Replace 'old' with 'new' in a file; 'old' must appear exactly once",
              "params": ["path", "old", "new"]},
    "grep":  {"fn": grep,  "description": "Search file contents for a regex pattern under a directory",
              "params": ["pattern", "path"]},
    "glob":  {"fn": glob,  "description": "Find files matching a glob pattern (use ** for recursive)",
              "params": ["pattern"]},
    "bash":  {"fn": bash,  "description": "Run a shell command",
              "params": ["cmd"]},
}
```

Six tools. No changes needed to `build_tool_schemas()` or `execute_tool()` — the registry pattern handles them.

Make sure the imports at the top of `main.py` include everything the tools need:

```python
import os
import re
import subprocess
import glob as _glob
from anthropic import Anthropic
from dotenv import load_dotenv
```

## The full file

The complete multi-tool coding agent lives at [`agents/coding-agent/main.py`](../../../../agents/coding-agent/main.py) — that's the end state of Part 2.

## Running it

```bash
uv run coding-agent/main.py
```

(From the `agents/` directory — the shared `.env` and `.venv` live there.)

Try prompts that require multiple tools:

```
❯ What Python files are in this project?
I'll look.
[glob matches the .py files]
You have two: agents/basic-agent/main.py and agents/coding-agent/main.py.

❯ Does either import the anthropic package?
[grep for the import]
Yes — both files have `from anthropic import Anthropic`.

❯ /q
```

(Exact phrasing varies — models are non-deterministic.)

The TAO loop iterates multiple times per turn: the model chains tools (glob → grep, read → edit) to answer multi-step questions.

## What you have now

A working coding agent with six tools. This is the end state of Part 1 + Part 2, and it lives at `agents/coding-agent/`.

The difference from `agents/basic-agent/` (Module 4 end state):

- Registry-based dispatch instead of an `if/elif` chain
- Five more tools (`write`, `edit`, `grep`, `glob`, `bash`)
- Can chain tools to complete multi-step tasks

## What's next

The agent is useful, but:

- **It forgets between sessions.** Conversation resets when you restart. Part 3 (Memory and Context) adds persistent memory.
- **No tracing.** When it does something wrong, you can't see why. Part 4 (Observability) adds structured traces.
- **No eval.** You don't know if it's *good*. Part 5 (Evaluation) addresses that.
- **`bash` runs on the host.** Part 6 (Safety and Guardrails) sandboxes it.

First, Module 8 covers MCP — the emerging standard for how tools like these get shared between agents.

## Prompt your coding agent

If you want your coding agent to write this for you, paste:

```
Add five tools to main.py's TOOLS registry: write, edit, grep, glob, bash.

For each tool, define a Python function that:
- Takes the parameters documented below
- Returns a string (including errors as strings — never raise)
- Catches exceptions with try/except and returns them as "error: <message>"

Tool specs:
- write(path, content): create or overwrite the file, return "wrote N chars to <path>"
- edit(path, old, new): find-and-replace in a file, but refuse if 'old' appears zero or more than one time
- grep(pattern, path): regex search under path, skip .git / __pycache__ / .venv, cap at 100 hits, format "file:line:content"
- glob(pattern): Python's glob.glob with recursive=True, return sorted matches joined by newline (alias the module as _glob to avoid name collision)
- bash(cmd): subprocess.run with shell=True, capture_output=True, 30s timeout; return stdout+stderr or "(exit N)"

Then add each to the TOOLS dict with name, fn, description, and params list. Don't change build_tool_schemas or execute_tool — they already handle the new tools.
```

The prompt tells your agent *what* to write. The module explains *why* — read it first.

---

**Next:** [Module 8: MCP](../08-mcp/)
