"""
Property tests for the recommender.

These assert things that must hold for *any* sensible scoring rule, rather than
pinning one hand-computed output. That makes them survive weight tuning while
still catching real regressions - including the failure the starter test misses,
where a "recommender" simply returns the input list unchanged.
"""

import random
from dataclasses import replace

import pytest

from src.recommender import (
    EXTENDED_CATALOG,
    GenreOnlyScorer,
    Recommender,
    Song,
    UserProfile,
    WeightedScorer,
    energy_fit,
    genre_similarity,
    load_songs,
    mood_similarity,
    recommend_songs,
    score_song,
)


def song(**overrides) -> Song:
    """A neutral song; override only the fields a test cares about."""
    base = dict(
        id=1,
        title="Test Track",
        artist="Test Artist",
        genre="pop",
        mood="happy",
        energy=0.5,
        tempo_bpm=110,
        valence=0.5,
        danceability=0.5,
        acousticness=0.5,
    )
    base.update(overrides)
    return Song(**base)


POP_FAN = UserProfile(
    favorite_genre="pop",
    favorite_mood="happy",
    target_energy=0.8,
    likes_acoustic=False,
)


# ---------------------------------------------------------------------------
# The test the starter was missing: input order must not be the answer.
# ---------------------------------------------------------------------------


def test_best_song_is_not_simply_the_first_song():
    """
    The starter fixture put the correct answer first, so `return songs[:k]` passed.
    Here the match is last, so returning input order fails.
    """
    songs = [
        song(id=1, genre="ambient", mood="chill", energy=0.1, acousticness=0.95),
        song(id=2, genre="jazz", mood="relaxed", energy=0.2, acousticness=0.9),
        song(id=3, genre="pop", mood="happy", energy=0.8, acousticness=0.1),
    ]
    results = Recommender(songs).recommend(POP_FAN, k=3)
    assert results[0].id == 3


def test_top_k_is_invariant_to_input_order():
    """Shuffling the catalog must not change which songs come back, or their order."""
    songs = load_songs(str(EXTENDED_CATALOG))
    baseline = [s["id"] for s, _, _ in recommend_songs(vars(POP_FAN), songs, k=5)]

    rng = random.Random(20260721)
    for _ in range(10):
        shuffled = songs[:]
        rng.shuffle(shuffled)
        got = [s["id"] for s, _, _ in recommend_songs(vars(POP_FAN), shuffled, k=5)]
        assert got == baseline


def test_ranking_is_deterministic_across_runs():
    songs = load_songs(str(EXTENDED_CATALOG))
    rec = Recommender([Song.from_dict(s) for s in songs])
    first = [s.id for s in rec.recommend(POP_FAN, k=10)]
    second = [s.id for s in rec.recommend(POP_FAN, k=10)]
    assert first == second


def test_ties_break_on_lower_id():
    """Identical songs must come back in a stable, predictable order."""
    songs = [song(id=7), song(id=3), song(id=5)]
    results = Recommender(songs).recommend(POP_FAN, k=3)
    assert [s.id for s in results] == [3, 5, 7]


# ---------------------------------------------------------------------------
# Monotonicity: improving a feature must never hurt the score.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("target", [0.0, 0.3, 0.5, 0.8, 1.0])
def test_moving_energy_toward_target_never_lowers_score(target):
    user = replace(POP_FAN, target_energy=target)
    scorer = WeightedScorer()

    previous = None
    # Walk a song's energy from 0 up to the target; the score must not decrease.
    steps = [round(i * 0.05, 2) for i in range(0, int(target * 20) + 1)]
    for energy in steps:
        current = scorer.score(user, song(energy=energy)).total
        if previous is not None:
            assert current >= previous - 1e-9, f"score dropped moving energy to {energy}"
        previous = current


def test_exact_genre_match_scores_at_least_as_high_as_partial_or_none():
    scorer = WeightedScorer()
    exact = scorer.score(POP_FAN, song(genre="pop")).total
    partial = scorer.score(POP_FAN, song(genre="indie pop")).total
    none = scorer.score(POP_FAN, song(genre="jazz")).total
    assert exact > partial > none


def test_acoustic_preference_is_symmetric():
    """Disliking acoustic must penalize acoustic songs, not merely ignore them."""
    scorer = WeightedScorer()
    likes = replace(POP_FAN, likes_acoustic=True)
    dislikes = replace(POP_FAN, likes_acoustic=False)

    acoustic_song = song(acousticness=0.95)
    assert scorer.score(likes, acoustic_song).total > scorer.score(dislikes, acoustic_song).total


# ---------------------------------------------------------------------------
# Feature similarity helpers
# ---------------------------------------------------------------------------


def test_genre_similarity_gives_partial_credit_for_compound_genres():
    assert genre_similarity("pop", "pop") == 1.0
    assert genre_similarity("pop", "indie pop") == pytest.approx(0.5)
    assert genre_similarity("pop", "jazz") == 0.0
    assert genre_similarity("", "pop") == 0.0


def test_mood_similarity_credits_near_synonyms():
    assert mood_similarity("chill", "chill") == 1.0
    assert 0 < mood_similarity("chill", "relaxed") < 1
    assert mood_similarity("chill", "intense") == 0.0


def test_energy_fit_peaks_at_the_target_and_is_symmetric():
    assert energy_fit(0.5, 0.5) == pytest.approx(1.0)
    assert energy_fit(0.5, 0.3) == pytest.approx(energy_fit(0.5, 0.7))
    assert energy_fit(0.5, 0.0) < energy_fit(0.5, 0.4)


# ---------------------------------------------------------------------------
# Structural guarantees
# ---------------------------------------------------------------------------


def test_scores_are_sorted_descending():
    songs = [Song.from_dict(s) for s in load_songs(str(EXTENDED_CATALOG))]
    ranked = Recommender(songs).ranked(POP_FAN)
    totals = [breakdown.total for _, breakdown in ranked]
    assert totals == sorted(totals, reverse=True)


def test_k_larger_than_catalog_returns_everything_without_duplicates():
    songs = [song(id=1), song(id=2, genre="jazz")]
    results = Recommender(songs).recommend(POP_FAN, k=99)
    assert len(results) == 2
    assert len({s.id for s in results}) == 2


def test_every_recommendation_has_a_non_empty_explanation():
    """Including songs that match nothing - explanations must never be blank."""
    songs = [Song.from_dict(s) for s in load_songs(str(EXTENDED_CATALOG))]
    rec = Recommender(songs)
    loner = UserProfile(
        favorite_genre="polka",
        favorite_mood="triumphant",
        target_energy=0.5,
        likes_acoustic=False,
    )
    for candidate in songs:
        assert rec.explain_recommendation(loner, candidate).strip() != ""


def test_explanation_agrees_with_the_score():
    """A perfect-match song must cite genre; an off-genre song must not."""
    rec = Recommender([song(genre="pop"), song(id=2, genre="jazz")])
    assert "pop" in rec.explain_recommendation(POP_FAN, rec.songs[0])
    assert "your favorite genre" not in rec.explain_recommendation(POP_FAN, rec.songs[1])


# ---------------------------------------------------------------------------
# Strategy pattern: swapping the model changes results, not the plumbing.
# ---------------------------------------------------------------------------


def test_strategies_are_interchangeable_and_actually_differ():
    songs = [Song.from_dict(s) for s in load_songs(str(EXTENDED_CATALOG))]
    weighted = [s.id for s in Recommender(songs, WeightedScorer()).recommend(POP_FAN, k=5)]
    genre_only = [s.id for s in Recommender(songs, GenreOnlyScorer()).recommend(POP_FAN, k=5)]

    assert len(weighted) == len(genre_only) == 5
    assert weighted != genre_only, "the extra features are not changing anything"


def test_lowering_genre_weight_changes_the_ranking():
    """
    The README's 2.0 -> 0.5 experiment must actually be observable.

    Note the profile: a jazz fan. For a pop fan the top 5 does NOT change, because
    in this catalog pop songs are also the happy, high-energy ones - genre is
    partly redundant with mood and energy. The weight only bites for listeners in
    sparse genres. That asymmetry is a finding, not a bug; see the README.
    """
    songs = [Song.from_dict(s) for s in load_songs(str(EXTENDED_CATALOG))]
    jazz_fan = UserProfile(
        favorite_genre="jazz",
        favorite_mood="relaxed",
        target_energy=0.35,
        likes_acoustic=True,
    )
    heavy = [s.id for s in Recommender(songs, WeightedScorer(genre_weight=2.0)).recommend(jazz_fan, k=5)]
    light = [s.id for s in Recommender(songs, WeightedScorer(genre_weight=0.5)).recommend(jazz_fan, k=5)]
    assert heavy != light


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def test_load_songs_reads_the_extended_catalog_with_correct_types():
    songs = load_songs(str(EXTENDED_CATALOG))
    assert len(songs) == 40
    first = songs[0]
    assert isinstance(first["id"], int)
    assert isinstance(first["energy"], float)
    assert {s["id"] for s in songs} == set(range(1, 41))


def test_load_songs_rejects_a_missing_file():
    with pytest.raises(FileNotFoundError):
        load_songs("data/does_not_exist.csv")


def test_load_songs_reports_the_line_of_a_malformed_row(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "id,title,artist,genre,mood,energy,tempo_bpm,valence,danceability,acousticness\n"
        "1,Good,A,pop,happy,0.5,110,0.5,0.5,0.5\n"
        "2,Bad,A,pop,happy,NOT_A_NUMBER,110,0.5,0.5,0.5\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="line 3"):
        load_songs(str(bad))


# ---------------------------------------------------------------------------
# The two public APIs must agree - there is only one model.
# ---------------------------------------------------------------------------


def test_dict_api_and_oop_api_produce_the_same_ranking():
    song_dicts = load_songs(str(EXTENDED_CATALOG))
    prefs = {"genre": "lofi", "mood": "focused", "energy": 0.4, "likes_acoustic": True}

    functional = [s["id"] for s, _, _ in recommend_songs(prefs, song_dicts, k=8)]
    oop = [
        s.id
        for s in Recommender([Song.from_dict(s) for s in song_dicts]).recommend(
            UserProfile.from_dict(prefs), k=8
        )
    ]
    assert functional == oop


def test_score_song_matches_the_scorer():
    prefs = {"genre": "pop", "mood": "happy", "energy": 0.8, "likes_acoustic": False}
    candidate = song(genre="pop", mood="happy", energy=0.8, acousticness=0.1)

    score, reasons = score_song(prefs, candidate.to_dict())
    assert score == pytest.approx(WeightedScorer().score(POP_FAN, candidate).total)
    assert reasons, "a perfect match should produce at least one reason"


def test_recommend_songs_returns_the_callers_own_dicts():
    song_dicts = load_songs(str(EXTENDED_CATALOG))
    prefs = {"genre": "pop", "mood": "happy", "energy": 0.8}
    for returned, _, _ in recommend_songs(prefs, song_dicts, k=3):
        assert any(returned is original for original in song_dicts)


# ---------------------------------------------------------------------------
# Known gap in the default catalog - documented as a test, not a comment.
# ---------------------------------------------------------------------------


def test_default_catalog_cannot_serve_a_sad_listener():
    """
    The shipped catalog has no low-valence music, so a melancholy user gets
    confidently wrong results. This test documents the bias for the model card;
    it is asserting the *dataset's* limitation, not the model's correctness.
    """
    songs = load_songs()
    assert min(s["valence"] for s in songs) > 0.45
    assert not any(s["mood"] == "sad" for s in songs)

    # The extended catalog is the fix.
    extended = load_songs(str(EXTENDED_CATALOG))
    assert min(s["valence"] for s in extended) < 0.15
    assert sum(1 for s in extended if s["mood"] == "sad") >= 5
