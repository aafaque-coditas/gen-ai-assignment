"""
Final Assignment - MCP tool: save_podcast_output
=====================================================
The "use an MCP tool to save the audio file and the final transcript
locally, side by side" requirement. Same minimal MCPServer (FastMCP) pattern
as session-6's oncall_server.py, including the same v2.0.0 SDK rename
(FastMCP -> MCPServer, aliased back so the code reads the same as the
original snippet).

Scoped to write ONLY inside this folder's output/ directory -- the same
least-privilege principle session-6's filesystem-server sandbox used
(scoped to one project folder, verified by trying to break it), enforced
here in the server's own code since this is a custom server rather than the
official filesystem one.

Never imported and called directly: pipeline.py launches this file as an
MCP subprocess (via save_agent.py) and calls save_podcast_output over the
protocol, through a real tool-calling loop, so the save genuinely goes
through MCP rather than being a hard-coded function call with extra
ceremony around it.

A real bug, and the fix: the tool's first version took the transcript TEXT
itself as a parameter, so save_agent.py's model had to copy the whole
multi-KB transcript verbatim into its own tool-call arguments. At
max_tokens=300 that JSON payload got cut off mid-string -- an "Unterminated
string" JSONDecodeError, not a flaky one, every run. Bumping max_tokens
would only postpone the same failure at a longer transcript. The actual fix:
this tool takes a transcript_source_path instead, the same way
audio_source_path already worked -- the model only ever has to echo back
two short file paths and a name, never the payload itself, so the argument
size stops scaling with the script's length at all.

Run standalone to serve over stdio:
    python podcast_server.py
More usefully, run through pipeline.py / save_agent.py, which launch this
exact file as a subprocess and talk MCP to it for real.
"""

import json
import shutil
from pathlib import Path

from mcp.server.mcpserver import MCPServer as FastMCP

OUTPUT_DIR = (Path(__file__).resolve().parent / "output").resolve()

mcp = FastMCP("podcast")


@mcp.tool()
def save_podcast_output(episode_name: str, transcript_source_path: str, audio_source_path: str) -> str:
    """Save a finished podcast episode's transcript and audio file to the
    output/ folder, side by side, both named after episode_name. Use this
    ONLY to persist a finished episode -- transcript_source_path and
    audio_source_path must both already exist (files already written to
    disk by the caller, e.g. a rendered transcript .txt and a TTS .wav).
    Returns the two saved paths as JSON, or an 'error' field if either
    source is missing or a destination would resolve outside output/."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    safe_name = "".join(c for c in episode_name if c.isalnum() or c in ("-", "_")) or "episode"
    transcript_dest_path = OUTPUT_DIR / f"{safe_name}.txt"
    audio_dest_path = OUTPUT_DIR / f"{safe_name}.wav"

    # Least-privilege check: both destinations must resolve inside
    # OUTPUT_DIR even after the filename sanitization above -- belt and
    # suspenders against a name that somehow still escapes it.
    for p in (transcript_dest_path, audio_dest_path):
        if OUTPUT_DIR not in p.resolve().parents:
            return json.dumps({"error": f"refused: {p} would resolve outside {OUTPUT_DIR}"})

    transcript_source = Path(transcript_source_path)
    audio_source = Path(audio_source_path)
    if not transcript_source.exists():
        return json.dumps({"error": f"transcript_source_path does not exist: {transcript_source_path}"})
    if not audio_source.exists():
        return json.dumps({"error": f"audio_source_path does not exist: {audio_source_path}"})

    shutil.copyfile(transcript_source, transcript_dest_path)
    shutil.copyfile(audio_source, audio_dest_path)

    return json.dumps({"transcript_path": str(transcript_dest_path), "audio_path": str(audio_dest_path)})


if __name__ == "__main__":
    mcp.run()  # stdio by default, same as session-6
