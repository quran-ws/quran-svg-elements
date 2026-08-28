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
                r'(?:data-mark(?:-part)?="([^"]+)" )?[^>]*?data-sig="([0-9a-f]+)"',
                svg):
            eid, mark, sig = m.group(1), m.group(2) or "?", m.group(3)
            w0 = svg.rfind('<g class="word"', 0, m.start())
            wt = re.search(r'data-uthmani="([^"]*)"', svg[w0:w0 + 400]) \
                if w0 > -1 else None
            occ[sig].append((pg, wt.group(1) if wt else "", mark, eid))
    lab = json.load(open(os.path.join(ROOT, ".cache", "marks", "labels.json")))

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
        grp = grp.replace('data-eid="%s" ' % eid,
                          'data-eid="%s" style="fill:#c22" ' % eid)
        root = re.search(r'<g transform="matrix[^"]*">', svg)
        vb = re.search(r'viewBox="[^"]*"', svg)
        return ('<svg xmlns="http://www.w3.org/2000/svg" %s>%s%s</g></svg>'
                % (vb.group(0) if vb else 'viewBox="0 0 345 550"',
                   root.group(0) if root else "<g>", grp))

    by_fam = defaultdict(list)
    for sig, rows in occ.items():
        fam = Counter(m for _, _, m, _ in rows).most_common(1)[0][0]
        by_fam[fam].append((sig, rows))

    out = ["""<!doctype html><html><head><meta charset="utf-8">
<title>Mark variants</title><style>
body{font-family:system-ui;margin:20px auto;max-width:1050px;background:#fafafa}
h1{font-size:22px} h2{font-size:18px;margin:24px 0 6px;padding:4px 10px;
background:#eee;border-radius:6px;cursor:pointer}
.row{background:#fff;border:1px solid #ddd;border-radius:8px;padding:10px 14px;
margin:6px 0;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.ink{width:170px;height:80px;flex:none;border:1px solid #eee;border-radius:6px}
.ink svg{width:100%;height:100%}
.w{font-size:20px;font-family:'KFGQPC Uthmanic Script HAFS',serif}
.k{color:#888;font-size:12px}
.btns button{margin:2px;padding:3px 8px;border:1px solid #bbb;border-radius:5px;
background:#f4f4f4;cursor:pointer;font-size:12px}
.btns button.on{background:#2563eb;color:#fff}
.saved{color:#3e7d4f;font-size:12px;margin-left:6px}
textarea{width:220px;min-height:30px;font:inherit;font-size:12px}
.sec{display:none}.sec.open{display:block}</style></head><body>
<h1>Mark variants — every shape, in place</h1>
<p>Red = this shape inside a real word. Click the correct name if the label is
wrong; it saves immediately. Click a family title to open it.</p>"""]
    for fam in FAMS + sorted(set(by_fam) - set(FAMS)):
        if fam not in by_fam:
            continue
        rows = sorted(by_fam[fam], key=lambda t: -len(t[1]))
        out.append('<h2 onclick="this.nextElementSibling.classList.toggle(\'open\');fitInk(this.nextElementSibling)">'
                   '%s — %d shapes, %d occurrences</h2><div class="sec">'
                   % (fam, len(rows), sum(len(r[1]) for r in rows)))
        for sig, rws in rows:
            pg0, w0, mk0, eid0 = rws[0]
            v = lab.get(sig)
            tl = (v.get("label") if isinstance(v, dict) else v) or "—"
            auto = v.get("auto", False) if isinstance(v, dict) else False
            # FINAL identification split: what the finished build actually
            # calls this shape, occurrence by occurrence (Abdullah audits the
            # end result, not the table)
            fin = Counter(m for _, _, m, _ in rws)
            fin_show = " / ".join("%s %d×" % (k, n)
                                  for k, n in fin.most_common())
            samples = "".join(
                '<span class="w">%s</span> <a class="k" href="/?page=%d&step=audit&user=abdullah">p%d</a> &nbsp;'
                % (html.escape(t), p, p) for p, t, _, _ in rws[:3])
            btns = "".join('<button data-sig="%s" data-lab="%s"%s>%s</button>'
                           % (sig, c, ' class="on"' if c == tl else "", c)
                           for c in CHOICES)
            tl_show = ("slash — fatha/kasra by position"
                       if tl in ("fatha", "kasra", "fathatan", "kasratan")
                       else ("damma-family — by pairing" if tl in
                             ("damma", "dammatan") else tl))
            out.append(
                '<div class="row"><div class="ink">%s</div>'
                '<div style="flex:1;min-width:260px">'
                '<div style="font-size:14px;font-weight:600">final: %s</div>'
                '<div class="k">sig %s · %d× · '
                'table: %s%s%s</div>'
                '<div>%s</div>'
                '<div class="btns">%s</div>'
                '<textarea placeholder="note" data-sig="%s"></textarea>'
                '<span class="saved" id="sv-%s"></span></div></div>'
                % (snippet(pg0, eid0), html.escape(fin_show), sig[:12],
                   len(rws), tl_show,
                   " (auto)" if auto else "",
                   (' · <a href="#" class="more" data-sig="%s">view %d samples…</a>'
                    % (sig, min(30, len(rws)))) if len(rws) > 1 else "",
                   samples, btns, sig, sig[:12]))
        out.append("</div>")
    out.append("""<script>
document.querySelectorAll('.btns button').forEach(b => b.onclick = () => {
  const sig = b.dataset.sig;
  const note = document.querySelector(`textarea[data-sig="${sig}"]`).value;
  fetch('/api/siglabel', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({sig, label: b.dataset.lab, note})})
    .then(() => {
      b.parentElement.querySelectorAll('button').forEach(x =>
        x.classList.toggle('on', x === b));
      document.getElementById('sv-' + sig.slice(0,12)).textContent = 'saved ✓';
    });
});
function fitInk(scope){
  requestAnimationFrame(() => {
    (scope || document).querySelectorAll('.ink svg:not([data-fit])').forEach(s => {
      try { const bb = s.getBBox();
        if (bb.width && bb.height) {
          s.setAttribute('viewBox', `${bb.x-3} ${bb.y-3} ${bb.width+6} ${bb.height+6}`);
          s.dataset.fit = "1";
        }
      } catch(_){}
    });
  });
}
const first = document.querySelector('h2').nextElementSibling;
first.classList.add('open');
fitInk(first);
/* modal: 30 in-context samples per shape, loaded on demand */
const modal = document.createElement('div');
modal.style.cssText = 'display:none;position:fixed;inset:4vh 6vw;background:#fff;'
  + 'border:1px solid #999;border-radius:10px;overflow:auto;padding:18px;'
  + 'z-index:99;box-shadow:0 8px 40px rgba(0,0,0,.35)';
document.body.appendChild(modal);
document.addEventListener('click', e => {
  if (e.target.closest('.mclose')) { modal.style.display = 'none'; return; }
  const a = e.target.closest('a.more');
  if (!a) { if (!modal.contains(e.target)) modal.style.display = 'none'; return; }
  e.preventDefault();
  modal.style.display = 'block';
  modal.innerHTML = '<p>loading…</p>';
  fetch('/api/sigsamples?sig=' + a.dataset.sig + '&n=30')
    .then(r => r.json()).then(d => {
      modal.innerHTML = '<h3 style="margin-top:0">sig ' + d.sig.slice(0,12)
        + ' — ' + d.samples.length + ' samples '
        + '<button class="mclose" style="float:left">close</button></h3>'
        + '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px">'
        + d.samples.map(x =>
            '<div style="border:1px solid #eee;border-radius:6px;padding:6px">'
            + '<div style="height:80px">' + x.svg + '</div>'
            + '<div class="w" style="font-size:18px">' + x.word + '</div>'
            + '<a class="k" href="/?page=' + x.page + '&step=audit&user=abdullah">p'
            + x.page + '</a></div>').join('') + '</div>';
      requestAnimationFrame(() => {
        modal.querySelectorAll('svg').forEach(s => {
          try { const bb = s.getBBox();
            if (bb.width && bb.height)
              s.setAttribute('viewBox',
                `${bb.x-2} ${bb.y-2} ${bb.width+4} ${bb.height+4}`);
            s.style.width = '100%'; s.style.height = '100%';
          } catch(_){}
        });
      });
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
