#!/usr/bin/env python3
"""
Neofetch-style GitHub profile card.

Fetches your GitHub stats through the GraphQL API and renders two SVGs
(dark_mode.svg, light_mode.svg) that README.md shows depending on the
viewer's theme. Runs daily via .github/workflows/build.yml.

Edit the CONFIG section below, then push. Everything else is automatic.
"""
import datetime as dt
import html
import json
import os
import sys
import time
from pathlib import Path

import requests
from dateutil.relativedelta import relativedelta

# ───────────────────────────── CONFIG ─────────────────────────────
USER = "azrainnn"          # <- your GitHub username
BIRTHDAY = dt.date(2004, 8, 10)        # powers the "Uptime" line
HEADER = "azrain shawn!"

INFO = [  # (key, value). None = blank line. ("#", "Title") = section rule.
    ("OS", "Windows 11, Raspberry Pi OS, Ubuntu"),
    ("Uptime", "{uptime}"),
    ("Host", "Universiti Teknologi PETRONAS"),
    ("Kernel", "B.CS (Hons.) Data Analytics"),
    ("IDE", "VS Code, Antigravity, Jupyter"),
    None,
    ("Languages.Programming", "Python, C++, C#, JavaScript, SQL"),
    ("Languages.Computer", "HTML, CSS, JSON, YAML"),
    ("Languages.Real", "English, Malay"),
    None,
    ("Hobbies.Software", "AI/ML, Cloud, Data Viz, Automation"),
    ("Hobbies.Hardware", "PC Building, Raspberry Pi"),
    ("Hobbies.Analog", "Running, Specialty Coffee"),
    ("#", "Projects"),
    ("FYP", "BirdSense - bird calls on RPi 5"),
    ("Optimizer", "AeroEvolve - GA flight scheduler"),
    ("#", "Contact"),
    ("Email", "you@example.com"),
    ("LinkedIn", "linkedin.com/in/azrainshawn"),
]

WIDTH = 60          # characters per info line
FONT_SIZE = 16
LINE_H = 20
CHAR_W = 10.2       # widest common monospace advance at 16px (Consolas is ~8.8)
ART_X, GAP = 15, 30

THEMES = {
    # deep rainforest + hornbill-casque amber
    "dark":  dict(bg="#0f1a14", text="#c8d3c5", key="#e8a33d", value="#9fd4ae",
                  dots="#3b5246", add="#5fd07d", dele="#ef6f6c",
                  # portrait shades, darkest pixels (hair, eyes) first
                  art=["#2b4738", "#3e5f4c", "#628b72", "#9fc6aa"],
                  # used when ascii_colors.txt exists: one letter per character
                  colors=dict(k="#55625b", h="#7d8a83", w="#e9efe9", a="#f5b13d", c="#e5532f",
                              b="#eadfb4", e="#ef6f6c", p="#0f1a14", r="#8c6a4c")),
    "light": dict(bg="#f4f7f2", text="#24302a", key="#a5520a", value="#1d6b3c",
                  dots="#b7c4bb", add="#1a7f37", dele="#c9302c",
                  art=["#14241b", "#2c4a38", "#5f8570", "#a3bcab"],
                  colors=dict(k="#1d2522", h="#4d5953", w="#97a39c", a="#d98a12", c="#c63b1c",
                              b="#b39a55", e="#c9302c", p="#f4f7f2", r="#8a6446")),
}
# ──────────────────────────────────────────────────────────────────

API = "https://api.github.com/graphql"
ROOT = Path(__file__).parent
CACHE = ROOT / "cache" / "loc.json"
TOKEN = os.environ.get("ACCESS_TOKEN") or os.environ.get("GITHUB_TOKEN")


def gql(query, **variables):
    for attempt in range(4):
        r = requests.post(API, json={"query": query, "variables": variables},
                          headers={"Authorization": f"bearer {TOKEN}"}, timeout=60)
        if r.status_code == 200 and "errors" not in r.json():
            return r.json()["data"]
        if r.status_code in (502, 503) or "timeout" in r.text.lower():
            time.sleep(2 ** attempt)
            continue
        sys.exit(f"GraphQL error {r.status_code}: {r.text[:500]}")
    sys.exit("GraphQL kept failing; try again later.")


def user_overview():
    q = """query($login:String!){ user(login:$login){
        id followers{totalCount}
        owned: repositories(ownerAffiliations:OWNER){totalCount}
        all: repositories(ownerAffiliations:[OWNER,COLLABORATOR,ORGANIZATION_MEMBER]){totalCount}
    }}"""
    return gql(q, login=USER)["user"]


def all_repos(affiliations):
    q = """query($login:String!,$aff:[RepositoryAffiliation],$cursor:String){
      user(login:$login){ repositories(first:100, after:$cursor, ownerAffiliations:$aff){
        pageInfo{hasNextPage endCursor}
        nodes{ nameWithOwner stargazerCount isFork
               owner{login}
               defaultBranchRef{ target{ ... on Commit{ oid } } } }
    }}}"""
    cursor, out = None, []
    while True:
        page = gql(q, login=USER, aff=affiliations, cursor=cursor)["user"]["repositories"]
        out += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return out
        cursor = page["pageInfo"]["endCursor"]


def repo_loc(name_with_owner, author_id):
    """Sum additions/deletions of every commit you authored on the default branch."""
    owner, name = name_with_owner.split("/")
    q = """query($owner:String!,$name:String!,$id:ID!,$cursor:String){
      repository(owner:$owner,name:$name){ defaultBranchRef{ target{ ... on Commit{
        history(first:100, after:$cursor, author:{id:$id}){
                   pageInfo{hasNextPage endCursor} nodes{ additions deletions } } } } } } }"""
    cursor, add, dele, commits = None, 0, 0, 0
    while True:
        repo = gql(q, owner=owner, name=name, id=author_id, cursor=cursor)["repository"]
        ref = repo and repo["defaultBranchRef"]
        if not ref:
            return dict(add=0, dele=0, commits=0)
        h = ref["target"]["history"]
        for n in h["nodes"]:
            add, dele, commits = add + n["additions"], dele + n["deletions"], commits + 1
        if not h["pageInfo"]["hasNextPage"]:
            return dict(add=add, dele=dele, commits=commits)
        cursor = h["pageInfo"]["endCursor"]


def collect_stats():
    me = user_overview()
    repos = all_repos(["OWNER", "COLLABORATOR", "ORGANIZATION_MEMBER"])
    stars = sum(r["stargazerCount"] for r in repos if r["owner"]["login"].lower() == USER.lower())

    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    fresh = {}
    for r in repos:
        ref = r["defaultBranchRef"]
        head = ref["target"]["oid"] if ref else None
        key = r["nameWithOwner"]
        if key in cache and cache[key]["head"] == head:
            fresh[key] = cache[key]                      # unchanged → reuse
        else:
            print(f"  counting {key}")
            fresh[key] = dict(head=head, **(repo_loc(key, me["id"]) if head else
                                            dict(add=0, dele=0, commits=0)))
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(fresh, indent=1, sort_keys=True))

    add = sum(v["add"] for v in fresh.values())
    dele = sum(v["dele"] for v in fresh.values())
    return dict(repos=me["owned"]["totalCount"], contrib=me["all"]["totalCount"],
                stars=stars, followers=me["followers"]["totalCount"],
                commits=sum(v["commits"] for v in fresh.values()),
                add=add, dele=dele, loc=add - dele)


def uptime(today=None):
    d = relativedelta(today or dt.date.today(), BIRTHDAY)
    plural = lambda n, w: f"{n} {w}{'' if n == 1 else 's'}"
    return f"{plural(d.years, 'year')}, {plural(d.months, 'month')}, {plural(d.days, 'day')}"


# ───────────────────────────── rendering ─────────────────────────────
def seg(text, cls=None):
    return (text, cls)


def field(key, value, width, bullet=True):
    """'. Key: ....... value' padded with dots to exactly `width` chars."""
    value, lead = str(value), (". " if bullet else "")
    n = max(1, width - len(lead) - len(key) - 1 - len(value) - 2)
    return [seg(lead), seg(key, "key"), seg(":"),
            seg(" " + "." * n + " ", "dots"), seg(value, "value")]


def rule(title):
    left = f"- {title} "
    return [seg(left), seg("-" * (WIDTH - len(left)), "dots")]


def build_lines(s):
    fmt = lambda n: f"{n:,}"
    lines = [[seg(HEADER, "key"), seg(" "), seg("-" * (WIDTH - len(HEADER) - 1), "dots")]]
    for item in INFO:
        if item is None:
            lines.append([])
        elif item[0] == "#":
            if lines[-1]:
                lines.append([])          # breathing room above each section
            lines.append(rule(item[1]))
        else:
            lines.append(field(item[0], item[1].format(uptime=uptime()), WIDTH))
    lines += [[], rule("GitHub Stats")]
    left, right = 35, WIDTH - 35 - 3      # two columns joined by " | "
    lines.append(field("Repos", f"{fmt(s['repos'])} {{Contributed: {fmt(s['contrib'])}}}", left)
                 + [seg(" | ")] + field("Stars", fmt(s["stars"]), right, bullet=False))
    lines.append(field("Commits", fmt(s["commits"]), left)
                 + [seg(" | ")] + field("Followers", fmt(s["followers"]), right, bullet=False))
    loc_tail = [seg(" ( "), seg(f"{fmt(s['add'])}++", "add"), seg(", "),
                seg(f"{fmt(s['dele'])}--", "dele"), seg(" )")]
    tail_len = sum(len(t) for t, _ in loc_tail)
    lines.append(field("Lines of Code on GitHub", fmt(s["loc"]), WIDTH - tail_len) + loc_tail)
    return lines


ART_RAMP = " .:-=+*#%@"   # same light->dark ramp make_ascii.py uses


def shade_row(row, palette):
    """Colour each character by how dark the pixel behind it was."""
    out, run, cur = [], "", None
    for ch in row:
        lvl = ART_RAMP.find(ch)
        idx = cur if ch == " " else (len(palette) - 1 - min(len(palette) - 1,
                                     max(0, lvl - 1) * len(palette) // (len(ART_RAMP) - 1)))
        if idx != cur and run:
            out.append(f'<tspan fill="{palette[cur]}">{html.escape(run)}</tspan>' if cur is not None
                       else html.escape(run))
            run = ""
        cur, run = idx, run + ch
    if run:
        out.append(f'<tspan fill="{palette[cur]}">{html.escape(run)}</tspan>' if cur is not None
                   else html.escape(run))
    return "".join(out)


def color_row(row, codes, colors):
    """Colour each character from the matching letter in ascii_colors.txt."""
    out, run, cur = [], "", None
    for i, ch in enumerate(row):
        code = codes[i] if i < len(codes) and codes[i] in colors else None
        if code != cur and run:
            out.append(f'<tspan fill="{colors[cur]}">{html.escape(run)}</tspan>' if cur else html.escape(run))
            run = ""
        cur, run = code, run + ch
    if run:
        out.append(f'<tspan fill="{colors[cur]}">{html.escape(run)}</tspan>' if cur else html.escape(run))
    return "".join(out)


def render(theme, lines, art, codes=None):
    c = THEMES[theme]
    INFO_X = int(ART_X + max(map(len, art)) * CHAR_W + GAP)
    height = max(len(lines), len(art)) * LINE_H + 40
    width = int(INFO_X + WIDTH * CHAR_W + 25)
    art_top = 30 + (len(lines) - len(art)) * LINE_H // 2
    out = [f'<?xml version="1.0" encoding="utf-8"?>',
           f'<svg xmlns="http://www.w3.org/2000/svg" xml:space="preserve" '
           f'font-family="Consolas, Menlo, \'DejaVu Sans Mono\', \'Courier New\', monospace" '
           f'width="{width}px" height="{height}px" font-size="{FONT_SIZE}px">',
           "<style>",
           f".key{{fill:{c['key']}}} .value{{fill:{c['value']}}} .dots{{fill:{c['dots']}}}",
           f".add{{fill:{c['add']}}} .dele{{fill:{c['dele']}}} text,tspan{{white-space:pre}}",
           "</style>",
           f'<rect width="{width}px" height="{height}px" fill="{c["bg"]}" rx="15"/>',
           f'<text x="{ART_X}" y="{art_top}">']
    for i, row in enumerate(art):
        out.append(f'<tspan x="{ART_X}" y="{art_top + i * LINE_H}">{color_row(row, codes[i], c["colors"]) if codes else shade_row(row, c["art"])}</tspan>')
    out.append("</text>")
    out.append(f'<text x="{INFO_X}" y="30" fill="{c["text"]}">')
    for i, line in enumerate(lines):
        parts = "".join(f'<tspan class="{cls}">{html.escape(t)}</tspan>' if cls else html.escape(t)
                        for t, cls in line)
        out.append(f'<tspan x="{INFO_X}" y="{30 + i * LINE_H}">{parts}</tspan>')
    out.append("</text></svg>")
    return "\n".join(out)


def main():
    demo = "--demo" in sys.argv
    if demo:
        stats = dict(repos=18, contrib=24, stars=37, followers=52,
                     commits=1234, add=98765, dele=43210, loc=55555)
    else:
        if not TOKEN:
            sys.exit("Set ACCESS_TOKEN (a GitHub personal access token).")
        if USER == "your-github-username":
            sys.exit("Edit USER at the top of today.py first.")
        t = time.perf_counter()
        stats = collect_stats()
        print(f"Fetched stats in {time.perf_counter() - t:.1f}s: {stats}")
    art = (ROOT / "ascii_art.txt").read_text().rstrip("\n").split("\n")
    cfile = ROOT / "ascii_colors.txt"          # optional; delete it to use plain shading
    codes = cfile.read_text().rstrip("\n").split("\n") if cfile.exists() else None
    if codes:
        codes += [""] * (len(art) - len(codes))
    lines = build_lines(stats)
    for theme in THEMES:
        (ROOT / f"{theme}_mode.svg").write_text(render(theme, lines, art, codes), encoding="utf-8")
    print("Wrote dark_mode.svg and light_mode.svg")


if __name__ == "__main__":
    main()
