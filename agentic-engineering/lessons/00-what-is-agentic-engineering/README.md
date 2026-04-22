# Lesson 0: What is agentic engineering?

## What is agentic engineering?

**Agentic engineering is the discipline of building agentic systems.** "Agentic systems" is the umbrella term from Anthropic's [*Building Effective Agents*](https://www.anthropic.com/engineering/building-effective-agents), covering both workflows and agents.

Working in this discipline entails these concerns:

- **Design tools** — what capabilities the system has, at what granularity, with what error semantics. See [Model Context Protocol](https://modelcontextprotocol.io) for one standardization effort.
- **Build the loop or the orchestration** — the control structure that sequences LLM calls, whether the model or your code decides
- **Architect memory** — what's remembered within a task, across tasks, and how it's retrieved
- **Manage context** — the context window as a budget; what goes in, what gets summarized, what gets evicted
- **Set up observability** — structured traces of every LLM call, tool call, and state transition (e.g., [Langfuse](https://langfuse.com), [LangSmith](https://smith.langchain.com), [Arize Phoenix](https://phoenix.arize.com))
- **Build evaluation** — task-completion suites, trajectory analysis, regression testing for non-deterministic systems
- **Handle safety** — sandboxing, prompt injection defenses, human approval gates (see [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/))
- **Manage cost and latency** — caching, batching, model routing, parallelization
- **Tune prompts and context** — the system prompt is scaffolding inside the larger system

> [!NOTE]
> These fall into three buckets: **foundations** (tools, loop, memory, context), **observability and trust** (tracing, evaluation, safety), and **production economics** (cost, latency, prompts).

## What are agentic systems?

Agentic systems coordinate multiple LLM invocations to accomplish multi-step tasks. A control structure sequences the calls; each step's output feeds into the next. Tools, memory, and retrieval are common participants but not strictly required — a pure LLM-to-LLM chain is still an agentic system.

The defining property is **coordination across steps**. A one-off prompt-response isn't an agentic system. A system that chains, routes, parallelizes, or loops multiple LLM calls is.

```mermaid
flowchart LR
    subgraph NotAgentic["Not an agentic system"]
        direction LR
        N1[Prompt] --> N2[LLM] --> N3[Output]
    end
    subgraph Agentic["Agentic system"]
        direction LR
        A1[Prompt] --> A2[LLM]
        A2 --> A3[Tool / LLM]
        A3 --> A4[LLM]
        A4 --> A5[Output]
    end
```

## Types of agentic systems

Agentic systems come in two forms, as defined in Anthropic's [*Building Effective Agents*](https://www.anthropic.com/engineering/building-effective-agents):

**Workflows** — systems where LLMs and tools are orchestrated through **predefined code paths**. Your code decides the sequence of steps.

**Agents** — systems where **LLMs dynamically direct their own processes and tool usage**. The model decides the sequence.

```mermaid
flowchart LR
    subgraph Workflow["Workflow — your code decides"]
        direction LR
        W1[LLM] --> W2[LLM] --> W3[LLM]
    end
    subgraph Agent["Agent — the model decides"]
        direction TB
        A1[LLM] --> A2{Tool?}
        A2 -->|yes| A3[Execute] --> A1
        A2 -->|no| A4[Done]
    end
```

Both are legitimate agentic systems. This curriculum subscribes to Anthropic's taxonomy.

### Common workflow patterns

| Pattern | Control flow | Example |
|---|---|---|
| **Prompt chaining** | LLM → LLM → LLM, fixed order | outline → draft → polish |
| **Routing** | Classify input → dispatch to one of N handlers | support tickets routed to billing / technical / refunds |
| **Parallelization** | Run N LLM calls in parallel → aggregate | N perspectives on one question |
| **Orchestrator-workers** | One LLM splits work → workers handle sub-tasks | research report with multiple sections |
| **Evaluator-optimizer** | Generator → Evaluator → loop until good | draft with a quality-gate loop |

<details>
<summary>See the control flow of each pattern</summary>

**Prompt chaining**

```mermaid
flowchart LR
    In[Input] --> A[LLM 1] --> B[LLM 2] --> C[LLM 3] --> Out[Output]
```

**Routing**

```mermaid
flowchart LR
    In[Input] --> R[Router LLM]
    R --> H1[Handler A]
    R --> H2[Handler B]
    R --> H3[Handler C]
```

**Parallelization**

```mermaid
flowchart LR
    In[Input] --> A[LLM]
    In --> B[LLM]
    In --> C[LLM]
    A --> Agg[Aggregate]
    B --> Agg
    C --> Agg
```

**Orchestrator-workers**

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

**Evaluator-optimizer**

```mermaid
flowchart LR
    In[Input] --> G[Generator LLM]
    G --> E[Evaluator LLM]
    E -->|good| Out[Output]
    E -->|refine| G
```

</details>

### What agents look like

Production examples:

- **Coding agents** — [Claude Code](https://claude.com/claude-code), [Cursor](https://cursor.com), [Devin](https://devin.ai), [Aider](https://aider.chat). The model opens files, edits them, runs tests, iterates.
- **Research agents** — [OpenAI Deep Research](https://openai.com/index/introducing-deep-research/), Claude's research mode. The model searches, synthesizes, digs deeper.
- **Task completion agents** — [SWE-agent](https://swe-agent.com), browser-use agents. The model manipulates a filesystem or GUI to complete a task.

In each case, the next action depends on what the previous action produced. The paths can't be enumerated in advance.

> [!IMPORTANT]
> Most systems marketed as "agents" in 2026 are workflows. That's often the right answer. This curriculum is about the case when it isn't.

## The Average Joes Lab stance: purist agents only

From Lesson 1 on, this curriculum is purist: **an agent is a system where the model directs its own control flow through a loop of tools.** Workflows are outside the scope of the teaching that follows.

The reason: **a workflow is just an agent with the control flow codified.** The pieces are the same (LLM calls, tools, context, memory), but *who decides the next step* shifts from the model to your code. Understanding agents → understanding workflows; the reverse doesn't hold.

```mermaid
flowchart LR
    A[Agent<br/>model decides] -->|codify control flow| W[Workflow<br/>code decides]
    W -.cannot derive.-> A
```

For most production systems a workflow is more reliable, cheaper, and easier to evaluate — [Anthropic makes the same case](https://www.anthropic.com/engineering/building-effective-agents). The interesting engineering problems — designing tools the model will use well, managing an open-ended context, making a non-deterministic loop reliable, evaluating a trajectory you can't enumerate — are agent problems. If you want a workflow, you already have the ingredients.

---

**Next:** [Lesson 1: What is an agent?](../01-what-is-an-agent/)
