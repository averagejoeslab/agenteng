# traced-agent

Adds **structured tracing** to the safe-agent. Every turn produces a tree of spans (turn → llm.call → tool.call) emitted as JSONL. The end state of [Module 9: Add observability](../../modules/09-add-observability/).

- **[Module 9: Add observability](../../modules/09-add-observability/)** — a `span()` context manager that auto-emits with timing and error capture. Each turn rooted at a `turn` span; LLM calls and tool calls nest under it via `parent_span_id`. The JSONL output is grep-able, jq-friendly, and one OTel exporter step away from any modern observability platform.

## Run it

Requires Docker (carries forward from safe-agent).

From the `agents/` directory:

```bash
uv run traced-agent/main.py
```

## State files

- `~/.traced-agent/messages.json` — conversation
- `~/.traced-agent/recall.json` — embedded summaries
- `~/.traced-agent/traces.jsonl` — span emission, one line per span

## Inspect traces

```bash
# All trace IDs:
jq -r '.trace_id' ~/.traced-agent/traces.jsonl | sort -u

# All spans for one trace:
jq 'select(.trace_id == "abc123")' ~/.traced-agent/traces.jsonl

# Summed input tokens for a trace:
jq -s '[.[] | select(.trace_id == "abc123" and .name == "llm.call")] | map(.attributes.input_tokens) | add' ~/.traced-agent/traces.jsonl
```

## What's new vs. safe-agent

- Every operation (turn, LLM call, tool call) emits a span with start/end times, duration, and structured attributes.
- Errors and approval denials are captured in span attributes for post-hoc debugging.
- The trace file is the input for the eval suite (`evals/`) — both regression detection and trajectory analysis.

## What this didn't address

- No cost/latency optimization — see `optimized-agent`.
