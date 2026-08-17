"""
Final Assignment - Small evaluation set (10 inputs, expected outcomes)
=============================================================================
Ten cases in three groups, all run for real, nothing mocked.

  CONTENT_QUESTIONS (4)  - questions I would ask about the finished episode,
                            each with the answer the source document actually
                            gives. Three ask whether a fact made it into the
                            script; the fourth is a negative case that fails
                            if the script invents a framework the document
                            never mentions.
  STRUCTURE_CHECKS (3)   - the plumbing: outline size, audio length matched
                            against script length, and the saved files really
                            being on disk and identical to what was generated.
  CRITIC_CHECKS (3)      - critic.check_section() called directly with text I
                            wrote by hand. One blatant fabrication it must
                            catch, one near-miss number it must catch, and one
                            true paraphrase it must leave alone.

An earlier version of this file checked single keywords against generous
thresholds ("angular" appears somewhere, audio longer than 5 seconds). Those
could not fail on any run that completed at all, so passing them proved very
little. Each check below is either tied to the answer the document actually
gives, scaled to the size of what was generated, or compares two things that
have to agree.
"""

import os
import re
from pathlib import Path


def normalize(text: str) -> str:
    """Lowercase, and treat hyphens as spaces so that '12-month' and
    '12 month' both match. The model writes it either way."""
    return text.lower().replace("-", " ")


def mentions(text: str, word: str) -> bool:
    """Whole-word match. The negative check below used a plain substring
    test at first and failed a clean run because 'ember' matched inside
    'members' -- a false alarm about a hallucination that never happened.
    Word boundaries are the fix; a substring test is not a mention test."""
    return re.search(rf"\b{re.escape(word)}\b", normalize(text)) is not None


CONTENT_QUESTIONS = [
    {
        "id": "q-framework",
        "question": "Which frontend framework is the design system built on?",
        "expected": "Angular, using Angular Material.",
        # Both, not just 'angular'. Naming Angular alone would leave out the
        # component library the document is specific about.
        "check": lambda r: "angular material" in normalize(r["narration"])
        and "angular" in normalize(r["narration"]),
    },
    {
        "id": "q-timeline",
        "question": "How long did the project take, against the original plan?",
        "expected": "About six months, against a twelve month plan.",
        # Both halves. 'six months' on its own loses the comparison that makes
        # the number worth saying at all.
        "check": lambda r: any(p in normalize(r["narration"]) for p in ["six month", "6 month"])
        and any(p in normalize(r["narration"]) for p in ["twelve month", "12 month"]),
    },
    {
        "id": "q-documentation",
        "question": "How is the design system documented and given to other teams?",
        "expected": "Documented in Storybook, and distributed as an npm package.",
        # AND, not OR. The document does both, so an episode that mentions
        # only one of them has left half the answer out.
        "check": lambda r: "storybook" in normalize(r["narration"]) and "npm" in normalize(r["narration"]),
    },
    {
        "id": "q-no-invented-frameworks",
        "question": "Does the episode name any frontend framework the document never mentions?",
        "expected": "No. Only Angular appears in the source document.",
        # The one case here that fails if the model makes something up, rather
        # than if it leaves something out. Whole-word matching, not substring
        # -- see mentions() for the false alarm that motivated it.
        "check": lambda r: not any(
            mentions(r["narration"], f) for f in ["react", "vue", "svelte", "next.js", "ember"]
        ),
    },
]

STRUCTURE_CHECKS = [
    {
        "id": "outline-size",
        "description": "The planned outline has between 3 and 7 sections.",
        "expected": "3 to 7 sections.",
        "check": lambda r: 3 <= r["num_sections"] <= 7,
    },
    {
        "id": "audio-matches-script",
        "description": "Audio length is consistent with how many words were narrated.",
        "expected": "At least one second of audio for every five words of script.",
        # Scaled to the script instead of a flat '> 5 seconds'. This is what
        # actually catches audio that stopped early: a 600 word script that
        # produced 20 seconds of sound would fail here and pass a flat floor.
        "check": lambda r: r["audio_seconds"] >= len(r["narration"].split()) / 5,
    },
    {
        "id": "saved-files-match",
        "description": "The save tool wrote both files, and the saved transcript matches the generated one.",
        "expected": "Both files exist, are not empty, and the text is identical.",
        # Comparing the two is the part that matters. Existence alone would
        # still pass if the file had been written truncated, which is exactly
        # how the old transcript-in-the-tool-call bug failed.
        "check": lambda r: bool(r["saved"].get("transcript_path"))
        and bool(r["saved"].get("audio_path"))
        and os.path.exists(r["saved"]["transcript_path"])
        and os.path.exists(r["saved"]["audio_path"])
        and os.path.getsize(r["saved"]["audio_path"]) > 0
        and Path(r["saved"]["transcript_path"]).read_text(encoding="utf-8") == r["transcript"],
    },
]

CRITIC_CHECKS = [
    {
        "id": "critic-catches-invented-facts",
        "description": "A section built on facts that are nowhere in the document.",
        "heading": "Tech Stack",
        "text": (
            "The design system project took eighteen months to complete, and the team built it "
            "using React and Vue, with a small amount of Svelte for the marketing site."
        ),
        "expected": "Flagged. Neither the timeline nor any of those frameworks is in the document.",
        "expect_flag": True,
    },
    {
        "id": "critic-catches-near-miss-number",
        "description": "A section that is right about everything except one number.",
        "heading": "Delivery Timeline",
        "text": (
            "The team built the design system on Angular and Angular Material, and they finished "
            "the work in seven months instead of the twelve months originally planned."
        ),
        # The hard one. Everything here is true except 'seven', and the wrong
        # number sits inside a sentence that otherwise matches the document
        # closely. This is the case most likely to slip through.
        "expected": "Flagged. The document says six months, not seven.",
        "expect_flag": True,
    },
    {
        "id": "critic-accepts-true-paraphrase",
        "description": "A section that is true but worded differently from the document.",
        "heading": "Timeline",
        "text": (
            "The team delivered the design system in about half the year originally set aside for "
            "it, and it's built on Angular's component framework."
        ),
        "expected": "Not flagged. Different wording, same facts.",
        "expect_flag": False,
    },
]
