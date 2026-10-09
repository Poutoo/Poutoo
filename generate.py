"""
Génère la carte stellaire du README : assets/sky-dark.svg et assets/sky-light.svg.

Pour ajouter un projet : ajoute une entrée dans PROJECTS, puis relance
    python generate.py
Les étoiles de fond sont tirées avec une graine fixe : la carte reste
identique d'une génération à l'autre tant que tu ne changes pas SEED.

Éclat des étoiles : pour chaque projet qui a un champ "repo", le script lit
la date du dernier push via l'API GitHub. Plus le repo a bougé récemment,
plus l'étoile brille. L'activité est rangée en 4 paliers pour que le SVG
ne change (et ne soit commité) que quand un projet change de palier.

    python generate.py            # interroge l'API (GITHUB_TOKEN optionnel en local)
    python generate.py --offline  # éclat par défaut, sans réseau
"""

import json
import math
import os
import random
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

W, H = 1000, 420
SEED = 107
OUT = Path(__file__).parent / "assets"

# --- Projets ---------------------------------------------------------------
# x, y       : position sur la carte (viewBox 1000 x 420)
# r          : rayon de l'étoile (= importance du projet)
# label      : "left" ou "right", côté où s'affiche le texte
# designation: désignation de Bayer de la vraie étoile (laisser "" si aucune)
# repo       : "owner/nom" sur GitHub, sert à calculer l'éclat (optionnel)
# ghost      : True = projet à venir (étoile en pointillés)
PROJECTS = [
    dict(name="Canopus", designation="α Carinae", repo="Poutoo/Canopus", x=455, y=285, r=9,
         desc=["Windows game optimizer", "WinUI 3, .NET 8, work in progress"],
         label="left", tint="warm"),
    dict(name="Vega", designation="α Lyrae", repo="Poutoo/Vega", x=745, y=130, r=7.5,
         desc=["Universal CLI video", "and music downloader"],
         label="right", tint="cool"),
    dict(name="Next star", designation="", x=890, y=320, r=5,
         desc=["Being charted"], label="left", ghost=True),
]

# Tracés de la constellation : paires d'index dans PROJECTS
LINKS = [(0, 1), (1, 2)]

THEMES = {
    "dark": dict(
        bg="#0d1117",            # = fond GitHub sombre, la carte s'y fond
        grid="#8aa4d6", grid_op=0.10,
        field="#dbe4ff",
        line="#c9d6f2", line_op=0.55,
        title="#f2f4fa", text="#c3cbe0", muted="#7d89a6",
        accent="#F76060",
        warm="#ffe7c2", cool="#cfe0ff", ghost="#7d89a6",
        glow=True,
    ),
    "light": dict(
        bg="#ffffff",            # = fond GitHub clair
        grid="#1d3461", grid_op=0.12,
        field="#1d3461",
        line="#1d3461", line_op=0.6,
        title="#13213f", text="#2c3d63", muted="#6b7894",
        accent="#d64545",
        warm="#13213f", cool="#13213f", ghost="#8a95ad",
        glow=False,
    ),
}

SERIF = "Georgia, 'Times New Roman', serif"
SANS = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"


# --- Activité des repos -------------------------------------------------------
# palier : (jours max depuis le dernier push, libellé de la légende)
LEVELS = [(None, "dormant"), (120, "quiet"), (30, "this month"), (7, "this week")]
DEFAULT_LEVEL = 2  # projets sans repo, ou mode --offline


def level_from_days(days):
    for lvl in range(len(LEVELS) - 1, 0, -1):
        if days <= LEVELS[lvl][0]:
            return lvl
    return 0


def fetch_levels(strict):
    """Renvoie {index_projet: palier}. En CI (strict), une erreur fait échouer
    le job : mieux vaut ne rien commiter qu'une carte éteinte à tort."""
    token = os.environ.get("GITHUB_TOKEN")
    now = datetime.now(timezone.utc)
    levels = {}
    for i, p in enumerate(PROJECTS):
        if not p.get("repo"):
            continue
        req = urllib.request.Request(
            f"https://api.github.com/repos/{p['repo']}",
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": "poutoo-star-chart",
                     **({"Authorization": f"Bearer {token}"} if token else {})})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.load(r)
            pushed = datetime.fromisoformat(data["pushed_at"].replace("Z", "+00:00"))
            days = (now - pushed).days
            levels[i] = level_from_days(days)
            print(f"{p['repo']}: dernier push il y a {days} j -> palier {levels[i]}")
        except Exception as e:
            if strict:
                sys.exit(f"Impossible de lire {p['repo']} : {e}")
            print(f"{p['repo']}: API indisponible ({e}), palier par défaut")
    return levels


# --- Étoiles de fond ---------------------------------------------------------
def field_stars():
    rng = random.Random(SEED)
    # zones à garder lisibles : titre + textes des projets
    keep_out = [(30, 30, 330, 150), (30, 362, 400, 410)]  # titre, légende
    for p in PROJECTS:
        if p["label"] == "left":
            keep_out.append((p["x"] - 260, p["y"] - 50, p["x"] + 20, p["y"] + 60))
        else:
            keep_out.append((p["x"] - 20, p["y"] - 50, p["x"] + 240, p["y"] + 60))

    stars = []
    while len(stars) < 170:
        x, y = rng.uniform(8, W - 8), rng.uniform(8, H - 8)
        if any(a <= x <= c and b <= y <= d for a, b, c, d in keep_out):
            continue
        if any(math.hypot(x - p["x"], y - p["y"]) < 30 for p in PROJECTS):
            continue
        # magnitude : beaucoup de petites étoiles, peu de brillantes
        mag = rng.random() ** 3
        r = 0.45 + mag * 1.9
        op = 0.25 + mag * 0.6 + rng.uniform(0, 0.15)
        twinkle = rng.random() < 0.22
        stars.append((x, y, r, min(op, 0.95), twinkle, rng.randint(0, 2)))
    return stars


# --- Grille de coordonnées (façon atlas céleste) -------------------------------
def grid(t):
    cx, cy = 520, 1500  # centre hors cadre : arcs de déclinaison
    parts = []
    for i, rad in enumerate(range(1120, 1520, 80)):
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{rad}" />')
    for ang in range(-30, 31, 10):  # lignes d'ascension droite
        a = math.radians(ang - 90)
        x2, y2 = cx + 1600 * math.cos(a), cy + 1600 * math.sin(a)
        parts.append(f'<line x1="{cx}" y1="{cy}" x2="{x2:.1f}" y2="{y2:.1f}" />')
    lines = "\n    ".join(parts)
    return (f'<g fill="none" stroke="{t["grid"]}" stroke-opacity="{t["grid_op"]}" '
            f'stroke-width="1">\n    {lines}\n  </g>')


def link_path(a, b):
    # on arrête le trait avant l'étoile pour ne pas la recouvrir
    dx, dy = b["x"] - a["x"], b["y"] - a["y"]
    d = math.hypot(dx, dy)
    ux, uy = dx / d, dy / d
    ga, gb = a["r"] + 9, b["r"] + 9
    x1, y1 = a["x"] + ux * ga, a["y"] + uy * ga
    x2, y2 = b["x"] - ux * gb, b["y"] - uy * gb
    return x1, y1, x2, y2, d - ga - gb


# effet de chaque palier : (échelle du noyau, opacité du halo)
LEVEL_FX = [(0.45, 0.0), (0.6, 0.15), (0.8, 0.35), (1.0, 0.7)]

def star_svg(p, t, i, lvl):
    x, y = p["x"], p["y"]
    if p.get("ghost"):
        return (f'<circle cx="{x}" cy="{y}" r="{p["r"] + 3}" fill="none" stroke="{t["ghost"]}" '
                f'stroke-width="1.2" stroke-dasharray="2 3" class="pulse" />')
    scale, _ = LEVEL_FX[lvl]
    r = round(p["r"] * scale, 2)
    color = t[p.get("tint", "cool")]
    out = []
    if t["glow"]:
        if lvl >= 1:  # pas de halo pour un projet dormant
            out.append(f'<circle cx="{x}" cy="{y}" r="{p["r"] * (2 + lvl * 1.1)}" fill="url(#glow-{i})" '
                       f'class="breathe d{i % 3}" />')
        if lvl == 3:
            s = r * 3.1
            out.append(f'<path d="M{x - s} {y}H{x + s}M{x} {y - s}V{y + s}" stroke="{color}" '
                       f'stroke-opacity="0.45" stroke-width="0.8" />')
    elif lvl == 3:
        out.append(f'<circle cx="{x}" cy="{y}" r="{r + 4}" fill="none" stroke="{color}" stroke-width="0.8" />')
    out.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}" />')  # noyau de l'étoile
    return "\n    ".join(out)


def legend_svg(t):
    """Légende façon atlas : l'éclat d'une étoile = activité récente."""
    x0, y = 50, 392
    parts = [f'<text x="{x0}" y="{y + 4}" font-family="{SANS}" font-size="12" '
             f'fill="{t["muted"]}">Last push</text>']
    x = x0 + 70
    for lvl in range(len(LEVELS) - 1, -1, -1):
        r = round(5 * LEVEL_FX[lvl][0], 2)
        parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{t["text"]}" />')
        parts.append(f'<text x="{x + 10}" y="{y + 4}" font-family="{SANS}" font-size="12" '
                     f'fill="{t["muted"]}">{LEVELS[lvl][1]}</text>')
        x += 22 + len(LEVELS[lvl][1]) * 6.4
    return "\n    ".join(parts)


def label_svg(p, t):
    left = p["label"] == "left"
    anchor = "end" if left else "start"
    off = p["r"] + 18
    x = p["x"] - off if left else p["x"] + off
    y = p["y"] + 7  # ligne de base du nom, alignée sur le centre de l'étoile
    ghost = p.get("ghost")
    rows = []
    if p["designation"]:
        rows.append(f'<text x="{x}" y="{y - 24}" text-anchor="{anchor}" font-family="{SERIF}" '
                    f'font-size="13" fill="{t["muted"]}">{p["designation"]}</text>')
    rows.append(f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="{SERIF}" '
                f'font-style="{"normal" if ghost else "italic"}" font-size="22" '
                f'fill="{t["muted"] if ghost else t["title"]}">{p["name"]}</text>')
    for k, line in enumerate(p["desc"]):
        rows.append(f'<text x="{x}" y="{y + 22 + k * 18}" text-anchor="{anchor}" '
                    f'font-family="{SANS}" font-size="13" fill="{t["text"]}">{line}</text>')
    return "\n    ".join(rows)


def build(theme, levels):
    t = THEMES[theme]
    lv = [levels.get(i, DEFAULT_LEVEL) for i in range(len(PROJECTS))]
    stars = field_stars()

    field = []
    for x, y, r, op, tw, d in stars:
        cls = f' class="twinkle d{d}"' if tw else ""
        field.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}" '
                     f'fill-opacity="{op:.2f}"{cls} />')

    links = []
    for n, (ia, ib) in enumerate(LINKS):
        a, b = PROJECTS[ia], PROJECTS[ib]
        x1, y1, x2, y2, length = link_path(a, b)
        dashed = b.get("ghost") or a.get("ghost")
        if dashed:
            links.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                         f'stroke-dasharray="3 6" class="fadein" style="animation-delay:{1.6 + n * 0.4}s" />')
        else:
            links.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                         f'stroke-dasharray="{length:.1f}" stroke-dashoffset="{length:.1f}" '
                         f'class="draw" style="animation-delay:{0.3 + n * 0.5}s" />')

    main = "\n    ".join(star_svg(p, t, i, lv[i]) for i, p in enumerate(PROJECTS))
    labels = "\n    ".join(label_svg(p, t) for p in PROJECTS)

    glow_defs = ""
    if t["glow"]:
        for i, p in enumerate(PROJECTS):
            if p.get("ghost"):
                continue
            c, op = t[p.get("tint", "cool")], LEVEL_FX[lv[i]][1]
            glow_defs += (f'<radialGradient id="glow-{i}"><stop offset="0" stop-color="{c}" stop-opacity="{op}"/>'
                          f'<stop offset="0.35" stop-color="{c}" stop-opacity="{op * 0.22:.3f}"/>'
                          f'<stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>')

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="title desc">
  <title id="title">Poutoo, star chart of projects</title>
  <desc id="desc">A constellation where each star is one of Poutoo's projects: Canopus and Vega.</desc>
  <defs>{glow_defs}</defs>
  <style>
    .twinkle {{ animation: twinkle 4s ease-in-out infinite; }}
    .breathe {{ animation: breathe 5s ease-in-out infinite; transform-box: fill-box; transform-origin: center; }}
    .pulse {{ animation: twinkle 3s ease-in-out infinite; }}
    .d1 {{ animation-delay: 1.3s; animation-duration: 5.2s; }}
    .d2 {{ animation-delay: 2.6s; animation-duration: 3.4s; }}
    .draw {{ animation: draw 1.4s ease-out forwards; }}
    .fadein {{ opacity: 0; animation: fadein 1s ease-out forwards; }}
    @keyframes twinkle {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.25; }} }}
    @keyframes breathe {{ 0%, 100% {{ transform: scale(1); }} 50% {{ transform: scale(0.82); }} }}
    @keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}
    @keyframes fadein {{ to {{ opacity: 1; }} }}
    @media (prefers-reduced-motion: reduce) {{
      .twinkle, .breathe, .pulse {{ animation: none; }}
      .draw {{ animation: none; stroke-dashoffset: 0; }}
      .fadein {{ animation: none; opacity: 1; }}
    }}
  </style>

  <rect width="100%" height="100%" fill="{t["bg"]}" />
  {grid(t)}

  <g fill="{t["field"]}">
    {chr(10).join("    " + s for s in field).lstrip()}
  </g>

  <g stroke="{t["line"]}" stroke-opacity="{t["line_op"]}" stroke-width="1.2" fill="none">
    {chr(10).join("    " + l for l in links).lstrip()}
  </g>

  <g>
    {main}
  </g>

  <g>
    {labels}
  </g>

  <g>
    <text x="48" y="92" font-family="{SERIF}" font-style="italic" font-size="52" fill="{t["title"]}">Poutoo</text>
    <text x="50" y="122" font-family="{SANS}" font-size="14" fill="{t["text"]}">Full-stack developer and designer.</text>
    <text x="50" y="142" font-family="{SANS}" font-size="14" fill="{t["muted"]}">Each star is a project I built.</text>
  </g>

  <g>
    {legend_svg(t)}
  </g>
</svg>
'''


if __name__ == "__main__":
    offline = "--offline" in sys.argv
    strict = os.environ.get("GITHUB_ACTIONS") == "true"
    levels = {} if offline else fetch_levels(strict)
    OUT.mkdir(exist_ok=True)
    for theme in THEMES:
        (OUT / f"sky-{theme}.svg").write_text(build(theme, levels), encoding="utf-8")
        print(f"assets/sky-{theme}.svg")
