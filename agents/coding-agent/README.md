# coding-agent

The multi-tool coding agent. Same REPL + TAO loop as `basic-agent`, plus a tool registry, a six-tool toolkit (`read`, `write`, `edit`, `grep`, `glob`, `bash`), and a centralized executor that handles errors for all tools. The end state of [Module 4: Add tools](../../modules/04-add-tools/).

Built on top of `basic-agent`, refined across:

- **[Module 4: Add tools](../../modules/04-add-tools/)** — tool design principles, the registry pattern, the six-tool toolkit, and a centralized executor

## Run it

From the `agents/` directory (one level up):

```bash
uv run coding-agent/main.py
```

Then at the `❯` prompt — try prompts that need multiple tools:

```
❯ What Python files are in this project?
❯ Does either import the anthropic package?
❯ Read the first 20 lines of basic-agent/main.py
❯ Run: ls -la
❯ /q
```

The model chains tools as needed (`glob` → `read`, `grep` → `edit`, etc.) to complete multi-step tasks.

## Tools

| Tool | Purpose |
|---|---|
| `read` | Read the contents of a file |
| `write` | Create or overwrite a file |
| `edit` | Find-and-replace in a file (refuses ambiguous matches) |
| `grep` | Regex search file contents under a directory |
| `glob` | Find files by pattern (supports `**` recursive) |
| `bash` | Run a shell command (30s timeout) |

## Files

- `main.py` — the agent (~160 lines)

Dependencies, venv, and `.env` live at the `agents/` level.

> [!WARNING]
> `bash` runs arbitrary commands on the host. Don't use this on prompts from untrusted sources.
