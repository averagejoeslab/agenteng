# agenteng

A framework-free, code-first content series on **agentic engineering**.

## What is an agent?

An agent is a system with exactly three ingredients:

1. **An LLM call** — the reasoning engine
2. **A TAO loop** (Think, Act, Observe) — the structure that turns single calls into sustained work
3. **Tools** — the ability to act

Remove any one and it's something else. No LLM call: not intelligent. No loop: it's a **workflow**. No tools: it's a **chatbot**.

> [!NOTE]
> Most production systems called "agents" are workflows. Workflows are often the right choice. This content is about the other case — when a task genuinely requires the model to direct its own process, and you need to build it yourself.

## What you'll build

You'll start by building a minimal coding agent in Python. Then you'll grow it into a real-world system: well-designed tools, memory and context management, observability, evaluation, safety and guardrails, and cost/latency optimization.

**No frameworks. Just primitives and the reasoning behind them.**

## Reference agents

This repo is both the content *and* runnable references. Each Part of the content produces a working agent; those agents live under [`agents/`](./agents/), sharing one venv and one `.env`.

Current agents:

- **[`agents/basic-agent`](./agents/basic-agent/)** — minimal coding agent Part 1 produces. Terminal REPL + TAO loop + `read` tool.

Run it:

```bash
cd agents
cp .env.example .env           # paste your Anthropic API key
uv sync                         # install deps into ./.venv
uv run basic-agent/main.py      # start the REPL
```

Then at the `❯` prompt:

```
❯ What's in pyproject.toml?
❯ Does main.py import python-dotenv?
❯ /q
```

The model calls `read(path=...)` when it needs to examine a file.

## Content

### Part 0 — Prereqs
Read the orientation and set up your environment before starting Part 1.

- [Module 0: What is agentic engineering?](./agentic-engineering/part-00/modules/00-what-is-agentic-engineering/) — the discipline, the landscape, what agentic engineers do
- Comfort reading Python
- [Python 3.13 or newer](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/) for dependency management
- An [Anthropic API key](https://console.anthropic.com)

### Part 1 — The Agent
Define the three ingredients. Build them up one at a time. End with a working agent.

1. [What is an agent?](./agentic-engineering/part-01/modules/01-what-is-an-agent/)
2. [A single LLM call](./agentic-engineering/part-01/modules/02-a-single-llm-call/)
3. [The TAO loop](./agentic-engineering/part-01/modules/03-the-tao-loop/)
4. [First tool](./agentic-engineering/part-01/modules/04-first-tool/)

### Part 2 — Tool Design *(coming soon)*
Grow the minimal agent into a multi-tool system. A proper tool executor, granularity decisions, error messages as the self-correction channel, MCP.

### Part 3 — Memory and Context *(coming soon)*
Persistent memory across sessions, context window as a budget, semantic recall, compaction and eviction.

### Part 4 — Observability *(coming soon)*
Structured traces of every LLM call, tool call, and state transition. Replay. Tooling landscape.

### Part 5 — Evaluation *(coming soon)*
Task-completion suites, trajectory analysis, LLM-as-judge, regression testing for non-deterministic systems.

### Part 6 — Safety and Guardrails *(coming soon)*
Identity and access management, sandboxing, input/output detection, human approval gates, loop bounds.

### Part 7 — Cost and Latency *(coming soon)*
Caching, batching, model routing, parallelization, compression.

### Part 8 — Prompt and Context Tuning *(coming soon)*
The system prompt as scaffolding. Iterative refinement of the full input assembly.

## License

MIT
