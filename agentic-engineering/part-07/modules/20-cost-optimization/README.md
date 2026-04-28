# Cost optimization

The agent now has observability (Module 16) and evaluation (Module 19). You can see what the agent does, you can score it, and you can detect regressions when something changes. That makes it safe to optimize — every cost-saving change can be validated against the eval suite to confirm it doesn't degrade quality.

This module covers the four highest-leverage cost levers for an LLM agent: **prompt caching**, **tool output caching**, **batching**, and **model routing**.

## Where the cost goes

Token bills add up across two axes: **input tokens** (what you send) and **output tokens** (what the model generates). Output is roughly 5× more expensive per token, but for a tool-using agent input dominates because every TAO loop iteration sends the full message history.

Look at a typical turn from Module 16's traces:

```
turn (4231ms)
├─ llm.call iteration=0 tokens=4321/87
├─ tool.call read
├─ llm.call iteration=1 tokens=4567/123
├─ tool.call grep
└─ llm.call iteration=2 tokens=4980/45
```

Three LLM calls. Each subsequent call sends the previous one's response *plus* the tool result *plus* everything before. Across iterations, input tokens grow super-linearly. By turn end, the agent has paid for the system prompt + tool schemas + initial user message **multiple times**.

## Prompt caching

Anthropic's prompt caching lets you mark stable prefixes (system prompt, tool schemas, large context blocks) so they're cached server-side and not billed at full rate on subsequent calls within ~5 minutes.

Cache hits are billed at 10% of input rate. For a stable system prompt, that's a 90% input-cost reduction on cached portions.

Mark the cacheable prefix with `cache_control`:

```python
response = await client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    system=[
        {
            "type": "text",
            "text": "You are a helpful coding assistant.",
            "cache_control": {"type": "ephemeral"},
        },
    ],
    messages=messages,
    tools=TOOL_SCHEMAS,
)
```

`cache_control` tells the API: *"this prefix is stable across calls; cache it."* On the second call within 5 minutes with the same prefix, the API serves the cached portion at the discounted rate.

Where to put `cache_control`:

| Boundary | Cache effect |
|---|---|
| End of system prompt | Caches system prompt only |
| End of tool schemas (last tool) | Caches system + all tools |
| End of stable older messages (e.g., a turn boundary you decide is "frozen") | Caches everything up to that point |

For a coding agent: cache through the tool schemas. Tool schemas don't change between calls; system prompt rarely does. Past messages do change (they grow), so don't cache them.

## Tool output caching

A different kind of caching: when the agent calls `read("main.py")` twice in the same session and the file hasn't changed, the second call wastes time and a roundtrip. The fix: cache tool outputs locally by `(name, input)`.

```python
import hashlib
import json

_tool_cache: dict[str, str] = {}


def _cache_key(name: str, input: dict) -> str:
    payload = json.dumps({"name": name, "input": input}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


async def execute_tool(name: str, input: dict, parent_span: str, trace_id: str) -> str:
    tool = TOOLS.get(name)
    if tool is None:
        return f"error: unknown tool {name}"

    # Cache only safe-to-cache tools (read-only, idempotent)
    if name in {"read", "glob", "grep"}:
        key = _cache_key(name, input)
        if key in _tool_cache:
            return _tool_cache[key]

    # ... existing approval, span, dispatch ...
    result = await tool["fn"](**input)
    output = result if isinstance(result, str) else str(result)

    if name in {"read", "glob", "grep"}:
        _tool_cache[_cache_key(name, input)] = output

    return output
```

Two design choices:

- **Only cache idempotent tools.** `read`, `glob`, `grep` produce the same output if the world hasn't changed. `write`, `edit`, `bash` are mutations — caching them would be wrong.
- **Invalidate on mutations.** If `write("main.py", ...)` is called, the cache for `read("main.py")` is now stale. Easy invalidation: clear the entire cache after any mutation tool runs.

```python
if name in {"write", "edit", "bash"}:
    _tool_cache.clear()
```

That's coarse but safe. Production code can do fine-grained invalidation (only clear entries with matching paths).

## Batching

The Anthropic [Message Batches API](https://docs.anthropic.com/en/api/creating-message-batches) processes up to 10,000 requests in a batch at 50% of the standard cost, with results within 24 hours. Useful when:

- You're running large eval suites (Module 19) — submit as a batch instead of N synchronous calls.
- Background jobs that don't need real-time response (summarizing past conversations for memory, generating embeddings, etc.).
- Re-running historical traces against a new model for regression testing.

For interactive agent calls, batching doesn't apply (you need the response immediately to act on `tool_use` blocks). For everything else, it's a 50% discount with a latency trade-off you usually don't care about.

## Model routing

Use a cheaper model for tasks that don't need the strongest reasoning. Coding agents often have low-stakes calls mixed with high-stakes ones:

| Call type | Model |
|---|---|
| Main agent loop (the call that decides tool use) | Strong model — claude-sonnet-4-5 or claude-opus-4-7 |
| Memory summarization (Module 13) | Cheap model — claude-haiku-4-5 |
| LLM-as-judge (Module 19) | Mid-tier model — claude-sonnet-4-5 |
| Trivial classification (intent detection, routing decisions) | Cheap model |

Each "subsidiary" LLM call inside the agent is a candidate for routing to a cheaper tier. The summary call from Module 13 was a generic `messages.create` with no model specification — change it to use `claude-haiku-4-5` and the cost drops 5-10× for a task where quality difference is small.

```python
# Module 13's summarize_turn becomes:
response = await client.messages.create(
    model="claude-haiku-4-5",   # cheap, sufficient for summaries
    max_tokens=200,
    system="You write one-paragraph summaries of agent conversations...",
    messages=[...],
)
```

Run the eval suite (Module 19) before and after to confirm the cheaper model doesn't degrade quality on summary-relevant tests.

## Putting it together

For a representative coding agent session, the cost reduction from this module:

| Lever | Reduction |
|---|---|
| Prompt caching (system + tools) | 50-70% on input tokens |
| Tool output caching (repeat reads) | 10-30% wall time + tokens |
| Cheap model for summaries | 5-10× on summary calls |
| Batching for evals | 50% on eval costs |

Compounding. With prompt caching alone, a coding agent's monthly bill can drop by 50%+ for stable workloads.

## Trade-offs to know

**Cache invalidation.** Both prompt cache (server-side, time-based) and tool cache (local, mutation-based) have invalidation logic. Coarse invalidation (clear everything on writes) is safe but loses cache hits. Fine-grained invalidation is more complex but preserves more hits.

**Cache staleness.** A 5-minute prompt cache window is fine for active sessions, expires faster than you might want. The cache breakpoint matters — put `cache_control` at the most-stable point.

**Model routing complexity.** Each model has different behavior. Cheap models hallucinate more, follow instructions less precisely. The eval suite (Module 19) is the only way to verify a router decision is safe.

**Batching latency.** 24-hour SLA. Acceptable for eval and background jobs; unacceptable for interactive responses. Don't try to use batches for the agent's main loop.

## What this didn't address

- **Compression.** Long context blocks can be summarized before sending — trades inference cost for upfront compute. Useful when the message history dominates token cost.
- **Routing more aggressively.** Some agents have an intent-detection model in front that picks the model per request. Adds complexity but big wins for mixed workloads.
- **Cache analytics.** Production cost optimization needs visibility — what fraction of calls hit the cache, what fraction hit cold? Hook into Module 16's traces to compute these.

## Prompt your coding agent

If you want your coding agent to write this for you, paste:

```
Add four cost-saving optimizations to main.py.

1. Prompt caching: change the `system` parameter to a list of dicts with cache_control on the system text. Pass tool schemas with cache_control on the last tool too if your SDK version supports it. Refer to https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching for the exact shape.

2. Tool output caching:
   - Add a module-level _tool_cache dict.
   - In execute_tool, before calling the tool, compute a cache key from (name, input) — sha256 of canonical JSON.
   - For idempotent tools (read, glob, grep), check cache first; if hit, return cached output.
   - For mutation tools (write, edit, bash), clear the entire cache after the call succeeds.

3. Cheap model routing: for the summarize_turn function from Module 13 (and any LLM-as-judge calls in evals), use model="claude-haiku-4-5" instead of the main model.

4. Batching is documented but not implemented inline (it requires the eval suite from Module 19 to be its primary user). Add a note in the docstring of the eval runner suggesting it as a next step.

Run the eval suite from Module 19 before and after to confirm no regression.
```

The prompt tells your agent *what* to write. The module explains *why* — read it first.

---

**Next:** [Module 21: Latency optimization](../21-latency-optimization/)
