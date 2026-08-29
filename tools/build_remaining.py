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
import time

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

    # STALENESS STAMP (Abdullah 2026-08-29): the ink previews are captured
    # from the cached page svgs AT BUILD TIME, so the board silently ages the
    # moment a page is rebuilt — he read p552 off this page and sent eids
    # that had already renumbered. Show both times; if the pages are newer
    # than the board, say so in red.
    import datetime
    cachedir = os.path.join(ROOT, ".cache", "words-svg", "hafs-kfqc")
    newest = max((os.path.getmtime(os.path.join(cachedir, f))
                  for f in os.listdir(cachedir) if f.endswith(".svg")),
                 default=0)
    now = time.time()
    fmt = "%H:%M:%S"
    stamp = ('built %s · newest page build %s'
             % (datetime.datetime.fromtimestamp(now).strftime(fmt),
                datetime.datetime.fromtimestamp(newest).strftime(fmt)))

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
           '<h1>Everything that remains</h1>',
           '<p id="tally"></p>',
           '<p>Red ink = the flagged mark family. Every link opens the '
           'review page with the word highlighted.</p>',
           '<p style="font-size:12px;color:#888">%s — the ink shown here is '
           'a snapshot; if you are sending eids, open the review page and '
           'read them there.</p>' % stamp]
    if not marks:
        out.append('<h2>Mark counts — 0 flags, all 604 pages</h2>')
    for title, _ in GROUPS:
        rows = grouped[title]
        if rows:
            out.append('<h2>%s — %d words</h2><table>%s</table>'
                       % (title, len(rows), "".join(rows)))
    if other:
        out.append('<h2>Ungrouped — %d words</h2><table>%s</table>'
                   % (len(other), "".join(other)))

    # Records a human has examined and confirmed as correct ink are not
    # deleted — deleting them would hide a regression at the same site. They
    # move to their own section, keyed tightly enough that any change to the
    # record brings it straight back to the open list.
    expp = os.path.join(ROOT, ".cache", "review", "explained.json")
    explained = {}
    if os.path.exists(expp):
        try:
            explained = json.load(open(expp))
        except Exception:
            explained = {}

    ivr, ivx = [], []
    for pg, r in intervals:
        kind = r.get("kind", r.get("type", "?"))
        wtxt = r.get("holder") or r.get("word") or "?"
        n = r.get("inside") or r.get("neighbor") or ""
        key = r.get("key", "")
        fam = r.get("mark") or r.get("fam") or ""
        ink = snippet(pg, wtxt, [fam] if fam else [])
        ekey = "%d|%s|%s|%s" % (pg, key, kind, fam)
        (ivx if ekey in explained else ivr).append(
                   '<tr><td>%s</td><td class="ink">%s</td>'
                   '<td class="w">%s%s</td><td>%s</td>'
                   '<td><a href="/?page=%d&step=audit&user=abdullah'
                   '&word=%s">open highlighted</a></td></tr>'
                   % (html.escape(str(kind).upper()), ink, wtxt,
                      (" ↔ " + n) if n else "", key, pg, key))
    out.append('<h2>Interval records — %d</h2>%s<table>%s</table>'
               % (len(ivr),
                  '' if ivr else '<p style="color:#666;font-size:13px">'
                  'Nothing in another word\'s territory anywhere in the '
                  'mushaf.</p>', "".join(ivr)))
    if ivx:
        out.append('<h2>Examined by eye, confirmed correct ink — %d</h2>'
                   '<p style="color:#666;font-size:13px;margin:2px 0 6px">'
                   'Kept, not deleted: if the ink ever moves, these return '
                   'to the open list above.</p><table>%s</table>'
                   % (len(ivx), "".join(ivx)))

    # POSITION dimension — the counting audits are blind to a mark of the
    # right name in the WRONG PLACE, which is most of what Abdullah's eye
    # catches. Each detector writes a {page: [rows]} json; the row's second
    # field is always the word text and the last is the human sentence.
    npos = 0
    for cachename, title, note in (
            ("topmost", "Topmost law",
             "a letter body drawn above a fatha/damma/sukun — forbidden"),
            ("slashpos", "Slash on the wrong side",
             "a fatha below its letters, or a kasra above them — the "
             "name-inversion signature of a mis-owned stroke"),
            ("crossline", "Drawn in another line's territory", ""),
            ("wordheight_form", "Too tall for this word elsewhere",
             "holding ink from another line"),
            ("wordheight", "Taller than its line's pitch",
             "worst first — most of this tail sits 5-10% over the "
             "threshold and is measurement noise, not defects")):
        # audit_crossline writes to docs/defects/, the rest to .cache/ —
        # reading only .cache/ silently showed "crossline 0" while the tool
        # itself had printed 4 findings, one of them the p71 body theft
        # Abdullah then found by eye. Look in both places, newest wins.
        cands = [os.path.join(ROOT, ".cache", "%s.json" % cachename),
                 os.path.join(ROOT, "docs", "defects", "%s.json" % cachename)]
        cands = [c for c in cands if os.path.exists(c)]
        if not cands:
            continue
        f = max(cands, key=os.path.getmtime)
        try:
            data = json.load(open(f))
        except Exception:
            continue
        rows = []
        # crossline writes a LIST of dicts; the others write {page:[rows]}
        if isinstance(data, list):
            data = {}
            for rec in json.load(open(f)):
                data.setdefault(str(rec.get("page")), []).append([
                    rec.get("key", ""), rec.get("holder", "?"),
                    rec.get("mark") or rec.get("kind") or "",
                    "drawn with %s on line %s (%.1fu away vs %.1fu from its "
                    "own word)" % (rec.get("other", "?"),
                                   rec.get("other_line"),
                                   rec.get("gap_other", 0.0),
                                   rec.get("gap_own", 0.0))])
        # worst first: the ratio is the row's first number
        flat = [(pg, r) for pg in data for r in data[pg]]
        flat.sort(key=lambda t: -next(
            (x for x in t[1] if isinstance(x, float)), 0.0))
        for pg, r in flat:
            if True:
                key = r[0]
                wtxt = r[1] if len(r) > 1 else "?"
                fam = r[2] if len(r) > 2 and isinstance(r[2], str) else ""
                why = next((x for x in reversed(r)
                            if isinstance(x, str) and " " in x), "")
                if why == wtxt:
                    why = ""
                if not why and len(r) > 2:
                    why = " · ".join(
                        ("%.2fx" % x) if isinstance(x, float) else str(x)
                        for x in r[2:])
                rows.append(
                    '<tr><td class="ink">%s</td><td class="w">%s</td>'
                    '<td>%s</td>'
                    '<td><a href="/?page=%s&step=audit&user=abdullah'
                    '&word=%s">open highlighted</a></td>'
                    '<td class="b">%s</td></tr>'
                    % (snippet(int(pg), wtxt, [fam] if fam else []),
                       wtxt, key, pg, key, html.escape(str(why))))
        npos += len(rows)
        if not rows:
            out.append('<h2>%s — 0</h2>' % title)
        if rows:
            out.append('<h2>%s — %d</h2>%s<table>%s</table>'
                       % (title, len(rows),
                          ('<p style="color:#666;font-size:13px;'
                           'margin:2px 0 6px">%s</p>' % note) if note else "",
                          "".join(rows)))

    out.append('<script>document.querySelectorAll(".ink svg").forEach(s=>{'
               'try{const bb=s.getBBox();if(bb.width&&bb.height)'
               's.setAttribute("viewBox",`${bb.x-4} ${bb.y-4} '
               '${bb.width+8} ${bb.height+8}`);}catch(e){}});</script>')

    out.append('<script>document.getElementById("tally").textContent = '
               '[...document.querySelectorAll("h2")].map(h=>h.textContent)'
               '.join("  ·  ");</script>')

    dst = os.path.join(ROOT, "docs", "defects", "remaining.html")
    open(dst, "w", encoding="utf-8").write("\n".join(out))
    print("wrote %s — %d mark flags, %d interval records (%d examined), "
          "%d position" % (dst, len(marks), len(ivr), len(ivx), npos))


if __name__ == "__main__":
    main()
