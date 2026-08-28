#!/usr/bin/env python3
"""Catalog of every mark shape (signature) with samples in context.

One section per mark family; inside, one row per SIGNATURE: its ink (drawn
red inside a sample word), how many times it occurs, what the table calls it,
sample words with page links — and buttons to flag a wrong label. Flags POST
to /api/siglabel and land in .cache/review/sig_labels.jsonl; they are applied
to labels.json only through the measured path (label_bisect / sweeps).

    python3 tools/build_variants_page.py
    -> docs/defects/variants.html
"""
import glob, html, json, os, re
from collections import Counter, defaultdict

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".cache", "words-svg", "hafs-kfqc")

FAMS = ["fatha", "kasra", "fathatan", "kasratan", "damma", "dammatan",
        "sukun", "shadda", "hamza", "maddah", "wasla", "small-alef",
        "small-waw", "small-ya", "small-noon", "sifr-mustadir",
        "sifr-mustatil", "meem-iqlab", "pause", "saktah", "seen-reading",
        "dot", "two-dots", "three-dots", "sajdah-line", "sajdah-sign", "hizb"]
CHOICES = ["fatha", "kasra", "damma", "sukun", "shadda", "hamza", "maddah",
           "wasla", "small-alef", "small-waw", "small-ya", "meem-iqlab",
           "pause", "dot", "two-dots", "three-dots", "letter", "letter-part",
           "letter-hamza"]


def main():
    occ = defaultdict(list)          # sig -> [(page, word, mark, eid)]
    for f in sorted(glob.glob(CACHE + "/*.svg")):
        pg = int(f[-7:-4])
        svg = open(f, encoding="utf-8").read()
        for m in re.finditer(
                r'<path data-eid="(e\d+)" data-kind="mark" '
                r'(?:data-mark(?:-part)?="([^"]+)" )?[^>]*?data-sig="([0-9a-f]+)"'
                r'(?:[^>]*?data-waqf="([^"]+)")?',
                svg):
            eid, mark, sig = m.group(1), m.group(2) or "?", m.group(3)
            tag_end = svg.find(">", m.start())
            attrs = dict(re.findall(r'data-([a-z-]+)="([^"]*)"',
                                    svg[m.start():tag_end]))
            # EVERY distinguishing attribute makes its own section: the
            # catalog's waqf types, tanween arrangement, iqlab membership,
            # welded parts, standalone signs
            if mark == "pause" and attrs.get("waqf"):
                mark = attrs["waqf"]
            if attrs.get("form"):
                mark += " (%s)" % attrs["form"]
            if attrs.get("iqlab"):
                mark += " (iqlab)"
            if "mark-part" in attrs:
                mark += " [part]"
            if attrs.get("standalone"):
                mark += " [standalone]"
            w0 = svg.rfind('<g class="word"', 0, m.start())
            wt = re.search(r'data-uthmani="([^"]*)"', svg[w0:w0 + 400]) \
                if w0 > -1 else None
            occ[sig].append((pg, wt.group(1) if wt else "", mark, eid, attrs))
    lab = json.load(open(os.path.join(ROOT, ".cache", "marks", "labels.json")))
    # prior review flags (last wins per sig)
    flags, reviewed = {}, {}
    fp = os.path.join(ROOT, ".cache", "review", "sig_labels.jsonl")
    if os.path.exists(fp):
        for line in open(fp, encoding="utf-8"):
            try:
                v = json.loads(line)
            except Exception:
                continue
            if v.get("label") and v["label"] != "reviewed-ok":
                flags[v["sig"]] = v
            if "reviewed" in v or v.get("label") == "reviewed-ok":
                reviewed[v["sig"]] = v.get("reviewed", True)

    def snippet(pg, eid):
        f = os.path.join(CACHE, "%03d.svg" % pg)
        svg = open(f, encoding="utf-8").read()
        m = re.search('<path data-eid="%s"' % eid, svg)
        if not m:
            return ""
        w0 = svg.rfind('<g class="word"', 0, m.start())
        if w0 == -1:
            w0 = svg.rfind("<g ", 0, m.start())
        depth = 0
        for mm in re.finditer(r"<g\b|</g>", svg[w0:]):
            depth += 1 if mm.group(0) == "<g" else -1
            if depth == 0:
                grp = svg[w0:w0 + mm.end()]
                break
        else:
            return ""
        if 'data-eid="%s"' % eid not in grp:
            # a STANDALONE sign (hizb, sajdah) lives outside every word
            # group: the nearest word's group cannot show it. Render the
            # sign's own path alone instead of an unrelated word.
            pe = svg.find(">", m.start())
            tail = svg.find("/>", m.start())
            if tail == -1 or (0 <= pe < tail):
                tail = svg.find("</path>", m.start())
                grp = svg[m.start():tail + 7] if tail > -1 else ""
            else:
                grp = svg[m.start():tail + 2]
            if not grp:
                return ""
        grp = grp.replace('data-eid="%s" ' % eid,
                          'data-eid="%s" style="fill:#c22" ' % eid)
        # the sign's welded parts (the ج's dot, the قلى dots, the small
        # noon's dot) belong to the shape — colour them too so the variant
        # shows the COMPLETE sign
        mk_m = re.search(r'data-eid="%s"[^>]*data-mark="([^"]+)"' % eid, grp)
        if mk_m:
            grp = re.sub(
                r'(<path data-eid="e\d+" data-kind="mark" '
                r'data-mark-part="%s" )' % re.escape(mk_m.group(1)),
                r'\1style="fill:#c22" ', grp)
        root = re.search(r'<g transform="matrix[^"]*">', svg)
        vb = re.search(r'viewBox="[^"]*"', svg)
        return ('<svg xmlns="http://www.w3.org/2000/svg" %s>%s%s</g></svg>'
                % (vb.group(0) if vb else 'viewBox="0 0 345 550"',
                   root.group(0) if root else "<g>", grp))

    by_fam = defaultdict(list)
    for sig, rows in occ.items():
        fam = Counter(m for _, _, m, _, _ in rows).most_common(1)[0][0]
        by_fam[fam].append((sig, rows))

    out = ["""<!doctype html><html><head><meta charset="utf-8">
<title>Mark variants</title><style>
body{font-family:system-ui;margin:20px auto;max-width:1050px;background:#fafafa}
h1{font-size:22px} h2{font-size:18px;margin:24px 0 6px;padding:4px 10px;
background:#eee;border-radius:6px;cursor:pointer}
.row{background:#fff;border:1px solid #ddd;border-radius:8px;padding:10px 14px;
margin:6px 0;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.ink{width:170px;height:80px;} .ink.zoom{width:80px;height:80px;flex:none;border:1px solid #eee;border-radius:6px}
.ink svg{width:100%;height:100%}
.w{font-size:20px;font-family:'KFGQPC Uthmanic Script HAFS',serif}
.k{color:#888;font-size:12px}
.btns button{margin:2px;padding:3px 8px;border:1px solid #bbb;border-radius:5px;
background:#f4f4f4;cursor:pointer;font-size:12px}
.btns button.on{background:#2563eb;color:#fff} .btns button.rvw.on{background:#3e7d4f}
.saved{color:#3e7d4f;font-size:12px;margin-left:6px}
textarea{width:220px;min-height:30px;font:inherit;font-size:12px}
.sec{display:none}.sec.open{display:block}</style></head><body>
<h1>Mark variants — every shape, in place</h1>
<p>Red = this shape inside a real word. Click the correct name if the label is
wrong; it saves immediately. Click a family title to open it.</p>"""]
    # sections ordered by total occurrences, rows within by count;
    # the unnamed group is pinned FIRST — every entry there is a defect
    if "?" in by_fam:
        by_fam["UNNAMED — needs your eye"] = by_fam.pop("?")
    fam_order = sorted(by_fam, key=lambda f: (f != "UNNAMED — needs your eye",
                                              -sum(len(r) for _, r in by_fam[f])))
    for fam in fam_order:
        rows = sorted(by_fam[fam], key=lambda t: -len(t[1]))
        n_rev = sum(1 for sig, _ in rows if reviewed.get(sig, False))
        prog = ('<span class="prog" style="float:left;font-size:14px;color:%s">%s %d/%d reviewed</span>'
                % ("#3e7d4f" if n_rev == len(rows) else "#888",
                   "✓" if n_rev == len(rows) else "", n_rev, len(rows)))
        allrev = ('<a class="revall" href="#" style="float:left;margin-left:12px;'
                  'font-size:12px;color:#68c">mark all reviewed</a>')
        out.append('<h2 onclick="this.nextElementSibling.classList.toggle(\'open\');fitInk(this.nextElementSibling)">'
                   '%s — %d shapes, %d occurrences %s%s</h2><div class="sec">'
                   % (fam, len(rows), sum(len(r[1]) for r in rows), prog, allrev))
        for sig, rws in rows:
            pg0, w0, mk0, eid0, at0 = rws[0]
            v = lab.get(sig)
            tl = (v.get("label") if isinstance(v, dict) else v) or "—"
            auto = v.get("auto", False) if isinstance(v, dict) else False
            # FINAL identification split: what the finished build actually
            # calls this shape, occurrence by occurrence (Abdullah audits the
            # end result, not the table)
            fin = Counter(m for _, _, m, _, _ in rws)
            fin_show = " / ".join("%s %d×" % (k, n)
                                  for k, n in fin.most_common())
            samples = "".join(
                '<span class="w">%s</span> <a class="k" href="/?page=%d&step=audit&user=abdullah">p%d</a> &nbsp;'
                % (html.escape(t), p, p) for p, t, _, _, _ in rws[:3])
            attr_chips = " ".join(
                '<span style="background:#eef;border-radius:4px;'
                'padding:1px 5px;font-size:11px">%s=%s</span>'
                % (html.escape(k), html.escape(v)) for k, v in at0.items()
                if k != "sig")
            fl = flags.get(sig)
            rv = reviewed.get(sig, False)
            state = ((' <span class="saved">your label: %s</span>' % fl["label"])
                     if fl else "")
            btns = ('<button data-sig="%s" data-final="%s" class="rvw%s">✓ reviewed</button>'
                    % (sig, html.escape(fin.most_common(1)[0][0] if fin else ""),
                       " on" if rv else ""))                 + "".join('<button data-sig="%s" data-lab="%s"%s>%s</button>'
                          % (sig, c,
                             ' class="on"' if (fl and fl["label"] == c)
                             or (not fl and c == tl) else "", c)
                          for c in CHOICES)
            tl_show = ("slash — fatha/kasra by position"
                       if tl in ("fatha", "kasra", "fathatan", "kasratan")
                       else ("damma-family — by pairing" if tl in
                             ("damma", "dammatan") else tl))
            snip = snippet(pg0, eid0)
            out.append(
                '<div class="row"><div class="ink">%s</div>'
                '<div class="ink zoom" title="the mark alone">%s</div>'
                '<div style="flex:1;min-width:260px">'
                '<div style="font-size:14px;font-weight:600">final: %s</div>'
                '<div style="margin:3px 0">%s</div>'
                '<div class="k">sig %s · %d× · '
                'table: %s%s%s</div>'
                '<div>%s</div>'
                '<div class="btns">%s</div>'
                '<textarea placeholder="note" data-sig="%s"></textarea>'
                '<span class="saved" id="sv-%s">%s</span></div></div>'
                % (snip, snip, html.escape(fin_show), attr_chips, sig[:12],
                   len(rws), tl_show,
                   " (auto)" if auto else "",
                   (' · <a href="#" class="more" data-sig="%s">view %d samples…</a>'
                    % (sig, min(30, len(rws)))) if len(rws) > 1 else "",
                   samples, btns, sig, sig[:12], state))
        out.append("</div>")
    out.append("""<script>
document.querySelectorAll('.btns button').forEach(b => b.onclick = () => {
  const sig = b.dataset.sig;
  const note = document.querySelector(`textarea[data-sig="${sig}"]`).value;
  if (b.classList.contains('rvw')) {
    // reviewed is a FLAG, independent of the mark type
    const now = !b.classList.contains('on');
    fetch('/api/siglabel', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({sig, reviewed: now, note, final: b.dataset.final || null})})
      .then(() => {
        b.classList.toggle('on', now);
        const sec = b.closest('.sec');
        const h2 = sec.previousElementSibling;
        const total = sec.querySelectorAll('.row').length;
        const done = sec.querySelectorAll('.btns .rvw.on').length;
        const p = h2.querySelector('.prog');
        if (p) {
          p.style.color = done === total ? '#3e7d4f' : '#888';
          p.textContent = (done === total ? '✓ ' : '') + done + '/' + total + ' reviewed';
        }
      });
    return;
  }
  fetch('/api/siglabel', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({sig, label: b.dataset.lab, note, reviewed: true})})
    .then(() => {
      b.parentElement.querySelectorAll('button:not(.rvw)').forEach(x =>
        x.classList.toggle('on', x === b));
      // choosing a type IS a review — flip the flag too
      const rv = b.parentElement.querySelector('.rvw');
      if (rv && !rv.classList.contains('on')) {
        rv.classList.add('on');
        const sec = b.closest('.sec');
        const h2 = sec.previousElementSibling;
        const total = sec.querySelectorAll('.row').length;
        const done = sec.querySelectorAll('.btns .rvw.on').length;
        const p = h2.querySelector('.prog');
        if (p) {
          p.style.color = done === total ? '#3e7d4f' : '#888';
          p.textContent = (done === total ? '✓ ' : '') + done + '/' + total + ' reviewed';
        }
      }
      document.getElementById('sv-' + sig.slice(0,12)).textContent = 'saved ✓';
    });
});
document.querySelectorAll('h2 .revall').forEach(a => a.onclick = (ev) => {
  ev.preventDefault(); ev.stopPropagation();
  const sec = a.closest('h2').nextElementSibling;
  const todo = [...sec.querySelectorAll('.btns .rvw:not(.on)')];
  if (!todo.length) return;
  a.textContent = 'saving 0/' + todo.length;
  let done = 0;
  (async () => {
    for (const b of todo) {
      await fetch('/api/siglabel', {method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({sig: b.dataset.sig, reviewed: true,
                              final: b.dataset.final || null})});
      b.classList.add('on');
      a.textContent = 'saving ' + (++done) + '/' + todo.length;
    }
    a.textContent = 'mark all reviewed';
    const h2 = a.closest('h2');
    const total = sec.querySelectorAll('.row').length;
    const on = sec.querySelectorAll('.btns .rvw.on').length;
    const p = h2.querySelector('.prog');
    if (p) { p.style.color = on === total ? '#3e7d4f' : '#888';
      p.textContent = (on === total ? '✓ ' : '') + on + '/' + total + ' reviewed'; }
  })();
});
function fitInk(scope){
  requestAnimationFrame(() => {
    (scope || document).querySelectorAll('.ink:not(.zoom) svg:not([data-fit])').forEach(s => {
      try { const bb = s.getBBox();
        if (!bb.width || !bb.height) return;
        s.setAttribute('viewBox', `${bb.x-3} ${bb.y-3} ${bb.width+6} ${bb.height+6}`);
        s.dataset.fit = "1";
        const red = s.querySelector('path[style*="c22"]');
        if (!red) return;
        const rb = red.getBBox();
        // halo circle so a 2-unit dot is findable in the word view
        const c = document.createElementNS('http://www.w3.org/2000/svg','circle');
        const r = Math.max(rb.width, rb.height) / 2 + 2.5;
        c.setAttribute('cx', rb.x + rb.width/2);
        c.setAttribute('cy', rb.y + rb.height/2);
        c.setAttribute('r', r);
        c.setAttribute('style',
          'fill:none;stroke:#c22;stroke-width:0.5;opacity:.75');
        red.parentNode.appendChild(c);
        // mark-alone zoom box: its own copy of the ink, viewBox
        // re-targeted to the red path's bbox
        const zsvg = s.closest('.row').querySelector('.ink.zoom svg');
        if (zsvg) {
          const zred = zsvg.querySelector('path[style*="c22"]');
          if (zred) {
            // hide everything but the mark; svg.getBBox() then returns the
            // mark's bbox in viewBox units, transforms included
            const others = [...zsvg.querySelectorAll('path')]
              .filter(p => !(p.getAttribute('style') || '').includes('c22'));
            others.forEach(p => p.style.display = 'none');
            const zb = zsvg.getBBox();
            others.forEach(p => p.style.display = '');
            if (zb.width && zb.height) {
              zsvg.setAttribute('viewBox',
                `${zb.x-1.5} ${zb.y-1.5} ${zb.width+3} ${zb.height+3}`);
              zsvg.dataset.fit = '1';
            }
          }
        }
      } catch(_){}
    });
  });
}
/* live state: paint saved labels + reviewed flags from the server on load */
fetch('/api/siglabels').then(r => r.json()).then(d => {
  for (const [sig, st] of Object.entries(d.sigs)) {
    const btns = document.querySelectorAll(`.btns button[data-sig="${sig}"]`);
    if (!btns.length) continue;
    btns.forEach(b => {
      if (b.classList.contains('rvw')) b.classList.toggle('on', !!st.reviewed);
      else if (st.label) b.classList.toggle('on', b.dataset.lab === st.label);
    });
  }
  document.querySelectorAll('.sec').forEach(sec => {
    const h2 = sec.previousElementSibling;
    const total = sec.querySelectorAll('.row').length;
    const done = sec.querySelectorAll('.btns .rvw.on').length;
    const p = h2 && h2.querySelector('.prog');
    if (p) {
      p.style.color = done === total ? '#3e7d4f' : '#888';
      p.textContent = (done === total ? '✓ ' : '') + done + '/' + total + ' reviewed';
    }
  });
});
const first = document.querySelector('h2').nextElementSibling;
first.classList.add('open');
fitInk(first);
/* modal: 30 in-context samples per shape, loaded on demand */
const modal = document.createElement('div');
modal.style.cssText = 'display:none;position:fixed;inset:4vh 6vw;background:#fff;'
  + 'border:1px solid #999;border-radius:10px;overflow:auto;padding:18px;'
  + 'z-index:99;box-shadow:0 8px 40px rgba(0,0,0,.35)';
document.body.appendChild(modal);
function loadGroup(sig, btn){
  const mk = btn.dataset.mark, off = +btn.dataset.off;
  btn.disabled = true;
  fetch('/api/sigsamples?sig=' + sig + '&mark=' + encodeURIComponent(mk)
        + '&offset=' + off + '&n=30')
    .then(r => r.json()).then(d => {
      const grid = btn.parentElement.querySelector('.mgrid');
      d.samples.forEach(x => {
        const cell = document.createElement('div');
        cell.style.cssText = 'border:1px solid #eee;border-radius:6px;padding:5px';
        const opts = ['fatha','kasra','fathatan','kasratan','damma','dammatan',
                      'hamza','sukun','shadda','maddah','wasla','meem-iqlab',
                      'pause','dot','two-dots','three-dots','letter','letter-part']
          .map(o => '<option' + (o === x.mark ? ' selected' : '') + '>'
                    + o + '</option>').join('');
        cell.innerHTML = '<div style="height:70px">' + x.svg + '</div>'
          + '<div class="w" style="font-size:17px">' + x.word + '</div>'
          + '<a class="k" href="/?page=' + x.page
          + '&step=audit&user=abdullah">p' + x.page + ' · ' + x.eid + '</a> '
          + '<select class="fixsel" style="font-size:11px">' + opts + '</select>'
          + '<button class="fixgo" style="font-size:11px">flag</button>'
          + '<span class="k fixok"></span>';
        cell.querySelector('.fixgo').onclick = () => {
          fetch('/api/eidflag', {method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({page: x.page, eid: x.eid, key: x.key,
              word: x.word, sig: d.sig || '', current: x.mark,
              correct: cell.querySelector('.fixsel').value})})
            .then(() => cell.querySelector('.fixok').textContent = '✓');
        };
        grid.appendChild(cell);
      });
      requestAnimationFrame(() => {
        grid.querySelectorAll('svg:not([data-fit])').forEach(s => {
          try { const bb = s.getBBox();
            if (bb.width && bb.height)
              s.setAttribute('viewBox',
                `${bb.x-2} ${bb.y-2} ${bb.width+4} ${bb.height+4}`);
            s.dataset.fit = '1';
            s.style.width = '100%'; s.style.height = '100%';
          } catch(_){}
        });
      });
      const next = off + d.samples.length;
      btn.dataset.off = next;
      if (next >= +btn.dataset.total) btn.remove();
      else { btn.disabled = false;
             btn.textContent = 'load 30 more (' + next + '/'
               + btn.dataset.total + ')'; }
    });
}
document.addEventListener('click', e => {
  if (e.target.closest('.mclose')) { modal.style.display = 'none'; return; }
  const lm = e.target.closest('.mmore');
  if (lm) { const sig2 = modal.querySelector('h3').textContent.trim().split(' ')[1];
            loadGroup(document.querySelector('a.more[data-sig^="' + sig2 + '"]').dataset.sig, lm);
            return; }
  const a = e.target.closest('a.more');
  if (!a) { if (!modal.contains(e.target)) modal.style.display = 'none'; return; }
  e.preventDefault();
  modal.style.display = 'block';
  modal.innerHTML = '<p>loading…</p>';
  const sig = a.dataset.sig;
  fetch('/api/sigsamples?sig=' + sig + '&groups=1')
    .then(r => r.json()).then(d => {
      modal.innerHTML = '<h3 style="margin-top:0">sig ' + sig.slice(0,12)
        + ' <button class="mclose" style="float:left">close</button></h3>'
        + d.groups.map(([mk, n]) =>
            '<div class="mgrp" data-mark="' + mk + '">'
            + '<h4 style="margin:12px 0 6px">' + mk + ' — ' + n + '×</h4>'
            + '<div class="mgrid" style="display:grid;'
            + 'grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:8px"></div>'
            + '<button class="mmore" data-mark="' + mk + '" data-off="0" '
            + 'data-total="' + n + '" style="margin:6px 0">load 30</button></div>'
          ).join('');
      modal.querySelectorAll('.mmore').forEach(b => loadGroup(sig, b));
    });
});
</script></body></html>""")
    p = os.path.join(ROOT, "docs", "defects", "variants.html")
    open(p, "w", encoding="utf-8").write("\n".join(out))
    n = sum(len(v) for v in by_fam.values())
    print("wrote %s (%d shapes) — open http://127.0.0.1:8777/docs/defects/variants.html"
          % (p, n))


if __name__ == "__main__":
    main()
