# Add tools

The agent from Module 3 has one tool. A coding agent needs more — read, write, edit, search, run commands. Adding the second tool surfaces a structural problem: the dispatch grows an `if/elif` per tool, the schema list duplicates the parameter descriptions, and there's no single place to handle errors.

This module fixes that in four steps.

1. **Tool design** — what makes a tool the model uses well.
2. **A registry** — define each tool once; derive the schemas and dispatch from it.
3. **The toolkit** — six tools every coding agent needs.
4. **A central executor** — one place that runs tools and turns exceptions into strings.

By the end you have [`agents/coding-agent`](../../agents/coding-agent/).

## Tool design

A tool is the agent's interface to its environment. Bad tools cost more tokens, take more turns, and produce worse results — even if the model is fine. A few principles, drawn from Anthropic's [*Writing Tools for Agents*](https://www.anthropic.com/engineering/writing-tools-for-agents):

**Pick the right granularity.** A `search_and_summarize` tool that does the whole job in one call beats `list_files` → `read` → `read` → `read`. Each tool call is a model round-trip; fewer round-trips means lower latency and fewer chances to derail. But going too coarse (`do_everything(task)`) hides choices the model needs to make. Aim for tools that match how a human would describe a sub-step.

**Name and describe like docs.** The model picks a tool by reading the name and description. `edit` beats `modify_file_contents`; *"Replace 'old' with 'new' in a file; 'old' must appear exactly once"* beats *"edits files"*. Constraints in the description (*"must appear exactly once"*) save the model from making mistakes the first time.

**Return strings.** The model consumes text. A tool can compute anything internally, but it returns a string for the model to read.

**Return errors as strings, never raise.** If the file doesn't exist, the tool returns `"error: file not found"` — the model sees the message and tries something else. A raised exception kills the loop.

**Make outputs informative but bounded.** A `grep` that returns 10,000 matches blows the context window. Cap the output, summarize, or paginate. The agent should never waste tokens reading noise.

## A registry

Each new tool needs three things plumbed: the function, the schema, and the dispatch branch. With one tool that's fine; with six it's three places to edit per tool, easy to drift out of sync.

A registry collapses those into one definition:

```python
TOOLS = {
    "read":  {"fn": read,  "description": "Read the contents of a file",
              "params": {"path": "Path to the file to read"}},
    "write": {"fn": write, "description": "Create or overwrite a file",
              "params": {"path": "Path to the file to write",
                         "content": "Content to write to the file"}},
    # ...
}
```

Each entry has the function, a description, and a `params` map of parameter-name to parameter-description. The schema and the dispatch fall out of this:

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


TOOL_SCHEMAS = build_tool_schemas(TOOLS)
```

Now adding a tool is one entry in `TOOLS`. The schema and dispatch update automatically.

> [!NOTE]
> This registry treats every parameter as a required string. That's enough for most coding-agent tools — paths, regex patterns, shell commands. If a tool needs numbers, enums, or optional parameters, the registry would extend; for our six tools, the simple shape is fine.

## The toolkit

Six tools cover most coding work — three read tools, three write/exec tools.

| Tool | Purpose |
|---|---|
| `read` | Read a file's contents |
| `grep` | Search file contents under a directory for a regex |
| `glob` | List files matching a glob pattern |
| `write` | Create or overwrite a file |
| `edit` | Replace exact text in a file (must match once) |
| `bash` | Run a shell command |

A few notes on the choices:

**`edit` requires `old` to match exactly once.** Models are good at copying enough surrounding context to make a target unique. If `old` matches multiple times, the tool returns an error rather than guessing — the model adjusts and retries.

**`grep` and `glob` are separate.** `grep` searches *inside* files (regex over content); `glob` searches *over* paths (filename patterns). They're complementary; combining them into one tool would force the model to encode the difference in arguments.

**`bash` is a single escape hatch.** Rather than tools for `run_tests`, `git_status`, `npm_install`, the model gets one general-purpose shell. The tradeoff: less guidance for the model, more flexibility, far fewer tools to maintain. For an experienced coding model, it works.

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
    regex = re.compile(pattern)
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

A few things to notice:

- **`grep` skips noise directories** (`.git`, `__pycache__`, `.venv`) by default and caps results at 100 lines. Without these limits a single `grep` can blow the context window.
- **`bash` has a 30-second timeout** and merges stdout/stderr — the model can read either kind of output uniformly.
- **`edit` and `write` return short confirmations.** `"ok"` and `"wrote 1234 chars to foo.py"` give the model just enough to know the action succeeded.

## A central executor

With six tools, every tool call goes through one place. That place becomes the natural home for cross-cutting concerns — error handling, future logging, future approval gates.

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

This is the safety net. Individual tools can use plain `with open(...)` — if the file doesn't exist, the executor catches the `FileNotFoundError` and returns it as a string. The agent loop never sees an exception; the model just sees a `tool_result` saying `"error: ..."` and adapts.

The TAO loop barely changes — the per-tool dispatch becomes a call to `execute_tool`:

```python
outputs = await asyncio.gather(
    *(execute_tool(c.name, c.input) for c in tool_calls)
)
```

## Reference: coding-agent

The end state is [`agents/coding-agent`](../../agents/coding-agent/). It's the same script — six tools through a registry, one executor, one async TAO loop:

```bash
cd agents
uv run coding-agent/main.py
```

Try it on a real task:

```
❯ find all the TODOs in this codebase and write a summary to TODOS.md
```

The model will pick its own path: probably `grep` first, maybe `read` on a few hot files, then `write`. Each tool call is one entry in the registry; the loop doesn't know or care how many there are.

## What's missing

- **Nothing persists.** Quit the program and the entire conversation is gone — including everything the agent learned about your codebase.
- **The context window will fill.** A long session will eventually overflow the model's input limit. Right now there's no answer to that.
- **`bash` runs on your machine.** Anything the model can type, your shell will execute. That's the next major problem.

---

**Next:** [Module 5: Add memory](../05-add-memory/)
