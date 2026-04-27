# The tool executor

Six tools from Module 7. Same `try/except Exception as e: return f"error: {e}"` in every one. This module pulls that pattern out of the tools and into the executor — the one central place that wraps every tool call. Tools become thin. The executor becomes the **base tool contract**: the single definition of what happens when any tool runs.

## The pattern shift

**Before (Module 7).** Every tool handles its own errors:

```python
async def read(path: str) -> str:
    try:
        with open(path, "r") as f:
            return f.read()
    except Exception as e:
        return f"error: {e}"
```

**After (this module).** The tool stays pure; the executor catches:

```python
async def read(path: str) -> str:
    with open(path, "r") as f:
        return f.read()
```

Six tools, each ~4 lines shorter. The `try/except` moves to one place.

## Centralizing error handling

Upgrade `execute_tool` from Module 6. It gains two responsibilities:

1. **Catch any exception** the tool raises and return it as a string.
2. **Stringify the result** — if a tool returns something non-string (e.g., a path list, a count), convert it before sending to the API.

```python
async def execute_tool(name: str, input: dict) -> str:
    tool = TOOLS.get(name)
    if tool is None:
        return f"error: unknown tool {name}"
    try:
        result = await tool["fn"](**input)
        return result if isinstance(result, str) else str(result)
    except Exception as e:
        return f"error: {e}"
```

Three things this does:

- **Unknown tool names** — returns an error string (same as Module 6).
- **Exceptions** — any tool that raises gets caught; the error becomes a string the model can read.
- **Non-string returns** — future tools that return structured data get stringified automatically.

The parallel-dispatch `asyncio.gather(*(execute_tool(...) for c in tool_calls))` at the call site is unchanged from Module 4 — gather works through the upgraded executor the same way.

## The base tool contract

With the executor doing this work, every tool in the registry now has the same shape:

- Takes named arguments matching its declared `params`
- Runs as a coroutine (`async def` in Python, `async function` in JS, `async fn` in Rust — the name differs, the property doesn't)
- Returns a value the executor will stringify (or throws — the executor catches)
- Doesn't need its own try/except

That's the **base tool contract**: the invariant every tool satisfies. The executor enforces it.

As a language-neutral signature:

```
tool: (named args) → string | any    (may throw; executor handles it)
```

Moving a responsibility from six places into one is the core refactor. The pattern matters beyond cleanup — the executor is where **cross-cutting concerns** live, and every later Part hooks into it:

- **Safety** (Part 4): check permissions in one place before any tool runs.
- **Observability** (Part 5): instrument one function, not six.
- **Cost / latency** (Part 7): wrap execution with timers once. Part 7 also replaces the sync tool bodies with `asyncio.to_thread` wrappers here, so `asyncio.gather` delivers real parallelism for blocking tools like `bash`.

Cross-cutting concerns are a language-agnostic concept — same pattern a middleware stack or an HTTP interceptor implements. Once the base contract exists, each new concern is a one-line addition.

## Refactoring the tools

Strip the try/except from each tool. The tool keeps only its happy-path logic (plus domain-specific guards like the edit tool's "must match exactly once" check — that's business logic, not error handling):

```python
async def read(path: str) -> str:
    with open(path, "r") as f:
        return f.read()


async def write(path: str, content: str) -> str:
    with open(path, "w") as f:
        f.write(content)
    return f"wrote {len(content)} chars to {path}"


async def edit(path: str, old: str, new: str) -> str:
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


async def grep(pattern: str, path: str) -> str:
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


async def glob(pattern: str) -> str:
    matches = sorted(_glob.glob(pattern, recursive=True))
    return "\n".join(matches) or "no matches"


async def bash(cmd: str) -> str:
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

The end state of Part 2 lives at [`agents/coding-agent/main.py`](../../../../agents/coding-agent/main.py). Thin tools, centralized executor, parallel dispatch.

## Running it

```bash
uv run coding-agent/main.py
```

(From the `agents/` directory — shared `.env` and `.venv` live there.)

Same behavior as Module 7 end state. Same prompts work. What changed is internal — the agent's code is shorter and every cross-cutting concern now has one place to live.

## What you have now

A coding agent with six tools and a clean async executor:

- Registry stores each tool's function, description, and parameters.
- Factory generates API-shaped schemas from the registry.
- Executor awaits any tool, catches any exception, stringifies the result.
- `asyncio.gather` dispatches every requested tool in a single turn concurrently.
- Each tool focuses on its happy path (plus its own domain logic).

This is the end state of Part 2 — lives at `agents/coding-agent/`.

## What's next

Part 3 (Memory and Context) tackles the remaining limitations:

- The conversation resets every time the REPL restarts.
- The context window fills up on long sessions; nothing manages eviction.
- Past sessions can't be recalled semantically.

The executor pattern stays. Each later Part adds responsibilities to it:

- Part 4 (Safety): gate tool execution on permissions.
- Part 5 (Observability): trace every tool call through the executor.
- Part 7 (Cost/Latency): wrap tool bodies in `asyncio.to_thread` so blocking calls (`bash`, large file I/O) don't stall the event loop — and `asyncio.gather` gives real parallelism.

## Prompt your coding agent

If you want your coding agent to write this for you, paste:

```
Refactor main.py so error handling lives in the executor, not in each tool.

1. Update `async def execute_tool(name, input)` to:
   - Return "error: unknown tool {name}" if the name isn't in TOOLS
   - Try to `await tool["fn"](**input)`
   - Stringify the result if it isn't already a string
   - Catch any Exception and return "error: {e}"

2. For each of the six tools (read, write, edit, grep, glob, bash), remove the blanket try/except that returns "error: {e}". Keep try/except only when it does tool-specific work:
   - edit: keep the "not found" / "appears N times" checks (domain logic)
   - grep: keep the inner except that silently skips unreadable files
   - bash: keep the TimeoutExpired catch that returns a specific timeout message

3. Do not change build_tool_schemas, the TAO loop, or the asyncio.gather dispatch.
```

The prompt tells your agent *what* to write. The module explains *why* — read it first.

---

**Next:** Part 3 — Memory and Context *(coming soon)*
