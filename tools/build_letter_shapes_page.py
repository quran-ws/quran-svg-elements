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
✂ and the whole word opens, the letter dark and the rest of it grey. Draw freehand: a
line across a stroke, or a loop right around the part you mean. Then click inside the
part that IS the letter, and the preview shows what the letter becomes.

The two gestures are read differently, because they mean different things. A LOOP — a
drawing whose ends come back together — is read by containment: the ink inside the loop
is one part, the ink outside is the other, and the click says which one is the letter.
A LINE is read by connectivity: it is painted over the ink as a barrier and the letter
is the region holding the click. Connectivity alone would betray a loop, because a click
that lands on the loop's own line can flood out to the wrong side, which is what happens
if the two are not told apart. Because the whole word is there, the same gesture takes
ink back from a neighbour as easily as it gives a sliver away.

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
RECORD = os.path.join(L.ROOT, "docs", "defects", "letter_shape_verdicts.jsonl")
FORMS = ["first", "middle", "last", "only"]
FORM_AR = {"first": "أول الكلمة", "middle": "وسط", "last": "آخر", "only": "منفرد"}


def recorded():
    """What the repo already holds for these shapes, keyed by shape id.

    The page used to remember only in the browser, and a browser remembers only what
    differs from the default, so a rebuild -- or a second machine -- showed judged
    shapes as fresh green and the copy button then re-emitted them as "good". That is
    how fifteen drawn trims came back as goods. The file is the record; the page is
    seeded from it and the browser may only override it.
    """
    out = {}
    if not os.path.exists(RECORD):
        return out
    for line in open(RECORD, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        out[r["id"]] = {"v": r["verdict"], "t": r.get("trim"), "r": bool(r.get("reviewed"))}
    return out


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


def card(c, scale=9, with_word=True, rec=None):
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
    if with_word:
        wp = word_paths(ex["page"], ex["wid"])
        data = json.dumps({"word": wp["paths"], "of": wp["of"], "index": ex["index"],
                           "box": [round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)]},
                          ensure_ascii=False).replace("<", "\\u003c")
        cut = '<div class="cut" onclick="openTrim(event,this.parentNode)">\u2702</div>'
        blob = '<script type="application/json" class="wd">%s</script>' % data
    else:
        cut = blob = ""                      # the rare pass judges the shape, it does not edit it
    sid = shape_id(ex)
    r = (rec or {}).get(sid)
    cls = "sh good"
    trim = ""
    if r:
        if r["t"]:
            cls = "sh trim"
            trim = ' data-trim=\'%s\'' % json.dumps(r["t"], ensure_ascii=False).replace("'", "&#39;")
        elif r["v"] == "bad":
            cls = "sh bad"
        if r["r"]:
            cls += " rev"
    return ('<div data-id="%s" data-ch="%s" data-form="%s" data-n="%d" '
            'data-page="%d" data-wid="%s" data-index="%d" data-w="%.3f" '
            'data-box="%.3f,%.3f,%.3f,%.3f"%s onclick="mark(event,this)" class="%s" '
            'title="p%d %s letter %d">%s%s%s<div class="cnt">%s</div></div>'
            % (sid, html.escape(c["ch"]), c["form"], c["n"], ex["page"], ex["wid"],
               ex["index"], x1 - x0, x0, y0, x1, y1, trim, cls, ex["page"], ex["wid"],
               ex["index"], cut, blob, "".join(parts), "{:,}".format(c["n"])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cover", type=float, default=0.8,
                    help="show the most-used shapes covering this fraction of all letters")
    ap.add_argument("--limit", type=int, default=0, help="hard cap on cards (0 = none)")
    ap.add_argument("--skip", type=int, default=0, help="skip this many shapes first (paging the tail)")
    ap.add_argument("--letter", help="only this letter")
    ap.add_argument("--rare", type=int, default=0,
                    help="instead of the common shapes, the tail: every shape used FEWER than this many "
                         "times, rarest first. A shape drawn once in the whole Quran is more often a bad "
                         "cut than a rare form, so the tail is a defect list, not a catalogue.")
    ap.add_argument("--shapes", default=SHAPES)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    clusters = json.load(open(a.shapes, encoding="utf-8"))
    rec = recorded()
    if a.letter:
        clusters = [c for c in clusters if c["ch"] == a.letter]
    total = sum(c["n"] for c in clusters)
    if a.rare:
        keep = sorted((c for c in clusters if c["n"] < a.rare), key=lambda c: (c["n"], c["ch"]))
        keep = keep[a.skip:]
        if a.limit:
            keep = keep[:a.limit]
        run = sum(c["n"] for c in keep)
    else:
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
            cs = sorted(by_letter[ch].get(form, []), key=(lambda c: c["n"]) if a.rare else (lambda c: -c["n"]))
            if not cs:
                continue
            body.append('<section class="sect" data-key="%s|%s">' % (html.escape(ch), form))
            body.append('<h3 class="frm">%s <span class="ar">%s</span> <small>%s letters, %d shapes</small>'
                        ' <button class="done" onclick="sectionDone(this)">mark section reviewed</button>'
                        ' <span class="prog"></span></h3>'
                        % (form, FORM_AR[form], "{:,}".format(sum(c["n"] for c in cs)), len(cs)))
            body.append('<div class="row">%s</div>' % "".join(card(c, with_word=not a.rare, rec=rec)
                                                              for c in cs))
            body.append('</section>')
    if a.rare:
        intro = ("Shapes drawn fewer than %d times in the whole Quran, rarest first. A shape this rare "
                 "is more often a bad cut than a rare form, so read these as suspects: "
                 "<b>click any that is genuinely wrong</b>, then press <b>mark section reviewed</b> "
                 "under the heading when you finish a block \u2014 Copy and Download emit only the "
                 "shapes you actually reviewed. This pass judges the shape only; correcting one is "
                 "the job of the common-shapes page." % a.rare)
    else:
        intro = ("Every shape the split produced, one card per shape, with the number of words that "
                 "draws it. <b>Everything starts marked right \u2014 click a shape to mark it wrong, "
                 "click again to put it back. Press \u2702 to open the whole word, draw a line across "
                 "the ink or a loop around it, then click the part that IS the letter \u2014 the preview "
                 "shows what the letter becomes, and the same gesture trims a sliver off or takes a "
                 "missing piece back.</b> The shapes are ordered by how much of the mushaf they carry, "
                 "so the first few cards of each letter are worth far more than the last.</b> "
                 "Everything you have already sent back is <b>already on this page</b>, read from "
                 "the record on disk, so a rebuild no longer loses it. When you finish a block, "
                 "press <b>mark section reviewed</b> under its heading \u2014 a green tick appears on "
                 "each card and Copy or Download then emits <b>only what you reviewed</b>, so a "
                 "default green is never mistaken for a judgement.")
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
            "#ovwrap{display:flex;gap:14px;align-items:flex-start}"
            "#ovprev{border-left:1px dashed #ccc;padding-left:14px;min-width:120px}"
            "#ovprev canvas{background:#fff}#ovprev .lbl{font-size:12px;color:#666;margin-top:4px}"
            "#ov button{position:static;margin:0 4px;padding:6px 12px}"
            "button{padding:8px 14px}"
            "#bar{position:fixed;top:8px;right:10px;z-index:9;background:#fff;border:1px solid #ccc;"
            "border-radius:8px;padding:6px 10px;font-size:13px;display:flex;gap:8px;align-items:center}"
            "#bar button{padding:5px 10px}"
            "#restored{font-size:12px;color:#2a7}"
            "button.done{font-size:11px;padding:2px 8px;margin-left:8px;font-weight:400}"
            ".prog{font-size:11px;color:#888;margin-left:6px}"
            ".sh.rev:after{content:'\\2713';position:absolute;top:0;right:3px;font-size:11px;color:#2a7}"
            ".sh.bad.rev:after{color:#b00}.sh.trim.rev:after{color:#c80}"
            ".sect.alldone h3.frm{color:#2a7}</style>"
            "<div id=bar><span id=tally></span><span id=restored></span>"
            "<button onclick='copyAll()'>Copy</button>"
            "<button onclick='downloadAll()'>Download</button></div>"
            "<div id=ov onclick='if(event.target.id==\"ov\")closeTrim()'><div class=box>"
            "<div id=ovwrap><div id=ovsvg></div><div id=ovprev></div></div><div class=btns><b id=ovmsg>draw the cut across the shape</b><br>"
            "<button onclick='invertSel()'>invert</button>"
            "<button onclick='clearTrim()'>clear</button>"
            "<button onclick='closeTrim()'>done</button></div></div></div>"
            "<h1>Letter shapes</h1>"
            "<p>" + intro + "</p>"
            + "".join(body) +
            "<script>"
            "let cur=null,drawing=false,pts=[],side=null,inv=false;"
            "function mark(ev,el){if(ev.target.classList.contains('cut'))return;const s=el.classList;"
            "if(s.contains('good')){s.remove('good');s.add('bad')}else{s.remove('bad');s.remove('trim');s.add('good')}"
            "delete el.dataset.trim;s.add('rev');tally();}"
            "function svgPt(svg,e){const r=svg.getBoundingClientRect(),vb=svg.viewBox.baseVal;"
            "return[vb.x+(e.clientX-r.left)/r.width*vb.width,vb.y+(e.clientY-r.top)/r.height*vb.height];}"
            "function wordSvg(el){const w=JSON.parse(el.querySelector('.wd').textContent);"
            "const NS='http://www.w3.org/2000/svg';const svg=document.createElementNS(NS,'svg');"
            "const g=document.createElementNS(NS,'g');g.setAttribute('transform','scale(1 -1)');"
            "w.word.forEach((d,i)=>{const p=document.createElementNS(NS,'path');p.setAttribute('d',d);"
            "p.setAttribute('fill',w.of[i]===w.index?'#111':'#c9c9c9');p.setAttribute('fill-rule','evenodd');"
            "g.appendChild(p)});svg.appendChild(g);svg.dataset.box=w.box.join(',');return svg;}"
            "function openTrim(ev,el){ev.stopPropagation();cur=el;pts=[];side=null;inv=false;"
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
            "document.getElementById('ovmsg').textContent='now click the part that IS the letter'}});"
            "svg.addEventListener('click',e=>{if(drawing||pts.length<2)return;side=svgPt(svg,e);redraw();"
            "if(preview())save();});"
            "document.getElementById('ovmsg').textContent="
            "'draw a line across it or a loop around it, then click the part that IS the letter';"
            "if(el.dataset.trim){const t=JSON.parse(el.dataset.trim);"
            "pts=(t.page_path||[]).map(q=>[q[0],-q[1]]);inv=!!t.invert;"
            "side=t.page_side?[t.page_side[0],-t.page_side[1]]:null;redraw();preview();}}"
            "function redraw(){const svg=document.getElementById('tsvg');if(!svg)return;const vb=svg.viewBox.baseVal;"
            "[...svg.querySelectorAll('.tl,.tp')].forEach(e=>e.remove());"
            "if(pts.length>1){const pl=document.createElementNS('http://www.w3.org/2000/svg','polyline');"
            "pl.setAttribute('points',pts.map(p=>p[0]+','+p[1]).join(' ')+(closed()?' '+pts[0][0]+','+pts[0][1]:''));"
            "pl.setAttribute('fill',closed()?'rgba(200,0,0,.07)':'none');"
            "pl.setAttribute('stroke','#b00');pl.setAttribute('stroke-width',vb.width/260);"
            "pl.setAttribute('stroke-linecap','round');pl.setAttribute('class','tl');svg.appendChild(pl);}"
            "if(side){const c=document.createElementNS('http://www.w3.org/2000/svg','circle');"
            "c.setAttribute('cx',side[0]);c.setAttribute('cy',side[1]);c.setAttribute('r',vb.width/90);"
            "c.setAttribute('fill','rgba(200,0,0,.55)');c.setAttribute('class','tp');svg.appendChild(c);}}"
            "function closed(){if(pts.length<8)return false;const a=pts[0],b=pts[pts.length-1];"
            "let x0=1e9,x1=-1e9,y0=1e9,y1=-1e9;pts.forEach(p=>{x0=Math.min(x0,p[0]);x1=Math.max(x1,p[0]);"
            "y0=Math.min(y0,p[1]);y1=Math.max(y1,p[1])});"
            "const diag=Math.hypot(x1-x0,y1-y0);return Math.hypot(a[0]-b[0],a[1]-b[1])<0.35*diag;}"
            "function preview(){const svg=document.getElementById('tsvg');const vb=svg.viewBox.baseVal;"
            "const w=JSON.parse(cur.querySelector('.wd').textContent);"
            "const W=Math.min(360,Math.round(vb.width*14)),H=Math.round(W*vb.height/vb.width),z=W/vb.width;"
            "const ink=document.createElement('canvas');ink.width=W;ink.height=H;"
            "const ic=ink.getContext('2d',{willReadFrequently:true});"
            "ic.setTransform(z,0,0,-z,-vb.x*z,-vb.y*z);ic.fillStyle='#000';"
            "w.word.forEach(d=>ic.fill(new Path2D(d),'evenodd'));"
            "const bar=document.createElement('canvas');bar.width=W;bar.height=H;"
            "const bc=bar.getContext('2d',{willReadFrequently:true});"
            "bc.setTransform(z,0,0,z,-vb.x*z,-vb.y*z);"
            "bc.beginPath();bc.moveTo(pts[0][0],pts[0][1]);pts.slice(1).forEach(p=>bc.lineTo(p[0],p[1]));"
            "if(closed()){bc.closePath();bc.fillStyle='#000';bc.fill()}"
            "else{bc.strokeStyle='#000';bc.lineWidth=Math.max(0.12,1.2/z);bc.lineJoin='round';"
            "bc.lineCap='round';bc.stroke()}"
            "const ia=ic.getImageData(0,0,W,H).data,ba=bc.getImageData(0,0,W,H).data;"
            "const sx=Math.round((side[0]-vb.x)*z),sy=Math.round((side[1]-vb.y)*z);"
            "const sel=new Uint8Array(W*H);"
            "if(closed()){"
            "const inSide=((sx>=0&&sy>=0&&sx<W&&sy<H&&ba[(sy*W+sx)*4+3]>110)!==inv);"
            "for(let i=0;i<W*H;i++){if(ia[i*4+3]<=110)continue;"
            "const inLoop=ba[i*4+3]>110;sel[i]=(inLoop===inSide)?1:0}}"
            "else{"
            "const free=new Uint8Array(W*H);for(let i=0;i<W*H;i++)free[i]=(ia[i*4+3]>110&&ba[i*4+3]<110)?1:0;"
            "let seed=-1,best=1e9;"
            "for(let y=0;y<H;y++)for(let x=0;x<W;x++){if(!free[y*W+x])continue;"
            "const d=(x-sx)*(x-sx)+(y-sy)*(y-sy);if(d<best){best=d;seed=y*W+x}}"
            "if(seed<0){document.getElementById('ovmsg').textContent="
            "'that click is not on any ink \u2014 click on the part that IS the letter';return false;}"
            "if(best>(0.06*W)*(0.06*W)){document.getElementById('ovmsg').textContent="
            "'click nearer the ink you mean';return false;}"
            "const st=[seed];sel[seed]=1;"
            "while(st.length){const j=st.pop(),x=j%W,y=(j/W)|0;"
            "[[1,0],[-1,0],[0,1],[0,-1]].forEach(([dx,dy])=>{const nx=x+dx,ny=y+dy;"
            "if(nx<0||ny<0||nx>=W||ny>=H)return;const k=ny*W+nx;if(free[k]&&!sel[k]){sel[k]=1;st.push(k)}});}"
            "if(inv)for(let i=0;i<W*H;i++){if(ia[i*4+3]<=110)continue;sel[i]=sel[i]?0:1}}"
            "const out=document.createElement('canvas');out.width=W;out.height=H;"
            "const oc=out.getContext('2d');const im=oc.createImageData(W,H);let n=0,tot=0;"
            "for(let i=0;i<W*H;i++){if(ia[i*4+3]<=110)continue;tot++;const o=i*4;"
            "if(sel[i]){n++;im.data[o]=20;im.data[o+1]=140;im.data[o+2]=60;im.data[o+3]=255}"
            "else{im.data[o]=205;im.data[o+1]=205;im.data[o+2]=205;im.data[o+3]=255}}"
            "oc.putImageData(im,0,0);const box=document.getElementById('ovprev');box.innerHTML='';"
            "box.appendChild(out);const lb=document.createElement('div');lb.className='lbl';"
            "lb.textContent='the letter becomes this \u2014 '+Math.round(100*n/Math.max(tot,1))+'% of the word\u2019s ink';"
            "box.appendChild(lb);return true;}"
            "function save(){if(!cur||pts.length<2||!side)return;const svg=document.getElementById('tsvg');"
            "const bx=svg.dataset.box.split(',').map(Number);"
            "const pg=p=>[+p[0].toFixed(3),+(-p[1]).toFixed(3)];"
            "const inside=pts.concat([side]).every(p=>p[0]>=bx[0]-0.5&&p[0]<=bx[2]+0.5&&-p[1]>=bx[1]-0.5&&-p[1]<=bx[3]+0.5);"
            "const f=p=>[+((p[0]-bx[0])/(bx[2]-bx[0])).toFixed(4),+((-p[1]-bx[1])/(bx[3]-bx[1])).toFixed(4)];"
            "const rec={page_path:pts.map(pg),page_side:pg(side),kind:closed()?'loop':'line',"
            "scope:inside?'shape':'word'};"
            "if(inside){rec.path=pts.map(f);rec.side=f(side)}"
            "rec.invert=inv;cur.dataset.trim=JSON.stringify(rec);"
            "cur.classList.remove('good');cur.classList.remove('bad');cur.classList.add('trim');"
            "document.getElementById('ovmsg').textContent="
            "(JSON.parse(cur.dataset.trim).scope==='shape'"
            "?'saved for this SHAPE \u2014 it applies to every word that draws it'"
            ":'saved for this WORD \u2014 it reaches into a neighbour, so it is one example')"
            "+' \u2014 press done';tally();}"
            "function invertSel(){if(!cur||pts.length<2||!side)return;inv=!inv;"
            "if(preview())save();}"
            "function clearTrim(){pts=[];side=null;inv=false;redraw();document.getElementById('ovprev').innerHTML='';"
            "if(cur){delete cur.dataset.trim;"
            "cur.classList.remove('trim');cur.classList.add('good');}"
            "document.getElementById('ovmsg').textContent="
            "'draw a line across it or a loop around it, then click the part that IS the letter';tally();}"
            "function closeTrim(){document.getElementById('ov').style.display='none';cur=null;drawing=false;}"
            "const KEY='letter_shape_verdicts_'+location.pathname.split('/').pop();"
            "function st(e){return{v:e.classList.contains('bad')?'bad':e.dataset.trim?'trim':'good',"
            "t:e.dataset.trim||null,r:e.classList.contains('rev')};}"
            "const REC={};document.querySelectorAll('.sh').forEach(e=>{REC[e.dataset.id]=st(e)});"
            "function same(a,b){return a.v===b.v&&!!a.r===!!b.r&&(a.t||'')===(b.t||'');}"
            "function store(){const o={};document.querySelectorAll('.sh').forEach(e=>{"
            "const s=st(e),base=REC[e.dataset.id]||{v:'good',t:null,r:false};"
            "if(!same(s,base))o[e.dataset.id]=s});"
            "try{localStorage.setItem(KEY,JSON.stringify(o))}catch(err){}}"
            "function applyState(e,s){e.classList.remove('good');e.classList.remove('bad');"
            "e.classList.remove('trim');"
            "if(s.t){e.dataset.trim=typeof s.t==='string'?s.t:JSON.stringify(s.t);e.classList.add('trim')}"
            "else{delete e.dataset.trim;e.classList.add(s.v==='bad'?'bad':'good')}"
            "if(s.r)e.classList.add('rev');else e.classList.remove('rev');}"
            "function restore(){let o={};try{o=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(err){}"
            "let n=0;document.querySelectorAll('.sh').forEach(e=>{const r=o[e.dataset.id];if(!r)return;"
            "n++;applyState(e,r)});"
            "if(n)document.getElementById('restored').textContent=n+' unsaved in this browser';tally();}"
            "function forget(){try{localStorage.removeItem(KEY)}catch(err){}location.reload();}"
            "function sectionDone(b){const sec=b.closest('.sect');"
            "const on=!sec.classList.contains('alldone');"
            "sec.querySelectorAll('.sh').forEach(e=>{if(on)e.classList.add('rev');"
            "else e.classList.remove('rev')});tally();}"
            "function tally(){const all=document.querySelectorAll('.sh').length;"
            "const b=document.querySelectorAll('.sh.bad').length;"
            "const m=document.querySelectorAll('.sh.trim').length;"
            "const r=document.querySelectorAll('.sh.rev').length;"
            "document.getElementById('tally').textContent="
            "r+' of '+all+' reviewed \u00b7 '+b+' wrong, '+m+' trimmed';"
            "document.querySelectorAll('.sect').forEach(sec=>{"
            "const t=sec.querySelectorAll('.sh').length,d=sec.querySelectorAll('.sh.rev').length;"
            "if(t&&d===t)sec.classList.add('alldone');else sec.classList.remove('alldone');"
            "const p=sec.querySelector('.prog');if(p)p.textContent=d+' of '+t+' reviewed';"
            "const bt=sec.querySelector('button.done');"
            "if(bt)bt.textContent=(t&&d===t)?'not reviewed':'mark section reviewed';});store();}"
            "function rows(){const out=[];document.querySelectorAll('.sh').forEach(e=>{const s=st(e);"
            "const o={id:e.dataset.id,letter:e.dataset.ch,form:e.dataset.form,n:+e.dataset.n,"
            "page:+e.dataset.page,wid:e.dataset.wid,index:+e.dataset.index,verdict:s.v,reviewed:s.r};"
            "if(s.t){o.trim=JSON.parse(s.t);o.box=e.dataset.box.split(',').map(Number)}"
            "out.push(o)});return out;}"
            "function text(){return rows().filter(o=>o.reviewed).map(o=>JSON.stringify(o)).join('\\n');}"
            "function copyAll(){const t=text();if(!t){alert('nothing is marked reviewed yet \u2014 "
            "press \u201cmark section reviewed\u201d under a heading when you finish it');return}"
            "navigator.clipboard.writeText(t);alert(t.split('\\n').length+' reviewed verdicts copied');}"
            "function downloadAll(){const t=text();if(!t){alert('nothing is marked reviewed yet');return}"
            "const a=document.createElement('a');"
            "a.href=URL.createObjectURL(new Blob([t+'\\n'],{type:'application/x-ndjson'}));"
            "a.download=location.pathname.split('/').pop().replace('.html','')+'_reviewed.jsonl';"
            "document.body.appendChild(a);a.click();a.remove();}"
            "restore();"
            "</script>")
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(page)
    print("%s: %d shapes covering %.0f%% of %s letters"
          % (a.out, len(keep), 100.0 * run / max(total, 1), "{:,}".format(total)))


if __name__ == "__main__":
    main()
