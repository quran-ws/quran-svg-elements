#!/usr/bin/env python3
"""Which letter pair to teach next, and where the calligrapher already answered it.

    python3 tools/pairs_worklist.py                 # ranked worklist
    python3 tools/pairs_worklist.py --json out.json

The cutter is only as good as its coverage of PAIRS: a joint between two letters is
either taught by a tajweed layer, taught by a drawing of Abdullah's, or guessed. This
ranks the pairs the mushaf actually contains by how many joints are still guessed, so
the next drawing is spent where the ink is, not where the eye happens to land.

Each row also names the page of `docs/khatt_plates.json` that draws that join by hand.
The books are not ground truth -- pen Naskh is not this typeface, and a scan has no
vectors to register -- but they settle the question our own ink cannot answer: given a
stroke shared by two letters, which one owns it. That is a matter of how the script is
built, and the drills state it letter by letter.
"""
import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import letters_lib as L                       # noqa: E402
from tools.build_letters_label_page import pair_coverage  # noqa: E402

PLATES = os.path.join(L.ROOT, "docs", "khatt_plates.json")


def plate_for(ch, book):
    """(book, page) that teaches this letter, or None."""
    if not os.path.exists(PLATES):
        return None
    idx = json.load(open(PLATES, encoding="utf-8"))
    if book == "anatomy":
        v = idx.get("anatomy", {}).get(ch)
        return tuple(v) if v else None
    pages = idx.get("drills", {}).get(ch)
    return ("mizan", pages[0]) if pages else None


def mushaf_pairs():
    """Every adjacent pair inside a run of the mushaf, with its count."""
    import glob
    import numpy as np
    from tools.build_letter_labels import LABELS_DIR
    c = Counter()
    for f in sorted(glob.glob(os.path.join(LABELS_DIR, "*.npz"))):
        meta = json.loads(str(np.load(f)["meta"]))
        for smp in meta:
            t = smp["text"]
            if len(t) != smp["n"]:
                continue
            for i in range(len(t) - 1):
                c[t[i:i + 2]] += 1
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--json")
    a = ap.parse_args()
    counts = mushaf_pairs()
    cov = pair_coverage(set(counts))
    idx = json.load(open(PLATES, encoding="utf-8")) if os.path.exists(PLATES) else {}
    rows = []
    for pr, total in counts.items():
        seen, layered, drawn = cov.get(pr, (0, 0, 0))
        taught = layered + drawn
        rows.append({"pair": pr, "joints": total, "taught": taught,
                     "layers": layered, "drawn": drawn,
                     "guessed": max(total - taught, 0),
                     "drill": (idx.get("drills", {}).get(pr[0]) or [None])[0],
                     "anatomy": (idx.get("anatomy", {}).get(pr[0]) or [None, None])[1]})
    rows.sort(key=lambda r: -r["guessed"])
    tot = sum(r["joints"] for r in rows)
    guessed = sum(r["guessed"] for r in rows)
    untaught = [r for r in rows if r["taught"] == 0]
    print("%d pairs over %s joints | %s joints still guessed (%.0f%%) | %d pairs with "
          "nothing taught at all"
          % (len(rows), "{:,}".format(tot), "{:,}".format(guessed),
             100.0 * guessed / max(tot, 1), len(untaught)))
    print("nothing taught, worst first: " +
          " ".join("%s(%d)" % (r["pair"], r["joints"])
                   for r in sorted(untaught, key=lambda r: -r["joints"])[:18]))
    print()
    print("%-5s %8s %7s %7s %7s   %s" % ("pair", "joints", "layers", "drawn", "guessed",
                                         "the calligrapher draws it at"))
    for r in rows[:a.top]:
        where = []
        if r["drill"]:
            where.append("mizan drills p%d" % r["drill"])
        if r["anatomy"]:
            where.append("anatomy p%d" % r["anatomy"])
        print("%-5s %8s %7d %7d %7d   %s"
              % (r["pair"], "{:,}".format(r["joints"]), r["layers"], r["drawn"],
                 r["guessed"], ", ".join(where) or "-"))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        print("\nwritten to", a.json)


if __name__ == "__main__":
    main()
