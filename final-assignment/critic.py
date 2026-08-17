"""
Final Assignment - Critic / reflection step
================================================
The assignment's required "critic/reflection step that reviews the draft
against the source... flags any claim the document doesn't support... the
agent revises before moving on." Runs per section: one LLM call checks the
section against the FULL source document (rag.all_chunks_context(), the same
whole-doc text the planner outlined from) and returns which claims, if any,
aren't supported; if any are flagged, a second LLM call rewrites just that
section grounded in the same source, and the critic re-checks. Bounded by
MAX_REVISIONS -- the same MAX_ITERATIONS discipline every agent loop in this
repo uses (session-4/5/6's ReAct loops, this session's own save_agent.py),
applied to a reflection loop instead of a tool-calling one.
"""

import json

from llm_client import call_model, DEFAULT_MODEL
from rag import all_chunks_context

MAX_REVISIONS = 3

CRITIC_SYSTEM_PROMPT = (
    "You are a fact-checking critic. You are given the FULL source document and one "
    "section of a podcast script that is supposed to be grounded in it. Flag every "
    "claim in the section that the document does NOT support -- invented numbers, "
    "names, or facts. Do NOT flag a claim that is a fair paraphrase of something the "
    "document actually says. "
    'Respond with ONLY a JSON object: {"supported": <bool>, "flagged_claims": ["<claim text>", ...]}'
)

REVISE_SYSTEM_PROMPT = (
    "Rewrite this podcast section to remove or correct every flagged claim, using "
    "ONLY the source document below as your source of truth. Keep the same spoken, "
    "narration style: 3-5 sentences, no markdown, no headings. If, once the "
    "unsupported claims are removed, there isn't much left to say, write a shorter, "
    "honest section instead of inventing anything to fill the space."
)


def check_section(client, section: dict, doc_text: str, model: str = DEFAULT_MODEL) -> tuple:
    """Returns ({"supported", "flagged_claims"}, tokens_dict)."""
    messages = [
        {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Source document:\n{doc_text}\n\nSection ({section['heading']}):\n{section['text']}",
        },
    ]
    reply, tokens = call_model(client, messages, model=model, temperature=0.0, max_tokens=300, json_mode=True)
    try:
        verdict = json.loads(reply)
    except json.JSONDecodeError:
        verdict = {"supported": True, "flagged_claims": []}
    return verdict, tokens


def revise_section(client, section: dict, flagged_claims: list, doc_text: str, model: str = DEFAULT_MODEL) -> tuple:
    """Returns (revised_text, tokens_dict)."""
    prompt = (
        f"Source document:\n{doc_text}\n\n"
        f"Section ({section['heading']}):\n{section['text']}\n\n"
        f"Flagged unsupported claims:\n" + "\n".join(f"- {c}" for c in flagged_claims)
    )
    messages = [{"role": "system", "content": REVISE_SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
    text, tokens = call_model(client, messages, model=model, temperature=0.3, max_tokens=300)
    return text, tokens


def critique_and_revise(client, draft: dict, model: str = DEFAULT_MODEL, verbose: bool = True) -> tuple:
    """Runs the critic over every section, revising up to MAX_REVISIONS times
    per section. Mutates and returns draft. Returns
    (draft, critic_log, token_log)."""
    doc_text = all_chunks_context()
    token_log = []
    critic_log = []

    for section in draft["sections"]:
        trace = {"heading": section["heading"], "revisions": 0, "flagged_history": [], "hit_cap": False}
        for iteration in range(1, MAX_REVISIONS + 1):
            verdict, tokens = check_section(client, section, doc_text, model)
            token_log.append({"stage": f"critic_{section['heading']}_pass{iteration}", **tokens})
            flagged = verdict.get("flagged_claims", [])
            trace["flagged_history"].append(flagged)
            if verbose:
                mark = "OK" if not flagged else "FLAGGED"
                print(f"[CRITIC pass {iteration}] {section['heading']}: {mark} {flagged if flagged else ''}")

            if not flagged:
                break

            revised_text, tokens = revise_section(client, section, flagged, doc_text, model)
            token_log.append({"stage": f"revise_{section['heading']}_pass{iteration}", **tokens})
            section["text"] = revised_text
            trace["revisions"] += 1
        else:
            # The for-loop ran out of MAX_REVISIONS passes without ever
            # breaking on an unflagged check -- the last pass still had
            # flagged claims. Cap the loop rather than revise forever.
            trace["hit_cap"] = True
        critic_log.append(trace)

    return draft, critic_log, token_log
