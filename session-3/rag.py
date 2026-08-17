"""
Session 3 Assignment - RAG Query CLI (online phase)
======================================================

Retrieve -> Generate (the final 2 steps of the RAG pipeline), with the
core requirement plus all four stretch goals:

  Core:
    - CLI: question -> top-k retrieve -> LLM answer from context
    - Log the retrieved chunks (scores and source)
  Stretch:
    --compare-k   Compare k=1 vs k=10 for the same question
    --json        Structured {"answer", "citations"} output
    --stream      Stream the final answer token-by-token
    --rerank      Retrieve wide, LLM-rerank, keep the top k

Usage:
    python rag.py "What tech stack is the design system built on?"
    python rag.py "..." --k 5
    python rag.py "..." --rerank
    python rag.py "..." --json
    python rag.py "..." --stream
    python rag.py "..." --compare-k
    python rag.py                      # no question -> interactive loop
"""

import argparse
import json
from pathlib import Path

from llm_client import get_client, call_model, stream_model, embed_texts, DEFAULT_MODEL
from vector_store import VectorStore

INDEX_PATH = Path(__file__).resolve().parent / "index.json"

SYSTEM_PROMPT = (
    "You are a support agent answering questions about a technical case "
    "study document. Use ONLY the context below to answer. If the context "
    "is insufficient or unrelated to the question, say plainly that you "
    "cannot find the answer in the provided context -- do not guess."
)

ANSWER_MAX_TOKENS = 500
RERANK_MAX_TOKENS = 300


def load_store(index_path: Path = INDEX_PATH) -> VectorStore:
    if not index_path.exists():
        raise SystemExit(f"No index found at {index_path}. Run `python ingest.py` first.")
    return VectorStore.load(index_path)


def format_source(item: dict) -> str:
    meta = item["metadata"]
    return f"{meta['source']} p.{meta['page']} #{meta['chunk_index']}"


def log_retrieved(results: list, show_context: bool = False):
    print(f"Retrieved {len(results)} chunk(s):")
    for r in results:
        print(f"  score={r['score']:.3f}  {format_source(r)}")
        if show_context:
            print(f"    {r['text'][:200]}{'...' if len(r['text']) > 200 else ''}")


def rerank(client, model: str, question: str, candidates: list, k: int) -> list:
    """Ask the LLM to score each candidate chunk's relevance 0-10, keep the top k.
    A lightweight stand-in for a dedicated cross-encoder re-ranker."""
    listing = "\n\n".join(f"[{i}] {c['text']}" for i, c in enumerate(candidates))
    prompt = (
        f"Question: {question}\n\n"
        f"Below are {len(candidates)} candidate passages, each tagged [index]. "
        "Rate how relevant each passage is to answering the question, on a "
        "scale of 0 (irrelevant) to 10 (directly answers it).\n\n"
        f"{listing}\n\n"
        'Respond with ONLY a JSON object: {"scores": {"0": <int>, "1": <int>, ...}}'
    )
    reply = call_model(client, [{"role": "user", "content": prompt}], model, temperature=0.0, max_tokens=RERANK_MAX_TOKENS, json_mode=True)
    try:
        scores = json.loads(reply)["scores"]
    except (json.JSONDecodeError, KeyError, TypeError):
        # If the LLM reranker call itself misbehaves, fall back to the
        # original similarity order rather than crashing the query.
        return candidates[:k]

    # Rank by original list position, not by re-finding each candidate with
    # .index() -- that was both O(n) per comparison and unsafe if two
    # candidates ever happened to be equal (duplicate chunk content).
    ranked = sorted(enumerate(candidates), key=lambda pair: scores.get(str(pair[0]), 0), reverse=True)
    return [candidate for _, candidate in ranked[:k]]


def retrieve(client, store: VectorStore, question: str, k: int, use_rerank: bool, wide_k: int = 15) -> list:
    query_vec = embed_texts(client, [question])[0]
    if use_rerank:
        candidates = store.search(query_vec, k=wide_k)
        return rerank(client, DEFAULT_MODEL, question, candidates, k)
    return store.search(query_vec, k=k)


def build_messages(question: str, results: list, json_mode: bool) -> list:
    context = "\n---\n".join(f"[{format_source(r)}]\n{r['text']}" for r in results)
    if json_mode:
        instructions = (
            f"{SYSTEM_PROMPT}\n\nRespond with ONLY a JSON object of the shape "
            '{"answer": "<answer text>", "citations": [{"source": "<file>", "page": <int>}]}. '
            "citations must list only sources you actually used. If you cannot "
            'answer from the context, set "answer" to say so and "citations" to [].'
        )
    else:
        instructions = SYSTEM_PROMPT
    return [
        {"role": "system", "content": instructions},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
    ]


def answer_question(client, store: VectorStore, question: str, args, k: int = None) -> str:
    k = args.k if k is None else k
    results = retrieve(client, store, question, k, args.rerank)
    log_retrieved(results, show_context=args.show_context)

    messages = build_messages(question, results, args.json)

    if args.stream:
        print("\nAssistant: ", end="", flush=True)
        chunks = []
        for delta in stream_model(client, messages, DEFAULT_MODEL, temperature=0.0, max_tokens=ANSWER_MAX_TOKENS):
            chunks.append(delta)
            print(delta, end="", flush=True)
        print()
        return "".join(chunks)

    answer = call_model(client, messages, DEFAULT_MODEL, temperature=0.0, max_tokens=ANSWER_MAX_TOKENS, json_mode=args.json)
    print(f"\nAssistant: {answer}")
    return answer


def run_compare_k(client, store: VectorStore, question: str, args):
    # Pass k explicitly rather than mutating args.k -- args is shared with
    # the interactive loop's caller, and this way a comparison run can't
    # leave a stale k behind for whatever runs next.
    for k in (1, 10):
        print(f"\n{'=' * 20} k={k} {'=' * 20}")
        answer_question(client, store, question, args, k=k)


def run_interactive(client, store: VectorStore, args):
    print("RAG Query CLI -- type 'quit' or 'exit' to leave\n")
    while True:
        try:
            question = input("Question: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        if not question:
            continue
        if question.lower() in {"quit", "exit"}:
            print("Goodbye!")
            break
        if args.compare_k:
            run_compare_k(client, store, question, args)
        else:
            answer_question(client, store, question, args)
        print()


def parse_args():
    parser = argparse.ArgumentParser(description="RAG query CLI over the ingested docs")
    parser.add_argument("question", nargs="?", help="Question to ask (omit for interactive mode)")
    parser.add_argument("--k", type=int, default=3, help="Number of chunks to retrieve (default: 3)")
    parser.add_argument("--json", action="store_true", help="Structured {answer, citations} output")
    parser.add_argument("--stream", action="store_true", help="Stream the final answer token-by-token")
    parser.add_argument("--rerank", action="store_true", help="Retrieve wide, LLM-rerank, keep top k")
    parser.add_argument("--compare-k", action="store_true", help="Compare k=1 vs k=10 for this question")
    parser.add_argument("--show-context", action="store_true", help="Also print each retrieved chunk's text")
    parser.add_argument("--index", default="index.json", help="Index file to query (default: index.json)")
    args = parser.parse_args()

    if args.json and args.stream:
        # Streaming JSON is awkward: stream_model() has no JSON mode, so
        # combining the flags would silently stream plain prose while
        # ignoring --json -- fail loudly instead.
        parser.error("--json and --stream cannot be combined; stream prose or request JSON, not both.")

    return args


def main():
    args = parse_args()
    client = get_client()
    store = load_store(Path(__file__).resolve().parent / args.index)

    if args.question is None:
        run_interactive(client, store, args)
        return

    if args.compare_k:
        run_compare_k(client, store, args.question, args)
    else:
        answer_question(client, store, args.question, args)


if __name__ == "__main__":
    main()
