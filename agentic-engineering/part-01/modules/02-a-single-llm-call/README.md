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

## The code

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

1. The SDK sent an HTTP POST to `https://api.anthropic.com/v1/messages`
2. The request body contained `model`, `max_tokens`, `system`, and `messages`
3. The API returned a JSON response with a `content` array
4. `response.content[0].text` extracted the text from the first block

That's the whole mechanic. The model saw the user message, generated a response, sent it back.

## What's missing

- **No tools.** The model can only produce text; it can't act.
- **No loop.** Each call is independent. Nothing carries forward.

## Prompt your coding agent

If you want your coding agent (Claude Code, Cursor, etc.) to write this for you, paste:

```
Create main.py in a project initialized with `uv init`. The project has `anthropic` and `python-dotenv` installed. In main.py:

- Load ANTHROPIC_API_KEY from a .env file using python-dotenv
- Use the Anthropic client to make one call to model claude-sonnet-4-5 with max_tokens 1024 and system prompt "You are a helpful assistant."
- Send the user message "What is 2 + 2?"
- Print the text from the first content block of the response

Keep it minimal — sync, no loop, no tools, no error handling.
```

The prompt tells your agent *what* to write. The module explains *why* — read it first.

---

**Next:** [Module 3: Multi-turn conversation](../03-multi-turn-conversation/)
