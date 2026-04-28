# Context as a budget

Module 11 made the conversation persist across restarts. With persistence comes a problem: `messages` grows forever. Every turn appends to it. Eventually the history exceeds the model's context window and the API refuses the request.

This module treats the context window as a **token budget**: count tokens, decide what's allowed in, evict what doesn't fit. The agent stays inside the budget by dropping the oldest content first.

## The shape of the budget

Every API call sends:

- the system prompt
- the tool schemas
- the message history
- a reservation for the response (`max_tokens`)

These all share the model's context window. If their total exceeds the window, the request fails before the model gets a chance to reason.

Working budget for the message history:

```
budget = context_window - max_response_tokens - system_prompt_tokens - tool_schema_tokens
```

For Claude Sonnet 4.5: context window is 200,000 tokens, `max_tokens=1024` reserves response space, the system prompt and six tool schemas take maybe 1,500 tokens combined. That leaves ~197,000 tokens for messages — but you'd want to leave headroom for safety. A practical budget might be 150,000.

## Counting tokens

The Anthropic SDK provides `client.messages.count_tokens(...)` — a free endpoint that returns the input token count for a request *without* running inference. It accepts the same shape as `messages.create`:

```python
count = await client.messages.count_tokens(
    model="claude-sonnet-4-5",
    system=system_prompt,
    messages=messages,
    tools=TOOL_SCHEMAS,
)
print(count.input_tokens)
```

Returns a `MessageTokensCount` with `input_tokens`. That's the exact number of tokens the next `messages.create` would consume from the context window.

(For local approximation without an API call you could use a tokenizer library, but `count_tokens` is what production code uses — accurate, free, no model dependency.)

## Eviction strategy: drop the oldest user-turn

The naive eviction — *"drop messages from the front until you're under budget"* — is wrong. Messages aren't independent. An assistant message containing a `tool_use` block requires its corresponding `tool_result` block in the next user message. Drop one without the other and the API rejects the request.

The right unit to drop is a **user turn**: the user message + everything generated in response, up through the assistant's final text-only message. That's a self-contained exchange the API will accept removing as a whole.

Algorithmically: walk forward from the start, find the first index where the previous assistant message had no `tool_use` blocks (a clean turn boundary). Truncate before that index.

```python
def find_safe_truncation_point(messages: list, drop_n: int = 1) -> int:
    """
    Return an index i such that messages[i:] is a valid conversation —
    no dangling tool_use blocks, starts with a user text message.
    Drops `drop_n` complete user turns from the front.
    """
    boundaries = []
    for i, msg in enumerate(messages):
        if msg["role"] != "user":
            continue
        # User messages that aren't tool_result responses are turn starts
        content = msg["content"]
        if isinstance(content, str):
            boundaries.append(i)
        elif not any(_is_tool_result(b) for b in content):
            boundaries.append(i)

    if drop_n >= len(boundaries):
        return len(boundaries) and boundaries[-1] or 0
    return boundaries[drop_n]


def _is_tool_result(block) -> bool:
    if isinstance(block, dict):
        return block.get("type") == "tool_result"
    return getattr(block, "type", None) == "tool_result"
```

`boundaries` is the list of indexes where the user starts a new turn (their content is text, not a `tool_result`). The first boundary is index 0. Dropping the first turn means truncating to `boundaries[1]`. Dropping two means `boundaries[2]`.

## The trim loop

Trimming until under budget:

```python
async def trim_to_budget(messages: list, budget: int) -> list:
    while True:
        count = await client.messages.count_tokens(
            model="claude-sonnet-4-5",
            system="You are a helpful coding assistant.",
            messages=messages,
            tools=TOOL_SCHEMAS,
        )
        if count.input_tokens <= budget or len(messages) <= 1:
            return messages
        truncate_at = find_safe_truncation_point(messages, drop_n=1)
        if truncate_at == 0:
            # Can't drop further without breaking the conversation
            return messages
        messages = messages[truncate_at:]
```

Loop:
1. Count current tokens.
2. If under budget or only one turn left, return.
3. Otherwise drop the oldest user turn and try again.

The `count_tokens` call is one API round-trip per trim iteration. In practice you'll trim infrequently — only when conversations grow large — so the cost is minor. If it becomes a hot path, cache locally.

## Wiring into the agent

Two changes to the Module 11 coding-agent:

1. **Define a budget.** A constant near the top:
   ```python
   CONTEXT_BUDGET = 150_000   # tokens
   ```

2. **Call `trim_to_budget` at the start of each user turn**, after appending the user message and before the inner TAO loop:
   ```python
   messages.append({"role": "user", "content": user_input})
   messages = await trim_to_budget(messages, CONTEXT_BUDGET)

   while True:  # inner TAO loop unchanged
       ...
   ```

Trimming once per outer turn (not per LLM call) is the right granularity — the budget rarely shifts mid-turn, and we already established mid-turn is unsafe to truncate.

## Running it

For most conversations the budget is never reached and the trim is a no-op. To exercise the eviction, set the budget very low temporarily (`CONTEXT_BUDGET = 5_000` for testing) and have a few-turn conversation that includes file reads. After a few turns you'll see the saved state stay roughly stable in size — the oldest exchanges dropping as new ones come in.

You can verify by inspecting `~/.coding-agent/messages.json` after each turn.

## Compaction as the next refinement

Eviction is destructive — dropped content is gone. **Compaction** (or **summarization**) is the alternative: replace the dropped exchanges with a short summary the model can still refer to. *"In an earlier conversation, the user established X, Y, Z."*

Compaction preserves more information per token but adds:

- **Cost.** Generating the summary is another LLM call.
- **Latency.** Trimming gets slower.
- **Quality risk.** The summary loses fidelity. The agent might miss specifics it would have remembered with the raw exchange.

For a curriculum agent, eviction is the simpler and adequate version. Production agents like Claude Code and Cursor compact on a schedule (e.g., when context exceeds 50% of the window) using a summarization prompt — not implemented here but the integration point is clear: replace `messages = messages[truncate_at:]` with `messages = await summarize_and_replace(messages, truncate_at)`.

## Trade-offs to know

**Budget vs. window.** The budget is a *target*; the window is the *limit*. Set the budget well below the window so you have headroom for the response (`max_tokens` is reserved separately) plus safety margin.

**`count_tokens` is one API call per trim iteration.** Acceptable for the low-frequency trim we do here. If you trim per-message instead of per-turn, the cost adds up.

**Tool schemas count.** Six tools' worth of schemas is roughly 1,500 tokens. If the toolkit grows, the budget shrinks accordingly.

**Eviction loses history.** The agent literally cannot reason about evicted exchanges. If you need long-term memory across many sessions, you need a different mechanism — the next module's job.

## What this didn't address

- **Compaction / summarization.** Same algorithm, just replaces dropped content with a generated summary instead of nothing.
- **Long-term recall.** Evicted exchanges are gone forever. The agent can't say *"what was that thing the user mentioned three weeks ago?"* unless we save and search past sessions semantically.
- **Adaptive budget.** This module uses a fixed constant. A smarter agent might track typical response sizes and adjust the budget dynamically.

## Prompt your coding agent

If you want your coding agent to write this for you, paste:

```
Add token-budget management to main.py.

1. Define CONTEXT_BUDGET = 150_000 (a constant near the top).

2. Add a helper `find_safe_truncation_point(messages, drop_n=1)` that returns an index such that messages[i:] is API-valid (no dangling tool_use). Walk through messages and collect boundaries — indices where a user message starts a fresh turn (content is a string, OR content is a list with no tool_result blocks). Return boundaries[drop_n] or len(messages) if we'd drop everything.

3. Add `async def trim_to_budget(messages, budget)`:
   - Call client.messages.count_tokens(model=..., system=..., messages=messages, tools=TOOL_SCHEMAS) and read .input_tokens
   - If under budget or len(messages) <= 1, return as-is
   - Otherwise truncate at find_safe_truncation_point(messages, 1) and loop

4. In main(), after appending the user message and before the inner TAO loop, call:
   messages = await trim_to_budget(messages, CONTEXT_BUDGET)

5. Don't trim mid-TAO-loop — only at user-turn boundaries.

Use the SDK's count_tokens method (free, no inference) — not a local tokenizer.
```

The prompt tells your agent *what* to write. The module explains *why* — read it first.

---

**Next:** [Module 13: Semantic recall](../13-semantic-recall/)
