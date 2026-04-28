# Approval gates and loop bounds

Module 14 made `bash` safer by containerizing it. The other destructive tools — `write`, `edit` — still run on the host with full filesystem access. And the agent itself can spin in a tight loop calling tools forever if something goes wrong with its reasoning.

This module wires three guards into the executor (Module 10): **approval gates** so destructive actions need human confirmation, **loop bounds** so the agent can't run unbounded, and **retry with backoff** so transient API failures don't crash the loop.

## Approval gates

Some tools are dangerous in ways the model can't reliably reason about — overwriting a file, deleting data, sending an email. The conservative pattern: before any tool flagged as "dangerous" runs, prompt the human to confirm.

The executor (Module 10) is the one place this hooks in. Every tool dispatch passes through `execute_tool`. We add an approval check there.

```python
DANGEROUS_TOOLS = {"write", "edit", "bash"}


async def request_approval(name: str, input: dict) -> bool:
    print(f"\n⚠ Tool '{name}' wants to run with: {input}")
    answer = input("approve? [y/N] ").strip().lower()
    return answer in ("y", "yes")


async def execute_tool(name: str, input: dict) -> str:
    tool = TOOLS.get(name)
    if tool is None:
        return f"error: unknown tool {name}"

    if name in DANGEROUS_TOOLS:
        if not await request_approval(name, input):
            return "error: user denied approval"

    try:
        result = await tool["fn"](**input)
        return result if isinstance(result, str) else str(result)
    except Exception as e:
        return f"error: {e}"
```

Three things to notice:

1. **Approval lives in the executor, not in the tools.** Adding a new dangerous tool is a one-line registry change (add to `DANGEROUS_TOOLS`).
2. **Denial returns an error string** the model can read. The agent doesn't crash — it sees `"error: user denied approval"` and decides what to do (often it asks the user why, or proposes an alternative).
3. **The approval prompt collides with `asyncio.gather`.** If the model emits three dangerous tool calls in parallel, they'd all `print` and `input()` simultaneously, garbling the terminal. Either serialize dangerous calls (lose parallelism for them) or batch the approvals (one "approve all three?" prompt). We'll serialize for simplicity.

To serialize: if any tool in the batch is dangerous, dispatch them sequentially instead of via `gather`:

```python
def has_dangerous(tool_calls) -> bool:
    return any(c.name in DANGEROUS_TOOLS for c in tool_calls)


# In the TAO loop:
if has_dangerous(tool_calls):
    outputs = []
    for c in tool_calls:
        outputs.append(await execute_tool(c.name, c.input))
else:
    outputs = await asyncio.gather(*(execute_tool(c.name, c.input) for c in tool_calls))
```

In production you'd be smarter about batching approvals — show the human all the proposed dangerous actions at once, get one yes/no. The principle is the same: approval is an executor-level concern, not a per-tool concern.

## Loop bounds

The TAO loop iterates as long as the model emits `tool_use`. Most of the time that's bounded by the task — the model finishes when it has the answer. Sometimes it's not. A confused model can loop calling the same tool with the same arguments, never converging. A misaligned model can deliberately loop. Either way, you need a hard limit.

The simplest bound: cap iterations of the inner loop.

```python
MAX_ITERATIONS = 30


async def main():
    messages = load_messages()
    while True:
        user_input = input("❯ ")
        if user_input.lower() in ("/q", "exit"):
            break
        messages.append({"role": "user", "content": user_input})

        # The TAO loop with a bound
        for iteration in range(MAX_ITERATIONS):
            response = await client.messages.create(...)
            messages.append({"role": "assistant", "content": response.content})
            for block in response.content:
                if block.type == "text":
                    print(block.text)
            tool_calls = [b for b in response.content if b.type == "tool_use"]
            if not tool_calls:
                break
            # ... dispatch and append tool_results ...
        else:
            # The for/else clause runs if the loop didn't break — i.e., we hit the limit.
            print(f"\n⚠ Reached {MAX_ITERATIONS} iterations without completion. Aborting turn.")
            messages.append({
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": ..., "content": "error: max iterations reached"}]
                # Or just append a synthetic stop signal — implementation detail
            })

        save_messages(messages)
```

Trade-offs:

- **Too low:** legitimate multi-step tasks fail. Reading a large codebase across many files might genuinely need 20+ tool calls.
- **Too high:** a runaway loop wastes tokens and money before being stopped.
- **30** is a reasonable starting point for a coding agent. Tune based on task profiles you observe in production traces (Module 16).

## Retry and backoff

The Anthropic API can fail transiently — rate limits, network blips, internal errors. Default behavior is the request raises an exception, which crashes the agent loop. Production agents wrap API calls with retry-on-transient-error and exponential backoff.

The Anthropic SDK has built-in retries (default 2 attempts). Configure them at the client:

```python
from anthropic import AsyncAnthropic

client = AsyncAnthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    max_retries=4,           # Retry up to 4 times on retriable errors
    timeout=60.0,            # Per-request timeout in seconds
)
```

The SDK retries on:
- Network errors
- HTTP 408, 409, 429 (rate limit), 5xx
- With exponential backoff between attempts

This handles ~95% of transient failure cases. For the ones the SDK doesn't catch — extreme rate limits, model deprecations, malformed schemas — you'd add an outer try/except around the `messages.create` call:

```python
try:
    response = await client.messages.create(...)
except APIError as e:
    print(f"API error: {e}")
    messages.pop()  # Drop the user message we just added
    continue        # Back to the REPL
```

But for normal use, the SDK's defaults are correct.

## Trade-offs to know

**Approval friction.** Every approval prompt interrupts the agent's flow. Set it too aggressively and the user gets prompted constantly; set it too loose and dangerous things slip through. Production agents often graduate trust: first time a tool runs in a session, ask. Subsequent times in the same session, allow. Reset trust on session restart. Or scope by file path: prompt for writes outside the project, allow inside.

**Loop bounds vs. task completion.** Hard caps risk truncating legitimate work. Better signals: detect *no progress* (same tool, same args, same result twice in a row) and stop on stall rather than count. We're using count for simplicity; production should consider stall detection.

**Approval and parallel dispatch.** As noted, dangerous calls force sequential dispatch. This loses Module 6's parallelism for those turns. Acceptable given that dangerous tools (write, edit, bash) tend to run one at a time anyway.

**Retry policy mismatches.** The SDK's defaults retry rate-limit errors with backoff, which is usually right. But for an interactive user-facing agent, waiting 30 seconds to retry feels broken. Consider a short retry budget for foreground calls, longer for background work.

## What this didn't address

- **Persisting trust across sessions.** Approvals are forgotten when the REPL restarts. A real safety system would persist trust scopes (user-confirmed: "this agent can write under `~/projects/foo` without asking").
- **Stall detection.** Loop bounds catch runaway count, not runaway behavior. Detecting same-tool-same-args-same-result loops is more nuanced and tied to observability (Module 16).
- **Output filtering.** Tool results may contain secrets (env vars, API responses). The current executor returns them verbatim to the model, which then puts them in messages and possibly persists to disk. PII/secret detection would happen here, in the executor, before results flow into messages.

## Prompt your coding agent

If you want your coding agent to write this for you, paste:

```
Add three safety guards to main.py: approval gates, loop bounds, and retry/backoff.

1. Approval gates:
   - Define DANGEROUS_TOOLS = {"write", "edit", "bash"} (set).
   - Add `async def request_approval(name, input)` that prints a warning, prompts the user with input("approve? [y/N] "), returns True only on "y" or "yes".
   - In execute_tool, after the unknown-tool check and before calling tool["fn"], if name in DANGEROUS_TOOLS, call request_approval. If False, return "error: user denied approval".
   - Add a `has_dangerous(tool_calls)` helper. In the TAO loop, if has_dangerous, dispatch sequentially (a for loop building outputs) instead of asyncio.gather. Otherwise keep gather.

2. Loop bounds:
   - Add MAX_ITERATIONS = 30 constant.
   - Replace the inner `while True` with `for iteration in range(MAX_ITERATIONS):`.
   - Use the for/else pattern: the else clause runs if the loop didn't break, prints a warning, and appends a synthetic stop so messages stays API-valid.

3. Retry/backoff:
   - Update the AsyncAnthropic client to pass max_retries=4 and timeout=60.0. The SDK handles transient errors with exponential backoff automatically.

Don't change tools, registry, or memory/recall logic.
```

The prompt tells your agent *what* to write. The module explains *why* — read it first.

---

**Next:** [Module 16: Structured tracing](../../../part-05/modules/16-structured-tracing/)
