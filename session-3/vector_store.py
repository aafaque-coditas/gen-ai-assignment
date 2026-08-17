"""
A plain in-memory vector store: brute-force cosine similarity over a
Python list of (embedding, text, metadata) records, persisted as JSON.

Per the vector-database guidance: "In-memory list -- Learning, under ~5k
chunks" is an explicitly sanctioned option, and this corpus is a handful
of chunks from one PDF -- nowhere near that ceiling.
No extra dependency (no chromadb/onnxruntime), and the whole index is
small enough that rebuilding it from scratch takes about a second.
"""

import json
import math


def cosine_similarity(a: list, b: list) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class VectorStore:
    def __init__(self):
        self.items = []  # list of {"embedding": [...], "text": str, "metadata": {...}}

    def add(self, embedding: list, text: str, metadata: dict):
        self.items.append({"embedding": embedding, "text": text, "metadata": metadata})

    def search(self, query_embedding: list, k: int = 3) -> list:
        """Return the top-k items by cosine similarity: {"text", "metadata", "score"}.
        Deliberately drops the stored embedding from the result -- callers
        (logging, prompts, citations) only ever need the text/metadata/score,
        and there's no reason to carry a 1536-float vector through the rest
        of the pipeline just to have it sit there unused."""
        scored = [
            {
                "text": item["text"],
                "metadata": item["metadata"],
                "score": cosine_similarity(query_embedding, item["embedding"]),
            }
            for item in self.items
        ]
        scored.sort(key=lambda r: r["score"], reverse=True)
        return scored[:k]

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.items, f)

    @classmethod
    def load(cls, path):
        store = cls()
        with open(path, "r", encoding="utf-8") as f:
            store.items = json.load(f)
        return store

    def __len__(self):
        return len(self.items)
