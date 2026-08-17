"""
Final Assignment - Plan-and-execute script writer
======================================================
Architecture pattern chosen (Session 5's list): **plan-and-execute**. One
LLM call plans a section-by-section outline grounded in the whole document
(rag.all_chunks_context() -- this corpus is only 6 chunks, small enough to
hand over whole), then every section gets its OWN top-k retrieval + its own
LLM call to expand it, so each section's prose is grounded in the specific
passages retrieved for its own topic, not just "the model remembers the
outline it wrote a minute ago." This is the same reasoning session-5's
README used to justify Sequential Pipeline over ReAct for a compliance-
sensitive number: fixed, inspectable stages beat one open-ended loop when
the shape of the work is known ahead of time -- and a podcast script's shape
(outline, then N grounded sections) is known ahead of time.
"""

import json

from llm_client import call_model, DEFAULT_MODEL
from rag import all_chunks_context, format_context, retrieve

OUTLINE_SYSTEM_PROMPT = (
    "You are a podcast script planner. Given the FULL text of a short technical "
    "document, plan a 4-6 section narrated explainer script a listener could follow "
    "on a commute. Base the outline ONLY on what the document actually covers -- do "
    "not invent a section about something it doesn't mention. For each section, also "
    "write a short search query that would retrieve the passages that section needs. "
    'Respond with ONLY a JSON object of the shape: {"title": "<episode title>", '
    '"sections": [{"heading": "<section heading>", "query": "<retrieval query for this section>"}]}'
)

SECTION_SYSTEM_PROMPT = (
    "You write one section of a narrated podcast script. Use ONLY the retrieved "
    "context below -- never invent a fact, number, or claim the context doesn't "
    "support. Write 3-5 sentences of natural spoken narration: no bullet points, no "
    "headings, no markdown, since this text will be read aloud by a text-to-speech "
    "engine. If the retrieved context doesn't actually support this section's "
    "heading, say so plainly in the narration instead of filling in from general "
    "knowledge."
)


def plan_outline(client, doc_text: str, model: str = DEFAULT_MODEL) -> tuple:
    """One LLM call: whole-document text in, structured JSON outline out.
    Returns (outline_dict, tokens_dict)."""
    messages = [
        {"role": "system", "content": OUTLINE_SYSTEM_PROMPT},
        {"role": "user", "content": doc_text},
    ]
    reply, tokens = call_model(client, messages, model=model, temperature=0.3, max_tokens=500, json_mode=True)
    try:
        outline = json.loads(reply)
    except json.JSONDecodeError:
        outline = {"title": "Untitled Episode", "sections": []}
    return outline, tokens


def expand_section(client, embed_fn, heading: str, query: str, k: int = 4, model: str = DEFAULT_MODEL) -> tuple:
    """One section's own retrieval + one LLM call to write it, grounded in
    just what that retrieval returned. Returns (section_dict, tokens_dict)."""
    results = retrieve(client, embed_fn, query, k=k)
    context = format_context(results)
    messages = [
        {"role": "system", "content": SECTION_SYSTEM_PROMPT},
        {"role": "user", "content": f"Section heading: {heading}\n\nRetrieved context:\n{context}"},
    ]
    text, tokens = call_model(client, messages, model=model, temperature=0.4, max_tokens=300)
    section = {
        "heading": heading,
        "text": text,
        "sources": [
            {"source": r["metadata"]["source"], "page": r["metadata"]["page"], "score": round(r["score"], 3)}
            for r in results
        ],
    }
    return section, tokens


def plan_and_execute(client, embed_fn, model: str = DEFAULT_MODEL, k: int = 4, verbose: bool = True) -> tuple:
    """Runs the full plan-and-execute stage: outline, then expand every
    section. Returns (draft, token_log) where draft is
    {"title", "sections": [{"heading", "text", "sources"}]}."""
    token_log = []
    doc_text = all_chunks_context()

    outline, tokens = plan_outline(client, doc_text, model)
    token_log.append({"stage": "plan_outline", **tokens})
    sections_spec = outline.get("sections", [])
    if verbose:
        print(f"[PLAN] '{outline.get('title')}' -- {len(sections_spec)} sections")

    sections = []
    for i, s in enumerate(sections_spec, start=1):
        section, tokens = expand_section(client, embed_fn, s["heading"], s["query"], k=k, model=model)
        token_log.append({"stage": f"expand_section_{i}", **tokens})
        sections.append(section)
        if verbose:
            print(f"[EXPAND {i}/{len(sections_spec)}] {s['heading']}")

    return {"title": outline.get("title", "Untitled Episode"), "sections": sections}, token_log
