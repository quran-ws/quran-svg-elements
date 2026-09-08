#!/usr/bin/env python3
"""Which ayah does each medallion close? Measure before writing a rule.

For every page: the marker centres the artwork carries (`ayah:x`/`ayah:y`, page
coordinates, in document order) against the END of every ayah taken from the
pipeline's own assignment — the ayah's LAST word, its leftmost body ink, at that
word's vertical centre. In RTL the medallion follows the last word on its left,
so the two should be a few units apart.

Prints, mushaf-wide: the distance distribution of the nearest match, the margin
to the SECOND nearest ayah end (an empty band there makes the assignment
proof-class), how many pages the document-order pairing gets right today, and
any page that cannot be matched 1:1.

    python3 scratchpad/mark_match.py [first last]
"""
import contextlib
import io
import json
import os
import sys
from multiprocessing import Pool

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))


def one(pg):
    import assign_words as aw
    from page import Page
    cap = {}
    real = aw.rewrite

    def spy(page, assignment):
        cap["a"] = assignment
        cap["p"] = page
        return real(page, assignment)

    aw.rewrite = spy
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            aw.assign_page("hafs/kfqc", pg,
                           os.path.join(ROOT, ".cache", "words"))
    except Exception as e:
        return {"page": pg, "error": str(e)[:200]}
    finally:
        aw.rewrite = real

    page = cap["p"]
    markers = page.markers()                    # document order
    # ayah ends, from the assignment
    ends = {}
    for word, atoms in cap["a"]:
        if not word:
            continue
        bods = [e for a in atoms for e in a["els"] if e["kind"] == "body"]
        if not bods:
            continue
        key = (word["surah"], word["ayah"])
        cur = ends.get(key)
        if cur is None or word["pos"] > cur[0]:
            ends[key] = (word["pos"],
                         min(e["x1"] for e in bods),
                         (min(e["y1"] for e in bods)
                          + max(e["y2"] for e in bods)) / 2.0)
    anchors = [(k, v[1], v[2]) for k, v in ends.items()]

    # polygon order, as tag_ayah_marks uses it today
    polys = json.load(open(os.path.join(
        ROOT, "mushafs", "hafs", "kfqc", "json", "%03d.json" % pg),
        encoding="utf-8")) if os.path.exists(os.path.join(
            ROOT, "mushafs", "hafs", "kfqc", "json",
            "%03d.json" % pg)) else []
    seen = []
    for pl in polys:
        k = (pl["surahNumber"], pl["ayahNumber"])
        if k not in seen:
            seen.append(k)
    seen.sort()

    rows = []
    for idx, (mx, my) in enumerate(markers):
        d = sorted(((abs(mx - ax) + abs(my - ay), k)
                    for k, ax, ay in anchors), key=lambda t: t[0])
        if not d:
            continue
        rows.append({"i": idx, "best": d[0][1], "d1": d[0][0],
                     "d2": d[1][0] if len(d) > 1 else None,
                     "today": seen[idx] if idx < len(seen) else None,
                     "rev": seen[len(markers) - 1 - idx]
                     if len(markers) == len(seen) else None})
    return {"page": pg, "n": len(markers), "rows": rows,
            "anchors": len(anchors)}


if __name__ == "__main__":
    lo = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    hi = int(sys.argv[2]) if len(sys.argv) > 2 else 604
    d1, margins = [], []
    same = diff = 0
    revsame = revdiff = 0
    revbad = []
    pages_ok = pages_bad = 0
    amb, dup, errs = [], [], []
    with Pool(24) as p:
        for r in p.imap_unordered(one, range(lo, hi + 1)):
            if r.get("error"):
                errs.append((r["page"], r["error"]))
                continue
            best = [x["best"] for x in r["rows"]]
            if len(set(best)) != len(best):
                dup.append(r["page"])
            page_changed = False
            for x in r["rows"]:
                d1.append(x["d1"])
                if x["d2"] is not None:
                    margins.append(x["d2"] - x["d1"])
                if x["rev"] is None:
                    revdiff += 1
                    if r["page"] not in revbad:
                        revbad.append(r["page"])
                elif x["rev"] == x["best"]:
                    revsame += 1
                else:
                    revdiff += 1
                    if r["page"] not in revbad:
                        revbad.append(r["page"])
                if x["today"] == x["best"]:
                    same += 1
                else:
                    diff += 1
                    page_changed = True
            if page_changed:
                pages_bad += 1
            else:
                pages_ok += 1

    d1.sort()
    margins.sort()

    def pct(v, q):
        return v[int(q * (len(v) - 1))] if v else None

    print("pages %d-%d | markers %d" % (lo, hi, len(d1)))
    print("nearest-anchor distance: min %.1f p50 %.1f p90 %.1f p99 %.1f "
          "max %.1f" % (d1[0], pct(d1, .5), pct(d1, .9), pct(d1, .99), d1[-1]))
    print("margin to 2nd nearest : min %.1f p1 %.1f p10 %.1f p50 %.1f"
          % (margins[0], pct(margins, .01), pct(margins, .10),
             pct(margins, .5)))
    print("histogram of nearest distance:")
    import collections
    h = collections.Counter(int(v // 5) * 5 for v in d1)
    for k in sorted(h):
        print("   %3d-%3d  %6d" % (k, k + 5, h[k]))
    print("histogram of margin:")
    h2 = collections.Counter(min(int(v // 5) * 5, 60) for v in margins)
    for k in sorted(h2):
        print("   %3d-%3d  %6d" % (k, k + 5, h2[k]))
    print("today's document-order label agrees with position: %d markers, "
          "disagrees: %d" % (same, diff))
    print("position-match == REVERSED document order: %d markers, differs: "
          "%d (pages %s)" % (revsame, revdiff, sorted(revbad)[:20]))
    print("pages already correct: %d | pages that change: %d"
          % (pages_ok, pages_bad))
    print("pages where two markers claim the same ayah: %d %s"
          % (len(dup), sorted(dup)[:20]))
    if errs:
        print("errors:", errs[:5])
