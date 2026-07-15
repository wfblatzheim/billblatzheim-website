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
"""
import json
import re

JUNK_NAMES = {"", "tbd", "tba", "the yard 18u"}

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_date(date_str):
    # e.g. "Jul 14th, 2026"
    m = re.match(r"(\w+)\s+(\d+)\w*,\s*(\d+)", date_str)
    if not m:
        return None
    mon, day, year = m.groups()
    mon_num = MONTHS.get(mon[:3].lower())
    year = int(year)
    day = int(day)
    if not mon_num or year < 2024 or year > 2027 or not (1 <= day <= 31):
        return None
    return f"{year:04d}-{mon_num:02d}-{day:02d}"


def parse_score(score_str):
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", score_str or "")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def build_known_lookup(teams):
    lookup = {}
    for t in teams:
        lookup[t["team_name"].strip().lower()] = t
    return lookup


def clean(games, teams):
    known = build_known_lookup(teams)
    cleaned = []
    dropped = {"bad_game_field": 0, "junk_team": 0, "bad_date": 0, "no_score": 0}

    for g in games:
        parts = g["game"].split(" @ ")
        if len(parts) != 2:
            dropped["bad_game_field"] += 1
            continue
        away_raw, home_raw = parts[0].strip(), parts[1].strip()

        if away_raw.lower() in JUNK_NAMES or home_raw.lower() in JUNK_NAMES:
            dropped["junk_team"] += 1
            continue

        date = parse_date(g["date"])
        if date is None:
            dropped["bad_date"] += 1
            continue

        score = parse_score(g["score"])
        if score is None:
            dropped["no_score"] += 1
            continue
        away_score, home_score = score

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
            "has_stats": g["stats"] == "Yes",
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
