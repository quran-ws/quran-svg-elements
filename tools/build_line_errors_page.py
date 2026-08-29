#!/usr/bin/env python3
"""The 14 line-partition sites, WITH and WITHOUT their overrides, side by side.

88 of the 250 surviving overrides are not artwork facts: they are 13 pages where
a whole word's ink sits one position off, 3-13 entries each, every entry shifting
the same way. One fix at the word-boundary stage would retire all 88 — but it
moves body ink on live pages, so it needs an eye first.

The question an eye has to answer is simply: WITHOUT the override, is our word
boundary wrong? So this page rebuilds each site twice — once with its overrides
and once with them stripped — and draws the affected words both ways.
`assign_page()` RETURNS the svg, so neither build touches the cache.
"""
import html
import json
import os
import re
import sys
import tempfile

ROOT = (os.environ.get("QSVG_ROOT")
        or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assign_words as aw  # noqa: E402

PALETTE = ["#c22", "#2a7", "#26c", "#c82", "#82c", "#0a8", "#a26"]


def word_svg(svg, keys):
    """Render the given words out of one page's svg, each word a colour."""
    root = re.search(r'<g transform="matrix[^"]*">', svg)
    vb = re.search(r'viewBox="[^"]*"', svg)
    body, n = [], 0
    for k in keys:
        # the emitter now carries one combined key (data-wid="2:6:3");
        # fall back to the three separate attributes for older builds
        i = svg.find('data-wid="%s"' % k)
        if i < 0:
            su, ay, wd = k.split(":")
            i = svg.find('data-surah="%s" data-ayah="%s" data-word="%s"'
                         % (su, ay, wd))
        if i < 0:
            continue
        ws = svg.rfind("<g class=\"word\"", 0, i)
        depth, grp = 0, None
        for m in re.finditer(r"<g\b|</g>", svg[ws:]):
            depth += 1 if m.group(0) == "<g" else -1
            if depth == 0:
                grp = svg[ws:ws + m.end()]
                break
        if not grp:
            continue
        col = PALETTE[n % len(PALETTE)]
        n += 1
        body.append(re.sub(r'fill="#231f20"', 'fill="%s"' % col, grp))
    if not body:
        return ""
    return ('<svg xmlns="http://www.w3.org/2000/svg" %s>%s%s</g></svg>'
            % (vb.group(0) if vb else "", root.group(0) if root else "<g>",
               "".join(body)))


def main():
    kept = [r for r in json.load(open(os.path.join(
        ROOT, "docs", "defects", "overrides-kept-2026-08-29.json")))
        if "LINE-PARTITION" in str(r.get("reason", ""))]
    ov_all = json.load(open(os.path.join(
        ROOT, ".cache", "review", "overrides.json")))
    ink = {(r.get("page"), r.get("key"))
           for r in json.load(open(os.path.join(
               ROOT, "docs", "defects", "ink_identity.json")))}

    sites = {}
    for r in kept:
        sites.setdefault(r["page"], []).append(r)

    out = ['<meta charset="utf-8"><title>Line-partition sites</title>',
           '<style>body{font-family:system-ui;margin:20px auto;max-width:1180px}',
           'h2{font-size:16px;background:#eee;padding:5px 10px;border-radius:6px}',
           'table{border-collapse:collapse;width:100%}',
           'td,th{padding:6px 8px;border-bottom:1px solid #eee;'
           'vertical-align:top;font-size:13px;text-align:left}',
           '.ink{width:560px}.ink svg{width:560px;height:230px;border:1px solid #eee;border-radius:6px;background:#fff}',
           '.w{font-family:"KFGQPC Uthmanic Script HAFS",serif;font-size:21px}',
           '.q{color:#666;font-size:13px;margin:4px 0 10px}',
           'a{color:#2a6ebb}</style>',
           '<h1>The 14 line-partition sites — with and without their overrides</h1>',
           '<p class="q">88 of the 250 surviving overrides are these. Each is a '
           'word whose ink sits ONE POSITION off. The question for your eye is '
           'only: <b>in the RIGHT column, is our word boundary wrong?</b> If it '
           'is wrong the same way at every site, one fix at the word-boundary '
           'stage retires all 88 and no per-piece override is needed.</p>']

    for pg in sorted(sites):
        rs = sites[pg]
        keys = sorted({r["value"].split("|")[0] for r in rs}
                      | {r.get("from_word") for r in rs if r.get("from_word")})
        keys = [k for k in keys if k and re.match(r"^\d+:\d+:\d+$", k)]
        # WITH overrides (today's build)
        _, svg_on, _, _ = aw.assign_page(
            "hafs/kfqc", pg, os.path.join(ROOT, ".cache", "words"))
        # WITHOUT this page's overrides
        alt = {k: v for k, v in ov_all.items() if k != str(pg)}
        tf = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(alt, tf, ensure_ascii=False)
        tf.close()
        os.environ["QSVG_OVR"] = tf.name
        try:
            _, svg_off, _, _ = aw.assign_page(
                "hafs/kfqc", pg, os.path.join(ROOT, ".cache", "words"))
        finally:
            os.environ.pop("QSVG_OVR", None)
            os.unlink(tf.name)

        ref = [k for (p, k) in ink if p == pg]
        out.append('<h2>p%d — %d override(s)%s</h2>' % (
            pg, len(rs),
            (' · MushafDatabase also disagrees with us at %s'
             % ", ".join(sorted(ref))) if ref else
            ' · with the overrides applied, MushafDatabase agrees with every word here'))
        out.append('<p class="q">%s</p>' % html.escape(
            rs[0].get("reason", "")[:200]))
        out.append('<table><tr><th style="width:50pct">WITH the overrides '
                   '(today)</th><th>WITHOUT them &mdash; is this wrong?</th>'
                   '</tr><tr><td class="ink">{on}</td>'
                   '<td class="ink">{off}</td></tr></table>'
                   .replace("50pct", "50%")
                   .format(on=word_svg(svg_on, keys),
                           off=word_svg(svg_off, keys)))
        rows = []
        for r in rs:
            rows.append('<tr><td class="w">%s</td><td>%s</td><td class="w">%s'
                        '</td><td>%s</td><td><a href="/?page=%d&step=audit&'
                        'user=abdullah&word=%s">open</a></td></tr>'
                        % (r.get("from_text", ""), r.get("from_word", ""),
                           r.get("to_text", ""), r["value"].split("|")[0], pg,
                           r["value"].split("|")[0]))
        out.append('<table><tr><th>from</th><th></th><th>to</th><th></th>'
                   '<th></th></tr>%s</table>' % "".join(rows))

    # Each snippet still carries the whole page's viewBox, so a few words
    # render tiny (Abdullah: "the words in the sample are too small to
    # judge"). Zoom every svg to its own content once it is in the DOM —
    # getBBox() is only available after layout, which is why this is script
    # and not computed here.
    out.append('<script>document.querySelectorAll(".ink svg").forEach(s=>{'
               'try{const b=s.getBBox();if(b.width&&b.height){'
               'const m=Math.max(b.width,b.height)*0.06;'
               's.setAttribute("viewBox",`${b.x-m} ${b.y-m} '
               '${b.width+2*m} ${b.height+2*m}`);'
               's.setAttribute("preserveAspectRatio","xMidYMid meet");'
               '}}catch(e){}});</script>')

    dst = os.path.join(ROOT, "docs", "defects", "line_errors.html")
    open(dst, "w", encoding="utf-8").write("\n".join(out))
    print("wrote %s — %d sites, %d overrides" % (dst, len(sites), len(kept)))


if __name__ == "__main__":
    main()
