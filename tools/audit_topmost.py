#!/usr/bin/env python3
"""Marks that should be the TOPMOST ink over their spot, but are not.

Abdullah's rule (2026-08-28): fathah, dammah and sukun ride ABOVE everything
of their own word at their x — nothing but a waqf/reading sign (which floats
higher still) legitimately sits over them. A "fathah" with letter-body ink
above it is a mis-named or mis-owned stroke: the kasrah inside the ح bowl of
p531 كَلَمْحِۭ and the p97 أَوْ below-letters "fathah" are both this shape of
defect, and no counting audit can see either.

Flags: mark in (fathah, dammah, sukun), non-welded, with a BODY element of the
same word fully above it (body.y2 <= mark.y1 + tol) overlapping >= 30% of
the mark's width. Small overlaps are ignored per the rule.

Usage: python3 tools/audit_topmost.py [start] [end] [jobs]
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

FAMS = ("fathah", "dammah", "sukun")
# waqf signs are the TOPMOST ink of their word, full stop (Abdullah
# 2026-08-28): anything of the same word above one — body OR mark — flags.
WAQF = ("waqf", "waqf_al_muanaqah")


def scan_page(pg):
    import assign_words as aw
    cap = {}
    orig = aw.rewrite
    def spy(page, assignment):
        cap["a"] = assignment
        return orig(page, assignment)
    aw.rewrite = spy
    try:
        aw.assign_page("hafs/kfqc", pg,
                       os.path.join(ROOT, ".cache", "words"))
    except Exception as exc:
        return pg, [("CRASH", "", "", str(exc)[:120])]
    finally:
        aw.rewrite = orig
    if "a" not in cap:
        return pg, []
    flags = []
    for word, atoms in cap["a"]:
        if not word:
            continue
        els = [e for a in atoms for e in a["els"]]
        bods = [e for e in els if e["kind"] == "body"]
        for e in els:
            mk = e.get("mark")
            if mk not in FAMS + WAQF or e.get("mkpart"):
                continue
            w = e["x2"] - e["x1"]
            if w <= 0:
                continue
            over = bods if mk in FAMS else [x for x in els if x is not e
                                            and not x.get("mkpart")]
            for b in over:
                ov = min(e["x2"], b["x2"]) - max(e["x1"], b["x1"])
                if ov < 0.3 * w:
                    continue
                if b["y2"] <= e["y1"] + 0.5:      # fully above the mark
                    key = "%d:%d:%d" % (word["surah"], word["ayah"],
                                        word["pos"])
                    flags.append((key, word["rasm_uthmani"], e["mark"],
                                  "body %.1fu above it, %.0f%% x-overlap"
                                  % (e["y1"] - b["y2"], 100 * ov / w)))
                    break
    return pg, flags


def main():
    a = sys.argv[1:]
    lo = int(a[0]) if a else 1
    hi = int(a[1]) if len(a) > 1 else lo
    jobs = int(a[2]) if len(a) > 2 else 14
    allf = {}
    with ProcessPoolExecutor(jobs) as ex:
        for pg, flags in ex.map(scan_page, range(lo, hi + 1)):
            if flags:
                allf[pg] = flags
    total = sum(len(v) for v in allf.values())
    print("pages %d-%d | flags %d on %d pages" % (lo, hi, total, len(allf)))
    for pg in sorted(allf):
        for key, txt, mk, why in allf[pg]:
            print("  p%d %s %s [%s]: %s" % (pg, key, txt, mk, why))
    out = os.path.join(ROOT, ".cache", "topmost.json")
    json.dump({str(p): v for p, v in allf.items()}, open(out, "w"),
              ensure_ascii=False, indent=1)
    print("wrote", out)


if __name__ == "__main__":
    main()
