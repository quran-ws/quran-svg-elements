#!/usr/bin/env python3
"""A page for drawing letter cuts by hand: docs/defects/letters_label.html

    python3 tools/build_letters_label_page.py --pairs "لك,عل,لح,كل,فل,كف,ته,فس,كت,بم" --per 40

For each sampled run the word is drawn large; click two points to draw a cut line
across the stroke (the first click starts a line, the second ends it), one line per
joint you want to give, right to left. Drag nothing; a wrong line is removed with
its ✕. "Copy" exports JSON lines {page, wid, run, text, cuts: [[[x,y],[x,y]]…]} in the
page-path coordinate system — the same units as the tajweed hand cuts — for
docs/defects/letters_hand_cuts.jsonl, which build_letter_labels.py reads as extra
hand cuts. Nothing here edits code.
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

OUT = os.path.join(L.ROOT, "docs", "defects", "letters_label.html")


PALE = ["#f4a3b5", "#a9dbb0", "#a8b8ec", "#f9c89a", "#c9a0d6", "#a5e8f8", "#f6a4f0", "#d9c3a0"]


def word_svg(word, run_eids, pad=2.0, scale=10, letters_word=None):
    """The word, the run to cut in dark grey; with `letters_word` (the model build's
    version) the model's letters are shown in pale colours under it as a hint."""
    polys = [poly for p in word["paths"] if p["d"] and p["kind"] == "body" for poly in L.flatten(p["d"])]
    if not polys:
        return "", None
    x0, y0, x1, y1 = L.bbox(polys)
    w, h = x1 - x0 + 2 * pad, y1 - y0 + 2 * pad
    parts = ['<svg class="art" data-x0="%.3f" data-y1="%.3f" data-w="%.3f" data-h="%.3f" viewBox="0 0 %.2f %.2f" width="%d" height="%d">'
             % (x0 - pad, y1 + pad, w, h, w, h, int(w * scale), int(h * scale))]
    # page-path y is UP: flip inside the group, so screen (sx, sy) ↔ page (x0-pad+sx, y1+pad-sy)
    parts.append('<g transform="translate(%.3f %.3f) scale(1 -1)">' % (-(x0 - pad), y1 + pad))
    shown = set()
    if letters_word:
        import re
        for k, m in enumerate(re.finditer(r'<g class="letter"([^>]*)>(.*?)</g>', letters_word["inner"], re.S)):
            at = L.parse_attrs(m.group(1))
            if at.get("data-unsplit") == "1":
                continue
            col = PALE[int(at.get("data-index", k)) % len(PALE)]
            for pm in re.finditer(r'<path ([^>]*?)/>', m.group(2)):
                pa = L.parse_attrs(pm.group(1))
                if pa.get("data-kind") == "body" and pa.get("d"):
                    base = pa.get("data-eid", "").rsplit("-", 1)[0] if pa.get("data-cut") == "1" else pa.get("data-eid")
                    if base in run_eids:
                        parts.append('<path d="%s" fill="%s" fill-rule="evenodd"/>' % (pa["d"], col))
                        shown.add(base)
    for p in word["paths"]:
        if p["kind"] != "body" or not p["d"]:
            continue
        if p["eid"] in shown:
            continue
        col = "#222" if p["eid"] in run_eids else "#bbb"
        parts.append('<path d="%s" fill="%s" fill-rule="evenodd"/>' % (p["d"], col))
    parts.append('</g><g class="lines"></g></svg>')
    return "".join(parts), (x0 - pad, y1 + pad)


def pair_coverage(pairs):
    """Per pair: joints in the mushaf, joints the tajweed layers cut, joints drawn by
    hand — read from the label masks (a joint is covered when both letters have
    single-bit pixels), so the ranking is measured, not kept by hand."""
    import numpy as np
    from tools.build_letter_labels import LABELS_DIR
    allp, cov, drawn = {}, {}, {}
    for f in sorted(glob.glob(os.path.join(LABELS_DIR, "*.npz"))):
        z = np.load(f)
        meta = json.loads(str(z["meta"]))
        mask = z["mask"]
        for smp, m in zip(meta, mask):
            t = smp["text"]
            if len(t) != smp["n"]:
                continue
            single = m[(m & (m - 1)) == 0]
            bits = {int(np.log2(b)) for b in np.unique(single[single > 0])}
            for i in range(len(t) - 1):
                pr = t[i:i + 2]
                if pr not in pairs:
                    continue
                allp[pr] = allp.get(pr, 0) + 1
                if smp.get("drawn"):
                    drawn[pr] = drawn.get(pr, 0) + 1
                elif i in bits and i + 1 in bits:
                    cov[pr] = cov.get(pr, 0) + 1
    return {pr: (allp.get(pr, 0), cov.get(pr, 0), drawn.get(pr, 0)) for pr in pairs}


def collect(pairs, per, seed, words=()):
    """`words` are (page, wid) asked for by name; they come first, marked "redo"."""
    rnd = random.Random(seed)
    by_pair = {p: [] for p in pairs}
    named = []
    for path in sorted(glob.glob(os.path.join(L.CUTS_DIR, "*.json"))):
        rec = json.load(open(path, encoding="utf-8"))
        for wid, wrec in rec["words"].items():
            for ri, run in enumerate(wrec["runs"]):
                if len(run["letters"]) < 2:
                    continue
                if (rec["page"], wid) in words:
                    named.append(("redo",) + (rec["page"], wid, ri, run["text"], run.get("eid", [])))
                for pr in pairs:
                    if pr in run["text"]:
                        by_pair[pr].append((rec["page"], wid, ri, run["text"], run.get("eid", []), bool(run.get("flags"))))
    out = list(named)
    for pr, items in by_pair.items():
        rnd.shuffle(items)
        items.sort(key=lambda it: not it[-1])             # runs the builder could not cut first
        out += [(pr,) + it[:-1] for it in items[:per]]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default="لك,عل,لح,كل,فل,كف,ته,فس,كت,بم")
    ap.add_argument("--per", type=int, default=40)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--words", default="", help="page:wid,... to show first (a drawing to redo)")
    ap.add_argument("--rank", action="store_true", help="order pairs by uncut joints, with a heading per pair")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    words = {(int(w.split(":")[0]), w.split(":", 1)[1]) for w in a.words.split(",") if w}
    pairs = [p for p in a.pairs.split(",") if p]
    stats = pair_coverage(pairs) if a.rank else {}
    if a.rank:                                             # most uncut joints first
        pairs.sort(key=lambda pr: -(stats[pr][0] - stats[pr][1] - stats[pr][2]))
    items = collect(pairs, a.per, a.seed, words)
    cards = []
    cache = {}
    last = None
    for pr, page, wid, ri, text, eids in items:
        if a.rank and pr != last:
            if pr == "redo":
                cards.append('<h2 class="sec">Redo</h2>')
            else:
                n, c, d = stats[pr]
                cards.append('<h2 class="sec"><span class="ar">%s</span> — %d joints in the mushaf, %d cut by the tajweed layers, %d drawn</h2>'
                             % (pr, n, c, d))
            last = pr
        if page not in cache:
            words, _ = L.read_words(page)
            lw = {}
            lpath = os.path.join(L.LETTERS_SVG, "%03d.svg" % page)
            if os.path.exists(lpath):
                lws, _ = L.read_words(page, L.LETTERS_SVG)
                lw = {w["wid"]: w for w in lws}
            cache[page] = ({w["wid"]: w for w in words}, lw)
        word = cache[page][0].get(wid)
        if word is None:
            continue
        svg, _ = word_svg(word, set(eids), letters_word=cache[page][1].get(wid))
        if not svg:
            continue
        cards.append('<div class="card" data-page="%d" data-wid="%s" data-run="%d" data-text="%s">%s'
                     '<div class="meta"><b>%s</b> p%d %s <span class="ar">%s</span> run <span class="ar">%s</span>'
                     ' <span class="count">0 cuts</span></div><div class="cutlist"></div></div>'
                     % (page, wid, ri, html.escape(text), svg, pr, page, wid, html.escape(word["uthmani"]), html.escape(text)))
    page = ("<!doctype html><meta charset=utf-8><title>Letter cuts — draw</title>"
            "<style>body{font-family:system-ui;margin:20px;background:#fafafa}"
            ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:14px}"
            ".card{background:#fff;border:1px solid #ddd;border-radius:6px;padding:8px}"
            "svg.art{max-width:100%;height:auto;cursor:crosshair;background:#fff}"
            ".ar{font-size:22px;direction:rtl}.meta{font-size:13px;margin-top:4px}.cutlist span{margin-right:8px;font-size:12px}"
            ".cutlist button{font-size:11px}button.copy{position:fixed;top:10px;right:10px;padding:8px 14px}"
            "h2.sec{grid-column:1/-1;margin:18px 0 4px;font-size:18px;border-bottom:1px solid #ccc}</style>"
            "<button class=copy onclick='copyAll()'>Copy cuts</button>"
            "<h1>Draw the letter cuts</h1><p>Dark grey is the run to cut; pale colours are the model's current guess, one per letter. Click two points to draw one cut line across the stroke, "
            "one line per joint, from right to left. ✕ removes a line. Then Copy and paste into "
            "<code>docs/defects/letters_hand_cuts.jsonl</code>.</p>"
            "<div class=grid>" + "".join(cards) + "</div>"
            "<script>"
            "document.querySelectorAll('svg.art').forEach(svg=>{let pending=null;"
            "svg.addEventListener('click',e=>{const r=svg.getBoundingClientRect();const vb=svg.viewBox.baseVal;"
            "const sx=(e.clientX-r.left)/r.width*vb.width, sy=(e.clientY-r.top)/r.height*vb.height;"
            "if(!pending){pending=[sx,sy];return;}const a=pending;pending=null;"
            "const ln=document.createElementNS('http://www.w3.org/2000/svg','line');"
            "ln.setAttribute('x1',a[0]);ln.setAttribute('y1',a[1]);ln.setAttribute('x2',sx);ln.setAttribute('y2',sy);"
            "ln.setAttribute('stroke','#e00');ln.setAttribute('stroke-width','0.35');svg.querySelector('.lines').appendChild(ln);"
            "const card=svg.closest('.card');const x0=+svg.dataset.x0,y1=+svg.dataset.y1;"
            "const cut=[[x0+a[0],y1-a[1]],[x0+sx,y1-sy]];"
            "const item=document.createElement('span');item.textContent='cut';const b=document.createElement('button');b.textContent='✕';"
            "b.onclick=()=>{ln.remove();item.remove();update(card)};item.appendChild(b);item.dataset.cut=JSON.stringify(cut);"
            "card.querySelector('.cutlist').appendChild(item);update(card);});});"
            "function update(card){const n=card.querySelectorAll('.cutlist span').length;card.querySelector('.count').textContent=n+' cuts';}"
            "function copyAll(){const out=[];document.querySelectorAll('.card').forEach(c=>{const cuts=[...c.querySelectorAll('.cutlist span')].map(s=>JSON.parse(s.dataset.cut));"
            "if(cuts.length)out.push({page:+c.dataset.page,wid:c.dataset.wid,run:+c.dataset.run,text:c.dataset.text,cuts});});"
            "navigator.clipboard.writeText(out.map(o=>JSON.stringify(o)).join('\\n'));alert(out.length+' words copied');}"
            "</script>")
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(page)
    print("%s: %d cards" % (a.out, len(cards)))


if __name__ == "__main__":
    main()
