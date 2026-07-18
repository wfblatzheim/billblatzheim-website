"""
Runs the full mnba-ratings refresh pipeline in order. Each step depends on
the previous one's output, so this stops at the first failure rather than
pushing stale/missing data downstream.

compare_polls.py isn't included here -- it checks against hand-transcribed
text from MBA's own poll articles, which only update on their own weekly
schedule, not every time new game scores show up. Run it separately when
there's a new poll to check against.
"""
import subprocess
import sys

STEPS = [
    "scrape_games.py",
    "scrape_standings.py",
    "clean_games.py",
    "batch_fit.py",
    "elo_live.py",
    "build_site.py",
    "build_scores.py",
]

if __name__ == "__main__":
    for step in STEPS:
        print(f"\n{'=' * 70}\n{step}\n{'=' * 70}")
        result = subprocess.run([sys.executable, step])
        if result.returncode != 0:
            print(f"\nFAILED at {step} (exit code {result.returncode}) -- stopping.")
            sys.exit(1)
    print("\nPipeline complete: games_raw.json, teams_raw.json, games_clean.json, "
          "ratings_2026.json, ratings_2026_live_elo.json, index.html, and scores.html "
          "are all up to date.")
