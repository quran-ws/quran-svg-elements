#!/usr/bin/env python3
"""Confirm the hand-drawn trims: docs/defects/letter_trims_review.html

    python3 tools/build_trim_review_page.py

A trim drawn on the shapes page is a loop around part of a word, and a click saying
which side is the letter. The first version of that page read the click by
CONNECTIVITY — flood fill from the click over the ink — which betrays a loop whenever
the click lands on the loop's own line: the fill escapes and takes the complement. The
page now reads a loop by CONTAINMENT, but the trims drawn before that fix may carry the
wrong side.

So this page shows each trim both ways, rendered from the ink: the letter as the ink
INSIDE the loop, and as the ink OUTSIDE it, with the share of the word each takes. One
click confirms which was meant. Nothing is guessed: the page states what each choice
would produce and the reviewer picks.
"""
import base64
import html
import io
import json
import os
import re
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import letters_lib as L          # noqa: E402

VERDICTS = os.path.join(L.ROOT, "docs", "defects", "letter_shape_verdicts.jsonl")
OUT = os.path.join(L.ROOT, "docs", "defects", "letter_trims_review.html")
_LETTER = re.compile(r'<g class="letter"([^>]*)>(.*?)</g>', re.S)
_PATH = re.compile(r'<path ([^>]*?)/>')
Z = 10


def word_of(page, wid):
    path = os.path.join(L.LETTERS_SVG, "%03d.svg" % page)
    if not os.path.exists(path):
        return None
    words, _ = L.read_words(page, L.LETTERS_SVG)
    for w in words:
        if w["wid"] != wid:
            continue
        out = []
        for m in _LETTER.finditer(w["inner"]):
            at = L.parse_attrs(m.group(1))
            polys = []
            for pm in _PATH.finditer(m.group(2)):
                pa = L.parse_attrs(pm.group(1))
                if pa.get("data-kind") == "body" and pa.get("d"):
                    polys += L.flatten(pa["d"])
            if polys:
                out.append((int(at.get("data-index", -1)), polys))
        return out
    return None


def png(rgb):
    from PIL import Image
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def render(letters, index, loop, mode):
    """mode: 'now' the letter as it stands, 'in' the ink inside the loop, 'out' outside."""
    from PIL import Image, ImageDraw
    allp = [p for _, ps in letters for p in ps]
    x0, y0, x1, y1 = L.bbox(allp)
    pad = 1.0
    w, h = x1 - x0 + 2 * pad, y1 - y0 + 2 * pad
    ink = L.raster(allp, x0 - pad, y0 - pad, w, h, Z)
    mine = L.raster([p for i, ps in letters if i == index for p in ps], x0 - pad, y0 - pad, w, h, Z)
    H, W = ink.shape
    im = Image.new("1", (W, H), 0)
    ImageDraw.Draw(im).polygon([(int((qx - (x0 - pad)) * Z), int((qy - (y0 - pad)) * Z))
                                for qx, qy in loop], fill=1)
    poly = np.array(im, dtype=bool)
    sel = mine if mode == "now" else (ink & poly if mode == "in" else ink & ~poly)
    rgb = np.full(ink.shape + (3,), 255, np.uint8)
    rgb[ink] = (205, 205, 205)
    rgb[ink & sel] = (20, 140, 60)
    share = 100.0 * int((ink & sel).sum()) / max(int(ink.sum()), 1)
    return png(rgb[::-1]), share


def main():
    rows = [json.loads(l) for l in open(VERDICTS, encoding="utf-8") if l.strip()]
    # only the trims drawn before the containment fix need confirming; the later ones
    # carry their own `invert` and were drawn against a preview of the result.
    trims = [r for r in rows if r["verdict"] == "trim" and r.get("needs_confirm")]
    cards = []
    for k, r in enumerate(trims):
        letters = word_of(r["page"], r["wid"])
        if not letters:
            continue
        loop = [(q[0], q[1]) for q in r["trim"]["page_path"]]
        now, s_now = render(letters, r["index"], loop, "now")
        ins, s_in = render(letters, r["index"], loop, "in")
        out, s_out = render(letters, r["index"], loop, "out")
        cards.append(
            '<div class="card" data-i="%d" data-id="%s">'
            '<div class="hd"><b class="ar">%s</b> %s &middot; p%d %s &middot; %s words draw this shape</div>'
            '<div class="row">'
            '<div class="opt now"><img src="%s"><div class="lbl">as it stands &mdash; %.0f%%</div></div>'
            '<div class="opt pick" data-side="in" onclick="pick(this)"><img src="%s">'
            '<div class="lbl">inside the loop &mdash; %.0f%%</div></div>'
            '<div class="opt pick" data-side="out" onclick="pick(this)"><img src="%s">'
            '<div class="lbl">outside the loop &mdash; %.0f%%</div></div>'
            '<div class="opt drop" onclick="pick(this)" data-side="none"><div class="x">&times;</div>'
            '<div class="lbl">drop this trim</div></div>'
            '</div></div>'
            % (k, r["id"], html.escape(r["letter"]), r["form"], r["page"], r["wid"],
               "{:,}".format(r["n"]), now, s_now, ins, s_in, out, s_out))
    page = ("<!doctype html><meta charset=utf-8><title>Confirm the trims</title>"
            "<style>body{font-family:system-ui;margin:20px;background:#fafafa}"
            ".card{background:#fff;border:1px solid #ddd;border-radius:8px;padding:10px;margin-bottom:14px}"
            ".hd{font-size:13px;color:#555;margin-bottom:6px}.ar{font-size:22px}"
            ".row{display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap}"
            ".opt{border:2px solid transparent;border-radius:6px;padding:4px;text-align:center}"
            ".opt img{display:block;max-height:120px;width:auto}"
            ".opt.pick{cursor:pointer}.opt.pick:hover{border-color:#999}"
            ".opt.chosen{border-color:#2a7;background:#f2fff8}"
            ".opt.now{opacity:.75}.opt.drop{cursor:pointer;padding:20px 14px;color:#b00}"
            ".opt.drop .x{font-size:30px}.lbl{font-size:12px;color:#666;margin-top:3px}"
            "button{position:fixed;top:10px;right:10px;padding:8px 14px}"
            "#t{position:fixed;top:10px;right:160px;background:#fff;border:1px solid #ccc;"
            "border-radius:6px;padding:8px 12px;font-size:13px}</style>"
            "<button onclick='copyAll()'>Copy confirmations</button><div id=t>0 of %d</div>"
            "<h1>Confirm the trims</h1>"
            "<p>Each of these was drawn as a loop around part of a word. The first version of the "
            "shapes page read the click by connectivity, so a click landing on the loop's own line "
            "could select the complement. Here is what each trim gives both ways, rendered from the "
            "ink. <b>Click the one that is the letter</b>, or drop the trim.</p>"
            % len(cards)
            + "".join(cards) +
            "<script>"
            "function pick(el){const r=el.closest('.row');"
            "[...r.querySelectorAll('.opt')].forEach(o=>o.classList.remove('chosen'));"
            "el.classList.add('chosen');const n=document.querySelectorAll('.opt.chosen').length;"
            "document.getElementById('t').textContent=n+' of '+document.querySelectorAll('.card').length;"
            "try{localStorage.setItem('trim_confirm',JSON.stringify(state()))}catch(e){}}"
            "function state(){const o={};document.querySelectorAll('.card').forEach(c=>{"
            "const s=c.querySelector('.opt.chosen');if(s)o[c.dataset.id]=s.dataset.side});return o}"
            "function copyAll(){const st=state();const out=[];"
            "document.querySelectorAll('.card').forEach(c=>{const v=st[c.dataset.id];"
            "if(v)out.push({id:c.dataset.id,side:v})});"
            "navigator.clipboard.writeText(out.map(o=>JSON.stringify(o)).join('\\n'));"
            "alert(out.length+' confirmations copied')}"
            "try{const st=JSON.parse(localStorage.getItem('trim_confirm')||'{}');"
            "document.querySelectorAll('.card').forEach(c=>{const v=st[c.dataset.id];if(!v)return;"
            "const el=[...c.querySelectorAll('.opt')].find(o=>o.dataset.side===v);if(el)el.classList.add('chosen')});"
            "const n=document.querySelectorAll('.opt.chosen').length;"
            "document.getElementById('t').textContent=n+' of '+document.querySelectorAll('.card').length;}catch(e){}"
            "</script>")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print("%s: %d trims" % (OUT, len(cards)))


if __name__ == "__main__":
    main()
