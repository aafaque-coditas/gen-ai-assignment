"""
Session 2 Assignment - Task 1: Sentiment Analysis Comparison
==============================================================

Classifies 20 real movies as positive / negative / neutral based on their
OMDb metadata (title, genre, plot, awards -- deliberately NOT the numeric
rating), first with a zero-shot prompt, then with a few-shot prompt, and
compares accuracy against ground truth derived from each movie's real
IMDb rating.

Data source: https://www.omdbapi.com/demo.aspx (free demo token, no API
key needed). "Sentiment" here means: was this movie generally well
received?
    imdbRating >= 7.0  -> positive
    imdbRating <  5.0  -> negative
    otherwise          -> neutral
That bucketing is the ground truth the model's guess is scored against.

Usage:
    python sentiment.py
    python sentiment.py --model openai/gpt-4o-mini
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# llm_client.py is shared across both Session 2 tasks and lives one level
# up, at session-2/ -- add it to the import path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm_client import get_client, call_model, DEFAULT_MODEL
from movies import TEST_MOVIES, FEW_SHOT_MOVIES

LABELS = ("positive", "negative", "neutral")
OMDB_URL = "https://www.omdbapi.com/demo.aspx/"


def fetch_movie(title: str):
    """Look up a movie's metadata on OMDb. Returns None if not found/unreachable."""
    url = OMDB_URL + "?" + urllib.parse.urlencode({"t": title, "token": "demo"})
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"  WARNING: could not fetch '{title}': {e}")
        return None
    if data.get("Response") != "True":
        print(f"  WARNING: OMDb has no data for '{title}': {data.get('Error')}")
        return None
    return data


def bucket_rating(imdb_rating: str):
    """Ground truth label from the movie's real IMDb rating -- not hand-labeled."""
    try:
        rating = float(imdb_rating)
    except (TypeError, ValueError):
        return None
    if rating >= 7.0:
        return "positive"
    if rating < 5.0:
        return "negative"
    return "neutral"


def describe_movie(data: dict) -> str:
    """Qualitative-only description. Deliberately excludes the numeric rating,
    so the model has to infer reception from plot/genre/awards text alone --
    otherwise it could just parrot the rating back instead of "reasoning"."""
    return (
        f"Title: {data.get('Title')} ({data.get('Year')})\n"
        f"Genre: {data.get('Genre')}\n"
        f"Plot: {data.get('Plot')}\n"
        f"Awards: {data.get('Awards')}"
    )


def load_movies(titles: list) -> list:
    """Fetch + bucket a list of movie titles from OMDb; skip any that fail."""
    movies = []
    for title in titles:
        data = fetch_movie(title)
        if data is None:
            continue
        true_label = bucket_rating(data.get("imdbRating"))
        if true_label is None:
            print(f"  WARNING: no usable imdbRating for '{title}', skipping")
            continue
        movies.append({"title": data["Title"], "description": describe_movie(data), "true": true_label})
    return movies


def build_zero_shot_prompt(description: str) -> str:
    return (
        "Based ONLY on this movie's metadata below -- not on any other "
        "knowledge you may have about this specific movie -- was it "
        "generally well received by audiences? Respond with exactly one "
        "word: positive (well received), negative (poorly received), or "
        "neutral (mixed/average reception). No other text.\n\n"
        f"{description}"
    )


def build_few_shot_prompt(description: str, examples: list) -> str:
    lines = [
        "Based ONLY on a movie's metadata below -- not on any other "
        "knowledge you may have about the specific movie -- judge whether "
        "it was generally well received by audiences. Respond with "
        "exactly one word: positive, negative, or neutral. No other text. "
        "Here are some examples:\n"
    ]
    for i, ex in enumerate(examples, start=1):
        lines.append(f"Example {i}:\n{ex['description']}\n-> {ex['true']}\n")
    lines.append(f"Now classify:\n{description}\n->")
    return "\n".join(lines)


def extract_label(raw_reply: str) -> str:
    """Pull the first positive/negative/neutral token out of the model's reply."""
    lowered = raw_reply.lower()
    for label in LABELS:
        if re.search(rf"\b{label}\b", lowered):
            return label
    return "unparseable"


def run_approach(client, model: str, movies: list, prompt_builder, label: str) -> list:
    """Classify every movie with the given prompt style; return per-item results."""
    results = []
    for movie in movies:
        prompt = prompt_builder(movie["description"])
        messages = [{"role": "user", "content": prompt}]
        reply = call_model(client, messages, model=model, temperature=0.0, max_tokens=10)
        predicted = extract_label(reply)
        results.append(
            {
                "title": movie["title"],
                "true": movie["true"],
                "predicted": predicted,
                "correct": predicted == movie["true"],
            }
        )
    correct_count = sum(r["correct"] for r in results)
    print(f"\n=== {label}: {correct_count}/{len(results)} correct ({correct_count / len(results):.0%}) ===")
    for r in results:
        mark = "OK  " if r["correct"] else "MISS"
        print(f"  [{mark}] true={r['true']:<9} pred={r['predicted']:<12} | {r['title']}")
    return results


def main():
    parser = argparse.ArgumentParser(description="Movie sentiment via OMDb metadata: zero-shot vs few-shot")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model name (default: {DEFAULT_MODEL})")
    args = parser.parse_args()

    print("Fetching test movies from OMDb...")
    test_movies = load_movies(TEST_MOVIES)
    print(f"  {len(test_movies)}/{len(TEST_MOVIES)} usable")

    print("\nFetching few-shot example movies from OMDb...")
    few_shot_examples = load_movies(FEW_SHOT_MOVIES)
    print(f"  {len(few_shot_examples)}/{len(FEW_SHOT_MOVIES)} usable")

    if not test_movies:
        raise SystemExit("No usable test movies fetched -- check your network connection.")

    client = get_client()

    zero_shot_results = run_approach(client, args.model, test_movies, build_zero_shot_prompt, "Zero-shot")
    few_shot_results = run_approach(
        client,
        args.model,
        test_movies,
        lambda desc: build_few_shot_prompt(desc, few_shot_examples),
        "Few-shot",
    )

    zero_acc = sum(r["correct"] for r in zero_shot_results) / len(zero_shot_results)
    few_acc = sum(r["correct"] for r in few_shot_results) / len(few_shot_results)

    print("\n--- Summary ---")
    print(f"Zero-shot accuracy: {zero_acc:.0%} ({sum(r['correct'] for r in zero_shot_results)}/{len(zero_shot_results)})")
    print(f"Few-shot accuracy:  {few_acc:.0%} ({sum(r['correct'] for r in few_shot_results)}/{len(few_shot_results)})")
    diff = few_acc - zero_acc
    if diff > 0:
        print(f"Few-shot improved accuracy by {diff:.0%}.")
    elif diff < 0:
        print(f"Few-shot did WORSE by {-diff:.0%} this run -- small samples can be noisy, worth re-running.")
    else:
        print("No difference this run.")


if __name__ == "__main__":
    main()
