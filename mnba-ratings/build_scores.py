"""
Generates scores.html: every 2026 MBA town ball game result in one
searchable/filterable page, instead of the multi-click game-by-game browsing
on mnbaseball.org. Companion to build_site.py (ratings page) -- same plain
styling.
"""
import json
import re
from datetime import date


def categorize(raw):
    r = raw.lower()
    # "Region"/"Section"/"District" games are regular-season regional-schedule
    # games (played all season, count toward playoff seeding) -- not the
    # postseason bracket itself. Actual playoff games say "playoff", "state
    # tourn(ament/ey)", or use a "- Rd N -" bracket-round label.
    if "state tourn" in r or "playoff" in r or re.search(r"-\s*rd\s*\d", r):
        return "Playoff"
    if r == "exhibition game":
        return "Exhibition"
    if re.search(r"(tournament|invite|invitational|classic|shindig|showdown|bash|tigertown|elite 8|friendly)", r):
        return "Tournament"
    return "League"


def load_games():
    games = json.load(open("games_clean.json"))
    rows = []
    for g in games:
        if not g["date"].startswith("2026"):
            continue
        if g["away_score"] == 0 and g["home_score"] == 0:
            continue  # no score reported yet
        rows.append({
            "d": g["date"],
            "a": g["away_team"],
            "h": g["home_team"],
            "ac": g["away_class"] or "",
            "hc": g["home_class"] or "",
            "al": g["away_league"] or "",
            "hl": g["home_league"] or "",
            "as": g["away_score"],
            "hs": g["home_score"],
            "t": categorize(g["game_type_raw"]),
        })
    rows.sort(key=lambda r: (r["d"], r["h"], r["a"]))
    return rows


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>MN Town Ball Scores (beta)</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif; max-width: 720px; margin: 40px auto; padding: 0 16px; color: #222; line-height: 1.5; }}
h1 {{ font-size: 22px; margin-bottom: 4px; }}
.subtitle {{ color: #777; font-size: 13px; margin-bottom: 16px; }}
.nav {{ font-size: 13px; margin-bottom: 24px; }}
.nav a {{ color: #06c; text-decoration: none; }}
.nav a:hover {{ text-decoration: underline; }}
.note {{ background: #fffbe6; border: 1px solid #f0e2a3; border-radius: 4px; padding: 12px 16px; font-size: 14px; margin-bottom: 24px; }}

.controls {{ position: sticky; top: 0; background: #fff; padding: 12px 0; margin-bottom: 8px; border-bottom: 1px solid #eee; z-index: 10; }}
#search {{ width: 100%; box-sizing: border-box; font-size: 15px; padding: 8px 10px; border: 1px solid #ccc; border-radius: 6px; margin-bottom: 10px; }}
.pillrow {{ display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 6px; }}
.pillrow .label {{ font-size: 11px; color: #999; text-transform: uppercase; letter-spacing: .03em; margin-right: 2px; }}
.pill {{ font-size: 13px; padding: 4px 10px; border-radius: 999px; border: 1px solid #ccc; background: #fafafa; color: #444; cursor: pointer; user-select: none; }}
.pill.active {{ background: #222; border-color: #222; color: #fff; }}
.count {{ font-size: 12px; color: #999; margin-top: 6px; }}

.day {{ margin-top: 22px; }}
.day-header {{ font-size: 13px; font-weight: 600; color: #555; border-bottom: 1px solid #333; padding-bottom: 3px; margin-bottom: 6px; }}
.game {{ display: flex; justify-content: space-between; align-items: center; padding: 7px 4px; border-bottom: 1px solid #f0f0f0; gap: 10px; }}
.teams {{ flex: 1 1 auto; min-width: 0; font-size: 14px; }}
.row {{ display: flex; align-items: baseline; gap: 6px; }}
.tclass {{ flex: 0 0 auto; display: inline-block; width: 15px; font-size: 10px; font-weight: 700; color: #aaa; }}
.tname {{ flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.score {{ flex: 0 0 auto; font-variant-numeric: tabular-nums; font-weight: 600; margin-left: auto; padding-left: 8px; }}
.win .tname, .win .score {{ font-weight: 700; color: #111; }}
.game .meta {{ flex: 0 0 auto; text-align: right; font-size: 11px; color: #999; }}
.type-tag {{ display: inline-block; padding: 1px 7px; border-radius: 999px; font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: .02em; }}
.type-League {{ background: #e6f0ff; color: #2557a7; }}
.type-Playoff {{ background: #ffe6e6; color: #b02a2a; }}
.type-Tournament {{ background: #eee6ff; color: #6a3fb0; }}
.type-Exhibition {{ background: #f0f0f0; color: #777; }}
.type-Tie {{ background: #fff3d6; color: #9a6c00; margin-left: 4px; }}
.meta .league {{ display: block; margin-top: 2px; max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.empty {{ color: #999; font-size: 14px; padding: 24px 0; text-align: center; }}
footer {{ margin-top: 48px; color: #999; font-size: 12px; border-top: 1px solid #eee; padding-top: 12px; }}
@media (max-width: 480px) {{
  .meta .league {{ max-width: 90px; }}
  .tname {{ font-size: 13px; }}
}}
</style>
</head>
<body>

<h1>Minnesota Town Ball Scores <span style="color:#999;font-weight:normal;">(beta)</span></h1>
<div class="subtitle">Unofficial, not affiliated with the MBA &middot; generated {generated_date}</div>
<div class="nav"><a href="index.html">&larr; Ratings</a></div>

<div class="note">
Every 2026 game result in one page &mdash; search a team, filter by class or game type, instead of
clicking through mnbaseball.org one team/date at a time.
</div>

<div class="controls">
<input type="text" id="search" placeholder="Search team or league&hellip;" autocomplete="off">
<div class="pillrow" id="class-pills">
<span class="label">Class</span>
</div>
<div class="pillrow" id="type-pills">
<span class="label">Type</span>
</div>
<div class="pillrow" id="sort-pills">
<span class="label">Sort</span>
</div>
<div class="count" id="count"></div>
</div>

<div id="results"></div>

<footer>
Built from mnbaseball.org schedule/results data. {n} games from the 2026 season &mdash; last updated {generated_date}.
</footer>

<script>
const GAMES = {games_json};

const state = {{ q: "", cls: "All", type: "All", sort: "new" }};

function pill(container, options, key) {{
  container.innerHTML += options.map(o =>
    `<span class="pill${{state[key] === o ? " active" : ""}}" data-key="${{key}}" data-val="${{o}}">${{o}}</span>`
  ).join("");
}}
pill(document.getElementById("class-pills"), ["All", "A", "B", "C"], "cls");
pill(document.getElementById("type-pills"), ["All", "League", "Playoff", "Tournament", "Exhibition"], "type");
pill(document.getElementById("sort-pills"), ["new", "old"], "sort");

document.querySelectorAll(".pill").forEach(el => {{
  el.addEventListener("click", () => {{
    state[el.dataset.key] = el.dataset.val;
    document.querySelectorAll(`.pill[data-key="${{el.dataset.key}}"]`).forEach(p =>
      p.classList.toggle("active", p.dataset.val === el.dataset.val));
    render();
  }});
}});

document.getElementById("search").addEventListener("input", e => {{
  state.q = e.target.value.trim().toLowerCase();
  render();
}});

function fmtDate(d) {{
  const [y, m, day] = d.split("-").map(Number);
  const dt = new Date(y, m - 1, day);
  return dt.toLocaleDateString("en-US", {{ weekday: "long", month: "long", day: "numeric" }});
}}

function escapeHtml(s) {{
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}}

function render() {{
  let rows = GAMES.filter(g => state.cls === "All" || g.ac === state.cls || g.hc === state.cls);
  rows = rows.filter(g => state.type === "All" || g.t === state.type);
  if (state.q) {{
    rows = rows.filter(g =>
      g.a.toLowerCase().includes(state.q) || g.h.toLowerCase().includes(state.q) ||
      g.al.toLowerCase().includes(state.q) || g.hl.toLowerCase().includes(state.q));
  }}
  rows = rows.slice().sort((x, y) => x.d < y.d ? -1 : x.d > y.d ? 1 : 0);
  if (state.sort === "new") rows.reverse();

  document.getElementById("count").textContent = `${{rows.length}} of ${{GAMES.length}} games`;

  const out = document.getElementById("results");
  if (!rows.length) {{
    out.innerHTML = '<div class="empty">No games match.</div>';
    return;
  }}

  let html = "";
  let curDay = null;
  for (const g of rows) {{
    if (g.d !== curDay) {{
      if (curDay !== null) html += "</div>";
      html += `<div class="day"><div class="day-header">${{fmtDate(g.d)}}</div>`;
      curDay = g.d;
    }}
    const aWin = g.as > g.hs, hWin = g.hs > g.as;
    html += `<div class="game">
      <div class="teams">
        <div class="row${{aWin ? " win" : ""}}"><span class="tclass">${{g.ac}}</span><span class="tname">${{escapeHtml(g.a)}}</span><span class="score">${{g.as}}</span></div>
        <div class="row${{hWin ? " win" : ""}}"><span class="tclass">${{g.hc}}</span><span class="tname">${{escapeHtml(g.h)}}</span><span class="score">${{g.hs}}</span></div>
      </div>
      <div class="meta">
        <span class="type-tag type-${{g.t}}">${{g.t}}</span>${{!aWin && !hWin ? '<span class="type-tag type-Tie">Tie</span>' : ""}}
        <span class="league">${{escapeHtml(g.hl || g.al)}}</span>
      </div>
    </div>`;
  }}
  html += "</div>";
  out.innerHTML = html;
}}

render();
</script>

</body>
</html>
"""


if __name__ == "__main__":
    rows = load_games()
    html = PAGE.format(
        generated_date=date.today().strftime("%B %-d, %Y"),
        games_json=json.dumps(rows, separators=(",", ":")),
        n=len(rows),
    )
    with open("scores.html", "w") as f:
        f.write(html)
    print(f"Wrote scores.html ({len(rows)} games)")
