"""
Session 3 Assignment - Indexing (offline phase)
==================================================

Ingest -> Chunk -> Embed -> Store (the first 3 steps of the RAG pipeline).

Loads every PDF in docs/, splits each page into overlapping word-chunks,
embeds them all, and saves the result as a JSON vector index that rag.py
queries later. Re-run this whenever the source docs change, or to
experiment with a different chunk size / overlap.

Usage:
    python ingest.py
    python ingest.py --chunk-size 400 --overlap 80
    python ingest.py --docs-dir docs --out index.json
"""

import argparse
from collections import Counter
from pathlib import Path

from chunking import chunk_words, load_pdf_pages
from llm_client import get_client, embed_texts, DEFAULT_EMBED_MODEL
from vector_store import VectorStore


def build_index(docs_dir: Path, chunk_size: int, overlap: int) -> VectorStore:
    pdf_paths = sorted(docs_dir.glob("*.pdf"))
    if not pdf_paths:
        raise SystemExit(f"No PDFs found in {docs_dir}")

    all_chunks = []  # list of (text, metadata)
    for pdf_path in pdf_paths:
        pages = load_pdf_pages(pdf_path)
        for page_num, page_text in enumerate(pages, start=1):
            for chunk_index, chunk_text in enumerate(chunk_words(page_text, chunk_size, overlap)):
                all_chunks.append(
                    (
                        chunk_text,
                        {"source": pdf_path.name, "page": page_num, "chunk_index": chunk_index},
                    )
                )

    print(f"Loaded {len(pdf_paths)} PDF(s), split into {len(all_chunks)} chunks "
          f"(chunk_size={chunk_size} words, overlap={overlap} words).")

    client = get_client()
    print(f"Embedding {len(all_chunks)} chunks with {DEFAULT_EMBED_MODEL}...")
    vectors = embed_texts(client, [text for text, _ in all_chunks])

    store = VectorStore()
    for (text, metadata), vector in zip(all_chunks, vectors):
        store.add(vector, text, metadata)
    return store


def main():
    parser = argparse.ArgumentParser(description="Build the RAG vector index from docs/*.pdf")
    parser.add_argument("--docs-dir", default="docs", help="Folder of PDFs to ingest (default: docs)")
    parser.add_argument("--out", default="index.json", help="Where to save the index (default: index.json)")
    parser.add_argument("--chunk-size", type=int, default=300, help="Words per chunk (default: 300)")
    parser.add_argument("--overlap", type=int, default=50, help="Overlap in words between chunks (default: 50)")
    args = parser.parse_args()

    docs_dir = Path(__file__).resolve().parent / args.docs_dir
    out_path = Path(__file__).resolve().parent / args.out

    store = build_index(docs_dir, args.chunk_size, args.overlap)
    store.save(out_path)

    by_source = Counter(item["metadata"]["source"] for item in store.items)
    print(f"\nSaved {len(store)} chunks to {out_path}")
    for source, count in by_source.items():
        print(f"  {source}: {count} chunks")


if __name__ == "__main__":
    main()
