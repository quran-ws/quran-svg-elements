#!/usr/bin/env python3
"""Every shape the letter split produced, grouped so a human can judge them once.

    python3 tools/letter_shapes.py 1 604 --jobs 24      # → .cache/letters/shapes.json

The build emits ~322,000 letters, far too many to look at, but they are not 322,000
different shapes: one letter in one position is drawn much the same way over and over.
So each emitted letter becomes a descriptor — its ink scaled into an 8x8 grid of ink
fractions, which ignores the stretch justification adds and keeps the form — and letters
whose descriptors lie within `--tol` of each other are one CLUSTER.

Exact signatures were tried first and are useless here: at a 12x12 bit grid 15,395
letters gave 11,988 distinct signatures, and even 5x5 gave 3,490, because the ink varies
continuously with kerning and curvature. Distance clustering at tol 2.0 gives about one
shape per eight letters, and the frequent shapes cover most of the mushaf.

Judging a cluster judges every instance in it, so one verdict reaches thousands of
words. `tools/build_letter_shapes_page.py` renders them for review.
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import letters_lib as L          # noqa: E402

G = 8
OUT = os.path.join(L.ROOT, ".cache", "letters",
                   "shapes" + ("-" + L.BUILD_TAG if L.BUILD_TAG else "") + ".json")
_LETTER = re.compile(r'<g class="letter"([^>]*)>(.*?)</g>', re.S)
_PATH = re.compile(r'<path ([^>]*?)/>')


def descriptor(polys):
    """The letter's ink scaled into a G x G grid of ink fractions."""
    x0, y0, x1, y1 = L.bbox(polys)
    w, h = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
    m = L.raster(polys, x0, y0, w, h, 4.0)
    if not m.any():
        return None
    rows, cols = m.shape
    g = np.zeros((G, G), dtype=np.float32)
    for r in range(G):
        r0, r1 = int(r * rows / G), max(int((r + 1) * rows / G), int(r * rows / G) + 1)
        for c in range(G):
            c0, c1 = int(c * cols / G), max(int((c + 1) * cols / G), int(c * cols / G) + 1)
            cell = m[r0:r1, c0:c1]
            g[r, c] = cell.mean() if cell.size else 0.0
    return g.ravel()


def page_rows(page):
    path = os.path.join(L.LETTERS_SVG, "%03d.svg" % page)
    if not os.path.exists(path):
        return []
    words, _ = L.read_words(page, L.LETTERS_SVG)
    out = []
    for w in words:
        groups = []
        for m in _LETTER.finditer(w["inner"]):
            at = L.parse_attrs(m.group(1))
            if at.get("data-unsplit") == "1":
                continue
            polys, ds = [], []
            for pm in _PATH.finditer(m.group(2)):
                pa = L.parse_attrs(pm.group(1))
                if pa.get("data-kind") == "body" and pa.get("d"):
                    polys += L.flatten(pa["d"])
                    ds.append(pa["d"])
            if polys:
                groups.append((at, polys, ds))
        by_run = defaultdict(list)
        for g in groups:
            by_run[g[0].get("data-run", "")].append(g)
        for run, gs in by_run.items():
            gs.sort(key=lambda g: int(g[0].get("data-index", 0)))
            for i, (at, polys, ds) in enumerate(gs):
                d = descriptor(polys)
                if d is None:
                    continue
                x0, y0, x1, y1 = L.bbox(polys)
                out.append({"page": page, "wid": w["wid"], "index": int(at.get("data-index", 0)),
                            "ch": at.get("data-text", ""),
                            "form": ("only" if len(gs) == 1 else "first" if i == 0
                                     else "last" if i == len(gs) - 1 else "middle"),
                            "w": round(x1 - x0, 2), "h": round(y1 - y0, 2),
                            "d": ds, "desc": d.tolist()})
    return out


def cluster(rows, tol):
    """Greedy leader clustering per (letter, form): the first instance opens a cluster
    and every later one joins the nearest leader within `tol`, or opens its own."""
    by = defaultdict(list)
    for r in rows:
        by[(r["ch"], r["form"])].append(r)
    out = []
    for (ch, form), items in by.items():
        leaders = np.zeros((0, G * G), dtype=np.float32)
        members = []
        for r in items:
            v = np.asarray(r["desc"], dtype=np.float32)
            if len(leaders):
                dist = np.linalg.norm(leaders - v, axis=1)
                j = int(dist.argmin())
                if dist[j] <= tol:
                    members[j].append(r)
                    continue
            leaders = np.vstack([leaders, v])
            members.append([r])
        for j, ms in enumerate(members):
            ex = ms[len(ms) // 2]
            out.append({"ch": ch, "form": form, "n": len(ms),
                        "w": round(float(np.median([m["w"] for m in ms])), 2),
                        "h": round(float(np.median([m["h"] for m in ms])), 2),
                        "example": {"page": ex["page"], "wid": ex["wid"],
                                    "index": ex["index"], "d": ex["d"]},
                        "pages": sorted({m["page"] for m in ms})[:6]})
    out.sort(key=lambda c: (c["ch"], c["form"], -c["n"]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("first", type=int)
    ap.add_argument("last", type=int, nargs="?")
    ap.add_argument("--jobs", type=int, default=24)
    ap.add_argument("--tol", type=float, default=2.0)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    pages = list(range(a.first, (a.last or a.first) + 1))
    rows = []
    with ProcessPoolExecutor(min(a.jobs, len(pages))) as ex:
        for r in ex.map(page_rows, pages):
            rows += r
    print("letters %d over %d pages" % (len(rows), len(pages)), flush=True)
    clusters = cluster(rows, a.tol)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(clusters, f, ensure_ascii=False)
    tot = sum(c["n"] for c in clusters)
    run = 0
    half = 0
    for i, c in enumerate(sorted(clusters, key=lambda c: -c["n"]), 1):
        run += c["n"]
        if not half and run >= 0.5 * tot:
            half = i
    per = defaultdict(int)
    for c in clusters:
        per[c["ch"]] += 1
    print("distinct shapes %d, half of every letter drawn covered by %d of them" % (len(clusters), half))
    print("shapes per letter:", dict(sorted(per.items(), key=lambda kv: -kv[1])[:10]))
    print("written to", a.out)


if __name__ == "__main__":
    main()
