#!/usr/bin/env python3
"""Build docs/defects/eye_batch.html — the six-detector eye-review page.

Rows come from the detector JSONs (.cache/topmost.json, slashpos.json,
wordheight.json, wordheight_form.json, crossline.json and
docs/defects/tanween_singles.json), ranked by how many independent detectors
convict each word. Every path of a word render is CLICKABLE: a click marks
the piece as "does not belong to this word" (orange), a second click
unmarks; Save posts the verdict, note, and picked eids to /api/eidflag.
"""
import json
import html
import os
import re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".cache", "words-svg", "hafs-kfqc")


def snippet(pg, word_txt, red_fams):
    f = os.path.join(CACHE, "%03d.svg" % pg)
    if not os.path.exists(f):
        return ""
    s = open(f, encoding="utf-8").read()
    i = s.find('data-uthmani="%s"' % word_txt)
    if i < 0:
        i = s.find(word_txt)
        if i < 0:
            return ""
    ws = s.rfind('<g class="word"', 0, i)
    depth = 0
    grp = None
    for mm in re.finditer(r"<g\b|</g>", s[ws:]):
        depth += 1 if mm.group(0) == "<g" else -1
        if depth == 0:
            grp = s[ws:ws + mm.end()]
            break
    if not grp:
        return ""
    for fam in red_fams:
        if not fam:
            continue
        grp = re.sub(r'(<path[^>]*data-mark="%s"[^>]*?)fill="#231f20"'
                     % re.escape(fam), r'\1fill="#c22"', grp)
    root = re.search(r'<g transform="matrix[^"]*">', s)
    vb = re.search(r'viewBox="[^"]*"', s)
    return ('<svg xmlns="http://www.w3.org/2000/svg" %s>%s%s</g></svg>'
            % (vb.group(0) if vb else "", root.group(0) if root else "<g>",
               grp))


_CAPS = {}


def neighbors(pg, word_txt):
    """prev/next in reading order + above/below on adjacent lines, from a
    pipeline capture (word body centers + line clustering)."""
    import assign_words as aw
    if pg not in _CAPS:
        cap = {}
        orig = aw.rewrite
        def spy(page, assignment):
            cap["a"] = assignment
            return orig(page, assignment)
        aw.rewrite = spy
        try:
            aw.assign_page("hafs/kfqc", pg,
                           os.path.join(ROOT, ".cache", "words"))
        except Exception:
            cap["a"] = []
        finally:
            aw.rewrite = orig
        _CAPS[pg] = [(w, at) for (w, at) in cap.get("a", []) if w]
    words = _CAPS[pg]
    recs = []
    for i, (w, at) in enumerate(words):
        els = [e for a in at for e in a["els"]]
        bods = [e for e in els if e["kind"] == "body"] or els
        if not bods:
            continue
        recs.append((i, w, min(e["y1"] for e in bods),
                     min(e["x1"] for e in bods),
                     max(e["x2"] for e in bods)))
    tgt = None
    for i, w, ty, x1, x2 in recs:
        if w["uthmani"] == word_txt:
            tgt = (i, w, ty, x1, x2)
            break
    if tgt is None:
        return {}
    ti, tw, ty, tx1, tx2 = tgt
    out = {}
    if ti > 0:
        out["before"] = words[ti - 1][0]["uthmani"]
    if ti + 1 < len(words):
        out["after"] = words[ti + 1][0]["uthmani"]
    ups = [(abs(ty - oy), w2) for i2, w2, oy, ox1, ox2 in recs
           if 12 < ty - oy < 55 and min(tx2, ox2) - max(tx1, ox1) > 2]
    dns = [(abs(oy - ty), w2) for i2, w2, oy, ox1, ox2 in recs
           if 12 < oy - ty < 55 and min(tx2, ox2) - max(tx1, ox1) > 2]
    if ups:
        out["above"] = min(ups)[1]["uthmani"]
    if dns:
        out["below"] = min(dns)[1]["uthmani"]
    return out


def load_cases():
    cases = defaultdict(list)
    def jload(p):
        p = os.path.join(ROOT, p)
        return json.load(open(p)) if os.path.exists(p) else {}
    for pg, rows in jload(".cache/topmost.json").items():
        for key, txt, mk, why in rows:
            cases[(int(pg), txt)].append((mk, "topmost: [%s] %s" % (mk, why)))
    for pg, rows in jload(".cache/slashpos.json").items():
        for row in rows:
            if len(row) >= 5:
                cases[(int(pg), row[1])].append((row[2],
                                                 "position: %s" % row[4]))
    for h in jload("docs/defects/tanween_singles.json") or []:
        cases[(h["page"], h["word"])].append((None,
                                              "missing %s" % h["missing"]))
    for pg, rows in jload(".cache/wordheight.json").items():
        for key, txt, r, hh, med in rows:
            cases[(int(pg), txt)].append((None,
                                          "height: %.2fx its line" % r))
    for pg, rows in jload(".cache/wordheight_form.json").items():
        for key, txt, r, hh, med in rows:
            cases[(int(pg), txt)].append(
                (None, "form-height: %.2fx its own form" % r))
    for r in jload(".cache/crossline.json") or []:
        cases[(r["page"], r["holder"])].append(
            (r["ink"] if r["ink"] != "body" else None,
             "crossline: holds %s drawn in %s's territory (line %d)"
             % (r["ink"], r["owner"], r["line"])))
    return cases


def main():
    cases = load_cases()
    ranked = sorted(cases.items(), key=lambda kv: (-len(kv[1]), kv[0][0]))
    out = ['<meta charset="utf-8"><title>Eye batch</title>',
           """<style>body{font-family:system-ui;margin:16px auto;max-width:1150px}
.row{display:flex;gap:14px;align-items:center;border:1px solid #ddd;border-radius:8px;padding:8px 12px;margin:6px 0;background:#fff}
.row.hot{background:#fff3ef}.row.hot3{background:#ffe8e0}
.ink{width:250px;height:120px;flex:none}.ink svg{width:100%;height:100%}
.ink path{cursor:pointer}
.ink path.picked{fill:#e67e22 !important;stroke:#e67e22;stroke-width:.6}
.w{font-size:22px;font-family:'KFGQPC Uthmanic Script HAFS',serif}
.n{color:#666;font-size:12.5px;flex:1}
select,input{font-size:12.5px;padding:2px}
button{padding:3px 10px;border:1px solid #bbb;border-radius:5px;background:#f4f4f4;cursor:pointer}
.sv{color:#3e7d4f;font-size:12px}
.pk{color:#e67e22;font-size:11px}
.nbs{display:flex;gap:4px;flex-wrap:wrap;max-width:340px}
.nb{border:1px dashed #ccc;border-radius:6px;padding:2px}
.nbl{font-size:10px;color:#888;text-align:center}
.nbi{width:150px;height:70px}
.nbi path.claimed{fill:#2980b9 !important;stroke:#2980b9;stroke-width:.6}</style>""",
           '<h1>Eye batch — %d words from six detectors</h1>'
           '<p>Red = suspect marks. <b>Click ink in the WORD box that is not its</b> (orange). <b>Click ink in a neighbour box that BELONGS to the word</b> (blue). Save stores both. '
           'belong to the word</b> — it turns orange and its id is saved '
           'with your verdict. Click again to unpick.</p>' % len(ranked)]
    for (pg, txt), notes in ranked:
        fams = {f for f, _ in notes if f}
        ink = snippet(pg, txt, fams)
        hot = " hot3" if len(notes) > 2 else (" hot" if len(notes) > 1 else "")
        key = "%d|%s" % (pg, txt)
        nb = neighbors(pg, txt)
        nbh = "".join(
            '<div class="nb"><div class="nbl">%s</div><div class="ink nbi">%s</div></div>'
            % (lbl, snippet(pg, w2, set()))
            for lbl, w2 in nb.items())
        out.append("""<div class="row%s" data-row="%s"><div class="ink">%s</div>
<div><div class="w">%s</div><a style="font-size:11px;color:#68c" href="/?page=%d&step=audit&user=abdullah">p%d</a></div>
<div class="n">%s</div>
<div class="nbs">%s</div>
<div><select data-k="%s"><option>correct as drawn (art fact)</option><option>wrong name — say in note</option><option>belongs to neighbour</option><option>pair — should weld</option><option>other (note)</option></select><br>
<input data-k="%s" placeholder="note" size="22"><br>
<button data-k="%s">save</button> <span class="sv"></span><br><span class="pk"></span></div></div>"""
            % (hot, html.escape(key), ink, html.escape(txt), pg, pg,
               "<br>".join(html.escape(n) for _, n in notes), nbh,
               html.escape(key), html.escape(key), html.escape(key)))
    out.append("""<script>
document.querySelectorAll('.ink').forEach(box=>{
  box.addEventListener('click',ev=>{
    const p=ev.target.closest('path');
    if(!p)return;
    if(box.classList.contains('nbi')){
      p.classList.toggle('claimed');
      return;
    }
    p.classList.toggle('picked');
    const row=box.closest('.row');
    const ids=[...row.querySelectorAll('path.picked')]
      .map(x=>x.getAttribute('data-eid')).filter(Boolean);
    const pk=row.querySelector('.pk');
    if(pk)pk.textContent=ids.length?('not-mine: '+ids.join(', ')):'';
  });
});
document.querySelectorAll('button[data-k]').forEach(b=>b.onclick=()=>{
  const k=b.dataset.k;
  const row=b.closest('.row');
  const sel=row.querySelector(`select[data-k="${k}"]`).value;
  const note=row.querySelector(`input[data-k="${k}"]`).value;
  const picked=[...row.querySelectorAll('path.picked')]
    .map(x=>x.getAttribute('data-eid')).filter(Boolean);
  const claimed=[...row.querySelectorAll('path.claimed')]
    .map(x=>x.getAttribute('data-eid')).filter(Boolean);
  fetch('/api/eidflag',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({page:parseInt(k), eid:'eye:'+k, correct:sel, note,
                         picked, claimed})})
   .then(()=>{const sv=row.querySelector('.sv');if(sv)sv.textContent='saved ✓';});
});
fetch('/api/eyeflags').then(r=>r.json()).then(d=>{
  Object.entries(d.eyes||{}).forEach(([k,v])=>{
    const sel=document.querySelector(`select[data-k="${k}"]`);
    const inp=document.querySelector(`input[data-k="${k}"]`);
    const btn=document.querySelector(`button[data-k="${k}"]`);
    if(sel&&v.correct)sel.value=v.correct;
    if(inp&&v.note)inp.value=v.note;
    if(btn){const row=btn.closest('.row');
      const sv=row.querySelector('.sv');if(sv)sv.textContent='saved ✓';
      (v.picked||[]).forEach(id=>{
        const p=row.querySelector(`path[data-eid="${id}"]`);
        if(p)p.classList.add('picked');});
      (v.claimed||[]).forEach(id=>{
        row.querySelectorAll(`.nbi path[data-eid="${id}"]`)
          .forEach(p=>p.classList.add('claimed'));});
      const ids=v.picked||[];
      const pk=row.querySelector('.pk');
      if(pk&&ids.length)pk.textContent='not-mine: '+ids.join(', ');
    }
  });
});
document.querySelectorAll('.ink svg').forEach(s=>{try{const bb=s.getBBox();
  if(bb.width&&bb.height)s.setAttribute('viewBox',`${bb.x-4} ${bb.y-4} ${bb.width+8} ${bb.height+8}`);}catch(e){}});
</script>""")
    dst = os.path.join(ROOT, "docs", "defects", "eye_batch.html")
    open(dst, "w", encoding="utf-8").write("\n".join(out))
    multi = sum(1 for _, n in ranked if len(n) > 1)
    print("wrote %s — %d words, %d multi-detector" % (dst, len(ranked), multi))


if __name__ == "__main__":
    main()
