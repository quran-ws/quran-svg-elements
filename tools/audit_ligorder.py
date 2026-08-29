#!/usr/bin/env python3
"""Where a word's ligature groups are DRAWN, against the order the text says.

A word is cut into `<g class="ligature">` groups by the joining rules, and the
groups are numbered in TEXT order. Two purely geometric laws follow, and
neither is checked anywhere: both are INTRA-word, while every existing
position law (intervals, strayink, crossband, crossline, topmost, slashpos)
compares a word to OTHER words. A word can hold exactly its own ink, exactly
its own marks, and still have that ink shared out among its own groups wrongly
-- no count moves, no pixel moves, and the emitted `data-text` lies.

LAW 1 -- ORDER. Arabic runs right to left, so group i+1 must not draw ink to
the RIGHT of where group i ends. Measured over 78,718 consecutive group pairs
(2026-08-29), overshoot = right_edge(i+1) - right_edge(i):

      -60.7 (p999) ......... -8.2 (median) ......... -2.5 (p1)   negative: fine
       0.00 .. 3.24     60 pairs   a following kaf / ain / haa arm or a
                                   kashida reaching back over a preceding
                                   non-joining letter -- real calligraphy
    ------------- EMPTY BAND, 3.24 -> 24.54, twenty-one units -------------
      24.54            1 pair     p366 25:68:20 ذَٰلِكَ

LAW 2 -- CONTIGUITY. A group is by construction ONE joined run, so its body
pieces must touch or nearly touch in x. Measured over the 855 groups that hold
two or more x-disjoint body pieces, largest hole inside a group:

       0.06 .. 4.83   854 groups   the ordinary hairline between two contours
                                   of one run, or a welded pair
    ------------- EMPTY BAND, 4.83 -> 13.95, nine units -------------------
      13.95            1 group     p585 80:38:1 وُجُوهࣱ

Both thresholds are put INSIDE their band at 8.0 units -- 2.5x clear of the
largest legitimate value on law 1, 1.7x clear on law 2, and both are far below
the flagged value. 8.0 units is about two thirds of a letter body's height, so
it cannot be reached by any pen overhang.

Both hits were read by eye and are real (see
docs/defects/NEW-DETECTORS-2026-08-29.md).

Usage: python3 tools/audit_ligorder.py [start] [end] [jobs] [--hist]
"""
import json
import os
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

# inside the empty bands 3.24..24.54 (order) and 4.83..13.95 (contiguity)
LIMIT = 8.0
# a contour this small draws nothing at all (see audit_nullink.py)
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
        return pg, [{"kind": "CRASH", "err": str(exc)[:160]}], [], []
    finally:
        aw.rewrite = orig
    if "a" not in cap:
        return pg, [], [], []
    page = cap["p"]
    flags, h_order, h_gap = [], [], []

    def real(el):
        """el drops out if every contour of it draws nothing."""
        M = page.paths[el["path"]]["M"]
        for c in el["contours"]:
            sp = c["sp"]
            try:
                b = transform_box(M, sp["xmin"], sp["ymin"],
                                  sp["xmax"], sp["ymax"])
            except Exception:
                return True
            if (b[2] - b[0]) * (b[3] - b[1]) >= NULL_AREA:
                return True
        return False

    for word, atoms in cap["a"]:
        if not word:
            continue
        key = "%d:%d:%d" % (word["surah"], word["ayah"], word["pos"])
        groups = defaultdict(list)
        segtext = {}
        for at in atoms:
            li = at.get("lig")
            if li is None:
                continue
            segtext[li] = (at.get("seg") or {}).get("text")
            for el in at["els"]:
                if el["kind"] == "body" and real(el):
                    groups[li].append(el)
        if not groups:
            continue

        # LAW 2 -- contiguity inside one group
        for li, els in groups.items():
            els = sorted(els, key=lambda e: e["x1"])
            reach = els[0]["x2"]
            hole, at_x = 0.0, None
            for e in els[1:]:
                if e["x1"] - reach > hole:
                    hole, at_x = e["x1"] - reach, reach
                reach = max(reach, e["x2"])
            h_gap.append(hole)
            if hole > LIMIT:
                flags.append({
                    "page": pg, "law": "CONTIGUITY", "key": key,
                    "word": word["uthmani"], "lig": li,
                    "seg": segtext.get(li), "hole": round(hole, 2),
                    "at_x": round(at_x, 2) if at_x is not None else None,
                    "pieces": [[round(e["x1"], 2), round(e["x2"], 2)]
                               for e in els],
                })

        # LAW 1 -- right-to-left order of consecutive groups
        ks = sorted(groups)
        for p, q in zip(ks, ks[1:]):
            over = (max(e["x2"] for e in groups[q])
                    - max(e["x2"] for e in groups[p]))
            h_order.append(over)
            if over > LIMIT:
                flags.append({
                    "page": pg, "law": "ORDER", "key": key,
                    "word": word["uthmani"],
                    "lig": q, "prev_lig": p,
                    "seg": segtext.get(q), "prev_seg": segtext.get(p),
                    "overshoot": round(over, 2),
                    "prev_x2": round(max(e["x2"] for e in groups[p]), 2),
                    "x2": round(max(e["x2"] for e in groups[q]), 2),
                })
    return pg, flags, h_order, h_gap


def _band(vals, name, limit):
    vals = sorted(vals, reverse=True)
    if not vals:
        return
    print("\n  %s, largest 12: %s"
          % (name, " ".join("%.2f" % v for v in vals[:12])))
    prev = None
    for v in vals[:400]:
        if prev is not None and prev - v > 2.0:
            print("    EMPTY BAND  %.2f -> %.2f   (limit %.1f is %s)"
                  % (prev, v, limit,
                     "inside" if v < limit < prev else "NOT inside"))
        prev = v


def main():
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    b = int(sys.argv[2]) if len(sys.argv) > 2 else 604
    jobs = int(sys.argv[3]) if len(sys.argv) > 3 else 32
    out, ho, hg = [], [], []
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for pg, flags, a1, a2 in ex.map(scan_page, range(a, b + 1)):
            out.extend(flags)
            if "--hist" in sys.argv:
                ho.extend(a1)
                hg.extend(a2)
    order = [f for f in out if f.get("law") == "ORDER"]
    cont = [f for f in out if f.get("law") == "CONTIGUITY"]
    print("audit_ligorder  pages %d-%d   (limit %.1f units)" % (a, b, LIMIT))
    print("  LAW 1  group drawn right of the group before it : %d" % len(order))
    for f in sorted(order, key=lambda f: -f["overshoot"]):
        print("    p%-4d %-12s %-18s group[%s]=%s starts %.2f right of "
              "group[%s]=%s" % (f["page"], f["key"], f["word"], f["lig"],
                                f["seg"], f["overshoot"], f["prev_lig"],
                                f["prev_seg"]))
    print("  LAW 2  a hole inside one joined group           : %d" % len(cont))
    for f in sorted(cont, key=lambda f: -f["hole"]):
        print("    p%-4d %-12s %-18s group[%s]=%s hole %.2f at x=%s pieces %s"
              % (f["page"], f["key"], f["word"], f["lig"], f["seg"],
                 f["hole"], f["at_x"], f["pieces"]))
    if "--hist" in sys.argv:
        _band(ho, "LAW 1 overshoot", LIMIT)
        _band(hg, "LAW 2 hole", LIMIT)
    p = os.path.join(ROOT, ".cache", "ligorder.json")
    with open(p, "w") as f:
        json.dump({"range": [a, b], "limit": LIMIT, "flags": out},
                  f, ensure_ascii=False, indent=1)
    print("\n  wrote %s" % p)


if __name__ == "__main__":
    main()
