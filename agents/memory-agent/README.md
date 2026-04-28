# memory-agent

Adds **persistence**, **token budget management**, and **semantic recall** to the coding-agent. The end state of [Module 5: Add memory](../../modules/05-add-memory/).

Built on top of `coding-agent`, with three concerns added:

- **Persistent memory** — JSON-file message storage at `~/.memory-agent/messages.json`, saved on user-turn boundaries.
- **Context as a budget** — the `count_tokens` API plus eviction by complete user turns to preserve `tool_use`/`tool_result` pairing.
- **Semantic recall** — `sentence-transformers` embeddings (`all-MiniLM-L6-v2`), a JSON vector store, top-K cosine similarity recall, with per-turn summaries injected into the system prompt.

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
