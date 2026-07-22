# 🎵 Music Recommender Simulation

## Project Summary

In this project you will build and explain a small music recommender system.

Your goal is to:

- Represent songs and a user "taste profile" as data
- Design a scoring rule that turns that data into recommendations
- Evaluate what your system gets right and wrong
- Reflect on how this mirrors real world AI recommenders

My version is called **SongFit 1.0**. It takes one listener's stated taste — a
favorite genre, a favorite mood, a target energy level, and whether they like
acoustic music — and returns the top 5 songs from the catalog with a reason for
each one. Each song earns points on four features, the points are added up, and
the songs are sorted by that total.

The starter code did not score anything at all. It returned the first 5 songs in
the file. I replaced that with real scoring, made the results stable and
repeatable, and made the explanations come from the same numbers that produced
the score. I also made the scorer swappable, which let me compare three different
models without editing the recommender.

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

### The Algorithm Recipe (finalized)

The whole system as a step-by-step recipe:

**Setup**

1. Read the catalog CSV and turn every row into a `Song`, converting the numbers
   from text and lower-casing `genre` and `mood` so matching is case-insensitive.
2. Read the listener's four preferences into a `UserProfile`.

**Score each song, one at a time, independently**

3. **Genre points.** Split both genre labels into words and compute the fraction
   of shared words out of all words used. Same label → 1. `pop` vs `indie pop` →
   0.5. Nothing shared → 0. Multiply by **2.00**.
4. **Mood points.** Same mood → 1. Different mood but same mood family → 0.6.
   Otherwise → 0. Multiply by **1.50**.
5. **Energy points.** Take the gap between the listener's target energy and the
   song's energy. A gap of zero scores 1, and the score falls away smoothly as
   the gap grows (a gap of about 0.29 halves it). Multiply by **1.50**.
6. **Acoustic points.** Re-centre the song's acousticness so 0.5 becomes 0, fully
   acoustic becomes +1 and fully electronic becomes −1. If the listener dislikes
   acoustic music, flip the sign. Multiply by **0.75**. This is the only term
   that can subtract.
7. **Add the four numbers together.** That is the song's score. Keep the four
   parts alongside the total — they are needed for the explanation.

**Rank the scored songs as a set**

8. Sort by score, highest first.
9. Break ties by the lower song `id`, so the same input always gives the same
   output.
10. Keep the first `k`.

**Explain**

11. For each recommendation, take the parts that added at least 0.05 points, sort
    them largest first, and state the top three as the reasons.
12. If any part *subtracted* at least 0.05, append it as a caveat so the
    explanation is honest about the song's weakness.
13. If nothing scored above the threshold, say so plainly rather than inventing a
    reason.


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

- **What happened when you changed the weight on genre from 2.0 to 0.5?**

No change in the ranking with the limited data. The scores changed, but the
overall ranking did not. With the extended data I did observe a change in the
ranking of the songs, but only for some listeners. The jazz fan's top 5 was
reordered, while the pop, lofi, and melancholy listeners kept exactly the same
top 5. The reason is that in this catalog the pop songs are also the happy,
high-energy ones, so genre is partly redundant with mood and energy. Listeners in
thin genres like jazz are the ones who feel the weight change.

- **What happened when you added tempo or valence to the score?**

Not much, because valence and tempo are largely redundant with genre and mood
(they are highly correlated with them). I built a separate 6-feature model to
test this and compared it against the original. For the pop and melancholy
listeners the top 5 did not change at all, and for the lofi and jazz listeners
only one song swapped.

The exception was worth the effort. For a listener asking for sad pop music, the
6-feature model replaced 3 of the 5 results. The original model had put
`Confetti Kids` at rank 3, which is tagged `happy` with valence 0.88, because
only 2 pop songs are tagged `sad` and the genre weight filled the rest of the
list with any pop song. Valence catches that mistake and the original model
cannot.

- **How did your system behave for different types of users?**

Different users with different profiles have different tastes and get a different
ranking of the songs. The quality was not equal between them, though. The pop and
lofi listeners got good results because those genres have 7 and 8 songs in the
extended catalog. The jazz and folk listeners have far fewer songs to choose
from, so their lists fill up with weaker matches and their results move much more
when I change the weights.


** How claude is concerned about biases. (claude answer's not mine!!!)
The worst case was asking for sad music on the original catalog. That catalog has
no sad songs at all, so the system returned chill ambient and jazz instead and
still displayed them like normal recommendations.

## Limitations and Risks

- It only works on a tiny catalog. Even the extended version is 40 songs, so the
  system often has to fill the list with weak matches.
- It does not understand lyrics, language, era, or artist popularity. It only
  knows the seven numbers and labels in the CSV.
- It uses only 4 of those 7 features. Valence, tempo, and danceability are loaded
  but never scored in the main model.
- Because valence is unused, sadness is only skin-deep. Two songs both tagged
  `sad` score the same even if one is far darker than the other.
- It is unfair to listeners in thin genres. Folk and indie have 2 songs each, and
  those listeners get weaker results that also move around much more when the
  weights change.
- It can return two nearly identical songs at the top, because the scoring rule
  judges each song alone and cannot see that a slot is being wasted.
- It always returns 5 songs, even when only 2 or 3 genuinely fit, and a weak
  match is displayed in exactly the same format as a strong one.
- Nothing is learned. The same listener sees the same 5 songs forever, and the
  system never finds out whether it was right.

I go deeper on these in the model card, including the mood families being my own
personal judgment and the genre matching failing on hyphenated genres.

---

## Reflection

Read and complete `model_card.md`:

[**Model Card**](model_card.md)

Write 1 to 2 paragraphs here about what you learned:

- about how recommenders turn data into predictions.

Basically, there are two ways to do this: one is by comparing songs against a
user profile and finding a match, and the other is by observing the behaviour of
many users and clustering them to learn their behaviours. The first one does not
really care how other users are listening or what their history is, while the
second one does, like YouTube and Spotify. However, the second way requires crowd
data and the tools to accumulate and mine those histories. My project can only do
the first one, because the dataset has no other users in it at all.

Giving weights basically prioritizes some features over others. Instead of
choosing the weights by hand, we could use matrix decomposition such as Principal
Component Analysis to find the important directions in the data. The real
difference is that my weights are numbers I typed in myself, while a real system
learns them from millions of interactions.

- about where bias or unfairness could show up in systems like this.

The clearest unfairness is that the system is only as good as the catalog. When I
asked for sad music on the original 10 songs, it returned chill ambient and jazz
with confident explanations, because there was no sad music to give. The scoring
was not wrong; the data was missing, and the user cannot tell the difference.

One thing I observed is that the claude tries its best to add sad music. I am not bothered by it, but all biases cases are made against sad music for some reason. For example this is a bias coming from Claude:

"The full list of biases is in the model card, including the mood families that I
decided on myself and the unused valence column that makes the system blind to
how sad a song actually sounds.
".



