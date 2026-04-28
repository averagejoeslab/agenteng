# Multi-turn conversation

Module 2 made one LLM call. The model saw a prompt, returned a response, and the script ended. Real interactive use needs more — the user asks something, then asks a follow-up that depends on what was just said. This module wraps the LLM call in a REPL and maintains conversation history across turns.

What you'll build is a **chatbot**: terminal in, model out, repeat. No tools, no autonomous control flow. Just turn-based conversation where the model remembers what was said before.

## The REPL

A REPL — read, evaluate, print, loop — is the simplest environment for an interactive program. In Python it's a `while True` over `input()`:

```python
while True:
    user_input = input("❯ ")
    if user_input.lower() in ("/q", "exit"):
        break
    # call the model, print response
```

`/q` or `exit` lets the user end the session.

## Maintaining conversation state

The Anthropic Messages API is stateless — each call is independent. To give the model conversational context, you send the entire prior conversation in the `messages` array on every call.

The pattern:

1. User types something. Append `{"role": "user", "content": user_input}` to `messages`.
2. Call the model with the full `messages` list.
3. Append the model's response to `messages`.
4. Print the text the model produced.
5. Repeat.

If the user's next question is *"what did I just ask?"*, the model can answer because the prior turn is still in `messages`.

## The code

```python
import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

messages = []

while True:
    user_input = input("❯ ")
    if user_input.lower() in ("/q", "exit"):
        break

    messages.append({"role": "user", "content": user_input})

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system="You are a helpful assistant.",
        messages=messages,
    )
    messages.append({"role": "assistant", "content": response.content})

    for block in response.content:
        if block.type == "text":
            print(block.text)
```

Three things to notice:

1. **`messages` lives outside the `while True`.** That's what carries history across turns. If `messages` were reset every iteration, the model would lose all context.
2. **One LLM call per user turn.** Read input, call model once, print, loop.
3. **Sync call.** Same `client.messages.create(...)` pattern from Module 2 — nothing fancy yet.

## Running it

```bash
uv run main.py
```

A session:

```
❯ What is 2 + 2?
4
❯ What did I just ask?
You asked what 2 plus 2 equals.
❯ Add one to that.
5
❯ /q
```

The model remembers the previous turn because `messages` accumulated it.

## Why this is a chatbot, not an agent

Look back at the code. The model produces text; your code prints it. The model has no way to **act** — no tools, no external effects. It can answer questions from its training, but it can't read a file, run a command, or look something up.

A chatbot per the [taxonomy](../../../../README.md#types-of-agentic-systems) sits outside the agent/workflow distinction entirely — it doesn't even have tools. It's an LLM in a loop with conversation memory.

## What's missing

- **No tools.** The model can talk; it can't act.
- **No autonomy over control flow.** Every turn is exactly one LLM call. No iteration, no decision about whether to call another tool.

## Prompt your coding agent

If you want your coding agent to write this for you, paste:

```
Extend main.py from the previous module to wrap the LLM call in a multi-turn REPL chatbot.

1. Replace the single hardcoded message with a `while True` REPL:
   - Read user input with `input("❯ ")`
   - Break if "/q" or "exit"
   - Otherwise append it as a user message
2. Maintain a `messages` list outside the loop so conversation history persists across turns.
3. After each LLM call:
   - Append the assistant's response to messages
   - Print any text blocks the model produced
4. Use a system prompt of "You are a helpful assistant."
5. Keep it sync — no async, no tools, no inner loop.
```

The prompt tells your agent *what* to write. The module explains *why* — read it first.

---

**Next:** [Module 4: First tool](../04-first-tool/)
