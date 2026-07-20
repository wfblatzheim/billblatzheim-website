"""
Pulls every game from mnbaseball.org's "retrieve_mba_schedule" AJAX action
(the same one that powers the per-team pages and the /games/?view=scores
date view) and saves it raw to disk, one request per season.

This replaced an older scraper that hit a different action,
"get_all_past_games" -- a legacy DataTables listing that turned out to be
missing games still present on the site's own team/date pages (e.g. games
entered directly through the newer schedule tool never made it into that
table). "retrieve_mba_schedule" is the source those pages actually read
from, so it's both more complete and more current.

No date filter/cursor on this endpoint either, so -- same as before -- we
just re-fetch everything each time and diff it against whatever's already
on disk, reporting what changed rather than silently overwriting.
"""
import json
import os
import re
import time
from datetime import date

import requests

BASE_URL = "https://mnbaseball.org"
SCHEDULE_PAGE = f"{BASE_URL}/games/"
AJAX_URL = f"{BASE_URL}/wp-admin/admin-ajax.php"
HEADERS = {
    "accept": "application/json, text/javascript, */*; q=0.01",
    "referer": SCHEDULE_PAGE,
    "x-requested-with": "XMLHttpRequest",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
    ),
}

# Actual seasons on the site are 2024-2026 as of writing; probing a wider
# window costs nothing (a handful of extra cheap requests) and means this
# doesn't need to be bumped by hand every year.
SEASON_PROBE_START = 2023
SEASON_PROBE_END_SLACK = 1  # probe up to (this year + slack)


def fetch_nonce():
    resp = requests.get(SCHEDULE_PAGE, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    m = re.search(r"mbaScheduleGlobal\s*=\s*(\{.*?\})\s*;", resp.text)
    if not m:
        raise RuntimeError("Couldn't find mbaScheduleGlobal on the schedule page -- site markup may have changed.")
    config = json.loads(m.group(1))
    return config["nonce"], config.get("ajaxUrl", AJAX_URL)


def fetch_season(season, nonce, ajax_url):
    resp = requests.post(
        ajax_url,
        headers=HEADERS,
        data={
            "action": "retrieve_mba_schedule",
            "nonce": nonce,
            "scope": "all",
            "entity": "",
            "season": str(season),
        },
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    if not payload.get("success"):
        message = payload.get("data", {}).get("message", "unknown error")
        raise RuntimeError(f"retrieve_mba_schedule failed for season {season}: {message}")
    return payload["data"]["games"]


def fetch_all():
    nonce, ajax_url = fetch_nonce()

    games_by_id = {}
    last_year = date.today().year + SEASON_PROBE_END_SLACK
    for season in range(SEASON_PROBE_START, last_year + 1):
        batch = fetch_season(season, nonce, ajax_url)
        print(f"  season {season}: {len(batch)} games")
        for g in batch:
            g["game_id"] = int(g["game_id"])
            games_by_id[g["game_id"]] = g
        time.sleep(0.3)  # be polite to their server

    return list(games_by_id.values())


def diff_and_report(old_games, new_games):
    old_by_id = {g["game_id"]: g for g in old_games}
    new_by_id = {g["game_id"]: g for g in new_games}

    added = [g for gid, g in new_by_id.items() if gid not in old_by_id]
    newly_finished = [
        g for gid, g in new_by_id.items()
        if gid in old_by_id and old_by_id[gid]["result"] != "Finished" and g["result"] == "Finished"
    ]
    changed_other = [
        g for gid, g in new_by_id.items()
        if gid in old_by_id and g != old_by_id[gid]
        and g not in newly_finished
        and old_by_id[gid]["result"] == "Finished"
    ]

    def describe(g):
        score = f"{g['away_team_r']}-{g['home_team_r']}" if g["result"] == "Finished" else g["result"]
        return f"  {g['game_id']}  {g['game_date']}  {g['away_team']} @ {g['home_team']}  {score}"

    print(f"\nNew games: {len(added)}")
    for g in added[:10]:
        print(describe(g))
    if len(added) > 10:
        print(f"  ... and {len(added) - 10} more")

    print(f"\nGames newly finished (previously pending): {len(newly_finished)}")
    for g in newly_finished[:10]:
        print(describe(g))
    if len(newly_finished) > 10:
        print(f"  ... and {len(newly_finished) - 10} more")

    if changed_other:
        print(f"\nOther changed records: {len(changed_other)}")
        for g in changed_other[:5]:
            print(f"  {g['game_id']}  {g['game_date']}  {g['away_team']} @ {g['home_team']}")


if __name__ == "__main__":
    out_path = "games_raw.json"
    old_games = json.load(open(out_path)) if os.path.exists(out_path) else []

    print("Fetching all games from mnbaseball.org (retrieve_mba_schedule)...")
    all_games = fetch_all()

    if old_games and "result" not in old_games[0]:
        print("\nExisting games_raw.json is in the old (get_all_past_games) format -- skipping diff.")
    elif old_games:
        diff_and_report(old_games, all_games)
    else:
        print("\nNo existing games_raw.json found -- nothing to diff against.")

    with open(out_path, "w") as f:
        json.dump(all_games, f, indent=2)
    print(f"\nSaved {len(all_games)} games to {out_path}")
