# Add sandboxing

> [!NOTE]
> **Coming soon.** This module is stubbed.

The agent from Module 5 has a `bash` tool that runs commands directly on the host machine. The model can write to your filesystem, install packages, exfiltrate data, or do worse — by mistake or by prompt injection. Production-grade agents put dangerous tools behind a sandbox.

## What this module will cover

- **The threat model.** What can go wrong when an LLM has shell access on your machine.
- **Docker as the sandbox.** Why containers are the right shape — isolated filesystem, no network, dropped capabilities.
- **`Dockerfile.sandbox`.** The image: minimal base, a working directory bind-mounted in, capabilities and network locked down.
- **Wiring `bash` into the container.** The tool builds the image on first run, then dispatches each command into a fresh container.
- **What's still on the host.** `read`, `write`, `edit`, `grep`, `glob` still touch the host filesystem; only `bash` is sandboxed. The discussion of where to draw that line.

## Reference: safe-agent

The end state for this module already lives at [`agents/safe-agent`](../../agents/safe-agent/). It runs `bash` inside a Docker container built from [`agents/Dockerfile.sandbox`](../../agents/Dockerfile.sandbox).

```bash
cd agents
uv run safe-agent/main.py
```

Requires Docker to be running.

---

**Next:** [Module 7: Add evaluation](../07-add-evaluation/)
