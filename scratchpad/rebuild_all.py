#!/usr/bin/env python3
"""Rebuild every page SVG into .cache/words-svg/<edition>/ with N workers.

Existing files are overwritten — this is the "no stale cache" rebuild the
handoff keeps asking for. Usage: rebuild_all.py [first] [last] [-jN]
"""
import os
import subprocess
import sys
from multiprocessing import Pool

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "assign_words.py")


def one(pg):
    r = subprocess.run([sys.executable, TOOL, "hafs/kfqc", str(pg)],
                       capture_output=True, text=True)
    return pg, r.returncode, (r.stderr or "")[-400:]


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-j")]
    jobs = next((int(a[2:]) for a in sys.argv[1:] if a.startswith("-j")), 24)
    lo = int(args[0]) if args else 1
    hi = int(args[1]) if len(args) > 1 else 604
    bad = 0
    with Pool(jobs) as p:
        for pg, rc, err in p.imap_unordered(one, range(lo, hi + 1)):
            if rc:
                bad += 1
                print("FAIL %d: %s" % (pg, err), file=sys.stderr)
    print("rebuilt %d pages, %d failures" % (hi - lo + 1, bad))
