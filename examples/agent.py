import os
import re
import asyncio
import subprocess
import glob as _glob
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()

client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


# --- Tools ---

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


# --- Registry ---

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
    try:
        result = await tool["fn"](**input)
        return result if isinstance(result, str) else str(result)
    except Exception as e:
        return f"error: {e}"


TOOL_SCHEMAS = build_tool_schemas(TOOLS)


# --- Loop ---

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
