"""
Experimental scorer: the original four-feature model plus tempo and valence.

This module does not modify recommender.py in any way. It imports from it and
extends it, so:

  - `ExtendedWeightedScorer` calls `WeightedScorer.score()` for the original four
    terms and only *appends* two more. The genre/mood/energy/acoustic numbers are
    therefore bit-for-bit identical to the baseline, which is what makes the
    comparison controlled - any ranking difference is caused by the two new
    features and nothing else.
  - `Recommender`, the ranking rule, the explanation machinery and both catalogs
    are reused unchanged.

Run `python -m src.compare_models` to see the two models side by side.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional

from src.recommender import (
    FeatureContribution,
    ScoreBreakdown,
    Song,
    UserProfile,
    WeightedScorer,
    energy_fit,
)

# Tempo is measured in BPM, not on a 0-1 scale like every other feature. Rather
# than min-max rescaling against catalog bounds (which would make scores depend
# on which catalog is loaded), the fit is a Gaussian whose width is expressed
# directly in BPM. The output is still 0-1, so the weight stays comparable.
TEMPO_SIGMA_BPM = 20.0

# Valence is already 0-1, so it uses the same width as energy.
VALENCE_SIGMA = 0.25


@dataclass
class ExtendedUserProfile(UserProfile):
    """
    A UserProfile that can also state a target valence and tempo.

    Both are optional. If a listener does not state a preference, the
    corresponding term is skipped entirely rather than being given an invented
    default - inventing one would silently reorder results based on a preference
    the user never expressed.
    """

    target_valence: Optional[float] = None
    target_tempo_bpm: Optional[float] = None


def valence_fit(target: float, actual: float, sigma: float = VALENCE_SIGMA) -> float:
    """Gaussian closeness on the happy/sad axis. Same shape as energy_fit."""
    return energy_fit(target, actual, sigma)


def tempo_fit(
    target_bpm: float, actual_bpm: float, sigma_bpm: float = TEMPO_SIGMA_BPM
) -> float:
    """
    Gaussian closeness in BPM, returning 0-1.

    With sigma = 20 BPM, a song about 24 BPM away from the target scores 0.5.
    """
    delta = float(target_bpm) - float(actual_bpm)
    return math.exp(-(delta * delta) / (2.0 * sigma_bpm * sigma_bpm))


class ExtendedWeightedScorer(WeightedScorer):
    """
    Six-feature model: genre, mood, energy, acoustic, valence, tempo.

    Inherits the original four terms rather than reimplementing them.
    """

    name = "weighted_v2"

    def __init__(
        self,
        valence_weight: float = 1.25,
        tempo_weight: float = 1.0,
        valence_sigma: float = VALENCE_SIGMA,
        tempo_sigma_bpm: float = TEMPO_SIGMA_BPM,
        **kwargs,
    ) -> None:
        # kwargs forwards genre_weight / mood_weight / energy_weight /
        # acoustic_weight / energy_sigma to the baseline unchanged.
        super().__init__(**kwargs)
        self.valence_weight = valence_weight
        self.tempo_weight = tempo_weight
        self.valence_sigma = valence_sigma
        self.tempo_sigma_bpm = tempo_sigma_bpm

    def max_score_for(self, user: UserProfile) -> float:
        """
        Best achievable score for this particular listener.

        Depends on the user, because skipped terms cannot contribute. Used to put
        two models with different numbers of features on a common 0-1 scale.
        """
        total = super().max_score
        if getattr(user, "target_valence", None) is not None:
            total += self.valence_weight
        if getattr(user, "target_tempo_bpm", None) is not None:
            total += self.tempo_weight
        return total

    def score(self, user: UserProfile, song: Song) -> ScoreBreakdown:
        base = super().score(user, song)
        contributions: List[FeatureContribution] = list(base.contributions)

        target_valence = getattr(user, "target_valence", None)
        if target_valence is not None:
            match = valence_fit(target_valence, song.valence, self.valence_sigma)
            if match >= 0.6:
                reason = (
                    f"its emotional tone (valence {song.valence:.2f}) is close to "
                    f"what you want ({target_valence:.2f})"
                )
            elif song.valence < target_valence:
                reason = f"it sounds sadder (valence {song.valence:.2f}) than you asked for"
            else:
                reason = f"it sounds brighter (valence {song.valence:.2f}) than you asked for"
            contributions.append(
                FeatureContribution("valence", self.valence_weight, match, reason)
            )

        target_tempo = getattr(user, "target_tempo_bpm", None)
        if target_tempo is not None:
            match = tempo_fit(target_tempo, song.tempo_bpm, self.tempo_sigma_bpm)
            if match >= 0.6:
                reason = (
                    f"its tempo ({song.tempo_bpm:.0f} BPM) is close to your target "
                    f"({target_tempo:.0f} BPM)"
                )
            elif song.tempo_bpm < target_tempo:
                reason = f"it is slower ({song.tempo_bpm:.0f} BPM) than you asked for"
            else:
                reason = f"it is faster ({song.tempo_bpm:.0f} BPM) than you asked for"
            contributions.append(
                FeatureContribution("tempo", self.tempo_weight, match, reason)
            )

        total = sum(c.points for c in contributions)
        return ScoreBreakdown(total=total, contributions=contributions)
