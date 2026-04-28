# safe-agent

The Part 4 end state. Adds **sandboxing** and **safety guards** to the memory-agent.

Built across Modules 14–15:

- **[Module 14: Sandboxing](../../agentic-engineering/part-04/modules/14-sandboxing/)** — `bash` runs inside a Docker container with `--cap-drop ALL`, `--network none`, `--read-only`, resource caps. Long-running container, `docker exec` per call.
- **[Module 15: Approval gates and loop bounds](../../agentic-engineering/part-04/modules/15-approval-gates-and-loop-bounds/)** — `write`, `edit`, `bash` require user approval before each run. Sequential dispatch when any requested tool is dangerous. `MAX_ITERATIONS` cap on the inner loop. SDK retry/backoff on transient API errors.

## Run it

Requires Docker.

From the `agents/` directory:

```bash
uv run safe-agent/main.py
```

The first run builds the `agenteng-sandbox` Docker image (~30s). Subsequent runs reuse it.

## What's new vs. memory-agent

- `bash` runs inside a containerized sandbox — can't damage the host filesystem outside the mounted workspace, no network, no privileges.
- Before any destructive tool runs, the agent prompts for approval.
- The TAO loop caps at 30 iterations to prevent runaway behavior.
- API calls retry with exponential backoff on transient errors.

## What this didn't address

- No structured tracing — see `traced-agent`.
