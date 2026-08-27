#!/usr/bin/env python3
"""Record the waqf signs that cannot be keyed by shape, as places.

`tools/waqf_table.py` keys a waqf sign by its outline signature, which settles ج, صلى,
قلى and م — 4,265 of the 4,272 waqf paths in the mushaf, every signature 100% pure.

The muʿānaqah `ۛ` does not fit that scheme. It is three dots in a triangle, and this
pipeline sees three dots: the cluster comes apart into a `two-dots` element and a `dot`,
neither of which is a pause shape, so no signature of ours corresponds to the sign. It
is also the rarest sign in the mushaf — six occurrences, in three pairs, and a pair is
the whole point of it: the reader stops at one of the two places, never at both.

    2:2   page 2    words 5 and 7
    5:26  page 112  words 5 and 8
    5:41  page 114  words 19 and 24, the pair straddling lines 9 and 10

Six facts about six places. They are written the way this project writes facts about
places — keyed by geometry, in a data file, so they survive pipeline changes — rather
than as a rule inferring a triangle from three dots.

    python3 tools/waqf_places.py "<ref>/SVG V1.01"
"""

import argparse
import contextlib
import importlib.util
import io
import json
import os
import sys
from collections import Counter

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import refdb                                                            # noqa: E402

PIPE = os.environ.get("QSVG_PIPE", os.path.join(ROOT, "tools", "assign_words.py"))
_spec = importlib.util.spec_from_file_location("assign_words", PIPE)
aw = importlib.util.module_from_spec(_spec)
sys.modules["assign_words"] = aw
_spec.loader.exec_module(aw)

_cap = {}
_orig = aw.rewrite


def _spy(page, a):
    _cap["a"] = a
    return _orig(page, a)


aw.rewrite = _spy
OUT = os.path.join(ROOT, ".cache", "marks", "waqf_places.json")

# Which signs to place rather than key by shape. The name here is the
# REFERENCE'S vocabulary (it is matched against MushafDatabase's data-waqf
# attributes); the table is WRITTEN in ours (taxonomy phase 1, decision 8).
BY_PLACE = ("waqf taanuq",)
_CANON = {"waqf lazim": "waqf-lazim", "waqf qila": "waqf-awla",
          "waqf sali": "wasl-awla", "waqf jaiz": "waqf-jaiz",
          "waqf taanuq": "muanaqah"}


def our_page(pg):
    with contextlib.redirect_stdout(io.StringIO()):
        aw.assign_page("hafs/kfqc", pg, os.path.join(ROOT, ".cache", "words"))
    words, els = {}, []
    for w, at in _cap["a"]:
        if not w:
            continue
        ee = [e for a in at for e in a["els"]]
        body = [e for e in ee if e["kind"] == "body"]
        if not body:
            continue
        words[(w["surah"], w["ayah"], w["pos"])] = {
            "x1": min(e["x1"] for e in body), "x2": max(e["x2"] for e in body),
            "y2": max(e["y2"] for e in body), "text": w["uthmani"]}
        els += ee
    return words, els


def _register(ref, mine):
    xs, ys = [], []
    for k in set(ref) & set(mine):
        r, m = ref[k], mine[k]
        if "body_x1" not in r or r["skel"] != refdb.skeleton(m["text"]):
            continue
        xs.append((m["x1"], r["body_x1"]))
        xs.append((m["x2"], r["body_x2"]))
        if "body_y2" in r:
            ys.append((m["y2"], r["body_y2"]))
    return refdb.register(xs, ys, "words") if xs and ys else None


def pages_with(refdir, signs):
    """Which pages draw one of these signs at all — so only those are re-run."""
    import re
    want = set(signs)
    hits = {}
    pat = re.compile(r'data-waqf="([^"]*)"')
    for pg in range(1, 605):
        p = os.path.join(refdir, "%03d.svg" % pg)
        if not os.path.exists(p):
            continue
        found = set(pat.findall(io.open(p, encoding="utf-8-sig").read())) & want
        if found:
            hits[pg] = found
    return hits


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("refdir")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--signs", default=",".join(BY_PLACE))
    args = ap.parse_args(argv)
    signs = tuple(s.strip() for s in args.signs.split(",") if s.strip())

    hits = pages_with(args.refdir, signs)
    print("pages drawing %s: %s" % ("/".join(signs), sorted(hits)))

    table, tally = {}, Counter()
    for pg in sorted(hits):
        rp = refdb.read_page(os.path.join(args.refdir, "%03d.svg" % pg))
        ref = refdb.fold(rp)
        mine, els = our_page(pg)
        reg = _register(ref, mine)
        if reg is None:
            print("   p%-4d no registration — skipped" % pg)
            continue
        occ = 0
        for r in ref.values():
            for kind, lab, b in r["pieces"]:
                if kind != "waqf" or lab not in signs:
                    continue
                occ += 1
                claimed = 0
                for e in els:
                    if e["kind"] == "body":
                        continue
                    ox1, oy1 = reg.x(e["x1"]), reg.y(e["y1"])
                    ox2, oy2 = reg.x(e["x2"]), reg.y(e["y2"])
                    if min(ox2, b[2]) <= max(ox1, b[0]) or min(oy2, b[3]) <= max(oy1, b[1]):
                        continue
                    key = "%.1f,%.1f,%.1f,%.1f" % (e["x1"], e["y1"], e["x2"], e["y2"])
                    # The occurrence id groups the pieces of ONE sign. The muʿānaqah is
                    # three dots, and unless the pipeline knows they are one glyph it
                    # counts them as three letter dots — `ٱلْقَوْمِ` on p112 came out with
                    # five dots where its spelling allows two, the extra three being the
                    # triangle sitting over it.
                    table.setdefault(str(pg), {})[key] = {"waqf": _CANON.get(lab, lab), "occ": occ}
                    claimed += 1
                tally[(pg, lab, claimed)] += 1
    for (pg, lab, n), c in sorted(tally.items()):
        print("   p%-4d %-14s %d occurrence(s), %d of our elements each" % (pg, lab, c, n))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(table, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print("\nwrote %s — %d pages, %d elements"
          % (args.out, len(table), sum(len(v) for v in table.values())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
