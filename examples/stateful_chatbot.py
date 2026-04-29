import os
import json
from pathlib import Path
from anthropic import Anthropic
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import numpy as np

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

MODEL = "claude-sonnet-4-5"
SUMMARY_MODEL = "claude-haiku-4-5"
CONTEXT_BUDGET = 150_000
RECALL_K = 3
RECALL_THRESHOLD = 0.3

STATE_DIR = Path.home() / ".stateful-chatbot"
MESSAGES_FILE = STATE_DIR / "messages.json"
RECALL_FILE = STATE_DIR / "recall.json"


# --- Persistence ---

def _serialize(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    raise TypeError(f"can't serialize {type(obj)}")


def load_messages() -> list:
    if not MESSAGES_FILE.exists():
        return []
    try:
        return json.loads(MESSAGES_FILE.read_text())
    except json.JSONDecodeError as e:
        print(f"warning: {MESSAGES_FILE} is corrupt ({e}); starting fresh")
        return []


def save_messages(messages: list) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    MESSAGES_FILE.write_text(json.dumps(messages, default=_serialize, indent=2))


# --- Token budget ---

def find_safe_truncation_point(messages: list, drop_n: int = 1) -> int:
    boundaries = [i for i, msg in enumerate(messages) if msg["role"] == "user"]
    if drop_n >= len(boundaries):
        return boundaries[-1] if boundaries else 0
    return boundaries[drop_n]


def trim_to_budget(messages: list, budget: int, system: str) -> list:
    while True:
        count = client.messages.count_tokens(
            model=MODEL, system=system, messages=messages,
        )
        if count.input_tokens <= budget or len(messages) <= 1:
            return messages
        truncate_at = find_safe_truncation_point(messages, drop_n=1)
        if truncate_at == 0:
            return messages
        messages = messages[truncate_at:]


# --- Semantic recall ---

print("Loading embedding model...")
_embed_model = SentenceTransformer("all-MiniLM-L6-v2")


def embed(text: str) -> np.ndarray:
    return _embed_model.encode(text, convert_to_numpy=True, normalize_embeddings=True)


def load_recall() -> list[dict]:
    if not RECALL_FILE.exists():
        return []
    try:
        return json.loads(RECALL_FILE.read_text())
    except json.JSONDecodeError:
        return []


def save_recall(entries: list[dict]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    RECALL_FILE.write_text(json.dumps(entries))


def add_to_recall(text: str, entries: list[dict]) -> None:
    vec = embed(text)
    entries.append({"text": text, "embedding": vec.tolist()})
    save_recall(entries)


def recall(query: str, entries: list[dict],
           k: int = RECALL_K, threshold: float = RECALL_THRESHOLD) -> list[str]:
    if not entries:
        return []
    q_vec = embed(query)
    scored = []
    for e in entries:
        e_vec = np.array(e["embedding"])
        score = float(np.dot(q_vec, e_vec))
        scored.append((score, e["text"]))
    scored.sort(reverse=True)
    return [text for score, text in scored[:k] if score >= threshold]


def summarize_turn(turn_messages: list) -> str:
    response = client.messages.create(
        model=SUMMARY_MODEL,
        max_tokens=200,
        system=("You write one-paragraph summaries of conversations. "
                "Capture what the user asked and what was discussed. No fluff."),
        messages=[{"role": "user", "content":
                   f"Summarize this exchange:\n\n"
                   f"{json.dumps(turn_messages, default=_serialize)[:8000]}"}],
    )
    return response.content[0].text


# --- Main loop ---

BASE_SYSTEM = "You are a helpful assistant."


def main():
    messages = load_messages()
    recall_entries = load_recall()

    while True:
        user_input = input("❯ ")
        if user_input.lower() in ("/q", "exit"):
            break

        recalled = recall(user_input, recall_entries)
        if recalled:
            memory_block = "\n\n".join(f"- {s}" for s in recalled)
            system = f"{BASE_SYSTEM}\n\n## Relevant memory from past conversations\n\n{memory_block}"
        else:
            system = BASE_SYSTEM

        messages.append({"role": "user", "content": user_input})
        messages = trim_to_budget(messages, CONTEXT_BUDGET, system)
        turn_start = len(messages) - 1

        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system,
            messages=messages,
        )
        assistant_text = response.content[0].text
        messages.append({"role": "assistant", "content": assistant_text})
        print(assistant_text)

        save_messages(messages)

        turn_messages = messages[turn_start:]
        summary = summarize_turn(turn_messages)
        add_to_recall(summary, recall_entries)


main()
