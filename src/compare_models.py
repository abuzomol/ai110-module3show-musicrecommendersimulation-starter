"""
Side-by-side comparison of the 4-feature baseline and the 6-feature experiment.

    python -m src.compare_models
    python -m src.compare_models --catalog data/songs.csv --k 3
    python -m src.compare_models --profile melancholy --detail

Both models are run over the same catalog, the same profiles and the same ranking
rule, so the only difference is the two extra features.
"""

import argparse
from typing import Dict, List, Sequence, Tuple

from src.recommender import (
    Recommender,
    ScoringStrategy,
    Song,
    WeightedScorer,
    load_songs,
)
from src.recommender_v2 import ExtendedUserProfile, ExtendedWeightedScorer

# The baseline ignores target_valence / target_tempo_bpm, so one profile object
# can drive both models.
COMPARISON_PROFILES: Dict[str, ExtendedUserProfile] = {
    "pop-happy": ExtendedUserProfile(
        favorite_genre="pop",
        favorite_mood="happy",
        target_energy=0.8,
        likes_acoustic=False,
        target_valence=0.85,
        target_tempo_bpm=120,
    ),
    "lofi-study": ExtendedUserProfile(
        favorite_genre="lofi",
        favorite_mood="focused",
        target_energy=0.4,
        likes_acoustic=True,
        target_valence=0.55,
        target_tempo_bpm=80,
    ),
    "melancholy": ExtendedUserProfile(
        favorite_genre="indie",
        favorite_mood="sad",
        target_energy=0.3,
        likes_acoustic=True,
        target_valence=0.15,
        target_tempo_bpm=70,
    ),
    "jazz-relaxed": ExtendedUserProfile(
        favorite_genre="jazz",
        favorite_mood="relaxed",
        target_energy=0.35,
        likes_acoustic=True,
        target_valence=0.60,
        target_tempo_bpm=90,
    ),
    # Two songs in the extended catalog are tagged sad but sit far apart on
    # valence. The baseline cannot tell them apart; this profile makes that
    # difference visible.
    "sad-but-not-bleak": ExtendedUserProfile(
        favorite_genre="pop",
        favorite_mood="sad",
        target_energy=0.4,
        likes_acoustic=False,
        target_valence=0.45,
        target_tempo_bpm=95,
    ),
}


def best_possible(scorer: ScoringStrategy, user: ExtendedUserProfile) -> float:
    """Max achievable score, so models with different feature counts compare fairly."""
    if hasattr(scorer, "max_score_for"):
        return scorer.max_score_for(user)
    return getattr(scorer, "max_score", 1.0)


def ranked_ids(
    songs: List[Song], user: ExtendedUserProfile, scorer: ScoringStrategy, k: int
) -> List[Tuple[Song, float, float]]:
    """Top k as (song, raw score, score as a fraction of the best possible)."""
    ceiling = best_possible(scorer, user) or 1.0
    return [
        (song, breakdown.total, breakdown.total / ceiling)
        for song, breakdown in Recommender(songs, scorer).ranked(user)[:k]
    ]


def overlap(a: Sequence[int], b: Sequence[int]) -> int:
    return len(set(a) & set(b))


def compare_profile(
    label: str,
    user: ExtendedUserProfile,
    songs: List[Song],
    k: int,
    detail: bool,
) -> None:
    baseline = WeightedScorer()
    extended = ExtendedWeightedScorer()

    base_rows = ranked_ids(songs, user, baseline, k)
    ext_rows = ranked_ids(songs, user, extended, k)
    base_ids = [s.id for s, _, _ in base_rows]
    ext_ids = [s.id for s, _, _ in ext_rows]

    print(f"\n{'=' * 78}")
    print(f"PROFILE: {label}")
    print(
        f"  genre={user.favorite_genre}  mood={user.favorite_mood}  "
        f"energy={user.target_energy}  acoustic={user.likes_acoustic}  "
        f"valence={user.target_valence}  tempo={user.target_tempo_bpm}"
    )
    print("=" * 78)

    print(f"\n{'#':<3}{'BASELINE (4 features)':<38}{'EXTENDED (6 features)':<38}")
    print(f"{'':<3}{'-' * 36:<38}{'-' * 36:<38}")
    for rank in range(k):
        left = right = ""
        if rank < len(base_rows):
            song, _, norm = base_rows[rank]
            left = f" {song.title[:24]:<24} {norm:.0%}"
        if rank < len(ext_rows):
            song, _, norm = ext_rows[rank]
            marker = " " if song.id in base_ids else "*"
            right = f"{marker}{song.title[:24]:<24} {norm:.0%}"
        print(f"{rank + 1:<3}{left:<38}{right:<38}")

    shared = overlap(base_ids, ext_ids)
    entered = [s.title for s, _, _ in ext_rows if s.id not in base_ids]
    dropped = [s.title for s, _, _ in base_rows if s.id not in ext_ids]

    print(f"\n  overlap@{k}: {shared}/{k}", end="")
    print("   same order" if base_ids == ext_ids else "   order changed")
    if entered:
        print(f"  entered (*): {', '.join(entered)}")
    if dropped:
        print(f"  dropped:     {', '.join(dropped)}")

    if detail and ext_rows:
        print("\n  Why the extended model's #1 won:")
        breakdown = extended.score(user, ext_rows[0][0])
        for contribution in sorted(breakdown.contributions, key=lambda c: -c.points):
            print(
                f"    {contribution.name:<9} {contribution.points:+.2f}"
                f"   ({contribution.reason})"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare the 4- and 6-feature models")
    parser.add_argument("--catalog", default="data/songs_extended.csv")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument(
        "--profile",
        choices=sorted(COMPARISON_PROFILES) + ["all"],
        default="all",
    )
    parser.add_argument(
        "--detail",
        action="store_true",
        help="Also print the per-feature breakdown of the extended model's top pick",
    )
    args = parser.parse_args()

    songs = [Song.from_dict(row) for row in load_songs(args.catalog)]
    print(f"Catalog: {args.catalog} ({len(songs)} songs)")
    print("Baseline = genre, mood, energy, acoustic")
    print("Extended = baseline + valence + tempo")
    print("Percentages are the score as a fraction of that model's best possible score.")

    selected = (
        COMPARISON_PROFILES
        if args.profile == "all"
        else {args.profile: COMPARISON_PROFILES[args.profile]}
    )
    for label, user in selected.items():
        compare_profile(label, user, songs, args.k, args.detail)
    print()


if __name__ == "__main__":
    main()
