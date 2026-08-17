"""
Final Assignment - Doc-to-Podcast Pipeline (Option 3)
==========================================================
Runs the whole assignment end to end:

  1. RAG            (Session 3) -- reused directly against session-3's real
                      index.json, no re-ingestion, no duplicated data.
  2. Plan-execute   (Session 5's architecture pattern) -- outline, then
                      expand each section with its own retrieval + one LLM
                      call.
  3. Critic/reflect (Session 5's other listed pattern) -- flags unsupported
                      claims per section, revises, bounded by MAX_REVISIONS.
  4. TTS            (Session 7) -- pyttsx3, since OpenRouter doesn't proxy
                      TTS (verified in session-7).
  5. MCP save       (Session 6 + 4) -- a ReAct tool-calling loop whose only
                      tool comes live from an MCP server persists the audio
                      + transcript to output/, side by side.

Every stage logs its own timing (*_ms) and token counts; the final summary
prints total_ms plus total tokens used -- Session 1's "watch your cost and
context budget" discipline, applied across a 5-stage pipeline.

Usage:
    python pipeline.py
    python pipeline.py --episode-name ds-case-study-ep1
    python pipeline.py --k 5 --model openai/gpt-4o-mini
"""

import argparse
import asyncio
import json
import time
from pathlib import Path

from critic import critique_and_revise
from llm_client import embed_texts, get_client, DEFAULT_MODEL
from planner import plan_and_execute
from save_agent import run_save_agent
from tts import synthesize_speech

SESSION_DIR = Path(__file__).resolve().parent
AUDIO_TMP_PATH = SESSION_DIR / "audio_tmp.wav"
TRANSCRIPT_TMP_PATH = SESSION_DIR / "transcript_tmp.txt"


def render_transcript(draft: dict) -> str:
    """The saved transcript: headings + narration, for a human reading it
    back later."""
    lines = [draft["title"], "=" * len(draft["title"]), ""]
    for section in draft["sections"]:
        lines.append(f"## {section['heading']}")
        lines.append(section["text"])
        lines.append("")
    return "\n".join(lines)


def render_narration(draft: dict) -> str:
    """The text actually fed to TTS -- narration only, no markdown headings
    (each section's prompt already asks for spoken-style prose; headings
    are for the saved transcript, not read aloud)."""
    parts = [draft["title"] + "."]
    for section in draft["sections"]:
        parts.append(section["text"])
    return " ".join(parts)


def run_pipeline(episode_name: str, model: str = DEFAULT_MODEL, k: int = 4, verbose: bool = True) -> dict:
    total_start = time.perf_counter()
    client = get_client()
    token_log = []

    # Stage 1+2: RAG + Plan-and-execute
    if verbose:
        print("=== Stage: Plan-and-execute (RAG-grounded outline + sections) ===")
    stage_start = time.perf_counter()
    draft, plan_tokens = plan_and_execute(client, embed_texts, model=model, k=k, verbose=verbose)
    plan_ms = (time.perf_counter() - stage_start) * 1000
    token_log.extend(plan_tokens)

    # Stage 3: Critic / reflection
    if verbose:
        print("\n=== Stage: Critic / reflection (grounded-claim check + revise) ===")
    stage_start = time.perf_counter()
    draft, critic_log, critic_tokens = critique_and_revise(client, draft, model=model, verbose=verbose)
    critic_ms = (time.perf_counter() - stage_start) * 1000
    token_log.extend(critic_tokens)

    transcript = render_transcript(draft)
    narration = render_narration(draft)
    # Written to disk now so the save agent can pass a PATH through its tool
    # call instead of the transcript text itself -- see podcast_server.py's
    # docstring for the truncation bug that motivated this.
    TRANSCRIPT_TMP_PATH.write_text(transcript, encoding="utf-8")

    # Stage 4: TTS
    if verbose:
        print("\n=== Stage: Text-to-speech ===")
    tts_result = synthesize_speech(narration, AUDIO_TMP_PATH)
    if verbose:
        print(f"[TTS] {tts_result['audio_seconds']:.1f}s of audio in {tts_result['tts_ms']:.0f}ms")

    # Stage 5: MCP save, via the save_agent ReAct+MCP tool-calling loop
    if verbose:
        print("\n=== Stage: MCP save (ReAct agent, tool sourced live from MCP) ===")
    save_start = time.perf_counter()
    save_result = asyncio.run(
        run_save_agent(client, episode_name, str(TRANSCRIPT_TMP_PATH), str(AUDIO_TMP_PATH), model=model, verbose=verbose)
    )
    save_ms = (time.perf_counter() - save_start) * 1000
    token_log.extend(save_result["token_log"])

    saved = {}
    for t in save_result["trace"]:
        if t["tool"] == "save_podcast_output":
            try:
                saved = json.loads(t["result"])
            except json.JSONDecodeError:
                saved = {"raw": t["result"]}

    total_ms = (time.perf_counter() - total_start) * 1000
    total_tokens = sum(t["total"] for t in token_log)

    result = {
        "title": draft["title"],
        "num_sections": len(draft["sections"]),
        "transcript": transcript,
        "narration": narration,
        "critic_log": critic_log,
        "saved": saved,
        "save_agent_answer": save_result["answer"],
        "save_agent_iterations": save_result["iterations"],
        "audio_seconds": tts_result["audio_seconds"],
        "timings_ms": {
            "plan_execute_ms": plan_ms,
            "critic_ms": critic_ms,
            "tts_ms": tts_result["tts_ms"],
            "mcp_save_ms": save_ms,
            "total_ms": total_ms,
        },
        "tokens": {"per_call": token_log, "total": total_tokens},
    }

    if verbose:
        print(f"\n--- Summary: '{draft['title']}' | total_ms={total_ms:.0f} | total_tokens={total_tokens} ---")
        for label, value in result["timings_ms"].items():
            print(f"  {label}: {value:.0f}ms")

    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description="Doc-to-podcast pipeline: RAG -> plan-execute -> critic -> TTS -> MCP save"
    )
    parser.add_argument("--episode-name", default="ds-case-study-ep1", help="Base filename for the saved transcript/audio")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--k", type=int, default=4, help="Chunks to retrieve per section (default: 4)")
    parser.add_argument("--quiet", action="store_true", help="Suppress stage-by-stage logging")
    return parser.parse_args()


def main():
    args = parse_args()
    run_pipeline(args.episode_name, model=args.model, k=args.k, verbose=not args.quiet)


if __name__ == "__main__":
    main()
