"""
Compares our live-Elo ratings against MBA's own subjective Class A/B/C polls
(Nick Gerhardt, published on mnbaseball.org), pulled directly from the poll
articles as of their most recent editions (Class A: July 10, 2026; Class B/C:
July 8, 2026).

The human poll is closer in spirit to our live-Elo model (informed by prior
history + season-to-date) than the blank-slate season batch fit, so that's
what we compare against here.
"""
import json

# Poll rank -> team name(s). Ties share a rank. "Also receiving votes" teams
# are placed after the last ranked spot, unordered among themselves.
POLLS = {
    "A": {
        1: ["Miesville Mudhens"],
        2: ["St. Paul Mudhens"],
        3: ["Chaska Cubs"],
        4: ["St. Patrick Irish"],
        5: ["Macs Industrial Warriors"],
        6: ["Minnetonka Monarchs"],
        7: ["Burnsville Bobcats", "Air Freight Unlimited"],
        9: ["Moorhead Mudcats", "St. Anthony Hogs", "Baseball 365"],
        10: ["Waconia Lakers"],
        11: ["Forest Lake Brewers", "Champlin Park LoGators", "Moorhead Brewers",
             "Stockmens Irish", "Coon Rapids Redbirds", "North St. Paul Snowmen",
             "Dundas Dukes", "Twin Ports Timbers"],
    },
    "B": {
        1: ["Buckman Billygoats"],
        2: ["Raymond Rockets"],
        3: ["Cold Spring Springers"],
        4: ["Young America Cardinals"],
        5: ["Webster Sox"],
        6: ["Bluffton Braves"],
        7: ["Nisswa Lightning"],
        8: ["Buffalo Bulldogs", "Watertown Red Devils"],
        10: ["Loretto Larks", "Bird Island Bullfrogs"],
        11: ["Jordan Brewers", "St. Martin Martins", "Austin Greyhounds",
             "Union Hill Bulldogs", "Delano Athletics", "Stewartville-Racine Sharks",
             "Eagle Lake Expos", "Le Sueur Braves", "Sauk Rapids Cyclones", "Carver Black Sox"],
    },
    "C": {
        1: ["Windom Pirates", "Hanska Lakers"],
        3: ["Cannon Falls Bears"],
        4: ["Glencoe Brewers"],
        5: ["Courtland Cubs"],
        6: ["Howard Lake Orphans"],
        7: ["Elrosa Saints"],
        8: ["Granite Falls Kilowatts"],
        9: ["Perham Pirates", "Morris Eagles"],
        11: ["Litchfield Blues", "New York Mills Millers", "Cologne Hollanders",
             "Luxemburg Brewers", "New Prague Orioles", "Brownton Bruins",
             "Upsala Blue Jays", "Waterville Indians", "Hadley Buttermakers",
             "Pierz Brewers", "Cold Spring Rockies", "Urbank Bombers", "Quamba Cubs",
             "Dassel-Cokato Saints", "Madison Mallards", "Minnesota Lake Royals",
             "Milroy Yankees"],
    },
}

# name fixups between the poll articles' prose (shorthand/informal) and our
# scraped standings names
NAME_FIXUPS = {
    "Urbank Bombers": "Urbank-Parkers Prairie Bombers",
}

# Teams the poll itself lists under a class that doesn't match our scraped
# 2026 standings class -- e.g. Buffalo Bulldogs shows up in the Class B poll's
# "also receiving votes" but our standings scrape has them as Class A. Rather
# than silently misreport these as a rating disagreement, we skip them with
# an explicit note; this is a discrepancy in the source article, not our data.
CLASS_MISMATCHES = {
    ("B", "Buffalo Bulldogs"): "A",
    ("C", "New Prague Orioles"): "B",
}


def apply_fixups(poll):
    return {
        rank: [NAME_FIXUPS.get(t, t) for t in teams_]
        for rank, teams_ in poll.items()
    }


def poll_rank_lookup(poll):
    lookup = {}
    for rank, teams in poll.items():
        for t in teams:
            lookup[t] = rank
    return lookup


if __name__ == "__main__":
    live = json.load(open("ratings_2026_live_elo.json"))
    teams = json.load(open("teams_raw.json"))
    team_names = {t["team_name"] for t in teams}

    # sanity-check every poll name actually matches a scraped team name
    print("Checking poll team names against scraped standings names...")
    all_poll_names = {t for poll in POLLS.values() for teams_ in poll.values() for t in teams_}
    unmatched = sorted(n for n in all_poll_names if n not in team_names)
    if unmatched:
        print(f"  UNMATCHED ({len(unmatched)}): {unmatched}")
    else:
        print("  all matched cleanly")

    for cls in ["A", "B", "C"]:
        print(f"\n{'='*70}\nClass {cls}\n{'='*70}")
        class_teams = [r for r in live if r["class"] == cls]
        class_teams.sort(key=lambda r: r["elo_live"], reverse=True)
        our_rank = {r["team"]: i + 1 for i, r in enumerate(class_teams)}

        poll_rank = poll_rank_lookup(apply_fixups(POLLS[cls]))

        rows = []
        for team, p_rank in poll_rank.items():
            if (cls, team) in CLASS_MISMATCHES:
                print(f"  (skipping {team}: poll lists them in Class {cls}, "
                      f"but 2026 standings has them in Class {CLASS_MISMATCHES[(cls, team)]})")
                continue
            o_rank = our_rank.get(team)
            if o_rank is None:
                print(f"  (poll team not found in our {cls} ratings: {team})")
                continue
            rows.append((o_rank - p_rank, o_rank, p_rank, team))

        rows.sort()
        print(f"\n  {'diff':>5} {'our#':>5} {'poll#':>6}  team")
        for diff, o_rank, p_rank, team in rows:
            print(f"  {diff:+5d} {o_rank:5d} {p_rank:6d}  {team}")
