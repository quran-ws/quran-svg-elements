"""Measure how the ayah-mark ORNAMENT rings fit, mushaf-wide.

The rings are not original ink: they were drawn around the existing ayah numerals
in the artwork repo, so their scale and offset are parameters, and this audit says
whether they are right.  Three questions, all answered in ONE coordinate space:

    CONTAINMENT   is the numeral fully inside the ring's central hole, and centred?
    CLEARANCE     how close does the ring's outer ink come to any non-mark ink?
    FIT           is the ring the right size for the numeral it encircles?

Coordinate space
----------------
Everything is reported in RENDERED PAGE UNITS: the SVG user space of the root
`viewBox="0 0 345 550"`, x rightwards, y downwards from the top of the page.
Every point is pushed through its full ancestor chain, which for a marker is the
root `matrix(1.3333 0 0 -1.3333 -55 640)` (note the NEGATIVE y scale) composed
with the marker group's own `translate(...) scale(0.011 -0.011)`.  Nothing here
compares a glyph-space number with a page-space one.

The transform is proved per marker: the artwork carries the medallion centre as
`ayah:x`/`ayah:y` on the numeral group, in page coordinates, and the computed
ring-hole centre must land on it.  `--proof` prints that residual.

Usage:
    python3 tools/audit_medallions.py                 # all 604 pages -> JSON
    python3 tools/audit_medallions.py --pages 3 10 --proof
"""

import argparse
import json
import math
import os
import re
import sys
from multiprocessing import Pool

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from page import Page, _matching_close                       # noqa: E402
from svg_lines import mul, parse_transform, subpaths, tokenize          # noqa: E402

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))
EDITION = "hafs/kfqc"

MARK_BLOCK = '<g id="ayah_markers"'
GROUP = re.compile(r"<g\b([^>]*)>((?:(?!</?g\b).)*)</g>", re.S)
D_ATTR = re.compile(r'\bd="([^"]*)"')
AYAH_XY = re.compile(r'ayah:x="([-\d.]+)"\s+ayah:y="([-\d.]+)"')
TRANSFORM = re.compile(r'transform="([^"]*)"')

# Curve flattening: each cubic/quad becomes CURVE_STEPS chords, then every chord
# longer than MAX_CHORD page units is subdivided, so a nearest-point distance is
# never wrong by more than MAX_CHORD/2 = 0.02 units (the ring is ~14 units wide).
# Candidate uniform shrinks of the ring about its own centre, the one knob the
# artwork exposes (the ornament is placed by `translate(...) scale(s -s)`).
SCALES = (0.98, 0.96, 0.95, 0.94, 0.93, 0.92, 0.91, 0.90, 0.88, 0.85, 0.80)
CURVE_STEPS = 8
MAX_CHORD = 0.04


# ---------------------------------------------------------------------------
# Path flattening
# ---------------------------------------------------------------------------

def flatten(d):
    """`d` -> list of contours, each an (N, 2) float array in the path's own space."""
    out, cur = [], []
    cx = cy = sx = sy = 0.0
    prev_ctrl, prev_kind = None, None

    def cubic(p0, p1, p2, p3):
        t = np.linspace(0.0, 1.0, CURVE_STEPS + 1)[1:]
        mt = 1.0 - t
        xs = (mt ** 3 * p0[0] + 3 * mt ** 2 * t * p1[0]
              + 3 * mt * t ** 2 * p2[0] + t ** 3 * p3[0])
        ys = (mt ** 3 * p0[1] + 3 * mt ** 2 * t * p1[1]
              + 3 * mt * t ** 2 * p2[1] + t ** 3 * p3[1])
        return list(zip(xs, ys))

    def quad(p0, p1, p2):
        t = np.linspace(0.0, 1.0, CURVE_STEPS + 1)[1:]
        mt = 1.0 - t
        xs = mt ** 2 * p0[0] + 2 * mt * t * p1[0] + t ** 2 * p2[0]
        ys = mt ** 2 * p0[1] + 2 * mt * t * p1[1] + t ** 2 * p2[1]
        return list(zip(xs, ys))

    for cmd, a, _s, _e in tokenize(d):
        rel = cmd.islower()
        c = cmd.lower()
        if c == "m":
            if cur:
                out.append(np.asarray(cur, float))
            nx = cx + a[0] if rel else a[0]
            ny = cy + a[1] if rel else a[1]
            cur = [(nx, ny)]
            cx, cy = sx, sy = nx, ny
            prev_ctrl, prev_kind = None, "m"
            continue
        if not cur:
            continue
        if c == "l":
            cx = cx + a[0] if rel else a[0]
            cy = cy + a[1] if rel else a[1]
            cur.append((cx, cy))
            prev_ctrl, prev_kind = None, "l"
        elif c == "h":
            cx = cx + a[0] if rel else a[0]
            cur.append((cx, cy))
            prev_ctrl, prev_kind = None, "l"
        elif c == "v":
            cy = cy + a[0] if rel else a[0]
            cur.append((cx, cy))
            prev_ctrl, prev_kind = None, "l"
        elif c in ("c", "s"):
            if c == "c":
                pts = [(a[0], a[1]), (a[2], a[3]), (a[4], a[5])]
                if rel:
                    pts = [(cx + px, cy + py) for px, py in pts]
            else:
                r = prev_ctrl if prev_kind in ("c", "s") and prev_ctrl else (cx, cy)
                refl = (2 * cx - r[0], 2 * cy - r[1])
                p = [(a[0], a[1]), (a[2], a[3])]
                if rel:
                    p = [(cx + px, cy + py) for px, py in p]
                pts = [refl] + p
            cur.extend(cubic((cx, cy), pts[0], pts[1], pts[2]))
            prev_ctrl = pts[1]
            cx, cy = pts[2]
            prev_kind = c
        elif c in ("q", "t"):
            if c == "q":
                ctrl = (cx + a[0], cy + a[1]) if rel else (a[0], a[1])
                end = (cx + a[2], cy + a[3]) if rel else (a[2], a[3])
            else:
                r = prev_ctrl if prev_kind in ("q", "t") and prev_ctrl else (cx, cy)
                ctrl = (2 * cx - r[0], 2 * cy - r[1])
                end = (cx + a[0], cy + a[1]) if rel else (a[0], a[1])
            cur.extend(quad((cx, cy), ctrl, end))
            prev_ctrl = ctrl
            cx, cy = end
            prev_kind = c
        elif c == "a":
            cx = cx + a[5] if rel else a[5]
            cy = cy + a[6] if rel else a[6]
            cur.append((cx, cy))          # arcs do not occur in this artwork
            prev_ctrl, prev_kind = None, "a"
        elif c == "z":
            cur.append((sx, sy))
            cx, cy = sx, sy
            prev_ctrl, prev_kind = None, "z"
    if cur:
        out.append(np.asarray(cur, float))
    return out


def xform(pts, M):
    a, b, c, d, e, f = M
    x, y = pts[:, 0], pts[:, 1]
    return np.column_stack((a * x + c * y + e, b * x + d * y + f))


def densify(pts, step=MAX_CHORD):
    """Resample a polyline so no gap between consecutive points exceeds `step`."""
    seg = np.diff(pts, axis=0)
    ln = np.hypot(seg[:, 0], seg[:, 1])
    n = np.maximum(1, np.ceil(ln / step).astype(int))
    out = []
    for i, k in enumerate(n):
        t = np.linspace(0.0, 1.0, k, endpoint=False)[:, None]
        out.append(pts[i] + t * seg[i])
    out.append(pts[-1:])
    return np.vstack(out)


def contour_area(pts):
    x, y = pts[:, 0], pts[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


def inside(poly, pts):
    """Ray-cast point-in-polygon; returns a boolean array over `pts`."""
    x, y = pts[:, 0], pts[:, 1]
    x1, y1 = poly[:, 0], poly[:, 1]
    x2, y2 = np.roll(x1, -1), np.roll(y1, -1)
    res = np.zeros(len(pts), bool)
    for i in range(len(poly)):
        cond = (y1[i] > y[:]) != (y2[i] > y[:])
        if not cond.any():
            continue
        denom = (y2[i] - y1[i])
        if denom == 0:
            continue
        xint = (x2[i] - x1[i]) * (y - y1[i]) / denom + x1[i]
        res ^= cond & (x < xint)
    return res


def min_dist(a, b):
    """Minimum distance between two point clouds (KD-tree; the clouds run to 10^4)."""
    if len(a) == 0 or len(b) == 0:
        return float("inf")
    if len(a) > len(b):
        a, b = b, a
    return float(cKDTree(b).query(a, k=1)[0].min())


def bbox(pts):
    return (float(pts[:, 0].min()), float(pts[:, 1].min()),
            float(pts[:, 0].max()), float(pts[:, 1].max()))


# ---------------------------------------------------------------------------
# One page
# ---------------------------------------------------------------------------

def root_matrix(svg):
    i = svg.find("<g ")
    t = TRANSFORM.search(svg[i:svg.index(">", i)])
    return parse_transform(t.group(1))


def marks_of(svg):
    """(ornament d, numeral d, local transform, numeral transform, ayah:x/y) per marker."""
    i = svg.find(MARK_BLOCK)
    if i < 0:
        return []
    block = svg[i:_matching_close(svg, i)]
    kids = list(GROUP.finditer(block))
    out, k = [], 0
    while k < len(kids):
        g = kids[k]
        if "scale(" in g.group(1) and k + 1 < len(kids) and "ayah:x" in kids[k + 1].group(1):
            num = kids[k + 1]
            xy = AYAH_XY.search(num.group(1))
            out.append({
                "orn_d": D_ATTR.search(g.group(2)).group(1),
                "orn_t": TRANSFORM.search(g.group(1)).group(1),
                "num_d": D_ATTR.search(num.group(2)).group(1),
                "num_t": (TRANSFORM.search(num.group(1)) or [None, ""])[1]
                if TRANSFORM.search(num.group(1)) else "",
                "ax": float(xy.group(1)) if xy else None,
                "ay": float(xy.group(2)) if xy else None,
            })
            k += 2
        else:
            m = D_ATTR.search(g.group(2))
            if m and "scale(" in g.group(1):
                out.append({
                    "orn_d": m.group(1),
                    "orn_t": TRANSFORM.search(g.group(1)).group(1),
                    "num_d": None, "num_t": "", "ax": None, "ay": None,
                })
            k += 1
    return out


def ayah_index(page_no):
    """Medallion centre -> "surah:ayah", from the page's own ayah polygons.

    The polygon file carries each ayah's marker centre in page coordinates, so a
    marker is named by WHERE it is drawn.  Document order is not used: it pairs
    markers with ayahs backwards on 441 pages, a labelling defect this audit
    routes around rather than inherits.
    """
    f = os.path.join(ROOT, "mushafs", EDITION, "json", "%03d.json" % page_no)
    if not os.path.exists(f):
        return []
    return [(float(e["x"]), float(e["y"]), "%s:%s" % (e["surahNumber"], e["ayahNumber"]))
            for e in json.load(open(f, encoding="utf-8"))]


def measure_page(page_no):
    src = os.path.join(ROOT, "mushafs", EDITION, "svg", "%03d.svg" % page_no)
    svg = open(src, encoding="utf-8").read()
    R = root_matrix(svg)
    page = Page(src)

    # Every non-mark contour on the page, in rendered page units, kept as a bbox
    # first so only the ink near a medallion is ever flattened.
    boxes = page.contours()
    # Contours are flattened path by path and indexed by position, never by slicing
    # `d`: a contour's source text opens with a relative moveto (and may carry an
    # implicit poly-lineto), so a slice re-headed as absolute lands in the wrong place.
    aidx = ayah_index(page_no)
    flat = [flatten(P["d"]) for P in page.paths]
    for P, f in zip(page.paths, flat):
        assert len(f) == len(subpaths(P["d"])), "contour indexing broke"

    recs = []
    for mi, m in enumerate(marks_of(svg)):
        Mo = mul(R, parse_transform(m["orn_t"]))
        rings = [densify(xform(c, Mo)) for c in flatten(m["orn_d"]) if len(c) > 2]
        if not rings:
            continue
        rings.sort(key=contour_area, reverse=True)
        outer = rings[0]
        ring_pts = np.vstack(rings)
        rb = bbox(ring_pts)
        scale = math.hypot(Mo[0], Mo[1])          # uniform: |a| == |d| in this art

        rec = {
            "page": page_no, "marker": mi,
            "ring_scale": round(scale, 6),
            "ring_w": round(rb[2] - rb[0], 3), "ring_h": round(rb[3] - rb[1], 3),
            "ring_cx": round((rb[0] + rb[2]) / 2, 3),
            "ring_cy": round((rb[1] + rb[3]) / 2, 3),
        }

        # The central hole: the biggest non-outer contour whose bbox straddles the
        # ring centre.  (The other holes are the two flourishes, above and below.)
        cx, cy = rec["ring_cx"], rec["ring_cy"]
        holes = [c for c in rings[1:]
                 if bbox(c)[0] < cx < bbox(c)[2] and bbox(c)[1] < cy < bbox(c)[3]]
        hole = max(holes, key=contour_area) if holes else None

        if m["num_d"] is not None:
            Mn = mul(R, parse_transform(m["num_t"])) if m["num_t"] else R
            nums = [densify(xform(c, Mn)) for c in flatten(m["num_d"]) if len(c) > 2]
            num_pts = np.vstack(nums) if nums else None
        else:
            num_pts = None

        if num_pts is not None:
            nb = bbox(num_pts)
            rec.update({
                "num_w": round(nb[2] - nb[0], 3), "num_h": round(nb[3] - nb[1], 3),
                "num_cx": round((nb[0] + nb[2]) / 2, 3),
                "num_cy": round((nb[1] + nb[3]) / 2, 3),
                "num_contours": len(nums),
            })
            # numeral to ring ink: the real "does it touch the ring" measure
            rec["num_to_ring"] = round(min_dist(num_pts, ring_pts), 4)
            # The same shrink knob, seen from the inside: what a smaller ring would
            # cost the numeral's breathing room.  Containment sets the floor on any
            # shrink that clearance asks for.
            c = np.array([rec["ring_cx"], rec["ring_cy"]])
            ntree = cKDTree(num_pts)
            rec["num_gap"] = {}
            for sc in SCALES:
                q = c + sc * (ring_pts - c)
                rec["num_gap"]["%.2f" % sc] = round(float(ntree.query(q, k=1)[0].min()), 4)
            if hole is not None:
                hb = bbox(hole)
                rec.update({
                    "hole_w": round(hb[2] - hb[0], 3), "hole_h": round(hb[3] - hb[1], 3),
                    "m_left": round(nb[0] - hb[0], 3),
                    "m_right": round(hb[2] - nb[2], 3),
                    "m_top": round(nb[1] - hb[1], 3),
                    "m_bottom": round(hb[3] - nb[3], 3),
                    "num_to_hole": round(min_dist(num_pts, hole), 4),
                    "num_inside": bool(inside(hole, num_pts).all()),
                    "outside_pts": int((~inside(hole, num_pts)).sum()),
                    "hole_cx": round((hb[0] + hb[2]) / 2, 3),
                    "hole_cy": round((hb[1] + hb[3]) / 2, 3),
                })
            if m["ax"] is not None:
                rec["ayah_xy"] = [m["ax"], m["ay"]]
                if aidx:
                    best = min(aidx, key=lambda e: (e[0] - m["ax"]) ** 2
                               + (e[1] - m["ay"]) ** 2)
                    rec["ayah_key"] = best[2]
                    rec["aid_dist"] = round(math.hypot(best[0] - m["ax"],
                                                       best[1] - m["ay"]), 3)
                rec["proof_dx"] = round(m["ax"] - rec["ring_cx"], 3)
                rec["proof_dy"] = round(m["ay"] - rec["ring_cy"], 3)

        # Clearance: nearest non-mark ink to the ring's outer silhouette.
        pad = 6.0
        near = [b for b in boxes
                if b["x2"] > rb[0] - pad and b["x1"] < rb[2] + pad
                and b["y2"] > rb[1] - pad and b["y1"] < rb[3] + pad]
        pts = []
        for b in near:
            c = flat[b["path"]][b["sp"]["index"]]
            if len(c) > 1:
                pts.append(densify(xform(c, page.paths[b["path"]]["M"])))
        if pts:
            ink = np.vstack(pts)
            rec["clearance"] = round(min_dist(outer, ink), 4)
            rec["clearance_all"] = round(min_dist(ring_pts, ink), 4)
            rec["near_contours"] = len(near)
            # A minimum distance cannot tell touching from overlapping, so anything
            # close gets the signed test: how much foreign ink is INSIDE the ring's
            # outer silhouette, and how deep.
            if rec["clearance"] < 1.0:
                # Where the contact is, and what a smaller ring would buy.  A uniform
                # shrink about the ring centre is the one knob the artwork exposes
                # (the ornament is placed by `translate(...) scale(s -s)`), so the
                # clearance is re-measured at candidate scales rather than guessed.
                tree = cKDTree(ink)
                dd, ii = tree.query(outer, k=1)
                j = int(np.argmin(dd))
                rec["contact_dx"] = round(float(outer[j][0] - rec["ring_cx"]), 3)
                rec["contact_dy"] = round(float(outer[j][1] - rec["ring_cy"]), 3)
                c = np.array([rec["ring_cx"], rec["ring_cy"]])
                rec["shrink"] = {}
                for sc in SCALES:
                    q = c + sc * (outer - c)
                    rec["shrink"]["%.2f" % sc] = round(float(tree.query(q, k=1)[0].min()), 4)
                within = ink[(ink[:, 0] > rb[0]) & (ink[:, 0] < rb[2])
                             & (ink[:, 1] > rb[1]) & (ink[:, 1] < rb[3])]
                if len(within):
                    hit = within[inside(outer, within)]
                    rec["pen_pts"] = int(len(hit))
                    rec["pen_depth"] = (round(float(cKDTree(outer).query(hit, k=1)[0].max()), 4)
                                        if len(hit) else 0.0)
                else:
                    rec["pen_pts"], rec["pen_depth"] = 0, 0.0
        else:
            rec["clearance"] = None
            rec["clearance_all"] = None
            rec["near_contours"] = 0
        recs.append(rec)
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", nargs=2, type=int, default=[1, 604])
    ap.add_argument("--jobs", type=int, default=32)
    ap.add_argument("--out", default=os.path.join(ROOT, ".cache", "medallions.json"))
    ap.add_argument("--proof", action="store_true")
    args = ap.parse_args()

    pages = list(range(args.pages[0], args.pages[1] + 1))
    with Pool(args.jobs) as pool:
        all_recs = [r for page in pool.imap(measure_page, pages, chunksize=2) for r in page]

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(all_recs, open(args.out, "w"), indent=1)
    print("markers measured: %d over %d pages -> %s"
          % (len(all_recs), len(pages), args.out))

    if args.proof:
        dx = [r["proof_dx"] for r in all_recs if "proof_dx" in r]
        dy = [r["proof_dy"] for r in all_recs if "proof_dy" in r]
        print("transform proof (ayah:x/y minus computed ring centre, page units):")
        print("  dx  n=%d  mean %.3f  max|.| %.3f" % (len(dx), np.mean(dx),
                                                      np.max(np.abs(dx))))
        print("  dy  n=%d  mean %.3f  max|.| %.3f" % (len(dy), np.mean(dy),
                                                      np.max(np.abs(dy))))


if __name__ == "__main__":
    main()
