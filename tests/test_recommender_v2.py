"""
Tests for the 6-feature experimental scorer.

The most important ones here are the isolation tests: they prove the experiment
does not change the baseline's behaviour, which is what makes any difference in
the comparison attributable to the two new features alone.
"""

import pytest

from src.recommender import (
    EXTENDED_CATALOG,
    Recommender,
    Song,
    UserProfile,
    WeightedScorer,
    load_songs,
)
from src.recommender_v2 import (
    ExtendedUserProfile,
    ExtendedWeightedScorer,
    tempo_fit,
    valence_fit,
)


def song(**overrides) -> Song:
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


PLAIN = UserProfile("pop", "happy", 0.8, False)
EXTENDED = ExtendedUserProfile("pop", "happy", 0.8, False, target_valence=0.85, target_tempo_bpm=120)
CATALOG = [Song.from_dict(row) for row in load_songs(str(EXTENDED_CATALOG))]


# ---------------------------------------------------------------------------
# Isolation: the experiment must not disturb the original model.
# ---------------------------------------------------------------------------


def test_baseline_ignores_the_new_preferences():
    """An ExtendedUserProfile scored by the baseline must equal a plain profile."""
    baseline = WeightedScorer()
    for candidate in CATALOG:
        assert baseline.score(EXTENDED, candidate).total == pytest.approx(
            baseline.score(PLAIN, candidate).total
        )


def test_extended_reuses_the_baseline_terms_unchanged():
    """
    The first four contributions must be bit-for-bit identical to the baseline's.
    This is what makes the comparison controlled rather than confounded.
    """
    baseline = WeightedScorer()
    extended = ExtendedWeightedScorer()
    for candidate in CATALOG:
        base_terms = baseline.score(EXTENDED, candidate).contributions
        ext_terms = extended.score(EXTENDED, candidate).contributions[: len(base_terms)]
        assert [(c.name, c.weight, c.match) for c in base_terms] == [
            (c.name, c.weight, c.match) for c in ext_terms
        ]


def test_extended_collapses_to_the_baseline_when_no_new_preferences_are_given():
    """Omitted preferences are skipped, not defaulted - so the models agree exactly."""
    silent = ExtendedUserProfile("pop", "happy", 0.8, False)  # no valence, no tempo
    baseline = WeightedScorer()
    extended = ExtendedWeightedScorer()
    for candidate in CATALOG:
        assert extended.score(silent, candidate).total == pytest.approx(
            baseline.score(silent, candidate).total
        )

    base_ids = [s.id for s in Recommender(CATALOG, baseline).recommend(silent, k=10)]
    ext_ids = [s.id for s in Recommender(CATALOG, extended).recommend(silent, k=10)]
    assert base_ids == ext_ids


# ---------------------------------------------------------------------------
# The new feature terms
# ---------------------------------------------------------------------------


def test_tempo_fit_peaks_at_the_target_and_is_symmetric():
    assert tempo_fit(120, 120) == pytest.approx(1.0)
    assert tempo_fit(120, 100) == pytest.approx(tempo_fit(120, 140))
    assert tempo_fit(120, 60) < tempo_fit(120, 110)


def test_valence_fit_peaks_at_the_target():
    assert valence_fit(0.5, 0.5) == pytest.approx(1.0)
    assert valence_fit(0.2, 0.9) < valence_fit(0.2, 0.3)


def test_valence_separates_songs_the_baseline_cannot_tell_apart():
    """
    Two songs identical except for valence. The baseline scores them the same;
    the extended model prefers the one matching the requested emotional tone.
    """
    bleak = song(id=1, mood="sad", valence=0.05)
    wistful = song(id=2, mood="sad", valence=0.45)
    user = ExtendedUserProfile("pop", "sad", 0.5, False, target_valence=0.45)

    baseline = WeightedScorer()
    assert baseline.score(user, bleak).total == pytest.approx(
        baseline.score(user, wistful).total
    )

    extended = ExtendedWeightedScorer()
    assert extended.score(user, wistful).total > extended.score(user, bleak).total


def test_moving_tempo_toward_the_target_never_lowers_the_score():
    extended = ExtendedWeightedScorer()
    previous = None
    for bpm in range(60, 121, 5):
        current = extended.score(EXTENDED, song(tempo_bpm=bpm)).total
        if previous is not None:
            assert current >= previous - 1e-9
        previous = current


# ---------------------------------------------------------------------------
# Bookkeeping
# ---------------------------------------------------------------------------


def test_max_score_reflects_which_terms_are_active():
    extended = ExtendedWeightedScorer()
    both = extended.max_score_for(EXTENDED)
    neither = extended.max_score_for(ExtendedUserProfile("pop", "happy", 0.8, False))
    assert both == pytest.approx(8.0)
    assert neither == pytest.approx(WeightedScorer().max_score)


def test_the_default_explanation_hides_the_new_features():
    """
    Documents a real limitation. The explanation shows only the top 3 positive
    terms, and genre/mood/energy usually outrank the new ones - so valence and
    tempo can change the ranking while remaining invisible in the reason text.
    Raising the cap reveals them.
    """
    scorer = ExtendedWeightedScorer()
    top = Recommender(CATALOG, scorer).recommend(EXTENDED, k=1)[0]
    breakdown = scorer.score(EXTENDED, top)

    assert breakdown.explanation().strip() != ""
    assert {"valence", "tempo"} <= {c.name for c in breakdown.contributions}

    default_text = breakdown.explanation()
    full_text = breakdown.explanation(max_reasons=6)
    assert "BPM" not in default_text and "valence" not in default_text
    assert "BPM" in full_text or "valence" in full_text


def test_extended_model_actually_changes_some_rankings():
    """If the two extra features never changed anything, the experiment is pointless."""
    user = ExtendedUserProfile(
        "pop", "sad", 0.4, False, target_valence=0.45, target_tempo_bpm=95
    )
    base_ids = [s.id for s in Recommender(CATALOG, WeightedScorer()).recommend(user, k=5)]
    ext_ids = [s.id for s in Recommender(CATALOG, ExtendedWeightedScorer()).recommend(user, k=5)]
    assert base_ids != ext_ids
