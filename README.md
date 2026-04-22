# agenteng

A framework-free, code-first curriculum for **agentic engineering**.

## What is an agent?

An agent is a system with exactly three ingredients:

1. **An LLM call** — the reasoning engine
2. **A TAO loop** (Think, Act, Observe) — the structure that turns single calls into sustained thought
3. **Tools** — the ability to act

Remove any one and it's something else. No LLM call: not intelligent. No loop: it's a **workflow**. No tools: it's a **chatbot**.

> [!NOTE]
> Most production systems called "agents" are workflows. Workflows are often the right choice. This curriculum is about the other case — when a task genuinely requires the model to direct its own process, and you need to build it yourself.

## What you'll build

You'll start by building a ~200-line coding agent in TypeScript. Then you'll add everything real agents need: memory, well-designed tools, sandboxing, reliability, evaluation, observability, and production deployment.

**No frameworks. Just primitives and the reasoning behind them.**

## Curriculum

### Part 1 — The Agent
Define the three ingredients. Build them up one at a time. End with a working agent.

1. [What is an agent?](./agentic-engineering/lessons/01-what-is-an-agent/)
2. A single LLM call *(coming soon)*
3. The TAO loop *(coming soon)*
4. The terminal environment *(coming soon)*
5. The first tool *(coming soon)*
6. More tools *(coming soon)*

### Part 2 — Memory *(coming soon)*
Session memory, persistent trace, context windows, semantic recall.

### Part 3 — Tools *(coming soon)*
Tool design for agents: granularity, error messages as self-correction, MCP.

### Part 4 — Safety *(coming soon)*
Sandboxing, capability scoping, prompt injection, loop bounds, human-in-the-loop.

### Part 5 — Reliability *(coming soon)*
Stop conditions, self-correction, checkpointing.

### Part 6 — Evaluation *(coming soon)*
Task success vs. trajectory quality, LLM-as-judge, regression suites.

### Part 7 — Observability *(coming soon)*
Structured tracing, replay, the tooling landscape.

### Part 8 — Production *(coming soon)*
Cost, latency, model routing, deployment, versioning.

## Reference implementations

- [**basic-agent**](https://github.com/averagejoeslab/basic-agent) — the ~200-line artifact built across Part 1
- [**nanoagent**](https://github.com/mrcloudchase/nanoagent) — an extended reference with persistent memory, semantic recall, and a Docker sandbox

## Prerequisites

- Comfort reading TypeScript
- [Bun](https://bun.sh) installed
- An [Anthropic API key](https://console.anthropic.com)

## License

MIT
