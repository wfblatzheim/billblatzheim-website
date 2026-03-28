#!/usr/bin/env python3
"""
MLB Box Score Newspaper
Fetches daily MLB box scores and generates a newspaper-style HTML page.

Usage:
    python3 update.py                # fetch yesterday's games
    python3 update.py 2026-03-24     # fetch a specific date
    python3 update.py --rebuild      # regenerate HTML from cache only
"""

import json, sys, os, time, re
from datetime import datetime, timedelta

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)

CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mlb_cache.json")
BASE_URL = "https://statsapi.mlb.com/api/v1"
MAX_DAYS = 60

TEAM_SHORT = {
    "Arizona Diamondbacks":"D-backs","Atlanta Braves":"Braves","Baltimore Orioles":"Orioles",
    "Boston Red Sox":"Red Sox","Chicago Cubs":"Cubs","Chicago White Sox":"White Sox",
    "Cincinnati Reds":"Reds","Cleveland Guardians":"Guardians","Colorado Rockies":"Rockies",
    "Detroit Tigers":"Tigers","Houston Astros":"Astros","Kansas City Royals":"Royals",
    "Los Angeles Angels":"Angels","Los Angeles Dodgers":"Dodgers","Miami Marlins":"Marlins",
    "Milwaukee Brewers":"Brewers","Minnesota Twins":"Twins","New York Mets":"Mets",
    "New York Yankees":"Yankees","Oakland Athletics":"Athletics","Philadelphia Phillies":"Phillies",
    "Pittsburgh Pirates":"Pirates","San Diego Padres":"Padres","San Francisco Giants":"Giants",
    "Seattle Mariners":"Mariners","St. Louis Cardinals":"Cardinals","Tampa Bay Rays":"Rays",
    "Texas Rangers":"Rangers","Toronto Blue Jays":"Blue Jays","Washington Nationals":"Nationals",
    "Athletics":"Athletics",
}

def team_short(name):
    return TEAM_SHORT.get(name, name.split()[-1])

TEAM_ABBR = {
    "Arizona Diamondbacks":"ARI","Atlanta Braves":"ATL","Baltimore Orioles":"BAL",
    "Boston Red Sox":"BOS","Chicago Cubs":"CHC","Chicago White Sox":"CWS",
    "Cincinnati Reds":"CIN","Cleveland Guardians":"CLE","Colorado Rockies":"COL",
    "Detroit Tigers":"DET","Houston Astros":"HOU","Kansas City Royals":"KC",
    "Los Angeles Angels":"LAA","Los Angeles Dodgers":"LAD","Miami Marlins":"MIA",
    "Milwaukee Brewers":"MIL","Minnesota Twins":"MIN","New York Mets":"NYM",
    "New York Yankees":"NYY","Oakland Athletics":"OAK","Philadelphia Phillies":"PHI",
    "Pittsburgh Pirates":"PIT","San Diego Padres":"SD","San Francisco Giants":"SF",
    "Seattle Mariners":"SEA","St. Louis Cardinals":"STL","Tampa Bay Rays":"TB",
    "Texas Rangers":"TEX","Toronto Blue Jays":"TOR","Washington Nationals":"WSH",
    "Athletics":"ATH",
    # Short names returned by standings API
    "Yankees":"NYY","Red Sox":"BOS","Blue Jays":"TOR","Orioles":"BAL","Rays":"TB",
    "Guardians":"CLE","Royals":"KC","Tigers":"DET","Twins":"MIN","White Sox":"CWS",
    "Astros":"HOU","Angels":"LAA","Mariners":"SEA","Rangers":"TEX",
    "Braves":"ATL","Mets":"NYM","Phillies":"PHI","Marlins":"MIA","Nationals":"WSH",
    "Brewers":"MIL","Cardinals":"STL","Cubs":"CHC","Reds":"CIN","Pirates":"PIT",
    "Dodgers":"LAD","Giants":"SF","Padres":"SD","D-backs":"ARI","Rockies":"COL",
}

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Cache read error: {e}")
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, separators=(',', ':'))
    print(f"  Cache saved ({os.path.getsize(CACHE_FILE)//1024} KB)")

def api_get(path, params=None):
    url = f"{BASE_URL}/{path}"
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()

def get_abbr(name):
    return TEAM_ABBR.get(name, name[:3].upper())

NAME_SUFFIXES = {"II", "III", "IV", "Jr.", "Sr.", "Jr", "Sr"}

def last_name(full):
    parts = full.strip().split()
    while len(parts) > 1 and parts[-1] in NAME_SUFFIXES:
        parts.pop()
    return parts[-1] if parts else full

def fmt_ip(ip):
    """Convert API innings pitched (e.g. '6.2') to display format ('6⅔')."""
    s = str(ip)
    if '.' in s:
        w, f = s.split('.')
        return w + {'0':'','1':'⅓','2':'⅔'}.get(f, f'.{f}')
    return s

def _build_scoring(pbp):
    result = []
    for p in (pbp or {}).get("allPlays", []):
        half = "Top" if p["about"]["isTopInning"] else "Bot"
        inning = p["about"]["inning"]
        # Scoring sub-events within a play (wild pitches, passed balls, etc.)
        for ev in p.get("playEvents", []):
            d = ev.get("details", {})
            if d.get("isScoringPlay"):
                result.append({
                    "half": half, "inning": inning,
                    "away_score": d.get("awayScore"),
                    "home_score": d.get("homeScore"),
                    "desc": d.get("description", ""),
                })
        # Top-level scoring play (hit, sac fly, etc.)
        if p.get("about", {}).get("isScoringPlay"):
            result.append({
                "half": half, "inning": inning,
                "away_score": p["result"]["awayScore"],
                "home_score": p["result"]["homeScore"],
                "desc": p["result"]["description"],
            })
    return result


def build_game(box, line, pbp=None):
    away_box = box.get("teams", {}).get("away", {})
    home_box = box.get("teams", {}).get("home", {})

    away_name = away_box.get("team", {}).get("name", "")
    home_name = home_box.get("team", {}).get("name", "")
    away_abbr = get_abbr(away_name)
    home_abbr = get_abbr(home_name)
    away_short = team_short(away_name)
    home_short = team_short(home_name)

    # Linescore
    lt = line.get("teams", {})
    innings = [
        {"n": i["num"],
         "a": i.get("away", {}).get("runs"),
         "h": i.get("home", {}).get("runs")}
        for i in line.get("innings", [])
    ]
    away_r = lt.get("away", {}).get("runs", 0)
    away_h = lt.get("away", {}).get("hits", 0)
    away_e = lt.get("away", {}).get("errors", 0)
    home_r = lt.get("home", {}).get("runs", 0)
    home_h = lt.get("home", {}).get("hits", 0)
    home_e = lt.get("home", {}).get("errors", 0)

    # Decisions
    decisions = box.get("decisions", {})
    winner_id = str(decisions.get("winner", {}).get("id", ""))
    loser_id  = str(decisions.get("loser",  {}).get("id", ""))
    save_id   = str(decisions.get("save",   {}).get("id", ""))

    def build_batters(tbox):
        players = tbox.get("players", {})
        rows = []
        for pid in tbox.get("batters", []):
            p = players.get(f"ID{pid}", {})
            border = str(p.get("battingOrder", "0"))
            if not border or border == "0":
                continue  # pitcher with no batting slot (DH game)
            bs = p.get("stats", {}).get("batting", {})
            ab  = bs.get("atBats", 0)
            r   = bs.get("runs", 0)
            h   = bs.get("hits", 0)
            rbi = bs.get("rbi", 0)
            bb  = bs.get("baseOnBalls", 0)
            k   = bs.get("strikeOuts", 0)
            avg = p.get("seasonStats", {}).get("batting", {}).get("avg", "---")
            ops = p.get("seasonStats", {}).get("batting", {}).get("ops", "---")
            pos = p.get("position", {}).get("abbreviation", "").lower()
            is_sub = border[-1] != "0"
            name = last_name(p.get("person", {}).get("fullName", ""))
            rows.append({"name": name, "pos": pos, "sub": is_sub,
                         "ab": ab, "r": r, "h": h, "rbi": rbi, "bb": bb, "k": k, "avg": avg, "ops": ops})
        return rows

    def build_pitchers(tbox):
        players = tbox.get("players", {})
        rows = []
        for pid in tbox.get("pitchers", []):
            p = players.get(f"ID{pid}", {})
            ps = p.get("stats", {}).get("pitching", {})
            ip = fmt_ip(ps.get("inningsPitched", "0"))
            h  = ps.get("hits", 0)
            r  = ps.get("runs", 0)
            er = ps.get("earnedRuns", 0)
            bb = ps.get("baseOnBalls", 0)
            so = ps.get("strikeOuts", 0)
            ws = p.get("seasonStats", {}).get("pitching", {})
            pid_s = str(pid)
            note = ""
            if pid_s == winner_id:
                note = f"W,{ws.get('wins',0)}-{ws.get('losses',0)}"
            elif pid_s == loser_id:
                note = f"L,{ws.get('wins',0)}-{ws.get('losses',0)}"
            elif pid_s == save_id:
                note = f"S,{ws.get('saves',0)}"
            name = last_name(p.get("person", {}).get("fullName", ""))
            rows.append({"name": name, "note": note,
                         "ip": ip, "h": h, "r": r, "er": er, "bb": bb, "so": so})
        return rows

    def hit_notes(tbox, stat_key):
        players = tbox.get("players", {})
        out = []
        for pid in tbox.get("batters", []):
            p = players.get(f"ID{pid}", {})
            n = p.get("stats", {}).get("batting", {}).get(stat_key, 0)
            if n > 0:
                name = last_name(p.get("person", {}).get("fullName", ""))
                season = p.get("seasonStats", {}).get("batting", {}).get(stat_key, 0)
                out.append(f"{name} {n} ({season})" if n > 1 else f"{name} ({season})")
        return out

    def sb_notes(tbox):
        players = tbox.get("players", {})
        out = []
        for pid in tbox.get("batters", []):
            p = players.get(f"ID{pid}", {})
            n = p.get("stats", {}).get("batting", {}).get("stolenBases", 0)
            if n > 0:
                name = last_name(p.get("person", {}).get("fullName", ""))
                out.append(f"{name}" if n == 1 else f"{name} {n}")
        return out

    notes = []
    # E
    if away_e or home_e:
        parts = ([f"{away_abbr} {away_e}"] if away_e else []) + ([f"{home_abbr} {home_e}"] if home_e else [])
        notes.append("E\u2014" + ", ".join(parts))
    # DP
    adp = away_box.get("teamStats",{}).get("fielding",{}).get("doublePlays",0)
    hdp = home_box.get("teamStats",{}).get("fielding",{}).get("doublePlays",0)
    if adp or hdp:
        notes.append(f"DP\u2014{away_abbr} {adp}, {home_abbr} {hdp}")
    # LOB
    alob = away_box.get("teamStats",{}).get("batting",{}).get("leftOnBase",0)
    hlob = home_box.get("teamStats",{}).get("batting",{}).get("leftOnBase",0)
    notes.append(f"LOB\u2014{away_abbr} {alob}, {home_abbr} {hlob}")
    # XBH / HR / SB
    doubles = hit_notes(away_box,"doubles") + hit_notes(home_box,"doubles")
    if doubles: notes.append("2B\u2014" + ", ".join(doubles))
    triples = hit_notes(away_box,"triples") + hit_notes(home_box,"triples")
    if triples: notes.append("3B\u2014" + ", ".join(triples))
    hrs = hit_notes(away_box,"homeRuns") + hit_notes(home_box,"homeRuns")
    if hrs: notes.append("HR\u2014" + ", ".join(hrs))
    sbs = sb_notes(away_box) + sb_notes(home_box)
    if sbs: notes.append("SB\u2014" + ", ".join(sbs))

    info    = box.get("info", [])
    time_g  = next((i["value"] for i in info if i.get("label") == "T"), "")
    att     = next((i["value"] for i in info if i.get("label") == "A"), "")
    venue   = next((i["value"] for i in info if i.get("label") == "Venue"), "")

    return {
        "away_name": away_name, "home_name": home_name,
        "away_abbr": away_abbr, "home_abbr": home_abbr,
        "away_short": away_short, "home_short": home_short,
        "away_r": away_r, "away_h": away_h, "away_e": away_e,
        "home_r": home_r, "home_h": home_h, "home_e": home_e,
        "innings": innings,
        "away_batters": build_batters(away_box),
        "home_batters": build_batters(home_box),
        "away_pitchers": build_pitchers(away_box),
        "home_pitchers": build_pitchers(home_box),
        "notes": notes,
        "time": time_g, "att": att, "venue": venue,
        "scoring": _build_scoring(pbp),
    }

def fetch_full_schedule(year, start_date=None):
    """Fetch the complete regular-season schedule for a year. Returns dict keyed by date.
    start_date: optional 'YYYY-MM-DD' string to exclude earlier dates."""
    print(f"\nFetching {year} schedule{' from ' + start_date if start_date else ''}...")
    data = api_get("schedule", {"sportId": 1, "season": year, "gameType": "R"})
    result = {}
    for date_obj in data.get("dates", []):
        d = date_obj.get("date")
        if start_date and d < start_date:
            continue
        games = []
        for g in date_obj.get("games", []):
            games.append({
                "away_name": g["teams"]["away"]["team"]["name"],
                "away_abbr": get_abbr(g["teams"]["away"]["team"]["name"]),
                "home_name": g["teams"]["home"]["team"]["name"],
                "home_abbr": get_abbr(g["teams"]["home"]["team"]["name"]),
                "time": g.get("gameDate", ""),   # ISO UTC datetime
                "venue": g.get("venue", {}).get("name", ""),
            })
        if games:
            result[d] = games
    print(f"  {len(result)} dates loaded.")
    return result

def refresh_probables(cache):
    """Fetch probable pitchers for today + 7 days and update schedule cache entries."""
    today = datetime.now().strftime("%Y-%m-%d")
    end   = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    print(f"\nRefreshing probables {today} → {end}...", end=" ", flush=True)
    try:
        data = api_get("schedule", {
            "sportId": 1, "startDate": today, "endDate": end,
            "gameType": "R", "hydrate": "probablePitcher",
        })
        schedule = cache.setdefault("__schedule__", {})
        for date_obj in data.get("dates", []):
            d = date_obj.get("date")
            games = []
            for g in date_obj.get("games", []):
                away_name = g["teams"]["away"]["team"]["name"]
                home_name = g["teams"]["home"]["team"]["name"]
                ap = g["teams"]["away"].get("probablePitcher", {}).get("fullName", "")
                hp = g["teams"]["home"].get("probablePitcher", {}).get("fullName", "")
                games.append({
                    "away_name": away_name,
                    "away_abbr": get_abbr(away_name),
                    "home_name": home_name,
                    "home_abbr": get_abbr(home_name),
                    "time": g.get("gameDate", ""),
                    "venue": g.get("venue", {}).get("name", ""),
                    "away_probable": last_name(ap) if ap else "TBD",
                    "home_probable": last_name(hp) if hp else "TBD",
                })
            if games:
                schedule[d] = games
        print("ok")
    except Exception as e:
        print(f"ERROR: {e}")

DIVISIONS = {
    201: "AL East",
    202: "AL Central",
    200: "AL West",
    204: "NL East",
    205: "NL Central",
    203: "NL West",
}
DIV_ORDER = ["AL East", "AL Central", "AL West", "NL East", "NL Central", "NL West"]

def fetch_standings(date_str):
    print(f"  Fetching standings for {date_str}...", end=" ", flush=True)
    try:
        data = api_get("standings", {
            "leagueId": "103,104",
            "season": date_str[:4],
            "standingsType": "regularSeason",
            "date": date_str,
        })
        divisions = {}
        for record in data.get("records", []):
            div_id = record.get("division", {}).get("id")
            div = DIVISIONS.get(div_id)
            if not div:
                continue
            teams = []
            for tr in record.get("teamRecords", []):
                teams.append({
                    "name": tr["team"]["name"],
                    "abbr": get_abbr(tr["team"]["name"]),
                    "w": tr.get("wins", 0),
                    "l": tr.get("losses", 0),
                    "pct": tr.get("winningPercentage", ".000"),
                    "gb": tr.get("gamesBack", "-"),
                })
            divisions[div] = teams
        print("ok")
        return divisions
    except Exception as e:
        print(f"ERROR: {e}")
        return {}

def fetch_leaders(date_str):
    print(f"  Fetching leaders for {date_str}...", end=" ", flush=True)
    try:
        hit = api_get("stats/leaders", {
            "leaderCategories": "homeRuns,battingAverage,runsBattedIn,stolenBases,onBasePlusSlugging",
            "season": date_str[:4], "sportId": 1, "limit": 5,
            "statGroup": "hitting", "leaderGameTypes": "R", "hydrate": "person,team",
        })
        pit = api_get("stats/leaders", {
            "leaderCategories": "earnedRunAverage,strikeouts,saves",
            "season": date_str[:4], "sportId": 1, "limit": 5,
            "statGroup": "pitching", "leaderGameTypes": "R", "hydrate": "person,team",
        })
        result = {}
        for cat in hit.get("leagueLeaders", []) + pit.get("leagueLeaders", []):
            key = cat.get("leaderCategory")
            if key and key not in result:
                result[key] = [
                    {"name": last_name(r.get("person", {}).get("fullName", "")),
                     "team": r.get("team", {}).get("abbreviation", ""),
                     "val": r.get("value", ""),
                     "rank": r.get("rank", 0)}
                    for r in cat.get("leaders", [])[:5]
                ]
        print("ok")
        return result
    except Exception as e:
        print(f"ERROR: {e}")
        return {}

def fetch_day(date_str):
    print(f"\nFetching {date_str}...")
    sched = api_get("schedule", {"sportId": 1, "date": date_str, "gameType": "R"})
    dates = sched.get("dates", [])
    if not dates:
        print("  No games scheduled.")
        return {"games": [], "standings": {}}

    games = []
    for g in dates[0].get("games", []):
        state = g.get("status", {}).get("abstractGameState", "")
        away  = g["teams"]["away"]["team"]["name"]
        home  = g["teams"]["home"]["team"]["name"]
        if state != "Final":
            print(f"  Skip: {away} @ {home} ({state})")
            continue
        pk = g["gamePk"]
        print(f"  {away} @ {home} ...", end=" ", flush=True)
        try:
            box  = api_get(f"game/{pk}/boxscore")
            line = api_get(f"game/{pk}/linescore")
            pbp  = api_get(f"game/{pk}/playByPlay")
            games.append(build_game(box, line, pbp))
            print("ok")
            time.sleep(0.4)
        except Exception as e:
            print(f"ERROR: {e}")

    standings = fetch_standings(date_str)
    leaders = fetch_leaders(date_str)
    print(f"  {len(games)} games fetched.")
    return {"games": games, "standings": standings, "leaders": leaders}


# ── HTML GENERATION ───────────────────────────────────────────────────────────

def generate_html(cache, generated_at):
    import calendar as cal_mod

    # Separate completed game data from schedule data
    schedule_raw = cache.get("__schedule__", {})
    game_dates = sorted([k for k in cache if not k.startswith("__")], reverse=True)[:MAX_DAYS]
    default = game_dates[0] if game_dates else ""

    # Cache entries may be the old format (list) or new format (dict with games+standings)
    def get_games(entry):
        return entry["games"] if isinstance(entry, dict) else entry
    def get_standings(entry):
        return entry.get("standings", {}) if isinstance(entry, dict) else {}
    def get_leaders(entry):
        return entry.get("leaders", {}) if isinstance(entry, dict) else {}

    js_data = "const gamesData={};\nconst standingsData={};\nconst leadersData={};\n" + "\n".join(
        f"gamesData['{d}']={json.dumps(get_games(cache[d]), ensure_ascii=False, separators=(',',':'))};"
        f"standingsData['{d}']={json.dumps(get_standings(cache[d]), ensure_ascii=False, separators=(',',':'))};"
        f"leadersData['{d}']={json.dumps(get_leaders(cache[d]), ensure_ascii=False, separators=(',',':'))};"
        for d in game_dates
    )

    # Schedule data for future dates (only dates not already in game_dates)
    today = datetime.now().strftime("%Y-%m-%d")
    future_dates = sorted([d for d in schedule_raw if d >= today and d not in game_dates])
    js_schedule = "const scheduleData={};\n" + "\n".join(
        f"scheduleData['{d}']={json.dumps(schedule_raw[d], ensure_ascii=False, separators=(',',':'))};"
        for d in future_dates
    )

    # All dates for nav = completed + future schedule dates
    all_nav_dates = sorted(set(game_dates) | set(future_dates), reverse=True)

    # Group by YYYY-MM for the archive nav
    months = {}
    for d in all_nav_dates:
        ym = d[:7]
        months.setdefault(ym, []).append(d)

    month_btns = ""
    for ym in sorted(months.keys()):
        yr, mo = ym.split("-")
        label = f"{cal_mod.month_abbr[int(mo)].upper()} '{yr[2:]}"
        month_btns += f'<button class="mon-btn" data-ym="{ym}" onclick="selectMonth(\'{ym}\')">{label}</button>'

    # JS date lookup per month (for rendering the date sub-row)
    js_months = "const monthDates={};\n" + "\n".join(
        f"monthDates['{ym}']={json.dumps(sorted(ds))};"
        for ym, ds in sorted(months.items(), reverse=True)
    )
    default_month = default[:7] if default else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>MLB Box Scores</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Barlow+Condensed:wght@400;600;700&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#f5f1e8;color:#1a1a1a;font-family:'Barlow Condensed',Arial,sans-serif;font-size:14px;overflow-x:hidden}}
a{{color:inherit;text-decoration:none}}

/* ── Masthead ── */
.masthead{{border-top:4px solid #1a1a1a;border-bottom:2px solid #1a1a1a;padding:10px 20px;display:flex;justify-content:space-between;align-items:baseline;width:100%}}
.back-link{{display:inline-flex;align-items:center;gap:5px;font-family:'Barlow Condensed',sans-serif;font-size:12px;font-weight:700;letter-spacing:.15em;text-transform:uppercase;color:#aaa;text-decoration:none;transition:color .15s}}
.back-link:hover{{color:#1a1a1a}}
.back-link:hover svg{{transform:translateX(-2px)}}
.back-link svg{{transition:transform .15s}}
.masthead-title{{font-family:'Playfair Display',Georgia,serif;font-size:32px;font-weight:900;letter-spacing:.12em;text-transform:uppercase}}
.masthead-date{{font-size:14px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#555}}
.masthead-context{{font-size:11px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:#aaa;text-align:right}}

/* ── Archive nav ── */
.arc-months{{width:100%;padding:5px 20px;border-bottom:1px solid #bbb;display:flex;flex-wrap:wrap;gap:2px;align-items:center}}
.arc-dates{{width:100%;padding:4px 20px;border-bottom:2px solid #1a1a1a;display:flex;flex-wrap:wrap;gap:2px;min-height:28px}}
.mon-btn{{cursor:pointer;padding:2px 10px;border:1px solid transparent;background:none;font-family:'Barlow Condensed',sans-serif;font-size:13px;font-weight:700;letter-spacing:.06em;color:#666}}
.mon-btn:hover{{color:#1a1a1a;border-color:#aaa}}
.mon-btn.active{{background:#1a1a1a;color:#f5f1e8;border-color:#1a1a1a}}
.day-btn{{cursor:pointer;padding:2px 7px;border:1px solid transparent;background:none;font-family:'Barlow Condensed',sans-serif;font-size:12px;font-weight:600;letter-spacing:.03em;color:#666}}
.day-btn:hover{{color:#1a1a1a;border-color:#aaa}}
.day-btn.active{{background:#555;color:#f5f1e8;border-color:#555}}

/* ── Grid ── */
.grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));width:100%;border-left:1px solid #bbb;border-top:1px solid #bbb}}
@media(min-width:1400px){{.grid{{grid-template-columns:repeat(4,minmax(0,1fr))}}}}
@media(max-width:760px){{.grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
@media(max-width:480px){{.grid{{grid-template-columns:minmax(0,1fr)}}}}

/* ── Box score card ── */
.box{{border-right:1px solid #bbb;border-bottom:1px solid #bbb;padding:9px 11px;font-size:12px;overflow:hidden}}
.box-hdr{{font-family:'Playfair Display',Georgia,serif;font-size:14px;font-weight:700;border-bottom:2px solid #1a1a1a;padding-bottom:3px;margin-bottom:5px;line-height:1.2}}
.box-hdr .final{{font-family:'Barlow Condensed',sans-serif;font-size:11px;font-weight:700;letter-spacing:.08em;color:#888;margin-left:4px}}

/* ── Linescore ── */
.ls-text{{font-size:12px;line-height:1.8;margin-bottom:4px;white-space:nowrap;font-variant-numeric:tabular-nums;width:100%}}
.ls-line{{display:flex;align-items:baseline}}
.ls-team{{font-weight:700;width:90px;flex-shrink:0}}
.ls-inn{{flex:1;letter-spacing:.05em;text-align:right}}
.ls-inn-group{{display:inline-block;margin-right:.4em}}
.ls-cell{{display:inline-block;min-width:.65em;text-align:center}}
.ls-rhe-val{{display:inline-block;min-width:1.4em;text-align:right}}
.ls-rhe{{flex-shrink:0;padding-left:.5em;border-left:1px solid #bbb;font-weight:700;letter-spacing:.08em}}

/* ── Section toggle headers ── */
.section-hdr{{width:100%;padding:4px 12px;font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#aaa;border-bottom:1px solid #ddd;display:flex;justify-content:space-between;align-items:center;cursor:pointer;user-select:none;box-sizing:border-box}}
.section-hdr:hover{{color:#555}}
.section-hdr-arrow{{font-size:9px}}

/* ── Expand toggle ── */
.expand-btn{{font-family:'Barlow Condensed',sans-serif;font-size:11px;font-weight:700;letter-spacing:.08em;color:#888;cursor:pointer;padding:2px 0;user-select:none;border-top:1px solid #ddd;margin-top:2px}}
.expand-btn:hover{{color:#1a1a1a}}

/* ── Batting / Pitching tables ── */
.tbl-hdr{{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;margin:6px 0 2px;padding-bottom:1px;border-bottom:1px solid #1a1a1a}}
table.bt,table.pt{{border-collapse:collapse;width:100%;font-family:'Barlow Condensed',sans-serif;font-size:12px}}
table.bt th,table.pt th{{text-align:right;padding:0 3px 1px;font-size:10px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;border-bottom:1px solid #bbb}}
table.bt th:first-child,table.pt th:first-child{{text-align:left}}
table.bt td,table.pt td{{text-align:right;padding:0 3px;line-height:1.4}}
table.bt td:first-child,table.pt td:first-child{{text-align:left}}
table.bt .sub td:first-child{{padding-left:10px;color:#555}}
table.bt .totrow td{{border-top:1px solid #999;font-weight:700}}
/* Fixed widths on stat columns so they never shift */
table.bt th:nth-child(2),table.bt td:nth-child(2){{width:26px}}
table.bt th:nth-child(3),table.bt td:nth-child(3){{width:20px}}
table.bt th:nth-child(4),table.bt td:nth-child(4){{width:20px}}
table.bt th:nth-child(5),table.bt td:nth-child(5){{width:20px}}
table.bt th:nth-child(6),table.bt td:nth-child(6){{width:20px}}
table.bt th:nth-child(7),table.bt td:nth-child(7){{width:20px}}
table.bt th:nth-child(8),table.bt td:nth-child(8){{width:34px}}
table.bt th:nth-child(9),table.bt td:nth-child(9){{width:34px}}
table.pt th:nth-child(2),table.pt td:nth-child(2){{width:28px}}
table.pt th:nth-child(3),table.pt td:nth-child(3),table.pt th:nth-child(4),table.pt td:nth-child(4),
table.pt th:nth-child(5),table.pt td:nth-child(5),table.pt th:nth-child(6),table.pt td:nth-child(6),
table.pt th:nth-child(7),table.pt td:nth-child(7){{width:20px}}

/* ── Schedule (upcoming) cards ── */
.sched-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));width:100%;border-left:1px solid #bbb;border-top:1px solid #bbb}}
@media(max-width:1100px){{.sched-grid{{grid-template-columns:repeat(3,minmax(0,1fr))}}}}
@media(max-width:760px){{.sched-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
@media(max-width:480px){{.sched-grid{{grid-template-columns:minmax(0,1fr)}}}}
.sched-card{{border-right:1px solid #bbb;border-bottom:1px solid #bbb;padding:9px 11px}}
.sched-matchup{{font-family:'Playfair Display',Georgia,serif;font-size:14px;font-weight:700;border-bottom:1px solid #ccc;padding-bottom:3px;margin-bottom:5px}}
.sched-time{{font-size:12px;color:#555;margin-top:3px}}
.sched-venue{{font-size:11px;color:#aaa;margin-top:2px}}
.sched-probables{{font-size:11px;color:#555;margin-top:4px;font-family:'Barlow Condensed',sans-serif}}
.sched-probables span{{color:#aaa}}

/* ── Standings ── */
.standings-wrap{{width:100%;border-bottom:2px solid #1a1a1a}}
.standings-inner{{display:grid;grid-template-columns:repeat(6,minmax(0,145px));border-left:1px solid #bbb;justify-content:center}}
@media(max-width:800px){{.standings-inner{{grid-template-columns:repeat(3,minmax(0,145px))}}}}
@media(max-width:500px){{
  .standings-inner{{grid-template-columns:repeat(2,minmax(0,145px))}}
  .standings-inner .standings-div:nth-child(1){{order:1}}
  .standings-inner .standings-div:nth-child(2){{order:3}}
  .standings-inner .standings-div:nth-child(3){{order:5}}
  .standings-inner .standings-div:nth-child(4){{order:2}}
  .standings-inner .standings-div:nth-child(5){{order:4}}
  .standings-inner .standings-div:nth-child(6){{order:6}}
}}
.standings-div{{border-right:1px solid #bbb;border-bottom:1px solid #bbb;padding:5px 7px}}
.standings-div-name{{font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#888;margin-bottom:3px;border-bottom:1px solid #ddd;padding-bottom:2px}}
table.st{{border-collapse:collapse;width:100%;font-family:'Barlow Condensed',sans-serif;font-size:11px}}
table.st th{{font-size:10px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;text-align:right;padding:0 3px 1px;color:#aaa}}
table.st th:first-child{{text-align:left}}
table.st td{{text-align:right;padding:0 3px;line-height:1.45}}
table.st td:first-child{{text-align:left;font-weight:600}}
table.st th:nth-child(2),table.st td:nth-child(2),
table.st th:nth-child(3),table.st td:nth-child(3){{width:22px}}
table.st th:nth-child(4),table.st td:nth-child(4){{width:30px}}
table.st th:nth-child(5),table.st td:nth-child(5){{width:26px}}
table.st tr.div-leader td{{font-weight:800}}

/* ── Leaders strip ── */
.leaders-inner{{display:grid;grid-template-columns:repeat(8,minmax(0,1fr));border-left:1px solid #bbb;border-bottom:2px solid #1a1a1a}}
@media(max-width:800px){{.leaders-inner{{grid-template-columns:repeat(4,minmax(0,1fr))}}}}
@media(max-width:500px){{.leaders-inner{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
.leaders-cat{{border-right:1px solid #bbb;padding:5px 7px}}
.leaders-cat-name{{font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#888;margin-bottom:3px;border-bottom:1px solid #ddd;padding-bottom:2px}}
.leaders-row{{font-family:'Barlow Condensed',sans-serif;font-size:12px;display:flex;justify-content:space-between;align-items:baseline;padding:1px 0;line-height:1.4}}
.leaders-row-name{{font-weight:600}}
.leaders-row-team{{color:#aaa;font-weight:400;font-size:11px;margin-left:3px}}
.leaders-row-val{{color:#333;font-size:12px}}

/* ── Scoring plays ── */
.scoring-plays{{font-family:'Barlow Condensed',sans-serif;font-size:12px;padding:4px 0}}
.scoring-play{{padding:2px 0;border-bottom:1px solid #f0ece2;line-height:1.4}}
.scoring-play:last-child{{border-bottom:none}}
.sc-inn{{font-weight:700;font-size:11px;letter-spacing:.05em;color:#888;margin-right:4px}}
.sc-score{{font-weight:700;color:#1a1a1a;margin-right:4px}}

/* ── Bulk controls ── */
.bulk-controls{{width:100%;padding:3px 12px;display:flex;gap:12px;border-bottom:1px solid #ddd;box-sizing:border-box}}
.bulk-btn{{font-family:'Barlow Condensed',sans-serif;font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#aaa;cursor:pointer;user-select:none;background:none;border:none;padding:2px 0}}
.bulk-btn:hover{{color:#1a1a1a}}

/* ── Notes ── */
.notes{{font-size:11px;color:#333;margin-top:5px;line-height:1.5;font-family:'Barlow Condensed',sans-serif}}
.meta{{font-size:10px;color:#999;margin-top:3px;font-family:'Barlow Condensed',sans-serif}}

.no-games{{padding:60px 20px;text-align:center;font-family:'Playfair Display',serif;font-size:18px;color:#888;width:100%}}
.footer{{width:100%;padding:12px 20px;font-size:11px;color:#aaa;letter-spacing:.06em;border-top:1px solid #ccc}}
</style>
</head>
<body>

<div class="masthead">
  <div class="masthead-title">MLB Box Scores</div>
  <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px">
    <a class="back-link" href="https://billblatzheim.com"><svg width="12" height="10" viewBox="0 0 12 10" fill="none"><path d="M11 5H1M4 1L1 5l3 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>Blatz Labs</a>
    <div class="masthead-date" id="hdr-date"></div>
    <div class="masthead-context" id="hdr-context"></div>
  </div>
</div>
<div class="arc-months">{month_btns}</div>
<div class="arc-dates" id="arc-dates"></div>
<div class="standings-wrap" id="standings"></div>
<div id="leaders"></div>
<div id="content"></div>
<div class="footer">Generated {generated_at} &middot; Data: MLB Stats API</div>

<script>
{js_data}
{js_schedule}
{js_months}

const TODAY = '{today}';
let currentDate = '';
let currentMonth = '';

const MONTH_NAMES = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

const TEAM_SHORT_MAP = {{'Arizona Diamondbacks':'D-backs','Atlanta Braves':'Braves','Baltimore Orioles':'Orioles','Boston Red Sox':'Red Sox','Chicago Cubs':'Cubs','Chicago White Sox':'White Sox','Cincinnati Reds':'Reds','Cleveland Guardians':'Guardians','Colorado Rockies':'Rockies','Detroit Tigers':'Tigers','Houston Astros':'Astros','Kansas City Royals':'Royals','Los Angeles Angels':'Angels','Los Angeles Dodgers':'Dodgers','Miami Marlins':'Marlins','Milwaukee Brewers':'Brewers','Minnesota Twins':'Twins','New York Mets':'Mets','New York Yankees':'Yankees','Oakland Athletics':'Athletics','Philadelphia Phillies':'Phillies','Pittsburgh Pirates':'Pirates','San Diego Padres':'Padres','San Francisco Giants':'Giants','Seattle Mariners':'Mariners','St. Louis Cardinals':'Cardinals','Tampa Bay Rays':'Rays','Texas Rangers':'Rangers','Toronto Blue Jays':'Blue Jays','Washington Nationals':'Nationals','Athletics':'Athletics'}};
const TEAM_CITY_MAP = {{'Arizona Diamondbacks':'Arizona','Atlanta Braves':'Atlanta','Baltimore Orioles':'Baltimore','Boston Red Sox':'Boston','Chicago Cubs':'Chicago','Chicago White Sox':'Chicago','Cincinnati Reds':'Cincinnati','Cleveland Guardians':'Cleveland','Colorado Rockies':'Colorado','Detroit Tigers':'Detroit','Houston Astros':'Houston','Kansas City Royals':'Kansas City','Los Angeles Angels':'Los Angeles','Los Angeles Dodgers':'Los Angeles','Miami Marlins':'Miami','Milwaukee Brewers':'Milwaukee','Minnesota Twins':'Minnesota','New York Mets':'New York','New York Yankees':'New York','Oakland Athletics':'Oakland','Philadelphia Phillies':'Philadelphia','Pittsburgh Pirates':'Pittsburgh','San Diego Padres':'San Diego','San Francisco Giants':'San Francisco','Seattle Mariners':'Seattle','St. Louis Cardinals':'St. Louis','Tampa Bay Rays':'Tampa Bay','Texas Rangers':'Texas','Toronto Blue Jays':'Toronto','Washington Nationals':'Washington','Athletics':'Oakland'}};
function teamShort(g, side) {{ return g[side+'_short'] || TEAM_SHORT_MAP[g[side+'_name']] || g[side+'_abbr']; }}
function teamCity(g, side) {{ return g[side+'_city'] || TEAM_CITY_MAP[g[side+'_name']] || g[side+'_abbr']; }}

function fmtDateLabel(d) {{
  const dt = new Date(d + 'T12:00:00');
  return dt.toLocaleDateString('en-US', {{weekday:'long', month:'long', day:'numeric', year:'numeric'}});
}}

function fmtDayBtn(d) {{
  const [y,m,day] = d.split('-');
  return MONTH_NAMES[parseInt(m)] + ' ' + parseInt(day);
}}

function localGameTime(isoStr) {{
  if (!isoStr) return '';
  try {{
    const dt = new Date(isoStr);
    return dt.toLocaleTimeString(undefined, {{hour:'numeric', minute:'2-digit', timeZoneName:'short'}});
  }} catch(e) {{ return isoStr; }}
}}

function selectMonth(ym) {{
  currentMonth = ym;
  document.querySelectorAll('.mon-btn').forEach(b => b.classList.toggle('active', b.dataset.ym === ym));
  const dates = monthDates[ym] || [];
  document.getElementById('arc-dates').innerHTML = dates.map(d => {{
    const future = d > TODAY;
    return `<button class="day-btn${{d===currentDate?' active':''}}" data-date="${{d}}"
      style="${{future?'color:#aaa;font-style:italic;':''}}"
      onclick="renderDate('${{d}}')">${{fmtDayBtn(d)}}</button>`;
  }}).join('');
}}

const DIV_ORDER = ['AL East','AL Central','AL West','NL East','NL Central','NL West'];
let standingsOpen = true;
let leadersOpen = true;

function toggleStandings() {{
  standingsOpen = !standingsOpen;
  document.getElementById('standings-body').style.display = standingsOpen ? '' : 'none';
  document.getElementById('standings-arrow').textContent = standingsOpen ? '\u25be' : '\u25b8';
}}

function toggleLeaders() {{
  leadersOpen = !leadersOpen;
  document.getElementById('leaders-body').style.display = leadersOpen ? '' : 'none';
  document.getElementById('leaders-arrow').textContent = leadersOpen ? '\u25be' : '\u25b8';
}}

function renderStandings(dateStr) {{
  const divs = standingsData[dateStr];
  if (!divs || !Object.keys(divs).length) {{
    document.getElementById('standings').innerHTML = '';
    return;
  }}
  const cols = DIV_ORDER.map(divName => {{
    const teams = divs[divName] || [];
    const rows = teams.map((t, i) =>
      `<tr class="${{i===0?'div-leader':''}}">
        <td>${{t.abbr}}</td><td>${{t.w}}</td><td>${{t.l}}</td><td>${{t.pct}}</td><td>${{t.gb}}</td>
      </tr>`
    ).join('');
    return `<div class="standings-div">
      <div class="standings-div-name">${{divName}}</div>
      <table class="st">
        <thead><tr><th></th><th>W</th><th>L</th><th>PCT</th><th>GB</th></tr></thead>
        <tbody>${{rows}}</tbody>
      </table>
    </div>`;
  }}).join('');
  const label = fmtDateLabel(dateStr);
  document.getElementById('standings').innerHTML =
    `<div class="section-hdr" onclick="toggleStandings()">
       <span>Standings &mdash; through games of ${{label}}</span>
       <span class="section-hdr-arrow" id="standings-arrow">${{standingsOpen ? '\u25be' : '\u25b8'}}</span>
     </div>
     <div id="standings-body" style="display:${{standingsOpen ? '' : 'none'}}">
       <div class="standings-inner">${{cols}}</div>
     </div>`;
}}

function dateRelativeLabel(dateStr) {{
  const yesterday = new Date(TODAY + 'T12:00:00');
  yesterday.setDate(yesterday.getDate() - 1);
  const yStr = yesterday.toISOString().slice(0,10);
  const tomorrow = new Date(TODAY + 'T12:00:00');
  tomorrow.setDate(tomorrow.getDate() + 1);
  const tStr = tomorrow.toISOString().slice(0,10);
  if (dateStr === yStr) return "Yesterday's Results";
  if (dateStr === TODAY) return "Today";
  if (dateStr === tStr) return "Tomorrow's Schedule";
  return '';
}}

function renderDate(dateStr) {{
  currentDate = dateStr;
  document.querySelectorAll('.day-btn').forEach(b => b.classList.toggle('active', b.dataset.date === dateStr));
  document.getElementById('hdr-date').textContent = fmtDateLabel(dateStr);
  document.getElementById('hdr-context').textContent = dateRelativeLabel(dateStr);

  renderStandings(dateStr);
  renderLeaders(dateStr);

  const games = gamesData[dateStr];
  if (games && games.length > 0) {{
    currentGameCount = games.length;
    const hasScoring = games.some(g => g.scoring && g.scoring.length);
    const controls = `<div class="bulk-controls">
      <button class="bulk-btn" onclick="toggleAllBoxes()">toggle all box scores</button>
      ${{hasScoring ? '<button class="bulk-btn" onclick="toggleAllScoring()">toggle all scoring</button>' : ''}}
    </div>`;
    document.getElementById('content').innerHTML =
      controls + '<div class="grid">' + games.map((g,i) => renderGame(g,i)).join('') + '</div>';
    return;
  }}

  const sched = scheduleData[dateStr];
  if (sched && sched.length > 0) {{
    document.getElementById('content').innerHTML =
      '<div class="sched-grid">' + sched.map(renderSchedCard).join('') + '</div>';
    return;
  }}

  document.getElementById('content').innerHTML = '<div class="no-games">No data for this date.</div>';
}}

function renderSchedCard(g) {{
  const t = localGameTime(g.time);
  const probables = (g.away_probable || g.home_probable) ?
    `<div class="sched-probables"><span>${{g.away_abbr}}:</span> ${{g.away_probable||'TBD'}} &nbsp;<span>${{g.home_abbr}}:</span> ${{g.home_probable||'TBD'}}</div>` : '';
  return `<div class="sched-card">
    <div class="sched-matchup">${{g.away_name.toUpperCase()}} at ${{g.home_name.toUpperCase()}}</div>
    <div class="sched-time">${{t}}</div>
    <div class="sched-venue">${{g.venue}}</div>
    ${{probables}}
  </div>`;
}}

const LEADERS_ORDER = [
  {{key:'homeRuns',label:'HR'}},
  {{key:'battingAverage',label:'AVG'}},
  {{key:'onBasePlusSlugging',label:'OPS'}},
  {{key:'runsBattedIn',label:'RBI'}},
  {{key:'stolenBases',label:'SB'}},
  {{key:'earnedRunAverage',label:'ERA'}},
  {{key:'strikeouts',label:'K'}},
  {{key:'saves',label:'SV'}},
];

function renderLeaders(dateStr) {{
  const data = leadersData[dateStr];
  if (!data || !Object.keys(data).length) {{
    document.getElementById('leaders').innerHTML = '';
    return;
  }}
  const cols = LEADERS_ORDER.map(cat => {{
    const rows = (data[cat.key] || []).map(r =>
      `<div class="leaders-row"><span class="leaders-row-name">${{r.name}}<span class="leaders-row-team">${{r.team}}</span></span><span class="leaders-row-val">${{r.val}}</span></div>`
    ).join('');
    return `<div class="leaders-cat"><div class="leaders-cat-name">${{cat.label}}</div>${{rows}}</div>`;
  }}).join('');
  document.getElementById('leaders').innerHTML =
    `<div class="section-hdr" onclick="toggleLeaders()">
       <span>League Leaders</span>
       <span class="section-hdr-arrow" id="leaders-arrow">${{leadersOpen ? '\u25be' : '\u25b8'}}</span>
     </div>
     <div id="leaders-body" style="display:${{leadersOpen ? '' : 'none'}}">
       <div class="leaders-inner">${{cols}}</div>
     </div>`;
}}

let currentGameCount = 0;

function toggleAllBoxes() {{
  const anyOpen = Array.from({{length:currentGameCount}},(_,i)=>document.getElementById('bx-'+i))
    .some(el=>el&&el.style.display!=='none');
  for (let i=0;i<currentGameCount;i++) {{
    const el=document.getElementById('bx-'+i);
    const lbl=document.getElementById('bx-lbl-'+i);
    if (!el) continue;
    el.style.display = anyOpen?'none':'block';
    lbl.textContent = anyOpen?'\u25b8 FULL BOX':'\u25be CLOSE';
  }}
}}

function toggleAllScoring() {{
  const anyOpen = Array.from({{length:currentGameCount}},(_,i)=>document.getElementById('sc-'+i))
    .some(el=>el&&el.style.display!=='none');
  for (let i=0;i<currentGameCount;i++) {{
    const el=document.getElementById('sc-'+i);
    const lbl=document.getElementById('sc-lbl-'+i);
    if (!el) continue;
    el.style.display = anyOpen?'none':'block';
    lbl.textContent = anyOpen?'\u25b8 HOW THEY SCORED':'\u25be HOW THEY SCORED';
  }}
}}

function toggleBox(idx) {{
  const el = document.getElementById('bx-' + idx);
  const lbl = document.getElementById('bx-lbl-' + idx);
  const open = el.style.display !== 'none';
  el.style.display = open ? 'none' : 'block';
  lbl.textContent = open ? '\u25b8 FULL BOX' : '\u25be CLOSE';
}}

function toggleScoring(idx) {{
  const el = document.getElementById('sc-' + idx);
  const lbl = document.getElementById('sc-lbl-' + idx);
  const open = el.style.display !== 'none';
  el.style.display = open ? 'none' : 'block';
  lbl.textContent = open ? '\u25b8 HOW THEY SCORED' : '\u25be HOW THEY SCORED';
}}

function renderGame(g, idx) {{
  const extra = g.innings.length > 9 ? ` (${{g.innings.length}})` : '';
  const hdr = `<div class="box-hdr">
    ${{teamShort(g,'away')}} ${{g.away_r}}, ${{teamShort(g,'home')}} ${{g.home_r}}
    <span class="final">FINAL${{extra}}</span>
  </div>`;

  function fmtInnings(vals) {{
    const groups = [];
    for (let i = 0; i < vals.length; i += 3) {{
      const cells = vals.slice(i, i+3).map(v => `<span class="ls-cell">${{v}}</span>`).join('');
      groups.push(`<span class="ls-inn-group">${{cells}}</span>`);
    }}
    return groups.join('');
  }}
  function fmtRHE(r, h, e) {{
    return `<span class="ls-rhe-val">${{r}}</span><span class="ls-rhe-val">${{h}}</span><span class="ls-rhe-val">${{e}}</span>`;
  }}
  const awayVals = g.innings.map(i => i.a !== null && i.a !== undefined ? String(i.a) : '\u2013');
  const homeVals = g.innings.map((i, idx) => {{
    if (i.h === null || i.h === undefined) return idx === g.innings.length - 1 ? 'x' : '\u2013';
    return String(i.h);
  }});
  const ls = `<div class="ls-text">
    <div class="ls-line"><span class="ls-team">${{teamCity(g,'away')}}</span><span class="ls-inn">${{fmtInnings(awayVals)}}</span><span class="ls-rhe">${{fmtRHE(g.away_r,g.away_h,g.away_e)}}</span></div>
    <div class="ls-line"><span class="ls-team">${{teamCity(g,'home')}}</span><span class="ls-inn">${{fmtInnings(homeVals)}}</span><span class="ls-rhe">${{fmtRHE(g.home_r,g.home_h,g.home_e)}}</span></div>
  </div>`;

  function batTable(batters, abbr) {{
    const rows = batters.map(b => {{
      const namePos = b.sub ? `<td style="padding-left:10px;color:#555">${{b.name}} ${{b.pos}}</td>` : `<td>${{b.name}} ${{b.pos}}</td>`;
      return `<tr>${{namePos}}<td>${{b.ab}}</td><td>${{b.r}}</td><td>${{b.h}}</td><td>${{b.rbi}}</td><td>${{b.bb}}</td><td>${{b.k}}</td><td>${{b.avg}}</td><td>${{b.ops}}</td></tr>`;
    }}).join('');
    const totAB=batters.reduce((s,b)=>s+(b.ab||0),0), totR=batters.reduce((s,b)=>s+(b.r||0),0);
    const totH=batters.reduce((s,b)=>s+(b.h||0),0), totRBI=batters.reduce((s,b)=>s+(b.rbi||0),0);
    const totBB=batters.reduce((s,b)=>s+(b.bb||0),0), totK=batters.reduce((s,b)=>s+(b.k||0),0);
    return `<div class="tbl-hdr">${{abbr}} Batting</div>
    <table class="bt"><thead><tr><th></th><th>AB</th><th>R</th><th>H</th><th>BI</th><th>BB</th><th>K</th><th>AVG</th><th>OPS</th></tr></thead>
    <tbody>${{rows}}<tr class="totrow"><td>Totals</td><td>${{totAB}}</td><td>${{totR}}</td><td>${{totH}}</td><td>${{totRBI}}</td><td>${{totBB}}</td><td>${{totK}}</td><td></td><td></td></tr></tbody></table>`;
  }}

  function pitTable(pitchers, abbr) {{
    const rows = pitchers.map(p => {{
      const nc = p.note ? `${{p.name}} <em style="font-style:normal;font-size:9px;">${{p.note}}</em>` : p.name;
      return `<tr><td>${{nc}}</td><td>${{p.ip}}</td><td>${{p.h}}</td><td>${{p.r}}</td><td>${{p.er}}</td><td>${{p.bb}}</td><td>${{p.so}}</td></tr>`;
    }}).join('');
    return `<div class="tbl-hdr">${{abbr}} Pitching</div>
    <table class="pt"><thead><tr><th></th><th>IP</th><th>H</th><th>R</th><th>ER</th><th>BB</th><th>SO</th></tr></thead>
    <tbody>${{rows}}</tbody></table>`;
  }}

  const notesHtml = g.notes.length ? `<div class="notes">${{g.notes.join('. ')}}.</div>` : '';
  const metaParts = [g.time?`T\u2014${{g.time}}`:'', g.att?`A\u2014${{g.att}}`:'', g.venue].filter(Boolean);
  const metaHtml = metaParts.length ? `<div class="meta">${{metaParts.join(' \u00b7 ')}}</div>` : '';

  const scoringRows = (g.scoring||[]).map(p =>
    `<div class="scoring-play"><span class="sc-inn">${{p.half.toUpperCase()}} ${{p.inning}}</span><span class="sc-score">${{p.away_score}}-${{p.home_score}}</span>${{p.desc}}</div>`
  ).join('');
  const scoringHtml = scoringRows ? `
    <div class="expand-btn" onclick="toggleScoring(${{idx}})"><span id="sc-lbl-${{idx}}">\u25be HOW THEY SCORED</span></div>
    <div id="sc-${{idx}}"><div class="scoring-plays">${{scoringRows}}</div></div>` : '';

  return `<div class="box">
    ${{hdr}}${{ls}}${{scoringHtml}}
    <div class="expand-btn" onclick="toggleBox(${{idx}})"><span id="bx-lbl-${{idx}}">\u25b8 FULL BOX</span></div>
    <div id="bx-${{idx}}" style="display:none">
      ${{batTable(g.away_batters,g.away_abbr)}}${{batTable(g.home_batters,g.home_abbr)}}
      ${{pitTable(g.away_pitchers,g.away_abbr)}}${{pitTable(g.home_pitchers,g.home_abbr)}}
      ${{notesHtml}}${{metaHtml}}
    </div>
  </div>`;
}}

selectMonth('{default_month}');
renderDate('{default}');
</script>
</body>
</html>"""


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    cache = load_cache()
    dirty = False

    if "--clear" in args:
        cache = {}
        save_cache(cache)
        print("Cache cleared.")
        return

    if "--schedule" in args:
        idx = args.index("--schedule")
        yr = args[idx + 1] if idx + 1 < len(args) else str(datetime.now().year)
        # Optional second arg: start date, e.g. --schedule 2026 2026-03-25
        raw_start = args[idx + 2] if idx + 2 < len(args) else None
        start_date = raw_start if raw_start and re.match(r'\d{4}-\d{2}-\d{2}', raw_start) else None
        sched = fetch_full_schedule(yr, start_date)
        cache["__schedule__"] = sched
        dirty = True

    if "--clear-date" in args:
        idx = args.index("--clear-date")
        d = args[idx + 1] if idx + 1 < len(args) else None
        if not d or not re.match(r'\d{4}-\d{2}-\d{2}', d):
            print("Usage: python3 update.py --clear-date 2026-03-24")
            return
        if d in cache:
            del cache[d]
            save_cache(cache)
            print(f"Removed {d} from cache.")
        else:
            print(f"{d} not found in cache.")
        if not cache:
            return

    if "--clear-year" in args:
        idx = args.index("--clear-year")
        yr = args[idx + 1] if idx + 1 < len(args) else None
        if not yr or not yr.isdigit():
            print("Usage: python3 update.py --clear-year 2025")
            return
        before = len(cache)
        cache = {d: v for d, v in cache.items() if not d.startswith(yr)}
        save_cache(cache)
        print(f"Removed {before - len(cache)} dates for {yr}.")
        # Rebuild HTML with remaining data
        if not cache:
            return

    no_fetch = {"--rebuild", "--clear-year", "--clear-date", "--schedule"}
    if not any(f in args for f in no_fetch):
        if args and re.match(r'\d{4}-\d{2}-\d{2}', args[0]):
            date_str = args[0]
        else:
            date_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        result = fetch_day(date_str)
        if result.get("games"):
            cache[date_str] = result
            dirty = True
        elif date_str not in cache:
            print("No games fetched and nothing in cache for this date.")

        refresh_probables(cache)
        dirty = True

    if dirty:
        save_cache(cache)

    if not cache:
        print("No data. Run: python3 update.py 2026-03-24")
        return

    print("\nGenerating HTML...")
    html = generate_html(cache, datetime.now().strftime("%b %d, %Y"))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Done -> index.html ({len(html.encode())//1024} KB)")
    print("\nUsage:")
    print("  python3 update.py                   # yesterday")
    print("  python3 update.py 2026-03-24        # specific date")
    print("  python3 update.py --schedule 2026   # load full season schedule")
    print("  python3 update.py --clear-year 2025 # remove a year from cache")
    print("  python3 update.py --rebuild         # regenerate HTML from cache")

if __name__ == "__main__":
    main()
