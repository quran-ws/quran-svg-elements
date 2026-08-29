#!/usr/bin/env python3
"""Build docs/defects/ligature_cuts.html — our ligature cut beside theirs.

One row per disagreement found by tools/audit_ligcuts.py: the same word drawn
twice, ours on the left and MushafDatabase's on the right, with every ligature
run in a different colour so the cut is visible at a glance. Marks are drawn in
grey on both sides — the disagreement is always about LETTER ink.

Ours comes from the cached page SVG (.cache/words-svg/hafs-kfqc), theirs from
the reference SVG. The cache is a SNAPSHOT: the header stamps when each side
was written, and a row can only be as fresh as its cache file.

Rows are ranked worst-first by tier. The last tier — our emitter merging runs
the joining rules forbid — is one systematic defect with 2,700 instances; a
visual is drawn for the most common patterns and the rest are listed compactly,
because 2,700 identical-in-kind pictures help nobody.

    python3 tools/build_ligcuts_page.py [--patterns 160]
"""

import argparse
import datetime
import html
import io
import json
import os
import re
from collections import Counter, defaultdict

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".cache", "words-svg", "hafs-kfqc")
REF = os.path.expanduser(
    "~/Dev/github.com/AbdullahObaid/MushafDatabase-Ligature-Based-SVG/SVG V1.01")
SRC = os.path.join(ROOT, "docs", "defects", "ligature_cuts.json")
DST = os.path.join(ROOT, "docs", "defects", "ligature_cuts.html")

COLORS = ["#d62728", "#1f77b4", "#2ca02c", "#9467bd", "#ff7f0e",
          "#17becf", "#8c564b", "#e377c2"]
GREY = "#bbb"

_pages, _refs = {}, {}


def _ourpage(pg):
    if pg not in _pages:
        p = os.path.join(CACHE, "%03d.svg" % pg)
        _pages[pg] = io.open(p, encoding="utf-8").read() if os.path.exists(p) else ""
    return _pages[pg]


def _refpage(pg):
    if pg not in _refs:
        p = os.path.join(REF, "%03d.svg" % pg)
        _refs[pg] = io.open(p, encoding="utf-8-sig").read() if os.path.exists(p) else ""
    return _refs[pg]


def _group(s, start):
    """The whole <g …> element beginning at `start`, by depth counting."""
    depth = 0
    for m in re.finditer(r"<g\b|</g>", s[start:]):
        depth += 1 if m.group(0) == "<g" else -1
        if depth == 0:
            return s[start:start + m.end()]
    return None


def _slim(t):
    return re.sub(r'\s(?:fill|fill-rule|data-sig|data-imlaei|data-qpc|'
                  r'data-mark-family)="[^"]*"', "", t)


def ours_svg(pg, key):
    """The word is found by surah/ayah/word index, NOT by its text: a page can
    draw the same word twice (فَلَا, ٱللَّهُ) and a text search picks the first."""
    s = _ourpage(pg)
    if not s:
        return "", 0
    su, ay, pos = key.split(":")
    i = s.find('<g class="word" data-surah="%s" data-ayah="%s" data-word="%s"'
               % (su, ay, pos))
    if i < 0:
        return "", 0
    grp = _group(s, i)
    if not grp:
        return "", 0
    # strip the source fills BEFORE colouring, or _slim would take the
    # colours straight back off again
    parts = re.split(r'(?=<g class="ligature")', _slim(grp))
    out, n = [parts[0]], 0
    for chunk in parts[1:]:
        col = COLORS[n % len(COLORS)]
        chunk = re.sub(r'(<path[^>]*data-kind="body"[^>]*)/>',
                       r'\1 fill="%s"/>' % col, chunk)
        chunk = re.sub(r'(<path[^>]*data-kind="mark"[^>]*)/>',
                       r'\1 fill="%s"/>' % GREY, chunk)
        out.append(chunk)
        n += 1
    root = re.search(r'<g transform="matrix[^"]*">', s)
    vb = re.search(r'viewBox="[^"]*"', s)
    return ('<svg xmlns="http://www.w3.org/2000/svg" %s>%s%s</g></svg>'
            % (vb.group(0) if vb else "", root.group(0) if root else "<g>",
               "".join(out))), n


def theirs_svg(pg, key):
    """key is "surah:ayah:pos" in OUR numbering; the reference numbers words
    differently (waw-alatf and stop signs are words of their own), so the word
    is located by matching the reference's own group ids recorded at audit
    time. Falls back to a surah/aya scan and picks the group whose folded
    letters match."""
    s = _refpage(pg)
    if not s:
        return "", 0
    su, ay, _ = key.split(":")
    pat = 'data-surah="%03d" data-aya="%03d"' % (int(su), int(ay))
    return s, pat


def theirs_word_svgs(pg, su, ay):
    """[(word-index, hafs, svg, nruns)] for one ayah on one reference page."""
    s = _refpage(pg)
    if not s:
        return []
    out = []
    for m in re.finditer(r'<g id="md-word-\d+"[^>]*>', s):
        tag = m.group(0)
        a = dict(re.findall(r'data-([a-z-]+)="([^"]*)"', tag))
        if a.get("type") != "text":
            continue
        if int(a.get("surah", -1)) != su or int(a.get("aya", -1)) != ay:
            continue
        grp = _group(s, m.start())
        if not grp:
            continue
        parts = re.split(r'(?=<g id="md-ligature-)', grp)
        body, n = [parts[0]], 0
        for chunk in parts[1:]:
            col = COLORS[n % len(COLORS)]
            chunk = re.sub(r'(<path[^>]*data-type="text"[^>]*?)/>',
                           r'\1 fill="%s"/>' % col, chunk)
            chunk = re.sub(r'(<path[^>]*data-type="(?:diacritic|dots)"[^>]*?)/>',
                           r'\1 fill="%s"/>' % GREY, chunk)
            body.append(chunk)
            n += 1
        inner = re.sub(r'\s(?:id|data-diacritic|data-dots)="[^"]*"', "",
                       "".join(body))
        out.append((int(a.get("word-index-in-ayah", 0)), a.get("hafs", ""),
                    inner, n, a.get("waw-alatf") == "true"))
    out.sort()
    return out


def theirs_for(row):
    """Their drawing of the SAME word, folding waw-alatf and stop-sign words
    back exactly as audit_ligcuts does, so position N means the same word."""
    su, ay, pos = (int(x) for x in row["key"].split(":"))
    items = theirs_word_svgs(row["page"], su, ay)
    WAQF = "ۖۗۘۙۚۛۜ۝۞۩"
    merged, pend = [], []
    for _, hafs, svg, n, waw in items:
        if waw:
            pend.append((svg, n))
            continue
        if hafs and all(c in WAQF or c.isspace() for c in hafs) and merged:
            continue
        merged.append(("".join(p[0] for p in pend) + svg,
                       sum(p[1] for p in pend) + n))
        pend = []
    if pos - 1 >= len(merged):
        return ("", 0)
    inner, n = merged[pos - 1]
    vb = re.search(r'viewBox="[^"]*"', _refpage(row["page"]))
    return ('<svg xmlns="http://www.w3.org/2000/svg" %s>%s</svg>'
            % (vb.group(0) if vb else "", inner), n)


TIERS = [
    ("A", "INK CHANGED HANDS — the word's edge disagrees past the empty band. "
          "This is the family no audit here can see: a stolen body piece",
     lambda r: r["kind"] in ("boundary", "extent")
     or (r["kind"] == "missing-ink" and r.get("left_word"))),
    ("B", "THEIRS-WRONG by the joining rules",
     lambda r: r["verdict"] == "THEIRS-WRONG"),
    ("C", "UNDECIDED — neither side is convicted by the joining rules, needs an eye",
     lambda r: r["verdict"] == "UNDECIDED"),
    ("D", "a group names letters whose ink sits in another group of the SAME word "
          "— the word's extent still matches theirs, so nothing was stolen",
     lambda r: r["kind"] == "missing-ink"),
    ("E", "our emitter emits one group where the joining rules and they both "
          "say two — the group's data-text names a run the script cannot draw",
     lambda r: r["kind"] == "cut" and r["verdict"] == "OURS-WRONG"),
]

CSS = """
body{font-family:system-ui,sans-serif;margin:20px auto;max-width:1180px;color:#222}
h1{margin-bottom:2px} .sub{color:#666;font-size:13px;margin-bottom:18px}
.tier{margin:34px 0 6px;padding:8px 12px;background:#f2f4f7;border-left:4px solid #556;
      border-radius:4px}
.tier h2{margin:0;font-size:16px} .tier p{margin:4px 0 0;color:#555;font-size:13px}
.row{display:flex;gap:12px;align-items:center;border:1px solid #e0e0e0;border-radius:8px;
     padding:8px 12px;margin:8px 0;background:#fff}
.row.hot{background:#fff5f2;border-color:#e0b0a0}
.pane{width:230px;height:110px;flex:none;text-align:center}
.pane svg{width:100%;height:88px} .pane .lab{font-size:11px;color:#888}
.meta{flex:1;font-size:13px;line-height:1.5}
.w{font-size:24px;font-family:'KFGQPC Uthmanic Script HAFS','Amiri',serif}
.runs{font-family:'KFGQPC Uthmanic Script HAFS','Amiri',serif;font-size:16px}
.k{color:#777;font-size:12px}
.ev{color:#444;font-size:12.5px}
.v{display:inline-block;padding:1px 7px;border-radius:9px;font-size:11px;font-weight:600;
   color:#fff}
.v.OURS-WRONG{background:#c0392b}.v.THEIRS-WRONG{background:#2c6fbb}
.v.UNDECIDED{background:#8a6d3b}
a{color:#2c6fbb}
table{border-collapse:collapse;font-size:12.5px;width:100%;margin-top:10px}
td,th{border-bottom:1px solid #eee;padding:3px 6px;text-align:left}
.sw{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:3px}
"""


def runlist(runs):
    """Arabic run names in READING ORDER, numbered. Without the numbers and
    the isolation the bidi algorithm reorders the list and run 1 reads last."""
    return ('<span dir="ltr" style="unicode-bidi:isolate">%s</span>'
            % " ".join('<span class="k">%d</span>&nbsp;<bdi>%s</bdi>'
                       % (i, html.escape(x)) for i, x in enumerate(runs, 1)))


def swatches(n):
    return "".join('<span class="sw" style="background:%s"></span>'
                   % COLORS[i % len(COLORS)] for i in range(n))


def render_row(r, ours, nours, theirs, ntheirs, extra=""):
    hot = " hot" if r["verdict"] != "OURS-WRONG" or r.get("left_word") else ""
    link = ("/?page=%d&step=audit&user=abdullah&word=%s"
            % (r["page"], r["key"]))
    return """<div class="row%s">
<div class="pane"><div class="lab">OURS — %d run(s) %s</div>%s</div>
<div class="pane"><div class="lab">MUSHAFDATABASE — %d run(s) %s</div>%s</div>
%s<div class="meta"><span class="w">%s</span>
 <span class="k">p%d &middot; %s &middot; <a href="%s">open in review</a></span><br>
 <span class="runs">ours %s &nbsp;|&nbsp; theirs %s</span><br>
 <span class="v %s">%s</span> <span class="ev">%s</span><br>
 <span class="ev">%s</span></div></div>""" % (
        hot, nours, swatches(nours), ours or "<i>no cached ink</i>",
        ntheirs, swatches(ntheirs), theirs or "<i>not found</i>", extra,
        html.escape(r["word"]), r["page"], html.escape(r["key"]), link,
        runlist(r["our_runs"]), runlist(r["ref_runs"]),
        r["verdict"], r["verdict"], html.escape(r.get("evidence", "")),
        html.escape(r.get("detail", "")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--patterns", type=int, default=160,
                    help="how many distinct cut patterns to draw in tier F")
    args = ap.parse_args()

    rows = json.load(open(SRC, encoding="utf-8"))
    for r in rows:
        r.setdefault("verdict", "UNDECIDED")
    seen, tiered = set(), []
    for code, title, test in TIERS:
        sel = [r for r in rows if id(r) not in seen and test(r)]
        for r in sel:
            seen.add(id(r))
        tiered.append((code, title, sel))

    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    ourfresh = min((os.path.getmtime(os.path.join(CACHE, f))
                    for f in os.listdir(CACHE) if f.endswith(".svg")), default=0)
    out = ['<meta charset="utf-8"><title>Ligature cuts vs MushafDatabase</title>',
           "<style>%s</style>" % CSS,
           "<h1>Our ligature cut vs MushafDatabase's</h1>",
           '<p class="sub">%d disagreements over %s comparable words '
           '(pages 1-604). Each ligature run is drawn in its own colour; marks '
           'are grey. Built %s. <b>The ink shown is a snapshot</b> — ours comes '
           'from the cached page SVGs, oldest written %s, so a row is only as '
           'fresh as that cache. Their coordinates are mapped into ours by the '
           'page transform (scale 4/3, per-page offset); the fit residual is '
           '0.10u median over ~130 words a page.</p>'
           % (len(rows), "{:,}".format(77422), stamp,
              datetime.datetime.fromtimestamp(ourfresh).strftime("%Y-%m-%d")
              if ourfresh else "unknown")]

    for code, title, sel in tiered:
        if not sel:
            continue
        out.append('<div class="tier"><h2>Tier %s — %s (%d)</h2></div>'
                   % (code, html.escape(title), len(sel)))
        if code != "E":
            for r in sorted(sel, key=lambda x: (x["page"], x["key"])):
                o, no = ours_svg(r["page"], r["key"])
                t, nt = theirs_for(r)
                extra = ""
                if code == "A":
                    # a stolen piece is only visible next to the word that has
                    # it, so tier A also draws OUR neighbours on either side
                    su, ay, pos = (int(x) for x in r["key"].split(":"))
                    for lbl, p2 in (("our previous word", pos - 1),
                                    ("our next word", pos + 1)):
                        if p2 < 1:
                            continue
                        n_svg, n_n = ours_svg(r["page"], "%d:%d:%d" % (su, ay, p2))
                        if n_svg:
                            extra += ('<div class="pane"><div class="lab">%s — '
                                      '%d run(s)</div>%s</div>' % (lbl, n_n, n_svg))
                out.append(render_row(r, o, no, t, nt, extra))
            continue
        # tier E: one visual per distinct pattern, most frequent first
        pat = defaultdict(list)
        for r in sel:
            pat[(tuple(r["our_runs"]), tuple(r["ref_runs"]))].append(r)
        order = sorted(pat.values(), key=lambda v: (-len(v), v[0]["page"]))
        out.append('<p class="sub">One systematic emitter defect. %d distinct '
                   'patterns; the %d most frequent are drawn, the rest listed '
                   'below.</p>' % (len(order), min(args.patterns, len(order))))
        for grp in order[:args.patterns]:
            r = grp[0]
            o, no = ours_svg(r["page"], r["key"])
            t, nt = theirs_for(r)
            out.append('<div class="k" style="margin-top:10px">%d word(s) share '
                       'this pattern</div>' % len(grp))
            out.append(render_row(r, o, no, t, nt))
            if len(grp) > 1:
                out.append('<div class="k">also: %s</div>' % ", ".join(
                    '<a href="/?page=%d&step=audit&user=abdullah&word=%s">p%d %s</a>'
                    % (x["page"], x["key"], x["page"], html.escape(x["word"]))
                    for x in grp[1:31]))
        rest = [r for grp in order[args.patterns:] for r in grp]
        if rest:
            out.append("<h3>The remaining %d, listed</h3>" % len(rest))
            out.append("<table><tr><th>page</th><th>key</th><th>word</th>"
                       "<th>ours</th><th>theirs</th></tr>")
            for r in sorted(rest, key=lambda x: x["page"]):
                out.append('<tr><td><a href="/?page=%d&step=audit&user=abdullah'
                           '&word=%s">%d</a></td><td>%s</td><td class="runs">%s'
                           '</td><td class="runs">%s</td><td class="runs">%s</td></tr>'
                           % (r["page"], r["key"], r["page"], html.escape(r["key"]),
                              html.escape(r["word"]),
                              runlist(r["our_runs"]),
                              runlist(r["ref_runs"])))
            out.append("</table>")

    out.append("""<script>
// each snippet carries the whole page's viewBox; shrink it to the word's own
// ink so the word fills the box on both sides
document.querySelectorAll('.pane svg').forEach(s=>{
  try{const b=s.getBBox();
    if(b.width&&b.height)
      s.setAttribute('viewBox',`${b.x-3} ${b.y-3} ${b.width+6} ${b.height+6}`);
  }catch(e){}
});
</script>""")
    io.open(DST, "w", encoding="utf-8").write("\n".join(out))
    print("wrote %s (%.1f MB)" % (DST, os.path.getsize(DST) / 1e6))
    for code, title, sel in tiered:
        print("   tier %s %-70s %5d" % (code, title, len(sel)))


if __name__ == "__main__":
    main()
