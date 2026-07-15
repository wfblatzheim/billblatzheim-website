"""
One-off exploration script: pulls the full get_all_past_games dataset from
mnbaseball.org's WordPress admin-ajax endpoint and saves it raw to disk so we
can inspect data quality (date ranges, game_type variety, score format)
before building the real ETL pipeline.
"""
import json
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


if __name__ == "__main__":
    print("Fetching all games from mnbaseball.org...")
    all_games = fetch_all()
    out_path = "games_raw.json"
    with open(out_path, "w") as f:
        json.dump(all_games, f, indent=2)
    print(f"Saved {len(all_games)} games to {out_path}")
