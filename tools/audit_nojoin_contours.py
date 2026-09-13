#!/usr/bin/env python3
"""Where the script says two letters cannot touch, does the ink agree?

    python3 tools/audit_nojoin_contours.py 1 604

A letter in NOJOIN never joins the letter after it, so by the rules of the script the
next letter starts a new stroke: the boundary is free, there is nothing to cut, and
nothing to put to a reviewer. That is only worth relying on where the INK agrees, so this
asks, of every such boundary in the mushaf, whether the two letters really are drawn in
separate pieces -- and asks it of the build's own split, because that is what the drawing
page shows.

It is asked twice: on the label canvas (4 px per unit, where the pipeline works) and on
the geometry at 16 px per unit. A boundary free at 16 and fused at 4 is not the print
fusing anything, it is our raster closing a gap the artwork leaves.
"""
import argparse
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import letters_lib as L                 # noqa: E402
from tools import build_letter_labels as B         # noqa: E402
from tools.build_letter_cuts import align_runs     # noqa: E402

NOJOIN = set("اأإآٱدذرزوؤءةى")
FINE = 16
EIGHT = np.ones((3, 3), bool)


def pieces_of(mask, lab, to_fine=None):
    """The connected pieces of the ink this letter's mask lands in."""
    ys, xs = np.nonzero(mask)
    if to_fine is not None:
        ys, xs = to_fine(ys, xs)
        ok = (ys >= 0) & (xs >= 0) & (ys < lab.shape[0]) & (xs < lab.shape[1])
        ys, xs = ys[ok], xs[ok]
    v = np.unique(lab[ys, xs])
    return set(int(k) for k in v if k)


def page_rows(page):
    try:
        words, _ = L.read_words(page)
    except Exception:
        return []
    out = []
    for w in words:
        try:
            _, runs = align_runs(w)
        except Exception:
            continue
        for lig, idx in (runs or []):
            t = lig["text"]
            if len(idx) < 2 or len(t) != len(idx):
                continue
            breaks = [i for i, ch in enumerate(t[:-1]) if ch in NOJOIN]
            if not breaks:
                continue
            polys = [q for p in lig["paths"] if p["kind"] == "body" and p["d"]
                     for q in L.flatten(p["d"])]
            if not polys:
                continue
            frame = B.canvas_frame(polys)
            ink = B.raster_on_canvas(polys, frame)
            masks = B.build_letter_masks(page, w["wid"], idx, frame, ink)
            coarse, nco = ndimage.label(ink, structure=EIGHT)
            if masks is None or all(m is None for m in masks):
                # the build cannot say -- but the rules and the contour count can: a run
                # drawn in exactly one more piece than it has forbidden boundaries is
                # partitioned by them, with no model and no drawing needed
                out += [(page, w["wid"], t, i,
                         "rule" if nco == len(breaks) + 1 else "no-split") for i in breaks]
                continue
            x0, y0, z = frame
            fx0, fy0, fx1, fy1 = L.bbox(polys)
            fine_img = L.raster(polys, fx0 - 0.3, fy0 - 0.3,
                                (fx1 - fx0) + 0.6, (fy1 - fy0) + 0.6, FINE)
            fine, _ = ndimage.label(fine_img, structure=EIGHT)

            def to_fine(ys, xs):
                return (np.rint((y0 + ys / z - (fy0 - 0.3)) * FINE).astype(int),
                        np.rint((x0 + xs / z - (fx0 - 0.3)) * FINE).astype(int))

            for i in breaks:
                if masks[i] is None or masks[i + 1] is None:
                    out.append((page, w["wid"], t, i, "no-split"))
                    continue
                a, b = pieces_of(masks[i], coarse), pieces_of(masks[i + 1], coarse)
                af, bf = (pieces_of(masks[i], fine, to_fine),
                          pieces_of(masks[i + 1], fine, to_fine))
                if not a or not b or not af or not bf:
                    out.append((page, w["wid"], t, i, "no-split"))
                elif not (a & b):
                    out.append((page, w["wid"], t, i, "free"))
                elif not (af & bf):
                    out.append((page, w["wid"], t, i, "raster"))
                else:
                    out.append((page, w["wid"], t, i, "fused"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("first", type=int)
    ap.add_argument("last", type=int, nargs="?")
    ap.add_argument("--jobs", type=int, default=32)
    ap.add_argument("--show", type=int, default=10)
    a = ap.parse_args()
    pages = list(range(a.first, (a.last or a.first) + 1))
    rows = []
    with ProcessPoolExecutor(min(a.jobs, len(pages))) as ex:
        for r in ex.map(page_rows, pages):
            rows += r
    c = Counter(r[4] for r in rows)
    tot = len(rows)
    print("%s boundaries the joining rules forbid, inside a run of joined ink"
          % "{:,}".format(tot))
    for k, what in (("free", "drawn apart, as the rule says -- never ask for these"),
                    ("rule", "no split in the build, but the contour count settles it"),
                    ("raster", "apart in the artwork, closed by our 4 px/unit raster"),
                    ("fused", "the print really does fuse them -- a line IS needed"),
                    ("no-split", "the build holds no letter there, so it cannot say")):
        print("   %-9s %6s (%4.1f%%)  %s"
              % (k, "{:,}".format(c[k]), 100.0 * c[k] / max(tot, 1), what))
    for k in ("rule", "raster", "fused"):
        by = Counter(r[2] for r in rows if r[4] == k)
        if not by:
            continue
        print("\n%s, most common runs:" % k)
        for t, n in by.most_common(a.show):
            ex1 = next(r for r in rows if r[4] == k and r[2] == t)
            print("   %-8s %5d   e.g. p%d %s" % (t, n, ex1[0], ex1[1]))


if __name__ == "__main__":
    main()
