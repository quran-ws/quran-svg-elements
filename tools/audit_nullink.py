#!/usr/bin/env python3
"""Contours that draw NOTHING but are counted as ink.

QSVG_NULLMARK already retires a degenerate MARK element (area < 0.5). Nothing
retires a degenerate BODY element, and nothing looks inside a multi-contour
mark, so a null blob can still be counted as a letter piece or as one of a
mark's contours. It is invisible to every existing audit: mark counts are
unchanged (a body is not a mark), the interval/territory audits ignore it, and
it moves no pixel because it paints no pixel.

MEASURED, all 604 pages, 781,732 transformed contour boxes (2026-08-29).
Drawn area of a contour, sorted ascending:

    0.00048 .. 0.0442   47 contours   <- draw nothing at all
    ------------- EMPTY BAND, a factor of 17 -------------
    0.7322 .. 1.2148 (p0.001) .. 17.50 (median) .. up      781,685 contours

Nothing whatsoever between 0.0442 and 0.7322. The threshold is put INSIDE the
band at 0.5 (the same constant QSVG_NULLMARK uses for whole elements), so it
is an order of magnitude clear of the largest null and 1.5x clear below the
smallest real ink. This is a proof, not a prior: a box 0.019 x 0.028 units
across cannot be a letter. (Measured over BODY contours alone the band is
wider still, 0.0443 -> 1.578; the marks supply the 0.73 lower edge.)

Of the 47: 33 are body contours (32 of them the WHOLE element -- a
`<g class="ligature">` piece that draws no ink yet counts toward the word's
piece budget) and 14 are sub-contours of a 2-contour mark, which is exactly
why the element-level NULLMARK test missed them.

Usage: python3 tools/audit_nullink.py [start] [end] [jobs] [--hist]
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

# inside the empty band 0.0443 .. 1.5780 (see the histogram above)
NULL_AREA = 0.5


def scan_page(pg):
    import assign_words as aw
    from svg_lines import transform_box
    cap = {}
    orig = aw.rewrite

    def spy(page, assignment):
        cap["p"] = page
        cap["a"] = assignment
        return orig(page, assignment)

    aw.rewrite = spy
    try:
        aw.assign_page("hafs/kfqc", pg, os.path.join(ROOT, ".cache", "words"))
    except Exception as exc:
        return pg, [{"kind": "CRASH", "err": str(exc)[:160]}], []
    finally:
        aw.rewrite = orig
    if "a" not in cap:
        return pg, [], []
    page = cap["p"]
    flags, areas = [], []
    for word, atoms in cap["a"]:
        if not word:
            continue
        key = "%d:%d:%d" % (word["surah"], word["ayah"], word["pos"])
        for at in atoms:
            seg = at.get("seg") or {}
            for el in at["els"]:
                M = page.paths[el["path"]]["M"]
                boxes = []
                for c in el["contours"]:
                    sp = c["sp"]
                    try:
                        b = transform_box(M, sp["xmin"], sp["ymin"],
                                          sp["xmax"], sp["ymax"])
                    except Exception:
                        continue
                    boxes.append((b[2] - b[0]) * (b[3] - b[1]))
                areas.extend(boxes)
                bad = [a for a in boxes if a < NULL_AREA]
                if not bad:
                    continue
                flags.append({
                    "page": pg, "key": key, "word": word["rasm_uthmani"],
                    "lig": at.get("lig"), "seg": seg.get("text"),
                    "kind": el["kind"], "mark": el.get("mark"),
                    "area": round(min(bad), 6),
                    "n_null": len(bad), "n_contours": len(boxes),
                    "whole_element": len(bad) == len(boxes),
                    "box": [round(el["x1"], 2), round(el["y1"], 2),
                            round(el["x2"], 2), round(el["y2"], 2)],
                })
    return pg, flags, areas


def main():
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    b = int(sys.argv[2]) if len(sys.argv) > 2 else 604
    jobs = int(sys.argv[3]) if len(sys.argv) > 3 else 32
    out, allareas = [], []
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for pg, flags, areas in ex.map(scan_page, range(a, b + 1)):
            out.extend(flags)
            if "--hist" in sys.argv:
                allareas.extend(areas)
    body = [f for f in out if f.get("kind") == "body"]
    mark = [f for f in out if f.get("kind") == "mark"]
    whole = [f for f in body if f.get("whole_element")]
    print("audit_nullink  pages %d-%d" % (a, b))
    print("  null BODY elements (a piece that draws nothing): %d"
          % len(whole))
    print("  null body contours total                       : %d" % len(body))
    print("  null MARK contours (inside a real mark)        : %d" % len(mark))
    print("  pages affected                                 : %d"
          % len({f["page"] for f in out}))
    for f in sorted(out, key=lambda f: (f["kind"], f["page"]))[:60]:
        print("   p%-4d %-12s %-16s %-6s %-11s area=%.5f %s"
              % (f["page"], f["key"], f["word"], f["kind"],
                 f.get("mark") or "-", f["area"],
                 "WHOLE-ELEMENT" if f.get("whole_element") else ""))
    if "--hist" in sys.argv and allareas:
        allareas.sort()
        n = len(allareas)
        print("\n  contour-area distribution (n=%d)" % n)
        for q in (0, .00001, .0001, .001, .01, .1, .5, .9, .99):
            print("    p%-8s %.5f" % (q, allareas[min(n - 1, int(n * q))]))
        prev = None
        for v in allareas[:400]:
            if prev is not None and v - prev > 0.5:
                print("    EMPTY BAND  %.4f -> %.4f" % (prev, v))
            prev = v
    p = os.path.join(ROOT, ".cache", "nullink.json")
    with open(p, "w") as f:
        json.dump({"range": [a, b], "threshold": NULL_AREA, "flags": out},
                  f, ensure_ascii=False, indent=1)
    print("\n  wrote %s" % p)


if __name__ == "__main__":
    main()
