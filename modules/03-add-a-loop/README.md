# Add a loop

Module 2 made one LLM call. The model answered, the program ended. Most useful interactions are conversations — questions, follow-ups, clarifications. The fix is a loop around the API call so the program can keep talking.

By the end you have a chatbot. Not an agent yet — the model can only emit text, not act. Tools come next.

## Stateless API, stateful loop

The Messages API is stateless. The server doesn't remember anything between calls. Every `messages.create` is independent — the only context the model has is the `messages` list you send it.

So the *program* keeps the state. You maintain a list of `{role, content}` turns; you append the user's input before the call and the assistant's reply after; you send the whole list every time.

This is the trick that makes a multi-turn conversation possible without any server-side session — the conversation lives in your variable.

## The chatbot

A `while True` around the API call, with a list that grows on each turn:

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

    assistant_text = response.content[0].text
    messages.append({"role": "assistant", "content": assistant_text})
    print(assistant_text)
```

Two things to notice:

1. **Every turn sends the full history.** No server-side state — `messages` is the entire conversation each call.
2. **Both roles get appended.** User input goes in before the call; the assistant's reply goes in after. The next turn sees both.

## Run it

The runnable version is [`examples/chatbot.py`](../../examples/chatbot.py).

```bash
cd examples
uv run chatbot.py
```

```
❯ My name is Sam.
Nice to meet you, Sam.
❯ What's my name?
Your name is Sam.
❯ /q
```

Quit the program and the conversation is gone — `messages` was just an in-memory list. Persistence is Module 5's problem.

## Why this isn't an agent

The chatbot can talk forever, but it can't *do* anything. It can describe how to read a file, explain what `git status` would output, propose what a config change might look like — but it cannot read, run, or write. It only emits text.

To act, the model needs **tools**: functions your code is willing to run on the model's behalf. That's the next module — and it's the moment the chatbot becomes an agent.

---

**Next:** [Module 4: Add tools](../04-add-tools/)
