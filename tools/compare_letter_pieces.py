#!/usr/bin/env python3
"""Two letter builds side by side: does a change break letters into pieces, or mend them?

    QSVG_LETTERS_TAG=probe python3 tools/compare_letter_pieces.py --against model 1 604

Counts, per build, the letters whose piece count differs from what that letter and form
is normally drawn with (`docs/letter_piece_norms.json`, measured over the whole mushaf).
The norms come from a file rather than from the build being judged, so a change cannot
move the goalposts by making its own mistakes look normal.

Accept only if off-norm letters fall, no family gets worse by more than one, and the ink
is untouched -- ownership may move between letters, ink may not.
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import letters_lib as L               # noqa: E402
from tools import audit_letter_pieces as A       # noqa: E402

NORMS_PATH = os.path.join(L.ROOT, "docs", "letter_piece_norms.json")


def norms():
    if os.path.exists(NORMS_PATH):
        return {tuple(k.split("|")): v for k, v in
                json.load(open(NORMS_PATH, encoding="utf-8"))["norms"].items()}
    raise SystemExit("no %s -- run audit_letter_pieces.py --json first" % NORMS_PATH)


def scan(tag, pages, jobs):
    os.environ["QSVG_LETTERS_TAG"] = tag
    import importlib
    importlib.reload(L)
    importlib.reload(A)
    rows = []
    with ProcessPoolExecutor(min(jobs, len(pages))) as ex:
        for r in ex.map(A.page_rows, pages):
            rows += r
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("first", type=int)
    ap.add_argument("last", type=int, nargs="?")
    ap.add_argument("--against", required=True, help="the build tag to compare with")
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--jobs", type=int, default=32)
    a = ap.parse_args()
    pages = list(range(a.first, (a.last or a.first) + 1, a.step))
    nm = norms()
    here = os.environ.get("QSVG_LETTERS_TAG", "")
    out = {}
    for tag in (a.against, here):
        rows = scan(tag, pages, a.jobs)
        got = [r for r in rows if r["pieces"] != nm.get((r["ch"], r["form"]), 1)]
        by = Counter((r["ch"], r["form"]) for r in got)
        out[tag] = (len(rows), got, by)
        print("%-8s %s letters | %s off their norm (%.2f%%)"
              % (tag or "(untagged)", "{:,}".format(len(rows)), "{:,}".format(len(got)),
                 100.0 * len(got) / max(len(rows), 1)))
    (na, ga, ba), (nb, gb, bb) = out[a.against], out[here]
    if na != nb:
        print("WARNING: the two builds do not hold the same number of letters (%d vs %d)"
              % (na, nb))
    print("\noff-norm letters %d -> %d (%+d)" % (len(ga), len(gb), len(gb) - len(ga)))
    worse = [(k, bb[k] - ba[k]) for k in set(ba) | set(bb) if bb[k] - ba[k] > 0]
    better = [(k, ba[k] - bb[k]) for k in set(ba) | set(bb) if ba[k] - bb[k] > 0]
    print("families improved: %d | families worsened: %d" % (len(better), len(worse)))
    for k, d in sorted(better, key=lambda t: -t[1])[:10]:
        print("   better %-3s %-7s %+d" % (k[0], k[1], -d))
    for k, d in sorted(worse, key=lambda t: -t[1])[:10]:
        print("   WORSE  %-3s %-7s %+d" % (k[0], k[1], d))


if __name__ == "__main__":
    main()
