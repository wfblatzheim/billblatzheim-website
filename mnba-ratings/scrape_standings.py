"""
Pulls the current-season standings page from mnbaseball.org and extracts
team -> class/league mapping plus W-L-T records. Unlike the games feed,
this page is plain server-rendered HTML (no admin-ajax call), so we parse
it directly with BeautifulSoup.

Each team's URL slug (e.g. "waterville-indians") is used as a stable
team identifier since the page has no explicit numeric team ID.
"""
import json

import requests
from bs4 import BeautifulSoup

URL = "https://mnbaseball.org/standings/"
HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
    ),
}


def fetch_standings():
    resp = requests.get(URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    teams = []
    for container in soup.select(".league-container"):
        league_link = container.select_one(".card-header a")
        league_name = league_link.get_text(strip=True)
        league_url = league_link["href"]

        for row in container.select("tbody tr"):
            team_link = row.select_one("td a")
            badge = row.select_one(".badge")
            tds = row.select("td")
            teams.append({
                "team_slug": team_link["href"].rstrip("/").split("/")[-1],
                "team_name": team_link.get_text(strip=True),
                "team_url": team_link["href"],
                "class": badge.get_text(strip=True),
                "league": league_name,
                "league_url": league_url,
                "league_record": tds[1].get_text(strip=True),
                "overall_record": tds[2].get_text(strip=True),
            })
    return teams


if __name__ == "__main__":
    teams = fetch_standings()
    with open("teams_raw.json", "w") as f:
        json.dump(teams, f, indent=2)
    print(f"Saved {len(teams)} teams to teams_raw.json")
