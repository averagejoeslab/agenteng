# A single LLM call

This module makes one LLM call. One prompt in, one response out. No loop, no tools, no state between calls.

The code uses **cooperative concurrency** from the start. One call doesn't need it, but every later module does: the model can request multiple tools in a single response, and we'll want to execute them in parallel. Establishing that shape here means no refactor later. Python expresses cooperative concurrency with `async`/`await` + `asyncio.run`; other languages have the same idea under different names.

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

## The code

Create `main.py`:

```python
import os
import asyncio
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()

client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


async def main():
    response = await client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system="You are a helpful assistant.",
        messages=[
            {"role": "user", "content": "What is 2 + 2?"}
        ],
    )
    print(response.content[0].text)


asyncio.run(main())
```

## Running it

```bash
uv run main.py
```

Expected output:

```
4
```

(Exact phrasing varies — models are non-deterministic.)

## What just happened

1. `asyncio.run(main())` started an event loop and ran the `main` coroutine
2. The SDK sent an HTTP POST to `https://api.anthropic.com/v1/messages`
3. The request body contained `model`, `max_tokens`, `system`, and `messages`
4. The API returned a JSON response with a `content` array
5. `response.content[0].text` extracted the text from the first block

That's the whole mechanic. The model saw the user message, generated a response, sent it back.

## Why concurrent I/O

An agent spends most of its wall time waiting — on the model API, on file reads, on shell commands. Each turn involves:

- One HTTP call to the LLM (hundreds of milliseconds)
- Zero-to-N tool calls, often independent and I/O-bound

Doing that sequentially wastes the wait. The fix is **cooperative concurrency**: a runtime that suspends one pending operation and runs another on the same thread. Every mainstream language has a primitive for it — Python's `async`/`await`, JavaScript's `async`/`await` + `Promise`, Go's goroutines, Rust's `Future`s. They differ in syntax; the shape is the same: a function declares it can yield, the runtime resumes it when its I/O completes.

With one LLM call and no tools there's nothing to overlap — this module looks like pointless ceremony. The reason to pay that cost now is that the *call-stack shape* has to match where we're going. A function that will eventually want to dispatch multiple tool calls in parallel must be a coroutine all the way up. Starting sync and rewriting later is the refactor we're avoiding.

In Python terms: every function from here on is `async def`, and the program's entry point is `asyncio.run(main())`.

## What's missing

- **No loop.** Each call is independent. Nothing carries forward.
- **No tools.** The model can only produce text; it can't act.

Module 3 wraps this call in the loop structure so it's ready for tools.

## Prompt your coding agent

If you want your coding agent (Claude Code, Cursor, etc.) to write this for you, paste:

```
Create main.py in a project initialized with `uv init`. The project has `anthropic` and `python-dotenv` installed. In main.py:

- Load ANTHROPIC_API_KEY from a .env file using python-dotenv
- Use the AsyncAnthropic client to make one call to model claude-sonnet-4-5 with max_tokens 1024 and system prompt "You are a helpful assistant."
- Send the user message "What is 2 + 2?"
- Print the text from the first content block of the response
- Wrap the call in `async def main()` and run it with `asyncio.run(main())`

Keep it minimal — no loop, no tools, no error handling.
```

The prompt tells your agent *what* to write. The module explains *why* — read it first.

---

**Next:** [Module 3: The TAO loop](../03-the-tao-loop/)
