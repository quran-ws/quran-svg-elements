#!/usr/bin/env python3
"""Centre every ayah medallion's ornament RING on its numeral, in the SOURCE artwork.

Abdullah drew the ornament rings; the NUMERALS are the original KFGQPC ink.
So when the two disagree the RING moves, never the number.

The correction is DERIVED, not tabulated.  For each marker this measures the
numeral's own ink bounding box and the ring's, and adds the difference of their
centres to the ring group's `translate(...)`.  One rule, no per-case table, and
it is right for numbers nobody has looked at.

Why any of them are off at all
------------------------------
Every affected numeral contains the Arabic-Indic digit `٥` (5, 15, 25, 35, 45,
55, 65, 75, 105, 115, 135, 145, 150, 155, 175, 185, 250, 255, ...).  That digit's
glyph origin differs from the others, so the numeral's optical centre drifts
inside a ring that was placed from the number's nominal spot.  The drift is
quantised into a handful of clusters (e.g. for `٥٥`: 0, 0.58, and 2.16 page
units), which is why a measured delta table would fix only the cases someone
happened to look at.

Coordinate space
----------------
The ring group and the numeral group are SIBLINGS inside `<g id="ayah_markers">`,
so they share every ancestor.  All geometry is therefore computed in the marker
block's own space, using each group's OWN transform and nothing else; the delta
in that space is exactly what may be added to the ring's `translate(...)`.
Ancestor transforms (the root `matrix(1.3333 0 0 -1.3333 ...)` with its negative
y scale, and the differing per-file viewBoxes of the surah-variant crops) are
composed only to REPORT offsets in rendered page units, never to compare against
anything measured in another space.

The transform is proved per marker, against a quantity the artwork records and
this script does not use: the numeral group carries `ayah:x`/`ayah:y`, the
medallion centre in page coordinates.  `--proof` prints the residual between it
and our independently computed numeral-box centre.

    python3 tools/centre_medallions.py                     # check, all mushafs
    python3 tools/centre_medallions.py --mushaf hafs --proof
    python3 tools/centre_medallions.py --apply
    python3 tools/centre_medallions.py --hist --json /tmp/m.json

Run it in the ARTWORK repo (`quranpedia/quran-svg`) and commit there; the
decomposition then re-derives from the corrected source.  Nothing in the
pipeline changes.
"""

import argparse
import collections
import json
import math
import os
import re
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audit_medallions import flatten, xform                      # noqa: E402
from page import _matching_close                                 # noqa: E402
from svg_lines import mul, parse_transform                        # noqa: E402

ROOT = (os.environ.get("QSVG_ROOT")
        or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MUSHAFS = ("duri", "hafs", "qalun", "shubah", "warsh")
BLOCK = '<g id="ayah_markers"'
GTAG = re.compile(r"<g\b([^>]*)>", re.S)
CHILD = re.compile(r"<g\b([^>]*)>((?:(?!<g\b).)*?)</g>", re.S)
D_ATTR = re.compile(r'\bd="([^"]*)"')
TRANSFORM = re.compile(r'transform="([^"]*)"')
AYAH_XY = re.compile(r'ayah:x="([-\d.eE+]+)"\s+ayah:y="([-\d.eE+]+)"')
TRANSLATE = re.compile(r"translate\(\s*([-\d.eE+]+)[\s,]+([-\d.eE+]+)\s*\)")

# Default tolerance, in rendered page units.  Justified by the measured
# distribution, not by taste: over all 6,236 hafs medallions the offset between
# the numeral's box centre and the ring's is
#     <=0.25  5,861      0.25-0.38  0 except a single 0.29     >=0.38  375
# i.e. an EMPTY BAND between the placement noise (rounding of the 2-dp
# `translate`, at most ~0.24) and the smallest real misplacement (0.38).  The
# same band is present in all five mushafs.  Put the threshold inside the band.
TOL = 0.30


def fnum(v):
    """Format a coordinate the way the artwork does: plain decimal, no exponent."""
    s = "%.6f" % v
    s = s.rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def ancestor_matrix(svg, upto):
    """Composed transform of every <g> still open at byte offset `upto`."""
    M = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    depth_stack = []
    for m in re.finditer(r"<g\b[^>]*>|</g>", svg[:upto]):
        if m.group(0) == "</g>":
            if depth_stack:
                depth_stack.pop()
            continue
        t = TRANSFORM.search(m.group(0))
        depth_stack.append(parse_transform(t.group(1)) if t else None)
    for T in depth_stack:
        if T is not None:
            M = mul(M, T)
    return M


def bbox_of(d, T):
    """Ink bounding box of path `d` under transform `T`, as (cx, cy, w, h)."""
    cs = [xform(c, T) for c in flatten(d) if len(c) > 1]
    if not cs:
        return None
    p = np.vstack(cs)
    x1, y1 = float(p[:, 0].min()), float(p[:, 1].min())
    x2, y2 = float(p[:, 0].max()), float(p[:, 1].max())
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0, x2 - x1, y2 - y1)


def marks_of(svg):
    """Pair each ornament group with the numeral group that follows it.

    Both are direct children of `<g id="ayah_markers">` and hold exactly one
    <path>.  An ornament carries `scale(...)` in its transform (it is a glyph at
    1/1000 em); a numeral carries only `translate(...)` plus `ayah:x`/`ayah:y`.
    Pairing is by adjacency, which is what the artwork writes; an ornament with
    no numeral after it is reported and skipped, never guessed at.

    On the opening spread (001/002 in every mushaf) each ornament is written
    TWICE, byte-identical, one on top of the other.  A run of ornaments before a
    numeral is therefore returned whole, and every ornament in it is moved by the
    same delta -- moving only one of a duplicated pair would turn an invisible
    duplicate into two visibly offset rings.  A run whose members are NOT
    byte-identical is not a duplicate, so it is reported and left alone.
    """
    i = svg.find(BLOCK)
    if i < 0:
        return [], (1.0, 0.0, 0.0, 1.0, 0.0, 0.0), 0
    j = _matching_close(svg, i)
    A = ancestor_matrix(svg, i)
    block, base = svg[i:j], i
    kids = []
    for m in CHILD.finditer(block):
        attrs, body = m.group(1), m.group(2)
        t = TRANSFORM.search(attrs)
        dm = D_ATTR.search(body)
        if not t:
            continue
        kids.append({
            "scaled": "scale(" in t.group(1),
            "t": t.group(1),
            # A group with no <path> is a numeral the artwork failed to draw
            # (11 of them, all in Qalun); it is carried so the pairing stays in
            # step, and reported rather than measured.
            "d": dm.group(1) if dm else None,
            "xy": AYAH_XY.search(attrs),
            "span": (base + m.start(1) + t.start(1), base + m.start(1) + t.end(1)),
        })
    out, unpaired, k = [], 0, 0
    while k < len(kids):
        if not kids[k]["scaled"]:
            k += 1
            continue
        run = []
        while k < len(kids) and kids[k]["scaled"]:
            run.append(kids[k])
            k += 1
        if k < len(kids) and len({(o["t"], o["d"]) for o in run}) == 1:
            out.append((run, kids[k]))
            k += 1
        else:
            unpaired += len(run)
    return out, A, unpaired


def measure_file(args):
    path, tol = args
    svg = open(path, encoding="utf-8").read()
    pairs, A, unpaired = marks_of(svg)
    ascale = math.hypot(A[0], A[1]) or 1.0
    recs, edits, inkless = [], [], 0
    for run, num in pairs:
        orn = run[0]
        if orn["d"] is None or num["d"] is None:
            inkless += 1
            continue
        To, Tn = parse_transform(orn["t"]), parse_transform(num["t"])
        rb, nb = bbox_of(orn["d"], To), bbox_of(num["d"], Tn)
        if rb is None or nb is None:
            inkless += 1
            continue
        dx, dy = nb[0] - rb[0], nb[1] - rb[1]
        off = math.hypot(dx, dy) * ascale
        pr = xform(np.array([[rb[0], rb[1]], [nb[0], nb[1]]]), A)
        r = {"file": path, "off": round(off, 4),
             "ring_cx": round(float(pr[0][0]), 3), "ring_cy": round(float(pr[0][1]), 3),
             "num_cx": round(float(pr[1][0]), 3), "num_cy": round(float(pr[1][1]), 3),
             "num_w": round(nb[2] * ascale, 3), "num_h": round(nb[3] * ascale, 3)}
        if num["xy"]:
            r["proof"] = round(math.hypot(r["num_cx"] - float(num["xy"].group(1)),
                                          r["num_cy"] - float(num["xy"].group(2))), 4)
        recs.append(r)
        if off > tol:
            t = TRANSLATE.search(orn["t"])
            if not t:
                r["skipped"] = "no translate"
                continue
            new = orn["t"][:t.start()] + "translate(%s %s)" % (
                fnum(float(t.group(1)) + dx), fnum(float(t.group(2)) + dy)
            ) + orn["t"][t.end():]
            r["copies"] = len(run)
            for o in run:                       # duplicated ornaments move together
                edits.append((o["span"][0], o["span"][1], new))
    return path, recs, edits, unpaired, len(pairs), inkless


def hist(vals, edges):
    c = collections.Counter()
    for v in vals:
        for e in edges:
            if v < e:
                c[e] += 1
                break
        else:
            c["inf"] += 1
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mushaf", default="all",
                    help="one of %s, or 'all'" % ",".join(MUSHAFS))
    ap.add_argument("--files", default="", help="comma-separated basenames, e.g. 117.svg")
    ap.add_argument("--skip", default="", help="comma-separated basenames to leave alone")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--tol", type=float, default=TOL)
    ap.add_argument("--jobs", type=int, default=32)
    ap.add_argument("--json", default="")
    ap.add_argument("--proof", action="store_true")
    ap.add_argument("--hist", action="store_true")
    a = ap.parse_args()

    mus = MUSHAFS if a.mushaf == "all" else tuple(a.mushaf.split(","))
    want = set(a.files.split(",")) if a.files else None
    skip = set(a.skip.split(",")) if a.skip else set()
    allrecs, changed_files = [], []
    for mu in mus:
        d = os.path.join(ROOT, "mushafs", mu, "kfqc", "svg")
        if not os.path.isdir(d):
            print("== %-7s NOT CHECKED OUT (%s)" % (mu, d))
            continue
        files = [os.path.join(d, f) for f in sorted(os.listdir(d))
                 if f.endswith(".svg") and f not in skip
                 and (want is None or f in want)]
        with Pool(min(a.jobs, max(1, len(files)))) as pool:
            res = pool.map(measure_file, [(f, a.tol) for f in files], chunksize=4)
        recs = [r for _, rr, _, _, _, _ in res for r in rr]
        unp = sum(u for _, _, _, u, _, _ in res)
        ink = sum(k for _, _, _, _, _, k in res)
        nmark = sum(n for _, _, _, _, n, _ in res)
        offs = [r["off"] for r in recs]
        bad = [r for r in recs if r["off"] > a.tol]
        for path, _, edits, _, _, _ in res:
            if edits and a.apply:
                svg = open(path, encoding="utf-8").read()
                for s0, s1, new in sorted(edits, reverse=True):
                    svg = svg[:s0] + new + svg[s1:]
                open(path, "w", encoding="utf-8").write(svg)
                changed_files.append(path)
            elif edits:
                changed_files.append(path)
        print("== %-7s files %d | markers %d | unpaired ornaments %d | "
              "numeral has no ink %d | off-centre >%.2fu: %d (%.2f%%) on %d files"
              % (mu, len(files), nmark, unp, ink, a.tol, len(bad),
                 100.0 * len(bad) / max(1, nmark),
                 len({r["file"] for r in bad})))
        if offs:
            offs_s = sorted(offs)
            print("   offset page units: median %.3f  p99 %.3f  max %.3f"
                  % (offs_s[len(offs_s) // 2], offs_s[int(len(offs_s) * 0.99)],
                     offs_s[-1]))
        if a.proof:
            pr = [r["proof"] for r in recs if "proof" in r]
            if pr:
                pr.sort()
                print("   transform proof (our numeral centre vs the artwork's "
                      "ayah:x/y, page units): n=%d median %.4f p99 %.4f max %.4f"
                      % (len(pr), pr[len(pr) // 2], pr[int(len(pr) * 0.99)], pr[-1]))
        if a.hist and offs:
            edges = [0.01, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5,
                     0.6, 0.8, 1.0, 1.5, 2.0, 2.5]
            h = hist(offs, edges)
            for e in edges + ["inf"]:
                if h.get(e):
                    print("     <%-5s %5d" % (e, h[e]))
        for r in recs:
            r["mushaf"] = mu
        allrecs += recs

    if a.json:
        json.dump(allrecs, open(a.json, "w"), indent=1)
        print("measurements -> %s" % a.json)
    print("%s %d files" % ("REWROTE" if a.apply else "would rewrite",
                           len(changed_files)))


if __name__ == "__main__":
    main()
