# Lesson 1: What is an agent?

A **chatbot** takes a message and returns text:

> *You:* "Create a hello world function in hello.ts"
> *Chatbot:* "Here's the code: `function hello() { console.log('Hello!'); }`"

The code was generated. No file was created.

An **agent** takes a message and *acts*:

> *You:* "Create a hello world function in hello.ts"
> *Agent:* calls `write("hello.ts", "function hello() { ... }")`
> *Agent:* "Done — hello.ts created."

The file now exists on disk. That's the difference.

## The definition

An agent is a system with three ingredients — plus one rule.

1. **An LLM call** — the reasoning engine
2. **A TAO loop** (Think, Act, Observe) — the structure that turns single calls into sustained work
3. **Tools** — functions the LLM can invoke to take action

**The rule:** the model directs the loop. Your code runs the loop and executes the tools, but the model decides *which* tool to call, *when*, and *when to stop*. Without that, an LLM + loop + tools is a workflow, not an agent.

Remove any ingredient and it's something else:

| Missing | What you have |
|---|---|
| LLM call | Deterministic code. Not intelligent. |
| Tools | A chatbot — can think, can't act. |
| Loop | One LLM call with optional tools, or a workflow your code orchestrates. |

## Chatbot vs. workflow vs. agent

```mermaid
flowchart LR
    subgraph Chatbot
        A1[LLM call]
    end
    subgraph Workflow
        B1[LLM call] -.predefined.-> B2[LLM call] -.path.-> B3[LLM call]
    end
    subgraph Agent
        direction TB
        C1[LLM call] --> C2{Tool?}
        C2 -->|yes| C3[Execute] --> C1
        C2 -->|no| C4[Done]
    end
```

The distinguishing question is **who decides the next step**:

| | LLM call | Tools | Agentic loop | Next step decided by |
|---|:---:|:---:|:---:|---|
| **Chatbot** | ✓ | ✗ | ✗ | The user (between turns) |
| **Workflow** | ✓ | sometimes | ✗ | Your code |
| **Agent** | ✓ | ✓ | ✓ | **The model** |

"Agentic loop" means a loop driven by the model's tool requests — distinct from a conversation loop (which multi-turn chatbots have) or an orchestration loop (which workflows may have). Only an agent has an agentic loop.

> [!NOTE]
> Most production systems called "agents" are workflows. They classify inputs, route to handlers, summarize, done — with predefined control flow. Those systems are often the right choice. They're just not agents by this definition, and this curriculum is about the other thing.

## The TAO loop

Each iteration has three phases: **Think, Act, Observe**.

1. **THINK** — the LLM reasons about what to do
2. **ACT** — it calls a tool
3. **OBSERVE** — it sees the result
4. **REPEAT** — until the model produces no more tool calls

THINK and ACT happen inside a single LLM response: the model emits reasoning text and a tool request in the same output. Your code handles execution (ACT) and feeds the result back (OBSERVE) on the next iteration.

> [!NOTE]
> This loop is commonly known as the **ReAct loop** — after the 2022 paper [*ReAct: Synergizing Reasoning and Acting in Language Models*](https://arxiv.org/abs/2210.03629) by Yao et al. The ReAct acronym drops observation; TAO keeps it visible. (The paper itself includes observation — it's the acronym that's lossy.)

A concrete trace:

```
User: "Find and summarize the TODOs in this codebase"

[THINK]    I'll search for TODO comments
[ACT]      grep("TODO", ".")
[OBSERVE]  src/auth.ts:42:  // TODO: session expiration
           src/auth.ts:87:  // TODO: rate limiting
           src/db.ts:14:    // TODO: connection pooling
           ... (47 lines across 12 files)
[THINK]    Most are in src/auth.ts — I'll read that file for context
[ACT]      read("src/auth.ts")
[OBSERVE]  [full file contents]
[THINK]    I have enough to summarize
[STOP]     "You have 47 TODOs across 12 files, concentrated in auth..."
```

The model chooses every action, reads every result, and decides when to stop. Your code just runs the loop.

## What we'll build

The next five lessons add one piece at a time:

| Lesson | Added | What it becomes |
|---|---|---|
| 2 | LLM call | A one-shot script |
| 3 | TAO loop (empty) | The loop structure with no tools to call |
| 4 | Terminal environment | An interactive REPL around the loop |
| 5 | First tool | **An agent** |
| 6 | More tools | A full toolkit |

By Lesson 6 you'll have a working coding agent in ~200 lines of TypeScript. Each lesson ends with something that runs.

> [!TIP]
> There's nothing magical about the ingredients. The LLM call is an HTTP POST. The loop is a `while(true)`. Tools are functions. What's interesting is how they fit together.

## What you'll need

- [Bun](https://bun.sh) — `curl -fsSL https://bun.sh/install | bash`
- An Anthropic API key from [console.anthropic.com](https://console.anthropic.com)

---

**Next:** Lesson 2: A single LLM call *(coming soon)*
