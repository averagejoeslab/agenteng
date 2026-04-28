# Structured tracing

You can't fix what you can't see. The agent built through Part 4 works, but its decisions are invisible — once a turn completes you can't easily ask *"why did the model call `read` on that file? What did `grep` return that made it switch to `edit`? How long did each step take?"*

This module emits **structured traces**: a JSON record of every LLM call, every tool call, every state transition the agent makes. Each turn becomes one trace; each operation inside the turn is a span. The trace is the foundation for debugging, replay (Module 17), evaluation (Modules 18-19), and cost/latency profiling (Modules 20-21).

## What a trace contains

For each turn, we want to capture:

- **The user input** that started the turn
- **Each LLM call** — its messages, the system prompt, tools sent, response received, token counts, latency
- **Each tool call** — name, input, output, duration, error if any
- **The final response** the user sees
- **Total tokens, total wall time** for the turn

Each event (LLM call, tool call) is a **span**: a record with a start time, end time, and structured attributes. A turn is a tree of spans rooted at the user input.

## The schema

A pragmatic schema that's compatible with OpenTelemetry conventions but kept simple:

```python
{
    "trace_id": "01HX9...",        # one per turn
    "span_id": "01HX9...",         # one per event
    "parent_span_id": "01HX9...",  # null for root, otherwise the parent's span_id
    "name": "llm.call" | "tool.call" | "turn",
    "start_time": "2026-04-27T18:42:11.234Z",
    "end_time": "2026-04-27T18:42:13.412Z",
    "duration_ms": 2178,
    "attributes": {
        # Free-form per-span. Common keys:
        "model": "claude-sonnet-4-5",
        "input_tokens": 4321,
        "output_tokens": 87,
        "tool.name": "read",
        "tool.input": {...},
        "tool.output": "...",
        "error": "...",
    },
}
```

One span per event. Spans link via `parent_span_id` to form a tree. The whole turn shares one `trace_id`.

## Where traces go

A JSONL file per session — append-only, easy to grep, easy to feed into other tools.

```python
TRACE_FILE = Path.home() / ".coding-agent" / "traces.jsonl"


def write_span(span: dict) -> None:
    TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TRACE_FILE, "a") as f:
        f.write(json.dumps(span, default=str) + "\n")
```

JSONL because each line is a complete record. Append-only because we never edit — write and forget. Production agents would emit to OpenTelemetry collectors or platform SDKs (Phoenix, Helicone, Langfuse); the JSONL local file is the simplest correct version.

## Instrumentation: a span context manager

A small helper that emits a span when its context exits:

```python
import time
import secrets
from contextlib import contextmanager
from datetime import datetime, timezone


def _new_id() -> str:
    return secrets.token_hex(8)


@contextmanager
def span(name: str, parent: str | None = None, trace_id: str | None = None, **attributes):
    span_id = _new_id()
    trace_id = trace_id or _new_id()
    start = datetime.now(timezone.utc)
    t0 = time.perf_counter()

    rec = {
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent,
        "name": name,
        "start_time": start.isoformat(),
        "attributes": dict(attributes),
    }
    try:
        yield rec
    except Exception as e:
        rec["attributes"]["error"] = str(e)
        raise
    finally:
        rec["end_time"] = datetime.now(timezone.utc).isoformat()
        rec["duration_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        write_span(rec)
```

Usage:

```python
with span("turn", attributes={"user_input": user_input}) as turn_rec:
    trace_id = turn_rec["trace_id"]
    parent = turn_rec["span_id"]

    with span("llm.call", parent=parent, trace_id=trace_id) as llm_rec:
        response = await client.messages.create(...)
        llm_rec["attributes"].update({
            "model": "claude-sonnet-4-5",
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        })
```

The context manager handles ID generation, timing, error capture, and emission. The function body just adds attributes specific to that span.

## Wiring into the executor

Module 10 made the executor the home for cross-cutting concerns. This is one. Wrap every tool invocation in a span:

```python
async def execute_tool(name: str, input: dict, parent_span: str, trace_id: str) -> str:
    tool = TOOLS.get(name)
    if tool is None:
        return f"error: unknown tool {name}"

    with span("tool.call", parent=parent_span, trace_id=trace_id,
              **{"tool.name": name, "tool.input": input}) as rec:
        if name in DANGEROUS_TOOLS:
            if not await request_approval(name, input):
                rec["attributes"]["error"] = "user denied approval"
                return "error: user denied approval"
        try:
            result = await tool["fn"](**input)
            output = result if isinstance(result, str) else str(result)
            rec["attributes"]["tool.output"] = output[:500]   # truncate long outputs
            return output
        except Exception as e:
            rec["attributes"]["error"] = str(e)
            return f"error: {e}"
```

`execute_tool` now needs `parent_span` and `trace_id` from its caller — the TAO loop passes them in. One small parameter change at the call site:

```python
outputs = await asyncio.gather(*(
    execute_tool(c.name, c.input, parent_span=llm_span_id, trace_id=trace_id)
    for c in tool_calls
))
```

## Wiring into the TAO loop

The full instrumented loop:

```python
async def main():
    messages = load_messages()
    while True:
        user_input = input("❯ ")
        if user_input.lower() in ("/q", "exit"):
            break
        messages.append({"role": "user", "content": user_input})

        with span("turn", attributes={"user_input": user_input}) as turn_rec:
            trace_id = turn_rec["trace_id"]
            turn_span_id = turn_rec["span_id"]

            for iteration in range(MAX_ITERATIONS):
                with span("llm.call", parent=turn_span_id, trace_id=trace_id) as llm_rec:
                    response = await client.messages.create(...)
                    llm_rec["attributes"].update({
                        "model": "claude-sonnet-4-5",
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                        "iteration": iteration,
                    })
                    llm_span_id = llm_rec["span_id"]

                messages.append({"role": "assistant", "content": response.content})
                # ... print text, dispatch tools (with parent=llm_span_id) ...

            turn_rec["attributes"]["iterations"] = iteration + 1

        save_messages(messages)
```

Each turn produces one tree of spans:

```
turn
├─ llm.call (iteration 0)
├─ tool.call (read)
├─ tool.call (grep)
├─ llm.call (iteration 1)
├─ tool.call (edit)
└─ llm.call (iteration 2)   # final, text-only
```

## Reading the trace

After running the agent, `~/.coding-agent/traces.jsonl` looks like:

```json
{"trace_id": "abc123", "span_id": "def456", "parent_span_id": null, "name": "turn", ...}
{"trace_id": "abc123", "span_id": "ghi789", "parent_span_id": "def456", "name": "llm.call", "attributes": {"input_tokens": 1234, "output_tokens": 56}, ...}
{"trace_id": "abc123", "span_id": "jkl012", "parent_span_id": "ghi789", "name": "tool.call", "attributes": {"tool.name": "read", "tool.input": {"path": "main.py"}, ...}, ...}
```

A line per span. To extract one turn:

```bash
jq -c '. | select(.trace_id == "abc123")' ~/.coding-agent/traces.jsonl
```

To compute total tokens for a turn:

```bash
jq -s '[.[] | select(.trace_id == "abc123" and .name == "llm.call")] | map(.attributes.input_tokens + .attributes.output_tokens) | add' ~/.coding-agent/traces.jsonl
```

## Trade-offs to know

**File size.** A long session can produce megabytes of traces. Rotate the file or write per-day files in production.

**Sensitive data.** Tool inputs and outputs go straight into traces. If the agent reads a file containing secrets, those secrets are now in `traces.jsonl`. Either filter sensitive content before writing, or treat the trace file as sensitive (encrypted at rest).

**Truncation vs. completeness.** We truncated `tool.output` to 500 chars. That keeps file size manageable but loses information for debugging. Production tracing systems often store the full payload elsewhere (object storage) and reference it from the span by ID.

**Sync writes.** `write_span` does a blocking file append. For a single-user CLI agent this is fine. For high-throughput agents, you'd batch writes or use an async logger.

## What this didn't address

- **Replay.** Traces capture what happened but don't directly let you reproduce it. Replay needs more — capturing the LLM's full request body so you can re-issue it identically.
- **Visualization.** A JSONL file is grep-able but not interactive. Module 17 covers replay + visualization tooling.
- **Distributed tracing.** Single-process here; no propagation across services. OpenTelemetry's wider patterns (W3C Trace Context, exporters) come into play when the agent talks to other services.
- **Eval integration.** Traces are the input to evaluation. Module 19 builds on this trace format to score agent runs.

## Prompt your coding agent

If you want your coding agent to write this for you, paste:

```
Add structured tracing to main.py.

1. Define a TRACE_FILE = Path.home() / ".coding-agent" / "traces.jsonl" and a write_span(span_dict) helper that appends a JSON line (use json.dumps with default=str).

2. Add a context manager `span(name, parent=None, trace_id=None, **attributes)`:
   - Generate span_id (8-byte hex). If trace_id is None, generate a new one.
   - Record start_time (ISO UTC), start a perf_counter for duration.
   - Yield a dict with trace_id, span_id, parent_span_id, name, start_time, attributes (mutable so callers can add).
   - On exit (including exception), set end_time, duration_ms, write_span. Re-raise on exception.

3. In main()'s outer REPL loop, wrap each turn:
   `with span("turn", attributes={"user_input": user_input}) as turn_rec:` — capture trace_id and turn_rec["span_id"].

4. In the inner TAO loop, wrap each LLM call:
   `with span("llm.call", parent=turn_span_id, trace_id=trace_id) as llm_rec:` — populate attributes with model, input_tokens (from response.usage), output_tokens, iteration.

5. Update execute_tool to take (name, input, parent_span, trace_id) — wrap the dispatch in `with span("tool.call", parent=parent_span, trace_id=trace_id, **{"tool.name": name, "tool.input": input}) as rec:`. On exception or denied approval, set rec["attributes"]["error"] = str(e). Truncate tool.output to 500 chars.

6. Update the gather call site to pass parent_span=llm_rec["span_id"] and trace_id from the enclosing turn.

Don't break existing functionality — just add tracing on top.
```

The prompt tells your agent *what* to write. The module explains *why* — read it first.

---

**Next:** [Module 17: Replay and observability tooling](../17-replay-and-observability-tooling/)
