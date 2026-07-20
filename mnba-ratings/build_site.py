"""
Generates a bare-bones index.html from the live-Elo ratings. Linked from the
main site nav now -- still evolving, so kept deliberately plain (no
chart/design polish yet).
"""
import json
from datetime import date, datetime

def load_last_games():
    games = json.load(open("games_clean.json"))
    last = {}
    for g in games:
        game_date = datetime.strptime(g["date"], "%Y-%m-%d").date()
        for side, opp_side in (("home", "away"), ("away", "home")):
            team = g[f"{side}_team"]
            prev = last.get(team)
            if prev and prev["date"] >= game_date:
                continue
            team_score = g[f"{side}_score"]
            opp_score = g[f"{opp_side}_score"]
            result = "W" if team_score > opp_score else "L" if team_score < opp_score else "T"
            last[team] = {
                "date": game_date,
                "text": (
                    f'{result} {team_score}-{opp_score} '
                    f'{"vs" if side == "home" else "@"} {g[f"{opp_side}_team"]} '
                    f'({game_date.strftime("%-m/%-d")})'
                ),
            }
    return {team: v["text"] for team, v in last.items()}


def load_data():
    live = json.load(open("ratings_2026_live_elo.json"))
    teams = json.load(open("teams_raw.json"))
    teams_meta = {t["team_name"]: t for t in teams}
    last_games = load_last_games()

    rows = []
    for r in live:
        if not r["known"]:
            continue
        meta = teams_meta[r["team"]]
        w, l, t = meta["overall_record"].split("-")
        record = f"{w}-{l}" if t == "0" else f"{w}-{l}-{t}"

        rows.append({
            "team": r["team"],
            "class": r["class"],
            "league": meta["league"],
            "record": record,
            "rating": round(r["elo_live"]),
            "last_game": last_games.get(r["team"], "—"),
        })
    return rows


def render_table(rows, show_class=False):
    rows = sorted(rows, key=lambda r: -r["rating"])
    class_col = '<col style="width:56px">' if show_class else ''
    class_th = '<th>Class</th>' if show_class else ''
    colgroup = (
        '<colgroup>'
        '<col style="width:44px">'
        '<col style="width:22%">'
        f'{class_col}'
        '<col style="width:26%">'
        '<col style="width:80px">'
        '<col style="width:24%">'
        '<col style="width:70px">'
        '</colgroup>'
    )
    out = [
        '<div class="table-wrap"><table>', colgroup,
        f'<thead><tr><th>#</th><th>Team</th>{class_th}<th>League</th><th>Record</th><th>Last Game</th><th>Rating</th></tr></thead>',
        '<tbody>',
    ]
    for i, r in enumerate(rows, 1):
        class_td = f'<td class="class">{r["class"]}</td>' if show_class else ''
        out.append(
            f'<tr><td class="rank">{i}</td><td class="team">{r["team"]}</td>{class_td}<td class="league">{r["league"]}</td>'
            f'<td>{r["record"]}</td><td class="last-game">{r["last_game"]}</td>'
            f'<td class="rating">{r["rating"]}</td></tr>'
        )
    out.append('</tbody></table></div>')
    return "\n".join(out)


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>MN Town Ball Ratings (beta)</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif; max-width: 860px; margin: 40px auto; padding: 0 16px; color: #222; line-height: 1.5; }}
h1 {{ font-size: 22px; margin-bottom: 4px; }}
.subtitle {{ color: #777; font-size: 13px; margin-bottom: 4px; }}
.nav {{ font-size: 13px; margin-bottom: 24px; }}
.nav a {{ color: #06c; text-decoration: none; }}
.nav a:hover {{ text-decoration: underline; }}
.note {{ background: #fffbe6; border: 1px solid #f0e2a3; border-radius: 4px; padding: 12px 16px; font-size: 14px; margin-bottom: 28px; }}
.explainer {{ font-size: 15px; margin-bottom: 32px; }}
.explainer ul {{ padding-left: 20px; }}
.explainer li {{ margin-bottom: 6px; }}
h2 {{ font-size: 18px; border-bottom: 2px solid #333; padding-bottom: 4px; margin-top: 40px; }}
.table-wrap {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; min-width: 560px; table-layout: fixed; font-size: 14px; margin-top: 12px; }}
th, td {{ text-align: left; padding: 5px 8px; border-bottom: 1px solid #eee; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
th {{ color: #777; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: .03em; }}
td.rank {{ overflow: visible; white-space: nowrap; color: #999; }}
td.team {{ font-weight: 500; }}
td.rating {{ text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; }}
td.league {{ color: #888; font-size: 13px; }}
td.last-game {{ color: #555; font-size: 13px; }}
td.class {{ color: #888; font-size: 13px; }}
tr:nth-child(even) {{ background: #fafafa; }}
footer {{ margin-top: 48px; color: #999; font-size: 12px; border-top: 1px solid #eee; padding-top: 12px; }}
.view-toggle {{ display: flex; gap: 6px; margin-top: 24px; }}
.view-toggle button {{ font: inherit; font-size: 13px; padding: 5px 12px; border-radius: 999px; border: 1px solid #ccc; background: #fafafa; color: #444; cursor: pointer; }}
.view-toggle button.active {{ background: #222; border-color: #222; color: #fff; }}
.view {{ display: none; }}
.view.active {{ display: block; }}
</style>
</head>
<body>

<h1>Minnesota Town Ball Ratings <span style="color:#999;font-weight:normal;">(beta)</span></h1>
<div class="subtitle">Unofficial, not affiliated with the MBA &middot; generated {generated_date}</div>
<div class="nav"><a href="scores.html">Scores &rarr;</a></div>

<div class="note">
This is a live, in-season model &mdash; ratings shift as more games are played and the underlying
model keeps getting refined. If a result looks off to you, I'd love to hear about it.
</div>

<div class="explainer">
<p><strong>What is this?</strong> An attempt at ranking every MBA town ball team (Class A, B, and C) on
one shared scale, using only game results &mdash; not reputation, not who won it last year.</p>
<ul>
<li>Win-loss record alone doesn't account for <em>who</em> you played. Beating a strong team counts for
more than beating a weak one, so a team can rank ahead of a team with a better record if its wins came
against tougher competition.</li>
<li>Blowout wins count for a bit more than nail-biters, but only up to a point &mdash; we can't tell a real
9-inning blowout from one that just hit the 10-run rule, so we cap it there.</li>
<li>A team's rating carries over some information from last season (regressed toward the average for
its class), then moves based on this year's games as they're played.</li>
<li>Every league in the state is connected to every other one through nonleague games, region/section
play, and tournaments, which is what makes comparing a Class C team in the far southwest to a Class A
metro team possible at all.</li>
</ul>
<p>It's rougher around the edges than that makes it sound &mdash; happy to talk through any result that
looks off.</p>
</div>

<div class="view-toggle">
<button data-view="by-class" class="active">By Class</button>
<button data-view="overall">Overall</button>
</div>

<div id="by-class" class="view active">
{tables_by_class}
</div>

<div id="overall" class="view">
{table_overall}
</div>

<footer>
Built from mnbaseball.org schedule/results and standings data. Ratings shown are a live, in-season
model (not a season-end snapshot) &mdash; last updated {generated_date}.
</footer>

<script>
document.querySelectorAll('.view-toggle button').forEach(function(btn) {{
  btn.addEventListener('click', function() {{
    document.querySelectorAll('.view-toggle button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById(btn.dataset.view).classList.add('active');
  }});
}});
</script>

</body>
</html>
"""


if __name__ == "__main__":
    rows = load_data()

    tables_by_class = []
    for cls in ["A", "B", "C"]:
        cls_rows = [r for r in rows if r["class"] == cls]
        tables_by_class.append(f"<h2>Class {cls}</h2>")
        tables_by_class.append(render_table(cls_rows))

    html = PAGE.format(
        generated_date=date.today().strftime("%B %-d, %Y"),
        tables_by_class="\n".join(tables_by_class),
        table_overall=render_table(rows, show_class=True),
    )

    with open("index.html", "w") as f:
        f.write(html)
    print(f"Wrote index.html ({len(rows)} teams across 3 classes)")
