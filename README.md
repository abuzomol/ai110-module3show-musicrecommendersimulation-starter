# 🎵 Music Recommender Simulation

## Project Summary

In this project you will build and explain a small music recommender system.

Your goal is to:

- Represent songs and a user "taste profile" as data
- Design a scoring rule that turns that data into recommendations
- Evaluate what your system gets right and wrong
- Reflect on how this mirrors real world AI recommenders

Replace this paragraph with your own summary of what your version does.

---

## How The System Works

The system has two separate rules, and keeping them separate is the main design
decision.

1. A **scoring rule** looks at one song and one user and returns a number.
2. A **ranking rule** takes all the scored songs and decides which ones, and in
   what order, actually get shown.

A scoring rule cannot express things that depend on the other results — how many
songs to return, what to do about ties, or whether two recommendations are near
duplicates of each other. Those are properties of the *list*, so they live in the
ranking rule.

### The data each part uses

Each `Song` carries seven attributes: `genre`, `mood`, `energy`, `tempo_bpm`,
`valence`, `danceability` and `acousticness`. **The current model scores only four
of them** — genre, mood, energy and acousticness. Tempo, valence and danceability
are loaded but unused; see Limitations.

Each `UserProfile` stores four preferences: `favorite_genre`, `favorite_mood`,
`target_energy` and `likes_acoustic`.

### The scoring rule

Each song earns points on four features, and the points are added up:

```
score = 2.00 x genre match        (0 to 1)
      + 1.50 x mood match         (0 to 1)
      + 1.50 x energy closeness   (0 to 1)
      + 0.75 x acoustic fit      (-1 to 1)
```

- **Genre** compares words, not whole strings, so `indie pop` gets half credit
  against a `pop` fan instead of zero.
- **Mood** gives full credit for an exact match and partial credit (0.6) for
  moods in the same family — `chill`, `relaxed` and `focused` describe basically
  the same listening situation in this catalog.
- **Energy closeness** peaks when the song's energy equals the target and falls
  off smoothly either side, so being slightly off barely costs anything while
  being far off costs a lot.
- **Acoustic fit** is the only term that can go *negative*. If the user dislikes
  acoustic music, acoustic-heavy songs are pushed down rather than merely not
  boosted.

Every feature is first converted to the same 0-to-1 range, which is what makes
the weights comparable: 2.00 for genre really does mean genre counts about 1.3x
as much as mood. A perfect song scores 5.75.

### The ranking rule

Sort by score, highest first, breaking ties by song `id` so the output is
identical on every run, then take the top `k`. Ties are common on a catalog this
small, so without a deterministic tie-break the results would wobble between runs.

### Why the explanations can be trusted

Because the score is a *sum*, each feature's contribution is exactly its share of
the total. The explanation is built from those same numbers, so it can never
disagree with the ranking — if a song is listed first, the reasons shown are
genuinely the reasons it won. Explanations also mention the strongest negative
term as a caveat rather than only listing good news.

### Swapping the model (Strategy pattern)

The scorer is a plug-in object, not hardcoded logic. `Recommender` accepts any
`ScoringStrategy`:

- `WeightedScorer` — the four-feature model above (default)
- `GenreOnlyScorer` — an ablation baseline that uses genre and nothing else

Both are ranked by the same code. This is what makes the experiments below a
matter of swapping one object instead of editing the recommender, and it means
the ablation baseline answers a real question: are the extra three features
earning their complexity?

---

## The Data

There are two catalogs, both with identical columns.

### `data/songs.csv` — the original 10 songs

The catalog shipped with the starter. **Used for:** the default demo run and the
sample output below.

It has a gap that turned out to be useful. Its lowest `valence` is 0.48 and no
song is tagged `sad`, so there is no melancholy music in it at all. A user asking
for sad indie music gets chill ambient and jazz instead — scored, ranked and
presented as confident recommendations. Nothing in the scoring rule is wrong
there; the catalog simply has nothing to offer, and the ranking rule still has to
fill five slots. That failure is preserved on purpose and is asserted by a test
(`test_default_catalog_cannot_serve_a_sad_listener`) so it is documented rather
than quietly fixed.

Other limits of the 10-song catalog: asking for `k=5` returns half of it, so
ranking quality is hard to judge; rock, ambient, jazz and synthwave have exactly
one song each; and no two songs are similar enough to test whether the system
returns near-duplicates.

### `data/songs_extended.csv` — 40 songs

Written for this project. It keeps the original 10 at the same ids and adds 30
more, chosen to cover what the small catalog could not test:

| Added | Why |
|---|---|
| 8 `sad` / low-valence songs (down to valence 0.05) | So a melancholy listener can actually be served |
| lofi expanded to 8 songs | Enough within-genre depth to judge ordering, not just genre matching |
| A near-duplicate pair: `Empty Apartment` and `Vacant Rooms`, different artists | Tests whether the top of the list is redundant |
| `Neon Echo` raised to 4 tracks | Tests per-artist repetition |
| Boundary rows: `Absolute Zero` (energy 0.00) and `Redline` (energy 1.00) | Exercises the ends of the energy scale |
| A new genre (`folk`) | A genre the original catalog never contained |

**Used for:** every experiment and almost all of the property tests. The
comparisons below are run on it, because on 10 songs most weight changes are
invisible.

---

## Getting Started

### Setup

1. Create a virtual environment (optional but recommended):

   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Mac or Linux
   .venv\Scripts\activate         # Windows

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Run the app:

```bash
python -m src.main
```

Run it from the **project root** (the folder containing `src/` and `data/`).
Catalog paths are resolved relative to the project root rather than the current
directory, so the app behaves the same no matter where you invoke it from.

### Command line options

| Flag | Default | What it does |
|---|---|---|
| `--catalog PATH` | `data/songs.csv` | Which song catalog to load |
| `--profile NAME` | `pop-happy` | `pop-happy`, `lofi-study`, `melancholy`, or `all` |
| `--k N` | `5` | How many songs to recommend |
| `--compare` | off | Also runs the genre-only baseline for side-by-side comparison |

Useful combinations:

```bash
# Default demo: the pop-happy listener on the original 10 songs
python -m src.main

# All three profiles on the 40-song catalog
python -m src.main --catalog data/songs_extended.csv --profile all

# Weighted model vs the genre-only baseline, same profile
python -m src.main --catalog data/songs_extended.csv --profile melancholy --compare

# The catalog gap: run this against both catalogs and compare
python -m src.main --profile melancholy --k 3
python -m src.main --catalog data/songs_extended.csv --profile melancholy --k 3
```

The three demo profiles are defined at the top of `src/main.py`; edit that dict
to try your own listener.

### Running Tests

From the project root:

```bash
pytest
```

Expected: **29 passed**.

There are two test files:

- `tests/test_recommender.py` — the two starter tests, unmodified.
- `tests/test_properties.py` — 27 tests added for this project.

The second file mostly contains **property tests**: instead of pinning one
hand-computed answer, they assert things that must hold for any sensible scoring
rule, so they survive weight tuning but still catch real breakage. They are
grouped by what they protect:

| Group | Example |
|---|---|
| Ranking is real | The best song is placed *last* in the input, so returning the list unchanged fails |
| Order independence | Shuffling the catalog 10 times must not change the top 5 |
| Determinism | Same input, same output; ties always break on the lower id |
| Monotonicity | Moving a song's energy toward the target can never lower its score |
| Feature helpers | `pop` vs `indie pop` scores 0.5; energy fit is symmetric around the target |
| Explanations | Never blank, even for a song that matches nothing, and consistent with the score |
| Strategy swapping | The two scorers produce different results; changing genre weight is observable |
| Data loading | Correct types, 40 rows, a clear error naming the line of a malformed row |
| The two APIs agree | The dict-based and object-based paths return identical rankings |

One of these deserves a note. The starter test passed against the *unimplemented*
recommender, because the stub returned `self.songs[:k]` and the fixture happened
to list the correct answer first. `test_best_song_is_not_simply_the_first_song`
puts the right answer last so that shortcut fails.

---

## Sample Recommendation Output

Default run, `python -m src.main` — the pop-happy listener on the original
10-song catalog:

```
Loaded 10 songs from data/songs.csv

=== pop-happy | model: weighted ===
Profile: {'genre': 'pop', 'mood': 'happy', 'energy': 0.8, 'likes_acoustic': False}

1. Sunrise City - Neon Echo  (score 5.48)
   Because: it is pop, your favorite genre; the mood is happy, exactly what you asked for; its energy (0.82) is close to your target (0.80)
2. Rooftop Lights - Indigo Parade  (score 4.21)
   Because: the mood is happy, exactly what you asked for; its energy (0.76) is close to your target (0.80); indie pop partly overlaps your favorite (pop)
3. Gym Hero - Max Pulse  (score 3.99)
   Because: it is pop, your favorite genre; its energy (0.93) is close to your target (0.80); its acoustic texture (0.05) suits your taste
4. Storm Runner - Voltline  (score 1.96)
   Because: its energy (0.91) is close to your target (0.80); its acoustic texture (0.10) suits your taste
5. Night Drive Loop - Neon Echo  (score 1.89)
   Because: its energy (0.75) is close to your target (0.80); its acoustic texture (0.22) suits your taste
```

Two things are visible in that output. `Rooftop Lights` is `indie pop`, and it
still places second because partial genre credit plus an exact mood match beats
`Gym Hero`, which is exactly the right genre but the wrong mood. And the score
falls off a cliff after rank 3 — positions 4 and 5 match on *nothing* but energy
and acoustic texture, and their explanations say so. With only 10 songs, the
ranking rule has to fill five slots whether or not five good songs exist.

Same run with `--profile lofi-study --k 3`:

```
=== lofi-study | model: weighted ===
Profile: {'genre': 'lofi', 'mood': 'focused', 'energy': 0.4, 'likes_acoustic': True}

1. Focus Flow - LoRoom  (score 5.42)
   Because: it is lofi, your favorite genre; the mood is focused, exactly what you asked for; its energy (0.40) is close to your target (0.40)
2. Library Rain - Paper Lanterns  (score 4.91)
   Because: it is lofi, your favorite genre; its energy (0.35) is close to your target (0.40); a chill mood is close to focused
3. Midnight Coding - LoRoom  (score 4.71)
   Because: it is lofi, your favorite genre; its energy (0.42) is close to your target (0.40); a chill mood is close to focused
```

Ranks 2 and 3 are the mood-family rule doing its job: neither song is tagged
`focused`, but `chill` earns partial credit instead of zero.

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or demo video link here -->

---

## Experiments You Tried

Use this section to document the experiments you ran. For example:

- What happened when you changed the weight on genre from 2.0 to 0.5
- What happened when you added tempo or valence to the score
- How did your system behave for different types of users

---

## Limitations and Risks

Summarize some limitations of your recommender.

Examples:

- It only works on a tiny catalog
- It does not understand lyrics or language
- It might over favor one genre or mood

You will go deeper on this in your model card.

---

## Reflection

Read and complete `model_card.md`:

[**Model Card**](model_card.md)

Write 1 to 2 paragraphs here about what you learned:

- about how recommenders turn data into predictions
- about where bias or unfairness could show up in systems like this



