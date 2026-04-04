#!/usr/bin/env python3
"""
Comprehensive exploration of nba_api endpoints relevant to playoff tracking.
Season: 2025-26 (current season as of April 2026)
"""

import sys
import time
import traceback
import pandas as pd

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 40)

SEASON = "2025-26"
SEASON_ID = "22025"  # PlayoffPicture uses SeasonID format: "2" prefix + year

def section(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def show_df(df, label="", max_rows=5):
    print(f"\n-- {label} --")
    print(f"  Shape: {df.shape}")
    print(f"  Columns: {list(df.columns)}")
    if len(df) > 0:
        print(df.head(max_rows).to_string(index=False))
    else:
        print("  [EMPTY - no rows returned]")

# ─────────────────────────────────────────────────────────────────────────────
# 1. PlayoffPicture
# ─────────────────────────────────────────────────────────────────────────────
section("1. PlayoffPicture  (endpoint: playoffpicture)")
print("  Parameters: LeagueID, SeasonID")
print(f"  Calling with SeasonID='{SEASON_ID}' ...")
try:
    from nba_api.stats.endpoints import PlayoffPicture
    pp = PlayoffPicture(season_id=SEASON_ID, timeout=60)
    time.sleep(1)

    east_pic = pp.east_conf_playoff_picture.get_data_frame()
    west_pic = pp.west_conf_playoff_picture.get_data_frame()
    east_stand = pp.east_conf_standings.get_data_frame()
    west_stand = pp.west_conf_standings.get_data_frame()
    east_rem = pp.east_conf_remaining_games.get_data_frame()
    west_rem = pp.west_conf_remaining_games.get_data_frame()

    show_df(east_pic, "EastConfPlayoffPicture")
    show_df(west_pic, "WestConfPlayoffPicture")
    show_df(east_stand, "EastConfStandings (first 5 rows, key cols)")
    # Show just the most relevant standing columns
    key_cols = ["RANK","TEAM","WINS","LOSSES","PCT","CLINCHED_PLAYOFFS","Clinched_Play_In","ELIMINATED_PLAYOFFS"]
    available = [c for c in key_cols if c in east_stand.columns]
    print("\n  East standings (key cols only):")
    print(east_stand[available].head(16).to_string(index=False))
    print("\n  West standings (key cols only):")
    west_avail = [c for c in key_cols if c in west_stand.columns]
    print(west_stand[west_avail].head(16).to_string(index=False))
    show_df(east_rem, "EastConfRemainingGames")
    show_df(west_rem, "WestConfRemainingGames")
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# 2. CommonPlayoffSeries
# ─────────────────────────────────────────────────────────────────────────────
section("2. CommonPlayoffSeries  (endpoint: commonplayoffseries)")
print("  Parameters: LeagueID, Season, SeriesID (nullable)")
print(f"  Calling with Season='{SEASON}' ...")
try:
    from nba_api.stats.endpoints import CommonPlayoffSeries
    cps = CommonPlayoffSeries(season=SEASON, timeout=60)
    time.sleep(1)

    df = cps.playoff_series.get_data_frame()
    show_df(df, "PlayoffSeries", max_rows=20)

    if len(df) > 0:
        print("\n  GAME_ID prefixes found:")
        df["game_prefix"] = df["GAME_ID"].astype(str).str[:3]
        print(df["game_prefix"].value_counts().to_string())
        print("\n  Unique SERIES_IDs:")
        print(df["SERIES_ID"].unique())
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# 3. LeagueStandingsV3
# ─────────────────────────────────────────────────────────────────────────────
section("3. LeagueStandingsV3  (endpoint: leaguestandingsv3)")
print("  Parameters: LeagueID, Season, SeasonType, SeasonYear")
print(f"  Calling with Season='{SEASON}', SeasonType='Regular Season' ...")
try:
    from nba_api.stats.endpoints import LeagueStandingsV3
    lsv3 = LeagueStandingsV3(season=SEASON, timeout=60)
    time.sleep(1)

    df = lsv3.standings.get_data_frame()
    show_df(df, "Standings")

    key_cols = ["PlayoffRank","ClinchIndicator","TeamCity","TeamName","Conference",
                "WINS","LOSSES","WinPCT","ClinchedPlayoffBirth","EliminatedConference"]
    available = [c for c in key_cols if c in df.columns]
    print("\n  Key standing columns:")
    print(df[available].head(30).to_string(index=False))
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# 4. LeagueGameFinder — Playoffs
# ─────────────────────────────────────────────────────────────────────────────
section("4. LeagueGameFinder — season_type='Playoffs'")
print(f"  Calling with season_nullable='{SEASON}', season_type_nullable='Playoffs' ...")
try:
    from nba_api.stats.endpoints import LeagueGameFinder
    lgf_po = LeagueGameFinder(
        player_or_team_abbreviation="T",
        season_nullable=SEASON,
        season_type_nullable="Playoffs",
        timeout=60
    )
    time.sleep(1)

    df = lgf_po.league_game_finder_results.get_data_frame()
    show_df(df, "LeagueGameFinderResults (Playoffs)", max_rows=10)

    if len(df) > 0:
        print("\n  GAME_ID prefixes:")
        df["prefix"] = df["GAME_ID"].astype(str).str[:3]
        print(df["prefix"].value_counts().to_string())
        print("\n  Sample GAME_IDs:")
        print(df["GAME_ID"].head(10).to_string())
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# 5. LeagueGameFinder — PlayIn
# ─────────────────────────────────────────────────────────────────────────────
section("5. LeagueGameFinder — season_type='PlayIn'")
print(f"  Calling with season_nullable='{SEASON}', season_type_nullable='PlayIn' ...")
try:
    from nba_api.stats.endpoints import LeagueGameFinder
    lgf_pi = LeagueGameFinder(
        player_or_team_abbreviation="T",
        season_nullable=SEASON,
        season_type_nullable="PlayIn",
        timeout=60
    )
    time.sleep(1)

    df = lgf_pi.league_game_finder_results.get_data_frame()
    show_df(df, "LeagueGameFinderResults (PlayIn)", max_rows=20)

    if len(df) > 0:
        print("\n  GAME_ID prefixes:")
        df["prefix"] = df["GAME_ID"].astype(str).str[:3]
        print(df["prefix"].value_counts().to_string())
        print("\n  All GAME_IDs:")
        print(df[["GAME_ID","GAME_DATE","MATCHUP","WL","PTS"]].to_string(index=False))
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# 6. LeagueGameFinder — Regular Season (to show GAME_ID format)
# ─────────────────────────────────────────────────────────────────────────────
section("6. LeagueGameFinder — Regular Season GAME_ID prefix analysis")
print(f"  Calling with season_nullable='{SEASON}', season_type_nullable='Regular Season' ...")
try:
    from nba_api.stats.endpoints import LeagueGameFinder
    lgf_rs = LeagueGameFinder(
        player_or_team_abbreviation="T",
        season_nullable=SEASON,
        season_type_nullable="Regular Season",
        timeout=60
    )
    time.sleep(1)

    df = lgf_rs.league_game_finder_results.get_data_frame()
    print(f"\n  Shape: {df.shape}")
    print(f"\n  GAME_ID prefixes (first digit = season type):")
    df["prefix"] = df["GAME_ID"].astype(str).str[:3]
    df["first_digit"] = df["GAME_ID"].astype(str).str[0]
    print(df["first_digit"].value_counts().to_string())
    print("\n  Sample GAME_IDs (Regular Season):")
    print(df["GAME_ID"].head(5).to_list())
    print(f"\n  SEASON_ID values:")
    print(df["SEASON_ID"].head(3).to_list())
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# 7. ScheduleLeagueV2 — look for playoff/playin fields
# ─────────────────────────────────────────────────────────────────────────────
section("7. ScheduleLeagueV2  (endpoint: scheduleleaguev2)")
print(f"  Calling with Season='{SEASON}' ...")
try:
    from nba_api.stats.endpoints import ScheduleLeagueV2
    sched = ScheduleLeagueV2(season=SEASON, timeout=120)
    time.sleep(1)

    games_df = sched.season_games.get_data_frame()
    weeks_df = sched.season_weeks.get_data_frame()

    show_df(weeks_df, "SeasonWeeks")
    print(f"\n  SeasonGames shape: {games_df.shape}")
    print(f"  SeasonGames columns: {list(games_df.columns)}")

    # Show key fields for identifying game type
    key_cols = ["gameId","gameDate","gameLabel","gameSubLabel","seriesText",
                "seriesGameNumber","gameSubtype","ifNecessary",
                "homeTeam_teamTricode","awayTeam_teamTricode",
                "homeTeam_seed","awayTeam_seed"]
    available = [c for c in key_cols if c in games_df.columns]

    # Filter to games with series info (playoff games)
    playoff_games = games_df[games_df["seriesText"].notna() & (games_df["seriesText"] != "")]
    print(f"\n  Games with seriesText (playoff/playin): {len(playoff_games)}")
    if len(playoff_games) > 0:
        print(playoff_games[available].head(20).to_string(index=False))

    playin_games = games_df[games_df["gameSubtype"].notna() & (games_df["gameSubtype"] != "")]
    print(f"\n  Games with gameSubtype set: {len(playin_games)}")
    if len(playin_games) > 0:
        print(playin_games[available].head(10).to_string(index=False))

    # Show gameId prefix analysis
    print("\n  GAME_ID first-digit distribution:")
    games_df["first_digit"] = games_df["gameId"].astype(str).str[0]
    print(games_df["first_digit"].value_counts().to_string())

    # Show sample of upcoming/recent games
    print("\n  Sample of recent/upcoming games (last 5 rows):")
    print(games_df[available].tail(5).to_string(index=False))

    # Show any games in April
    april_games = games_df[games_df["gameDate"].astype(str).str.startswith("2026-04")]
    print(f"\n  April 2026 games: {len(april_games)}")
    if len(april_games) > 0:
        print(april_games[available].head(15).to_string(index=False))

except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# 8. TeamEstimatedMetrics (ratings)
# ─────────────────────────────────────────────────────────────────────────────
section("8. TeamEstimatedMetrics  (endpoint: teamestimatedmetrics)")
print(f"  Calling with Season='{SEASON}', SeasonType='Regular Season' ...")
try:
    from nba_api.stats.endpoints import TeamEstimatedMetrics
    tem = TeamEstimatedMetrics(season=SEASON, timeout=60)
    time.sleep(1)

    df = tem.team_estimated_metrics.get_data_frame()
    show_df(df, "TeamEstimatedMetrics", max_rows=10)
    print("\n  All columns:", list(df.columns))
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# 9. GAME_ID format documentation
# ─────────────────────────────────────────────────────────────────────────────
section("9. GAME_ID Format Documentation")
print("""
  NBA GAME_ID format: 10-digit string  e.g. "0022500001"

  Digit breakdown:
    [0]   = Season type prefix
              0 = Regular Season
              1 = Preseason
              2 = All-Star
              4 = Play-In Tournament  (or sometimes encoded as prefix "005")
              5 = Play-In Tournament  (confirmed in recent seasons)
    [1-2] = Last two digits of season year (e.g. 25 for 2025-26)
    [3-4] = Sub-league/division code (00 for NBA)
    [5-9] = Sequential game number within season type

  Examples from 2024-25 season:
    0022400001  -> Regular Season game #1 (002 = RS, 24 = 2024-25)
    0052400001  -> Play-In game           (005 = Play-In, 24 = 2024-25)
    0042400101  -> Playoff game           (004 = Playoffs, 24 = 2024-25)

  SEASON_ID format (used in some endpoints):
    "22025"  -> "2" (regular season code) + "2025" (season start year)
    "42025"  -> "4" (playoff code) + "2025"
    "52025"  -> "5" (play-in code) + "2025"

  The PlayoffPicture endpoint uses SeasonID="22025" for 2025-26 season.
""")

# ─────────────────────────────────────────────────────────────────────────────
# 10. Try previous season's CommonPlayoffSeries to verify structure
# ─────────────────────────────────────────────────────────────────────────────
section("10. CommonPlayoffSeries — 2024-25 season (to verify working structure)")
print("  Calling with Season='2024-25' ...")
try:
    from nba_api.stats.endpoints import CommonPlayoffSeries
    cps24 = CommonPlayoffSeries(season="2024-25", timeout=60)
    time.sleep(1)

    df = cps24.playoff_series.get_data_frame()
    show_df(df, "PlayoffSeries 2024-25", max_rows=20)

    if len(df) > 0:
        print("\n  GAME_ID prefix analysis:")
        df["prefix3"] = df["GAME_ID"].astype(str).str[:3]
        df["first_digit"] = df["GAME_ID"].astype(str).str[0]
        print(df["first_digit"].value_counts().to_string())
        print("\n  Sample series structure:")
        print(df[["GAME_ID","SERIES_ID","GAME_NUM","HOME_TEAM_ID","VISITOR_TEAM_ID"]].head(20).to_string(index=False))
        print("\n  Unique series in 2024-25 playoffs:")
        print(df.groupby("SERIES_ID").agg(
            games=("GAME_ID","count"),
            game_nums=("GAME_NUM", list)
        ).to_string())
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# 11. PlayoffPicture for 2024-25 (to see what populated data looks like)
# ─────────────────────────────────────────────────────────────────────────────
section("11. PlayoffPicture — 2024-25 season (to see populated bracket data)")
print("  Calling with SeasonID='22024' ...")
try:
    from nba_api.stats.endpoints import PlayoffPicture
    pp24 = PlayoffPicture(season_id="22024", timeout=60)
    time.sleep(1)

    east_pic = pp24.east_conf_playoff_picture.get_data_frame()
    west_pic = pp24.west_conf_playoff_picture.get_data_frame()

    show_df(east_pic, "EastConfPlayoffPicture 2024-25", max_rows=20)
    show_df(west_pic, "WestConfPlayoffPicture 2024-25", max_rows=20)
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# 12. LeagueGameFinder PlayIn for 2024-25 (to see structure)
# ─────────────────────────────────────────────────────────────────────────────
section("12. LeagueGameFinder PlayIn — 2024-25 season (to see populated data)")
print("  Calling with season_nullable='2024-25', season_type_nullable='PlayIn' ...")
try:
    from nba_api.stats.endpoints import LeagueGameFinder
    lgf_pi24 = LeagueGameFinder(
        player_or_team_abbreviation="T",
        season_nullable="2024-25",
        season_type_nullable="PlayIn",
        timeout=60
    )
    time.sleep(1)

    df = lgf_pi24.league_game_finder_results.get_data_frame()
    show_df(df, "LeagueGameFinderResults (PlayIn 2024-25)", max_rows=20)

    if len(df) > 0:
        print("\n  GAME_ID prefix analysis:")
        df["first_digit"] = df["GAME_ID"].astype(str).str[0]
        df["prefix5"] = df["GAME_ID"].astype(str).str[:5]
        print(df["first_digit"].value_counts().to_string())
        print("\n  All 2024-25 Play-In games:")
        print(df[["GAME_ID","GAME_DATE","MATCHUP","WL","PTS","SEASON_ID"]].drop_duplicates("GAME_ID").to_string(index=False))
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()

print("\n\n" + "=" * 80)
print("  EXPLORATION COMPLETE")
print("=" * 80)
