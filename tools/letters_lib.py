#!/usr/bin/env python3
"""Shared geometry and text tables for the letter-level decomposition.

Spec: docs/superpowers/specs/2026-09-05-letter-level-decomposition-design.md

What lives here:
  * path parsing / flattening / evenodd rasterising of the page paths (which are in
    the page-path coordinate system: y UP, under the page's flipping matrix);
  * `cut_run()` — split one run contour by cut polylines into per-letter pieces, all
    boundary curves the run's own except the cut line (this is why the pixel gate
    holds: measured 2026-09-04, max alpha diff 17/255 with no overlap);
  * `letters_of()` — the per-letter expectation (marks, dots, joining) read from the
    uthmani text with the SAME tables `assign_words.py` uses. The tables are parsed
    out of that file's source at import time rather than copied, so they cannot drift.
  * `read_words()` — the word-level SVG as data.
"""
import ast
import io
import math
import os
import re
import subprocess

import numpy as np
import pathops
from PIL import Image, ImageDraw

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.dirname(os.path.abspath(__file__))
WORDS_SVG = os.path.join(ROOT, ".cache", "words-svg", "hafs-kfqc")
# QSVG_LETTERS_TAG=<tag> keeps a second build side by side (cuts-<tag>, letters-svg-<tag>)
BUILD_TAG = os.environ.get("QSVG_LETTERS_TAG", "")
CUTS_DIR = os.path.join(ROOT, ".cache", "letters", "cuts" + ("-" + BUILD_TAG if BUILD_TAG else ""))
LETTERS_SVG = os.path.join(ROOT, ".cache", "letters-svg" + ("-" + BUILD_TAG if BUILD_TAG else ""), "hafs-kfqc")

NUM = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_CMD = re.compile(r"([MmLlHhVvCcSsQqTtZz])([^MmLlHhVvCcSsQqTtZz]*)")


class CutError(Exception):
    def __init__(self, why, **info):
        super().__init__(why)
        self.why = why
        self.info = info


# ----------------------------------------------------------------------------
# tables, parsed from assign_words.py so they cannot drift from the pipeline
# ----------------------------------------------------------------------------
def _pipeline_tables():
    src = open(os.path.join(TOOLS, "assign_words.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    want = {"HARAKA", "DOTS", "NONJOIN", "HAMZA_MAP"}
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id in want:
            v = node.value
            # the tables are literals, except NONJOIN = set("…"): unwrap that one call
            if isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == "set":
                out[node.targets[0].id] = set(ast.literal_eval(v.args[0]))
            else:
                out[node.targets[0].id] = ast.literal_eval(v)
    missing = want - set(out)
    if missing:
        raise RuntimeError("assign_words.py tables not found: %s" % sorted(missing))
    return out


_T = _pipeline_tables()
HARAKA, DOTS, NONJOIN, HAMZA_MAP = _T["HARAKA"], _T["DOTS"], _T["NONJOIN"], _T["HAMZA_MAP"]

# the emitter's names for two HARAKA labels that are spelled differently in the table
_EMIT_NAME = {"small-circle": "sifr-mustadir", "pause": "waqf"}
# the pause family as the emitter writes it (word-level marks, never a letter's)
WORD_LEVEL = ("waqf-", "wasl-awla", "muanaqah", "hizb", "seen-reading")


def letters_of(uthmani):
    """[{'ch','marks':[label…],'dots':label|None,'joins_next':bool,'body':bool}] in
    reading order. Mirrors segment_word(): a space or tatweel breaks/is skipped, a bare
    ء is a mark-only letter, hamza carriers are drawn dotless with a hamza/wasla/maddah
    mark, a word-final ي is drawn dotless, pause signs are word-level (not returned)."""
    out, pend = [], []
    for ch in uthmani:
        if ch == "ـ":                       # tatweel
            continue
        if ch == " ":
            if out:
                out[-1]["joins_next"] = False
            continue
        if ch in HARAKA:
            label, _pos = HARAKA[ch]
            label = _EMIT_NAME.get(label, label)
            if label == "waqf":
                continue                          # word-level, handled by the emitter
            if out:
                out[-1]["marks"].append(label)
            else:
                pend.append(label)
            continue
        if ch == "ء":                        # ء on the line: mark-only letter
            out.append({"ch": ch, "marks": pend + ["hamza"], "dots": None,
                        "joins_next": False, "body": False})
            pend = []
            continue
        if ch in HAMZA_MAP:
            base, extra = HAMZA_MAP[ch]
            marks = [extra[0]]
        elif "ء" <= ch <= "ي" or ch == "ى":
            base, marks = ch, []
        else:
            raise ValueError("unknown letter %r in %r" % (ch, uthmani))
        dots = DOTS.get(base, (None,))[0]
        out.append({"ch": base, "src": ch, "marks": pend + marks, "dots": dots,
                    "joins_next": base not in NONJOIN, "body": True})
        pend = []
    if out:
        out[-1]["joins_next"] = False
        if out[-1]["ch"] == "ي":            # final ya is dotless in this script
            out[-1]["dots"] = None
        if pend:
            out[-1]["marks"] += pend
    return out


def runs_of(letters):
    """Letter indices grouped into connected runs (the ligature groups)."""
    runs, cur = [], []
    for i, l in enumerate(letters):
        if not l["body"]:
            if cur:
                runs.append(cur)
                cur = []
            runs.append([i])
            continue
        cur.append(i)
        if not l["joins_next"]:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    return runs


# ----------------------------------------------------------------------------
# paths
# ----------------------------------------------------------------------------
def parse_d(d):
    """→ list of subpaths; each is [('M',(x,y)), ('L',(x,y)) | ('Q',(cx,cy,x,y)) |
    ('C',(x1,y1,x2,y2,x,y)) …]. Everything absolute; Z closes (no segment emitted)."""
    subs, cur = [], None
    cx = cy = sx = sy = 0.0
    last_c = None        # last control point for S/T reflection, with its kind
    for cmd, args in _CMD.findall(d):
        a = [float(v) for v in NUM.findall(args)]
        rel = cmd.islower()
        c = cmd.upper()
        if c == "Z":
            cx, cy = sx, sy
            last_c = None
            continue
        if c == "M":
            for i in range(0, len(a), 2):
                x, y = (cx + a[i], cy + a[i + 1]) if rel else (a[i], a[i + 1])
                if i == 0:
                    cur = [("M", (x, y))]
                    subs.append(cur)
                    sx, sy = x, y
                else:
                    cur.append(("L", (x, y)))
                cx, cy = x, y
            last_c = None
            continue
        if c == "H":
            for v in a:
                cx = cx + v if rel else v
                cur.append(("L", (cx, cy)))
            last_c = None
            continue
        if c == "V":
            for v in a:
                cy = cy + v if rel else v
                cur.append(("L", (cx, cy)))
            last_c = None
            continue
        n = {"L": 2, "C": 6, "S": 4, "Q": 4, "T": 2}[c]
        for i in range(0, len(a), n):
            seg = a[i:i + n]
            if rel:
                pts = [(cx + seg[j], cy + seg[j + 1]) for j in range(0, n, 2)]
            else:
                pts = [(seg[j], seg[j + 1]) for j in range(0, n, 2)]
            if c == "L":
                cur.append(("L", pts[0]))
                last_c = None
            elif c == "C":
                cur.append(("C", (*pts[0], *pts[1], *pts[2])))
                last_c = ("C", pts[1])
            elif c == "S":
                c1 = (2 * cx - last_c[1][0], 2 * cy - last_c[1][1]) if last_c and last_c[0] == "C" else (cx, cy)
                cur.append(("C", (*c1, *pts[0], *pts[1])))
                last_c = ("C", pts[0])
            elif c == "Q":
                cur.append(("Q", (*pts[0], *pts[1])))
                last_c = ("Q", pts[0])
            elif c == "T":
                c1 = (2 * cx - last_c[1][0], 2 * cy - last_c[1][1]) if last_c and last_c[0] == "Q" else (cx, cy)
                cur.append(("Q", (*c1, *pts[0])))
                last_c = ("Q", c1)
            cx, cy = pts[-1]
    return subs


def flatten(d, steps=12):
    """Closed polylines (one per subpath), curves sampled with `steps` points."""
    polys = []
    for sub in parse_d(d):
        pts = []
        for kind, v in sub:
            if kind == "M":
                pts.append(v)
            elif kind == "L":
                pts.append(v)
            elif kind == "Q":
                x0, y0 = pts[-1]
                for k in range(1, steps + 1):
                    t = k / steps
                    u = 1 - t
                    pts.append((u * u * x0 + 2 * u * t * v[0] + t * t * v[2],
                                u * u * y0 + 2 * u * t * v[1] + t * t * v[3]))
            elif kind == "C":
                x0, y0 = pts[-1]
                for k in range(1, steps + 1):
                    t = k / steps
                    u = 1 - t
                    pts.append((u ** 3 * x0 + 3 * u * u * t * v[0] + 3 * u * t * t * v[2] + t ** 3 * v[4],
                                u ** 3 * y0 + 3 * u * u * t * v[1] + 3 * u * t * t * v[3] + t ** 3 * v[5]))
        if len(pts) >= 3:
            if pts[0] == pts[-1]:
                pts.pop()
            polys.append(pts)
    return polys


def bbox(polys):
    xs = [p[0] for poly in polys for p in poly]
    ys = [p[1] for poly in polys for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def to_path(d):
    p = pathops.Path()
    pen = p.getPen()
    for sub in parse_d(d):
        for kind, v in sub:
            if kind == "M":
                pen.moveTo(v)
            elif kind == "L":
                pen.lineTo(v)
            elif kind == "Q":
                pen.qCurveTo((v[0], v[1]), (v[2], v[3]))
            elif kind == "C":
                pen.curveTo((v[0], v[1]), (v[2], v[3]), (v[4], v[5]))
        pen.closePath()
    p.fillType = pathops.FillType.EVEN_ODD
    return p


def _f(v, prec):
    s = ("%." + str(prec) + "f") % v
    s = s.rstrip("0").rstrip(".") if "." in s else s
    return "0" if s in ("-0", "") else s


def path_d(p, prec=3):
    """SVG `d` for a pathops path. Segments come pen-style: moveTo/lineTo/qCurveTo/
    curveTo/closePath; a qCurveTo may carry several off-curve points (TrueType style),
    whose implied on-curve midpoints are made explicit here."""
    out = []
    cur = None
    for verb, pts in p.segments:
        if verb == "moveTo":
            out.append("M%s %s" % (_f(pts[0][0], prec), _f(pts[0][1], prec)))
            cur = pts[0]
        elif verb == "lineTo":
            out.append("L%s %s" % (_f(pts[0][0], prec), _f(pts[0][1], prec)))
            cur = pts[0]
        elif verb == "curveTo":
            out.append("C" + " ".join(_f(c, prec) for q in pts for c in q))
            cur = pts[-1]
        elif verb == "qCurveTo":
            offs, end = list(pts[:-1]), pts[-1]
            if end is None:                      # closed all-off-curve contour: not produced by skia
                continue
            for i, off in enumerate(offs):
                if i < len(offs) - 1:
                    nxt = offs[i + 1]
                    on = ((off[0] + nxt[0]) / 2, (off[1] + nxt[1]) / 2)
                else:
                    on = end
                out.append("Q%s %s %s %s" % (_f(off[0], prec), _f(off[1], prec), _f(on[0], prec), _f(on[1], prec)))
            cur = end
        elif verb == "closePath":
            out.append("Z")
        else:
            raise ValueError("unexpected path verb %r" % verb)
    return "".join(out)


def area(polys_or_d):
    """Evenodd area. Accepts a `d` string or flattened polylines."""
    if isinstance(polys_or_d, str):
        p = to_path(polys_or_d)
    else:
        p = pathops.Path()
        pen = p.getPen()
        for poly in polys_or_d:
            pen.moveTo(poly[0])
            for q in poly[1:]:
                pen.lineTo(q)
            pen.closePath()
        p.fillType = pathops.FillType.EVEN_ODD
    p.simplify()
    return abs(p.area)


def raster(polys, x0, y0, w, h, z):
    """Evenodd mask, rows = (y - y0) * z, cols = (x - x0) * z. XOR of ring fills."""
    W, H = max(1, int(math.ceil(w * z))), max(1, int(math.ceil(h * z)))
    acc = np.zeros((H, W), dtype=bool)
    for poly in polys:
        im = Image.new("1", (W, H), 0)
        ImageDraw.Draw(im).polygon([((x - x0) * z, (y - y0) * z) for x, y in poly], fill=1)
        acc ^= np.array(im, dtype=bool)
    return acc


def centroid(polys):
    m = raster(polys, *bbox(polys)[:2],
               bbox(polys)[2] - bbox(polys)[0] + 0.1, bbox(polys)[3] - bbox(polys)[1] + 0.1, 8)
    ys, xs = np.nonzero(m)
    if not len(xs):
        x0, y0, x1, y1 = bbox(polys)
        return (x0 + x1) / 2, (y0 + y1) / 2
    x0, y0 = bbox(polys)[:2]
    return x0 + xs.mean() / 8, y0 + ys.mean() / 8


def point_poly_dist(pt, polys):
    """Distance from a point to the nearest polyline edge."""
    px, py = pt
    best = float("inf")
    for poly in polys:
        n = len(poly)
        for i in range(n):
            ax, ay = poly[i]
            bx, by = poly[(i + 1) % n]
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy
            t = 0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
            qx, qy = ax + t * dx, ay + t * dy
            d = math.hypot(px - qx, py - qy)
            if d < best:
                best = d
    return best


# ----------------------------------------------------------------------------
# cutting
# ----------------------------------------------------------------------------
def _simplify(pts, eps):
    """Douglas–Peucker."""
    if len(pts) < 3:
        return pts
    (ax, ay), (bx, by) = pts[0], pts[-1]
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy) or 1e-9
    dmax, idx = 0, 0
    for i in range(1, len(pts) - 1):
        d = abs(dy * pts[i][0] - dx * pts[i][1] + bx * ay - by * ax) / L
        if d > dmax:
            dmax, idx = d, i
    if dmax > eps:
        return _simplify(pts[:idx + 1], eps)[:-1] + _simplify(pts[idx:], eps)
    return [pts[0], pts[-1]]


# Cutting. A cut is a polyline crossing the stroke once, ends on the run contour. It
# is LOCAL: painted one pixel wide over the run's raster it splits the ink into
# connected components, and the letter is the component holding its reference point.
# The exact vector piece is the run intersected with that component's one-pixel
# envelope (never reaching the other side's pixels) intersected with the half-plane
# of the cut — so every boundary curve of the piece is the run's own except the
# chord itself. A half-plane alone is wrong whenever the chord lies along a
# baseline (the infinite line slices every stroke at that height); the envelope is
# what keeps the cut local. Stacked joints and tails need no special case.
def _pip(pt, poly):
    """Ray-casting point in polygon."""
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            xi = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if xi > x:
                inside = not inside
    return inside


def _poly_path(poly):
    reg = pathops.Path()
    pen = reg.getPen()
    pen.moveTo(poly[0])
    for q in poly[1:]:
        pen.lineTo(q)
    pen.closePath()
    reg.fillType = pathops.FillType.WINDING
    return reg


def _shoelace(poly):
    a = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        a += x0 * y1 - x1 * y0
    return a / 2


def half_plane(cut, ref, box, sign=None):
    """Side polygon of a cut: the polyline extended along its end tangents, closed far
    away on the side of `ref` (or of `sign` × the left normal when ref is None)."""
    x0, y0, x1, y1 = box
    D = 3 * math.hypot(x1 - x0, y1 - y0) + 10
    A, B = cut[0], cut[-1]
    ua = (A[0] - cut[1][0], A[1] - cut[1][1])
    ub = (B[0] - cut[-2][0], B[1] - cut[-2][1])
    na, nb = math.hypot(*ua) or 1e-9, math.hypot(*ub) or 1e-9
    A_ext = (A[0] + ua[0] / na * D, A[1] + ua[1] / na * D)
    B_ext = (B[0] + ub[0] / nb * D, B[1] + ub[1] / nb * D)
    dx, dy = B[0] - A[0], B[1] - A[1]
    nn = math.hypot(dx, dy) or 1e-9
    n = (-dy / nn, dx / nn)                      # left normal of A→B
    mid = ((A[0] + B[0]) / 2, (A[1] + B[1]) / 2)
    if ref is not None:
        sgn = 1 if (ref[0] - mid[0]) * n[0] + (ref[1] - mid[1]) * n[1] > 0 else -1
    else:
        sgn = sign if sign is not None else (1 if n[0] > 0 else -1)      # the right side
    n = (n[0] * sgn, n[1] * sgn)
    return [A_ext] + list(cut) + [B_ext, (B_ext[0] + n[0] * D, B_ext[1] + n[1] * D),
                                  (A_ext[0] + n[0] * D, A_ext[1] + n[1] * D)]


def _mask_path(mask, x0, y0, z):
    """Exact polygon of a pixel mask (union of its pixel squares) as a pathops path."""
    p = pathops.Path()
    pen = p.getPen()
    for r in range(mask.shape[0]):
        row = mask[r]
        c = 0
        W = len(row)
        while c < W:
            if row[c]:
                c1 = c
                while c1 < W and row[c1]:
                    c1 += 1
                xa, xb = x0 + c / z, x0 + c1 / z
                ya, yb = y0 + r / z, y0 + (r + 1) / z
                pen.moveTo((xa, ya))
                pen.lineTo((xb, ya))
                pen.lineTo((xb, yb))
                pen.lineTo((xa, yb))
                pen.closePath()
                c = c1
            else:
                c += 1
    p.fillType = pathops.FillType.WINDING
    p.simplify()
    return p


def _nearest_true(mask, rc, max_px):
    H, W = mask.shape
    r0, c0 = rc
    best = None
    for r in range(max(0, r0 - max_px), min(H, r0 + max_px + 1)):
        for c in range(max(0, c0 - max_px), min(W, c0 + max_px + 1)):
            if mask[r, c]:
                d = (r - r0) ** 2 + (c - c0) ** 2
                if best is None or d < best[0]:
                    best = (d, (r, c))
    return best[1] if best else None


# connectivity for the painted-strip components: 8-connected, like the ink itself (a
# one-pixel diagonal bridge in a thin stroke is still the same stroke)
_FOUR = np.ones((3, 3), dtype=bool)

def _paint(cut, x0, y0, z, W, H):
    ext = 2.5 / z
    A, B = cut[0], cut[-1]
    ua = (A[0] - cut[1][0], A[1] - cut[1][1])
    ub = (B[0] - cut[-2][0], B[1] - cut[-2][1])
    na, nb = math.hypot(*ua) or 1e-9, math.hypot(*ub) or 1e-9
    painted = [(A[0] + ua[0] / na * ext, A[1] + ua[1] / na * ext)] + list(cut) + \
              [(B[0] + ub[0] / nb * ext, B[1] + ub[1] / nb * ext)]
    # three pixels wide: the exact chord must lie INSIDE the painted strip everywhere
    # (a one-pixel diagonal line is a staircase the chord slips out of between steps)
    im = Image.new("1", (W, H), 0)
    ImageDraw.Draw(im).line([((x - x0) * z, (y - y0) * z) for x, y in painted], fill=1, width=3)
    return np.array(im, dtype=bool)


def split_by_cut(ink, cut, x0, y0, z):
    """Paint `cut` (page units) one pixel wide over `ink` (raster in the frame x0, y0,
    z), extended a few pixels past both ends, and 4-label the rest. Returns
    (labels, line_mask, (id_a, id_b)) — the two components flanking the chord — or
    None when the chord does not separate the ink it crosses."""
    from scipy import ndimage
    H, W = ink.shape
    A, B = cut[0], cut[-1]
    line = _paint(cut, x0, y0, z, W, H)
    free = ink & ~line
    lab, n = ndimage.label(free, structure=_FOUR)
    dx, dy = B[0] - A[0], B[1] - A[1]
    nn = math.hypot(dx, dy) or 1e-9
    nrm = (-dy / nn, dx / nn)

    def rc(p):
        return (min(H - 1, max(0, int((p[1] - y0) * z))), min(W - 1, max(0, int((p[0] - x0) * z))))

    sizes = np.bincount(lab.ravel())
    min_px = max(20, int(0.02 * ink.sum()))
    for mid in _along(cut, [0.5, 0.4, 0.6, 0.3, 0.7, 0.2, 0.8, 0.1, 0.9]):
        got = []
        for sgn in (1, -1):
            q = rc((mid[0] + nrm[0] * sgn * 3.0 / z, mid[1] + nrm[1] * sgn * 3.0 / z))
            q = _nearest_true(free, q, 3)
            got.append(int(lab[q]) if q else 0)
        if got[0] and got[1] and got[0] != got[1] and sizes[got[0]] >= min_px and sizes[got[1]] >= min_px:
            return lab, line, (got[0], got[1])
    return None




def cut_run(d, cuts, refs=None, z=8, tol=0.005):
    """Split the run `d` (one evenodd path) by `cuts` in READING ORDER (cut k lies
    between letter k and k+1) into len(cuts)+1 pieces. A cut is a polyline or a list
    of polylines (a medial kaf meets its neighbour at two places).

    All cuts are painted three pixels wide over the run's raster at once; the ink then
    falls into components. `refs[k]` is letter k's anchor point or list of anchor
    points (one per ink region of the letter); every component holding one of them
    is letter k's, and a component holding none goes to the nearest claimed one. The
    exact piece is the run intersected with the letter's one-pixel envelope, where
    inside the painted strips the envelope is replaced by each chord's half-plane —
    so every boundary curve is the run's own except the chords, which act nowhere
    else. Without refs, letter k is the right flank of cut k.

    Raises CutError when a chord does not separate letters k and k+1, two letters'
    anchors share a component, a piece is empty, or the area balance breaks."""
    from scipy import ndimage
    run = to_path(d)
    run.simplify()
    total = abs(run.area)
    if not cuts:
        return [path_d(run)]
    n = len(cuts) + 1
    cuts = [c if (c and not isinstance(c[0][0], (int, float))) else [c] for c in cuts]
    polys = flatten(d)
    bx0, by0, bx1, by1 = bbox(polys)
    pad = 1.0
    x0, y0 = bx0 - pad, by0 - pad
    w, h = bx1 - bx0 + 2 * pad, by1 - by0 + 2 * pad
    ink = raster(polys, x0, y0, w, h, z)
    H, W = ink.shape
    box = (bx0, by0, bx1, by1)

    def rc(p):
        return (min(H - 1, max(0, int((p[1] - y0) * z))), min(W - 1, max(0, int((p[0] - x0) * z))))

    def xy(q):
        return (x0 + (q[1] + 0.5) / z, y0 + (q[0] + 0.5) / z)

    for k, cut in enumerate(cuts):
        for pl in cut:
            if len(pl) < 2:
                raise CutError("degenerate cut", piece=k)
    strips = [[_paint(pl, x0, y0, z, W, H) for pl in cut] for cut in cuts]
    lines = [np.any(st, axis=0) for st in strips]
    LR = np.any(lines, axis=0)
    free = ink & ~LR
    lab, ncomp = ndimage.label(free, structure=_FOUR)
    sizes = np.bincount(lab.ravel())
    min_px = max(20, int(0.02 * ink.sum()))
    # the two flanks of every chord polyline
    flanks = []          # per cut: list per polyline of ((cid, pt), (cid, pt))
    for k, cut in enumerate(cuts):
        fl = []
        for pl in cut:
            A, B = pl[0], pl[-1]
            dx, dy = B[0] - A[0], B[1] - A[1]
            nn = math.hypot(dx, dy) or 1e-9
            nrm = (-dy / nn, dx / nn)
            got = None
            for mid in _along(pl, [0.5, 0.4, 0.6, 0.3, 0.7, 0.2, 0.8, 0.1, 0.9]):
                pair = []
                for sgn in (1, -1):
                    q = rc((mid[0] + nrm[0] * sgn * 3.0 / z, mid[1] + nrm[1] * sgn * 3.0 / z))
                    q = _nearest_true(free, q, 3)
                    pair.append((int(lab[q]), xy(q)) if q else (0, None))
                if pair[0][0] and pair[1][0] and pair[0][0] != pair[1][0] \
                        and sizes[pair[0][0]] >= min_px and sizes[pair[1][0]] >= min_px:
                    got = pair
                    break
            if got is None:
                raise CutError("cut does not separate", piece=k)
            fl.append(got)
        flanks.append(fl)
    # component → letter, from the anchors
    owner = {}
    refs = list(refs or []) + [None] * n
    for k in range(n):
        pts = refs[k]
        if pts is None:
            continue
        if pts and isinstance(pts[0], (int, float)):
            pts = [pts]
        for p in pts:
            q = _nearest_true(free, rc(p), int(0.8 * z) + 1)
            cid = int(lab[q]) if q else 0
            if not cid:
                continue
            if cid in owner and owner[cid] != k:
                raise CutError("references share a component", piece=k)
            owner[cid] = k
        if not any(v == k for v in owner.values()):
            raise CutError("reference off the ink", piece=k)
    for k in range(n - 1):
        if refs[k] is None or not refs[k]:
            (ca, pa), (cb, pb) = flanks[k][0]
            right = ca if pa[0] >= pb[0] else cb
            other = cb if right == ca else ca
            owner.setdefault(right if right not in owner else other, k)
    if refs[n - 1] is None or not refs[n - 1]:
        (ca, pa), (cb, pb) = flanks[-1][0]
        left = ca if pa[0] < pb[0] else cb
        other = cb if left == ca else ca
        owner.setdefault(left if left not in owner else other, n - 1)
    # unclaimed components (fragments a strip carved off) go to the nearest claimed one
    claimed = dict(owner)
    for cid in range(1, ncomp + 1):
        if cid in owner:
            continue
        ys, xs = np.nonzero(lab == cid)
        best = None
        for oc, k in claimed.items():
            oys, oxs = np.nonzero(lab == oc)
            step = max(1, len(oxs) // 400)
            dd = np.min(np.hypot(xs[:, None] - oxs[None, ::step], ys[:, None] - oys[None, ::step]))
            if best is None or dd < best[0]:
                best = (dd, k)
        owner[cid] = best[1] if best else 0
    # every chord must separate letters k and k+1
    for k, fl in enumerate(flanks):
        for j, ((ca, pa), (cb, pb)) in enumerate(fl):
            la, lb = owner.get(ca), owner.get(cb)
            if la is None or lb is None:
                raise CutError("cut does not separate its letters", piece=k, letters=(la, lb))
            if len(fl) == 1:
                ok = {la, lb} == {k, k + 1}
            else:            # a chord set: each chord parts a letter ≤ k from a letter > k
                ok = min(la, lb) <= k < max(la, lb)
            if not ok:
                raise CutError("cut does not separate its letters", piece=k, letters=(la, lb))
    letter_mask = [np.zeros(ink.shape, dtype=bool) for _ in range(n)]
    for cid, k in owner.items():
        letter_mask[k] |= lab == cid
    pieces = []
    for k in range(n):
        env = ndimage.binary_dilation(letter_mask[k], iterations=1)
        for j in range(n):
            if j != k:
                env &= ~letter_mask[j]
        adjacent = np.zeros(ink.shape, dtype=bool)
        for j in (k - 1, k):
            if 0 <= j < len(cuts):
                adjacent |= lines[j]
        region = _mask_path((env & ~LR) | (env & LR & ~adjacent), x0, y0, z)
        for j in (k - 1, k):
            if 0 <= j < len(cuts):
                for pl, strip, ((ca, pa), (cb, pb)) in zip(cuts[j], strips[j], flanks[j]):
                    side_pt = pa if owner.get(ca) == k else pb
                    hp = _poly_path(half_plane(pl, side_pt, box))
                    region = pathops.op(region, pathops.op(_mask_path(strip, x0, y0, z), hp, pathops.PathOp.INTERSECTION),
                                        pathops.PathOp.UNION)
        piece = pathops.op(run, region, pathops.PathOp.INTERSECTION)
        piece.simplify()
        if abs(piece.area) < 0.05:
            raise CutError("empty piece", piece=k)
        pieces.append(piece)
    s = sum(abs(p.area) for p in pieces)
    if abs(s - total) > max(tol * total, 0.02):
        raise CutError("area not conserved", total=total, pieces=s)
    # the boolean op re-fits curves (sub-pixel) and, rarely, clips a hole (measured on
    # p70: a filled corner of a ه counter, ~0.3 u²). Raster the union of the pieces
    # against the run at 12 px/u: beyond the refit noise it is a wrong split — refuse.
    zz = 12
    fr = (bx0 - 1, by0 - 1, bx1 - bx0 + 2, by1 - by0 + 2)
    ref_m = raster(polys, *fr, zz)
    uni = np.zeros(ref_m.shape, dtype=bool)
    for p in pieces:
        m = raster(flatten(path_d(p, prec=6)), *fr, zz)
        h_, w_ = min(m.shape[0], uni.shape[0]), min(m.shape[1], uni.shape[1])
        uni[:h_, :w_] |= m[:h_, :w_]
    from scipy import ndimage as _ndi
    # refit noise is a one-pixel sliver along the contour; a clipped hole is a blob.
    # A morphological opening keeps only blobs.
    # (a 2×2 opening: refit noise is a one-pixel chain, a clipped hole a strip ≥ 2 px)
    k2 = np.ones((2, 2), dtype=bool)
    blob = _ndi.binary_opening(uni & ~ref_m, structure=k2) | _ndi.binary_opening(ref_m & ~uni, structure=k2)
    if int(blob.sum()) >= 6:
        raise CutError("pieces do not reproduce the run", blob=int(blob.sum()))
    return [path_d(p) for p in pieces]


def _along(poly, ts):
    """Points at fractions `ts` of a polyline's length."""
    segs = [(poly[i], poly[i + 1], math.hypot(poly[i + 1][0] - poly[i][0], poly[i + 1][1] - poly[i][1]))
            for i in range(len(poly) - 1)]
    total = sum(s[2] for s in segs) or 1e-9
    out = []
    for t in ts:
        target = t * total
        acc = 0.0
        for j, (a, b, ln) in enumerate(segs):
            if acc + ln >= target or j == len(segs) - 1:
                u = 0 if ln == 0 else max(0.0, min(1.0, (target - acc) / ln))
                out.append((a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u))
                break
            acc += ln
    return out


# ----------------------------------------------------------------------------
# the word-level SVG as data
# ----------------------------------------------------------------------------
_ATTR = re.compile(r'([a-zA-Z:-]+)="([^"]*)"')
_LIG = re.compile(r'<g class="ligature" data-text="([^"]*)">(.*?)</g>', re.S)
_PATH = re.compile(r'<path ([^>]*?)/>', re.S)
_TAG = re.compile(r'<g\b[^>]*>|</g>')


def parse_attrs(s):
    return dict(_ATTR.findall(s))


def _group_spans(s, marker='<g class="word"'):
    """(start, end) of every group opened by `marker`, matching nested <g>/</g>."""
    spans = []
    pos = 0
    while True:
        i = s.find(marker, pos)
        if i < 0:
            break
        depth = 0
        for m in _TAG.finditer(s, i):
            if m.group(0).startswith("</"):
                depth -= 1
                if depth == 0:
                    spans.append((i, m.end()))
                    pos = m.end()
                    break
            else:
                depth += 1
        else:
            break
    return spans


def read_words(page, svg_dir=WORDS_SVG):
    """Words of a page in reading order:
    {'wid','uthmani','attrs','span':(start,end),'open':the open tag,'inner':text between
     the open tag and the closing </g>, 'ligatures':[{'text','paths':[…]}],
     'paths':[{'kind','mark','eid','d','attrs','raw','loose'}…] (document order)}."""
    s = open(os.path.join(svg_dir, "%03d.svg" % page), encoding="utf-8").read()
    words = []
    for a, b in _group_spans(s):
        open_end = s.index(">", a) + 1
        open_tag = s[a:open_end]
        inner = s[open_end:b - len("</g>")]
        attrs = parse_attrs(open_tag[len("<g"):])
        ligs, paths = [], []
        for lm in _LIG.finditer(inner):
            lp = []
            for pm in _PATH.finditer(lm.group(2)):
                at = parse_attrs(pm.group(1))
                rec = {"kind": at.get("data-kind"), "mark": at.get("data-mark"),
                       "eid": at.get("data-eid"), "d": at.get("d"), "attrs": at,
                       "raw": pm.group(0), "loose": False}
                lp.append(rec)
                paths.append(rec)
            ligs.append({"text": lm.group(1), "paths": lp})
        rest = _LIG.sub("", inner)
        for pm in _PATH.finditer(rest):
            at = parse_attrs(pm.group(1))
            paths.append({"kind": at.get("data-kind"), "mark": at.get("data-mark"),
                          "eid": at.get("data-eid"), "d": at.get("d"), "attrs": at,
                          "raw": pm.group(0), "loose": True})
        words.append({"wid": attrs.get("data-wid"), "uthmani": attrs.get("data-uthmani", ""),
                      "attrs": attrs, "span": (a, b), "open": open_tag, "ligatures": ligs,
                      "paths": paths, "inner": inner})
    key = lambda w: tuple(int(v) for v in w["wid"].split(":"))
    words.sort(key=key)
    return words, s


def word_polys(word, kinds=("body",)):
    return [poly for p in word["paths"] if p["kind"] in kinds and p["d"]
            for poly in flatten(p["d"])]


def render_mask(svg_text, x0, y0, w, h, z):
    """Rasterise an SVG snippet (paths in page-path coords) with rsvg — used only by
    tests and audits, the pipeline paths go through `raster()`."""
    hdr = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="%f %f %f %f" width="%d" '
           'height="%d">' % (x0, y0, w, h, int(w * z), int(h * z)))
    png = subprocess.run(["rsvg-convert"], input=(hdr + svg_text + "</svg>").encode(),
                         capture_output=True, check=True).stdout
    return np.array(Image.open(io.BytesIO(png)).convert("RGBA"))[..., 3] > 128


# ----------------------------------------------------------------------------
# outline sampling helpers (registration, cut lifting)
# ----------------------------------------------------------------------------
def resample(polys, step):
    """Points along closed polylines at most `step` apart (each vertex kept)."""
    out = []
    for poly in polys:
        n = len(poly)
        for i in range(n):
            ax, ay = poly[i]
            bx, by = poly[(i + 1) % n]
            L = math.hypot(bx - ax, by - ay)
            k = max(1, int(math.ceil(L / step)))
            for j in range(k):
                t = j / k
                out.append((ax + (bx - ax) * t, ay + (by - ay) * t))
    return out


def outline_tree(polys, step=0.05):
    from scipy.spatial import cKDTree
    pts = np.array(resample(polys, step), dtype=float)
    return cKDTree(pts), pts


def transform_polys(polys, s, tx, ty):
    return [[(x * s + tx, y * s + ty) for x, y in poly] for poly in polys]


def cut_run_masks(d, masks, chords, frame, tol=0.005):
    """Split the run `d` by a trusted per-pixel ownership.

    `masks[k]` is letter k's pixel mask in the raster `frame` = (x0, y0, z); `chords[j]`
    is a list of polylines (may be empty) straightening the boundary between letters
    j and j+1. Every ink pixel belongs to the letter whose mask holds it (unowned ink
    pixels go to the nearest owned one); the piece is the run intersected with the
    letter's one-pixel envelope, and inside each painted chord strip with the chord's
    half-plane on the letter's side. Where no chord exists the boundary is the pixel
    staircase itself. Checks: no empty piece, areas conserve, pieces reproduce the run."""
    from scipy import ndimage
    x0, y0, z = frame
    run = to_path(d)
    run.simplify()
    total = abs(run.area)
    n = len(masks)
    polys = flatten(d)
    bx0, by0, bx1, by1 = bbox(polys)
    box = (bx0, by0, bx1, by1)
    H, W = masks[0].shape
    ink = raster(polys, x0, y0, W / z, H / z, z)
    ink_ = np.zeros((H, W), dtype=bool)
    h_, w_ = min(H, ink.shape[0]), min(W, ink.shape[1])
    ink_[:h_, :w_] = ink[:h_, :w_]
    ink = ink_
    own = np.full((H, W), -1, dtype=np.int64)
    for k, m in enumerate(masks):
        own[m & ink] = k
    unowned = ink & (own < 0)
    if unowned.any():
        have = own >= 0
        if not have.any():
            raise CutError("no ownership")
        _, (ir, ic) = ndimage.distance_transform_edt(~have, return_indices=True)
        own[unowned] = own[ir[unowned], ic[unowned]]
    letter_mask = [own == k for k in range(n)]
    for k in range(n):
        if not letter_mask[k].any():
            raise CutError("letter without ink", piece=k)
    strips = [[_paint(pl, x0, y0, z, W, H) for pl in (chords[j] if j < len(chords) else [])] for j in range(n - 1)]
    lines = [np.any(st, axis=0) if st else np.zeros((H, W), dtype=bool) for st in strips]
    LR = np.any(lines, axis=0) if lines else np.zeros((H, W), dtype=bool)

    def xy(q):
        return (x0 + (q[1] + 0.5) / z, y0 + (q[0] + 0.5) / z)

    def rc(p):
        return (min(H - 1, max(0, int((p[1] - y0) * z))), min(W - 1, max(0, int((p[0] - x0) * z))))

    # every strip's ink pixels are split by the chord's line; each side goes wholly to
    # the letter owning most of it, so no strip pixel is lost or counted twice
    rr, cc = np.mgrid[0:H, 0:W]
    PX = x0 + (cc + 0.5) / z
    PY = y0 + (rr + 0.5) / z
    strip_parts = []           # (owner letter, strip mask, chord, side point)
    for j in range(n - 1):
        for pl, strip in zip(chords[j] if j < len(chords) else [], strips[j]):
            A, B = pl[0], pl[-1]
            dx, dy = B[0] - A[0], B[1] - A[1]
            sign = (PX - A[0]) * dy - (PY - A[1]) * dx
            for sgn in (1, -1):
                part = strip & ink & ((sign * sgn) > 0)
                if not part.any():
                    continue
                owners = own[part]
                owners = owners[owners >= 0]
                if not len(owners):
                    continue
                k = int(np.bincount(owners).argmax())
                ys_, xs_ = np.nonzero(part)
                side_pt = (x0 + (xs_.mean() + 0.5) / z, y0 + (ys_.mean() + 0.5) / z)
                strip_parts.append((k, strip, pl, side_pt))
    pieces = []
    for k in range(n):
        env = ndimage.binary_dilation(letter_mask[k], structure=_FOUR, iterations=1)
        for j in range(n):
            if j != k:
                env &= ~letter_mask[j]
        region = _mask_path(env & ~LR, x0, y0, z)
        for owner, strip, pl, side_pt in strip_parts:
            if owner != k:
                continue
            hp = _poly_path(half_plane(pl, side_pt, box))
            region = pathops.op(region, pathops.op(_mask_path(strip, x0, y0, z), hp, pathops.PathOp.INTERSECTION),
                                pathops.PathOp.UNION)
        piece = pathops.op(run, region, pathops.PathOp.INTERSECTION)
        piece.simplify()
        if abs(piece.area) < 0.05:
            raise CutError("empty piece", piece=k)
        pieces.append(piece)
    s = sum(abs(p.area) for p in pieces)
    if abs(s - total) > max(tol * total, 0.02):
        raise CutError("area not conserved", total=total, pieces=s)
    zz = 12
    fr = (bx0 - 1, by0 - 1, bx1 - bx0 + 2, by1 - by0 + 2)
    ref_m = raster(polys, *fr, zz)
    uni = np.zeros(ref_m.shape, dtype=bool)
    for p in pieces:
        m = raster(flatten(path_d(p, prec=6)), *fr, zz)
        hh, ww = min(m.shape[0], uni.shape[0]), min(m.shape[1], uni.shape[1])
        uni[:hh, :ww] |= m[:hh, :ww]
    k2 = np.ones((2, 2), dtype=bool)
    blob = ndimage.binary_opening(uni & ~ref_m, structure=k2) | ndimage.binary_opening(ref_m & ~uni, structure=k2)
    if int(blob.sum()) >= 6:
        raise CutError("pieces do not reproduce the run", blob=int(blob.sum()))
    return [path_d(p) for p in pieces]
