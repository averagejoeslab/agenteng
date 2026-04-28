# Sandboxing

The agent has `bash`. That tool runs arbitrary commands on the host with the user's permissions. For a curriculum running locally in a project you control, that's tolerable. For anything you'd actually deploy — running on shared infrastructure, executing user-provided prompts, putting the agent in an environment with credentials it shouldn't touch — it's not.

This module containerizes the `bash` tool. The agent runs commands inside a Docker container with no network, a read-only root filesystem, capped CPU and memory, and a non-root user. The agent can do its work without ability to harm the host.

## What sandboxing buys

Concrete protections against:

- **Filesystem damage outside the project.** The container only mounts the project directory. `rm -rf /` inside the container is contained.
- **Network exfiltration.** The container has `--network none`. Even if a tool result contains credentials, no process inside can reach the network to exfiltrate them.
- **Privilege escalation.** Non-root user, `--cap-drop ALL`, `--security-opt no-new-privileges`.
- **Resource exhaustion.** Memory cap, CPU cap, PID limit prevent fork bombs and runaway loops.
- **Persistence between runs.** `--rm` removes the container on exit; nothing persists outside the mounted volume.

What it doesn't protect: a malicious prompt that gets the model to delete files inside the mounted project directory. The agent has legitimate write access there. Approval gates (Module 15) handle that surface.

## The sandbox image

A minimal Debian-based image with the tools the agent needs (`bash`, `coreutils`, `grep`, `find`, etc.). Save as `Dockerfile.sandbox`:

```dockerfile
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash coreutils findutils grep ripgrep \
 && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd -m -u 1000 agent
USER agent
WORKDIR /workspace
```

Build it once:

```bash
docker build -f Dockerfile.sandbox -t coding-agent-sandbox .
```

The image is tiny (~100MB) and reused across all `bash` invocations.

## The sandboxed bash tool

A long-running container we exec commands into beats spinning up a new container per call (slow). Pattern:

1. **Start a container at agent startup.** Long-running, idle.
2. **`docker exec` for each `bash` call.** Cheap.
3. **Stop the container at agent exit.** Clean up.

```python
import subprocess
import secrets

SANDBOX_IMAGE = "coding-agent-sandbox"
_container_name = None


def start_sandbox(workspace: str) -> str:
    """Start a long-running sandbox container. Returns container ID."""
    global _container_name
    _container_name = f"coding-agent-{secrets.token_hex(8)}"
    subprocess.run([
        "docker", "run", "-d", "--rm",
        "--name", _container_name,
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--network", "none",
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=100m",
        "-v", f"{workspace}:/workspace",
        "-w", "/workspace",
        "--memory", "512m",
        "--cpus", "1.0",
        "--pids-limit", "100",
        "--user", "1000:1000",
        SANDBOX_IMAGE,
        "sleep", "infinity",
    ], check=True, capture_output=True)
    return _container_name


def stop_sandbox():
    if _container_name:
        subprocess.run(
            ["docker", "stop", _container_name],
            check=False, capture_output=True, timeout=5,
        )


async def bash(cmd: str) -> str:
    """Run a shell command inside the sandbox."""
    try:
        result = subprocess.run(
            ["docker", "exec", _container_name, "bash", "-c", cmd],
            capture_output=True, text=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        return "error: command timed out after 30s"
    out = result.stdout + result.stderr
    return out.strip() or f"(exit {result.returncode})"
```

Six flags worth knowing:

| Flag | What it does |
|---|---|
| `--cap-drop ALL` | Drops all Linux capabilities |
| `--security-opt no-new-privileges` | Prevents `setuid` from elevating |
| `--network none` | No network interfaces inside the container |
| `--read-only` | Root filesystem is read-only (writes only to the tmpfs and the mounted volume) |
| `--tmpfs /tmp:rw,noexec,nosuid,size=100m` | Writable but non-executable temp space, capped at 100MB |
| `--user 1000:1000` | Run as the unprivileged user from the Dockerfile, not root |

Plus resource caps (`--memory`, `--cpus`, `--pids-limit`) and `--rm` for cleanup.

## Wiring into the agent

Three changes to the Module 13 agent:

1. **Start the sandbox at agent startup**, before the REPL begins.
2. **Replace the bash tool's body** to use `docker exec` instead of `subprocess.run` directly.
3. **Stop the sandbox at exit** — register an `atexit` handler.

```python
import atexit

async def main():
    workspace = os.getcwd()
    start_sandbox(workspace)
    atexit.register(stop_sandbox)

    messages = load_messages()
    # ... rest of main unchanged ...
```

Other tools (`read`, `write`, `edit`, `grep`, `glob`) still run on the host. They access the same workspace mounted into the sandbox at `/workspace`, so the views match. Only `bash` — the catastrophic-damage surface — runs inside the container.

## Trade-offs to know

**Docker dependency.** The user needs Docker running. Real production agents add fallback paths (run unsandboxed in trusted environments, refuse to start in untrusted ones).

**Host file writes from non-bash tools.** `write` and `edit` still run on the host. They're constrained to whatever path the agent runs from, but they're not isolated from the host filesystem. For full isolation, every tool that touches the filesystem should run in the container — at the cost of needing the agent's Python runtime inside too. Most production coding agents accept this trade and trust the file tools.

**Performance.** `docker exec` per call adds tens of milliseconds. For interactive use it's imperceptible. For tight inner loops it can matter.

**Network in the sandbox.** `--network none` means no `pip install`, no `curl`, no `git pull` inside the sandbox. If the agent legitimately needs network access for some workflows, you'd run a second container with selective network access for those tools — and accept the larger surface.

## What this didn't address

- **Per-tool permissions.** Sandboxing is binary — bash is contained or not. Real production has graduated trust: this tool can read but not write, that tool can write to specific paths. Approval gates (Module 15) handle some of this.
- **Workspace integrity.** Inside the sandbox, the agent can still corrupt files in the mounted workspace. The sandbox protects the *host*, not the project.
- **Image management.** The image is built manually here. Production code should rebuild on Dockerfile changes and pin to a digest for reproducibility.

## Prompt your coding agent

If you want your coding agent to write this for you, paste:

```
Containerize the bash tool. The other tools (read, write, edit, grep, glob) keep running on the host.

1. Add a Dockerfile.sandbox in the project root:
   - FROM debian:bookworm-slim
   - Install bash, coreutils, findutils, grep, ripgrep
   - Create a non-root user (uid 1000), set as USER, set WORKDIR /workspace

2. Build the image once: `docker build -f Dockerfile.sandbox -t coding-agent-sandbox .`

3. In main.py, add a sandbox manager:
   - start_sandbox(workspace) runs `docker run -d --rm` with: --cap-drop ALL, --security-opt no-new-privileges, --network none, --read-only, --tmpfs /tmp:rw,noexec,nosuid,size=100m, -v workspace:/workspace, -w /workspace, --memory 512m, --cpus 1.0, --pids-limit 100, --user 1000:1000, image=coding-agent-sandbox, command=sleep infinity. Save the random container name in a module-level variable.
   - stop_sandbox() runs `docker stop <name>` with a short timeout, swallows errors.

4. Replace bash() to dispatch via `docker exec <name> bash -c <cmd>` instead of running on the host. Keep the 30s timeout and the same return shape.

5. In main(), call start_sandbox(os.getcwd()) at startup and atexit.register(stop_sandbox).

Don't change other tools.
```

The prompt tells your agent *what* to write. The module explains *why* — read it first.

---

**Next:** [Module 15: Approval gates and loop bounds](../15-approval-gates-and-loop-bounds/)
