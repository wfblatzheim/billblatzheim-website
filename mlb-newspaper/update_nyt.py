#!/usr/bin/env python3
"""
MLB Box Scores — Old NYT Style
Generates nyt.html from the same cache as update.py, but with a classic
New York Times newspaper aesthetic: blackletter masthead, Old Standard TT
serif throughout, white background, dense column layout.

Usage:
    python3 update_nyt.py        # regenerate nyt.html from cache
"""

import re, os, sys
from datetime import datetime

# Reuse all data-fetching and HTML generation from the main script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from update import load_cache, generate_html

# ── NYT Font import ───────────────────────────────────────────────────────────

NYT_FONTS = '<link href="https://fonts.googleapis.com/css2?family=Old+Standard+TT:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">'

# ── NYT CSS ───────────────────────────────────────────────────────────────────

NYT_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#fff;color:#111;font-family:'Old Standard TT',Georgia,serif;font-size:14px;overflow-x:hidden}
a{color:inherit;text-decoration:none}

/* ── Masthead ── */
.masthead{border-top:6px solid #111;border-bottom:3px double #111;padding:8px 20px 10px;display:flex;justify-content:space-between;align-items:baseline;width:100%}
.masthead-title{font-family:'Old Standard TT',Georgia,serif;font-size:48px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;line-height:1}
.masthead-date{font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#111;font-family:'Old Standard TT',serif}
.masthead-context{font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:#555;text-align:right;font-family:'Old Standard TT',serif;font-style:italic}
.back-link{display:inline-flex;align-items:center;gap:5px;font-family:'Old Standard TT',serif;font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#888;text-decoration:none;transition:color .15s}
.back-link:hover{color:#111}
.back-link-arrow{transition:transform .15s}
.back-link:hover .back-link-arrow{transform:translateX(-2px)}

/* ── Navigation ── */
.arc-months{padding:4px 20px;border-bottom:1px solid #ccc;display:flex;flex-wrap:wrap;gap:2px}
.arc-dates{padding:3px 20px;border-bottom:2px solid #111;display:flex;flex-wrap:wrap;gap:2px}
.mon-btn{cursor:pointer;padding:2px 8px;border:1px solid transparent;background:none;font-family:'Old Standard TT',serif;font-size:13px;font-weight:700;color:#555}
.mon-btn:hover{color:#111;border-color:#aaa}
.mon-btn.active{background:#111;color:#fff;border-color:#111}
.day-btn{cursor:pointer;padding:1px 6px;border:1px solid transparent;background:none;font-family:'Old Standard TT',serif;font-size:12px;color:#555}
.day-btn:hover{color:#111;border-color:#aaa}
.day-btn.active{background:#555;color:#fff;border-color:#555}

/* ── Grid ── */
.grid{column-count:3;column-gap:0;width:100%;border-top:3px solid #111;column-rule:1px solid #bbb}
@media(min-width:1400px){.grid{column-count:4}}
@media(max-width:760px){.grid{column-count:2}}
@media(max-width:480px){.grid{column-count:1}}

/* ── Box score card ── */
.box{break-inside:avoid;display:inline-block;width:100%;border-bottom:1px solid #ccc;padding:10px 12px;font-size:13px;overflow:hidden;box-sizing:border-box}
.box-hdr{font-family:'Old Standard TT',Georgia,serif;font-size:15px;font-weight:700;border-bottom:2px solid #111;padding-bottom:3px;margin-bottom:5px;line-height:1.2}
.box-hdr .final{font-family:'Old Standard TT',serif;font-size:11px;font-weight:400;font-style:italic;color:#666;margin-left:4px}

/* ── Linescore ── */
.ls-text{font-size:13px;line-height:1.8;margin-bottom:4px;white-space:nowrap;font-variant-numeric:tabular-nums;width:100%;font-family:'Old Standard TT',serif}
.ls-line{display:flex;align-items:baseline}
.ls-team{font-weight:700;width:90px;flex-shrink:0;overflow:hidden;text-overflow:ellipsis}
.ls-inn{flex:1;letter-spacing:.05em;text-align:right}
.ls-inn-group{display:inline-block;margin-right:.4em}
.ls-cell{display:inline-block;min-width:.65em;text-align:center}
.ls-rhe{flex-shrink:0;padding-left:.5em;border-left:1px solid #bbb;font-weight:700;letter-spacing:.08em}
.ls-rhe-val{display:inline-block;min-width:1.4em;text-align:right}

/* ── Sections ── */
.section-hdr{width:100%;padding:3px 12px;font-size:9px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#666;border-bottom:1px solid #ccc;display:flex;justify-content:space-between;align-items:center;cursor:pointer;user-select:none;box-sizing:border-box;font-family:'Old Standard TT',serif}
.section-hdr:hover{color:#111}
.section-hdr-arrow{font-size:9px}
.expand-btn{font-family:'Old Standard TT',serif;font-style:italic;font-size:11px;color:#777;cursor:pointer;padding:2px 0;user-select:none;border-top:1px solid #ddd;margin-top:2px}
.expand-btn:hover{color:#111}

/* ── Tables ── */
.tbl-hdr{font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;margin:6px 0 2px;padding-bottom:1px;border-bottom:2px solid #111;font-family:'Old Standard TT',serif}
table.bt,table.pt{border-collapse:collapse;width:100%;font-family:'Old Standard TT',serif;font-size:13px}
table.bt th,table.pt th{text-align:right;padding:0 3px 1px;font-size:9px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;border-bottom:1px solid #bbb}
table.bt td,table.pt td{padding:0 3px;line-height:1.4;text-align:right}
table.bt td:first-child,table.pt td:first-child{text-align:left}
table.bt th:first-child,table.pt th:first-child{text-align:left}
table.bt col:nth-child(2),table.pt col:nth-child(2){width:28px}
table.bt col:nth-child(n+3):nth-child(-n+7),table.pt col:nth-child(n+3):nth-child(-n+7){width:20px}
table.bt col:nth-child(n+8),table.pt col:nth-child(n+8){width:34px}
.bt-sub td:first-child{padding-left:10px;color:#555}
.bt-total{border-top:1px solid #999;font-weight:700}

/* ── Schedule ── */
.sched-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));width:100%;border-left:1px solid #ccc;border-top:2px solid #111}
@media(max-width:1100px){.sched-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:760px){.sched-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:480px){.sched-grid{grid-template-columns:minmax(0,1fr)}}
.sched-card{border-right:1px solid #ccc;border-bottom:1px solid #ccc;padding:9px 11px}
.sched-matchup{font-family:'Old Standard TT',Georgia,serif;font-size:14px;font-weight:700;border-bottom:1px solid #ccc;padding-bottom:3px;margin-bottom:5px}
.sched-time{font-size:12px;color:#555;margin-top:3px;font-style:italic}
.sched-venue{font-size:11px;color:#888;margin-top:2px}
.sched-probables{font-size:11px;color:#555;margin-top:4px;font-family:'Old Standard TT',serif}

/* ── Standings ── */
.standings-wrap{width:100%;border-bottom:2px solid #111}
.standings-inner{display:grid;grid-template-columns:repeat(6,minmax(0,145px));border-left:1px solid #ccc;justify-content:center}
@media(max-width:800px){.standings-inner{grid-template-columns:repeat(3,minmax(0,145px))}}
@media(max-width:500px){
  .standings-inner{grid-template-columns:repeat(2,minmax(0,145px))}
  .standings-div:nth-child(1){order:1}.standings-div:nth-child(2){order:3}.standings-div:nth-child(3){order:5}
  .standings-div:nth-child(4){order:2}.standings-div:nth-child(5){order:4}.standings-div:nth-child(6){order:6}
}
.standings-div{border-right:1px solid #ccc;border-bottom:1px solid #ccc;padding:5px 7px}
.standings-div-name{font-size:9px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#777;margin-bottom:3px;border-bottom:1px solid #ccc;padding-bottom:2px;font-family:'Old Standard TT',serif}
table.st{border-collapse:collapse;width:100%;font-family:'Old Standard TT',serif;font-size:11px}
table.st th{font-size:9px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;text-align:right;padding:0 3px 1px;color:#888}
table.st td{padding:0 3px;line-height:1.45;text-align:right}
table.st td:first-child{text-align:left;max-width:70px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
table.st th:first-child{text-align:left}
table.st col:nth-child(2),table.st col:nth-child(3){width:22px}
table.st col:nth-child(4){width:30px}
table.st col:nth-child(5){width:26px}
.st-leader{font-weight:800}

/* ── Leaders ── */
.leaders-inner{display:grid;grid-template-columns:repeat(8,minmax(0,1fr));border-left:1px solid #ccc;border-bottom:2px solid #111}
@media(max-width:800px){.leaders-inner{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media(max-width:500px){.leaders-inner{grid-template-columns:repeat(2,minmax(0,1fr))}}
.leaders-cat{border-right:1px solid #ccc;border-bottom:1px solid #ccc;padding:5px 7px}
.leaders-cat-name{font-size:9px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#777;margin-bottom:3px;border-bottom:1px solid #ccc;padding-bottom:2px;font-family:'Old Standard TT',serif}
.leaders-row{font-family:'Old Standard TT',serif;font-size:12px;display:flex;justify-content:space-between;align-items:baseline;padding:1px 0;line-height:1.4}
.leaders-row-name{font-weight:400}
.leaders-row-team{color:#888;font-weight:400;font-size:10px;margin-left:3px;font-style:italic}
.leaders-row-val{color:#111;font-size:12px;font-weight:700}

/* ── Scoring plays ── */
.scoring-plays{font-family:'Old Standard TT',serif;font-size:13px;padding:4px 0}
.scoring-play{padding:2px 0;border-bottom:1px solid #eee;line-height:1.4}
.scoring-play:last-child{border-bottom:none}
.sc-inn{font-weight:700;font-size:12px;letter-spacing:.04em;color:#666;margin-right:4px;font-style:italic}
.sc-score{font-weight:700;margin-right:4px}

/* ── Misc ── */
.bulk-controls{width:100%;padding:3px 12px;display:flex;gap:12px;border-bottom:1px solid #ddd;box-sizing:border-box}
.bulk-btn{font-family:'Old Standard TT',serif;font-style:italic;font-size:11px;color:#aaa;cursor:pointer;user-select:none;background:none;border:none;padding:2px 0}
.bulk-btn:hover{color:#111}
.notes{font-size:11px;color:#444;margin-top:5px;line-height:1.5;font-family:'Old Standard TT',serif;font-style:italic}
.meta{font-size:10px;color:#888;margin-top:3px;font-family:'Old Standard TT',serif}
.no-games{padding:60px 20px;text-align:center;font-family:'Old Standard TT',serif;font-size:18px;color:#888;width:100%}
.footer{width:100%;padding:12px 20px;font-size:11px;color:#888;letter-spacing:.06em;border-top:1px solid #ccc;font-family:'Old Standard TT',serif;font-style:italic}
""".strip()

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    cache = load_cache()
    if not cache:
        print("No cache found. Run update.py first to fetch data.")
        sys.exit(1)

    print("Generating nyt.html...")
    html = generate_html(cache, datetime.now().strftime("%b %d, %Y"))

    # Swap font import
    html = re.sub(
        r'<link[^>]+fonts\.googleapis\.com[^>]+>',
        NYT_FONTS,
        html
    )

    # Swap entire <style> block
    html = re.sub(
        r'<style>.*?</style>',
        f'<style>\n{NYT_CSS}\n</style>',
        html,
        flags=re.DOTALL
    )

    # Update page title
    html = html.replace('<title>MLB Box Scores</title>', '<title>MLB Box Scores — The Times</title>')

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nyt.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Done -> nyt.html ({len(html.encode())//1024} KB)")

if __name__ == "__main__":
    main()
