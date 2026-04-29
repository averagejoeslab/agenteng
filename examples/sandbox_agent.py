import os
import re
import json
import atexit
import asyncio
import secrets
import subprocess
import glob as _glob
from pathlib import Path
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import numpy as np

load_dotenv()

client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

MODEL = "claude-sonnet-4-5"
SUMMARY_MODEL = "claude-haiku-4-5"
CONTEXT_BUDGET = 150_000
RECALL_K = 3
RECALL_THRESHOLD = 0.3
SANDBOX_IMAGE = "agenteng-sandbox"

STATE_DIR = Path.home() / ".sandbox-agent"
MESSAGES_FILE = STATE_DIR / "messages.json"
RECALL_FILE = STATE_DIR / "recall.json"


# --- Sandbox ---

_sandbox_name: str | None = None


def start_sandbox(workspace: str) -> None:
    global _sandbox_name
    inspect = subprocess.run(["docker", "image", "inspect", SANDBOX_IMAGE],
                              capture_output=True)
    if inspect.returncode != 0:
        print(f"Building sandbox image '{SANDBOX_IMAGE}'...")
        subprocess.run(
            ["docker", "build", "-f", "Dockerfile.sandbox", "-t", SANDBOX_IMAGE, "."],
            check=True,
        )

    _sandbox_name = f"sandbox-agent-{secrets.token_hex(8)}"
    subprocess.run([
        "docker", "run", "-d", "--rm",
        "--name", _sandbox_name,
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--network", "none",
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=100m",
        "-v", f"{workspace}:/workspace",
        "-w", "/workspace",
        "--memory", "512m",
        "--cpus", "1.0",
        "--pids-limit", "100",
        "--user", "1000:1000",
        SANDBOX_IMAGE,
        "sleep", "infinity",
    ], check=True, capture_output=True)


def stop_sandbox():
    if _sandbox_name:
        subprocess.run(
            ["docker", "stop", "-t", "1", _sandbox_name],
            check=False, capture_output=True, timeout=10,
        )


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
            ["docker", "exec", _sandbox_name, "bash", "-c", cmd],
            capture_output=True, text=True, timeout=30,
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
    "bash":  {"fn": bash,  "description": "Run a shell command (sandboxed)",
              "params": {"cmd": "Shell command to run"}},
}


def build_tool_schemas(tools):
    schemas = []
    for name, meta in tools.items():
        properties = {p: {"type": "string", "description": desc} for p, desc in meta["params"].items()}
        schemas.append({
            "name": name,
            "description": meta["description"],
            "input_schema": {"type": "object", "properties": properties, "required": list(meta["params"])},
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


# --- Persistence ---

def _serialize(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    raise TypeError(f"can't serialize {type(obj)}")


def load_messages() -> list:
    if not MESSAGES_FILE.exists():
        return []
    try:
        return json.loads(MESSAGES_FILE.read_text())
    except json.JSONDecodeError as e:
        print(f"warning: {MESSAGES_FILE} is corrupt ({e}); starting fresh")
        return []


def save_messages(messages: list) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    MESSAGES_FILE.write_text(json.dumps(messages, default=_serialize, indent=2))


def _is_tool_result(block) -> bool:
    if isinstance(block, dict):
        return block.get("type") == "tool_result"
    return getattr(block, "type", None) == "tool_result"


def find_safe_truncation_point(messages: list, drop_n: int = 1) -> int:
    boundaries = []
    for i, msg in enumerate(messages):
        if msg["role"] != "user":
            continue
        content = msg["content"]
        if isinstance(content, str):
            boundaries.append(i)
        elif not any(_is_tool_result(b) for b in content):
            boundaries.append(i)
    if drop_n >= len(boundaries):
        return boundaries[-1] if boundaries else 0
    return boundaries[drop_n]


async def trim_to_budget(messages: list, budget: int, system: str) -> list:
    while True:
        count = await client.messages.count_tokens(
            model=MODEL, system=system, messages=messages, tools=TOOL_SCHEMAS,
        )
        if count.input_tokens <= budget or len(messages) <= 1:
            return messages
        truncate_at = find_safe_truncation_point(messages, drop_n=1)
        if truncate_at == 0:
            return messages
        messages = messages[truncate_at:]


# --- Semantic recall ---

print("Loading embedding model...")
_embed_model = SentenceTransformer("all-MiniLM-L6-v2")


def embed(text: str) -> np.ndarray:
    return _embed_model.encode(text, convert_to_numpy=True, normalize_embeddings=True)


def load_recall() -> list[dict]:
    if not RECALL_FILE.exists():
        return []
    try:
        return json.loads(RECALL_FILE.read_text())
    except json.JSONDecodeError:
        return []


def save_recall(entries: list[dict]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    RECALL_FILE.write_text(json.dumps(entries))


def add_to_recall(text: str, entries: list[dict]) -> None:
    vec = embed(text)
    entries.append({"text": text, "embedding": vec.tolist()})
    save_recall(entries)


def recall(query: str, entries: list[dict], k: int = RECALL_K, threshold: float = RECALL_THRESHOLD) -> list[str]:
    if not entries:
        return []
    q_vec = embed(query)
    scored = []
    for e in entries:
        e_vec = np.array(e["embedding"])
        score = float(np.dot(q_vec, e_vec))
        scored.append((score, e["text"]))
    scored.sort(reverse=True)
    return [text for score, text in scored[:k] if score >= threshold]


async def summarize_turn(turn_messages: list) -> str:
    response = await client.messages.create(
        model=SUMMARY_MODEL,
        max_tokens=200,
        system="You write one-paragraph summaries of agent conversations. Capture what the user asked and what was concluded or done. No fluff.",
        messages=[{"role": "user",
                   "content": f"Summarize this exchange:\n\n{json.dumps(turn_messages, default=_serialize)[:8000]}"}],
    )
    return response.content[0].text


# --- Main loop ---

BASE_SYSTEM = "You are a helpful coding assistant."


async def main():
    start_sandbox(os.getcwd())
    atexit.register(stop_sandbox)

    messages = load_messages()
    recall_entries = load_recall()

    while True:
        user_input = input("❯ ")
        if user_input.lower() in ("/q", "exit"):
            break

        recalled = recall(user_input, recall_entries)
        if recalled:
            memory_block = "\n\n".join(f"- {s}" for s in recalled)
            system = f"{BASE_SYSTEM}\n\n## Relevant memory from past conversations\n\n{memory_block}"
        else:
            system = BASE_SYSTEM

        messages.append({"role": "user", "content": user_input})
        messages = await trim_to_budget(messages, CONTEXT_BUDGET, system)
        turn_start = len(messages) - 1

        while True:
            response = await client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=system,
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

            outputs = await asyncio.gather(*(execute_tool(c.name, c.input) for c in tool_calls))
            messages.append({
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": c.id, "content": o}
                            for c, o in zip(tool_calls, outputs)],
            })

        save_messages(messages)

        turn_messages = messages[turn_start:]
        summary = await summarize_turn(turn_messages)
        add_to_recall(summary, recall_entries)


asyncio.run(main())
