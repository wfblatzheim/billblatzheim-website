"""
Bradley-Terry batch fit over a single season's cleaned games.

Still a binary win/loss outcome under the hood (no home-field advantage
term either) -- this is the first-pass "if the season ended today" ranking,
order-independent, no seed values required. Margin of victory is folded in
as a per-game *weight* on the logistic regression loss (a blowout counts
more toward pinning down the strength gap than a nail-biter does), rather
than changing what's being predicted.

We have no innings_played data, so we can't tell a genuine 9-inning blowout
apart from a game the 10-run rule cut short. Practical stand-in: cap the
margin at MOV_CAP before log-scaling it, on the logic that anything past
that point is about equally "decisive" and further margin doesn't add real
information (23% of 2026 games ended with a 10+ run margin, so this isn't
a rare edge case).

Ties are dropped: they're rare (26 of 1950 games in the 2026 season, most
of them 0-0 and almost certainly postponed/incomplete games rather than a
true baseball tie) and this is a binary win/loss model.
"""
import json

import numpy as np
from scipy import sparse
from sklearn.linear_model import LogisticRegression

REG_STRENGTH = 1.0  # C in sklearn's LogisticRegression; keeps thin-sample teams from diverging
MOV_CAP = 10  # runs; margins beyond this are treated as equally decisive


def mov_weight(margin):
    return 1 + np.log1p(min(margin, MOV_CAP))


def fit_season(games, teams_meta, season_year, use_mov=True):
    season_games = [
        g for g in games
        if g["date"][:4] == str(season_year) and g["home_score"] != g["away_score"]
    ]

    team_names = sorted({g["home_team"] for g in season_games} | {g["away_team"] for g in season_games})
    idx = {name: i for i, name in enumerate(team_names)}
    n_teams = len(team_names)
    n_games = len(season_games)

    rows, cols, data = [], [], []
    y = np.zeros(n_games)
    weights = np.ones(n_games)
    games_played = np.zeros(n_teams, dtype=int)
    wins = np.zeros(n_teams, dtype=int)

    for g_i, g in enumerate(season_games):
        h, a = idx[g["home_team"]], idx[g["away_team"]]
        rows += [g_i, g_i]
        cols += [h, a]
        data += [1, -1]
        home_won = g["home_score"] > g["away_score"]
        y[g_i] = 1 if home_won else 0
        if use_mov:
            weights[g_i] = mov_weight(abs(g["home_score"] - g["away_score"]))
        games_played[h] += 1
        games_played[a] += 1
        wins[h if home_won else a] += 1

    X = sparse.csr_matrix((data, (rows, cols)), shape=(n_games, n_teams))

    model = LogisticRegression(fit_intercept=False, C=REG_STRENGTH, solver="lbfgs", max_iter=1000)
    model.fit(X, y, sample_weight=weights)

    strength = model.coef_[0]
    strength = strength - strength.mean()  # center for interpretability; differences are all that matter

    # Standard error per team, from the curvature (Hessian) of the fitted model's
    # objective at the solution. sklearn minimizes 0.5*||beta||^2 + C * weighted
    # log-loss, so the Hessian is I + C * X^T diag(w_i * p_i * (1-p_i)) X. Its
    # inverse approximates the covariance of the fitted coefficients -- teams
    # with few games, less-decisive games, or shakier ties into the rest of the
    # graph get a wider standard error here, all from the same fit, no separate
    # heuristic needed.
    p = model.predict_proba(X)[:, 1]
    curvature = weights * p * (1 - p)
    X_dense = X.toarray()
    hessian = np.eye(n_teams) + REG_STRENGTH * (X_dense.T * curvature) @ X_dense
    cov = np.linalg.inv(hessian)
    se = np.sqrt(np.diag(cov))

    elo_scale = 400 / np.log(10)
    results = []
    for name, i in idx.items():
        meta = teams_meta.get(name)
        results.append({
            "team": name,
            "known": meta is not None,
            "class": meta["class"] if meta else None,
            "league": meta["league"] if meta else None,
            "rating": round(float(strength[i]), 4),
            "elo_like": round(1500 + float(strength[i]) * elo_scale, 1),
            "se_elo": round(float(se[i]) * elo_scale, 1),
            "games_played": int(games_played[i]),
            "wins": int(wins[i]),
            "losses": int(games_played[i] - wins[i]),
        })

    results.sort(key=lambda r: r["rating"], reverse=True)
    return results, n_games, n_teams


if __name__ == "__main__":
    games = json.load(open("games_clean.json"))
    teams = json.load(open("teams_raw.json"))
    teams_meta = {t["team_name"]: t for t in teams}

    results, n_games, n_teams = fit_season(games, teams_meta, 2026, use_mov=True)
    print(f"Fit {n_teams} teams over {n_games} games (2026 season, ties dropped, MOV-weighted)\n")

    print("Top 20:")
    for r in results[:20]:
        cls = r["class"] or "?"
        print(f"  {r['elo_like']:7.1f} +/-{r['se_elo']:5.1f}  [{cls}]  {r['team']:30s}  {r['wins']}-{r['losses']}  ({r['games_played']}g)")

    print("\nBottom 10:")
    for r in results[-10:]:
        cls = r["class"] or "?"
        print(f"  {r['elo_like']:7.1f} +/-{r['se_elo']:5.1f}  [{cls}]  {r['team']:30s}  {r['wins']}-{r['losses']}  ({r['games_played']}g)")

    print("\nWidest and narrowest confidence bands:")
    by_se = sorted(results, key=lambda r: r["se_elo"])
    print("  Narrowest (most confident):")
    for r in by_se[:5]:
        print(f"    +/-{r['se_elo']:5.1f}  {r['elo_like']:7.1f}  {r['team']:30s}  ({r['games_played']}g)")
    print("  Widest (least confident):")
    for r in by_se[-5:]:
        print(f"    +/-{r['se_elo']:5.1f}  {r['elo_like']:7.1f}  {r['team']:30s}  ({r['games_played']}g)")

    print("\nHarrisburg Woodies vs. a similarly-rated, well-established team:")
    for name in ["Harrisburg Woodies", "Miesville Mudhens"]:
        r = next(r for r in results if r["team"] == name)
        print(f"  {r['elo_like']:7.1f} +/-{r['se_elo']:5.1f}  {name}  ({r['games_played']}g)")

    with open("ratings_2026.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved {len(results)} team ratings to ratings_2026.json")

    # Compare against the plain win/loss version to see what MOV weighting actually changed
    plain_results, _, _ = fit_season(games, teams_meta, 2026, use_mov=False)
    plain_rank = {r["team"]: i for i, r in enumerate(sorted(plain_results, key=lambda r: -r["rating"]))}
    mov_rank = {r["team"]: i for i, r in enumerate(results)}

    moves = [(mov_rank[t] - plain_rank[t], t) for t in mov_rank]
    moves.sort()
    print("\nBiggest rank improvements from MOV weighting (negative = moved up):")
    for delta, team in moves[:10]:
        print(f"  {delta:+4d}  {team}")
    print("\nBiggest rank drops from MOV weighting:")
    for delta, team in moves[-10:]:
        print(f"  {delta:+4d}  {team}")
