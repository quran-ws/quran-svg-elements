#!/usr/bin/env python3
"""Build docs/defects/last_flags.html — every flag left in the mushaf, to be read by eye.

The sweep is down to a handful of words. All of them are body-partition
questions: one word holds a run of ink the spelling does not allow it, a
neighbour is short of one, and a mark follows the wrong body. Counting cannot
settle those — only the ink can — so this page draws each case with every word
of the ayah-fragment in its OWN colour, and asks which word each disputed
piece belongs to.

    python3 tools/build_lastflags_page.py <sweep-dir>
"""
import html
import json
import os
import re
import sys

import sys as _sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".cache", "words-svg", "hafs-kfqc")
OUT = os.path.join(ROOT, "docs", "defects", "last_flags.html")

# one hue per word position, so the partition is visible at a glance
HUES = ["#c1121f", "#1d3557", "#2a9d8f", "#e07a00", "#6a4c93",
        "#0b7285", "#b5179e", "#386641", "#9c6644", "#3a0ca3"]


_BOXES = {}


def boxes_for(pg):
    """{element id: "x1,y1,x2,y2"} exactly as the pipeline keys an override.

    tools/build_overrides.py REFUSES an edit that carries only an element id —
    ids are handed out in emission order and shift with every pipeline change,
    so resolving one later can name the wrong piece entirely. The geometry has
    to be recorded at the moment of the edit, and it has to be the pipeline's
    own: `"%.1f,%.1f,%.1f,%.1f" % (x1, y1, x2, y2)`, verified here against the
    override already live on page 6 (245.3,411.2,252.4,427.0 -> 2:35:13).
    """
    if pg in _BOXES:
        return _BOXES[pg]
    _sys.path.insert(0, os.path.join(ROOT, "tools"))
    import assign_words as aw
    cap = {}
    orig = aw.rewrite

    def spy(page, assignment, _c=cap):
        _c["a"] = assignment
        return orig(page, assignment)

    aw.rewrite = spy
    try:
        aw.assign_page("hafs/kfqc", pg,
                       os.path.join(ROOT, ".cache", "words"))
    finally:
        aw.rewrite = orig
    out, n = {}, 0
    for w, atoms in cap.get("a", []):
        for a in atoms:
            for el in a["els"]:
                n += 1
                out["e%d" % n] = "%.1f,%.1f,%.1f,%.1f" % (
                    el["x1"], el["y1"], el["x2"], el["y2"])
    _BOXES[pg] = out
    return out


def group_at(src, start):
    """The whole <g …>…</g> beginning at `start`."""
    depth = 0
    for m in re.finditer(r"<g\b|</g>", src[start:]):
        depth += 1 if m.group(0) == "<g" else -1
        if depth == 0:
            return src[start:start + m.end()]
    return ""


def fragments_for(src, ayah_key):
    """Every <g class="ayah-fragment"> of one ayah, in document order."""
    out = []
    for m in re.finditer(r'<g class="ayah-fragment"[^>]*data-ayah-key="%s"[^>]*>'
                         % re.escape(ayah_key), src):
        out.append(group_at(src, m.start()))
    return out


def line_frame(src, frag):
    """The <g class="line"> transform the fragment is drawn under."""
    i = src.find(frag)
    ls = src.rfind('<g class="line"', 0, i)
    if ls < 0:
        return "", ""
    head = src[ls:src.find(">", ls) + 1]
    inner = re.search(r'<g transform="[^"]*">', src[ls:i])
    return head, (inner.group(0) if inner else "<g>")


def colour(frag, flagged, boxes):
    """Give every word its own hue, and every path its id, box and owner."""
    def paint(m):
        key = m.group(1)
        pos = int(key.split(":")[2])
        hue = HUES[(pos - 1) % len(HUES)]
        grp = group_at(frag, m.start())
        new = grp.replace('fill="#231f20"', 'fill="%s"' % hue)

        def stamp(pm):
            eid = pm.group(1)
            box = boxes.get(eid)
            return (pm.group(0)[:-1]
                    + ' data-owner="%s"' % key
                    + (' data-box="%s"' % box if box else "")
                    + ">")
        new = re.sub(r'<path\b[^>]*data-element-id="(e\d+)"[^>]*>', stamp, new)
        if key in flagged:
            new = new.replace('<g class="word"',
                              '<g class="word flagged"', 1)
        return new
    out, pos = [], 0
    for m in re.finditer(r'<g class="word" data-word-key="([\d:]+)"', frag):
        if m.start() < pos:
            continue
        out.append(frag[pos:m.start()])
        grp = group_at(frag, m.start())
        out.append(paint(m))
        pos = m.start() + len(grp)
    out.append(frag[pos:])
    return "".join(out)


def words_of(src, ayah_key):
    """[(word key, text)] for one ayah, in document order."""
    out = []
    for frag in fragments_for(src, ayah_key):
        for m in re.finditer(r'<g class="word" data-word-key="([\d:]+)"'
                             r'[^>]*data-rasm-uthmani="([^"]*)"', frag):
            if m.group(1) not in [k for k, _ in out]:
                out.append((m.group(1), m.group(2)))
    return out


def legend(src, ayah_key, flagged):
    items = []
    for key, txt in words_of(src, ayah_key):
        pos = int(key.split(":")[2])
        hue = HUES[(pos - 1) % len(HUES)]
        cls = " on" if key in flagged else ""
        items.append('<button class="sw%s" data-word="%s"><i style="background:%s">'
                     '</i><span class="ar">%s</span> <span class="k">%s</span></button>'
                     % (cls, key, hue, html.escape(txt), key))
    return '<div class="legend">' + "".join(items) + "</div>"


def render(pg, ayah_key, flagged):
    f = os.path.join(CACHE, "%03d.svg" % pg)
    if not os.path.exists(f):
        return "<p>page %d not emitted</p>" % pg
    src = open(f, encoding="utf-8").read()
    boxes = boxes_for(pg)
    vb = re.search(r'viewBox="[^"]*"', src)
    page_frame = re.search(r'<g transform="matrix[^"]*">', src)
    svgs = []
    for frag in fragments_for(src, ayah_key):
        _, inner = line_frame(src, frag)
        svgs.append(
            '<svg xmlns="http://www.w3.org/2000/svg" %s class="ink">%s%s%s</g></g></svg>'
            % (vb.group(0) if vb else "",
               page_frame.group(0) if page_frame else "<g>",
               inner, colour(frag, flagged, boxes)))
    return "".join(svgs) + legend(src, ayah_key, flagged)


def main():
    sweep = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.environ.get("QSVG_SWEEPS", ""), "post-artwork")
    cases = []
    for name in sorted(os.listdir(sweep)):
        if not name.endswith(".json"):
            continue
        d = json.load(open(os.path.join(sweep, name), encoding="utf-8"))
        if not (d.get("marks") or d.get("intervals")):
            continue
        pg = d["page"]
        by_ayah = {}
        for m in d.get("marks", []):
            s, a, _p = m["key"].split(":")
            by_ayah.setdefault("%s:%s" % (s, a), {"marks": [], "intervals": []})
            by_ayah["%s:%s" % (s, a)]["marks"].append(m)
        for i in d.get("intervals", []):
            s, a, _p = i["key"].split(":")
            by_ayah.setdefault("%s:%s" % (s, a), {"marks": [], "intervals": []})
            by_ayah["%s:%s" % (s, a)]["intervals"].append(i)
        for ak, rec in by_ayah.items():
            cases.append((pg, ak, rec))

    rows = []
    for n, (pg, ak, rec) in enumerate(cases, 1):
        flagged = {m["key"] for m in rec["marks"]}
        flagged |= {i["key"] for i in rec["intervals"]}
        bits = []
        for m in rec["marks"]:
            fl = ", ".join("<b>%s</b> holds %s, the spelling allows %s"
                           % (html.escape(f), h, w) for f, h, w in m["bad"])
            bits.append('<li><span class="k">%s</span> <span class="ar">%s</span> — %s</li>'
                        % (m["key"], html.escape(m["word"]), fl))
        for i in rec["intervals"]:
            bits.append('<li><span class="k">%s</span> %s — <b>%s</b> held by '
                        '<span class="ar">%s</span> but drawn inside '
                        '<span class="ar">%s</span>\'s territory</li>'
                        % (i["key"], i["kind"], html.escape(i["mark"]),
                           html.escape(i["holder"]), html.escape(i["inside"])))
        rows.append(
            '<section class="case" data-case="%d" data-page="%d" data-ayah="%s">'
            '<h2>%d. page %d &middot; ayah %s</h2>'
            '<ul class="flags">%s</ul>'
            '<div class="stage">%s</div>'
            '<div class="ask">'
            '<p><b>To say what belongs where:</b> click a word below to arm it, '
            'then click each piece of ink that belongs to it. Click a piece '
            'again to undo. The armed word is outlined.</p>'
            '<div class="moves"><em>no moves yet</em></div>'
            '<label>verdict '
            '<select><option value="">—</option>'
            '<option>ours is right, the audit is wrong</option>'
            '<option>the ink is mis-partitioned — the moves above say how</option>'
            '<option>needs the print</option>'
            '</select></label>'
            '<textarea rows="3" placeholder="what you see"></textarea></div>'
            '</section>'
            % (n, pg, ak, n, pg, ak, "".join(bits), render(pg, ak, flagged)))

    doc = """<!doctype html><meta charset="utf-8">
<title>Every flag left in the mushaf</title>
<style>
 :root{--bg:#fbfaf7;--fg:#1a1a1a;--mut:#666;--line:#e2ded5}
 body{margin:0;background:var(--bg);color:var(--fg);
      font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
 header{padding:28px 32px;border-bottom:1px solid var(--line)}
 h1{margin:0 0 6px;font-size:22px;letter-spacing:-.01em}
 .sub{color:var(--mut);max-width:70ch}
 .case{padding:26px 32px;border-bottom:1px solid var(--line)}
 h2{font-size:15px;margin:0 0 10px;letter-spacing:.02em;color:var(--mut);
    text-transform:uppercase}
 .flags{margin:0 0 14px;padding-left:18px}
 .flags li{margin:3px 0}
 .k{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--mut)}
 .ar{font-size:19px}
 .stage{background:#fff;border:1px solid var(--line);border-radius:8px;
        padding:10px;overflow-x:auto}
 svg.ink{display:block;width:100%;height:auto;margin:6px 0}
 .legend{display:flex;flex-wrap:wrap;gap:6px 14px;margin-top:10px;
         padding-top:10px;border-top:1px solid var(--line)}
 .sw{display:inline-flex;align-items:center;gap:5px;font-size:13px;opacity:.72}
 .sw.on{opacity:1;font-weight:600}
 .sw.on i{outline:2px solid var(--fg);outline-offset:1px}
 .sw i{width:11px;height:11px;border-radius:3px;display:inline-block}
 .ask{margin-top:12px;display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap}
 .ask p{flex:1 1 100%;margin:0 0 4px;color:var(--mut);font-size:13px}
 select,textarea{font:inherit;padding:6px 8px;border:1px solid var(--line);
                 border-radius:6px;background:#fff}
 textarea{flex:1 1 320px;resize:vertical}
 .sw{font:inherit;border:1px solid var(--line);background:#fff0;color:inherit;
      padding:3px 7px;border-radius:6px;cursor:pointer}
 .sw:hover{border-color:var(--fg)}
 .sw.armed{outline:2px solid #0b7285;outline-offset:1px;background:#0b728514}
 svg.ink path{cursor:pointer}
 svg.ink path:hover{stroke:#0b7285;stroke-width:.6}
 svg.ink path.moved{stroke:#0b7285;stroke-width:.9;stroke-dasharray:1.2 .8}
 .moves{font-size:13px;margin:0 0 10px;flex:1 1 100%}
 .moves em{color:var(--mut)}
 .moves div{font:12px ui-monospace,Menlo,monospace;margin:2px 0}
 .moves b{font-family:inherit;font-size:14px}
 footer{padding:22px 32px;display:flex;gap:12px;align-items:center}
 button{font:inherit;padding:8px 14px;border-radius:6px;border:1px solid #0b7285;
        background:#0b7285;color:#fff;cursor:pointer}
 #out{font:12px ui-monospace,Menlo,monospace;white-space:pre-wrap;
      padding:0 32px 40px;color:var(--mut)}
 @media (prefers-color-scheme:dark){
  :root{--bg:#14140f;--fg:#eee;--mut:#9a958a;--line:#2f2c25}
  .stage{background:#faf7f0}
 }
</style>
<header>
 <h1>Every flag left in the mushaf</h1>
 <p class="sub">The sweep is down to <b>@@NM@@ mark flags</b> and <b>@@NI@@ interval flags</b>
 on <b>@@PAGES@@ pages</b> — 600 of 604 are clean. All of what is left is a body-partition
 question: one word holds a run of ink its spelling does not allow, a neighbour is
 short of one, and a mark follows the wrong body. Counting cannot settle those.
 Each word of the ayah is drawn in <b>its own colour</b>; say which word the
 disputed ink belongs to.</p>
</header>
@@ROWS@@
<footer><button id="save">Copy verdicts as JSON</button>
<span class="sub">then paste them back into the session</span></footer>
<pre id="out"></pre>
<script>
/* Each snippet keeps the page frame so the ink lands exactly where the page
   draws it — which leaves one line adrift in a 345x550 canvas. Crop every
   snippet to its own words, measured through the real transform chain. */
for (const svg of document.querySelectorAll('svg.ink')) {
  const words = svg.querySelectorAll('g.word');
  if (!words.length) continue;
  const ctm = svg.getScreenCTM();
  if (!ctm) continue;
  const inv = ctm.inverse();
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const w of words) {
    const r = w.getBoundingClientRect();
    for (const [cx, cy] of [[r.left, r.top], [r.right, r.bottom]]) {
      const pt = new DOMPoint(cx, cy).matrixTransform(inv);
      x0 = Math.min(x0, pt.x); y0 = Math.min(y0, pt.y);
      x1 = Math.max(x1, pt.x); y1 = Math.max(y1, pt.y);
    }
  }
  if (!isFinite(x0)) continue;
  const padX = (x1 - x0) * 0.02 + 1, padY = (y1 - y0) * 0.35 + 1;
  svg.setAttribute('viewBox',
    [x0 - padX, y0 - padY, (x1 - x0) + 2 * padX, (y1 - y0) + 2 * padY].join(' '));
}
/* Arm a word, then click the ink that belongs to it. A move is recorded
   against the piece's OWN geometry, which is what tools/build_overrides.py
   keys an override by — it refuses an edit carrying only an element id. */
const moves = new Map();                       // path element -> target word key

function redraw(c) {
  const box = c.querySelector('.moves');
  const mine = [...c.querySelectorAll('svg.ink path.moved')];
  if (!mine.length) { box.innerHTML = '<em>no moves yet</em>'; return; }
  box.innerHTML = mine.map(p =>
    `<div>${p.dataset.elementId}&nbsp; <b class="ar">${p.dataset.owner}</b>` +
    ` &rarr; <b class="ar">${moves.get(p)}</b>&nbsp; <span style="opacity:.6">` +
    `${p.dataset.box || 'NO GEOMETRY'}</span></div>`).join('');
}

for (const c of document.querySelectorAll('.case')) {
  let armed = null;
  c.querySelectorAll('.sw').forEach(sw => sw.onclick = () => {
    c.querySelectorAll('.sw').forEach(o => o.classList.toggle('armed', o === sw && o !== armed));
    armed = (armed === sw) ? null : sw;
  });
  c.querySelectorAll('svg.ink path').forEach(path => path.onclick = () => {
    if (moves.has(path)) { moves.delete(path); path.classList.remove('moved'); }
    else if (armed) { moves.set(path, armed.dataset.word); path.classList.add('moved'); }
    else { return; }
    redraw(c);
  });
}

document.getElementById('save').onclick = () => {
  const lines = [], notes = [];
  for (const c of document.querySelectorAll('.case')) {
    const page = +c.dataset.page;
    for (const p of c.querySelectorAll('svg.ink path.moved')) {
      lines.push(JSON.stringify({
        id: crypto.randomUUID(), page, step: 'words', kind: 'move-element',
        payload: { element_id: p.dataset.elementId, to: moves.get(p),
                   from: p.dataset.owner, box: p.dataset.box },
        editor: 'abdullah', ts: new Date().toISOString().slice(0, 19),
        status: 'proposed'
      }));
    }
    const v = c.querySelector('select').value, n = c.querySelector('textarea').value;
    if (v || n) notes.push({ page, ayah: c.dataset.ayah, verdict: v, note: n });
  }
  const text = (lines.length ? '# append to .cache/review/edits.jsonl\n' + lines.join('\n') : '')
    + (notes.length ? '\n\n# verdicts\n' + JSON.stringify(notes, null, 1) : '')
    || 'nothing recorded yet';
  document.getElementById('out').textContent = text;
  navigator.clipboard && navigator.clipboard.writeText(text);
};
</script>
"""
    nm = sum(len(r["marks"]) for _, _, r in cases)
    ni = sum(len(r["intervals"]) for _, _, r in cases)
    pages = len({p for p, _, _ in cases})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    page = (doc.replace("@@NM@@", str(nm)).replace("@@NI@@", str(ni))
            .replace("@@PAGES@@", str(pages)).replace("@@ROWS@@", "".join(rows)))
    open(OUT, "w", encoding="utf-8").write(page)
    print("%s: %d cases, %d mark flags, %d interval flags, %d pages"
          % (os.path.relpath(OUT, ROOT), len(cases), nm, ni, pages))


main()
