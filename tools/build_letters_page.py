#!/usr/bin/env python3
"""The letter-level review sheet: docs/defects/letters_review.html

    python3 tools/build_letters_page.py [--sample 0.02] [--seed 7] [--limit 400]

Two sections, each a grid of word crops with every letter in its own colour and the
cut chords drawn:

  * FLAGGED — every run the builder could not cut (unsplit in the output) and every
    run with a soft flag, with the flags and a note box;
  * BLIND SAMPLE — a seeded random 2% of ACCEPTED runs whose cuts are DigitalKhatt
    joints (not hand cuts), so the algorithm's output gets judged, not only its
    failures (challenge-all-agent-work).

Decisions come back as data: the Copy button emits JSON [{wid, run, verdict, note}]
for docs/defects/letters_verdicts.jsonl. Nothing here edits code.
"""
import argparse
import glob
import html
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import letters_lib as L          # noqa: E402

OUT = os.path.join(L.ROOT, "docs", "defects", "letters_review.html")
COLS = ["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#42d4f4", "#f032e6", "#9a6324"]


def word_svg(word, letters_word=None, cuts=None, pad=2.0):
    """An inline SVG of the word: letters coloured from the letters build when given,
    else the word's paths in grey; cut chords in black."""
    polys = [poly for p in word["paths"] if p["d"] for poly in L.flatten(p["d"])]
    if not polys:
        return ""
    x0, y0, x1, y1 = L.bbox(polys)
    w, h = x1 - x0 + 2 * pad, y1 - y0 + 2 * pad
    parts = ['<svg viewBox="%.2f %.2f %.2f %.2f" width="%d" height="%d">'
             % (x0 - pad, -(y1 + pad), w, h, int(w * 6), int(h * 6)),
             '<g transform="scale(1 -1)">']
    if letters_word:
        import re
        for k, m in enumerate(re.finditer(r'<g class="letter"([^>]*)>(.*?)</g>', letters_word["inner"], re.S)):
            at = L.parse_attrs(m.group(1))
            col = "#999" if at.get("data-unsplit") == "1" else COLS[int(at.get("data-index", k)) % len(COLS)]
            for pm in re.finditer(r'<path ([^>]*?)/>', m.group(2)):
                pa = L.parse_attrs(pm.group(1))
                parts.append('<path d="%s" fill="%s" fill-rule="evenodd"/>' % (pa.get("d", ""), col))
        rest = re.sub(r'<g class="letter"[^>]*>.*?</g>', "", letters_word["inner"], flags=re.S)
        for pm in re.finditer(r'<path ([^>]*?)/>', rest):
            pa = L.parse_attrs(pm.group(1))
            parts.append('<path d="%s" fill="#666" fill-rule="evenodd"/>' % pa.get("d", ""))
    else:
        for p in word["paths"]:
            parts.append('<path d="%s" fill="#888" fill-rule="evenodd"/>' % p["d"])
    for c in cuts or []:
        pts = " ".join("%.3f,%.3f" % (x, y) for x, y in c["poly"])
        parts.append('<polyline points="%s" fill="none" stroke="#000" stroke-width="0.25"/>' % pts)
    parts.append("</g></svg>")
    return "".join(parts)


def collect_repaired(seed, limit, floor=0.06):
    """A blind sample of the runs where a letter came close to having no ink at all —
    the ones `repair_starved` took back from a neighbour. These are the split's weakest
    cases by construction, so judging them by eye says whether the repair puts the
    letter in the right place, not merely that it gives it one."""
    rnd = random.Random(seed)
    rows = []
    for path in sorted(glob.glob(os.path.join(L.CUTS_DIR, "*.json"))):
        rec = json.load(open(path, encoding="utf-8"))
        for wid, wrec in rec["words"].items():
            if wrec.get("flags"):
                continue
            for ri, run in enumerate(wrec["runs"]):
                if len(run["letters"]) < 2 or run.get("flags"):
                    continue
                sh = run.get("model", {}).get("share") or []
                if sh and min(sh) < floor:
                    rows.append((rec["page"], wid, ri, ["smallest letter %.0f%% of the run" % (100 * min(sh))]))
    rnd.shuffle(rows)
    return [], rows[:limit]


def collect(sample, seed, limit, pairs=None, per=60):
    """Flagged runs and a blind sample of accepted ones; with `pairs`, instead a sample
    of accepted runs containing each listed letter pair (the pairs the hand cuts never
    cover), `per` of each."""
    rnd = random.Random(seed)
    flagged, accepted = [], []
    by_pair = {p: [] for p in (pairs or [])}
    for path in sorted(glob.glob(os.path.join(L.CUTS_DIR, "*.json"))):
        rec = json.load(open(path, encoding="utf-8"))
        page = rec["page"]
        for wid, wrec in rec["words"].items():
            if wrec.get("flags"):
                flagged.append((page, wid, None, wrec["flags"]))
                continue
            for ri, run in enumerate(wrec["runs"]):
                if len(run["letters"]) < 2:
                    continue
                if run.get("flags"):
                    flagged.append((page, wid, ri, run["flags"]))
                    continue
                if pairs:
                    text = run["text"]
                    for pr in pairs:
                        if pr in text:
                            by_pair[pr].append((page, wid, ri, ["pair " + pr]))
                elif any(c["src"] in ("dk", "model") for c in run["cuts"]) and rnd.random() < sample:
                    accepted.append((page, wid, ri, []))
    if pairs:
        for pr, items in by_pair.items():
            rnd.shuffle(items)
            accepted += items[:per]
        return [], accepted
    return flagged[:limit], accepted[:limit]


def letter_strip(letters_word, page, wid):
    """Every letter of the word on its own, in reading order, each in the colour it has
    in the word above and with its own character under it. Clicking one marks that
    letter wrong, so a verdict names the letter rather than the word."""
    if not letters_word:
        return ""
    import re
    cells = []
    for k, m in enumerate(re.finditer(r'<g class="letter"([^>]*)>(.*?)</g>', letters_word["inner"], re.S)):
        at = L.parse_attrs(m.group(1))
        if at.get("data-unsplit") == "1":
            continue
        idx = int(at.get("data-index", k))
        col = COLS[idx % len(COLS)]
        polys, parts = [], []
        for pm in re.finditer(r'<path ([^>]*?)/>', m.group(2)):
            pa = L.parse_attrs(pm.group(1))
            if pa.get("data-kind") == "body" and pa.get("d"):
                polys += L.flatten(pa["d"])
                parts.append('<path d="%s" fill="%s" fill-rule="evenodd"/>' % (pa["d"], col))
        if not polys:
            continue
        x0, y0, x1, y1 = L.bbox(polys)
        pad = 1.0
        w, h = x1 - x0 + 2 * pad, y1 - y0 + 2 * pad
        svg = ('<svg viewBox="%.2f %.2f %.2f %.2f" width="%d" height="%d"><g transform="scale(1 -1)">%s</g></svg>'
               % (x0 - pad, -(y1 + pad), w, h, int(w * 7), int(h * 7), "".join(parts)))
        cells.append('<div class="lt" data-index="%d" data-ch="%s" onclick="markLetter(this)">%s'
                     '<div class="lch" style="color:%s">%s</div></div>'
                     % (idx, html.escape(at.get("data-text", "")), svg, col,
                        html.escape(at.get("data-text", ""))))
    return '<div class="strip">%s</div>' % "".join(cells)


def render(items, title, note):
    cards = []
    cache = {}
    for page, wid, ri, flags in items:
        if page not in cache:
            words, _ = L.read_words(page)
            lw = {}
            lpath = os.path.join(L.LETTERS_SVG, "%03d.svg" % page)
            if os.path.exists(lpath):
                lws, _ = L.read_words(page, L.LETTERS_SVG)
                lw = {w["wid"]: w for w in lws}
            rec = json.load(open(os.path.join(L.CUTS_DIR, "%03d.json" % page), encoding="utf-8"))
            cache[page] = ({w["wid"]: w for w in words}, lw, rec)
        by_w, lw, rec = cache[page]
        word = by_w.get(wid)
        if word is None:
            continue
        runs = rec["words"].get(wid, {}).get("runs", [])
        cuts = [c for r in runs for c in r.get("cuts", [])]
        run_text = runs[ri]["text"] if ri is not None and ri < len(runs) else ""
        cards.append(
            '<div class="card" data-page="%d" data-wid="%s" data-run="%s"><div class="art">%s</div>'
            '<div class="meta"><b>p%d %s</b> <span class="ar">%s</span> <span class="run ar">%s</span>'
            '<div class="flags">%s</div></div>%s'
            '<div class="meta"><select class="verdict"><option value="">—</option>'
            '<option value="ok">cut is right</option>'
            '<option value="wrong">cut is wrong</option><option value="unsure">unsure</option></select> '
            '<input class="note" placeholder="note"></div></div>'
            % (page, wid, "" if ri is None else ri, word_svg(word, lw.get(wid), cuts), page, wid,
               html.escape(word["uthmani"]), html.escape(run_text), html.escape(", ".join(flags)),
               letter_strip(lw.get(wid), page, wid)))
    return '<h2>%s <small>%d</small></h2><p>%s</p><div class="grid">%s</div>' % (title, len(cards), note, "".join(cards))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=float, default=0.02)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--limit", type=int, default=400)
    ap.add_argument("--pairs", help="comma-separated letter pairs to sample instead (e.g. لك,عل)")
    ap.add_argument("--per", type=int, default=60)
    ap.add_argument("--repaired", action="store_true",
                    help="blind sample of runs where a letter was nearly starved (the repair's cases)")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    pairs = a.pairs.split(",") if a.pairs else None
    if a.repaired:
        flagged, accepted = collect_repaired(a.seed, a.limit)
    else:
        flagged, accepted = collect(a.sample, a.seed, a.limit, pairs, a.per)
    body = render(flagged, "Flagged runs", "Runs the builder could not cut, or cut with a doubt. These are unsplit in the output.")
    if a.repaired:
        body = render(accepted, "Runs where a letter was nearly starved",
                      "A blind sample of the runs where the model gave one letter almost none of the ink and "
                      "the repair took its share back from the neighbour holding it. Judge whether each letter "
                      "now holds the right ink.")
    elif pairs:
        body = render(accepted, "Uncovered letter pairs, cut by the model",
                      "Pairs the hand cuts never cover (%s), %d runs each. Judge the cut between those two letters." % (", ".join(pairs), a.per))
    else:
        body += render(accepted, "Blind sample of accepted cuts",
                       "A seeded random %.0f%% of runs cut WITHOUT a hand cut. Judge the cut, not the colours." % (a.sample * 100))
    page = ("<!doctype html><meta charset=utf-8><title>Letter cuts — review</title>"
            "<style>body{font-family:system-ui;margin:20px;background:#fafafa}"
            ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}"
            ".card{background:#fff;border:1px solid #ddd;border-radius:6px;padding:8px}"
            ".art svg{max-width:100%;height:auto}.ar{font-size:22px;direction:rtl}.run{color:#36c}"
            ".flags{color:#b00;font-size:12px;margin:4px 0}.note{width:60%}"
            ".strip{display:flex;direction:rtl;gap:6px;align-items:flex-end;overflow-x:auto;"
            "border-top:1px dashed #ddd;border-bottom:1px dashed #ddd;padding:6px 0;margin:6px 0}"
            ".lt{text-align:center;cursor:pointer;padding:2px;border:2px solid transparent;border-radius:4px}"
            ".lt:hover{background:#f2f2f2}.lt.bad{border-color:#b00;background:#fff0f0}"
            ".lt svg{display:block}.lch{font-size:20px;direction:rtl}"
            "button{position:fixed;top:10px;right:10px;padding:8px 14px}</style>"
            "<button onclick='copyAll()'>Copy decisions</button><h1>Letter cuts</h1>" + body +
            "<script>function markLetter(el){el.classList.toggle('bad');const c=el.closest('.card');"
            "if(c.querySelectorAll('.lt.bad').length&&!c.querySelector('.verdict').value)"
            "c.querySelector('.verdict').value='wrong';}"
            "function copyAll(){const out=[];document.querySelectorAll('.card').forEach(c=>{"
            "const v=c.querySelector('.verdict').value,n=c.querySelector('.note').value;"
            "const bad=[...c.querySelectorAll('.lt.bad')].map(e=>({index:+e.dataset.index,letter:e.dataset.ch}));"
            "if(v||n||bad.length)out.push({page:+c.dataset.page,wid:c.dataset.wid,run:c.dataset.run,"
            "verdict:v||(bad.length?'wrong':''),wrong:bad,note:n})});"
            "navigator.clipboard.writeText(out.map(o=>JSON.stringify(o)).join('\\n'));alert(out.length+' decisions copied')}</script>")
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(page)
    print("%s: %d flagged, %d sampled" % (a.out, len(flagged), len(accepted)))


if __name__ == "__main__":
    main()
