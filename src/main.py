"""
Command line runner for the Music Recommender Simulation.

Usage:
    python -m src.main                          # default catalog, weighted model
    python -m src.main --catalog data/songs_extended.csv
    python -m src.main --compare                # weighted vs genre-only, side by side

The scoring model lives in recommender.py; this file only chooses a catalog,
a profile and a strategy, then prints the result.
"""

import argparse
from typing import Dict, List

from src.recommender import (
    GenreOnlyScorer,
    ScoringStrategy,
    WeightedScorer,
    load_songs,
    recommend_songs,
)

# Profiles used for the demo run and for the experiments in the README.
# "melancholy" exists to expose a real gap: the default catalog has no song with
# valence below 0.48, so there is nothing genuinely sad to recommend.
DEMO_PROFILES: Dict[str, Dict] = {
    "pop-happy": {
        "genre": "pop",
        "mood": "happy",
        "energy": 0.8,
        "likes_acoustic": False,
    },
    "lofi-study": {
        "genre": "lofi",
        "mood": "focused",
        "energy": 0.4,
        "likes_acoustic": True,
    },
    "melancholy": {
        "genre": "indie",
        "mood": "sad",
        "energy": 0.3,
        "likes_acoustic": True,
    },
}


def print_recommendations(
    label: str, user_prefs: Dict, songs: List[Dict], k: int, scorer: ScoringStrategy
) -> None:
    print(f"\n=== {label} | model: {scorer.name} ===")
    print(f"Profile: {user_prefs}\n")

    for rank, (song, score, explanation) in enumerate(
        recommend_songs(user_prefs, songs, k=k, scorer=scorer), start=1
    ):
        print(f"{rank}. {song['title']} - {song['artist']}  (score {score:.2f})")
        print(f"   Because: {explanation}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Music Recommender Simulation")
    parser.add_argument(
        "--catalog",
        default="data/songs.csv",
        help="Path to the song catalog CSV (default: data/songs.csv)",
    )
    parser.add_argument("--k", type=int, default=5, help="How many songs to recommend")
    parser.add_argument(
        "--profile",
        choices=sorted(DEMO_PROFILES) + ["all"],
        default="pop-happy",
        help="Which demo profile to run",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Run the weighted model and the genre-only baseline side by side",
    )
    args = parser.parse_args()

    songs = load_songs(args.catalog)
    print(f"Loaded {len(songs)} songs from {args.catalog}")

    profiles = DEMO_PROFILES if args.profile == "all" else {args.profile: DEMO_PROFILES[args.profile]}
    scorers: List[ScoringStrategy] = [WeightedScorer()]
    if args.compare:
        scorers.append(GenreOnlyScorer())

    for label, prefs in profiles.items():
        for scorer in scorers:
            print_recommendations(label, prefs, songs, args.k, scorer)


if __name__ == "__main__":
    main()
