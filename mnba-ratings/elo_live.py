"""
Live, sequential Elo rating for the 2026 season, seeded from a regressed
carryover of each team's 2025 batch-fit rating.

Carryover logic (no historical class data available -- see notes):
- We don't have team class/league snapshots for 2024/2025, only for the
  current (2026) season. So "class average" as a seed prior is built by
  taking each team's 2025 end-of-season batch-fit rating and grouping it
  by that team's CURRENT 2026 class -- i.e. "what did teams who are now
  classified as A/B/C actually rate at the end of last season." This
  needs no historical class labels, just the 2026 standings snapshot
  applied retroactively as a grouping key.
- A team with a 2025 rating gets RETAIN_FRACTION of it, blended toward
  its 2026-class's average 2025 rating for the rest (regression to the
  mean -- some roster turnover is real, but a team's identity isn't
  erased either).
- A team with no 2025 rating (new, or didn't match a name) is seeded
  directly at its 2026-class average.
- A team with no known 2026 class at all is seeded at the global mean.

Then games are replayed in chronological order with a standard Elo update,
K-factor scaled by margin of victory (capped the same way as the batch fit,
same rationale: no innings_played data to properly separate a truncated
10-run-rule game from a real blowout).
"""
import json

import numpy as np

from batch_fit import fit_season, MOV_CAP

K_BASE = 20
RETAIN_FRACTION = 0.70  # how much of a team's prior-season rating carries over


def mov_multiplier(margin):
    # 1.0 for a 1-run game, ~3.46 for a capped-or-bigger blowout
    return np.log1p(min(margin, MOV_CAP)) / np.log1p(1)


def build_2025_carryover_seeds(games, teams_meta):
    results_2025, _, _ = fit_season(games, teams_meta, 2025, use_mov=True)
    rating_2025 = {r["team"]: r["elo_like"] for r in results_2025}

    # group 2025 ratings by each team's CURRENT (2026) class
    by_class = {}
    for team, meta in teams_meta.items():
        if team in rating_2025:
            by_class.setdefault(meta["class"], []).append(rating_2025[team])
    class_avg = {cls: float(np.mean(vals)) for cls, vals in by_class.items()}
    global_avg = float(np.mean(list(rating_2025.values())))

    print("2026-class averages, based on those teams' 2025 end-of-season ratings:")
    for cls, avg in sorted(class_avg.items()):
        print(f"  Class {cls}: {avg:.1f}  (n={len(by_class[cls])})")
    print(f"  Global (unclassified fallback): {global_avg:.1f}")

    return rating_2025, class_avg, global_avg


def seed_team(team, teams_meta, rating_2025, class_avg, global_avg):
    meta = teams_meta.get(team)
    cls = meta["class"] if meta else None
    prior = rating_2025.get(team)
    target = class_avg.get(cls, global_avg)

    if prior is not None:
        return RETAIN_FRACTION * prior + (1 - RETAIN_FRACTION) * target
    return target


def run_live_elo(games, teams_meta):
    rating_2025, class_avg, global_avg = build_2025_carryover_seeds(games, teams_meta)

    season = sorted(
        (g for g in games if g["date"][:4] == "2026" and g["home_score"] != g["away_score"]),
        key=lambda g: (g["date"], g["game_id"]),
    )

    rating = {}
    games_played = {}
    blended_seed = {}

    def get_rating(team):
        if team not in rating:
            s = seed_team(team, teams_meta, rating_2025, class_avg, global_avg)
            rating[team] = s
            blended_seed[team] = s
            games_played[team] = 0
        return rating[team]

    for g in season:
        h, a = g["home_team"], g["away_team"]
        r_h, r_a = get_rating(h), get_rating(a)

        expected_h = 1 / (1 + 10 ** (-(r_h - r_a) / 400))
        actual_h = 1.0 if g["home_score"] > g["away_score"] else 0.0

        margin = abs(g["home_score"] - g["away_score"])
        k = K_BASE * mov_multiplier(margin)

        delta = k * (actual_h - expected_h)
        rating[h] = r_h + delta
        rating[a] = r_a - delta
        games_played[h] += 1
        games_played[a] += 1

    return rating, games_played, rating_2025, blended_seed


if __name__ == "__main__":
    games = json.load(open("games_clean.json"))
    teams = json.load(open("teams_raw.json"))
    teams_meta = {t["team_name"]: t for t in teams}

    live_rating, games_played, rating_2025, blended_seed = run_live_elo(games, teams_meta)

    live_results = []
    for team, r in live_rating.items():
        meta = teams_meta.get(team)
        live_results.append({
            "team": team,
            "known": meta is not None,
            "class": meta["class"] if meta else None,
            "elo_live": round(r, 1),
            "games_played": games_played[team],
            "raw_2025_rating": round(rating_2025[team], 1) if team in rating_2025 else None,
            "blended_seed": round(blended_seed[team], 1),
        })
    live_results.sort(key=lambda r: r["elo_live"], reverse=True)

    print(f"\nLive Elo, end of 2026 season ({len(live_results)} teams):\n")
    print("Top 20:")
    for r in live_results[:20]:
        cls = r["class"] or "?"
        print(f"  {r['elo_live']:7.1f}  [{cls}]  {r['team']:30s}  blended_seed={r['blended_seed']:7.1f}  ({r['games_played']}g)")

    print("\nBottom 10:")
    for r in live_results[-10:]:
        cls = r["class"] or "?"
        print(f"  {r['elo_live']:7.1f}  [{cls}]  {r['team']:30s}  blended_seed={r['blended_seed']:7.1f}  ({r['games_played']}g)")

    print("\nMorris Eagles (2nd in pure season batch fit) under the live Elo carryover model:")
    me = next(r for r in live_results if r["team"] == "Morris Eagles")
    print(f"  {me}")
    print(f"  rank in live Elo: {live_results.index(me) + 1} of {len(live_results)}")

    # compare to the season-long batch fit for 2026
    batch_results, _, _ = fit_season(games, teams_meta, 2026, use_mov=True)
    batch_rank = {r["team"]: i for i, r in enumerate(batch_results)}
    live_rank = {r["team"]: i for i, r in enumerate(live_results)}

    diffs = [(live_rank[t] - batch_rank[t], t) for t in live_rank if t in batch_rank]
    diffs.sort()
    print("\nBiggest disagreements (live Elo ranks much BETTER than season batch fit):")
    for d, t in diffs[:10]:
        print(f"  {d:+4d}  {t}")
    print("\nBiggest disagreements (live Elo ranks much WORSE than season batch fit):")
    for d, t in diffs[-10:]:
        print(f"  {d:+4d}  {t}")

    with open("ratings_2026_live_elo.json", "w") as f:
        json.dump(live_results, f, indent=2)
    print(f"\nSaved {len(live_results)} live Elo ratings to ratings_2026_live_elo.json")
