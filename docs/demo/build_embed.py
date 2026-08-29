#!/usr/bin/env python3
"""Build 003-embed.svg: page 3 plus the hooks that make it steerable from CSS
alone — <view> crops, :target isolation rules, per-line/per-word spacing
indices, alternative ayah ornaments, and a <title> on every word.

Reads .cache/words-svg/hafs-kfqc/003.svg and geom.json (measured in a browser
by the demo page). Writes 003-embed.svg. Touches nothing else.
"""
import json, pathlib, re, html

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SRC  = ROOT / ".cache/words-svg/hafs-kfqc/003.svg"
G    = json.loads((HERE / "geom.json").read_text())

PAD    = 4          # margin around every generated crop, in viewBox units
FLIP_A, FLIP_E = 1.3333, -55        # page matrix: x_viewBox = 1.3333*x - 55

svg = SRC.read_text(encoding="utf-8").split("?>", 1)[1].strip()

# ---------------------------------------------------------------- word order
# every word's index within its printed line, and its line number
line_of, k_of, per_line = {}, {}, {}
cur_line = None
for m in re.finditer(r'<g class="line" data-line="(\d+)">|'
                     r'<g class="word" data-surah="\d+" data-ayah="(\d+)" data-word="(\d+)"', svg):
    if m.group(1):
        cur_line = int(m.group(1))
        per_line[cur_line] = 0
    else:
        key = f"{m.group(2)}-{m.group(3)}"
        line_of[key] = cur_line
        k_of[key] = per_line[cur_line]
        per_line[cur_line] += 1

last_word = {}
for key in G["W"]:
    a, w = key.split("-")
    last_word[a] = max(last_word.get(a, 0), int(w))

closes = dict((idx, ayah) for ayah, idx in G["closes"])     # marker index -> ayah

# ------------------------------------------------------------------- rewrite
def line_tag(m):
    n = int(m.group(1))
    kmid = (per_line[n] - 1) / 2
    return (f'<g class="line" data-line="{n}" '
            f'style="--i:{n};--kmid:{kmid:g}">')

svg = re.sub(r'<g class="line" data-line="(\d+)">', line_tag, svg)

def word_tag(m):
    head, a, w, tail = m.group(0), m.group(1), m.group(2), m.group(3)
    key = f"{a}-{w}"
    n = last_word[a]
    ge = " ".join(str(i) for i in range(1, int(w) + 1))     # index >= any of these
    le = " ".join(str(i) for i in range(int(w), n + 1))     # index <= any of these
    text = re.search(r'data-uthmani="([^"]*)"', head).group(1)
    return (head[:-1]
            + f' id="w-{key}" data-ge="{ge}" data-le="{le}"'
            + f' style="--k:{k_of[key]}">'
            + f'<title>{text}</title>')

svg = re.sub(r'<g class="word" data-surah="\d+" data-ayah="(\d+)" data-word="(\d+)"[^>]*(>)',
             word_tag, svg)

idx = -1
def marker_tag(m):
    global idx
    idx += 1
    info = G["M"][idx]
    a = closes.get(idx)
    ln = info["line"]
    cx_vb = FLIP_A * info["cx"] + FLIP_E
    k = sum(1 for key, b in G["W"].items()
            if line_of[key] == ln and b[0] > cx_vb)          # words to its right
    kmid = (per_line[ln] - 1) / 2
    return (m.group(0)[:-1]
            + f' data-closes="{a}" data-line="{ln}"'
            + f' style="--i:{ln};--k:{k};--kmid:{kmid:g}">')

svg = re.sub(r'<g class="ayah-marker" data-surah="\d+" data-ayah="\d+"(>)', marker_tag, svg)

# ornament alternates, dropped in beside the printed one
def ornament_slot(m):
    global oidx
    info = G["M"][oidx]; oidx += 1
    t = f'translate({info["cx"]:g} {info["cy"]:g}) scale({info["r"]:g})'
    uses = "".join(f'<use class="alt alt-{n}" href="#orn-{n}"/>' for n in ALTS)
    return m.group(0) + f'<g class="orn-alt" transform="{t}">{uses}</g>'

ALTS = ["ring", "double", "diamond", "star", "rosette", "brackets"]
oidx = 0
svg = re.sub(r'<g class="ayah-marker"[^>]*>', ornament_slot, svg)

# ------------------------------------------------------------------ defs/css
def scallop(n=8, rb=0.8, lobe=0.34):
    pts = []
    import math
    for i in range(n + 1):
        a = i / n * math.tau
        pts.append((math.cos(a) * rb, math.sin(a) * rb))
    d = f"M {pts[0][0]:.4f} {pts[0][1]:.4f}"
    for x, y in pts[1:]:
        d += f" A {lobe} {lobe} 0 0 1 {x:.4f} {y:.4f}"
    return d + " Z"

DEFS = f'''<defs>
<g id="orn-ring"><circle r="1" fill="none" stroke="currentColor" stroke-width=".11"/></g>
<g id="orn-double"><circle r="1" fill="none" stroke="currentColor" stroke-width=".09"/><circle r=".78" fill="none" stroke="currentColor" stroke-width=".05"/></g>
<g id="orn-diamond"><path d="M 0 -1 L 1 0 L 0 1 L -1 0 Z" fill="none" stroke="currentColor" stroke-width=".11" stroke-linejoin="round"/></g>
<g id="orn-star"><rect x="-.72" y="-.72" width="1.44" height="1.44" fill="none" stroke="currentColor" stroke-width=".09"/><rect x="-.72" y="-.72" width="1.44" height="1.44" fill="none" stroke="currentColor" stroke-width=".09" transform="rotate(45)"/></g>
<g id="orn-rosette"><path d="{scallop()}" fill="none" stroke="currentColor" stroke-width=".08" stroke-linejoin="round"/></g>
<g id="orn-brackets"><path d="M .55 -1 Q 1.05 0 .55 1" fill="none" stroke="currentColor" stroke-width=".13" stroke-linecap="round"/><path d="M -.55 -1 Q -1.05 0 -.55 1" fill="none" stroke="currentColor" stroke-width=".13" stroke-linecap="round"/></g>
</defs>'''

views, iso = [], []
def both(cls, tid, sel):
    """one rule that answers to a root class and to a URL fragment"""
    iso.append(f'svg.{cls} {sel},svg:has(#{tid}:target) {sel}{{display:none}}')

for a, b in G["A"].items():
    views.append(f'<view id="v-ayah-{a}" viewBox="{b[0]-PAD:g} {b[1]-PAD:g} {b[2]+2*PAD:g} {b[3]+2*PAD:g}"/>')
    both(f"only-ayah-{a}", f"v-ayah-{a}", f'g.word:not([data-ayah="{a}"])')
    both(f"only-ayah-{a}", f"v-ayah-{a}", f'g.ayah-marker:not([data-closes="{a}"])')

for n, b in G["L"].items():
    views.append(f'<view id="v-line-{n}" viewBox="{b[0]-PAD:g} {b[1]-PAD:g} {b[2]+2*PAD:g} {b[3]+2*PAD:g}"/>')
    both(f"only-line-{n}", f"v-line-{n}", f'g.line:not([data-line="{n}"])')
    both(f"only-line-{n}", f"v-line-{n}", f'g.ayah-marker:not([data-line="{n}"])')

for key, b in G["W"].items():
    views.append(f'<view id="v-word-{key}" viewBox="{b[0]-PAD:g} {b[1]-PAD:g} {b[2]+2*PAD:g} {b[3]+2*PAD:g}"/>')
    both(f"only-word-{key}", f"v-word-{key}", f'g.word:not(#w-{key})')
    both(f"only-word-{key}", f"v-word-{key}", 'g.ayah-marker')

# the switches are <view>s carrying the page's own viewBox: in an <img> only a
# <view> target sets :target, and this one leaves the framing alone
orn_on = "".join(
    f'<view id="set-{n}" viewBox="0 0 345 550"/>' for n in ALTS)
orn_css = "".join(
    f'svg.orn-{n} .alt-{n},svg:has(#set-{n}:target) .alt-{n}{{display:inline}}'
    f'svg.orn-{n} [data-kind="ayah-marker-ornament"],'
    f'svg:has(#set-{n}:target) [data-kind="ayah-marker-ornament"]{{display:none}}'
    for n in ALTS)

STYLE = f'''<style>
/* --- spacing: one knob each, no script -------------------------------- */
svg {{ overflow: visible; --gap: 0; --wgap: 0; --osize: 1; --mid: 8 }}
g.line   {{ transform: translateY(calc((var(--mid) - var(--i)) * var(--gap) * 1px)) }}
g.word   {{ transform: translateX(calc((var(--kmid) - var(--k)) * var(--wgap) * 1px)) }}
g.ayah-marker {{ transform: translate(calc((var(--kmid) - var(--k)) * var(--wgap) * 1px),
                                      calc((var(--mid) - var(--i)) * var(--gap) * 1px)) }}
/* --- ornaments -------------------------------------------------------- */
.orn-alt {{ color: #231f20 }}
.alt {{ display: none; transform: scale(var(--osize));
       transform-box: fill-box; transform-origin: center }}
{orn_css}

/* --- isolation: same rule answers to a class or to the URL fragment ---- */
{chr(10).join(iso)}
</style>'''

head_end = svg.index(">") + 1
svg = (svg[:head_end] + STYLE + DEFS + "".join(views) + orn_on + svg[head_end:])
svg = svg.replace('<svg ', '<svg id="page3" ', 1)

out = HERE / "003-embed.svg"
out.write_text(svg, encoding="utf-8")
print(f"003-embed.svg  {len(svg)/1024:.0f} KB  "
      f"({len(views)} views, {len(iso)} isolation rules, {len(ALTS)} ornaments)")
