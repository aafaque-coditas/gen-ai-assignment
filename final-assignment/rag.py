"""
Final Assignment - RAG over Session 3's already-ingested document
=======================================================================
Reuses Session 3's vector_store.py and index.json directly, the same
"no duplicated data" rule session-4's search_docs tool already followed one
session earlier (session-4/tools.py wires straight into session-3's index
instead of re-ingesting the PDF). The source document is
../session-3/docs/DS- Technical Case Study.pdf; this file queries
../session-3/index.json, Session 3's real, already-built index, rather than
re-running ingest.py against the same PDF a third time.

Chosen document, and why: a README, policy doc, or paper of my own would
work too, but this repo already has one real, non-trivial technical
document with a working RAG index behind it (session-3), and reusing it here
is exactly the kind of cross-session integration this capstone assignment
is designed to force -- Session 3's RAG index feeding this assignment's
planner, the same way it already feeds session-4's agent and session-5's
debrief notes.
"""

import sys
from pathlib import Path

SESSION_3_DIR = Path(__file__).resolve().parent.parent / "session-3"
sys.path.insert(0, str(SESSION_3_DIR))
from vector_store import VectorStore  # noqa: E402

INDEX_PATH = SESSION_3_DIR / "index.json"
_STORE_CACHE = {}


def load_store() -> VectorStore:
    if INDEX_PATH not in _STORE_CACHE:
        if not INDEX_PATH.exists():
            raise FileNotFoundError(
                f"No Session 3 index at {INDEX_PATH}. Run `python ingest.py` in session-3/ first."
            )
        _STORE_CACHE[INDEX_PATH] = VectorStore.load(INDEX_PATH)
    return _STORE_CACHE[INDEX_PATH]


def retrieve(client, embed_fn, query: str, k: int = 4) -> list:
    """Top-k retrieval for one section's query. Returns
    [{"text", "metadata", "score"}, ...]."""
    store = load_store()
    query_vec = embed_fn(client, [query])[0]
    return store.search(query_vec, k=k)


def format_context(results: list) -> str:
    """Renders retrieved chunks WITH their source/page/score, so every
    downstream LLM call can cite what it actually used -- the "answers
    cited from context" requirement."""
    return "\n---\n".join(
        f"[{r['metadata']['source']} p.{r['metadata']['page']} #{r['metadata']['chunk_index']} score={r['score']:.3f}]\n{r['text']}"
        for r in results
    )


def all_chunks_context() -> str:
    """The whole indexed document, concatenated. Used for the outline stage
    and the critic stage: this corpus is only 6 chunks from a 6-page PDF
    (session-3's README explains why it stayed an in-memory list under the
    ~5k-chunk "Learning" ceiling), small enough to hand the model the entire
    source rather than a per-section retrieval slice, so outlining and
    fact-checking see the full picture, not just whatever one query
    happened to retrieve."""
    store = load_store()
    return "\n---\n".join(
        f"[p.{item['metadata']['page']} #{item['metadata']['chunk_index']}]\n{item['text']}" for item in store.items
    )
