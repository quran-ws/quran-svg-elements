#!/usr/bin/env python3
"""The shapes the split produced, for a human to mark the good ones.

    python3 tools/build_letter_shapes_page.py --cover 0.8    # → docs/defects/letter_shapes.html

`tools/letter_shapes.py` reduces the 322,746 emitted letters to 10,143 shapes. They are
very unevenly used: the top 58 shapes are half of every letter drawn in the mushaf, the
top 315 are 80%, and 5,418 shapes occur exactly once. So a page of a few hundred cards,
ordered by how many words each shape stands for, buys most of the corpus.

Each card is one shape, drawn from a middling instance of its cluster, under the letter
and the position it takes in its run. Every card starts RIGHT, because most of them are:
the reviewer's work is to click the wrong ones, not to confirm hundreds of good ones.
Copy emits one line per shape with its id and verdict, so a verdict can be applied to
every word that draws it — the same way `labels.json` carries one decision per mark
signature across the whole mushaf.
"""
import argparse
import hashlib
import html
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import letters_lib as L          # noqa: E402

SHAPES = os.path.join(L.ROOT, ".cache", "letters",
                      "shapes" + ("-" + L.BUILD_TAG if L.BUILD_TAG else "") + ".json")
OUT = os.path.join(L.ROOT, "docs", "defects", "letter_shapes.html")
FORMS = ["first", "middle", "last", "only"]
FORM_AR = {"first": "أول الكلمة", "middle": "وسط", "last": "آخر", "only": "منفرد"}


def shape_id(ex):
    return hashlib.sha1(("|".join(ex["d"])).encode("utf-8")).hexdigest()[:12]


def card(c, scale=9):
    polys = [poly for d in c["example"]["d"] for poly in L.flatten(d)]
    if not polys:
        return ""
    x0, y0, x1, y1 = L.bbox(polys)
    pad = 1.0
    w, h = x1 - x0 + 2 * pad, y1 - y0 + 2 * pad
    parts = ['<svg viewBox="%.2f %.2f %.2f %.2f" width="%d" height="%d"><g transform="scale(1 -1)">'
             % (x0 - pad, -(y1 + pad), w, h, int(w * scale), int(h * scale))]
    for d in c["example"]["d"]:
        parts.append('<path d="%s" fill="#222" fill-rule="evenodd"/>' % d)
    parts.append("</g></svg>")
    ex = c["example"]
    return ('<div data-id="%s" data-ch="%s" data-form="%s" data-n="%d" '
            'data-page="%d" data-wid="%s" data-index="%d" onclick="mark(this)" class="sh good" '
            'title="p%d %s letter %d">%s<div class="cnt">%s</div></div>'
            % (shape_id(ex), html.escape(c["ch"]), c["form"], c["n"], ex["page"], ex["wid"],
               ex["index"], ex["page"], ex["wid"], ex["index"], "".join(parts),
               "{:,}".format(c["n"])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cover", type=float, default=0.8,
                    help="show the most-used shapes covering this fraction of all letters")
    ap.add_argument("--limit", type=int, default=0, help="hard cap on cards (0 = none)")
    ap.add_argument("--letter", help="only this letter")
    ap.add_argument("--shapes", default=SHAPES)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    clusters = json.load(open(a.shapes, encoding="utf-8"))
    if a.letter:
        clusters = [c for c in clusters if c["ch"] == a.letter]
    total = sum(c["n"] for c in clusters)
    ranked = sorted(clusters, key=lambda c: -c["n"])
    keep, run = [], 0
    for c in ranked:
        keep.append(c)
        run += c["n"]
        if run >= a.cover * total or (a.limit and len(keep) >= a.limit):
            break
    by_letter = defaultdict(lambda: defaultdict(list))
    for c in keep:
        by_letter[c["ch"]][c["form"]].append(c)
    order = sorted(by_letter, key=lambda ch: -sum(x["n"] for f in by_letter[ch].values() for x in f))
    body = []
    for ch in order:
        n_ch = sum(x["n"] for f in by_letter[ch].values() for x in f)
        body.append('<h2 class="sec"><span class="ar">%s</span> <small>%s letters, %d shapes</small></h2>'
                    % (html.escape(ch), "{:,}".format(n_ch),
                       sum(len(v) for v in by_letter[ch].values())))
        for form in FORMS:
            cs = sorted(by_letter[ch].get(form, []), key=lambda c: -c["n"])
            if not cs:
                continue
            body.append('<h3 class="frm">%s <span class="ar">%s</span> <small>%s letters</small></h3>'
                        % (form, FORM_AR[form], "{:,}".format(sum(c["n"] for c in cs))))
            body.append('<div class="row">%s</div>' % "".join(card(c) for c in cs))
    page = ("<!doctype html><meta charset=utf-8><title>Letter shapes — mark the good ones</title>"
            "<style>body{font-family:system-ui;margin:20px;background:#fafafa}"
            "h2.sec{border-bottom:2px solid #333;margin:26px 0 4px;font-size:20px}"
            "h3.frm{margin:12px 0 4px;font-size:14px;color:#555;font-weight:600}"
            ".ar{font-size:26px;direction:rtl}small{color:#777;font-weight:400;font-size:12px}"
            ".row{display:flex;flex-wrap:wrap;gap:8px;direction:rtl}"
            ".sh{background:#fff;border:2px solid #ddd;border-radius:6px;padding:4px;cursor:pointer;text-align:center}"
            ".sh:hover{border-color:#333}.sh.good{border-color:#2a7;background:#f2fff8}"
            ".sh.bad{border-color:#b00;background:#fff2f2}"
            ".sh svg{display:block;max-height:70px;width:auto}"
            ".cnt{font-size:11px;color:#666}"
            "button{position:fixed;top:10px;right:10px;padding:8px 14px;z-index:9}"
            "#tally{position:fixed;top:10px;right:150px;padding:8px 12px;background:#fff;"
            "border:1px solid #ccc;border-radius:6px;font-size:13px;z-index:9}</style>"
            "<button onclick='copyAll()'>Copy verdicts</button><div id=tally>0 wrong</div>"
            "<h1>Letter shapes</h1>"
            "<p>Every shape the split produced, one card per shape, with the number of words that "
            "draw it. <b>Everything starts marked right — click a shape to mark it wrong, click again "
            "to put it back.</b> "
            "The shapes are ordered by how much of the mushaf they carry, so the first few cards of "
            "each letter are worth far more than the last. Then press Copy and paste the lines back.</p>"
            + "".join(body) +
            "<script>"
            "function mark(el){const s=el.classList;"
            "if(s.contains('good')){s.remove('good');s.add('bad')}else{s.remove('bad');s.add('good')}tally();}"
            "function tally(){const b=document.querySelectorAll('.sh.bad').length;"
            "const t=document.querySelectorAll('.sh').length;"
            "document.getElementById('tally').textContent=b+' wrong of '+t;}"
            "function copyAll(){const out=[];document.querySelectorAll('.sh').forEach(e=>{"
            "const v=e.classList.contains('bad')?'bad':'good';out.push({id:e.dataset.id,letter:e.dataset.ch,form:e.dataset.form,"
            "n:+e.dataset.n,page:+e.dataset.page,wid:e.dataset.wid,index:+e.dataset.index,verdict:v})});"
            "navigator.clipboard.writeText(out.map(o=>JSON.stringify(o)).join('\\n'));"
            "alert(out.length+' verdicts copied');}"
            "</script>")
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(page)
    print("%s: %d shapes covering %.0f%% of %s letters"
          % (a.out, len(keep), 100.0 * run / max(total, 1), "{:,}".format(total)))


if __name__ == "__main__":
    main()
