# memory-agent

The Part 3 end state. Adds **persistence**, **token budget management**, and **semantic recall** to the coding-agent.

Built across Modules 11–13:

- **[Module 11: Persistent memory](../../agentic-engineering/part-03/modules/11-persistent-memory/)** — JSON-file message storage at `~/.memory-agent/messages.json`, save on user-turn boundaries.
- **[Module 12: Context as a budget](../../agentic-engineering/part-03/modules/12-context-as-a-budget/)** — `count_tokens` API, eviction by complete user turns to preserve `tool_use`/`tool_result` pairing.
- **[Module 13: Semantic recall](../../agentic-engineering/part-03/modules/13-semantic-recall/)** — `sentence-transformers` embeddings (`all-MiniLM-L6-v2`), JSON vector store, top-K cosine similarity recall, per-turn summaries injected into the system prompt.

## Run it

From the `agents/` directory:

```bash
uv run memory-agent/main.py
```

The first run downloads the embedding model (~80MB). Subsequent runs are fast.

## State files

- `~/.memory-agent/messages.json` — current conversation, persisted across REPL restarts
- `~/.memory-agent/recall.json` — embedded summaries of past turns for semantic recall

## What's new vs. coding-agent

- Conversation survives REPL restarts.
- Long sessions stay under the context window via budget-aware eviction.
- Past sessions can be recalled by semantic similarity to the current query.

## What this didn't address

- `bash` runs on the host with no sandbox — see `safe-agent`.
