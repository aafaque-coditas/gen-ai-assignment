# Session 1 Assignment — Terminal API Chat

[chatbot.py](chatbot.py) implements the two Session 1 assignment tasks that
belong here (temperature moved to Session 2, where it's actually taught).

## Setup

```bash
cd session-1
pip install -r requirements.txt
```

Make sure the repo root `.env` (one level up from this folder) has:

```
OPENAI_API_KEY=sk-...
```

(Already present in this repo's `.env` — never commit real keys.)

> **Note:** the key currently in this repo's `.env` is actually an
> **OpenRouter** key (prefix `sk-or-...`), stored under the `OPENAI_API_KEY`
> name. `chatbot.py` auto-detects this: if the key starts with `sk-or-`,
> it points the OpenAI SDK's `base_url` at `https://openrouter.ai/api/v1`
> and defaults to the OpenRouter model id `openai/gpt-4o-mini`. If you swap
> in a real OpenAI key (`sk-...`) instead, it talks to `api.openai.com`
> directly with model `gpt-4o-mini` — no code changes needed.

## Task 1 — API access

Handled at the top of `chatbot.py`: the key is read from `OPENAI_API_KEY`
in the project's root `.env` file via `python-dotenv`. It's never
hard-coded or printed.

## Task 2 — CLI chat

Keeps the whole conversation in a `messages` list, tagged with only two
roles — `user` and `assistant` — and resends it on every request, since
the API itself is stateless.

```bash
python chatbot.py
python chatbot.py --model gpt-4o-mini --temperature 0.2
python chatbot.py --stream
```

Type `quit` or `exit` to leave.

## Task 3 (temperature) — moved to Session 2

The temperature experiment now lives in [../session-2/](../session-2/),
alongside where Session 2 actually teaches what temperature does.

## Verified result

Actual transcript, showing the `messages` list genuinely carrying memory
across turns — the second answer depends on the first turn, which only
works because the whole history is resent on every call:

```
GenAI Terminal Chat -- type 'quit' or 'exit' to leave
(model=openai/gpt-4o-mini, temperature=0.7)

You: My favorite number is 7.
Assistant: That's a great choice! The number 7 has a lot of interesting
significance in various cultures and contexts...

You: What is my favorite number plus 3?
Assistant: Your favorite number is 7, so 7 plus 3 equals 10.

You: quit
Goodbye!
```

If the API truly had no memory of its own and the script weren't resending
history, the second question would have gotten a "I don't know your
favorite number" reply instead.
