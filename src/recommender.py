"""
Music Recommender Simulation - scoring and ranking logic.

Design:
  - A weighted additive scorer (genre, mood, energy, acoustic texture), where
    every feature term is normalized to a comparable range so the weights mean
    something when you tune them.
  - The scorer is a swappable Strategy, so alternative models can be compared
    side by side without touching the Recommender.
  - Explanations are built from the SAME per-feature contributions that produced
    the score, so an explanation can never disagree with the ranking.

Both public APIs (the OOP `Recommender` and the dict-based functions used by
main.py) delegate to one scorer. There is only one model in this file.
"""

from __future__ import annotations

import csv
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

# Paths are resolved from this file, not the current working directory, so the
# app behaves the same whether you run it from the project root or elsewhere.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_CATALOG = DATA_DIR / "songs.csv"
EXTENDED_CATALOG = DATA_DIR / "songs_extended.csv"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Song:
    """
    Represents a song and its attributes.
    Required by tests/test_recommender.py
    """

    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float

    @classmethod
    def from_dict(cls, row: Dict) -> "Song":
        """Builds a Song from a CSV row or plain dict, coercing numeric types."""
        return cls(
            id=int(row["id"]),
            title=str(row["title"]),
            artist=str(row["artist"]),
            genre=str(row["genre"]).strip().lower(),
            mood=str(row["mood"]).strip().lower(),
            energy=float(row["energy"]),
            tempo_bpm=float(row["tempo_bpm"]),
            valence=float(row["valence"]),
            danceability=float(row["danceability"]),
            acousticness=float(row["acousticness"]),
        )

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "artist": self.artist,
            "genre": self.genre,
            "mood": self.mood,
            "energy": self.energy,
            "tempo_bpm": self.tempo_bpm,
            "valence": self.valence,
            "danceability": self.danceability,
            "acousticness": self.acousticness,
        }


@dataclass
class UserProfile:
    """
    Represents a user's taste preferences.
    Required by tests/test_recommender.py
    """

    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool

    @classmethod
    def from_dict(cls, prefs: Dict) -> "UserProfile":
        """
        Builds a UserProfile from the looser dict shape used by main.py.

        Accepts either the dataclass field names or the shorter aliases
        ("genre", "mood", "energy") that the starter main.py passes.
        """
        genre = prefs.get("favorite_genre", prefs.get("genre", ""))
        mood = prefs.get("favorite_mood", prefs.get("mood", ""))
        energy = prefs.get("target_energy", prefs.get("energy", 0.5))
        likes_acoustic = prefs.get("likes_acoustic", False)
        return cls(
            favorite_genre=str(genre).strip().lower(),
            favorite_mood=str(mood).strip().lower(),
            target_energy=float(energy),
            likes_acoustic=bool(likes_acoustic),
        )


# ---------------------------------------------------------------------------
# Feature similarity helpers
#
# Each returns a value on a fixed, comparable scale:
#   genre/mood/energy -> [0.0, 1.0]   (0 = no fit, 1 = perfect fit)
#   acoustic          -> [-1.0, 1.0]  (signed: a mismatch is penalized)
# Keeping the scales fixed is what makes the weights interpretable.
# ---------------------------------------------------------------------------

# Moods in the same cluster are treated as near-synonyms. The catalog uses
# "chill", "relaxed" and "focused" for what is essentially the same listening
# situation, so exact-match-only scoring would throw away real signal.
MOOD_CLUSTERS: Sequence[frozenset] = (
    frozenset({"chill", "relaxed", "focused", "mellow", "dreamy", "sleepy"}),
    frozenset({"happy", "upbeat", "joyful"}),
    frozenset({"intense", "energetic", "aggressive"}),
    frozenset({"moody", "melancholy", "sad", "somber"}),
)

# Credit given when two moods land in the same cluster but are not identical.
MOOD_CLUSTER_CREDIT = 0.6


def genre_similarity(a: str, b: str) -> float:
    """
    Token-overlap (Jaccard) similarity between two genre labels.

    Exact match scores 1.0. "indie pop" vs "pop" scores 0.5 rather than 0,
    which matters because the catalog contains both.
    """
    tokens_a = set(str(a).strip().lower().split())
    tokens_b = set(str(b).strip().lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    union = tokens_a | tokens_b
    return len(tokens_a & tokens_b) / len(union)


def mood_similarity(a: str, b: str) -> float:
    """Exact mood match scores 1.0; same-cluster moods get partial credit."""
    mood_a = str(a).strip().lower()
    mood_b = str(b).strip().lower()
    if not mood_a or not mood_b:
        return 0.0
    if mood_a == mood_b:
        return 1.0
    for cluster in MOOD_CLUSTERS:
        if mood_a in cluster and mood_b in cluster:
            return MOOD_CLUSTER_CREDIT
    return 0.0


def energy_fit(target: float, actual: float, sigma: float = 0.25) -> float:
    """
    Gaussian closeness between the user's target energy and the song's energy.

    A Gaussian is used instead of a linear 1 - |difference| so there is a
    tolerance band: small mismatches barely matter, large ones fall off fast.
    `sigma` is the width of that band and is worth tuning as an experiment.
    """
    delta = float(target) - float(actual)
    return math.exp(-(delta * delta) / (2.0 * sigma * sigma))


def acoustic_fit(likes_acoustic: bool, acousticness: float) -> float:
    """
    Signed fit in [-1, 1] for the acoustic preference.

    Signed rather than a one-sided bonus: a user who dislikes acoustic music
    should have acoustic-heavy tracks pushed *down*, not merely left alone.
    """
    centered = (float(acousticness) - 0.5) * 2.0
    return centered if likes_acoustic else -centered


# ---------------------------------------------------------------------------
# Score breakdown
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeatureContribution:
    """One feature's contribution to a song's total score."""

    name: str
    weight: float
    match: float
    reason: str

    @property
    def points(self) -> float:
        return self.weight * self.match


@dataclass(frozen=True)
class ScoreBreakdown:
    """A song's total score plus the per-feature terms that produced it."""

    total: float
    contributions: List[FeatureContribution] = field(default_factory=list)

    def positive_reasons(self, min_points: float = 0.05) -> List[str]:
        ranked = sorted(self.contributions, key=lambda c: -c.points)
        return [c.reason for c in ranked if c.points >= min_points]

    def negative_reasons(self, max_points: float = -0.05) -> List[str]:
        ranked = sorted(self.contributions, key=lambda c: c.points)
        return [c.reason for c in ranked if c.points <= max_points]

    def explanation(self, max_reasons: int = 3) -> str:
        """
        Human-readable explanation, always non-empty.

        Leads with the strongest positive terms and appends the single worst
        negative term as a caveat, so the explanation stays honest about why a
        song ranked where it did.
        """
        positives = self.positive_reasons()[:max_reasons]
        negatives = self.negative_reasons()
        if not positives:
            base = "no strong match with your profile, included only to fill out the list"
        else:
            base = "; ".join(positives)
        if negatives:
            base += f" (but {negatives[0]})"
        return base


# ---------------------------------------------------------------------------
# Scoring strategies (Strategy pattern)
# ---------------------------------------------------------------------------


class ScoringStrategy(ABC):
    """
    Interface for a scoring model.

    Swapping strategies is how experiments are run: the Recommender, the CLI and
    the tests are all unchanged, only the scoring rule differs.
    """

    name: str = "abstract"

    @abstractmethod
    def score(self, user: UserProfile, song: Song) -> ScoreBreakdown:
        """Returns the song's score and the per-feature terms behind it."""


class WeightedScorer(ScoringStrategy):
    """
    Weighted additive model over genre, mood, energy and acoustic texture.

    Because every feature term is normalized first, the weights are directly
    comparable - halving `genre_weight` really does halve genre's influence
    relative to mood.
    """

    name = "weighted"

    def __init__(
        self,
        genre_weight: float = 2.0,
        mood_weight: float = 1.5,
        energy_weight: float = 1.5,
        acoustic_weight: float = 0.75,
        energy_sigma: float = 0.25,
    ) -> None:
        self.genre_weight = genre_weight
        self.mood_weight = mood_weight
        self.energy_weight = energy_weight
        self.acoustic_weight = acoustic_weight
        self.energy_sigma = energy_sigma

    @property
    def max_score(self) -> float:
        """Score a hypothetical perfect song would receive. Useful for reading output."""
        return (
            self.genre_weight
            + self.mood_weight
            + self.energy_weight
            + self.acoustic_weight
        )

    def score(self, user: UserProfile, song: Song) -> ScoreBreakdown:
        contributions: List[FeatureContribution] = []

        genre_match = genre_similarity(user.favorite_genre, song.genre)
        if genre_match >= 1.0:
            genre_reason = f"it is {song.genre}, your favorite genre"
        elif genre_match > 0.0:
            genre_reason = f"{song.genre} partly overlaps your favorite ({user.favorite_genre})"
        else:
            genre_reason = f"{song.genre} is outside your favorite genre"
        contributions.append(
            FeatureContribution("genre", self.genre_weight, genre_match, genre_reason)
        )

        mood_match = mood_similarity(user.favorite_mood, song.mood)
        if mood_match >= 1.0:
            mood_reason = f"the mood is {song.mood}, exactly what you asked for"
        elif mood_match > 0.0:
            mood_reason = f"a {song.mood} mood is close to {user.favorite_mood}"
        else:
            mood_reason = f"the {song.mood} mood does not match {user.favorite_mood}"
        contributions.append(
            FeatureContribution("mood", self.mood_weight, mood_match, mood_reason)
        )

        energy_match = energy_fit(user.target_energy, song.energy, self.energy_sigma)
        if energy_match >= 0.6:
            energy_reason = (
                f"its energy ({song.energy:.2f}) is close to your target "
                f"({user.target_energy:.2f})"
            )
        else:
            energy_reason = (
                f"its energy ({song.energy:.2f}) is far from your target "
                f"({user.target_energy:.2f})"
            )
        contributions.append(
            FeatureContribution("energy", self.energy_weight, energy_match, energy_reason)
        )

        acoustic_match = acoustic_fit(user.likes_acoustic, song.acousticness)
        if acoustic_match >= 0:
            acoustic_reason = (
                f"its acoustic texture ({song.acousticness:.2f}) suits your taste"
            )
        else:
            acoustic_reason = (
                "it is more acoustic than you like"
                if not user.likes_acoustic
                else "it is less acoustic than you like"
            )
        contributions.append(
            FeatureContribution(
                "acoustic", self.acoustic_weight, acoustic_match, acoustic_reason
            )
        )

        total = sum(c.points for c in contributions)
        return ScoreBreakdown(total=total, contributions=contributions)


class GenreOnlyScorer(ScoringStrategy):
    """
    Ablation baseline: genre similarity and nothing else.

    Exists so the weighted model can be compared against something. If the full
    model does not beat this on your test profiles, the extra features are not
    earning their complexity.
    """

    name = "genre_only"

    def __init__(self, genre_weight: float = 1.0) -> None:
        self.genre_weight = genre_weight

    def score(self, user: UserProfile, song: Song) -> ScoreBreakdown:
        match = genre_similarity(user.favorite_genre, song.genre)
        reason = (
            f"it is {song.genre}, your favorite genre"
            if match >= 1.0
            else f"{song.genre} partly overlaps your favorite ({user.favorite_genre})"
            if match > 0
            else f"{song.genre} is outside your favorite genre"
        )
        contribution = FeatureContribution("genre", self.genre_weight, match, reason)
        return ScoreBreakdown(total=contribution.points, contributions=[contribution])


# ---------------------------------------------------------------------------
# Recommender
# ---------------------------------------------------------------------------


class Recommender:
    """
    OOP implementation of the recommendation logic.
    Required by tests/test_recommender.py
    """

    def __init__(self, songs: List[Song], scorer: Optional[ScoringStrategy] = None):
        self.songs = songs
        self.scorer = scorer if scorer is not None else WeightedScorer()

    def score_breakdown(self, user: UserProfile, song: Song) -> ScoreBreakdown:
        return self.scorer.score(user, song)

    def ranked(self, user: UserProfile) -> List[Tuple[Song, ScoreBreakdown]]:
        """
        Every song, best first.

        Ties break on song id so the ordering is deterministic. On a catalog this
        small, ties are common and unstable output would make tests flaky.
        """
        scored = [(song, self.scorer.score(user, song)) for song in self.songs]
        scored.sort(key=lambda pair: (-pair[1].total, pair[0].id))
        return scored

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        return [song for song, _ in self.ranked(user)[:k]]

    def recommend_with_scores(
        self, user: UserProfile, k: int = 5
    ) -> List[Tuple[Song, float, str]]:
        """Top k as (song, score, explanation), for callers that want to display why."""
        return [
            (song, breakdown.total, breakdown.explanation())
            for song, breakdown in self.ranked(user)[:k]
        ]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        return self.scorer.score(user, song).explanation()


# ---------------------------------------------------------------------------
# Dict-based API used by src/main.py
#
# These are thin adapters over the same scorer - they do not reimplement the
# model, so the two APIs cannot drift apart.
# ---------------------------------------------------------------------------


def load_songs(csv_path: str = str(DEFAULT_CATALOG)) -> List[Dict]:
    """
    Loads songs from a CSV file.
    Required by src/main.py

    Relative paths are resolved against the project root, so `python -m src.main`
    works from anywhere. Blank rows are skipped; malformed rows raise.
    """
    path = Path(csv_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"No song catalog at {path}")

    songs: List[Dict] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for line_no, row in enumerate(csv.DictReader(handle), start=2):
            if not row or not (row.get("id") or "").strip():
                continue
            try:
                songs.append(Song.from_dict(row).to_dict())
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Bad row in {path.name} at line {line_no}: {exc}") from exc
    return songs


def score_song(
    user_prefs: Dict, song: Dict, scorer: Optional[ScoringStrategy] = None
) -> Tuple[float, List[str]]:
    """
    Scores a single song against user preferences.
    Required by recommend_songs() and src/main.py
    """
    active = scorer if scorer is not None else WeightedScorer()
    breakdown = active.score(UserProfile.from_dict(user_prefs), Song.from_dict(song))
    return breakdown.total, breakdown.positive_reasons()


def recommend_songs(
    user_prefs: Dict,
    songs: List[Dict],
    k: int = 5,
    scorer: Optional[ScoringStrategy] = None,
) -> List[Tuple[Dict, float, str]]:
    """
    Functional implementation of the recommendation logic.
    Required by src/main.py
    """
    user = UserProfile.from_dict(user_prefs)
    recommender = Recommender([Song.from_dict(song) for song in songs], scorer=scorer)

    # Return the caller's own dicts rather than round-tripped copies.
    by_id = {int(song["id"]): song for song in songs}
    return [
        (by_id[song.id], breakdown.total, breakdown.explanation())
        for song, breakdown in recommender.ranked(user)[:k]
    ]
