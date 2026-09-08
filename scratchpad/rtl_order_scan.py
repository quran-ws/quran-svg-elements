#!/usr/bin/env python3
"""How many emitted groups are in right-to-left order? QSVG_RTL on vs off.

For every page: rebuild with QSVG_EIDMAP so each emitted path's eid carries its
bounding box, then walk the emitted SVG and check, per <g class="ligature">,
that the elements come out with x descending, and per <g class="word">, that
its ligature groups do too.

    python3 scratchpad/rtl_order_scan.py [0|1] [first last]
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from multiprocessing import Pool

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
MODE = sys.argv[1] if len(sys.argv) > 1 else "1"


def one(pg):
    td = tempfile.mkdtemp()
    em = os.path.join(td, "e.json")
    env = dict(os.environ, QSVG_ROOT=ROOT, QSVG_EIDMAP=em, QSVG_RTL=MODE)
    subprocess.run([sys.executable, os.path.join(ROOT, "tools",
                                                 "assign_words.py"),
                    "hafs/kfqc", str(pg), "--out-dir", td],
                   capture_output=True, env=env)
    svg = open(os.path.join(td, "%03d.svg" % pg), encoding="utf-8").read()
    box = {r["element_id"]: r["x2"] for r in json.load(open(em))}
    lig = ligbad = word = wordbad = 0
    for wm in re.finditer(r'<g class="word"[^>]*>', svg):
        i = wm.start()
        depth = 0
        grp = svg[i:]
        for mm in re.finditer(r"<g\b|</g>", svg[i:]):
            depth += 1 if mm.group(0) == "<g" else -1
            if depth == 0:
                grp = svg[i:i + mm.end()]
                break
        word += 1
        firsts = []
        for part in re.split(r'(?=<g class="ligature")', grp)[1:]:
            xs = [box[e] for e in re.findall(r'data-element-id="(e\d+)"', part)
                  if e in box]
            if not xs:
                continue
            lig += 1
            if any(a < b for a, b in zip(xs, xs[1:])):
                ligbad += 1
            firsts.append(xs[0])
        if any(a < b for a, b in zip(firsts, firsts[1:])):
            wordbad += 1
    for f in os.listdir(td):
        os.unlink(os.path.join(td, f))
    os.rmdir(td)
    return lig, ligbad, word, wordbad


if __name__ == "__main__":
    lo = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    hi = int(sys.argv[3]) if len(sys.argv) > 3 else 604
    t = [0, 0, 0, 0]
    with Pool(24) as p:
        for r in p.imap_unordered(one, range(lo, hi + 1)):
            for i in range(4):
                t[i] += r[i]
    print("QSVG_RTL=%s pages %d-%d: ligature groups %d, not RTL %d | "
          "words %d, ligature order not RTL %d" % (MODE, lo, hi, *t))
