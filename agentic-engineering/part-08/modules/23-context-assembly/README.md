# Context assembly

Module 22 covered the system prompt — what you tell the model about *itself*. This module covers what you put in *the rest of the context* — recalled memories, recent turns, tool schemas, tool results — and how to assemble them coherently within the token budget.

Context assembly is where many earlier modules come together. Module 11 gave persistence; Module 12 gave the budget; Module 13 gave semantic recall; Module 22 gave the system prompt; this module is the strategy that decides, on every turn, exactly what gets sent.

## What's actually sent

A complete API call to Claude has roughly this shape:

```
{
  system: <string or list of cacheable blocks>,
  tools: <array of tool schemas>,
  messages: [
    {role: "user" | "assistant", content: ...},
    ...
  ],
  max_tokens: ...,
}
```

Three slots: system, tools, messages. Each slot has a token cost; together they fit within the model's context window minus `max_tokens` reservation.

The strategy question for each slot:

| Slot | Stable across turns? | Source |
|---|---|---|
| `system` | Yes (Module 22) | The prompt + recalled memories (Module 13) prepended |
| `tools` | Yes (Module 8 registry) | Generated once at startup |
| `messages` | No — grows every turn | Module 11 persistence + Module 12 eviction |

Module 13 changed the system slot from "constant string" to "constant + recalled memories." Module 12 changed the messages slot from "everything" to "everything within budget." Both were context-assembly decisions. This module formalizes them.

## The assembly function

Think of context assembly as a function that runs at the start of every LLM call:

```
assemble(user_input, conversation_state) → {system, tools, messages}
```

Inputs:
- the new user message (or the in-flight tool_result)
- the conversation state (existing messages, recall store, etc.)

Outputs:
- the three slots ready for `messages.create`

The function makes choices like:
- Which past memories to recall and inject?
- Where to put recalled memories — in system, or as a synthetic user message?
- How much of the message history to send vs. evict?
- When to compact vs. evict?
- Should anything be prepended to the user's current input?

Concrete:

```python
async def assemble(messages: list, recall_entries: list, user_input: str) -> dict:
    # 1. Recall relevant memories from past sessions
    recalled = recall(user_input, recall_entries, k=3, threshold=0.3)

    # 2. Build the system prompt — base + recalled context
    system = [
        {"type": "text", "text": BASE_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
    ]
    if recalled:
        memory_block = "\n\n".join(f"- {s}" for s in recalled)
        system.append({
            "type": "text",
            "text": f"## Recalled context from past conversations\n\n{memory_block}",
        })

    # 3. Trim message history to budget
    trimmed = await trim_to_budget(messages, CONTEXT_BUDGET)

    return {
        "system": system,
        "tools": TOOL_SCHEMAS,
        "messages": trimmed,
    }
```

This function is the single pull-everything-together that earlier modules implicitly built up to. Centralize it, and every cross-cutting context concern has one place to live.

## Where to put recalled memories

Module 13 injected recalled snippets into the system prompt. That's one of three options:

| Strategy | Pros | Cons |
|---|---|---|
| **In system prompt** (current) | Cached at server side; clear that this is "background context" | Less visible to the model than the user's current message |
| **As prepended synthetic user message** | The model treats it as fresh context; high salience | Counts against message budget; not cached |
| **Inline in the user message** | "User asks X. Background: ..." | Mingles user intent with system context — confusing |

For a memory-style use case (recall past sessions), **system prompt** is the right default. For a RAG-style use case (retrieve documents at search time), **prepended user message** is often better because the retrieved chunks are salient to *this* turn, not background context.

You can do both: stable per-session memories in system, per-turn retrieved chunks in messages.

## Token budget allocation

The total budget gets partitioned across slots. A practical default for a coding agent on Claude Sonnet 4.5 (200k context):

| Slot | Budget |
|---|---|
| System prompt | 2,000 tokens (well-designed system from Module 22) |
| Recalled memories (in system) | 3,000 tokens (top-3 summaries, ~1000 each) |
| Tool schemas | 1,500 tokens (six tools w/ descriptions) |
| Reserved for response (`max_tokens`) | 1,024 tokens |
| Safety margin | 5,000 tokens |
| Available for messages | ~187,000 tokens |

The messages budget is what Module 12's eviction targets. Reduce it if you want to leave more headroom for long responses, or if you're using a smaller model with a smaller window.

## When to assemble

Two pragmatic rules:

**Once per outer turn.** The user types something; assemble runs; the inner TAO loop runs all subsequent LLM calls with that assembled context plus the loop's own appended messages. Don't re-recall memories mid-loop — once is enough.

**Re-trim mid-loop only when needed.** If the inner TAO loop runs many iterations and accumulated tool results push back over budget, trim again. But the recalled memories don't change mid-turn.

```python
async def main():
    while True:
        user_input = input("❯ ")
        if user_input.lower() in ("/q", "exit"):
            break
        messages.append({"role": "user", "content": user_input})

        # Assemble once per outer turn
        ctx = await assemble(messages, recall_entries, user_input)
        messages = ctx["messages"]   # apply trim

        for iteration in range(MAX_ITERATIONS):
            response = await client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=1024,
                system=ctx["system"],
                tools=ctx["tools"],
                messages=messages,
            )
            messages.append({"role": "assistant", "content": response.content})
            # ... existing dispatch logic ...
            tool_calls = [b for b in response.content if b.type == "tool_use"]
            if not tool_calls:
                break
            # ... tool dispatch ...

            # Mid-loop budget check
            if (await client.messages.count_tokens(...)).input_tokens > CONTEXT_BUDGET:
                messages = await trim_to_budget(messages, CONTEXT_BUDGET)

        save_messages(messages)
        # ... summarize and add to recall ...
```

## Closing the loop with eval

Each context-assembly choice is a hypothesis: *"recalling 3 past memories is better than 5"*; *"system prompt with examples beats system without"*; *"recalled memories as user messages beats system slot"*. The Module 19 eval suite is how you decide.

Run the suite, change one assembly variable, run again. If pass rate moves materially, the change is real. If it doesn't, the variable wasn't load-bearing — pick whichever has lower token cost (Module 20's optimizations apply here too).

## Trade-offs to know

**Recall threshold tuning.** Lower threshold = more memories recalled = more tokens spent + potentially more noise. Higher threshold = fewer memories = potentially missing relevant context. The eval suite tells you which side errs better for your tasks.

**Budget allocation rigidity.** Fixed budgets per slot are simple but can't adapt to varying turn shapes. Some turns need lots of recall (the user's referencing old work); some need none (a fresh task). Smarter assembly tracks per-turn need and reallocates dynamically.

**Cache invalidation from assembly.** If recalled memories are in the system prompt, every turn with different recall results invalidates the prompt cache. You pay full rate. Solutions: cache at the boundary *before* recalled memories (so base system + tools cache, recall doesn't); or accept the cache miss as the price of dynamic context.

**Compounding choices.** Each module added one assembly concern (memory, budget, recall, prompt). Together they're a complex policy. Periodically simplify: are all the levers actually contributing? The eval suite tells you.

## What this completes

This is the final module of the curriculum. The reader has built:

- An agent (LLM + loop + tools) that's runnable, async, and production-shaped
- A multi-tool toolkit with proper engineering (registry, executor, error handling)
- Memory across sessions (persistence, budget management, semantic recall)
- Safety guards (sandboxing, approval, loop bounds)
- Observability (structured tracing, replay, tooling integration)
- Evaluation (test cases, scoring, regression tracking)
- Cost and latency optimizations (prompt caching, tool caching, async threading, streaming)
- Prompt design and context assembly (the iterative loop with eval feedback)

That covers the agentic-engineering discipline end to end. Beyond this curriculum: real-world agent design has open problems — multi-agent composition, long-horizon planning, robust self-correction, alignment at scale — but the foundation is here. With this in place, advanced topics are extensions, not prerequisites.

---

**End of curriculum.**
