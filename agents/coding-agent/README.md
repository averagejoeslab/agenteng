# coding-agent

The multi-tool coding agent Part 2 produces. Same REPL + TAO loop as `basic-agent`, plus a tool registry, a six-tool toolkit (`read`, `write`, `edit`, `grep`, `glob`, `bash`), and a centralized executor that handles errors for all tools.

Built on top of Part 1, refined across Modules 5–8:

- **[Module 5: Tool design](../../agentic-engineering/part-02/modules/05-tool-design/)** — the components of a function tool and what makes a good one
- **[Module 6: The tool registry](../../agentic-engineering/part-02/modules/06-the-tool-registry/)** — the `TOOLS` dict + schema factory + dispatcher
- **[Module 7: Building the toolkit](../../agentic-engineering/part-02/modules/07-building-the-toolkit/)** — implementing the six tools
- **[Module 8: The tool executor](../../agentic-engineering/part-02/modules/08-the-tool-executor/)** — centralizing error handling in the executor; tools become thin (this agent's end state)

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

- `main.py` — the agent (~160 lines, built across Modules 5–8)

Dependencies, venv, and `.env` live at the `agents/` level.

> [!WARNING]
> `bash` runs arbitrary commands on the host. Don't use this on prompts from untrusted sources.
