# The tool executor

Six tools from Module 7. Same `try/except Exception as e: return f"error: {e}"` in every one. This module pulls that pattern out of the tools and into the executor — one central place that wraps every tool call. Tools become thin. The executor becomes the **base tool contract**: the single definition of what happens when any tool runs.

## The pattern shift

**Before (Module 7).** Every tool handles its own errors:

```python
def read(path: str) -> str:
    try:
        with open(path, "r") as f:
            return f.read()
    except Exception as e:
        return f"error: {e}"
```

**After (this module).** The tool stays pure; the executor catches:

```python
def read(path: str) -> str:
    with open(path, "r") as f:
        return f.read()
```

Six tools, each ~4 lines shorter. The `try/except` moves to one place.

## Centralizing error handling

Upgrade `execute_tool` from Module 6. It gains two responsibilities:

1. **Catch any exception** the tool raises and return it as a string.
2. **Stringify the result** — if a tool returns something non-string (e.g., a path list, a count), convert it before sending to the API.

```python
def execute_tool(name: str, input: dict) -> str:
    tool = TOOLS.get(name)
    if tool is None:
        return f"error: unknown tool {name}"
    try:
        result = tool["fn"](**input)
        return result if isinstance(result, str) else str(result)
    except Exception as e:
        return f"error: {e}"
```

Three things this does:

- **Unknown tool names** — returns an error string (same as Module 6).
- **Exceptions** — any tool that raises gets caught; the error becomes a string the model can read.
- **Non-string returns** — future tools that return structured data get stringified automatically.

## The base tool contract

With the executor doing this work, every tool in the registry now has the same shape:

- Takes kwargs matching its `params`
- Returns a value the executor will stringify (or raises — the executor catches)
- Doesn't need its own try/except

That's the **base tool contract**: the invariant every tool satisfies. The executor enforces it.

Think of it like a function signature for the *whole category* of tools:

```
(**kwargs) -> str | Any   (raise allowed, executor handles)
```

Moving a responsibility from six places into one is the core refactor. But the pattern matters beyond cleanup:

- **Add observability** (Part 4): instrument one function, not six.
- **Add approval gates** (Part 6): check permissions in one place before any tool runs.
- **Add timing / cost** (Part 7): wrap execution with timers once.

The executor is where cross-cutting concerns live. Once the base contract exists, each new concern is a one-line addition.

## Refactoring the tools

Strip the try/except from each tool. The tool keeps only its happy-path logic (plus domain-specific guards like the edit tool's "must match exactly once" check — that's business logic, not error handling):

```python
def read(path: str) -> str:
    with open(path, "r") as f:
        return f.read()


def write(path: str, content: str) -> str:
    with open(path, "w") as f:
        f.write(content)
    return f"wrote {len(content)} chars to {path}"


def edit(path: str, old: str, new: str) -> str:
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


def grep(pattern: str, path: str) -> str:
    regex = re.compile(pattern)   # re.error propagates; executor catches
    hits = []
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


def glob(pattern: str) -> str:
    matches = sorted(_glob.glob(pattern, recursive=True))
    return "\n".join(matches) or "no matches"


def bash(cmd: str) -> str:
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        return "error: command timed out after 30s"
    out = result.stdout + result.stderr
    return out.strip() or f"(exit {result.returncode})"
```

Notes on what stayed:

- **`edit`'s content-based errors** (not found, ambiguous match) stay in the tool. They're domain logic — part of what `edit` means — not incidental exceptions.
- **`grep`'s inner `try/except (OSError, UnicodeDecodeError)`** stays. It's not catching errors to report — it's *skipping* unreadable files silently. Different purpose.
- **`bash`'s `TimeoutExpired` catch** stays. Converting a timeout into a specific user-visible message is domain logic; a bare `"error: ..."` from the executor wouldn't convey the timeout.

**Rule**: if the try/except produces a tool-specific message or changes behavior, it belongs in the tool. If it just forwards an exception as `"error: {e}"`, the executor handles it.

## The full file

The end state of Part 2 lives at [`agents/coding-agent/main.py`](../../../../agents/coding-agent/main.py). Thin tools, centralized executor.

## Running it

```bash
uv run coding-agent/main.py
```

(From the `agents/` directory — shared `.env` and `.venv` live there.)

Same behavior as Module 7 end state. Same prompts work. What changed is internal — the agent's code is shorter and every cross-cutting concern now has one place to live.

## What you have now

A coding agent with six tools and a clean executor:

- Registry stores each tool's function, description, and parameters.
- Factory generates API-shaped schemas from the registry.
- Executor runs any tool, catches any exception, stringifies the result.
- Each tool focuses on its happy path (plus its own domain logic).

This is the end state of Part 2 — lives at `agents/coding-agent/`.

## What's next

Part 3 (Memory and Context) tackles the remaining limitations:

- The conversation resets every time the REPL restarts.
- The context window fills up on long sessions; nothing manages eviction.
- Past sessions can't be recalled semantically.

The executor pattern stays. Each later Part adds responsibilities to it:

- Part 4 (Observability): trace every tool call through the executor.
- Part 6 (Safety): gate tool execution on permissions.
- Part 7 (Cost/Latency): time and cache executions.

## Prompt your coding agent

If you want your coding agent to write this for you, paste:

```
Refactor main.py so error handling lives in the executor, not in each tool.

1. Update execute_tool(name, input) to:
   - Return "error: unknown tool {name}" if the name isn't in TOOLS
   - Try to call tool["fn"](**input)
   - Stringify the result if it isn't already a string
   - Catch any Exception and return "error: {e}"

2. For each of the six tools (read, write, edit, grep, glob, bash), remove the blanket try/except that returns "error: {e}". Keep try/except only when it does tool-specific work:
   - edit: keep the "not found" / "appears N times" checks (domain logic)
   - grep: keep the inner except that silently skips unreadable files
   - bash: keep the TimeoutExpired catch that returns a specific timeout message

3. Do not change build_tool_schemas or the TAO loop.
```

The prompt tells your agent *what* to write. The module explains *why* — read it first.

---

**Next:** Part 3 — Memory and Context *(coming soon)*
