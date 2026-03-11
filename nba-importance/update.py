"""
NBA Game Importance Scorer
==========================
Pulls live NBA data, calculates SRS from scratch, scores remaining games
by playoff seeding importance, and outputs a ranked HTML report.

Requirements:
    pip install nba_api pandas numpy requests

Usage:
    python nba_importance.py
    Then open index.html in your browser.
"""

import numpy as np
import pandas as pd
import json
import time
from datetime import datetime, date
from collections import defaultdict

# ── nba_api imports ──────────────────────────────────────────────────────────
from nba_api.stats.endpoints import leaguegamefinder, leaguestandings, teamgamelogs
from nba_api.stats.static import teams as nba_teams_static

# ── Config ───────────────────────────────────────────────────────────────────
SEASON = "2025-26"
MOV_CAP = 20          # Cap margin of victory (reduces blowout inflation)
HOME_COURT_ADVANTAGE = 3.0  # Points added to home team SRS before win probability calc
SRS_ITERATIONS = 500  # Iterations for the solver
SLEEP = 0.7           # Seconds between API calls (be polite to the API)

# Every boundary between seeds carries weight — higher = more consequential.
# Think of these as the "value of crossing this line":
#   1: Full HCA through entire playoffs
#   2: HCA through conf finals
#   4: Last home-court seed (top 4 get HCA in R1)
#   6: Direct playoff vs play-in — biggest cliff in seeding
#   10: Play-in vs lottery — second biggest cliff
BOUNDARY_WEIGHTS = {
    1: 2.0,   # #1 overall seed — full home court advantage
    2: 1.3,   # HCA through conference finals
    4: 1.1,   # last home court seed in R1
    6: 2.8,   # direct playoff vs. play-in (biggest cliff)
    10: 2.2,  # play-in vs. lottery
}


# ── Step 1: Fetch all games played this season ───────────────────────────────
def fetch_game_results():
    print("📡 Fetching game results from NBA API...")
    finder = leaguegamefinder.LeagueGameFinder(
        season_nullable=SEASON,
        league_id_nullable="00",
        season_type_nullable="Regular Season"
    )
    time.sleep(SLEEP)
    df = finder.get_data_frames()[0]

    # Keep only completed games
    df = df[df["WL"].notna()].copy()

    # Filter to home team rows only (each game appears twice)
    home = df[df["MATCHUP"].str.contains("vs\\.")].copy()
    away = df[df["MATCHUP"].str.contains("@")].copy()

    # Build clean game-by-game record
    games = []
    for _, row in home.iterrows():
        game_id = row["GAME_ID"]
        away_row = away[away["GAME_ID"] == game_id]
        if away_row.empty:
            continue
        away_row = away_row.iloc[0]
        games.append({
            "game_id": game_id,
            "date": row["GAME_DATE"],
            "home_team_id": row["TEAM_ID"],
            "home_team": row["TEAM_ABBREVIATION"],
            "away_team_id": away_row["TEAM_ID"],
            "away_team": away_row["TEAM_ABBREVIATION"],
            "home_pts": row["PTS"],
            "away_pts": away_row["PTS"],
            "home_mov": row["PTS"] - away_row["PTS"],
        })

    df_games = pd.DataFrame(games)
    df_games["date"] = pd.to_datetime(df_games["date"])
    print(f"   ✅ {len(df_games)} completed games found.")
    return df_games


# ── Step 2: Calculate SRS ────────────────────────────────────────────────────
def calculate_srs(df_games):
    print("🧮 Calculating SRS...")
    team_ids = list(set(df_games["home_team_id"]) | set(df_games["away_team_id"]))
    team_idx = {tid: i for i, tid in enumerate(team_ids)}
    n = len(team_ids)

    # Point differential per game (capped)
    mov_sum = defaultdict(float)
    game_count = defaultdict(int)
    opponent_games = defaultdict(list)  # team_id -> list of opponent_ids

    for _, row in df_games.iterrows():
        h, a = row["home_team_id"], row["away_team_id"]
        mov = np.clip(row["home_mov"], -MOV_CAP, MOV_CAP)
        mov_sum[h] += mov
        mov_sum[a] -= mov
        game_count[h] += 1
        game_count[a] += 1
        opponent_games[h].append(a)
        opponent_games[a].append(h)

    avg_mov = {tid: mov_sum[tid] / game_count[tid] for tid in team_ids}

    # Iterative SRS solver
    srs = {tid: avg_mov[tid] for tid in team_ids}
    for _ in range(SRS_ITERATIONS):
        new_srs = {}
        for tid in team_ids:
            if not opponent_games[tid]:
                new_srs[tid] = 0.0
                continue
            opp_avg = np.mean([srs[o] for o in opponent_games[tid]])
            new_srs[tid] = avg_mov[tid] + opp_avg
        srs = new_srs

    # Attach abbreviations
    id_to_abbr = {}
    for _, row in df_games[["home_team_id", "home_team"]].drop_duplicates().iterrows():
        id_to_abbr[row["home_team_id"]] = row["home_team"]

    srs_df = pd.DataFrame([
        {"team_id": tid, "team": id_to_abbr.get(tid, str(tid)), "srs": round(srs[tid], 2)}
        for tid in team_ids
    ]).sort_values("srs", ascending=False).reset_index(drop=True)

    print("   ✅ SRS calculated.")
    return srs_df, srs


# ── Step 3: Fetch current standings ─────────────────────────────────────────
def fetch_standings():
    print("📡 Fetching current standings...")
    standings_ep = leaguestandings.LeagueStandings(season=SEASON, league_id="00")
    time.sleep(SLEEP)
    df = standings_ep.get_data_frames()[0]

    # Print columns once so we can debug if needed
    # print("   Standings columns:", list(df.columns))

    # Flexibly find the right column names (NBA API changes these occasionally)
    col_map = {}
    for col in df.columns:
        cl = col.lower()
        if cl == "teamid":                          col_map["team_id"] = col
        elif cl in ("teamabbreviation", "teamslug", "teamcity"): col_map.setdefault("team", col)
        elif cl == "conference":                    col_map["conference"] = col
        elif cl in ("playoffrank", "confrank", "clinchseed"): col_map.setdefault("seed", col)
        elif cl in ("wins", "w"):                   col_map.setdefault("wins", col)
        elif cl in ("losses", "l"):                 col_map.setdefault("losses", col)
        elif cl in ("winpct", "pct"):               col_map.setdefault("win_pct", col)
        elif cl in ("clinchindicator", "clinch"):   col_map.setdefault("clinch", col)

    # TeamAbbreviation might be stored as TeamSlug or similar — fall back to TeamCity
    if "team" not in col_map:
        for col in df.columns:
            if "team" in col.lower() and "id" not in col.lower():
                col_map["team"] = col
                break

    if "clinch" not in col_map:
        col_map["clinch"] = None  # not critical, just add empty column

    needed = ["team_id", "team", "conference", "seed", "wins", "losses", "win_pct"]
    missing = [k for k in needed if k not in col_map]
    if missing:
        print(f"   ⚠️  Could not find columns for: {missing}")
        print(f"   Available columns: {list(df.columns)}")
        raise KeyError(f"Missing columns: {missing}")

    rename = {v: k for k, v in col_map.items() if v is not None}
    df = df.rename(columns=rename)

    keep = ["team_id", "team", "conference", "seed", "wins", "losses", "win_pct"]
    if "clinch" in df.columns:
        keep.append("clinch")
    else:
        df["clinch"] = ""

    df = df[keep].copy()
    df["games_played"] = df["wins"] + df["losses"]
    df["games_remaining"] = 82 - df["games_played"]

    # Fix ambiguous city names using team IDs
    TEAM_ID_TO_ABBR = {
        1610612747: "LAL", 1610612746: "LAC",  # both "Los Angeles" / "LA"
        1610612745: "HOU", 1610612738: "BOS", 1610612751: "BKN",
        1610612766: "CHA", 1610612741: "CHI", 1610612739: "CLE",
        1610612742: "DAL", 1610612743: "DEN", 1610612765: "DET",
        1610612744: "GSW", 1610612748: "MIA", 1610612749: "MIL",
        1610612750: "MIN", 1610612740: "NOP", 1610612752: "NYK",
        1610612760: "OKC", 1610612753: "ORL", 1610612755: "PHI",
        1610612756: "PHX", 1610612757: "POR", 1610612758: "SAC",
        1610612759: "SAS", 1610612761: "TOR", 1610612762: "UTA",
        1610612764: "WAS", 1610612763: "MEM", 1610612737: "ATL",
        1610612754: "IND", 1610612767: "UTA",
    }
    df["team"] = df["team_id"].map(TEAM_ID_TO_ABBR).fillna(df["team"])

    print(f"   ✅ Standings fetched for {len(df)} teams.")
    return df


# ── Step 4: Fetch remaining schedule ────────────────────────────────────────
def fetch_remaining_schedule():
    print("📡 Fetching remaining schedule...")
    from nba_api.stats.endpoints import scheduleleaguev2
    time.sleep(SLEEP)

    today = pd.Timestamp(date.today())
    schedule = []

    try:
        sched_ep = scheduleleaguev2.ScheduleLeagueV2(
            league_id="00",
            season="2025-26"
        )
        time.sleep(SLEEP)
        df = sched_ep.get_data_frames()[0]

        # Use known camelCase column names from ScheduleLeagueV2
        # (uppercasing then hardcoding to avoid detection failures)
        df.columns = [c.upper() for c in df.columns]

        date_col    = "GAMEDATE"
        time_col    = "GAMEDATETIMEUTC"
        game_id_col = "GAMEID"
        home_col    = "HOMETEAM_TEAMID"
        away_col    = "AWAYTEAM_TEAMID"
        home_abbr   = "HOMETEAM_TEAMTRICODE"
        away_abbr   = "AWAYTEAM_TEAMTRICODE"

        # Verify they all exist
        missing = [c for c in [date_col, time_col, game_id_col, home_col, away_col, home_abbr, away_abbr] if c not in df.columns]
        if missing:
            raise ValueError(f"Missing expected columns: {missing}")

        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df[df[date_col].notna()]
        df = df[df[date_col] >= today]
        print(f"   Upcoming games: {len(df)}")

        for _, row in df.iterrows():
            home_name = str(row.get("HOMETEAM_TEAMNAME", "")).strip().lower()
            away_name = str(row.get("AWAYTEAM_TEAMNAME", "")).strip().lower()
            schedule.append({
                "game_id": row[game_id_col],
                "date": row[date_col],
                "game_time_utc": str(row[time_col]) if pd.notna(row[time_col]) else "",
                "home_team_id": row[home_col],
                "home_team": row[home_abbr],
                "home_team_full": home_name or row[home_abbr],
                "away_team_id": row[away_col],
                "away_team": row[away_abbr],
                "away_team_full": away_name or row[away_abbr],
            })


    except Exception as e:
        print(f"   ScheduleLeagueV2 failed: {e}")
        print("   Trying fallback: scraping schedule from LeagueGameFinder for all teams...")

    # Fallback: use scoreboard date-by-date via LeagueSchedule alternative
    if not schedule:
        try:
            from nba_api.stats.endpoints import leagueschedule
            sched2 = leagueschedule.LeagueSchedule(season_year=SEASON, league_id="00")
            time.sleep(SLEEP)
            df2 = sched2.get_data_frames()[0]
            print(f"   LeagueSchedule columns: {list(df2.columns)[:10]}")
            df2.columns = [c.upper() for c in df2.columns]
            date_col = next((c for c in df2.columns if "DATE" in c), None)
            if date_col:
                df2[date_col] = pd.to_datetime(df2[date_col], errors="coerce")
                df2 = df2[df2[date_col] >= today]
                home_col = next((c for c in df2.columns if "HOME" in c and "ID" in c), None)
                away_col = next((c for c in df2.columns if ("AWAY" in c or "VISIT" in c) and "ID" in c), None)
                home_abbr = next((c for c in df2.columns if "HOME" in c and ("ABBR" in c or "SLUG" in c or "ABBREVIATION" in c)), None)
                away_abbr = next((c for c in df2.columns if ("AWAY" in c or "VISIT" in c) and ("ABBR" in c or "SLUG" in c or "ABBREVIATION" in c)), None)
                game_id_col = next((c for c in df2.columns if "GAME" in c and "ID" in c), None)
                for _, row in df2.iterrows():
                    schedule.append({
                        "game_id": row[game_id_col] if game_id_col else "",
                        "date": row[date_col],
                        "home_team_id": row[home_col] if home_col else 0,
                        "home_team": row[home_abbr] if home_abbr else "",
                        "away_team_id": row[away_col] if away_col else 0,
                        "away_team": row[away_abbr] if away_abbr else "",
                    })
        except Exception as e2:
            print(f"   LeagueSchedule also failed: {e2}")

    if not schedule:
        print("   ❌ Could not retrieve remaining schedule from any endpoint.")
        print("   Paste the output above and we'll debug further.")
        return pd.DataFrame(columns=["game_id", "date", "home_team_id", "home_team", "away_team_id", "away_team"])

    df_sched = pd.DataFrame(schedule).drop_duplicates("game_id")
    df_sched = df_sched.sort_values("date").reset_index(drop=True)
    print(f"   ✅ {len(df_sched)} remaining games found.")
    return df_sched


# ── Step 5: Score each game ──────────────────────────────────────────────────
def score_games(schedule, standings, srs_dict):
    print("📊 Scoring games by importance...")

    stand_map = standings.set_index("team_id").to_dict("index")
    srs_series = pd.Series(srs_dict)

    scored = []
    for _, game in schedule.iterrows():
        h_id = game["home_team_id"]
        a_id = game["away_team_id"]

        if h_id not in stand_map or a_id not in stand_map:
            continue

        h = stand_map[h_id]
        a = stand_map[a_id]

        # Only score games within same conference (playoff seeding is per-conf)
        # Inter-conference games still matter but less directly — apply 0.6x
        same_conf = h["conference"] == a["conference"]
        conf_factor = 1.0 if same_conf else 0.6

        # --- Seed pressure: Gaussian decay from every meaningful boundary ---
        # Each boundary contributes pressure that falls off smoothly with distance.
        # sigma=1.5 means a team 3 seeds away still feels ~13% of the boundary weight,
        # so a team at 4 feels both the 4/5 home-court line AND the 6/7 play-in cliff.
        def seed_pressure(seed, games_remaining):
            if games_remaining == 0:
                return 0
            pressure = 0
            for boundary, weight in BOUNDARY_WEIGHTS.items():
                # Boundary sits *between* seeds `boundary` and `boundary+1`
                # Distance is how far this team is from that dividing line
                dist = abs(seed - boundary - 0.5)
                sigma = 1.5
                pressure += weight * np.exp(-0.5 * (dist / sigma) ** 2)
            return pressure

        h_pressure = seed_pressure(h["seed"], h["games_remaining"])
        a_pressure = seed_pressure(a["seed"], a["games_remaining"])
        combined_pressure = h_pressure + a_pressure

        # --- Head-to-head multiplier: chasing same seed? ---
        seed_gap = abs(h["seed"] - a["seed"])
        h2h_multiplier = 1.0
        if same_conf and seed_gap <= 3:
            h2h_multiplier = 1.0 + (1.0 - seed_gap / 4) * 1.0  # up to 2x

        # --- Upset potential (SRS-based win probability) ---
        h_srs = srs_dict.get(h_id, 0)
        a_srs = srs_dict.get(a_id, 0)
        srs_diff = h_srs - a_srs + HOME_COURT_ADVANTAGE  # home court ~3pt bump
        # Logistic: P(home wins). Scale factor ~7 is typical for NBA point spreads
        p_home_win = 1 / (1 + np.exp(-srs_diff / 7))
        # Upset potential is highest when game is near 50/50
        upset_weight = 1 - abs(p_home_win - 0.5) * 2  # 1.0 at 50/50, 0.0 at 100%

        # --- Scarcity: later games matter more ---
        avg_games_remaining = (h["games_remaining"] + a["games_remaining"]) / 2
        scarcity = np.clip(1 + (20 - avg_games_remaining) / 20, 1.0, 2.0)

        # --- Marquee quality: small boost for games between playoff-caliber teams ---
        # Based on seed position rather than SRS, so a tight MIN vs LAL game
        # gets the same respect as OKC vs DEN.
        # Both in top 6 (direct playoff): 1.15x
        # Both in top 10 (playoff + play-in): 1.07x
        # One or both outside top 10: 1.0x
        h_seed, a_seed = h["seed"], a["seed"]
        if h_seed <= 6 and a_seed <= 6:
            marquee_multiplier = 1.15
        elif h_seed <= 10 and a_seed <= 10:
            marquee_multiplier = 1.07
        else:
            marquee_multiplier = 1.0

        # --- Raw score ---
        raw = (
            combined_pressure
            * h2h_multiplier
            * (0.5 + 0.5 * upset_weight)   # blend: always some base, boost for toss-ups
            * scarcity
            * conf_factor
            * marquee_multiplier
        )

        # --- What's at stake label ---
        def stakes_label(seed, conf):
            if seed == 1:
                return f"#{seed} — full HCA"
            elif seed == 2:
                return f"#{seed} — HCA thru conf finals"
            elif seed <= 4:
                return f"#{seed} — R1 home court"
            elif seed <= 6:
                return f"#{seed} — direct playoff"
            elif seed <= 10:
                return f"#{seed} — play-in"
            else:
                return f"#{seed} — lottery"

        scored.append({
            "date": game["date"].strftime("%b %d"),
            "date_sort": int(game["date"].timestamp()),
            "game_time_utc": game.get("game_time_utc", ""),
            "home": game["home_team"],
            "home_full": game.get("home_team_full", game["home_team"]),
            "away": game["away_team"],
            "away_full": game.get("away_team_full", game["away_team"]),
            "home_seed": h["seed"],
            "away_seed": a["seed"],
            "home_conf": h["conference"],
            "away_conf": a["conference"],
            "home_srs": round(h_srs, 1),
            "away_srs": round(a_srs, 1),
            "p_home_win": round(p_home_win * 100, 1),
            "raw_score": raw,
            "home_record": f"{h['wins']}-{h['losses']}",
            "away_record": f"{a['wins']}-{a['losses']}",
            "home_stakes": stakes_label(h["seed"], h["conference"]),
            "away_stakes": stakes_label(a["seed"], a["conference"]),
            "same_conf": same_conf,
        })

    df_scored = pd.DataFrame(scored)
    if df_scored.empty:
        return df_scored

    # Normalize to 0-100
    max_score = df_scored["raw_score"].max()
    df_scored["importance"] = (df_scored["raw_score"] / max_score * 100).round(1)
    df_scored = df_scored.sort_values("importance", ascending=False).reset_index(drop=True)
    df_scored["rank"] = df_scored.index + 1
    print(f"   ✅ {len(df_scored)} games scored.")
    return df_scored


# ── Step 6: Build HTML report ────────────────────────────────────────────────
def build_html(scored_games, srs_df, standings):
    print("🎨 Building HTML report...")

    # Serialize all game data to JSON for JS filtering
    import json as _json

    all_games = []
    for _, g in scored_games.iterrows():
        all_games.append({
            "rank": int(g["rank"]),
            "importance": float(g["importance"]),
            "date": g["date"],
            "date_sort": int(g["date_sort"]) if isinstance(g["date_sort"], (int, float)) else 0,
            "home": g["home"],
            "home_full": g.get("home_full", g["home"]),
            "away": g["away"],
            "away_full": g.get("away_full", g["away"]),
            "home_record": g["home_record"],
            "away_record": g["away_record"],
            "home_seed": int(g["home_seed"]),
            "away_seed": int(g["away_seed"]),
            "home_conf": g["home_conf"],
            "away_conf": g["away_conf"],
            "home_srs": float(g["home_srs"]),
            "away_srs": float(g["away_srs"]),
            "p_home_win": float(g["p_home_win"]),
            "home_stakes": g["home_stakes"],
            "away_stakes": g["away_stakes"],
            "same_conf": bool(g["same_conf"]),
            "game_time_utc": g.get("game_time_utc", "") if "game_time_utc" in g else "",
        })

    games_json = _json.dumps(all_games)

    # SRS table rows
    srs_rows = ""
    for _, row in srs_df.iterrows():
        color = "#22c55e" if row["srs"] > 0 else "#ef4444"
        bar_w = min(abs(row["srs"]) / 12 * 100, 100)
        bar_color = "#22c55e" if row["srs"] > 0 else "#ef4444"
        srs_rows += f"""<tr>
          <td style="font-weight:700;font-size:13px;">{row['team']}</td>
          <td>
            <div style="display:flex;align-items:center;gap:6px;">
              <div style="background:{bar_color};height:8px;width:{bar_w:.1f}px;border-radius:4px;min-width:2px;"></div>
              <span style="color:{color};font-weight:700;font-size:13px;">{row['srs']:+.2f}</span>
            </div>
          </td>
        </tr>"""

    # Standings tables
    def conf_table(conf_name):
        conf = standings[standings["conference"] == conf_name].sort_values("seed")
        rows_html = ""
        DIVIDER_GOLD = '<tr><td colspan="4" style="padding:2px 0;"><div style="height:2px;background:#f0c030;opacity:0.6;"></div></td></tr>'
        DIVIDER_RED  = '<tr><td colspan="4" style="padding:2px 0;"><div style="height:2px;background:#cc1122;opacity:0.6;"></div></td></tr>'
        for _, r in conf.iterrows():
            seed = int(r["seed"])
            if seed == 7:
                rows_html += DIVIDER_GOLD
            if seed == 11:
                rows_html += DIVIDER_RED
            badge_color = "#2979ff" if seed <= 6 else ("#f0c030" if seed <= 10 else "#3d5a80")
            rows_html += f"""<tr>
              <td style="color:{badge_color};font-family:'Barlow Condensed',sans-serif;font-weight:900;text-align:center;width:24px;font-size:14px;">{seed}</td>
              <td style="font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:14px;text-transform:uppercase;letter-spacing:0.3px;">{r['team']}</td>
              <td style="text-align:center;font-family:'Barlow Condensed',sans-serif;font-size:13px;font-weight:600;color:#8eadd4;">{r['wins']}-{r['losses']}</td>
              <td style="text-align:center;font-family:'Barlow Condensed',sans-serif;font-size:12px;font-weight:600;color:#3d5a80;">{r['games_remaining']}g</td>
            </tr>"""
        return rows_html

    now = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    # Split team buttons by conference
    east_teams = sorted(set(
        g["home"] for g in all_games if g["home_conf"] == "East"
    ) | set(
        g["away"] for g in all_games if g["away_conf"] == "East"
    ))
    west_teams = sorted(set(
        g["home"] for g in all_games if g["home_conf"] == "West"
    ) | set(
        g["away"] for g in all_games if g["away_conf"] == "West"
    ))
    east_buttons = "".join('<button class="team-btn" onclick="filterTeam(\'' + t + '\')">' + t + '</button>' for t in east_teams)
    west_buttons = "".join('<button class="team-btn" onclick="filterTeam(\'' + t + '\')">' + t + '</button>' for t in west_teams)
    team_buttons = east_buttons  # unused placeholder
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NBA Game Importance Scorer</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:ital,wght@0,400;0,600;0,700;0,800;0,900;1,700;1,800&family=Barlow:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {{
    --nbc-blue: #1059c4;
    --nbc-blue-dark: #0a3d8f;
    --nbc-blue-bright: #2979ff;
    --nbc-gold: #f0c030;
    --nbc-red: #cc1122;
    --bg: #08101e;
    --bg-card: #0d1b30;
    --bg-card-alt: #111f35;
    --border: #1a3155;
    --text-primary: #ffffff;
    --text-secondary: #8eadd4;
    --text-muted: #3d5a80;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    background: var(--bg);
    color: var(--text-primary);
    font-family: 'Barlow', sans-serif;
    min-height: 100vh;
    background-image:
      repeating-linear-gradient(
        0deg,
        transparent,
        transparent 3px,
        rgba(16, 89, 196, 0.03) 3px,
        rgba(16, 89, 196, 0.03) 4px
      );
  }}

  /* ── Header ── */
  .header {{
    background: linear-gradient(135deg, var(--nbc-blue-dark) 0%, #0d2d6e 50%, #091d4a 100%);
    border-bottom: 3px solid var(--nbc-gold);
    padding: 0 16px;
    position: relative;
    overflow: hidden;
  }}
  .header::before {{
    content: '';
    position: absolute;
    left: 0; top: 0; right: 0; bottom: 0;
    background: repeating-linear-gradient(
      90deg,
      transparent,
      transparent 18px,
      rgba(255,255,255,0.03) 18px,
      rgba(255,255,255,0.03) 19px
    );
    pointer-events: none;
  }}
  .header-inner {{
    position: relative;
    padding: 14px 0 12px;
    display: flex;
    align-items: baseline;
    gap: 16px;
    flex-wrap: wrap;
  }}
  h1 {{
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 28px;
    font-weight: 900;
    font-style: italic;
    color: #fff;
    text-transform: uppercase;
    letter-spacing: 1px;
    line-height: 1;
  }}
  h1 span.nbc-accent {{
    color: var(--nbc-gold);
  }}
  .subtitle {{
    font-family: 'Barlow Condensed', sans-serif;
    color: rgba(255,255,255,0.5);
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    line-height: 1;
  }}
  @media (min-width: 768px) {{
    .header {{ padding: 0 28px; }}
    h1 {{ font-size: 36px; }}
  }}

  /* ── Layout ── */
  .layout {{ display: flex; flex-direction: column; gap: 14px; padding: 14px 16px 24px; }}
  @media (min-width: 768px) {{
    .layout {{ flex-direction: row; padding: 20px 28px 28px; align-items: flex-start; }}
    .main-col {{ flex: 1; min-width: 0; }}
    .side-col {{ width: 290px; flex-shrink: 0; }}
  }}
  .main-col {{ width: 100%; }}
  .side-col {{ display: flex; flex-direction: column; gap: 12px; }}

  /* ── Cards ── */
  .card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 2px;
    padding: 14px;
    position: relative;
  }}
  .card::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--nbc-blue) 0%, var(--nbc-blue-bright) 100%);
  }}
  @media (min-width: 768px) {{ .card {{ padding: 16px 18px; }} }}
  .card-title {{
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 11px;
    font-weight: 800;
    color: var(--nbc-gold);
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-bottom: 12px;
  }}

  /* ── Filters ── */
  .filters {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 2px;
    padding: 12px 14px;
    margin-bottom: 12px;
    position: relative;
  }}
  .filters::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--nbc-blue) 0%, var(--nbc-blue-bright) 100%);
  }}
  @media (min-width: 768px) {{ .filters {{ padding: 14px 18px; margin-bottom: 14px; }} }}

  .filter-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }}
  .filter-row:last-child {{ margin-bottom: 0; }}
  .filter-label {{
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 11px; font-weight: 700;
    color: var(--nbc-gold);
    text-transform: uppercase; letter-spacing: 1px;
    width: 46px; flex-shrink: 0;
  }}
  .conf-btn, .team-btn, .clear-btn {{
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 13px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.5px;
    padding: 4px 10px; border-radius: 1px;
    border: 1px solid var(--border);
    background: var(--bg);
    color: var(--text-secondary);
    cursor: pointer; transition: all 0.12s;
    white-space: nowrap; flex-shrink: 0;
    -webkit-tap-highlight-color: transparent;
  }}
  .conf-btn:hover, .team-btn:hover {{ border-color: var(--nbc-blue-bright); color: #fff; }}
  .conf-btn.active {{
    background: var(--nbc-blue);
    border-color: var(--nbc-blue-bright);
    color: #fff;
  }}
  .team-btn.active {{
    background: var(--nbc-blue);
    border-color: var(--nbc-blue-bright);
    color: #fff;
  }}
  .clear-btn {{ border-color: var(--nbc-red); color: var(--nbc-red); }}
  .clear-btn:hover {{ background: var(--nbc-red); color: #fff; }}

  .conf-row {{ display: flex; gap: 5px; overflow-x: auto; -webkit-overflow-scrolling: touch; padding-bottom: 2px; }}
  .conf-row::-webkit-scrollbar {{ display: none; }}
  .team-scroll {{ overflow-x: auto; -webkit-overflow-scrolling: touch; flex: 1; }}
  .team-scroll::-webkit-scrollbar {{ display: none; }}
  .team-scroll-inner {{ display: flex; gap: 4px; width: max-content; }}
  .result-count {{
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 13px; font-weight: 700;
    color: var(--text-muted);
    text-transform: uppercase; letter-spacing: 0.5px;
    white-space: nowrap; margin-left: 4px;
  }}

  /* ── Games table ── */
  .games-table {{ width: 100%; border-collapse: collapse; }}
  .games-table th {{
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 11px; font-weight: 700;
    color: var(--nbc-gold);
    text-transform: uppercase; letter-spacing: 1px;
    padding: 0 10px 10px; text-align: left; white-space: nowrap;
    border-bottom: 1px solid var(--border);
  }}
  .games-table td {{
    padding: 10px 10px;
    border-bottom: 1px solid rgba(26,49,85,0.6);
    vertical-align: middle;
  }}
  .games-table tr:last-child td {{ border-bottom: none; }}
  .games-table tbody tr:active td {{ background: #0f2040; }}
  @media (min-width: 768px) {{
    .games-table tbody tr:hover td {{ background: #0f2040; }}
    .games-table th {{ font-size: 12px; padding: 0 14px 10px; }}
    .games-table td {{ padding: 11px 14px; }}
  }}

  .col-rank, .col-srs, .col-prob, .col-stakes {{ display: none; }}
  @media (min-width: 768px) {{
    .col-rank, .col-srs, .col-prob, .col-stakes {{ display: table-cell; }}
  }}

  /* Score bar */
  .imp-bar-wrap {{ display: flex; align-items: center; gap: 8px; }}
  .imp-bar {{ height: 4px; border-radius: 0; min-width: 2px; max-width: 70px; flex-shrink: 0; }}
  .imp-val {{
    font-family: 'Barlow', sans-serif;
    font-weight: 700; font-size: 13px;
    width: 40px; text-align: right; flex-shrink: 0;
    letter-spacing: 0.3px;
  }}

  /* Date cell */
  .date-cell {{
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 13px; font-weight: 700;
    color: var(--text-secondary);
    text-transform: uppercase; white-space: nowrap;
  }}

  /* Matchup */
  .team-name {{
    font-family: 'Barlow', sans-serif;
    font-weight: 700; font-size: 14px;
    text-transform: none; letter-spacing: 0.3px;
  }}
  .team-record {{
    font-family: 'Barlow', sans-serif;
    color: var(--text-muted); font-size: 11px; margin-left: 3px;
  }}
  .vs-sep {{
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 700; font-size: 11px;
    color: var(--nbc-gold); margin: 0 5px;
    text-transform: uppercase;
  }}
  .inter-badge {{
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 10px; font-weight: 700;
    background: rgba(41,121,255,0.15);
    color: var(--nbc-blue-bright);
    border: 1px solid rgba(41,121,255,0.3);
    padding: 1px 5px; margin-left: 5px; vertical-align: middle;
    text-transform: uppercase; letter-spacing: 0.5px;
  }}

  /* Stakes / SRS / prob cells */
  .stakes-cell {{
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 12px; font-weight: 600;
    color: var(--text-secondary); line-height: 1.7;
    text-transform: uppercase; letter-spacing: 0.3px;
  }}
  .srs-cell {{
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 13px; font-weight: 700;
    text-align: center; color: var(--text-secondary); white-space: nowrap;
  }}
  .prob-cell {{
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 13px; font-weight: 700;
    text-align: center; color: var(--text-secondary); white-space: nowrap;
  }}

  /* Mobile expand */
  .detail-row {{ display: none; }}
  .detail-row td {{ padding: 0 10px 12px; border-bottom: 1px solid var(--border); }}
  .detail-row.open {{ display: table-row; }}
  .detail-inner {{
    background: var(--bg);
    border-left: 3px solid var(--nbc-blue);
    padding: 10px 12px;
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 13px; font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase; letter-spacing: 0.3px;
    line-height: 1.8;
  }}
  @media (min-width: 768px) {{
    .detail-row {{ display: none !important; }}
    .game-row {{ cursor: default; }}
  }}
  .game-row {{ cursor: pointer; }}

  /* ── Side tables ── */
  .side-table {{ width: 100%; border-collapse: collapse; }}
  .side-table td {{
    padding: 7px 8px;
    border-bottom: 1px solid rgba(26,49,85,0.6);
    vertical-align: middle; white-space: nowrap;
  }}
  .side-table tr:last-child td {{ border-bottom: none; }}
  .side-table tr:hover td {{ background: #0f2040; }}

  .side-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; min-width: 0; }}
  @media (min-width: 768px) {{ .side-grid {{ display: contents; }} }}

  /* ── Legend ── */
  .legend {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }}
  .legend-item {{
    display: flex; align-items: center; gap: 5px;
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 11px; font-weight: 700;
    color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px;
  }}
  .dot {{ width: 8px; height: 3px; border-radius: 0; flex-shrink: 0; }}

  /* ── Back link ── */
  .back-link {{
    display: inline-flex; align-items: center; gap: 6px;
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 12px; font-weight: 700; letter-spacing: .18em;
    text-transform: uppercase; color: #888;
    text-decoration: none;
    transition: color .15s;
    margin-bottom: 8px;
  }}
  .back-link:hover {{ color: #e8002d; }}
  .back-link svg {{ transition: transform .15s; }}
  .back-link:hover svg {{ transform: translateX(-2px); }}

  #no-results {{
    display:none; padding: 32px; text-align: center;
    color: var(--text-muted);
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 16px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px;
  }}
  .sortable {{ cursor: pointer; user-select: none; white-space: nowrap; -webkit-tap-highlight-color: transparent; }}
  .sortable:hover {{ color: #fff; }}
  .active-sort {{ color: #fff !important; }}
  .sort-arrow {{ font-size: 10px; margin-left: 2px; opacity: 0.8; }}
</style>
</head>
<body>

<div class="header">
  <div class="header-inner">
    <a class="back-link" href="https://billblatzheim.com">
      <svg width="12" height="10" viewBox="0 0 12 10" fill="none"><path d="M11 5H1M4 1L1 5l3 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
      Blatz Labs
    </a>
    <h1>NBA <span class="nbc-accent">Game</span> Importance</h1>
    <p class="subtitle">{SEASON} &nbsp;·&nbsp; {now} &nbsp;·&nbsp; SRS from live data</p>
  </div>
</div>

<div class="layout">

  <!-- Main column -->
  <div class="main-col">

    <!-- Filters -->
    <div class="filters">
      <div class="filter-row">
        <span class="filter-label">Conf</span>
        <div class="conf-row">
          <button class="conf-btn active" onclick="filterConf('all')">All</button>
          <button class="conf-btn" onclick="filterConf('East')">East</button>
          <button class="conf-btn" onclick="filterConf('West')">West</button>
          <button class="conf-btn" onclick="filterConf('inter')">Inter-conf</button>
        </div>
        <span class="result-count" id="result-count"></span>
      </div>
      <div class="filter-row" style="align-items:flex-start;">
        <span class="filter-label" style="padding-top:4px;">Team</span>
        <div style="flex:1;min-width:0;">
          <div class="team-scroll" style="margin-bottom:5px;">
            <div class="team-scroll-inner">{east_buttons}</div>
          </div>
          <div class="team-scroll">
            <div class="team-scroll-inner">{west_buttons}</div>
          </div>
        </div>
        <button class="clear-btn" onclick="clearFilters()">✕</button>
      </div>
    </div>


    <!-- Legend -->
    <div class="legend">
      <div class="legend-item"><div class="dot" style="background:#cc1122;"></div>High (75+)</div>
      <div class="legend-item"><div class="dot" style="background:#f0c030;"></div>Med-high (50+)</div>
      <div class="legend-item"><div class="dot" style="background:#2979ff;"></div>Medium (25+)</div>
      <div class="legend-item"><div class="dot" style="background:#3d5a80;"></div>Lower</div>
    </div>

    <!-- Games table -->
    <div class="card" style="padding: 14px 0;">
      <table class="games-table" id="games-table">
        <thead>
          <tr>
            <th class="col-rank" style="padding-left:10px;">#</th>
            <th class="sortable active-sort" onclick="sortBy('importance')" data-col="importance">Score <span class="sort-arrow">↓</span></th>
            <th class="sortable" onclick="sortBy('date_sort')" data-col="date_sort">Date <span class="sort-arrow"></span></th>
            <th class="sortable" onclick="sortBy('home')" data-col="home">Matchup <span class="sort-arrow"></span></th>
            <th class="stakes-header col-stakes">At Stake</th>
            <th class="col-srs sortable" onclick="sortBy('srs_gap')" data-col="srs_gap" style="text-align:center;">SRS Gap <span class="sort-arrow"></span></th>
            <th class="col-prob sortable" onclick="sortBy('closeness')" data-col="closeness" style="text-align:center;">Win% <span class="sort-arrow"></span></th>
          </tr>
        </thead>
        <tbody id="games-tbody">
        </tbody>
      </table>
      <div id="no-results">No games match your filter.</div>
    </div>

    <p style="color:#1e293b;font-size:10px;margin-top:10px;text-align:center;">
      Score = seed pressure × head-to-head × upset potential × scarcity × conf factor. Tap a row on mobile for details.
    </p>
  </div>

  <!-- Side column -->
  <div class="side-col">
    <div class="side-grid">

      <div class="card">
        <div class="card-title">East</div>
        <div style="font-size:10px;color:#475569;margin-bottom:6px;">
          <span style="color:#f0c030;">━</span> playoff &nbsp;<span style="color:#cc1122;">━</span> play-in
        </div>
        <table class="side-table">
          {conf_table("East")}
        </table>
      </div>

      <div class="card">
        <div class="card-title">West</div>
        <div style="font-size:10px;color:#475569;margin-bottom:6px;">
          <span style="color:#f0c030;">━</span> playoff &nbsp;<span style="color:#cc1122;">━</span> play-in
        </div>
        <table class="side-table">
          {conf_table("West")}
        </table>
      </div>

    </div>

    <div class="card">
      <div class="card-title">SRS Ratings</div>
      <p style="font-size:10px;color:#475569;margin-bottom:10px;">Adj. pt diff vs strength of schedule. Cap: {MOV_CAP}pts.</p>
      <table class="side-table">
        {srs_rows}
      </table>
    </div>

  </div>
</div>

<script>
const ALL_GAMES = {games_json};

function impColor(s) {{
  if (s >= 75) return '#cc1122';    /* NBC red — top tier */
  if (s >= 50) return '#f0c030';    /* NBC gold — high */
  if (s >= 25) return '#2979ff';    /* NBC blue — medium */
  return '#3d5a80';                 /* muted blue — lower */
}}

function formatGameTime(utcStr) {{
  if (!utcStr || utcStr === 'nan' || utcStr === 'None') return '';
  try {{
    // Ensure proper ISO format
    const str = utcStr.endsWith('Z') ? utcStr : utcStr.replace(' ', 'T') + 'Z';
    const dt = new Date(str);
    if (isNaN(dt.getTime())) return '';
    return dt.toLocaleTimeString([], {{ hour: 'numeric', minute: '2-digit', timeZoneName: 'short' }});
  }} catch(e) {{ return ''; }}
}}

function renderGames(games) {{
  const tbody = document.getElementById('games-tbody');
  tbody.innerHTML = '';
  games.forEach((g, i) => {{
    const color = impColor(g.importance);
    const barW = Math.max(g.importance, 1);
    const interBadge = g.same_conf ? '' : '<span class="inter-badge">Inter-conf</span>';
    const hSrs = (g.home_srs >= 0 ? '+' : '') + g.home_srs.toFixed(1);
    const aSrs = (g.away_srs >= 0 ? '+' : '') + g.away_srs.toFixed(1);
    const rowId = `detail-${{i}}`;

    // Main row
    const tr = document.createElement('tr');
    tr.className = 'game-row';
    tr.onclick = () => {{
      const d = document.getElementById(rowId);
      if (d) d.classList.toggle('open');
    }};
    tr.innerHTML = `
      <td class="rank-cell col-rank">${{g.rank}}</td>
      <td>
        <div class="imp-bar-wrap">
          <div class="imp-bar" style="background:${{color}};width:${{barW}}px;"></div>
          <span class="imp-val" style="color:${{color}}">${{g.importance.toFixed(1)}}</span>
        </div>
      </td>
      <td class="date-cell">
        ${{g.date}}
        ${{g.game_time_utc ? '<br><span style="font-size:10px;color:#475569;">' + formatGameTime(g.game_time_utc) + '</span>' : ''}}
      </td>
      <td class="matchup-cell">
        <span class="team-name">${{g.away_full || g.away}}</span><span class="team-record">${{g.away_record}}</span>
        <span class="vs-sep">@</span>
        <span class="team-name">${{g.home_full || g.home}}</span><span class="team-record">${{g.home_record}}</span>
        ${{interBadge}}
      </td>
      <td class="stakes-cell col-stakes">${{g.away}}: ${{g.away_stakes}}<br>${{g.home}}: ${{g.home_stakes}}</td>
      <td class="srs-cell col-srs">
        ${{aSrs}} / ${{hSrs}}
        <br><span style="font-size:10px;color:#475569;">
          ${{(function() {{
            const edge = (g.home_srs + 3.0) - g.away_srs;
            const leader = edge > 0 ? g.home : g.away;
            return leader + ' +' + Math.abs(edge).toFixed(1) + ' adj';
          }})()}}
        </span>
      </td>
      <td class="prob-cell col-prob">
        ${{g.p_home_win >= 50
          ? g.home + " " + g.p_home_win.toFixed(1) + "%"
          : g.away + " " + (100 - g.p_home_win).toFixed(1) + "%"
        }}
      </td>
    `;
    tbody.appendChild(tr);

    // Expandable detail row (mobile tap)
    const dr = document.createElement('tr');
    dr.className = 'detail-row';
    dr.id = rowId;
    dr.innerHTML = `
      <td colspan="7">
        <div class="detail-inner">
          <div>${{g.away}}: ${{g.away_stakes}}</div>
          <div>${{g.home}}: ${{g.home_stakes}}</div>
          <div style="margin-top:6px;color:#64748b;">SRS: ${{g.away}} ${{aSrs}} / ${{g.home}} ${{hSrs}} · adj edge: ${{(function(){{const e=(g.home_srs+3.0)-g.away_srs;return (e>0?g.home:g.away)+' +'+ Math.abs(e).toFixed(1);}})()}}</div>
          <div style="color:#64748b;">Win prob: ${{g.p_home_win >= 50
            ? g.home + " " + g.p_home_win.toFixed(1) + "%"
            : g.away + " " + (100 - g.p_home_win).toFixed(1) + "%"
          }}</div>
        </div>
      </td>
    `;
    tbody.appendChild(dr);
  }});
  document.getElementById('result-count').textContent = games.length + ' games';
  document.getElementById('no-results').style.display = games.length === 0 ? 'block' : 'none';
}}

// Add srs_gap as a derived field for sorting
ALL_GAMES.forEach(g => {{
  g.srs_gap = Math.abs((g.home_srs + 3.0) - g.away_srs);
  g.closeness = Math.abs(g.p_home_win - 50); // 0 = perfectly even, 50 = total blowout
}});

let activeConf = 'all';
let activeTeam = null;
let sortCol = 'importance';
let sortDir = 1; // 1 = descending (high first), -1 = ascending (low first)

function getFilteredGames() {{
  let games = ALL_GAMES;
  if (activeConf === 'East') games = games.filter(g => g.home_conf === 'East' && g.away_conf === 'East');
  else if (activeConf === 'West') games = games.filter(g => g.home_conf === 'West' && g.away_conf === 'West');
  else if (activeConf === 'inter') games = games.filter(g => !g.same_conf);
  if (activeTeam) games = games.filter(g => g.home === activeTeam || g.away === activeTeam);
  return games;
}}

function getSortedGames(games) {{
  return [...games].sort((a, b) => {{
    let av = a[sortCol], bv = b[sortCol];
    // sortDir: 1 = descending (high first), -1 = ascending (low first)
    if (typeof av === 'string') return sortDir * bv.localeCompare(av);
    return sortDir * (bv - av);
  }});
}}

function applyFilters() {{
  renderGames(getSortedGames(getFilteredGames()));
}}

function sortBy(col) {{
  if (sortCol === col) {{
    sortDir *= -1; // same column: flip direction
  }} else {{
    sortCol = col;
    if (['date_sort', 'srs_gap', 'closeness'].includes(col)) sortDir = 1; // ascending = closest/earliest first
    else sortDir = -1; // descending = highest first
  }}
  // Update header styles
  document.querySelectorAll('.sortable').forEach(th => {{
    th.classList.remove('active-sort');
    th.querySelector('.sort-arrow').textContent = '';
  }});
  const activeCol = document.querySelector(`[data-col="${{col}}"]`);
  if (activeCol) {{
    activeCol.classList.add('active-sort');
    activeCol.querySelector('.sort-arrow').textContent = sortDir === 1 ? '↓' : '↑';
  }}
  applyFilters();
}}

function filterConf(conf) {{
  activeConf = conf;
  document.querySelectorAll('.conf-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  applyFilters();
}}

function filterTeam(team) {{
  if (activeTeam === team) {{
    activeTeam = null;
    document.querySelectorAll('.team-btn').forEach(b => b.classList.remove('active'));
  }} else {{
    activeTeam = team;
    document.querySelectorAll('.team-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
  }}
  applyFilters();
}}

function clearFilters() {{
  activeConf = 'all';
  activeTeam = null;
  document.querySelectorAll('.conf-btn').forEach(b => b.classList.remove('active'));
  document.querySelector('.conf-btn').classList.add('active');
  document.querySelectorAll('.team-btn').forEach(b => b.classList.remove('active'));
  applyFilters();
}}

// Initial render — importance descending by default
sortCol = 'importance';
sortDir = 1;
applyFilters();
</script>
</body>
</html>"""

    output_path = "index.html"
    with open(output_path, "w") as f:
        f.write(html)
    print(f"   ✅ Report saved to: {output_path}")
    return output_path


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("\n🏀 NBA Game Importance Scorer")
    print("=" * 40)

    games = fetch_game_results()
    srs_df, srs_dict = calculate_srs(games)
    standings = fetch_standings()
    schedule = fetch_remaining_schedule()
    scored = score_games(schedule, standings, srs_dict)

    output = build_html(scored, srs_df, standings)

    print("\n" + "=" * 40)
    print("✅ Done! Open this file in your browser:")
    print(f"   {output}")
    print("\nTop 5 most important upcoming games:")
    for _, row in scored.head(5).iterrows():
        print(f"  {row['rank']}. {row['home']} vs {row['away']} ({row['date']}) — {row['importance']:.1f}/100")


if __name__ == "__main__":
    main()
