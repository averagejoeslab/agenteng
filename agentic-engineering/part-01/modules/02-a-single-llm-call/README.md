# A single LLM call

This module makes one LLM call. One prompt in, one response out. No loop, no tools, no state between calls.

The code is **async** from the start. One call doesn't need concurrency, but every later module does — the model can request multiple tools in a single response, and we'll want to execute them in parallel. Establishing the async idiom here means no refactor later.

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

## Why async

Python's `async`/`await` lets a single thread wait on I/O without blocking. With one call there's nothing to overlap — it looks like pointless ceremony. Two things make it worth paying that cost now:

- **Parallel tool calls later.** A single LLM response can request multiple tools at once. We'll want to run those in parallel with `asyncio.gather`. That requires the whole call stack up to `main` to be async.
- **Consistency.** Mixing sync and async Python is painful. Pick one early; the choice is async because the production shape (Part 2 and beyond) needs it.

The alternative — starting sync, rewriting to async later — is the refactor we're avoiding.

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
