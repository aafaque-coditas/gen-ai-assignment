"""
Movie titles used by sentiment.py, looked up live against the OMDb API
(https://www.omdbapi.com/demo.aspx, free demo token -- no key needed).

TEST_MOVIES     - the 20 movies we classify and score accuracy against.
FEW_SHOT_MOVIES - a separate, smaller set used only to build the few-shot
                   prompt. Kept distinct from TEST_MOVIES on purpose: if a
                   test movie's own answer were baked into the few-shot
                   examples, the "accuracy improvement" would be fake.

Ground truth is derived live from each movie's real IMDb rating (bucketed
at runtime in sentiment.py) -- nothing here is hand-labeled. Titles were
picked ahead of time by checking their real ratings so the 20 test movies
span positive/negative/neutral reasonably evenly:
  positive (>= 7.0): Inception, The Godfather, The Dark Knight, Parasite,
                      Whiplash, Passengers, Wonder Woman
  neutral (5.0-6.9):  Batman and Robin, Suicide Squad, Justice League,
                      Alien Covenant, Terminator Genisys,
                      Men in Black International
  negative (< 5.0):   The Room, Cats, Jack and Jill, The Emoji Movie,
                      Movie 43, Dragonball Evolution, Catwoman
"""

TEST_MOVIES = [
    "Inception",
    "The Godfather",
    "The Dark Knight",
    "Parasite",
    "Whiplash",
    "Passengers",
    "Wonder Woman",
    "Batman and Robin",
    "Suicide Squad",
    "Justice League",
    "Alien Covenant",
    "Terminator Genisys",
    "Men in Black International",
    "The Room",
    "Cats",
    "Jack and Jill",
    "The Emoji Movie",
    "Movie 43",
    "Dragonball Evolution",
    "Catwoman",
]

FEW_SHOT_MOVIES = [
    "The Shawshank Redemption",  # positive
    "Titanic",  # positive
    "Battlefield Earth",  # negative
    "Gotti",  # negative
    "San Andreas",  # neutral -- solidly mid-tier, not a notorious flop
    "King Arthur: Legend of the Sword",  # neutral -- same
]
