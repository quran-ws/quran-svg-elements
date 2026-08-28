#!/usr/bin/env python3
"""One page with EVERY audit mismatch the code finds — no human input involved.

Reads the current sweep (newest of tax2/tax1), and for each flagged word shows
the word's ink (extracted from the cached review SVG), the word text, and the
expected-vs-held line per mark family, plus a link to the full page.

    python3 tools/build_mismatch_page.py
    -> docs/defects/mismatches.html  (serve: /docs/defects/mismatches.html)
"""
import glob, html, json, os, re

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".cache", "words-svg", "hafs-kfqc")


def newest_sweep():
    for d in ("jaa-full", "lredeal-full", "drift", "i39full", "i36", "tax2", "tax1"):
        p = os.path.join(ROOT, ".cache", "sweeps", d)
        if os.path.isdir(p) and len(glob.glob(p + "/*.json")) > 500:
            return p, d
    raise SystemExit("no full sweep found")


def word_snippet(page, key):
    """Standalone SVG of one word group from the cached page build."""
    f = os.path.join(CACHE, "%03d.svg" % page)
    if not os.path.exists(f):
        return None
    svg = open(f, encoding="utf-8").read()
    s, a, w = key.split(":")
    m = re.search(r'<g class="word"[^>]*data-surah="%s"[^>]*data-ayah="%s"[^>]*data-word="%s"[^>]*>' % (s, a, w), svg)
    if not m:
        return None
    g0 = m.start()
    depth = 0
    for mm in re.finditer(r"<g\b|</g>", svg[g0:]):
        depth += 1 if mm.group(0) == "<g" else -1
        if depth == 0:
            grp = svg[g0:g0 + mm.end()]
            break
    else:
        return None
    root = re.search(r'<g transform="matrix[^"]*">', svg)
    vb = re.search(r'viewBox="[^"]*"', svg)
    return ('<svg xmlns="http://www.w3.org/2000/svg" %s>%s%s</g></svg>'
            % (vb.group(0) if vb else 'viewBox="0 0 345 550"',
               root.group(0) if root else "<g>", grp))


def main():
    sweep, name = newest_sweep()
    rows = []
    for f in sorted(glob.glob(sweep + "/*.json")):
        j = json.load(open(f))
        for m in j.get("marks", []):
            rows.append((j["page"], m["key"], m["word"],
                         ["%s: held %s, expected %s" % (b[0], b[1], b[2])
                          for b in m["bad"]], "mark counts"))
        for i in j.get("intervals", []):
            rows.append((j["page"], i.get("key", "?"),
                         i.get("holder", ""),
                         ["%s: %s holds a %s inside %s's territory"
                          % (i.get("kind"), i.get("holder"), i.get("mark", "mark"),
                             i.get("inside"))], "territory"))
    out = ["""<!doctype html><html><head><meta charset="utf-8">
<title>Audit mismatches</title><style>
body{font-family:system-ui;margin:20px auto;max-width:980px;background:#fafafa}
.card{background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px 16px;
margin:8px 0;display:flex;gap:16px;align-items:center}
.ink{width:190px;height:90px;flex:none;border:1px solid #eee;border-radius:6px;background:#fff}
.ink svg{width:100%;height:100%}
.w{font-size:26px;font-family:'KFGQPC Uthmanic Script HAFS',serif}
.bad{color:#b0453a;font-size:14px}
.k{color:#888;font-size:12px}
a.go{background:#2563eb;color:#fff;padding:6px 12px;border-radius:6px;
text-decoration:none;font-size:13px;margin-left:auto;flex:none}
h1{font-size:22px}</style></head><body>"""]
    out.append("<h1>Audit mismatches — found by code, not by eye</h1>")
    out.append("<p>%d mismatches from sweep <b>%s</b>. Every card: the ink, the word, "
               "and what disagrees.</p>" % (len(rows), name))
    for pg, key, word, bads, kind in rows:
        snip = word_snippet(pg, key) or "<span class='k'>no preview</span>"
        out.append(
            '<div class="card"><div class="ink">%s</div>'
            '<div><div class="w">%s</div><div class="k">p%d · %s · %s</div>'
            '%s</div>'
            '<a class="go" href="/?page=%d&step=audit&user=abdullah">open page</a></div>'
            % (snip, html.escape(word), pg, key, kind,
               "".join('<div class="bad">%s</div>' % html.escape(b) for b in bads),
               pg))
    out.append("""<script>
requestAnimationFrame(() => {
  document.querySelectorAll('.ink svg').forEach(s => {
    try { const bb = s.getBBox();
      if (bb.width && bb.height)
        s.setAttribute('viewBox', `${bb.x-2} ${bb.y-2} ${bb.width+4} ${bb.height+4}`);
    } catch(_){}
  });
});
</script></body></html>""")
    p = os.path.join(ROOT, "docs", "defects", "mismatches.html")
    open(p, "w", encoding="utf-8").write("\n".join(out))
    print("wrote %s (%d cards) — open http://127.0.0.1:8777/docs/defects/mismatches.html"
          % (p, len(rows)))


if __name__ == "__main__":
    main()
