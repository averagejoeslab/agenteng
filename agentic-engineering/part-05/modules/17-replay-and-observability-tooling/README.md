# Replay and observability tooling

Module 16 emits structured traces. The traces sit in a JSONL file. This module turns those traces into something you can actually use: **replay** (reconstruct exactly what the agent did, optionally re-run it deterministically) and **integration with observability platforms** (Phoenix, Langfuse, Helicone) for the production case where local files aren't enough.

## Replay: what it means and what it requires

Replay isn't one thing. There's a spectrum:

| Level | What you can do | What you need to capture |
|---|---|---|
| **Read replay** | Inspect exactly what happened — every prompt, every tool result, every model response | What we already have from Module 16 |
| **Mock replay** | Re-run the agent code with the same inputs but mocked LLM/tool responses, watching the same trace play through | The full request/response bodies for LLM calls and tool calls |
| **Live replay** | Re-run the agent for real with the same starting state, hoping for similar behavior | The starting `messages`, system prompt, and tool schemas |

We'll build read replay (a CLI viewer) and mock replay (a deterministic re-run for debugging). Live replay is mostly a question of capturing the full LLM call body — `messages.create()` arguments — which we add a span attribute for.

## A trace viewer

Read the JSONL, group by `trace_id`, render a tree:

```python
import json
import sys
from collections import defaultdict
from pathlib import Path

TRACE_FILE = Path.home() / ".coding-agent" / "traces.jsonl"


def load_traces():
    traces = defaultdict(list)
    with open(TRACE_FILE) as f:
        for line in f:
            span = json.loads(line)
            traces[span["trace_id"]].append(span)
    return traces


def print_tree(spans, parent_id=None, depth=0):
    children = [s for s in spans if s.get("parent_span_id") == parent_id]
    children.sort(key=lambda s: s["start_time"])
    for s in children:
        indent = "  " * depth
        d = s.get("duration_ms", "?")
        attrs = s.get("attributes", {})
        if s["name"] == "turn":
            label = f'{s["name"]} ({d}ms): {attrs.get("user_input", "")[:60]}'
        elif s["name"] == "llm.call":
            label = f'{s["name"]} ({d}ms) tokens={attrs.get("input_tokens")}/{attrs.get("output_tokens")}'
        elif s["name"] == "tool.call":
            label = f'{s["name"]} ({d}ms) {attrs.get("tool.name")}({attrs.get("tool.input")})'
        else:
            label = f'{s["name"]} ({d}ms)'
        if attrs.get("error"):
            label += f' ⚠ {attrs["error"]}'
        print(f"{indent}{label}")
        print_tree(spans, parent_id=s["span_id"], depth=depth + 1)


def main():
    traces = load_traces()
    if len(sys.argv) > 1:
        trace_id = sys.argv[1]
        print_tree(traces[trace_id])
    else:
        for trace_id, spans in sorted(traces.items()):
            root = next((s for s in spans if s.get("parent_span_id") is None), None)
            label = root["attributes"].get("user_input", "")[:60] if root else "?"
            print(f"{trace_id}: {label}")


if __name__ == "__main__":
    main()
```

Save as `view_traces.py`. `uv run view_traces.py` lists turns; `uv run view_traces.py <trace_id>` renders one as a tree:

```
turn (4231ms): What's in pyproject.toml?
  llm.call (812ms) tokens=4321/87
  tool.call (12ms) read({'path': 'pyproject.toml'})
  llm.call (1342ms) tokens=4567/123
```

## Mock replay

To re-run the agent against a captured trace deterministically, we need to intercept the LLM call and the tool calls — return the captured outputs instead of hitting the real API or filesystem.

The cleanest place to mock is the executor (Module 10) and the LLM client. Replace `client.messages.create` with a function that returns the captured `response.content` for each iteration in order. Replace `execute_tool` with a function that returns the captured outputs.

```python
class TraceReplayer:
    def __init__(self, spans):
        self.spans = sorted(spans, key=lambda s: s["start_time"])
        self.llm_calls = [s for s in self.spans if s["name"] == "llm.call"]
        self.tool_calls = [s for s in self.spans if s["name"] == "tool.call"]
        self.llm_idx = 0
        self.tool_idx = 0

    async def llm(self, *args, **kwargs):
        span = self.llm_calls[self.llm_idx]
        self.llm_idx += 1
        # Return a fake response that mimics anthropic.types.Message
        return FakeMessage(content=span["attributes"].get("response_content"))

    async def execute_tool(self, name, input, **kwargs):
        span = self.tool_calls[self.tool_idx]
        self.tool_idx += 1
        return span["attributes"]["tool.output"]
```

For this to work end-to-end, Module 16's traces have to capture the full `response.content` (not just token counts) — extend the LLM-call span to record `attributes["response_content"] = [b.model_dump() for b in response.content]`. Trade-off: traces get larger.

Mock replay is most valuable for **debugging**: when a user reports *"the agent did X and it was wrong,"* you can re-run their exact session against your local code with the same prompts and tool outputs — what changes is the agent's logic. If your fix changes behavior on replay, you've found the bug.

## Production observability platforms

For deployed agents, JSONL files don't scale. The trace volume is large, the queries are interactive, and multiple developers want to share a single source of truth. The tooling landscape:

| Platform | Strength | Integration |
|---|---|---|
| **[Phoenix (Arize)](https://github.com/Arize-ai/phoenix)** | Open source, OpenTelemetry-based, runs locally or self-hosted | Drop-in OTel exporter |
| **[Langfuse](https://langfuse.com)** | Trace-first UX with eval/scoring built in | Python SDK with `@observe` decorators |
| **[Helicone](https://www.helicone.ai)** | Proxy-based — set `base_url` and traces flow automatically | Single-line client config change |
| **[Datadog APM](https://www.datadoghq.com/product/apm/)** | If you already have Datadog | OpenTelemetry exporter |
| **OpenTelemetry collector** | Vendor-neutral plumbing — emit OTel, send to anything | Most flexible, most setup |

The semantic conventions for **GenAI tracing** are stabilizing under OpenTelemetry: `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, etc. If you adopt those names in your span attributes from the start, swapping platforms is mostly a configuration change.

To convert Module 16's local tracer to OTel-shaped spans, add an exporter alongside the file writer. Pseudocode:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint="http://localhost:4317")))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("coding-agent")

# Replace the custom span() context manager with tracer.start_as_current_span(name)
```

The local JSONL stays for development; OTel exports go to whatever platform the team uses. Same instrumentation, two destinations.

## Trade-offs to know

**File-based vs. platform.** Files are easy to start with, hard to scale and share. Platforms are easy to scale, harder to start with (account, integration, vendor lock-in). For a curriculum, files. For production, an OTel-compatible platform.

**Trace size vs. fidelity.** Storing full LLM request and response bodies enables replay but balloons trace size. Common compromise: store full request/response in object storage, reference by ID from the span.

**Sampling.** In production with high traffic, you can't trace every turn. Adopt sampling — keep all error traces, sample successful ones (1 in 100). Tail-based sampling makes the *"keep all errors"* part work.

**Privacy.** Production traces capture user prompts, tool outputs, model responses — all of which may contain sensitive content. Compliance review the trace pipeline; mask known patterns; encrypt at rest.

## What this didn't address

- **Distributed tracing across services.** When the agent calls a separate API or hands off to another service, propagating `trace_id` via HTTP headers (W3C Trace Context) is what links the spans across hops.
- **Real-time visualization.** The JSONL viewer is post-hoc. A live web UI (like Phoenix's) is what you want for active debugging — out of scope for this curriculum, well-handled by existing tooling.
- **Sampling logic.** We trace everything. Production needs cost-aware sampling.

## Prompt your coding agent

If you want your coding agent to write this for you, paste:

```
Add a trace viewer and prepare for replay.

1. Create view_traces.py at the project root:
   - load_traces() reads ~/.coding-agent/traces.jsonl, returns dict of trace_id -> list of spans
   - print_tree(spans, parent_id=None, depth=0) recursively renders spans as a tree, showing duration, key attributes (input_tokens for llm.call, tool.name and tool.input for tool.call, user_input for turn)
   - main() with no args: list all trace_ids with the user_input. With one arg: print_tree for that trace_id.

2. Extend Module 16's llm.call span attributes to include `response_content` = [b.model_dump() for b in response.content]. This is what mock replay needs.

3. Add a TraceReplayer class (in a separate replay.py) that:
   - Takes a list of spans for one trace
   - Has llm(*args, **kwargs) returning the captured response_content as a fake message
   - Has execute_tool(name, input, ...) returning the captured tool.output
   - Yields each in order (llm_idx, tool_idx counters)

This is the hooks for mock replay; full integration is left for the user to wire (replace client.messages.create with replayer.llm in test paths).
```

The prompt tells your agent *what* to write. The module explains *why* — read it first.

---

**Next:** [Module 18: Eval foundations](../../../part-06/modules/18-eval-foundations/)
