#!/usr/bin/env python3
"""How many separate pieces of ink each letter is emitted as, mushaf-wide.

    python3 tools/audit_letter_pieces.py 1 604 --jobs 32
    python3 tools/audit_letter_pieces.py 1 604 --json docs/defects/letter_pieces.json

A ن or a و is one stroke: its ink is one connected region, and a group holding two
disconnected pieces is a broken cut, not a letter. But the rule is not "one letter, one
piece" -- a medial ك really is an arm plus a bowl, and the tooth of a س really can come
away from its own baseline in this typeface -- so the count that is legal has to be
MEASURED per letter and form rather than assumed.

That is what this reports: for every (letter, form) the distribution of piece counts over
the whole mushaf, the count that dominates it, and the instances that sit outside. Where
the distribution has an empty band -- one shape drawn 3,000 times as a single piece and
never as two -- an outlier is a proof and needs no second signal, the same standing as
the mark audits' empty bands.

Pieces are counted on the ink, not on the path list: the boolean library that builds the
final outlines can split one region across several <path> elements, and can leave a
sliver that no eye would call a piece. Both counts are reported so the two can be told
apart: `paths` over `pieces` is the library's doing, `pieces` over 1 is the cutter's.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import letters_lib as L          # noqa: E402

_LETTER = re.compile(r'<g class="letter"([^>]*)>(.*?)</g>', re.S)
_PATH = re.compile(r'<path ([^>]*?)/>')
Z = 8
MIN_PX = 6          # a blob under this is the library's sliver, not a piece of a letter


def page_rows(page):
    path = os.path.join(L.LETTERS_SVG, "%03d.svg" % page)
    if not os.path.exists(path):
        return []
    words, _ = L.read_words(page, L.LETTERS_SVG)
    out = []
    for w in words:
        groups = defaultdict(list)
        for m in _LETTER.finditer(w["inner"]):
            at = L.parse_attrs(m.group(1))
            if at.get("data-unsplit") == "1":
                continue
            polys, ds = [], []
            for pm in _PATH.finditer(m.group(2)):
                pa = L.parse_attrs(pm.group(1))
                if pa.get("data-kind") == "body" and pa.get("d"):
                    polys += L.flatten(pa["d"])
                    ds.append(pa["d"])
            if polys:
                groups[at.get("data-run", "")].append((at, polys, ds))
        for run, gs in groups.items():
            gs.sort(key=lambda g: int(g[0].get("data-index", 0)))
            for i, (at, polys, ds) in enumerate(gs):
                x0, y0, x1, y1 = L.bbox(polys)
                pad = 0.5
                m = L.raster(polys, x0 - pad, y0 - pad,
                             x1 - x0 + 2 * pad, y1 - y0 + 2 * pad, Z)
                lab, n = ndimage.label(m, structure=np.ones((3, 3), dtype=bool))
                sizes = ndimage.sum(m, lab, range(1, n + 1)) if n else []
                real = int(sum(1 for s in sizes if s >= MIN_PX))
                out.append({"page": page, "wid": w["wid"],
                            "index": int(at.get("data-index", 0)),
                            "ch": at.get("data-text", ""),
                            "form": ("only" if len(gs) == 1 else "first" if i == 0
                                     else "last" if i == len(gs) - 1 else "middle"),
                            "pieces": max(real, 1), "raw_pieces": n, "paths": len(ds),
                            "px": int(m.sum())})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("first", type=int)
    ap.add_argument("last", type=int, nargs="?")
    ap.add_argument("--jobs", type=int, default=32)
    ap.add_argument("--json")
    ap.add_argument("--show", type=int, default=18)
    a = ap.parse_args()
    pages = list(range(a.first, (a.last or a.first) + 1))
    rows = []
    with ProcessPoolExecutor(min(a.jobs, len(pages))) as ex:
        for r in ex.map(page_rows, pages):
            rows += r
    by = defaultdict(Counter)
    for r in rows:
        by[(r["ch"], r["form"])][r["pieces"]] += 1
    total = len(rows)
    multi = [r for r in rows if r["pieces"] > 1]
    print("%s letters over %d pages | %s emitted as more than one piece (%.2f%%)"
          % ("{:,}".format(total), len(pages), "{:,}".format(len(multi)),
             100.0 * len(multi) / max(total, 1)))
    slivers = sum(1 for r in rows if r["raw_pieces"] > r["pieces"])
    split_paths = sum(1 for r in rows if r["paths"] > r["pieces"])
    print("the boolean library's doing: %s letters carry a blob under %d px, %s hold more "
          "<path> elements than pieces" % ("{:,}".format(slivers), MIN_PX,
                                           "{:,}".format(split_paths)))
    print()
    # what each family's piece count NORMALLY is, read from the mushaf rather than assumed.
    # ك final is two pieces 1,857 times and one piece 26 times: for that family a single
    # piece is the defect, and a rule that says "one letter, one piece" would break 1,857
    # correct letters to fix 26.
    norms, bimodal = {}, []
    for (ch, form), c in by.items():
        n = sum(c.values())
        dom, dn = c.most_common(1)[0]
        norms[(ch, form)] = dom
        if n >= 50 and dn / n < 0.90:
            bimodal.append((ch, form, n, dict(c)))
    off = [r for r in rows if r["pieces"] != norms[(r["ch"], r["form"])]]
    print("families whose norm is NOT one piece: " + ", ".join(
        "%s-%s=%d (%s letters)" % (ch, form, d, "{:,}".format(sum(by[(ch, form)].values())))
        for (ch, form), d in sorted(norms.items()) if d != 1) or "(none)")
    print("%s letters differ from their family's norm (%.2f%%)"
          % ("{:,}".format(len(off)), 100.0 * len(off) / max(total, 1)))
    if bimodal:
        print("families with no clear norm (under 90%% agreement), left alone: " + ", ".join(
            "%s-%s %s" % (ch, form, dist) for ch, form, n, dist in bimodal))
    print()
    print("families where a second piece is the exception (the empty band is the proof)")
    print("%-4s %-7s %8s  %-28s %s" % ("ch", "form", "letters", "piece counts", "odd"))
    fams = []
    for (ch, form), c in by.items():
        n = sum(c.values())
        if n < 20:
            continue
        dom, dn = c.most_common(1)[0]
        odd = n - dn
        fams.append((odd, ch, form, n, dom, c))
    for odd, ch, form, n, dom, c in sorted(fams, key=lambda t: -t[0])[:a.show]:
        if odd == 0:
            continue
        dist = " ".join("%d:%s" % (k, "{:,}".format(v)) for k, v in sorted(c.items()))
        print("%-4s %-7s %8s  %-28s %d (%.1f%%)"
              % (ch, form, "{:,}".format(n), dist, odd, 100.0 * odd / n))
    clean = [(ch, form, sum(c.values())) for (ch, form), c in by.items()
             if len(c) == 1 and sum(c.values()) >= 100]
    print("\n%d families of 100+ letters are drawn with the SAME piece count every single "
          "time" % len(clean))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"letters": total,
                   "norms": {"%s|%s" % k: v for k, v in norms.items()},
                   "off_norm": sorted(off, key=lambda r: (r["ch"], r["form"]))[:6000],
                       "families": {"%s|%s" % k: dict(v) for k, v in by.items()},
                       "multi": sorted(multi, key=lambda r: -r["pieces"])[:4000]},
                      f, ensure_ascii=False)
        print("written to", a.json)


if __name__ == "__main__":
    main()
