#!/usr/bin/env python3
"""Build docs/defects/ink_vs_text.html — every word whose emitted TEXT does not
describe its own INK.

tools/audit_ink_text.py finds them; this shows them. Against our text of record
(`data-rasm-uthmani`) there are none, over 77,432 words. All that survives is
the secondary `data-qpc` attribute, and this page is how that gets adjudicated:
each card carries the printed ink cropped out of the page it is drawn on, both
spellings set in the print's own face, and the code points underneath, so the
disagreement is visible rather than asserted.

    python3 tools/build_ink_text_page.py
"""
import base64
import collections
import glob
import html
import json
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QROOT = os.environ.get("QSVG_ROOT", ROOT)
CACHE = os.path.join(QROOT, ".cache", "words-svg", "hafs-kfqc")
ROWS = os.path.join(ROOT, "docs", "defects", "ink_vs_text.json")
FONT = os.path.join(QROOT, ".cache", "fonts", "UthmanicHafs-v-3.0.ttf")
OUT = os.path.join(ROOT, "docs", "defects", "ink_vs_text.html")

TAG = re.compile(r"<g\b|</g>")
WORD = re.compile(r'<g class="word" ([^>]*)>')
ATTR = re.compile(r'([a-z-]+)="([^"]*)"')


def font_coverage(texts):
    """Every code point the page will draw must exist in the embedded face.

    A missing glyph does not error — the browser silently substitutes another
    font for that run, so the text quietly stops being set in the print's face
    exactly where the interesting marks are. Verified rather than assumed:
    UthmanicHafs v3.0 covers both texts completely, while the review platform's
    V22 face is missing U+08F0-08F2 (the open tanwin) which rasm_uthmani uses
    6,643 times — picking that one would have fallen back on every tanwin.
    """
    d = open(FONT, "rb").read()
    n = struct.unpack(">H", d[4:6])[0]
    off = next(struct.unpack(">I", d[12 + 16 * i + 8:12 + 16 * i + 12])[0]
               for i in range(n) if d[12 + 16 * i:12 + 16 * i + 4] == b"cmap")
    nt = struct.unpack(">H", d[off + 2:off + 4])[0]
    st = fmt = None
    for i in range(nt):
        so = struct.unpack(">I", d[off + 4 + 8 * i + 4:off + 4 + 8 * i + 8])[0]
        f = struct.unpack(">H", d[off + so:off + so + 2])[0]
        if f in (4, 12):
            st, fmt = off + so, f
    chars = set()
    if fmt == 4:
        x2 = struct.unpack(">H", d[st + 6:st + 8])[0]
        for i in range(x2 // 2):
            e = struct.unpack(">H", d[st + 14 + 2 * i:st + 16 + 2 * i])[0]
            a = struct.unpack(">H", d[st + 16 + x2 + 2 * i:st + 18 + x2 + 2 * i])[0]
            if not (a == e == 0xFFFF):
                chars.update(range(a, e + 1))
    else:
        for i in range(struct.unpack(">I", d[st + 12:st + 16])[0]):
            a, e, _ = struct.unpack(">III", d[st + 16 + 12 * i:st + 28 + 12 * i])
            chars.update(range(a, e + 1))
    missing = {c for t in texts for c in (t or "") if ord(c) not in chars}
    if missing:
        raise SystemExit("font lacks %d code point(s) the page draws: %s"
                         % (len(missing),
                            " ".join("U+%04X" % ord(c) for c in sorted(missing))))
    return len(chars)


def font_css():
    if not os.path.exists(FONT):
        raise SystemExit("missing font: " + FONT)
    b64 = base64.b64encode(open(FONT, "rb").read()).decode("ascii")
    return ('@font-face{font-family:"hafs";font-display:block;'
            'src:url(data:font/ttf;base64,%s)}' % b64)


def cps(t):
    return " ".join("%04X" % ord(c) for c in t or "")


def group_at(src, start):
    depth = 0
    for m in TAG.finditer(src, start):
        depth += 1 if m.group(0) == "<g" else -1
        if depth == 0:
            return src[start:m.end()]
    return ""


def snippet(src, start):
    """The word group, still inside the page and line frames that place it, so
    it draws exactly as the mushaf draws it. Cropped to the word at runtime."""
    vb = re.search(r'viewBox="[^"]*"', src)
    frame = re.search(r'<g transform="matrix[^"]*">', src)
    ls = src.rfind('<g class="line"', 0, start)
    inner = re.search(r'<g transform="[^"]*">', src[ls:start])
    grp = group_at(src, start).replace('fill="#231f20"', 'fill="#1a1a1a"')
    return ('<svg xmlns="http://www.w3.org/2000/svg" %s class="ink">%s%s%s</g></g></svg>'
            % (vb.group(0) if vb else "", frame.group(0) if frame else "<g>",
               inner.group(0) if inner else "<g>", grp))


def sig(r):
    """The disagreement's shape, so identical sites group into one class."""
    a = ",".join("%s x%d" % (k, v) for k, v in sorted(r["ink_draws_text_omits"].items()))
    b = ",".join("%s x%d" % (k, v) for k, v in sorted(r["text_spells_ink_omits"].items()))
    return (a, b)


def main():
    rows = json.load(open(ROWS, encoding="utf-8"))
    want = collections.defaultdict(list)
    for r in rows:
        want[r["page"]].append(r)

    cards = collections.defaultdict(list)
    for pg in sorted(want):
        f = os.path.join(CACHE, "%03d.svg" % pg)
        src = open(f, encoding="utf-8").read()
        idx = {}
        for m in WORD.finditer(src):
            a = dict(ATTR.findall(m.group(1)))
            if a.get("data-word-key"):
                idx[a["data-word-key"]] = (m.start(), a, m.end())
        for r in want[pg]:
            hit = idx.get(r["word_key"])
            if not hit:
                continue
            start, a, end = hit
            body = group_at(src, start)
            ink = [x for x in re.findall(r'data-mark="([^"]+)"', body)
                   if x not in ("dot", "two_dots", "three_dots")]
            cards[sig(r)].append({
                "page": pg, "key": r["word_key"],
                "svg": snippet(src, start),
                "uth": a.get("data-rasm-uthmani"), "qpc": a.get("data-qpc"),
                "ink": ink,
                "plus": r["ink_draws_text_omits"],
                "minus": r["text_spells_ink_omits"],
            })

    order = sorted(cards.items(), key=lambda kv: -len(kv[1]))
    out = []
    for i, (s, items) in enumerate(order):
        a, b = s
        bits = []
        if a:
            bits.append('<span class="pill ink">ink draws <b>%s</b></span>' % html.escape(a))
        if b:
            bits.append('<span class="pill txt">qpc spells <b>%s</b></span>' % html.escape(b))
        cs = []
        for it in items:
            cs.append(
                '<div class="card"><div class="stage">%s</div>'
                '<div class="k">p%d · %s</div>'
                '<div class="src ok"><b>ours · rasm_uthmani</b>'
                '<span class="ar">%s</span><span class="cp">%s</span></div>'
                '<div class="src no"><b>data-qpc</b>'
                '<span class="ar">%s</span><span class="cp">%s</span></div>'
                '<div class="ink-list"><b>ink names</b> %s</div></div>'
                % (it["svg"], it["page"], html.escape(it["key"]),
                   html.escape(it["uth"] or ""), cps(it["uth"]),
                   html.escape(it["qpc"] or ""), cps(it["qpc"]),
                   html.escape(", ".join(it["ink"]))))
        out.append(
            '<section class="cls"><h2>%d word%s <span class="pills">%s</span></h2>'
            '<div class="cards">%s</div></section>'
            % (len(items), "" if len(items) == 1 else "s", "".join(bits), "".join(cs)))

    doc = """<!doctype html><meta charset="utf-8">
<title>Ink against its own text</title>
<style>@@FONTS@@
 :root{--bg:#fbfaf7;--fg:#1a1a1a;--mut:#666;--line:#e2ded5;--ok:#0b7285;--no:#a5361f}
 body{margin:0;background:var(--bg);color:var(--fg);
      font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
 header{padding:26px 32px;border-bottom:1px solid var(--line)}
 h1{margin:0 0 6px;font-size:22px}
 .sub{color:var(--mut);max-width:80ch}
 .cls{padding:22px 32px;border-bottom:1px solid var(--line)}
 h2{font-size:15px;margin:0 0 12px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
 .pills{display:flex;gap:6px;flex-wrap:wrap;font-weight:400}
 .pill{font-size:11px;padding:3px 8px;border-radius:99px;border:1px solid var(--line)}
 .pill.ink{background:#e7f2f4;color:#08505c;border-color:#bcd9de}
 .pill.txt{background:#f7e9e5;color:#7d2917;border-color:#e6c6bd}
 .cards{display:flex;gap:14px;overflow-x:auto;padding-bottom:8px}
 .card{flex:0 0 268px;border:1px solid var(--line);border-radius:8px;background:#fff;padding:10px}
 .stage{background:#fff;border-bottom:1px solid var(--line);margin:-10px -10px 8px;
        padding:10px;border-radius:8px 8px 0 0}
 svg.ink{display:block;width:100%;height:auto}
 .k{font:11px ui-monospace,Menlo,monospace;color:var(--mut);margin-bottom:8px}
 .src{margin:8px 0;padding-left:8px;border-left:3px solid var(--line)}
 .src.ok{border-left-color:var(--ok)}
 .src.no{border-left-color:var(--no)}
 .src b{display:block;font-size:11px;color:var(--mut);font-weight:600}
 .ar{font-family:"hafs",serif;font-size:27px;display:block;line-height:2.1;
     direction:rtl;unicode-bidi:isolate}
 .cp{font:10px ui-monospace,Menlo,monospace;color:var(--mut);word-break:break-all}
 .ink-list{font-size:11px;color:var(--mut);margin-top:8px;
           border-top:1px dashed var(--line);padding-top:6px}
 .ink-list b{color:var(--fg)}
 @media (prefers-color-scheme:dark){
  :root{--bg:#14140f;--fg:#eee;--mut:#9a958a;--line:#2f2c25}
  /* the cards stay light in dark mode so the ink reads as it does on paper,
     which means every colour INSIDE a card must be restated — inheriting the
     page foreground puts near-white text on a near-white card. */
  .card,.stage{background:#faf7f0;color:#1a1a1a}
  .card .cp,.card .ink-list,.card .k,.card .src b{color:#6b6459}
  .card .ink-list b{color:#1a1a1a}
 }
</style>
<header><h1>Ink against its own text</h1>
<p class="sub">Does each word's emitted text describe the ink in that same word
group? Over <b>77,432 words and 331,129 mark elements</b>, our text of record
<code>data-rasm-uthmani</code> disagrees with the ink <b>nowhere</b>. These
<b>@@N@@</b> are the whole residue, and every one of them is the secondary
<code>data-qpc</code> attribute.</p>
<p class="sub">The image on each card is the real ink, cropped out of the page
it is drawn on. Both spellings are set in <b>KFGQPC UthmanicHafs v3.0</b>, the
face of this print — verified to cover every code point on this page, so no
character quietly falls back to another font.
<span style="color:var(--ok)">Teal</span> is ours,
<span style="color:var(--no)">red</span> is qpc — read the ink and see which one
it is.</p></header>
@@ROWS@@
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
</script>
"""
    total = sum(len(v) for _, v in order)
    glyphs = font_coverage([it[k] for _, v in order for it in v
                            for k in ("uth", "qpc")])
    print("font covers every code point drawn (%d in its cmap)" % glyphs)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(
        doc.replace("@@FONTS@@", font_css())
           .replace("@@N@@", "{:,}".format(total))
           .replace("@@ROWS@@", "".join(out)))
    print("wrote %s — %d cards in %d classes" % (OUT, total, len(order)))


if __name__ == "__main__":
    main()
