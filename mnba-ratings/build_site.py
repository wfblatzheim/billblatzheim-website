"""
Generates a bare-bones index.html from the live-Elo ratings. Not linked from
the main site nav -- this is a private-share link for early feedback, so
kept deliberately plain (no chart/design polish yet).
"""
import json
from datetime import date

def load_data():
    live = json.load(open("ratings_2026_live_elo.json"))
    teams = json.load(open("teams_raw.json"))
    teams_meta = {t["team_name"]: t for t in teams}

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
        })
    return rows


def render_table(rows):
    rows = sorted(rows, key=lambda r: -r["rating"])
    out = ['<table>', '<thead><tr><th>#</th><th>Team</th><th>League</th><th>Record</th><th>Rating</th></tr></thead>', '<tbody>']
    for i, r in enumerate(rows, 1):
        out.append(
            f'<tr><td>{i}</td><td>{r["team"]}</td><td class="league">{r["league"]}</td>'
            f'<td>{r["record"]}</td><td class="rating">{r["rating"]}</td></tr>'
        )
    out.append('</tbody></table>')
    return "\n".join(out)


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta name="robots" content="noindex, nofollow">
<title>MN Town Ball Ratings (draft)</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif; max-width: 720px; margin: 40px auto; padding: 0 16px; color: #222; line-height: 1.5; }}
h1 {{ font-size: 22px; margin-bottom: 4px; }}
.subtitle {{ color: #777; font-size: 13px; margin-bottom: 24px; }}
.note {{ background: #fffbe6; border: 1px solid #f0e2a3; border-radius: 4px; padding: 12px 16px; font-size: 14px; margin-bottom: 28px; }}
.explainer {{ font-size: 15px; margin-bottom: 32px; }}
.explainer ul {{ padding-left: 20px; }}
.explainer li {{ margin-bottom: 6px; }}
h2 {{ font-size: 18px; border-bottom: 2px solid #333; padding-bottom: 4px; margin-top: 40px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 14px; margin-top: 12px; }}
th, td {{ text-align: left; padding: 5px 8px; border-bottom: 1px solid #eee; }}
th {{ color: #777; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: .03em; }}
td.rating {{ text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; }}
td.league {{ color: #888; font-size: 13px; }}
tr:nth-child(even) {{ background: #fafafa; }}
footer {{ margin-top: 48px; color: #999; font-size: 12px; border-top: 1px solid #eee; padding-top: 12px; }}
</style>
</head>
<body>

<h1>Minnesota Town Ball Ratings <span style="color:#999;font-weight:normal;">(draft)</span></h1>
<div class="subtitle">Unofficial, not affiliated with the MBA &middot; generated {generated_date}</div>

<div class="note">
This is an early, unfinished prototype. Ratings will change as more games are played and as the
underlying model gets refined. Please don't share this link further yet &mdash; just looking for
gut-check feedback on whether these rankings feel roughly right.
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

{tables}

<footer>
Built from mnbaseball.org schedule/results and standings data. Ratings shown are a live, in-season
model (not a season-end snapshot) &mdash; last updated {generated_date}.
</footer>

</body>
</html>
"""


if __name__ == "__main__":
    rows = load_data()

    tables = []
    for cls in ["A", "B", "C"]:
        cls_rows = [r for r in rows if r["class"] == cls]
        tables.append(f"<h2>Class {cls}</h2>")
        tables.append(render_table(cls_rows))

    html = PAGE.format(
        generated_date=date.today().strftime("%B %-d, %Y"),
        tables="\n".join(tables),
    )

    with open("index.html", "w") as f:
        f.write(html)
    print(f"Wrote index.html ({len(rows)} teams across 3 classes)")
