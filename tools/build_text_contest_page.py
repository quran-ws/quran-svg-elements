#!/usr/bin/env python3
"""Build docs/defects/text_contest.html — which source spells the print right.

Our word text is quran.com's `text_uthmani`. quran-ws/quran-text ships its own
(`.cache/word_by_word_translation/hafs.json`, `t` plus a `marks[]` layer for the
waqf), and MushafDatabase labels the same artwork a third way. They disagree on
54,500 of 77,432 words — but almost all of that is ENCODING, not content: the
same mark written at a different code point, or in a different order.

CLAUDE.md: "Compare after normalising code points to families, or you measure
encoding rather than content." So the question is not per word, it is per KIND
of difference, and only the ink can settle it. Each class below is shown with
real words, the printed ink above and the three spellings beneath.

    python3 tools/build_text_contest_page.py [examples-per-class]
"""
import glob
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QROOT = os.environ.get("QSVG_ROOT", ROOT)
CACHE = os.path.join(QROOT, ".cache", "words-svg", "hafs-kfqc")
LIB = os.path.join(QROOT, ".cache", "word_by_word_translation", "hafs.json")
REF = os.path.join(ROOT, "MushafDatabase-Ligature-Based-SVG", "SVG V1.01")
OUT = os.path.join(ROOT, "docs", "defects", "text_contest.html")

# Every source is drawn in the font the print itself is set in — KFGQPC
# UthmanicHafs v3.0, shipped alongside the text by quran-ws/quran-text.
# Abdullah checked it against the artwork: it matches. This matters because a
# system Arabic face draws U+06DF and U+0652 almost alike, and that pair IS
# the biggest class of disagreement — a generic font would settle the question
# by accident. Embedded base64 so the page travels on its own.
FONT = os.path.join(QROOT, ".cache", "fonts", "UthmanicHafs-v-3.0.ttf")


def font_css():
    import base64
    if not os.path.exists(FONT):
        raise SystemExit("missing font: " + FONT)
    b64 = base64.b64encode(open(FONT, "rb").read()).decode("ascii")
    return ('@font-face{font-family:"hafs";font-display:block;'
            'src:url(data:font/ttf;base64,%s)}' % b64)


WORD = re.compile(r'<g class="word" data-word-key="(\d+):(\d+):(\d+)"'
                  r'[^>]*data-rasm-uthmani="([^"]*)"[^>]*>')
TAG = re.compile(r"<g\b|</g>")


def cps(t):
    return " ".join("%04X" % ord(c) for c in t)


def library():
    h = json.load(open(LIB, encoding="utf-8"))
    by = {x["w"]: x for x in h["words"]}
    out = {}
    for a in h["ayat"]:
        lo, hi = a["words"]
        for pos, i in enumerate(range(lo, hi + 1), 1):
            w = by.get(i)
            if not w:
                continue
            out[(a["sura"], a["n"], pos)] = (
                w.get("t", "")
                + "".join(m.get("sign", "") for m in (w.get("marks") or [])))
    return out


def classify(ours, lib):
    """What KIND of disagreement this is — the thing a verdict applies to."""
    d = set(ours) ^ set(lib)
    if not d:
        return "order", "same marks, written in a different order"
    pts = {"%04X" % ord(c) for c in d}
    if pts <= {"0652", "06E1"}:
        return "sukun", "sukun: U+0652 against U+06E1"
    if pts <= {"0652", "06DF"}:
        return "sifr", "U+0652 against U+06DF, the rounded zero"
    if pts <= {"0649", "064A"}:
        return "yaa", "final ى (U+0649) against ي (U+064A)"
    if pts <= {"0622", "0627", "0653", "0623", "0625", "0640", "0654"}:
        return "hamzah", "hamzah seat and maddah written differently"
    return "other", "something else"


def group_at(src, start):
    depth = 0
    for m in TAG.finditer(src, start):
        depth += 1 if m.group(0) == "<g" else -1
        if depth == 0:
            return src[start:m.end()]
    return ""


def snippet(src, start):
    vb = re.search(r'viewBox="[^"]*"', src)
    frame = re.search(r'<g transform="matrix[^"]*">', src)
    ls = src.rfind('<g class="line"', 0, start)
    inner = re.search(r'<g transform="[^"]*">', src[ls:start])
    grp = group_at(src, start).replace('fill="#231f20"', 'fill="#1a1a1a"')
    return ('<svg xmlns="http://www.w3.org/2000/svg" %s class="ink">%s%s%s</g></g></svg>'
            % (vb.group(0) if vb else "", frame.group(0) if frame else "<g>",
               inner.group(0) if inner else "<g>", grp))


def main():
    per = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    lib = library()
    refcache = {}
    classes = {}
    for f in sorted(glob.glob(os.path.join(CACHE, "*.svg"))):
        pg = int(os.path.basename(f)[:3])
        src = open(f, encoding="utf-8").read()
        for m in WORD.finditer(src):
            key = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
            ours = m.group(4)
            lt = lib.get(key)
            if lt is None or lt == ours:
                continue
            cid, label = classify(ours, lt)
            got = classes.setdefault(cid, {"label": label, "n": 0, "ex": []})
            got["n"] += 1
            if len(got["ex"]) < per:
                if pg not in refcache:
                    try:
                        sys.path.insert(0, os.path.join(ROOT, "tools"))
                        import audit_reference as ar
                        refcache[pg] = ar.reference(
                            os.path.join(REF, "%03d.svg" % pg))
                    except Exception:
                        refcache[pg] = {}
                r = refcache[pg].get(key)
                got["ex"].append({
                    "page": pg, "key": "%d:%d:%d" % key,
                    "svg": snippet(src, m.start()),
                    "ours": ours, "lib": lt, "ref": r[1] if r else None})

    order = sorted(classes.items(), key=lambda kv: -kv[1]["n"])
    rows = []
    for cid, c in order:
        cards = []
        for e in c["ex"]:
            three = []
            for name, t, note in (("ours · quran.com text_uthmani", e["ours"], ""),
                                  ("quran-ws/quran-text", e["lib"], ""),
                                  ("MushafDatabase", e["ref"], "")):
                if t is None:
                    three.append('<div class="src"><b>%s</b><span class="na">'
                                 'not in this release</span></div>' % name)
                    continue
                three.append('<div class="src"><b>%s</b><span class="ar">%s</span>'
                             '<span class="cp">%s</span></div>'
                             % (name, html.escape(t), cps(t)))
            cards.append('<div class="card"><div class="stage">%s</div>'
                         '<div class="k">p%d &middot; %s</div>%s</div>'
                         % (e["svg"], e["page"], e["key"], "".join(three)))
        rows.append(
            '<section class="cls" data-cls="%s"><h2>%s <span class="cnt">%d words</span></h2>'
            '<p class="lab">%s</p><div class="cards">%s</div>'
            '<div class="ask"><label>which spelling is the print\'s? '
            '<select><option value="">—</option>'
            '<option>ours (quran.com text_uthmani)</option>'
            '<option>quran-ws/quran-text</option>'
            '<option>MushafDatabase</option>'
            '<option>they are equivalent — encoding only</option>'
            '</select></label>'
            '<textarea rows="2" placeholder="why"></textarea></div></section>'
            % (cid, cid, c["n"], html.escape(c["label"]), "".join(cards)))

    doc = """<!doctype html><meta charset="utf-8">
<title>Which source spells the print</title>
<style>@@FONTS@@
 :root{--bg:#fbfaf7;--fg:#1a1a1a;--mut:#666;--line:#e2ded5}
 body{margin:0;background:var(--bg);color:var(--fg);
      font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
 header{padding:26px 32px;border-bottom:1px solid var(--line)}
 h1{margin:0 0 6px;font-size:22px}
 .sub{color:var(--mut);max-width:76ch}
 .cls{padding:24px 32px;border-bottom:1px solid var(--line)}
 h2{font-size:15px;margin:0;text-transform:uppercase;letter-spacing:.02em;color:var(--mut)}
 .cnt{text-transform:none;letter-spacing:0;color:var(--fg);font-weight:600}
 .lab{margin:4px 0 14px;color:var(--mut)}
 .cards{display:flex;gap:14px;overflow-x:auto;padding-bottom:6px}
 .card{flex:0 0 260px;border:1px solid var(--line);border-radius:8px;background:#fff;padding:10px}
 .stage{background:#fff;border-bottom:1px solid var(--line);margin:-10px -10px 8px;
        padding:8px;border-radius:8px 8px 0 0}
 svg.ink{display:block;width:100%;height:auto}
 .k{font:11px ui-monospace,Menlo,monospace;color:var(--mut);margin-bottom:6px}
 .src{margin:6px 0}
 .src b{display:block;font-size:11px;color:var(--mut);font-weight:600}
 .ar{font-family:"hafs",serif;font-size:27px;display:block;
      line-height:2.1;direction:rtl;unicode-bidi:isolate}
 .cp{font:10px ui-monospace,Menlo,monospace;color:var(--mut);word-break:break-all}
 .na{font-size:12px;color:var(--mut);font-style:italic}
 .ask{margin-top:14px;display:flex;gap:12px;flex-wrap:wrap;align-items:center}
 select,textarea{font:inherit;padding:6px 8px;border:1px solid var(--line);border-radius:6px}
 textarea{flex:1 1 320px}
 footer{padding:22px 32px}
 button{font:inherit;padding:8px 14px;border-radius:6px;border:1px solid #0b7285;
        background:#0b7285;color:#fff;cursor:pointer}
 #out{font:12px ui-monospace,Menlo,monospace;white-space:pre-wrap;padding:0 32px 40px;color:var(--mut)}
 @media (prefers-color-scheme:dark){
  :root{--bg:#14140f;--fg:#eee;--mut:#9a958a;--line:#2f2c25}
  .card,.stage{background:#faf7f0;color:#1a1a1a}
 }
</style>
<header><h1>Which source spells the print</h1>
<p class="sub">Our word text is quran.com's <code>text_uthmani</code>.
quran-ws/quran-text ships its own, and MushafDatabase labels the same artwork a
third way. They disagree on <b>@@N@@ of 77,432 words</b> — but the disagreement is
almost all ENCODING, not content, so the verdict belongs to the KIND of
difference, not to each word. The ink above each card is what the page actually
draws.</p>
<p class="sub">All three are set in <b>KFGQPC UthmanicHafs v3.0</b>, the face this print uses, so the three spellings are drawn the way the mushaf would draw them.</p></header>
@@ROWS@@
<footer><button id="save">Copy verdicts as JSON</button></footer>
<pre id="out"></pre>
<script>
for (const svg of document.querySelectorAll('svg.ink')) {
  const w = svg.querySelector('g.word'); if (!w) continue;
  const ctm = svg.getScreenCTM(); if (!ctm) continue;
  const inv = ctm.inverse(), r = w.getBoundingClientRect();
  let x0=Infinity,y0=Infinity,x1=-Infinity,y1=-Infinity;
  for (const [cx,cy] of [[r.left,r.top],[r.right,r.bottom]]) {
    const p = new DOMPoint(cx,cy).matrixTransform(inv);
    x0=Math.min(x0,p.x); y0=Math.min(y0,p.y); x1=Math.max(x1,p.x); y1=Math.max(y1,p.y);
  }
  if(!isFinite(x0)) continue;
  const px=(x1-x0)*0.06+1, py=(y1-y0)*0.30+1;
  svg.setAttribute('viewBox',[x0-px,y0-py,(x1-x0)+2*px,(y1-y0)+2*py].join(' '));
}
document.getElementById('save').onclick = () => {
  const out=[...document.querySelectorAll('.cls')].map(c=>({
    kind:c.dataset.cls, verdict:c.querySelector('select').value,
    note:c.querySelector('textarea').value
  })).filter(v=>v.verdict||v.note);
  const j=JSON.stringify(out,null,1);
  document.getElementById('out').textContent=j;
  navigator.clipboard&&navigator.clipboard.writeText(j);
};
</script>
"""
    total = sum(c["n"] for _, c in order)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(
        doc.replace("@@FONTS@@", font_css()).replace("@@N@@", "{:,}".format(total)).replace("@@ROWS@@", "".join(rows)))
    print("%s: %d classes, %d differing words"
          % (os.path.relpath(OUT, ROOT), len(order), total))
    for cid, c in order:
        print("   %-8s %6d  %s" % (cid, c["n"], c["label"]))


main()
