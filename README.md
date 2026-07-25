# billblatzheim-website

Files for billblatzheim.com — a small collection of static sports dashboards.
Each project is a self-contained directory: a Python script fetches/generates
data and writes a fully self-contained `index.html` (no build step, no server
required). Deploy = commit + push.

## File structure

```
.
├── index.html            # Homepage — links out to each project below
├── scripts/
│   └── daily_update.sh   # Cron job (launchd): runs the MLB update daily (auto-push is broken, see below)
├── f1/                    # F1 season tracker
│   ├── update.py
│   ├── f1_cache.json      # Build-time cache (fetched season data)
│   └── index.html         # Generated output
├── mlb-newspaper/         # MLB box scores, newspaper-style
│   ├── update.py          # Modern layout -> index.html
│   ├── update_nyt.py      # Classic NYT layout -> nyt.html (shares update.py's cache)
│   └── mlb_cache.json
├── mnba-ratings/          # MN Town Ball (MBA) Elo ratings
│   ├── update.py          # Orchestrates the pipeline below, in order
│   ├── scrape_games.py
│   ├── scrape_standings.py
│   ├── clean_games.py
│   ├── batch_fit.py
│   ├── elo_live.py
│   ├── build_site.py      # -> index.html
│   ├── build_scores.py    # -> scores.html
│   ├── compare_polls.py   # Run manually/separately (see below)
│   └── *.json             # games_raw, teams_raw, games_clean, ratings_2026*
├── nba-importance/        # NBA game-importance scorer
│   ├── update.py          # -> index.html (regular season) or playoff.html (postseason)
│   └── playoff.html
└── four-factors/          # Dean Oliver four factors dashboard
    └── index.html         # Static — no update script, edited by hand
```

## Updating each project

### F1 Season Tracker (`f1/`)
```
python3 update.py                        # rebuild index.html from cache + baked-in data
python3 update.py --add 2022 2023 2024 2025  # fetch & cache seasons
python3 update.py --add 2026             # add current season mid-year
python3 update.py --refresh 2025         # force re-fetch a season
```

### MLB Box Score Newspaper (`mlb-newspaper/`)
```
python3 update.py                # fetch yesterday's games -> index.html
python3 update.py 2026-03-24     # fetch a specific date
python3 update.py --rebuild      # regenerate HTML from cache only, no fetch
python3 update.py --schedule 2026    # load the full season schedule
python3 update.py --clear-date 2026-03-24
python3 update.py --clear-year 2025

python3 update_nyt.py            # regenerate nyt.html from the same cache
```
Runs automatically every day via `scripts/daily_update.sh` (launchd cron),
which is *supposed* to also commit and push if anything changed — in
practice the auto-commit/push has never reliably worked from cron, so the
generated files still need to be pushed manually most days (TODO: fix this).

### MNBA Elo Ratings (`mnba-ratings/`)
```
python3 update.py                # runs the full pipeline, stops at first failure:
                                  # scrape_games -> scrape_standings -> clean_games
                                  # -> batch_fit -> elo_live -> build_site -> build_scores

python3 compare_polls.py         # run separately, only when MBA publishes a new poll
```

### NBA Game Importance (`nba-importance/`)
```
python3 update.py
```
Writes `index.html` directly during the regular season; during the
playoffs it instead writes `playoff.html` and makes `index.html` redirect
to it.

### Four Factors (`four-factors/`)
No script — `index.html` is static and edited by hand.

## Manual deploy
After running the relevant `update.py`, commit and push the changed
`index.html`/cache files for that project:
```
git add <project>/index.html <project>/*_cache.json ...
git commit -m "..."
git push
```
