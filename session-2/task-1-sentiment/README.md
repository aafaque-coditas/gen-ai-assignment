# Task 1 — Sentiment Analysis Comparison

Classifies 20 real movies as positive / negative / neutral using **live
metadata from the OMDb API** ([movies.py](movies.py) lists the titles;
[sentiment.py](sentiment.py) fetches `https://www.omdbapi.com/demo.aspx`
at runtime with the free `demo` token — no API key needed).

- The model only ever sees **Title, Genre, Plot, and Awards text** — never
  the numeric rating.
- **Ground truth** is derived live from each movie's real IMDb rating:
  `>= 7.0` → positive, `< 5.0` → negative, otherwise → neutral. Nothing is
  hand-labeled.
- Classifies all 20 with a **zero-shot** prompt, then again with a
  **few-shot** prompt (6 labeled examples baked in — 2 positive, 2
  negative, 2 neutral — deliberately *different* movies from the 20 test
  ones, so the model can't just see the answer key).

Uses [../llm_client.py](../llm_client.py) (shared with Task 2) for API
access — see [../../session-1/README.md](../../session-1/README.md) for
the note on the OpenRouter-key auto-detection.

## Run it

```bash
cd task-1-sentiment
pip install -r ../requirements.txt
python sentiment.py
python sentiment.py --model openai/gpt-4o-mini
```

## Result

Verified, live run against the real OMDb API and OpenRouter:

```
Fetching test movies from OMDb...
  20/20 usable

Fetching few-shot example movies from OMDb...
  6/6 usable

=== Zero-shot: 13/20 correct (65%) ===
=== Few-shot: 13/20 correct (65%) ===

--- Summary ---
Zero-shot accuracy: 65% (13/20)
Few-shot accuracy:  65% (13/20)
No difference this run.
```

### The finding

Both approaches produced **identical predictions on every single movie**,
missing the same 6 (all famous, "mid-tier" ~5.0–6.9 IMDb blockbusters —
*Batman & Robin*, *Suicide Squad*, *Justice League*, *Alien: Covenant*,
*Terminator Genisys*, *Men in Black: International* — all called
"negative" instead of "neutral").

That's not a prompt-wording problem. To confirm, we added an explicit
instruction to both prompts — *"judge ONLY from this text, not from any
other knowledge you may have about this specific movie"* — and the
predictions didn't change at all. The model already knows these are
famous movies and answers from its own memorized real-world reputation of
them (it "knows" *Batman & Robin* is a punchline), not from the
plot/genre/awards snippet it was actually given. No amount of few-shot
examples about *other* movies can override that — an instruction can't
make a model un-know something.

**The lesson:** zero-shot vs. few-shot prompting is a technique for
teaching a model a *task pattern* it doesn't already know. It has much
less room to help when the input itself is something the model already
has strong memorized priors about (famous real people, famous movies,
well-known facts) — the model isn't reasoning from your prompt's content
in that case, it's recalling. Check first whether the model is actually
reading your data or just recognizing the subject, before reaching for
few-shot examples as a fix.
