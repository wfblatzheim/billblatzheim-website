"""
Turns games_raw.json + teams_raw.json into a cleaned games dataset.

Design decisions (see conversation/notes for rationale):
- We do NOT try to detect/drop out-of-state opponents. There's no reliable
  automated signal for it (team names carry no consistent state marker, and
  plenty of high-frequency "unknown" names are actually folded/renamed MN
  teams, not out-of-staters). Instead every game with two parseable, non-junk
  team names is kept, and each team is tagged as "known" (matches the 2026
  standings list, so we have class/league for it) or "unknown" (real team,
  but no current class/league on record).
- Ranking output will later be restricted to known 2026 teams; unknown teams
  still contribute their game results to the graph so known teams' records
  against them count.
- Only games_raw.json records with result == "Finished" are kept. The source
  API fills in a "0" run count for postponed/cancelled/not-yet-played games
  too, which would otherwise show up as phantom 0-0 ties.
"""
import json

JUNK_NAMES = {"", "tbd", "tba", "the yard 18u"}


def parse_date(date_str):
    # game_date is already "YYYY-MM-DD"; just sanity-check it.
    parts = date_str.split("-")
    if len(parts) != 3:
        return None
    year, month, day = parts
    if not (year.isdigit() and month.isdigit() and day.isdigit()):
        return None
    year, month, day = int(year), int(month), int(day)
    if year < 2024 or year > 2027 or not (1 <= month <= 12) or not (1 <= day <= 31):
        return None
    return date_str


def build_known_lookup(teams):
    lookup = {}
    for t in teams:
        lookup[t["team_name"].strip().lower()] = t
    return lookup


def clean(games, teams):
    known = build_known_lookup(teams)
    cleaned = []
    dropped = {"junk_team": 0, "bad_date": 0, "not_finished": 0, "bad_score": 0}

    for g in games:
        away_raw, home_raw = g["away_team"].strip(), g["home_team"].strip()

        if away_raw.lower() in JUNK_NAMES or home_raw.lower() in JUNK_NAMES:
            dropped["junk_team"] += 1
            continue

        date = parse_date(g["game_date"])
        if date is None:
            dropped["bad_date"] += 1
            continue

        try:
            away_score, home_score = int(g["away_team_r"]), int(g["home_team_r"])
        except (TypeError, ValueError):
            dropped["bad_score"] += 1
            continue

        # result == "Finished" is the normal signal a game was actually played.
        # But some historical (mostly 2024) records carry a real, non-0-0
        # scoreline without that status field being set -- keep those too.
        # A 0-0 line with no "Finished" status is ambiguous (not-yet-played
        # placeholder vs. genuine cancellation) and gets dropped either way.
        if g["result"] != "Finished" and (away_score, home_score) == (0, 0):
            dropped["not_finished"] += 1
            continue

        away_known = known.get(away_raw.lower())
        home_known = known.get(home_raw.lower())

        cleaned.append({
            "game_id": g["game_id"],
            "date": date,
            "game_type_raw": g["game_type"],
            "away_team": away_known["team_name"] if away_known else away_raw,
            "away_known": away_known is not None,
            "away_class": away_known["class"] if away_known else None,
            "away_league": away_known["league"] if away_known else None,
            "home_team": home_known["team_name"] if home_known else home_raw,
            "home_known": home_known is not None,
            "home_class": home_known["class"] if home_known else None,
            "home_league": home_known["league"] if home_known else None,
            "away_score": away_score,
            "home_score": home_score,
        })

    return cleaned, dropped


if __name__ == "__main__":
    games = json.load(open("games_raw.json"))
    teams = json.load(open("teams_raw.json"))

    cleaned, dropped = clean(games, teams)

    print(f"Input games: {len(games)}")
    print(f"Cleaned games: {len(cleaned)}")
    print(f"Dropped: {dropped}")

    both_known = sum(1 for g in cleaned if g["away_known"] and g["home_known"])
    one_unknown = sum(1 for g in cleaned if g["away_known"] != g["home_known"])
    both_unknown = sum(1 for g in cleaned if not g["away_known"] and not g["home_known"])
    print(f"\nBoth teams known (2026 standings): {both_known}")
    print(f"One team unknown: {one_unknown}")
    print(f"Both teams unknown: {both_unknown}")

    with open("games_clean.json", "w") as f:
        json.dump(cleaned, f, indent=2)
    print(f"\nSaved {len(cleaned)} cleaned games to games_clean.json")
