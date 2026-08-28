#!/usr/bin/env python3
"""The definitive remaining-issues board, with ink previews.

Regenerates docs/defects/remaining.html from the current sweep dir:
every remaining mark flag and interval record, one row each, with
- a live ink preview of the word, the FLAGGED mark family painted red
- a link opening the review platform with the word highlighted.
"""
import glob
import html
import json
import os
import sys

ROOT = (os.environ.get("QSVG_ROOT")
        or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_eye_batch import snippet  # noqa: E402

SWEEP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    ROOT, ".cache", "sweeps", "r17")

GROUPS = [
    ("Slash strays (fatha/kasra counts)",
     {"fatha", "kasra", "kasratan", "fathatan"}),
    ("Patterned small marks",
     {"small-alef", "small-ya", "small-waw", "hamza", "pause", "meem-iqlab"}),
    ("Dammatan residue", {"damma", "dammatan"}),
    ("Pieces / art cases", {"ligatures", "pieces"}),
]


def main():
    marks, intervals = [], []
    for f in sorted(glob.glob(os.path.join(SWEEP, "*.json"))):
        pg = int(os.path.basename(f)[:-5])
        d = json.load(open(f))
        for r in d.get("marks", []):
            marks.append((pg, r))
        for r in d.get("intervals", []):
            intervals.append((pg, r))

    def row(pg, key, word, badtxt, fams):
        ink = snippet(pg, word, sorted(fams))
        return ('<tr><td class="ink">%s</td><td class="w">%s</td>'
                '<td>%s</td>'
                '<td><a href="/?page=%d&step=audit&user=abdullah&word=%s">'
                'open highlighted</a></td><td class="b">%s</td></tr>'
                % (ink, word, key, pg, key, html.escape(badtxt)))

    grouped = {t: [] for t, _ in GROUPS}
    other = []
    for pg, r in marks:
        fams = {b[0] for b in r["bad"]}
        badtxt = " · ".join("%s %s/%s" % (b[0], b[1], b[2])
                            for b in r["bad"])
        h = row(pg, r["key"], r["word"], badtxt, fams)
        for title, gf in GROUPS:
            if fams & gf:
                grouped[title].append(h)
                break
        else:
            other.append(h)

    out = ['<meta charset="utf-8"><title>Remaining issues</title>',
           '<style>body{font-family:system-ui;margin:20px auto;'
           'max-width:1100px}',
           'h2{font-size:16px;margin:22px 0 6px;background:#eee;'
           'padding:4px 10px;border-radius:6px}',
           'td{padding:4px 10px;border-bottom:1px solid #eee;'
           'vertical-align:middle}',
           '.w{font-size:24px;font-family:"KFGQPC Uthmanic Script HAFS",'
           'serif;white-space:nowrap}',
           'a{color:#68c;text-decoration:none}.b{color:#a33;'
           'font-size:12.5px}',
           '.ink{width:230px;height:95px}.ink svg{width:220px;height:90px}'
           '</style>',
           '<h1>Everything that remains — %d mark flags · %d interval '
           'records</h1>' % (len(marks), len(intervals)),
           '<p>Red ink = the flagged mark family. Every link opens the '
           'review page with the word highlighted.</p>']
    for title, _ in GROUPS:
        rows = grouped[title]
        if rows:
            out.append('<h2>%s — %d words</h2><table>%s</table>'
                       % (title, len(rows), "".join(rows)))
    if other:
        out.append('<h2>Ungrouped — %d words</h2><table>%s</table>'
                   % (len(other), "".join(other)))

    ivr = []
    for pg, r in intervals:
        kind = r.get("kind", r.get("type", "?"))
        wtxt = r.get("holder") or r.get("word") or "?"
        n = r.get("inside") or r.get("neighbor") or ""
        key = r.get("key", "")
        fam = r.get("mark") or r.get("fam") or ""
        ink = snippet(pg, wtxt, [fam] if fam else [])
        ivr.append('<tr><td>%s</td><td class="ink">%s</td>'
                   '<td class="w">%s%s</td><td>%s</td>'
                   '<td><a href="/?page=%d&step=audit&user=abdullah'
                   '&word=%s">open highlighted</a></td></tr>'
                   % (html.escape(str(kind).upper()), ink, wtxt,
                      (" ↔ " + n) if n else "", key, pg, key))
    out.append('<h2>Interval records — %d</h2><table>%s</table>'
               % (len(ivr), "".join(ivr)))
    out.append('<script>document.querySelectorAll(".ink svg").forEach(s=>{'
               'try{const bb=s.getBBox();if(bb.width&&bb.height)'
               's.setAttribute("viewBox",`${bb.x-4} ${bb.y-4} '
               '${bb.width+8} ${bb.height+8}`);}catch(e){}});</script>')

    dst = os.path.join(ROOT, "docs", "defects", "remaining.html")
    open(dst, "w", encoding="utf-8").write("\n".join(out))
    print("wrote %s — %d mark flags, %d interval records"
          % (dst, len(marks), len(intervals)))


if __name__ == "__main__":
    main()
