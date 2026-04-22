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

# Add the Anthropic Python SDK
uv add anthropic

# Store your API key in a .env file
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env
```

## The code

Create `main.py`:

```python
import os
from anthropic import Anthropic

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

- **No loop.** Each call is independent. Nothing carries forward.
- **No tools.** The model can only produce text; it can't act.

Module 3 wraps this call in the loop structure so it's ready for tools.

---

**Next:** [Module 3: The TAO loop](../03-the-tao-loop/)
