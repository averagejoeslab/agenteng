# agenteng

A framework-free take on **agentic engineering**.

## What is agentic engineering?

**Agentic engineering is the discipline of building agentic systems.**

Working in this discipline involves the following items:

- **Building the control flow** — the control flow determines the path the system takes
- **Designing tools** — what capabilities the system has, at what granularity, with what error semantics.
- **Architecting memory** — what's remembered, when it's remembered, and how it's retrieved
- **Managing context** — the context window is a budget of tokens; determine what goes into context and what gets evicted.
- **Handling safety/guardrails** — identity and access management, sandboxing, input/output detection, human approval gates, etc.
- **Setting up observability** — structured traces of every LLM call, tool call, and state transition to help with debugging and monitoring.
- **Building evaluations** — to benchmark the system's performance and ensure it is meeting the desired goals.
- **Managing cost and latency** — optimize costs and latency by caching, batching, model routing, parallelization, compression, etc.
- **Tuning prompts and context** — behavioral optimization via tuning the system prompt and context management.

## What are agentic systems?

An agentic system is a program that coordinates LLM calls to accomplish a goal. The term comes from Anthropic's [*Building Effective Agents*](https://www.anthropic.com/engineering/building-effective-agents) and serves as an umbrella over both workflows and agents.

## Types of agentic systems

Agentic systems come in two forms, as defined in Anthropic's [*Building Effective Agents*](https://www.anthropic.com/engineering/building-effective-agents):

**Workflows** — systems where LLMs and tools are orchestrated through **predefined code paths**. Your code decides the sequence of steps and the model follows.

```mermaid
flowchart LR
    W1[LLM] --> W2[LLM] --> W3[LLM]
```

**Agents** — systems where **LLMs dynamically direct their own path through the control flow**. The model decides the sequence.

```mermaid
flowchart LR
    A1[LLM] --> A2{Tool?}
    A2 -->|yes| A3[Execute] --> A1
    A2 -->|no| A4[Done]
```

We subscribe to Anthropic's line of thinking and taxonomy on agentic systems. The sections below zoom in on each — common workflow patterns first, then common agent patterns.

### Common workflow patterns

**Prompt chaining** — LLM → LLM → LLM, fixed order. Example: outline → draft → polish.

```mermaid
flowchart LR
    In[Input] --> A[LLM 1] --> B[LLM 2] --> C[LLM 3] --> Out[Output]
```

**Routing** — Classify input → dispatch to one of N handlers. Example: support tickets routed to billing / technical / refunds.

```mermaid
flowchart LR
    In[Input] --> R[Router LLM]
    R --> H1[Handler A]
    R --> H2[Handler B]
    R --> H3[Handler C]
```

**Parallelization** — Run N LLM calls in parallel → aggregate. Example: N perspectives on one question.

```mermaid
flowchart LR
    In[Input] --> A[LLM]
    In --> B[LLM]
    In --> C[LLM]
    A --> Agg[Aggregate]
    B --> Agg
    C --> Agg
```

**Orchestrator-workers** — One LLM splits work → workers handle sub-tasks. Example: research report with multiple sections.

```mermaid
flowchart LR
    In[Input] --> O[Orchestrator LLM]
    O --> W1[Worker LLM]
    O --> W2[Worker LLM]
    O --> W3[Worker LLM]
    W1 --> S[Synthesize]
    W2 --> S
    W3 --> S
```

**Evaluator-optimizer** — Generator → Evaluator → loop until good. Example: draft with a quality-gate loop.

```mermaid
flowchart LR
    In[Input] --> G[Generator LLM]
    G --> E[Evaluator LLM]
    E -->|good| Out[Output]
    E -->|refine| G
```

### Common agent patterns

Workflows are a catalog of orchestration shapes. Agents are **one pattern** — an autonomous loop — and that's the whole list. What varies between agents in practice is the environment, the toolkit, and whether one of the tools happens to be another agent.

**Autonomous agent** — an LLM in a loop with tools, choosing what to do next based on what it observes. This is the pattern this repo builds.

```mermaid
flowchart LR
    Task[User task] --> LLM[LLM]
    LLM --> Q{Tool call?}
    Q -->|yes| Act[Execute tool<br/>+ observe result]
    Act --> LLM
    Q -->|no| Done[Done]
```

## Composition

Agents and workflows compose. You can build multi-agent systems, multi-workflow systems, or systems that mix both.

> [!NOTE]
> **Whether to use multi-agent composition at all is a live disagreement in the field.** Anthropic embraces it ([multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system); Claude Code subagents). Cognition argues *against* it in [*Don't Build Multi-Agents*](https://cognition.ai/blog/dont-build-multi-agents), making the case for a single-threaded linear agent with shared context — citing reliability and debuggability. Cursor 2.0 takes a third path: parallel independent agents on separate Git worktrees, no supervisor. The right composition depends on whether sub-tasks share context, run in parallel, and need to surface partial state — there is no default answer.

## The Average Joes Lab stance: purist agents only

We believe in the [Anthropic model](https://www.anthropic.com/engineering/building-effective-agents): **a real agent has autonomy over its own control flow.** The model decides what tool to call, what to do with the result, and when the task is done. No predetermined path.

**A workflow is an LLM on rails it can't get off of.** Your code lays the track; the model fills in text at each stop.

This content sticks to that strict definition: only systems with autonomous control flow count as agents. Workflows are outside the scope of what follows.

```mermaid
flowchart LR
    A[Agent<br/>model decides] -->|freeze the path| W[Workflow<br/>code decides]
    W -.cannot derive.-> A
```

The primitives are the same — LLM calls, tools, context, memory. An agent's control flow is the model making those choices live; a workflow's control flow is you making them in advance. The building blocks transfer; how you orchestrate them into a fixed sequence is its own discipline.

For most production systems a workflow is more reliable, cheaper, and easier to evaluate — build a workflow if you can. But the interesting engineering problems — designing tools the model will use well, managing an open-ended context, making a non-deterministic loop reliable, evaluating a trajectory you can't enumerate — are agent problems. If you want a workflow, compose the primitives from this content into the sequence your problem needs.

## What agents look like

Production examples:

- **Coding agents** — [Claude Code](https://claude.com/claude-code), [Cursor](https://cursor.com), [Devin](https://devin.ai), [Aider](https://aider.chat), [nanoagent](https://github.com/averagejoeslab/nanoagent). The model opens files, edits them, runs tests, iterates.
- **Research agents** — [OpenAI Deep Research](https://openai.com/index/introducing-deep-research/), Claude's research mode. The model searches, synthesizes, digs deeper.
- **Task completion agents** — [SWE-agent](https://swe-agent.com), browser-use agents. The model manipulates a filesystem or GUI to complete a task.

In each case, the next action depends on what the previous action produced. The paths can't be enumerated in advance.

> [!IMPORTANT]
> Most systems marketed as "agents" in 2026 are workflows. That's often the right answer. This content is about the case when it isn't.

## Setup

- Assumed programming experience (I will use Python as the example language)
- [Python 3.13 or newer](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/) for dependency management
- An [Anthropic API key](https://console.anthropic.com) (or other model provider API key)

## Content

### Part 1 — The Basic Agent
Define what an agent is and build one end-to-end. Concept, single LLM call, multi-turn conversation, first tool, the TAO loop, then async with parallel tool dispatch.

1. [What is an agent?](./agentic-engineering/part-01/modules/01-what-is-an-agent/)
2. [A single LLM call](./agentic-engineering/part-01/modules/02-a-single-llm-call/)
3. [Multi-turn conversation](./agentic-engineering/part-01/modules/03-multi-turn-conversation/)
4. [First tool](./agentic-engineering/part-01/modules/04-first-tool/)
5. [The TAO loop](./agentic-engineering/part-01/modules/05-the-tao-loop/)
6. [Async and parallel tool dispatch](./agentic-engineering/part-01/modules/06-async-and-parallel-dispatch/)

**Reference implementation agent:** [`agents/basic-agent`](./agents/basic-agent/)

### Part 2 — Tool Engineering
Grow the basic agent into a multi-tool coding agent: tool design principles, a registry pattern, the toolkit, and a centralized executor.

7. [Tool design](./agentic-engineering/part-02/modules/07-tool-design/)
8. [The tool registry](./agentic-engineering/part-02/modules/08-the-tool-registry/)
9. [Building the toolkit](./agentic-engineering/part-02/modules/09-building-the-toolkit/)
10. [The tool executor](./agentic-engineering/part-02/modules/10-the-tool-executor/)

**Reference implementation agent:** [`agents/coding-agent`](./agents/coding-agent/)

### Part 3 — Memory and Context
Persistent memory across sessions, context window as a budget, semantic recall.

11. [Persistent memory](./agentic-engineering/part-03/modules/11-persistent-memory/)
12. [Context as a budget](./agentic-engineering/part-03/modules/12-context-as-a-budget/)
13. [Semantic recall](./agentic-engineering/part-03/modules/13-semantic-recall/)

### Part 4 — Safety and GuardrailsSandboxing, approval gates, loop bounds, retry/backoff.

14. [Sandboxing](./agentic-engineering/part-04/modules/14-sandboxing/)
15. [Approval gates and loop bounds](./agentic-engineering/part-04/modules/15-approval-gates-and-loop-bounds/)

### Part 5 — ObservabilityStructured traces of every LLM call, tool call, and state transition. Replay. Tooling landscape.

16. [Structured tracing](./agentic-engineering/part-05/modules/16-structured-tracing/)
17. [Replay and observability tooling](./agentic-engineering/part-05/modules/17-replay-and-observability-tooling/)

### Part 6 — EvaluationTask-completion suites, trajectory analysis, LLM-as-judge, regression testing for non-deterministic systems.

18. [Eval foundations](./agentic-engineering/part-06/modules/18-eval-foundations/)
19. [Eval implementation](./agentic-engineering/part-06/modules/19-eval-implementation/)

### Part 7 — Cost and LatencyCaching, batching, model routing, prompt caching, async/threading for parallelism.

20. [Cost optimization](./agentic-engineering/part-07/modules/20-cost-optimization/)
21. [Latency optimization](./agentic-engineering/part-07/modules/21-latency-optimization/)

### Part 8 — Prompt and Context TuningThe system prompt as scaffolding. Iterative refinement of the full input assembly.

22. [Prompt design](./agentic-engineering/part-08/modules/22-prompt-design/)
23. [Context assembly](./agentic-engineering/part-08/modules/23-context-assembly/)

## License

MIT
