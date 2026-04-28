# Eval implementation

Module 18 covered the principles. This module builds the harness: a runner that loads test cases, executes the agent against each, scores outputs (with code where possible, LLM-as-judge where not), aggregates pass rates with stochastic averaging, and stores results so regressions are visible over time.

## The shape of a test case

A test case is a YAML or JSON document with three required fields and optional ones:

```yaml
id: read-pyproject-version
description: Agent reads pyproject.toml and reports the Python version
input: "What's the Python version requirement in pyproject.toml?"

# How to score
checks:
  - type: contains
    value: "3.13"
  - type: tool_used
    tool: read
  - type: tool_count_max
    value: 3

# Optional metadata
tags: [read, file-tools]
```

Three check types cover most cases:

- **`contains`** — the final agent text contains a substring. Cheap, exact, useful when the answer is concrete.
- **`tool_used`** — the agent invoked a specific tool at least once. From the trace.
- **`tool_count_max`** — the agent stayed within a sensible tool budget. Catches confused trajectories.

For qualitative cases, add an LLM-as-judge check:

```yaml
- type: llm_judge
  rubric: |
    Score 1-5: Did the agent's answer correctly identify the Python version
    in a way that's clear and concise?
```

Save test cases as `evals/cases/*.yaml`.

## The runner

```python
import asyncio
import yaml
from pathlib import Path
import importlib.util


async def run_case(case: dict, agent_main_path: str) -> dict:
    """Run the agent on a single case, return results dict."""
    # Spawn the agent as a subprocess so we can capture stdout and not pollute the runner's state.
    proc = await asyncio.create_subprocess_exec(
        "uv", "run", agent_main_path,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    user_input = case["input"] + "\n/q\n"
    stdout, stderr = await proc.communicate(user_input.encode())
    return {
        "id": case["id"],
        "stdout": stdout.decode(),
        "stderr": stderr.decode(),
        "exit_code": proc.returncode,
    }
```

Spawning the agent as a subprocess gives clean isolation — each case runs against fresh state, no shared memory or trace contamination. We pipe the user input and `/q` to make the agent finish and exit.

## Scoring with checks

```python
async def score(case: dict, result: dict, traces: list) -> dict:
    """Apply each check to the result; return per-check pass/fail and an overall score."""
    check_results = []
    for check in case.get("checks", []):
        if check["type"] == "contains":
            passed = check["value"] in result["stdout"]
        elif check["type"] == "tool_used":
            tools_called = {s["attributes"].get("tool.name")
                            for s in traces if s["name"] == "tool.call"}
            passed = check["tool"] in tools_called
        elif check["type"] == "tool_count_max":
            count = sum(1 for s in traces if s["name"] == "tool.call")
            passed = count <= check["value"]
        elif check["type"] == "llm_judge":
            passed = await llm_judge(case["input"], result["stdout"], check["rubric"])
        else:
            passed = False
        check_results.append({"check": check["type"], "passed": passed, "details": check})

    overall = all(c["passed"] for c in check_results)
    return {"id": case["id"], "passed": overall, "checks": check_results}
```

Traces come from reading `~/.coding-agent/traces.jsonl` filtered by start time of this run. The runner needs to record when each case started and end, then load only spans in that window. (Or each run could write to a per-case trace file.)

## LLM-as-judge

```python
JUDGE_MODEL = "claude-sonnet-4-5"  # could be a cheaper model

async def llm_judge(user_input: str, agent_output: str, rubric: str) -> bool:
    response = await client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=200,
        system=(
            "You are a strict evaluator. Read the rubric, score the agent's "
            "output, and return only the final pass/fail decision."
        ),
        messages=[{
            "role": "user",
            "content": (
                f"User input: {user_input}\n\n"
                f"Agent output: {agent_output}\n\n"
                f"Rubric: {rubric}\n\n"
                "Output exactly one word: PASS or FAIL."
            ),
        }],
    )
    text = response.content[0].text.strip().upper()
    return text.startswith("PASS")
```

Two-line prompt, binary decision. For continuous scores you'd ask for a 1-5 number; for this curriculum binary is enough.

## Stochastic averaging

Run each case N times; report the pass rate.

```python
async def run_case_n_times(case: dict, agent_path: str, n: int = 5) -> dict:
    runs = []
    for _ in range(n):
        result = await run_case(case, agent_path)
        traces = load_traces_for_run(result)  # filter by time window
        scored = await score(case, result, traces)
        runs.append(scored)
    pass_rate = sum(1 for r in runs if r["passed"]) / n
    return {
        "id": case["id"],
        "pass_rate": pass_rate,
        "runs": runs,
    }
```

Concurrency: in production, you'd run cases in parallel (`asyncio.gather` over cases) to keep eval suites fast. For a curriculum runner, sequential is fine.

## The full harness

```python
import asyncio
import yaml
import json
from pathlib import Path
from datetime import datetime, timezone


CASES_DIR = Path("evals/cases")
RESULTS_DIR = Path("evals/results")


async def main():
    case_files = sorted(CASES_DIR.glob("*.yaml"))
    cases = [yaml.safe_load(p.read_text()) for p in case_files]

    print(f"Running {len(cases)} cases × 5 runs each...")
    results = []
    for case in cases:
        r = await run_case_n_times(case, "agents/coding-agent/main.py", n=5)
        results.append(r)
        marker = "✓" if r["pass_rate"] == 1.0 else ("≈" if r["pass_rate"] >= 0.6 else "✗")
        print(f"  {marker} {r['id']}: {r['pass_rate']:.0%}")

    # Write a results file timestamped for regression tracking
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_file = RESULTS_DIR / f"{timestamp}.json"
    out_file.write_text(json.dumps({
        "timestamp": timestamp,
        "results": results,
    }, indent=2, default=str))
    print(f"\nResults: {out_file}")

    overall = sum(r["pass_rate"] for r in results) / len(results)
    print(f"Overall pass rate: {overall:.1%}")


if __name__ == "__main__":
    asyncio.run(main())
```

Save as `evals/run.py`. `uv run evals/run.py` runs the suite and stores results.

## Regression tracking

Each run produces a timestamped JSON file in `evals/results/`. To track regression, compare two runs:

```python
def diff(prev_path, curr_path):
    prev = {r["id"]: r["pass_rate"] for r in json.loads(Path(prev_path).read_text())["results"]}
    curr = {r["id"]: r["pass_rate"] for r in json.loads(Path(curr_path).read_text())["results"]}
    for case_id in sorted(set(prev) | set(curr)):
        p = prev.get(case_id, 0.0)
        c = curr.get(case_id, 0.0)
        delta = c - p
        if delta < -0.1:
            print(f"  ⚠ {case_id}: {p:.0%} → {c:.0%}  REGRESSION")
        elif delta > 0.1:
            print(f"  + {case_id}: {p:.0%} → {c:.0%}")
```

In CI, this comparison gates merges. A change that drops pass rate by more than a threshold blocks the PR.

## A starter test set

`evals/cases/read-version.yaml`:

```yaml
id: read-pyproject-version
description: Agent reads pyproject.toml and reports the Python version
input: "What's the Python version requirement in pyproject.toml?"
checks:
  - type: contains
    value: "3.13"
  - type: tool_used
    tool: read
  - type: tool_count_max
    value: 3
tags: [read, file-tools]
```

`evals/cases/find-todos.yaml`:

```yaml
id: find-todos
description: Agent enumerates TODO comments in the codebase
input: "Are there any TODO comments in this codebase? List them."
checks:
  - type: tool_used
    tool: grep
  - type: llm_judge
    rubric: |
      Did the agent enumerate TODOs accurately based on the grep output?
      The answer should reference specific files and lines if any TODOs exist,
      or clearly state that none exist.
tags: [grep, multi-step]
```

`evals/cases/handle-missing-file.yaml`:

```yaml
id: handle-missing-file
description: Agent recovers gracefully when asked to read a nonexistent file
input: "What's in the file does-not-exist.xyz?"
checks:
  - type: contains
    value: "doesn't exist"
  - type: tool_count_max
    value: 5
tags: [error-recovery]
```

Start with 5-10 cases like these. Add more as the agent encounters new behaviors you want pinned.

## Trade-offs to know

**Subprocess vs. in-process.** Subprocess gives perfect isolation but adds startup cost (~1s per case) and complicates trace correlation. In-process is faster but requires careful state reset between cases. Subprocess is the right default for a curriculum and most production cases.

**Trace correlation across runs.** We assume `traces.jsonl` is shared across runs and we filter by time window. With concurrent runs, this gets messy — better to point each run at its own trace file via env var.

**Cost.** Every case run is N × (agent inference + judge inference). 50 cases × 5 runs × 2 inferences each = 500 inferences per eval suite. Cache aggressively (Module 20 helps).

**Stability of the judge.** A judge model that itself shifts behavior over time (e.g., a model upgrade) breaks the regression signal. Pin the judge model version separately from the agent's model.

## What this didn't address

- **Eval datasets at scale.** Real production eval suites have hundreds to thousands of cases, often generated semi-automatically from production traces. Pipeline for collecting/curating those is its own thing.
- **Cost-aware scheduling.** Running the full suite for every PR is expensive. Production CI often runs a "smoke" subset on every PR and the full suite on main only.
- **Eval feedback into prompts.** Module 22 (Prompt design) closes the loop — eval scores drive prompt iteration.

## Prompt your coding agent

If you want your coding agent to write this for you, paste:

```
Build an eval harness in evals/.

1. Create evals/cases/ with sample YAML test cases (read-pyproject-version, find-todos, handle-missing-file). Each has: id, description, input, checks (list of {type, ...}). Check types: contains, tool_used, tool_count_max, llm_judge (with rubric).

2. Create evals/run.py with:
   - run_case(case, agent_path): subprocess to `uv run <agent_path>`, pipe `case["input"]\n/q\n`, capture stdout. Return {id, stdout, stderr, exit_code}.
   - score(case, result, traces): apply each check; for "llm_judge" call a binary llm_judge() helper. Return {id, passed, checks}.
   - run_case_n_times(case, agent_path, n=5): run + score N times, compute pass_rate.
   - main(): glob evals/cases/*.yaml, run each n times, print marker (✓ ≈ ✗), write results to evals/results/<timestamp>.json.

3. Add llm_judge(user_input, agent_output, rubric) using AsyncAnthropic; system: "You are a strict evaluator..."; ask for PASS or FAIL.

4. Add a diff tool (evals/diff.py) that compares two timestamped result files and prints regressions / improvements >10%.

Don't change the agent itself.
```

The prompt tells your agent *what* to write. The module explains *why* — read it first.

---

**Next:** [Module 20: Cost optimization](../../../part-07/modules/20-cost-optimization/)
