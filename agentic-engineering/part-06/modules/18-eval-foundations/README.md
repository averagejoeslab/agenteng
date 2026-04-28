# Eval foundations

This module is conceptual. Module 19 implements; this one establishes what we're implementing and why.

You can't improve what you can't measure. The agent has been growing more capable through Parts 1-5, but every change — a new tool, a tweaked prompt, an added safety check — could be making it better, worse, or both depending on the task. Without a way to measure quality systematically, you're flying blind.

This module covers what evaluation means for a non-deterministic agent: why traditional unit tests don't apply, what to measure, and how to design test suites that survive the model's variability.

## Why agent eval is different

Traditional code is deterministic. Same input, same output. Tests assert exact equality and either pass or fail. The semantics map cleanly: `assert add(2, 2) == 4`.

Agents are non-deterministic. Same input can produce different tool sequences, different reasoning paths, different final answers, all of which might be equally correct. Two valid completions of *"summarize this file"* might phrase the summary differently and still both be right.

So the tests change shape:

- **Output equality doesn't work.** The exact text varies. You need fuzzier checks (does the answer contain the right facts? does the trajectory hit the right steps?).
- **One run isn't enough.** A test passing once doesn't mean it always passes. Average over N runs.
- **Failure isn't binary.** "It was 80% right" is meaningful. Eval scores are often continuous, not pass/fail.
- **Subjective quality matters.** *"Is this summary good?"* requires judgment, not just exact-match.

The shape of eval for agents has three pieces: **task-completion**, **trajectory analysis**, and **quality judgment**.

## Task completion

Did the agent accomplish the goal? Examples for a coding agent:

| Task | Pass condition |
|---|---|
| *"Read pyproject.toml and tell me the Python version requirement."* | Final answer contains `3.13` (or whatever's in the file) |
| *"Add a docstring to the `read` function."* | The file `read` lives in now contains a docstring on that function |
| *"Find any TODOs in the codebase."* | Final answer enumerates the TODOs that exist |

These have **side-effect-checkable** pass conditions. You don't need to read the agent's reasoning — you check the world afterward (or check the final text). Either the docstring is there or it isn't; either the version number is correct or it isn't.

Task-completion evals are the most useful kind because the pass condition is concrete. Run the agent on the task, then check the world.

## Trajectory analysis

The agent's path matters too, not just the destination. *"The agent answered correctly"* is different from *"the agent answered correctly after running 47 tool calls in a confused loop."* Both pass task completion; only one is good.

What to measure in a trajectory:

- **Number of LLM calls.** More usually means worse (slower, more expensive, possibly confused).
- **Number of tool calls.** Same.
- **Duplicate tool calls** with identical args (a strong signal of stuck reasoning).
- **Failed tool calls.** The model misuse the tool; the tool returned an error.
- **Iterations to first text.** How quickly did the agent stop being indecisive?
- **Specific tool patterns.** *"The agent used `bash` when `read` would have sufficed"* is often a sign of a missing capability or a poor system prompt.

The traces from Module 16 are exactly the input for trajectory analysis. Every span you captured becomes signal.

## Quality judgment (LLM-as-judge)

Some questions can't be checked with code:

- *"Was that explanation clear?"*
- *"Did the agent follow the user's coding style?"*
- *"Was the refactor minimal, or did it touch unrelated lines?"*

These are subjective. The standard production move: **LLM-as-judge** — give a separate model the question, the agent's answer, and a rubric, and have it score.

```
You are evaluating an agent's response.

User asked: "{user_input}"
Agent answered: "{agent_response}"

Score the answer on a 1-5 scale where:
1 = wrong or off-topic
3 = correct but unhelpful
5 = correct and well-explained

Output: <score>1-5</score> <reasoning>...</reasoning>
```

Trade-offs of LLM-as-judge:

- **Bias.** The judge model has its own preferences, which can correlate with the agent model in ways that mask real problems.
- **Inconsistency.** Same agent output, run twice through the judge, can score differently.
- **Cost.** Every eval doubles inference cost (run the agent, then run the judge).
- **Dependence on prompt.** A poorly written rubric produces low-signal scores.

Used correctly, LLM-as-judge is the only way to evaluate qualitative criteria at scale. Used badly, it's eval theater.

## Stochastic evaluation

Agents are non-deterministic. A single eval run is a sample. The result you should report is a distribution over many runs, not a point.

Concrete pattern: run each test case **N times** (N = 5 or 10 typical). Report:

- **Pass rate** — fraction of runs that passed task completion.
- **Mean score** — for continuous metrics, the average across runs.
- **Variance** — high variance = unreliable behavior, even if mean looks fine.

A test that passes 5/5 is probably solid. A test that passes 8/10 might be flaky in a way you should investigate. A test that passes 10/10 in development but 2/10 in production is hitting a model temperature or system prompt difference.

For curriculum-grade work, N=5 is enough. For production rollouts of model upgrades, you'd want N=50+ on critical tasks.

## Test design

Three properties of a good agent eval:

**1. Realistic.** The test mirrors how users actually use the agent. Synthetic tests that pass while users still complain are worse than no tests.

**2. Pinpointed.** Each test exercises one thing. *"Did the agent handle a bash error correctly?"* and *"Did the agent explain the error?"* are two tests, not one. Composite tests obscure which part regressed.

**3. Stable.** The test should pass consistently when the agent is working. Tests that fail randomly become noise; teams ignore them. Reliability of the test matters as much as the agent's behavior.

A starter test set for a coding agent:

| Category | Tests |
|---|---|
| **Read** | Recall a fact from a file, identify imports, count lines |
| **Search** | Find files by pattern, find lines matching regex, locate symbol definitions |
| **Edit** | Apply a clean refactor, fix a typo, add a docstring |
| **Multi-step** | Find and fix a bug across 2 files, refactor based on a search result |
| **Error recovery** | Handle missing file, recover from a tool error |

Start small. 10 tests well-tuned beats 100 flaky.

## Regression as the use case

The most valuable thing eval gives you: **a regression suite**. Run it before any change to the agent — system prompt, tool changes, model upgrades, refactors. If pass rate drops, the change is worse on something you cared about.

This is what makes Parts 7 and 8 (cost/latency optimization, prompt tuning) safe to do. Without an eval suite, every optimization is a roll of the dice — *"the agent feels faster, but did it lose accuracy?"* is unanswerable. With evals, you measure.

## What this didn't address

Implementation. Module 19 builds the harness — code that runs the agent on each test case, captures traces, scores results, computes pass rate, tracks regression over time.

---

**Next:** [Module 19: Eval implementation](../19-eval-implementation/)
