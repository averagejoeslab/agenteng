# Prompt design

Through the curriculum so far, the system prompt has been a one-liner: `"You are a helpful coding assistant."` That's enough for the agent to function but leaves significant behavioral leverage on the table. The system prompt is the agent's specification — what it's for, how it behaves, what it knows about the environment, what conventions it follows.

This module covers prompt design as engineering: structure, examples, iteration. The eval suite from Module 19 is what makes prompt iteration safe — every change is validated against the suite before it ships.

## What the system prompt does

The system prompt is the only thing the model sees that *you* control directly across every turn. It lives at the top of the context, gets cached (Module 20's prompt caching), and shapes everything downstream. The model's behavior is a function of:

1. **Its training.** What it learned. You don't control this.
2. **The system prompt.** Your specification. You control this.
3. **The conversation messages.** What's been said. The agent and user share control.
4. **Tool schemas + descriptions.** Module 7 established these.

System prompt + tool descriptions are the highest-leverage levers. A small system prompt change can reshape an entire turn's behavior.

## Structure: sections, not soup

A long string of advice gets ignored. A structured prompt with named sections gets followed:

```
You are a coding agent for the [project name] codebase.

## Your role
Help the user understand and modify the codebase. Be precise, concise, and grounded in actual file contents.

## Tools
You have read, write, edit, grep, glob, and bash. Prefer focused tools (read for files, grep for content, glob for paths) over bash unless you specifically need a shell.

## Conventions
- The codebase follows [language] conventions: [specifics].
- Tests live in [path]. Run them with [command].
- Don't write to [forbidden paths].

## Working style
- Read before editing. Don't guess at file contents.
- For multi-step tasks, narrate your plan briefly before executing.
- If a tool returns an error, examine it before retrying.

## When you're done
Stop calling tools. The user wants the answer, not more action.
```

Five sections — role, tools, conventions, working style, completion criteria — each a few lines. The model parses structure better than narrative when both exist.

## Few-shot examples

The model already knows how to use tools generally. Few-shot examples teach it *how to use them in your specific context*. Examples go in the system prompt or in the first user message:

```
## Examples

User: "What does main.py import?"
Assistant approach: read("main.py") → answer based on the imports at the top.

User: "Find all uses of `Anthropic` in this codebase."
Assistant approach: grep("Anthropic", ".") → list the files and lines.

User: "Add error handling to the read function."
Assistant approach: read the file → identify the function → use edit() with a precise old/new pair → confirm.
```

Examples shape behavior more than instructions do. *"Be concise"* is a vague directive. A two-sentence example answer is a concrete pattern.

Trade-offs:

- Examples take tokens. Each example costs you on every call (until prompt caching makes them free).
- Bad examples are worse than no examples. The model will copy them precisely. Vet examples carefully.
- Few-shot generalizes weakly when examples are too narrow. 3-5 diverse examples beat 10 similar ones.

## Iterative refinement

Prompt changes feel like art, but they should be engineering. The cycle:

1. **Hypothesize.** Form a specific claim — *"adding a section about working style will reduce tool overuse on simple tasks."*
2. **Implement.** Change the system prompt.
3. **Eval.** Run the Module 19 eval suite.
4. **Compare.** Did the metric you cared about move? Did anything else regress?
5. **Decide.** Keep, revert, or tune.

Without the eval suite, prompt iteration is gut-feel and selection bias — you remember the time it worked, forget the times it didn't. With evals, you have data.

Concrete metrics for prompt changes:

- **Pass rate** on the eval suite (Module 19). The headline number.
- **Mean tool calls per turn** (from Module 16 traces). Lower is usually better.
- **Mean tokens per turn**. Direct cost signal.
- **Failure cases.** Which specific cases regressed? Look at their traces.

## Common prompt issues and fixes

| Problem | Diagnosis | Fix |
|---|---|---|
| Agent calls too many tools for simple questions | Over-eager tool use | Add a "simple questions get direct answers" line |
| Agent answers without checking files | Confabulation | "Always read before answering questions about file contents" |
| Agent uses `bash` when a focused tool exists | Missing routing guidance | "Prefer `read` over `cat`, `grep` over `bash grep`, etc." |
| Agent's tone is too casual or too formal | Style drift | Few-shot examples in target tone |
| Agent forgets project-specific conventions mid-task | Long context dilution | Re-state critical conventions at the top of the prompt |
| Agent loops on the same tool with same args | Stuck reasoning | "If a tool returned the same result twice, try a different approach" |

Each fix is a hypothesis. Eval whether it actually helps before committing.

## Prompt caching reminder

Module 20 introduced prompt caching. Every word in the system prompt costs tokens at full rate on the *first* call within a 5-minute window, then 10% on subsequent calls. So:

- Verbose system prompts get cheap fast for active sessions.
- A change to the system prompt invalidates the cache; the next call pays full rate.
- Stable, well-structured prompts are friend to the cache. Frequently-edited prompts aren't.

Iterate during development; settle on a stable shape for production.

## Trade-offs to know

**Prompt complexity vs. predictability.** Longer prompts give more guidance but also more opportunities for the model to misread or contradict. Resist the urge to add a line for every observed failure — fix the most-impactful issues, accept some imperfection.

**Model-specific tuning.** A prompt tuned for Sonnet may behave differently on Opus or Haiku. The eval suite catches regressions when you upgrade models.

**Drift over time.** Anthropic releases new model snapshots; their behavior shifts subtly. Prompts that worked last quarter may need adjustment. Run the eval suite when changing models.

**The temptation to over-specify.** Trust the model. If it's smart enough to be useful, it doesn't need 50 lines of micromanaging instructions. Specify constraints and conventions; leave the reasoning to the model.

## What this didn't address

- **Context assembly.** What you put into each call beyond the system prompt — recalled memories, recent turns, tool results — is the next module.
- **Few-shot selection at runtime.** Some agents pick few-shot examples dynamically based on the current task. More complex; useful for diverse workloads.
- **Multi-turn prompt management.** When the prompt itself needs to change between turns (e.g., narrowing scope after the user clarifies), you're really doing context assembly — Module 23.

## Prompt your coding agent

Less applicable here than other modules — prompt design is the work, not the tooling. But: use your existing eval suite (Module 19) to A/B-test prompt versions. Keep two prompts in version control, run the eval against both, pick the winner.

---

**Next:** [Module 23: Context assembly](../23-context-assembly/)
