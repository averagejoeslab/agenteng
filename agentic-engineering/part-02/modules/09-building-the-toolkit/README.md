# Building the toolkit

This module adds five tools to the registry from Module 8: `write`, `edit`, `grep`, `glob`, `bash`. Together with `read`, they're enough for the model to function as a real coding agent — examine files, make changes, find things, run commands.

Each tool follows Module 7's principles: focused responsibility, errors as strings, clear name and description. All tools are `async def` so the executor can dispatch them in parallel with `asyncio.gather`. The bodies are otherwise ordinary synchronous Python — async is about *how they're scheduled*, not about the work inside.

## write

Create or overwrite a file.

```python
async def write(path: str, content: str) -> str:
    try:
        with open(path, "w") as f:
            f.write(content)
        return f"wrote {len(content)} chars to {path}"
    except Exception as e:
        return f"error: {e}"
```

Design notes:

- Returns a confirmation with byte count, not the content. The model knows what it wrote.
- Overwrites without prompting. Destructive — handle with care.
- Creates the file if it doesn't exist.

## edit

Find-and-replace in a file.

```python
async def edit(path: str, old: str, new: str) -> str:
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

- Refuses if `old` appears more than once — safety against ambiguous changes.
- Refuses if `old` isn't found — better error than a silent no-op.
- `new` can be empty (effectively a delete).

## grep

Search file contents for a regex across a directory tree.

```python
import re

async def grep(pattern: str, path: str) -> str:
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

async def glob(pattern: str) -> str:
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

async def bash(cmd: str) -> str:
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
- Sync tool bodies in general block the event loop while they run — a slow `bash` or a multi-thousand-file `grep` holds up every other concurrent call. The proper fix is to wrap tool bodies in `asyncio.to_thread`. For our purposes, sequential-but-correct is fine; file I/O is fast enough that no one notices.

> [!WARNING]
> `bash` runs arbitrary commands on your machine with your permissions. In real agents you'd sandbox this (Docker, firejail, seccomp). For this curriculum — running locally in a project you control — it's fine.

## Adding them to the registry

Update the `TOOLS` dict. Each parameter carries a short description (per Module 7's advice) — the factory from Module 8 lifts those straight into the schema.

```python
TOOLS = {
    "read":  {"fn": read,  "description": "Read the contents of a file",
              "params": {"path": "Path to the file to read"}},
    "write": {"fn": write, "description": "Create or overwrite a file",
              "params": {"path": "Path to the file to write",
                         "content": "Content to write to the file"}},
    "edit":  {"fn": edit,  "description": "Replace 'old' with 'new' in a file; 'old' must appear exactly once",
              "params": {"path": "Path to the file to edit",
                         "old": "Exact text to replace (must appear exactly once)",
                         "new": "Replacement text"}},
    "grep":  {"fn": grep,  "description": "Search file contents for a regex pattern under a directory",
              "params": {"pattern": "Regex pattern to search for",
                         "path": "Directory to search under"}},
    "glob":  {"fn": glob,  "description": "Find files matching a glob pattern (use ** for recursive)",
              "params": {"pattern": "Glob pattern; use ** for recursive matches"}},
    "bash":  {"fn": bash,  "description": "Run a shell command",
              "params": {"cmd": "Shell command to run"}},
}
```

Six tools. No changes needed to `build_tool_schemas()` or `execute_tool()` — the registry pattern handles them.

The system prompt also loses its single-tool hint — it read *"Use the read tool when you need to examine file contents"* through Module 8; with six tools, naming them all in the prompt adds noise without helping the model. Shorten it to `"You are a helpful coding assistant."` — the schemas carry the rest.

Make sure the imports at the top of `main.py` cover everything the tools need:

```python
import os
import re
import asyncio
import subprocess
import glob as _glob
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
```

## Running it

```bash
uv run main.py
```

Try prompts that require multiple tools:

```
❯ What Python files are in this project?
I'll look.
[glob matches the .py files]
You have two: agents/basic-agent/main.py and agents/coding-agent/main.py.

❯ Does either import the anthropic package?
[grep for the import]
Yes — both files have `from anthropic import AsyncAnthropic`.

❯ /q
```

(Exact phrasing varies — models are non-deterministic.)

The TAO loop iterates multiple times per turn: the model chains tools (`glob` → `grep`, `read` → `edit`) to answer multi-step questions. And when the model emits several tool calls in one response, `asyncio.gather` runs them concurrently.

## The repetition problem

Look at the six tools. Every one of them has this pattern:

```python
async def tool(...):
    try:
        # do the actual work
        ...
    except Exception as e:
        return f"error: {e}"
```

Six `try/except Exception as e: return f"error: {e}"` blocks of identical shape. Same pattern, six times. If you add a seventh tool, you write it again. If you change the error format, you change it in six places. That's a signal that something is misplaced. The executor (`execute_tool` from Module 8) is the natural place to catch exceptions for *all* tools — moving the try/except up there lets each tool shrink to its happy path.

## What this didn't address

The agent has a real toolkit but still has gaps:

- **Six identical try/except blocks** clutter the tool functions.
- **`bash` runs on the host with your permissions.** Real-world deployment requires sandboxing.
- **No memory across sessions.** The conversation resets every time you restart the REPL.
- **No tracing.** Hard to debug or measure systematically.
- **No eval.** No way to verify behavior changes don't regress.

## Prompt your coding agent

If you want your coding agent to write this for you, paste:

```
Add five tools to main.py's TOOLS registry: write, edit, grep, glob, bash.

For each tool, define an `async def` function that:
- Takes the parameters documented below
- Returns a string (including errors as strings — never raise)
- Catches exceptions with try/except and returns them as "error: <message>"
- Is `async def` even if the body is sync, so the executor can await it

Tool specs:
- write(path, content): create or overwrite the file, return "wrote N chars to <path>"
- edit(path, old, new): find-and-replace in a file, but refuse if 'old' appears zero or more than one time
- grep(pattern, path): regex search under path, skip .git / __pycache__ / .venv, cap at 100 hits, format "file:line:content"
- glob(pattern): Python's glob.glob with recursive=True, return sorted matches joined by newline (alias the module as _glob to avoid name collision)
- bash(cmd): subprocess.run with shell=True, capture_output=True, 30s timeout; return stdout+stderr or "(exit N)"

Then add each to the TOOLS dict with fn, description, and a params dict mapping each parameter name to a short description the model will read. Don't change build_tool_schemas or execute_tool — they already handle the new tools.

Also shorten the system prompt to "You are a helpful coding assistant." — the single-tool hint from the earlier modules adds noise now that there are six tools.
```

The prompt tells your agent *what* to write. The module explains *why* — read it first.

---

**Next:** [Module 10: The tool executor](../10-the-tool-executor/)
