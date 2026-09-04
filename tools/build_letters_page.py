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


def collect(sample, seed, limit):
    rnd = random.Random(seed)
    flagged, accepted = [], []
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
                elif any(c["src"] == "dk" for c in run["cuts"]) and rnd.random() < sample:
                    accepted.append((page, wid, ri, []))
    return flagged[:limit], accepted[:limit]


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
            '<div class="card" data-wid="%s" data-run="%s"><div class="art">%s</div>'
            '<div class="meta"><b>p%d %s</b> <span class="ar">%s</span> <span class="run ar">%s</span>'
            '<div class="flags">%s</div>'
            '<select class="verdict"><option value="">—</option><option value="ok">cut is right</option>'
            '<option value="wrong">cut is wrong</option><option value="unsure">unsure</option></select> '
            '<input class="note" placeholder="note"></div></div>'
            % (wid, "" if ri is None else ri, word_svg(word, lw.get(wid), cuts), page, wid,
               html.escape(word["uthmani"]), html.escape(run_text), html.escape(", ".join(flags))))
    return '<h2>%s <small>%d</small></h2><p>%s</p><div class="grid">%s</div>' % (title, len(cards), note, "".join(cards))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=float, default=0.02)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--limit", type=int, default=400)
    a = ap.parse_args()
    flagged, accepted = collect(a.sample, a.seed, a.limit)
    body = render(flagged, "Flagged runs", "Runs the builder could not cut, or cut with a doubt. These are unsplit in the output.")
    body += render(accepted, "Blind sample of accepted DigitalKhatt cuts",
                   "A seeded random %.0f%% of runs cut WITHOUT a hand cut. Judge the cut, not the colours." % (a.sample * 100))
    page = ("<!doctype html><meta charset=utf-8><title>Letter cuts — review</title>"
            "<style>body{font-family:system-ui;margin:20px;background:#fafafa}"
            ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}"
            ".card{background:#fff;border:1px solid #ddd;border-radius:6px;padding:8px}"
            ".art svg{max-width:100%;height:auto}.ar{font-size:22px;direction:rtl}.run{color:#36c}"
            ".flags{color:#b00;font-size:12px;margin:4px 0}.note{width:60%}"
            "button{position:fixed;top:10px;right:10px;padding:8px 14px}</style>"
            "<button onclick='copyAll()'>Copy decisions</button><h1>Letter cuts</h1>" + body +
            "<script>function copyAll(){const out=[];document.querySelectorAll('.card').forEach(c=>{"
            "const v=c.querySelector('.verdict').value,n=c.querySelector('.note').value;"
            "if(v||n)out.push({wid:c.dataset.wid,run:c.dataset.run,verdict:v,note:n})});"
            "navigator.clipboard.writeText(out.map(o=>JSON.stringify(o)).join('\\n'));alert(out.length+' decisions copied')}</script>")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print("%s: %d flagged, %d sampled" % (OUT, len(flagged), len(accepted)))


if __name__ == "__main__":
    main()
