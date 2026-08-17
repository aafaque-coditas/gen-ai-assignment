"""
Document loading + chunking for the RAG pipeline. Chunk size and overlap
are counted in words here (no tokenizer dependency) -- a reasonable
stand-in for the commonly recommended token counts (300-800 tokens,
50-100 overlap), since English prose runs roughly 1 word ~ 1.3 tokens.
"""

from pypdf import PdfReader


def load_pdf_pages(path) -> list:
    """Return a list of page texts (1 string per page) for a PDF file."""
    reader = PdfReader(str(path))
    return [page.extract_text() or "" for page in reader.pages]


def chunk_words(text: str, chunk_size: int = 300, overlap: int = 50) -> list:
    """Split text into overlapping chunks of `chunk_size` words, stepping
    forward by (chunk_size - overlap) words each time so consecutive
    chunks share `overlap` words -- sentences that fall on a chunk
    boundary still appear whole in at least one chunk."""
    words = text.split()
    if not words:
        return []

    step = max(chunk_size - overlap, 1)
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        if end >= len(words):
            break
        start += step
    return chunks
