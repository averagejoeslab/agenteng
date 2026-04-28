# Semantic recall

Module 12 keeps the active conversation under a token budget by evicting the oldest exchanges. Eviction is destructive — once dropped, content is gone from the agent's awareness. That's fine for a single long session, but for an agent that runs across days and weeks, useful information from old conversations gets thrown away.

This module adds **semantic recall**: keep an external store of past conversations, embed them as vectors, and retrieve the relevant ones at the start of each new turn based on similarity to the user's input. The agent gains long-term memory without ballooning the active context.

## What semantic recall buys

Concrete examples of what becomes possible:

- *"Last week we decided to use the registry pattern. Why?"* — the agent retrieves the prior exchange that established the decision.
- *"What was that bash command you suggested for cleaning .pyc files?"* — pulls the specific command from a past session.
- *"Continue the refactor we started on auth.py"* — the agent recalls what was in progress.

None of this requires the old conversation to fit in current context. The retrieval system pulls only the relevant slice.

## The mechanism: embeddings + similarity search

An **embedding** is a fixed-length vector that represents the semantic content of a piece of text. Texts with similar meanings have vectors close together in that space; unrelated texts are far apart. *"How do I read a file?"* and *"What's the syntax for opening files?"* embed to nearby vectors even though they share few words.

Pattern:

1. **Save:** when a turn or session ends, embed a summary of the exchange and store `(embedding, text)` to disk.
2. **Recall:** at the start of each new user turn, embed the user's input, find the top-K most similar past entries by cosine similarity, and inject them into the prompt.
3. **The agent answers** with both the active context and the recalled snippets available to it.

The retrieval doesn't need to be exact — top-K nearest is enough. The model can ignore irrelevant snippets.

## Embedding model

We need a function `embed(text) -> vector`. Three reasonable choices:

| Option | Pros | Cons |
|---|---|---|
| Local (`sentence-transformers`, e.g. `all-MiniLM-L6-v2`) | No API key, fast, private | ~80MB model download, embeddings are mediocre vs. cloud models |
| Voyage AI (`voyage-3-lite`) | Anthropic-recommended; high quality | Another API key |
| OpenAI (`text-embedding-3-small`) | High quality, cheap | Another API key |

For this module we use **local sentence-transformers** to keep dependencies self-contained. The interface is the same regardless of provider — swap one line of code to switch.

```bash
uv add sentence-transformers
```

(This pulls in PyTorch as a transitive dependency. Heavy but standard.)

```python
from sentence_transformers import SentenceTransformer
import numpy as np

_model = SentenceTransformer("all-MiniLM-L6-v2")

def embed(text: str) -> np.ndarray:
    return _model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
```

`normalize_embeddings=True` makes vectors unit-length, so cosine similarity reduces to a dot product.

## The store

For a curriculum agent, an in-memory list backed by a JSON file is enough:

```python
import json
import numpy as np
from pathlib import Path

RECALL_FILE = Path.home() / ".coding-agent" / "recall.json"


def load_recall() -> list[dict]:
    """Returns list of {"text": str, "embedding": list[float]}."""
    if not RECALL_FILE.exists():
        return []
    try:
        return json.loads(RECALL_FILE.read_text())
    except json.JSONDecodeError:
        return []


def save_recall(entries: list[dict]) -> None:
    RECALL_FILE.parent.mkdir(parents=True, exist_ok=True)
    RECALL_FILE.write_text(json.dumps(entries))


def add_to_recall(text: str, entries: list[dict]) -> None:
    vec = embed(text)
    entries.append({"text": text, "embedding": vec.tolist()})
    save_recall(entries)
```

Embeddings are stored as plain lists in JSON. For thousands of entries this gets slow — production code should move to a real vector store (sqlite-vss, lance, qdrant, pgvector). For dozens to hundreds of past exchanges, JSON is fine.

## Similarity search

```python
def recall(query: str, entries: list[dict], k: int = 3, threshold: float = 0.3) -> list[str]:
    if not entries:
        return []
    q_vec = embed(query)
    scored = []
    for e in entries:
        e_vec = np.array(e["embedding"])
        score = float(np.dot(q_vec, e_vec))   # cosine similarity (vectors normalized)
        scored.append((score, e["text"]))
    scored.sort(reverse=True)
    return [text for score, text in scored[:k] if score >= threshold]
```

Two knobs:

- **`k`** — how many results to return. 3 is a reasonable starting point; too many crowds the prompt, too few misses things.
- **`threshold`** — minimum similarity to count as relevant. 0.3 filters out noise. Set higher for stricter recall, lower if results feel too sparse.

## What to embed: the exchange-summary problem

Don't embed individual messages — too granular, lots of tool_result blocks that are uninteresting on their own. Don't embed the full conversation — too much, the embedding becomes a smear.

The right granularity is one **summary per completed user turn**: a short text that captures what the user asked and what the agent did. Generate it from the same model:

```python
async def summarize_turn(turn_messages: list) -> str:
    """Generate a one-paragraph summary of a completed user turn."""
    response = await client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=200,
        system="You write one-paragraph summaries of agent conversations. Capture what the user asked and what was concluded or done. No fluff.",
        messages=[
            {
                "role": "user",
                "content": f"Summarize this exchange:\n\n{json.dumps(turn_messages, default=str)[:8000]}",
            }
        ],
    )
    return response.content[0].text
```

One extra LLM call per turn. Acceptable cost for the recall capability — it runs after the user got their answer, so it doesn't add latency to the response.

## Wiring into the agent

Three additions to the Module 12 coding-agent:

1. **Load recall entries on startup:** `recall_entries = load_recall()` near the top of `main()`.
2. **Inject recalled snippets into the system prompt** at the start of each user turn:
   ```python
   recalled = recall(user_input, recall_entries)
   system = "You are a helpful coding assistant."
   if recalled:
       memory_block = "\n\n".join(f"- {s}" for s in recalled)
       system = f"{system}\n\nRelevant memory from past conversations:\n{memory_block}"
   ```
3. **Summarize and store after each turn completes** (after the inner TAO loop exits and after `save_messages`):
   ```python
   turn_start = previous_messages_count   # capture before appending the turn
   turn_messages = messages[turn_start:]
   summary = await summarize_turn(turn_messages)
   add_to_recall(summary, recall_entries)
   ```

The system prompt now varies per turn. The `client.messages.create(...)` call passes the dynamic `system` value rather than a constant.

## Running it

Session 1:

```
❯ I'm refactoring auth.py to extract the token validation into a separate function called validate_jwt.
[agent does the work]
❯ /q
```

A summary like *"User refactored auth.py to extract JWT token validation into a separate function called validate_jwt."* gets embedded and saved to `~/.coding-agent/recall.json`.

Session 2 (could be the next day):

```
❯ Where did we put the JWT validation logic?
```

The agent's recall function embeds *"Where did we put the JWT validation logic?"*, finds the prior summary by similarity, and injects it into the system prompt for this turn. The model can answer: *"In `auth.py`, in the `validate_jwt` function we extracted yesterday."*

The information was recalled across sessions, even though Module 12's eviction may have dropped the original exchange from the active context long ago.

## Trade-offs to know

**Embedding model quality.** `all-MiniLM-L6-v2` is small and fast but mediocre. For production, voyage-3-lite or text-embedding-3-small produce better recall. The integration is identical — swap the `embed` function.

**Vector store at scale.** A flat JSON file works for hundreds of entries. Beyond that, switch to sqlite-vss, lance, or a managed service like Qdrant. The recall function's interface stays the same.

**Granularity of summaries.** One per turn is a coarse choice. Too coarse and you lose specifics ("what was the exact bash command?"). Too fine (per-message) and the store fills up with noise. Production agents often summarize at multiple granularities — one summary per turn, one summary per session.

**Recall threshold tuning.** Setting threshold too low → noise floods the system prompt. Too high → relevant memories don't surface. Worth tuning against actual user behavior.

**Stale memories.** A recalled summary from six months ago might be obsolete (the code changed). Production memory systems often track recency and decay scores over time — not implemented here.

## What this didn't address

- **Persistence schema migrations.** If the embedding model changes, all old vectors are incompatible. Production code versions the store and re-embeds on upgrade.
- **Multi-modal recall.** Just text here. Real agents may need to recall code snippets, images, structured data. The embedding model has to support those modalities.
- **Privacy controls.** All conversation summaries get embedded and stored. If anything sensitive flowed through (credentials, PII), it's now searchable in the recall store. Part 4 (Safety) addresses this surface.

## Prompt your coding agent

If you want your coding agent to write this for you, paste:

```
Add semantic recall to main.py.

1. Add `sentence-transformers` to dependencies (`uv add sentence-transformers`).

2. Create an embedding helper:
   - from sentence_transformers import SentenceTransformer
   - Initialize a module-level `_model = SentenceTransformer("all-MiniLM-L6-v2")`
   - `def embed(text: str) -> np.ndarray` returning a normalized vector (normalize_embeddings=True).

3. Create a recall store backed by a JSON file at ~/.coding-agent/recall.json:
   - load_recall() returns a list of {"text": str, "embedding": list[float]}.
   - save_recall(entries) writes the list as JSON.
   - add_to_recall(text, entries) embeds, appends, saves.

4. Add `recall(query, entries, k=3, threshold=0.3)`:
   - Embed the query.
   - Compute dot product with every stored embedding (vectors are unit-normalized so dot product = cosine similarity).
   - Return the top-K texts with score >= threshold.

5. Add `async def summarize_turn(turn_messages)`:
   - One-shot LLM call (system: "You write one-paragraph summaries..."; user: the JSON-serialized turn messages, truncated if needed).
   - Return the response's first text block.

6. In main():
   - Load recall_entries on startup.
   - At the start of each user turn (after appending user_input), call recall() and inject results into the system prompt for that turn's LLM calls.
   - After the inner TAO loop exits and save_messages runs, summarize the turn (the new messages added this turn) and add_to_recall.

7. Don't change the TAO loop or the executor — only the system prompt and post-turn hook.
```

The prompt tells your agent *what* to write. The module explains *why* — read it first.

---

**Next:** [Module 14: Sandboxing](../../../part-04/modules/14-sandboxing/)
