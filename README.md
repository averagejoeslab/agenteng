# agenteng

A framework-free take on **agentic engineering**.

## What is an agent?

An agent is a system with these three components:

1. **An LLM** — the reasoning engine
2. **A loop** (Think, Act, Observe) — a control flow that sustains the agent's work
3. **Tools** — the capability to take actions in an environment

This repo contains the content for guiding you through being an agentic engineer and it also contains reference implementations of agents.

## Content

### Part 0 — Prereqs
Read the orientation and set up your environment before starting Part 1.

- [Module 0: What is agentic engineering?](./agentic-engineering/part-00/modules/00-what-is-agentic-engineering/) — the discipline of building agentic systems, what agentic engineers do, and what agentic systems are
- Assumed programming experience (I will use Python as the example language)
- [Python 3.13 or newer](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/) for dependency management
- An [Anthropic API key](https://console.anthropic.com) (or other model provider API key)

### Part 1 — The Agent
Define what an agent is and the three components that make it up. Build them up one at a time.

1. [What is an agent?](./agentic-engineering/part-01/modules/01-what-is-an-agent/)
2. [A single LLM call](./agentic-engineering/part-01/modules/02-a-single-llm-call/)
3. [The TAO loop](./agentic-engineering/part-01/modules/03-the-tao-loop/)
4. [First tool](./agentic-engineering/part-01/modules/04-first-tool/)

**Reference implementation agent:** [`agents/basic-agent`](./agents/basic-agent/)

### Part 2 — Tool Design
Understand proper agentic tool design and expand the basic agent by moving to a tool registry, building a proper toolkit, and centralizing error handling in a tool executor.

5. [Tool design](./agentic-engineering/part-02/modules/05-tool-design/)
6. [The tool registry](./agentic-engineering/part-02/modules/06-the-tool-registry/)
7. [Building the toolkit](./agentic-engineering/part-02/modules/07-building-the-toolkit/)
8. [The tool executor](./agentic-engineering/part-02/modules/08-the-tool-executor/)

**Reference implementation agent:** [`agents/coding-agent`](./agents/coding-agent/)

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
