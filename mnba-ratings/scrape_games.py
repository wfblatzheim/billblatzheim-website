"""
Pulls the full get_all_past_games dataset from mnbaseball.org's WordPress
admin-ajax endpoint and saves it raw to disk.

The endpoint has no date filter or "since" cursor -- it's a flat DataTables
listing, so there's no way to ask for only what's new. The full pull is
cheap though (a few seconds, no auth), so we just re-fetch everything each
time and diff it against whatever's already on disk, reporting what
actually changed (new games, games that got a score filled in, etc.)
rather than silently overwriting.
"""
import json
import os
import time

import requests

BASE = "https://mnbaseball.org/wp-admin/admin-ajax.php"
HEADERS = {
    "accept": "application/json, text/javascript, */*; q=0.01",
    "referer": "https://mnbaseball.org/games/",
    "x-requested-with": "XMLHttpRequest",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
    ),
}
PAGE_SIZE = 500


def fetch_page(start, length):
    params = {
        "draw": 1,
        "columns[0][data]": "game_id",
        "columns[1][data]": "date",
        "columns[2][data]": "time",
        "columns[3][data]": "game",
        "columns[4][data]": "game_type",
        "columns[5][data]": "score",
        "columns[6][data]": "scored",
        "columns[7][data]": "stats",
        "order[0][column]": 1,
        "order[0][dir]": "asc",
        "start": start,
        "length": length,
        "search[value]": "",
        "action": "get_all_past_games",
    }
    resp = requests.get(BASE, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_all():
    games = []
    start = 0
    total = None
    while total is None or start < total:
        payload = fetch_page(start, PAGE_SIZE)
        total = payload["recordsTotal"]
        batch = payload["data"]
        if not batch:
            break
        games.extend(batch)
        print(f"  fetched {len(games)}/{total}")
        start += PAGE_SIZE
        time.sleep(0.5)  # be polite to their server
    return games


def diff_and_report(old_games, new_games):
    old_by_id = {g["game_id"]: g for g in old_games}
    new_by_id = {g["game_id"]: g for g in new_games}

    added = [g for gid, g in new_by_id.items() if gid not in old_by_id]
    newly_scored = [
        g for gid, g in new_by_id.items()
        if gid in old_by_id and old_by_id[gid]["scored"] != "Yes" and g["scored"] == "Yes"
    ]
    changed_other = [
        g for gid, g in new_by_id.items()
        if gid in old_by_id and g != old_by_id[gid]
        and g not in newly_scored  # already reported above
        and old_by_id[gid]["scored"] == "Yes"  # exclude the newly_scored bucket
    ]

    print(f"\nNew games: {len(added)}")
    for g in added[:10]:
        print(f"  {g['game_id']}  {g['date']}  {g['game']}  {g['score']}")
    if len(added) > 10:
        print(f"  ... and {len(added) - 10} more")

    print(f"\nGames newly scored (previously pending): {len(newly_scored)}")
    for g in newly_scored[:10]:
        print(f"  {g['game_id']}  {g['date']}  {g['game']}  {g['score']}")
    if len(newly_scored) > 10:
        print(f"  ... and {len(newly_scored) - 10} more")

    if changed_other:
        print(f"\nOther changed records: {len(changed_other)}")
        for g in changed_other[:5]:
            print(f"  {g['game_id']}  {g['date']}  {g['game']}  old={old_by_id[g['game_id']]}  new={g}")


if __name__ == "__main__":
    out_path = "games_raw.json"
    old_games = json.load(open(out_path)) if os.path.exists(out_path) else []

    print("Fetching all games from mnbaseball.org...")
    all_games = fetch_all()

    if old_games:
        diff_and_report(old_games, all_games)
    else:
        print("\nNo existing games_raw.json found -- nothing to diff against.")

    with open(out_path, "w") as f:
        json.dump(all_games, f, indent=2)
    print(f"\nSaved {len(all_games)} games to {out_path}")
