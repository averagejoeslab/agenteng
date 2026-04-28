# Persistent memory

The agent built through Part 2 forgets everything when you restart it. The conversation lives entirely in `messages` in memory; quitting the REPL drops it. For one-off scripts that's fine. For an agent you actually use — debugging across days, continuing a half-finished refactor tomorrow morning — you need state that survives restart.

This module gives the agent **persistent memory**: save the conversation on every turn, load it on startup. The mechanics are mundane (read a file, write a file). The interesting part is the design choices around *what* to store, *where*, and *when*.

## The bare mechanic

The Messages API is stateless. The server stores nothing between calls — the agent has been sending the full `messages` history with every request from Module 3 onward. So persistence isn't about the API; it's about your local `messages` list.

The pattern:

1. **On startup**, load `messages` from disk if a saved file exists. Otherwise start with `[]`.
2. **After each turn** completes, write `messages` to disk.

That's it. The agent loop barely changes; two function calls bracket each turn.

## Where to put the file

Three reasonable locations:

| Location | Pros | Cons |
|---|---|---|
| `./.agent-state.json` (cwd) | per-project conversations | gets lost when you `cd` elsewhere |
| `~/.coding-agent/state.json` (home) | one persistent state per user | one global conversation regardless of project |
| `~/.coding-agent/<project-id>.json` | per-project, persistent | needs a project ID concept |

We'll use the **home-directory single file** for this module. It's the simplest correct thing — one ongoing conversation you resume across sessions. Per-project state and multiple named sessions are extensions.

## What to serialize

`messages` is a list of `{"role": ..., "content": ...}` dicts where `content` is either a string or a list of `ContentBlock` objects from the SDK. The SDK's blocks are Pydantic models with a `model_dump()` method that produces JSON-serializable dicts.

`json.dumps` handles the strings natively. For the blocks, we'll use a `default` function that calls `model_dump()`.

```python
import json

def serialize(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    raise TypeError(f"can't serialize {type(obj)}")

json.dumps(messages, default=serialize, indent=2)
```

The reverse is even simpler — JSON-decoded dicts go straight back to the API. The API accepts dicts in the same shape as the block objects.

## The code

A small storage module. Two functions: `load_messages` and `save_messages`.

```python
import json
from pathlib import Path

STATE_DIR = Path.home() / ".coding-agent"
STATE_FILE = STATE_DIR / "messages.json"


def _serialize(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    raise TypeError(f"can't serialize {type(obj)}")


def load_messages() -> list:
    if not STATE_FILE.exists():
        return []
    try:
        return json.loads(STATE_FILE.read_text())
    except json.JSONDecodeError as e:
        print(f"warning: {STATE_FILE} is corrupt ({e}); starting fresh")
        return []


def save_messages(messages: list) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(messages, default=_serialize, indent=2))
```

Notes:

- **Missing file → empty list.** First-run case. No error, just start fresh.
- **Corrupt file → empty list with warning.** Don't crash the agent on bad state; print a heads-up and continue. The user will see the warning when starting up.
- **Directory created on save.** Idempotent; safe to call repeatedly.
- **Atomic writes are skipped here for brevity.** Production code should write to a temp file and `os.rename` to avoid partial-write corruption on crash. Mentioned, not implemented.

## Wiring into the agent

Two changes to the Module 10 coding-agent:

1. **Replace `messages = []` with `messages = load_messages()`** at the top of `main`.
2. **Call `save_messages(messages)` at the end of each user turn** (after the inner TAO loop exits).

That's the whole integration. The TAO loop itself is unchanged.

```python
async def main():
    messages = load_messages()

    while True:
        user_input = input("❯ ")
        if user_input.lower() in ("/q", "exit"):
            break

        messages.append({"role": "user", "content": user_input})

        # The TAO loop (unchanged from Module 10)
        while True:
            response = await client.messages.create(...)
            messages.append({"role": "assistant", "content": response.content})
            # ... existing dispatch logic ...
            tool_calls = [b for b in response.content if b.type == "tool_use"]
            if not tool_calls:
                break
            # ... execute and append tool results ...

        # Persist after each completed user turn
        save_messages(messages)
```

We save **after the inner loop exits** (one user-turn complete) rather than after each LLM call. Reasoning: mid-turn state can be inconsistent — a `tool_use` block needs its matching `tool_result` to be valid for the API. Saving at exchange boundaries means the loaded state is always API-valid.

## Running it

```bash
uv run coding-agent/main.py
```

Session 1:

```
❯ I'm working on the agenteng repo. The README's at the root.
Got it.
❯ /q
```

Quit. Look at the file:

```bash
cat ~/.coding-agent/messages.json
```

You should see your conversation as JSON.

Session 2:

```bash
uv run coding-agent/main.py
```

```
❯ What was I working on?
You were working on the agenteng repo. The README is at the root.
```

The agent remembers because `messages` was loaded from disk on startup. The full prior conversation went into the very first API call of the new session.

## Trade-offs to know

**File vs. database.** A flat JSON file is great until conversations get long enough that re-reading and re-writing the whole thing on every turn gets slow. SQLite is the natural next step — append-only inserts, fast reads. For a curriculum agent on small conversations, the file approach is fine. We'll address scale in the next module.

**Single session vs. named sessions.** This module has one ongoing conversation. Real coding agents (Claude Code, Aider) often have a notion of "session" tied to a project directory — one conversation per repo. That's a routing problem on top of storage; the storage primitive is the same.

**Privacy and secrets.** The file contains every message — user inputs and tool outputs. If a tool ever returned an API key or a password, it's now on disk. Worth knowing; we'll address it in Part 4 (Safety).

## What this didn't address

- **Unbounded growth.** Every turn appends. After enough conversation the message history exceeds the model's context window, and the API will start refusing requests. The next module addresses this — context as a budget.
- **Search across sessions.** The conversation is one linear log. There's no way for the agent to recall *"what did the user ask three weeks ago?"* without rereading everything. That's a Module 13 problem.
- **Atomic saves.** A crash mid-write can corrupt the file. Production agents write to a temp file and rename atomically.

## Prompt your coding agent

If you want your coding agent to write this for you, paste:

```
Add persistent message storage to main.py.

1. Create a small storage module (or inline two helpers in main.py):
   - STATE_FILE = Path.home() / ".coding-agent" / "messages.json"
   - load_messages() returns the JSON contents as a list, or [] if the file is missing or corrupt (print a warning if corrupt).
   - save_messages(messages) writes JSON to STATE_FILE, creating the parent directory if needed. Use a json.dumps default that calls model_dump() on Pydantic SDK blocks.

2. In `async def main()`:
   - Replace `messages = []` with `messages = load_messages()`.
   - After the inner TAO loop exits (one user turn complete), call save_messages(messages).
   - Don't save mid-turn — wait until the inner loop exits so the saved state is API-valid (no dangling tool_use without tool_result).

3. Don't change the TAO loop, the executor, or any tools.
```

The prompt tells your agent *what* to write. The module explains *why* — read it first.

---

**Next:** [Module 12: Context as a budget](../12-context-as-a-budget/)
