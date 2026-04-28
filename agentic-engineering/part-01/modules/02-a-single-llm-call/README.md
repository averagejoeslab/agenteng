# A single LLM call

This module makes one LLM call. One prompt in, one response out. No loop, no tools, no state between calls.

## The Messages API

The model is reached over HTTP. One POST per call, one JSON response. The [Anthropic Messages API](https://docs.anthropic.com/en/api/messages) specifies the full contract; to start we need four fields:

| Field | Purpose |
|---|---|
| `model` | Which Claude model to call (we'll use `claude-sonnet-4-5`) |
| `max_tokens` | Cap on the response length |
| `system` | System prompt — context that applies to the whole conversation |
| `messages` | The conversation — a list of `{"role": "user", "content": "..."}` turns |

The response contains a `content` array of blocks. For a plain text response there's one block with `type: "text"`.

## Setup

```bash
# Create a project directory
mkdir agent && cd agent

# Initialize with uv
uv init

# Add the Anthropic Python SDK and python-dotenv for loading .env
uv add anthropic python-dotenv

# Store your API key in a .env file
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env
```

## The sync version

Create `main.py`:

```python
import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    system="You are a helpful assistant.",
    messages=[
        {"role": "user", "content": "What is 2 + 2?"}
    ],
)
print(response.content[0].text)
```

Run it:

```bash
uv run main.py
```

Expected output:

```
4
```

(Exact phrasing varies — models are non-deterministic.)

## What just happened

1. The SDK sent an HTTP POST to `https://api.anthropic.com/v1/messages`
2. The request body contained `model`, `max_tokens`, `system`, and `messages`
3. The API returned a JSON response with a `content` array
4. `response.content[0].text` extracted the text from the first block

That's the whole mechanic. The model saw the user message, generated a response, sent it back.

## Why streaming matters

The code above waits for the *full* response before printing anything. For a short answer (`"4"`) the wait is short. For a longer response — a paragraph, a code block, a multi-step explanation — the user stares at a blank screen for several seconds while the model generates the entire message.

**Streaming** sends each chunk as the model generates it. Total latency stays the same, but *time to first token* drops to near-instant. For interactive use, that's the difference between an app that feels frozen and one that feels alive.

The Anthropic API supports streaming over the same Messages endpoint. The SDK exposes it as a streaming context manager. Python's `async`/`await` is the natural way to consume an async stream — the program yields control to the runtime each time it waits for the next chunk.

## The async streaming version

```python
import os
import asyncio
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()

client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


async def main():
    async with client.messages.stream(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system="You are a helpful assistant.",
        messages=[
            {"role": "user", "content": "Write three sentences about agents."}
        ],
    ) as stream:
        async for text in stream.text_stream:
            print(text, end="", flush=True)
    print()


asyncio.run(main())
```

Five things to notice:

1. **`AsyncAnthropic`** — the async-flavored client. Same API surface, awaitable methods.
2. **`async def main()` + `asyncio.run(main())`** — async functions can't run on their own. `asyncio.run` starts an event loop, runs the coroutine, and stops the loop when it's done.
3. **`async with client.messages.stream(...)`** — opens a streaming response. The context manager handles connection lifecycle.
4. **`async for text in stream.text_stream`** — yields text chunks as they arrive. The program yields control while waiting for the next chunk.
5. **`print(..., end="", flush=True)`** — print without a newline; flush so each chunk shows up immediately rather than buffered.

Run it:

```bash
uv run main.py
```

The response materializes a few words at a time rather than appearing all at once.

## When you need each

| Use case | Sync `messages.create` | Async streaming |
|---|---|---|
| One-off scripts where you just need the answer | ✓ | overkill |
| Interactive UIs displaying long responses | full-response wait per call | tokens land live |
| Agents that need the full response before deciding what to do | ✓ | doesn't fit — you can't dispatch tools mid-stream |

The agent we'll build doesn't stream — it needs the full response to detect `tool_use` blocks before dispatching tools. But you've now seen one real reason async exists in LLM applications.

## What's missing

- **No tools.** The model can only produce text; it can't act.
- **No loop.** Each call is independent. Nothing carries forward.

## Prompt your coding agent

If you want your coding agent (Claude Code, Cursor, etc.) to write this for you, paste:

```
Create main.py in a project initialized with `uv init`. The project has `anthropic` and `python-dotenv` installed.

Write two versions in main.py — first sync, then async with streaming.

Sync version:
- Load ANTHROPIC_API_KEY from a .env file using python-dotenv
- Use the Anthropic client to make one call to model claude-sonnet-4-5 with max_tokens 1024 and system prompt "You are a helpful assistant."
- Send the user message "What is 2 + 2?"
- Print the text from the first content block of the response

Async streaming version (replaces the sync version when you run it):
- Use AsyncAnthropic instead of Anthropic
- Send a longer user message (e.g., "Write three sentences about agents.") so streaming is visible
- Open a streaming response with `async with client.messages.stream(...) as stream:`
- Iterate text chunks with `async for text in stream.text_stream:` and print each chunk immediately with print(text, end="", flush=True)
- Wrap in `async def main()` and run with `asyncio.run(main())`

Keep both minimal — no tools, no loop, no error handling.
```

The prompt tells your agent *what* to write. The module explains *why* — read it first.

---

**Next:** [Module 3: First tool](../03-first-tool/)
