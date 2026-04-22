# Lesson 0: What is agentic engineering?

## The discipline

**Agentic engineering is the craft of building agents** — systems where a language model directs its own actions through tools, reasoning in a loop until a task is complete.

It's a distinct discipline from adjacent practices:

- **Prompt engineering** optimizes a single input to get a better single output. One shot.
- **ML engineering** trains, fine-tunes, and deploys models. It works on the weights.
- **Agentic engineering** treats the model as a fixed cognitive engine and builds the system around it — the loop, the tools, the memory, the observability, the safety.

The model is the brain. Agentic engineering is everything else.

## Types of agentic systems

There are two kinds of systems built on LLMs. The distinction is drawn sharply by Anthropic in [*Building Effective Agents*](https://www.anthropic.com/engineering/building-effective-agents):

**Workflows** — systems where LLMs and tools are orchestrated through **predefined code paths**. Your code decides the sequence of steps.

**Agents** — systems where **LLMs dynamically direct their own processes and tool usage**. The model decides the sequence.

### Common workflow patterns

Most production "AI apps" are workflows. The common patterns:

- **Prompt chaining** — LLM call → LLM call → LLM call, in a fixed order (e.g., outline → draft → polish)
- **Routing** — classify input, dispatch to a specialized handler (e.g., support tickets routed to billing, technical, or refunds)
- **Parallelization** — run multiple LLM calls in parallel and aggregate (e.g., N perspectives on one question)
- **Orchestrator-workers** — one LLM splits a task into sub-tasks, workers handle them
- **Evaluator-optimizer** — one LLM generates, another evaluates; loop until quality threshold

All of these are useful. All are workflows, not agents.

### What agents look like

Real agents are rarer because they're harder. Production examples:

- **Coding agents** — Claude Code, Cursor's agent mode, Devin, Aider. The model opens files, edits them, runs tests, iterates.
- **Research agents** — Deep Research, investigation systems. The model searches, synthesizes, digs deeper.
- **Task completion agents** — SWE-agent, browser-use agents. The model manipulates a filesystem or GUI to complete a task.

In each case, the next action depends on what the previous action produced. The paths can't be enumerated in advance.

> [!NOTE]
> Most systems marketed as "agents" are workflows. Workflows are often the right answer — they're more reliable, cheaper, and easier to evaluate. Build a workflow if you can. This curriculum is about the case when you can't.

## What agentic engineers do

The day-to-day work of building and operating agents:

- **Design tools** — what capabilities the agent has, at what granularity, with what error semantics
- **Build the loop** — the control structure that turns single LLM calls into sustained work; stop conditions; loop bounds
- **Architect memory** — what the agent remembers within a task, across tasks, and how it's retrieved
- **Manage context** — the context window as a budget; what goes in, what gets summarized, what gets evicted
- **Set up observability** — structured traces of every LLM call, tool call, and state transition
- **Build evaluation** — task-completion suites, trajectory analysis, regression testing for non-deterministic systems
- **Handle safety** — sandboxing, prompt injection defenses, human approval gates for irreversible actions
- **Manage cost and latency** — caching, batching, model routing, parallelization
- **Tune prompts and context** — system prompts still matter; they're scaffolding inside the larger system now

An agentic engineer is part systems designer, part researcher, part debugger. The model is non-deterministic, so the work is less *"this is correct"* and more *"this is reliable enough."*

## Where this curriculum goes

Each Part of the curriculum addresses one of the concerns above, starting from a working agent and adding capabilities until you're building production-grade systems. See the [root README](../../../) for the full map.

Start with [Lesson 1: What is an agent?](../01-what-is-an-agent/) to meet what we're going to build.

---

**Next:** [Lesson 1: What is an agent?](../01-what-is-an-agent/)
