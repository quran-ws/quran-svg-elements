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

A shape is often not simply right or wrong: the curve is the letter's own, but it carries
a sliver of its neighbour, or it is missing one. So a card can also be CORRECTED — press
✂ and the whole word opens, the letter dark and the rest of it grey. Draw the boundary
freehand (a joint is rarely a straight line) and click the side that belongs to THIS
letter. Because the whole word is there, the same gesture takes ink back from a
neighbour as easily as it gives ink away.

A correction that stays inside the letter's own box is a fact about the SHAPE and is
recorded in fractions of that box, so it transfers to every instance of it. One that
reaches into a neighbour is a fact about that WORD, and is recorded in page units.

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


_WORDS = {}


def word_paths(page, wid):
    """Every body path of the word, and which letter each belongs to, from the letters
    build. Cached per page: the shapes page opens the same page many times."""
    key = (page, wid)
    if key in _WORDS:
        return _WORDS[key]
    import re as _re
    path = os.path.join(L.LETTERS_SVG, "%03d.svg" % page)
    out = {"paths": [], "of": []}
    if os.path.exists(path):
        words, _ = L.read_words(page, L.LETTERS_SVG)
        for w in words:
            if w["wid"] != wid:
                continue
            for m in _re.finditer(r'<g class="letter"([^>]*)>(.*?)</g>', w["inner"], _re.S):
                at = L.parse_attrs(m.group(1))
                idx = int(at.get("data-index", -1))
                for pm in _re.finditer(r'<path ([^>]*?)/>', m.group(2)):
                    pa = L.parse_attrs(pm.group(1))
                    if pa.get("data-kind") == "body" and pa.get("d"):
                        out["paths"].append(pa["d"])
                        out["of"].append(idx)
    _WORDS[key] = out
    return out


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
    wp = word_paths(ex["page"], ex["wid"])
    data = json.dumps({"word": wp["paths"], "of": wp["of"], "index": ex["index"],
                       "box": [round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)]},
                      ensure_ascii=False).replace("<", "\\u003c")
    return ('<div data-id="%s" data-ch="%s" data-form="%s" data-n="%d" '
            'data-page="%d" data-wid="%s" data-index="%d" data-w="%.3f" '
            'data-box="%.3f,%.3f,%.3f,%.3f" onclick="mark(event,this)" class="sh good" '
            'title="p%d %s letter %d">'
            '<div class="cut" onclick="openTrim(event,this.parentNode)">\u2702</div>'
            '<script type="application/json" class="wd">%s</script>'
            '%s<div class="cnt">%s</div></div>'
            % (shape_id(ex), html.escape(c["ch"]), c["form"], c["n"], ex["page"], ex["wid"],
               ex["index"], x1 - x0, x0, y0, x1, y1, ex["page"], ex["wid"], ex["index"],
               data, "".join(parts), "{:,}".format(c["n"])))


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
            ".sh{position:relative}.cut{position:absolute;top:1px;left:2px;font-size:11px;opacity:.25}"
            ".cut:hover{opacity:1}.sh.trim{border-color:#c80;background:#fffaf0}"
            "#ov{display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:20;"
            "align-items:center;justify-content:center}"
            "#ov .box{background:#fff;padding:14px;border-radius:8px;text-align:center;max-width:92vw}"
            "#ov svg{cursor:crosshair;background:#fff}#ov .btns{margin-top:8px}"
            "#ov button{position:static;margin:0 4px;padding:6px 12px}"
            "button{position:fixed;top:10px;right:10px;padding:8px 14px;z-index:9}"
            "#tally{position:fixed;top:10px;right:150px;padding:8px 12px;background:#fff;"
            "border:1px solid #ccc;border-radius:6px;font-size:13px;z-index:9}</style>"
            "<button onclick='copyAll()'>Copy verdicts</button><div id=tally>0 wrong</div>"
            "<div id=ov onclick='if(event.target.id==\"ov\")closeTrim()'><div class=box>"
            "<div id=ovsvg></div><div class=btns><b id=ovmsg>draw the cut across the shape</b><br>"
            "<button onclick='clearTrim()'>clear</button>"
            "<button onclick='closeTrim()'>done</button></div></div></div>"
            "<h1>Letter shapes</h1>"
            "<p>Every shape the split produced, one card per shape, with the number of words that "
            "draw it. <b>Everything starts marked right — click a shape to mark it wrong, click again "
            "to put it back. Press \u2702 to open the whole word, draw the boundary freehand and click the "
            "side that belongs to the dark letter \u2014 that both trims a sliver off and takes a missing "
            "piece back from a neighbour.</b> "
            "The shapes are ordered by how much of the mushaf they carry, so the first few cards of "
            "each letter are worth far more than the last. Then press Copy and paste the lines back.</p>"
            + "".join(body) +
            "<script>"
            "let cur=null,drawing=false,pts=[],side=null;"
            "function mark(ev,el){if(ev.target.classList.contains('cut'))return;const s=el.classList;"
            "if(s.contains('good')){s.remove('good');s.add('bad')}else{s.remove('bad');s.remove('trim');s.add('good')}"
            "delete el.dataset.trim;tally();}"
            "function svgPt(svg,e){const r=svg.getBoundingClientRect(),vb=svg.viewBox.baseVal;"
            "return[vb.x+(e.clientX-r.left)/r.width*vb.width,vb.y+(e.clientY-r.top)/r.height*vb.height];}"
            "function wordSvg(el){const w=JSON.parse(el.querySelector('.wd').textContent);"
            "const NS='http://www.w3.org/2000/svg';const svg=document.createElementNS(NS,'svg');"
            "const g=document.createElementNS(NS,'g');g.setAttribute('transform','scale(1 -1)');"
            "w.word.forEach((d,i)=>{const p=document.createElementNS(NS,'path');p.setAttribute('d',d);"
            "p.setAttribute('fill',w.of[i]===w.index?'#111':'#c9c9c9');p.setAttribute('fill-rule','evenodd');"
            "g.appendChild(p)});svg.appendChild(g);svg.dataset.box=w.box.join(',');return svg;}"
            "function openTrim(ev,el){ev.stopPropagation();cur=el;pts=[];side=null;"
            "const svg=wordSvg(el);const box=document.getElementById('ovsvg');box.innerHTML='';box.appendChild(svg);"
            "svg.id='tsvg';document.getElementById('ov').style.display='flex';"
            "const bx=svg.getBBox();const pad=1.0;"
            "svg.setAttribute('viewBox',(bx.x-pad)+' '+(bx.y-pad)+' '+(bx.width+2*pad)+' '+(bx.height+2*pad));"
            "const vb=svg.viewBox.baseVal;"
            "svg.setAttribute('width',Math.min(900,vb.width*20));svg.setAttribute('height',vb.height*20);"
            "svg.addEventListener('mousedown',e=>{if(side!==null)return;drawing=true;pts=[svgPt(svg,e)];redraw();});"
            "svg.addEventListener('mousemove',e=>{if(!drawing)return;const p=svgPt(svg,e);"
            "const q=pts[pts.length-1];if((p[0]-q[0])**2+(p[1]-q[1])**2>(vb.width/300)**2){pts.push(p);redraw()}});"
            "svg.addEventListener('mouseup',()=>{if(drawing){drawing=false;"
            "document.getElementById('ovmsg').textContent='now click the piece that belongs to the neighbour'}});"
            "svg.addEventListener('click',e=>{if(drawing||pts.length<2||side)return;side=svgPt(svg,e);redraw();save();});"
            "document.getElementById('ovmsg').textContent="
            "'draw the boundary, then click the side that belongs to the dark letter';"
            "if(el.dataset.trim){const t=JSON.parse(el.dataset.trim);"
            "pts=(t.page_path||[]).map(q=>[q[0],-q[1]]);"
            "side=t.page_side?[t.page_side[0],-t.page_side[1]]:null;redraw();}}"
            "function redraw(){const svg=document.getElementById('tsvg');if(!svg)return;const vb=svg.viewBox.baseVal;"
            "[...svg.querySelectorAll('.tl,.tp')].forEach(e=>e.remove());"
            "if(pts.length>1){const pl=document.createElementNS('http://www.w3.org/2000/svg','polyline');"
            "pl.setAttribute('points',pts.map(p=>p[0]+','+p[1]).join(' '));pl.setAttribute('fill','none');"
            "pl.setAttribute('stroke','#b00');pl.setAttribute('stroke-width',vb.width/90);"
            "pl.setAttribute('stroke-linecap','round');pl.setAttribute('class','tl');svg.appendChild(pl);}"
            "if(side){const c=document.createElementNS('http://www.w3.org/2000/svg','circle');"
            "c.setAttribute('cx',side[0]);c.setAttribute('cy',side[1]);c.setAttribute('r',vb.width/45);"
            "c.setAttribute('fill','rgba(200,0,0,.55)');c.setAttribute('class','tp');svg.appendChild(c);}}"
            "function save(){if(!cur||pts.length<2||!side)return;const svg=document.getElementById('tsvg');"
            "const bx=svg.dataset.box.split(',').map(Number);"
            "const pg=p=>[+p[0].toFixed(3),+(-p[1]).toFixed(3)];"
            "const inside=pts.concat([side]).every(p=>p[0]>=bx[0]-0.5&&p[0]<=bx[2]+0.5&&-p[1]>=bx[1]-0.5&&-p[1]<=bx[3]+0.5);"
            "const f=p=>[+((p[0]-bx[0])/(bx[2]-bx[0])).toFixed(4),+((-p[1]-bx[1])/(bx[3]-bx[1])).toFixed(4)];"
            "const rec={page_path:pts.map(pg),page_side:pg(side),scope:inside?'shape':'word'};"
            "if(inside){rec.path=pts.map(f);rec.side=f(side)}"
            "cur.dataset.trim=JSON.stringify(rec);"
            "cur.classList.remove('good');cur.classList.remove('bad');cur.classList.add('trim');"
            "document.getElementById('ovmsg').textContent="
            "(JSON.parse(cur.dataset.trim).scope==='shape'"
            "?'saved for this SHAPE \u2014 it applies to every word that draws it'"
            ":'saved for this WORD \u2014 it reaches into a neighbour, so it is one example')"
            "+' \u2014 press done';tally();}"
            "function clearTrim(){pts=[];side=null;redraw();if(cur){delete cur.dataset.trim;"
            "cur.classList.remove('trim');cur.classList.add('good');}"
            "document.getElementById('ovmsg').textContent="
            "'draw the boundary, then click the side that belongs to the dark letter';tally();}"
            "function closeTrim(){document.getElementById('ov').style.display='none';cur=null;drawing=false;}"
            "function tally(){const b=document.querySelectorAll('.sh.bad').length;"
            "const m=document.querySelectorAll('.sh.trim').length;"
            "const t=document.querySelectorAll('.sh').length;"
            "document.getElementById('tally').textContent=b+' wrong, '+m+' trimmed, of '+t;}"
            "function copyAll(){const out=[];document.querySelectorAll('.sh').forEach(e=>{"
            "const v=e.classList.contains('bad')?'bad':e.dataset.trim?'trim':'good';"
            "const o={id:e.dataset.id,letter:e.dataset.ch,form:e.dataset.form,n:+e.dataset.n,"
            "page:+e.dataset.page,wid:e.dataset.wid,index:+e.dataset.index,verdict:v};"
            "if(e.dataset.trim){o.trim=JSON.parse(e.dataset.trim);o.box=e.dataset.box.split(',').map(Number)}"
            "out.push(o)});"
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
