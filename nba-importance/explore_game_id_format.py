#!/usr/bin/env python3
"""
Deeper investigation of GAME_ID format, SERIES_ID structure,
and how to detect play-in games from schedule data.
"""

import time
import pandas as pd

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)

def section(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

# ─────────────────────────────────────────────────────────────────────────────
# A. Decode SERIES_ID structure from 2024-25 data
# ─────────────────────────────────────────────────────────────────────────────
section("A. SERIES_ID Decoding — 2024-25 Playoffs")
try:
    from nba_api.stats.endpoints import CommonPlayoffSeries
    cps = CommonPlayoffSeries(season="2024-25", timeout=60)
    time.sleep(1)
    df = cps.playoff_series.get_data_frame()

    # SERIES_ID example: "004240010"
    # Format: 004 | 24 | 0 | 1 | 0
    #         type  yr  ?  rd  series#
    print("\n  All unique SERIES_IDs from 2024-25:")
    for sid in sorted(df["SERIES_ID"].unique()):
        games = df[df["SERIES_ID"] == sid]
        n_games = len(games)
        home = games["HOME_TEAM_ID"].iloc[0]
        visitor = games["VISITOR_TEAM_ID"].iloc[0]
        print(f"  {sid}  -> {n_games} games played (home={home}, visitor={visitor})")
        print(f"    GAME_IDs: {sorted(games['GAME_ID'].tolist())}")

    print("""
  SERIES_ID format breakdown (e.g., "004240040"):
    Chars 0-2: "004" = season type (004 = NBA Playoffs)
    Chars 3-4: "24"  = season year (2024-25 season)
    Char  5:   "0"   = league subdivision (0 = NBA)
    Char  6:   "0"   = round number (0=first round, 1=conf semis, 2=conf finals, 3=finals? or...)
    Char  7:   "4"   = series number within round
    Char  8:   "0"   = (often 0)

  Actually let's parse it properly:
    """)

    # Let's decode more carefully
    print("  Detailed SERIES_ID breakdown:")
    for sid in sorted(df["SERIES_ID"].unique()):
        games_in_series = len(df[df["SERIES_ID"] == sid])
        game_ids = sorted(df[df["SERIES_ID"] == sid]["GAME_ID"].tolist())
        # From game IDs like 0042400101:
        # 004 = playoff type
        # 24 = 2024-25 season
        # 00 = ??
        # 1 = round
        # 01 = matchup number
        # last game id digit = game number
        sample_gid = game_ids[0]
        print(f"  SERIES_ID={sid}  games={games_in_series}")
        print(f"    sample GAME_ID={sample_gid}")
        # GAME_ID: 0042400101
        # pos 0: 0 (leading zero)
        # pos 1-3: 042 = 04 + 2
        # Actually: 004 | 24 | 00 | 1 | 01
        # type=004, season=24, league=00, round=1, matchup=01
        gid = sample_gid
        print(f"    GAME_ID breakdown: type={gid[0:3]}, season={gid[3:5]}, league={gid[5:7]}, round={gid[7]}, matchup_num={gid[8:10]}")
        print(f"    SERIES_ID: {sid[0:3]}/{sid[3:5]}/{sid[5]}/{sid[6]}/{sid[7:]}")
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback; traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# B. ScheduleLeagueV2 — detect play-in games using gameLabel/gameId prefix
# ─────────────────────────────────────────────────────────────────────────────
section("B. ScheduleLeagueV2 — Play-In detection for 2025-26 (current)")
try:
    from nba_api.stats.endpoints import ScheduleLeagueV2
    sched = ScheduleLeagueV2(season="2025-26", timeout=120)
    time.sleep(1)
    games_df = sched.season_games.get_data_frame()

    # Play-in games have gameId starting with "005"
    playin = games_df[games_df["gameId"].astype(str).str.startswith("005")]
    playoffs = games_df[games_df["gameId"].astype(str).str.startswith("004")]
    regular = games_df[games_df["gameId"].astype(str).str.startswith("002")]
    preseason = games_df[games_df["gameId"].astype(str).str.startswith("001")]
    other = games_df[~games_df["gameId"].astype(str).str.startswith(("001","002","004","005","006"))]

    print(f"\n  Game type counts by GAME_ID prefix:")
    print(f"    001* (Preseason):    {len(preseason)} games")
    print(f"    002* (Regular):      {len(regular)} games")
    print(f"    004* (Playoffs):     {len(playoffs)} games")
    print(f"    005* (Play-In):      {len(playin)} games")
    print(f"    Other:               {len(other)} games")
    if len(other) > 0:
        print(f"    Other game IDs: {other['gameId'].head(10).tolist()}")

    if len(playin) > 0:
        print(f"\n  Play-In games in 2025-26 schedule:")
        cols = ["gameId","gameDate","gameLabel","gameSubLabel","seriesText","seriesGameNumber",
                "gameSubtype","homeTeam_teamTricode","awayTeam_teamTricode"]
        avail = [c for c in cols if c in playin.columns]
        print(playin[avail].to_string(index=False))
    else:
        print("\n  No Play-In games found yet (005* prefix) in schedule")

    if len(playoffs) > 0:
        print(f"\n  Playoff games in 2025-26 schedule:")
        cols = ["gameId","gameDate","gameLabel","gameSubLabel","seriesText","seriesGameNumber",
                "ifNecessary","homeTeam_teamTricode","awayTeam_teamTricode","homeTeam_seed","awayTeam_seed"]
        avail = [c for c in cols if c in playoffs.columns]
        print(playoffs[avail].to_string(index=False))
    else:
        print("\n  No 004* playoff games found in schedule yet")

    # Show unique gameLabel values to understand all game types
    print(f"\n  All unique gameLabel values:")
    print(games_df["gameLabel"].value_counts().to_string())

    print(f"\n  All unique gameSubtype values:")
    print(games_df["gameSubtype"].value_counts().to_string())

except Exception as e:
    print(f"  ERROR: {e}")
    import traceback; traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# C. ScheduleLeagueV2 for 2024-25 — verify play-in game IDs
# ─────────────────────────────────────────────────────────────────────────────
section("C. ScheduleLeagueV2 — Play-In games in 2024-25 (verified data)")
try:
    from nba_api.stats.endpoints import ScheduleLeagueV2
    sched24 = ScheduleLeagueV2(season="2024-25", timeout=120)
    time.sleep(1)
    g24 = sched24.season_games.get_data_frame()

    playin24 = g24[g24["gameId"].astype(str).str.startswith("005")]
    playoffs24 = g24[g24["gameId"].astype(str).str.startswith("004")]

    print(f"\n  2024-25 Play-In games (005* prefix): {len(playin24)}")
    if len(playin24) > 0:
        cols = ["gameId","gameDate","gameLabel","gameSubLabel","seriesText",
                "homeTeam_teamTricode","awayTeam_teamTricode","homeTeam_score","awayTeam_score"]
        avail = [c for c in cols if c in playin24.columns]
        print(playin24[avail].to_string(index=False))

    print(f"\n  2024-25 Playoff games (004* prefix): {len(playoffs24)}")
    if len(playoffs24) > 0:
        cols = ["gameId","gameDate","gameLabel","gameSubLabel","seriesText","seriesGameNumber",
                "ifNecessary","homeTeam_teamTricode","awayTeam_teamTricode",
                "homeTeam_seed","awayTeam_seed","homeTeam_score","awayTeam_score"]
        avail = [c for c in cols if c in playoffs24.columns]
        # Show first round games
        print("  First 20 playoff games:")
        print(playoffs24[avail].head(20).to_string(index=False))
        print(f"\n  seriesText distribution:")
        print(playoffs24["seriesText"].value_counts().head(20).to_string())

except Exception as e:
    print(f"  ERROR: {e}")
    import traceback; traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# D. LeagueDashTeamStats — for team ratings during playoffs
# ─────────────────────────────────────────────────────────────────────────────
section("D. LeagueDashTeamStats — check it works for Playoffs season type")
try:
    from nba_api.stats.endpoints import LeagueDashTeamStats
    # Try playoff stats for prior season to confirm structure
    ldts = LeagueDashTeamStats(season="2024-25", season_type_all_star="Playoffs", timeout=60)
    time.sleep(1)
    df = ldts.league_dash_team_stats.get_data_frame()
    print(f"\n  Shape: {df.shape}")
    print(f"  Columns: {list(df.columns)}")
    print(f"\n  Sample (sorted by NET_RATING desc):")
    if "NET_RATING" in df.columns:
        print(df.sort_values("NET_RATING", ascending=False)[
            ["TEAM_NAME","GP","W","L","W_PCT","PTS","OFF_RATING","DEF_RATING","NET_RATING"]
        ].head(16).to_string(index=False))
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback; traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# E. BoxScoreSummaryV2 — check what playoff series info it provides
# ─────────────────────────────────────────────────────────────────────────────
section("E. BoxScoreSummaryV2 — playoff series state from a game")
print("  Using a 2024-25 playoff game: 0042400101 (Cleveland vs Miami, Game 1)")
try:
    from nba_api.stats.endpoints import BoxScoreSummaryV2
    bss = BoxScoreSummaryV2(game_id="0042400101", timeout=60)
    time.sleep(1)

    # Check all result sets
    for ds in bss.data_sets:
        df = ds.get_data_frame()
        if len(df) > 0:
            print(f"\n  DataSet with {df.shape}: cols={list(df.columns)}")
            print(df.head(3).to_string(index=False))
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback; traceback.print_exc()

print("\n\n" + "=" * 80)
print("  DEEP DIVE COMPLETE")
print("=" * 80)
