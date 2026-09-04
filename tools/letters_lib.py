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
CUTS_DIR = os.path.join(ROOT, ".cache", "letters", "cuts")
LETTERS_SVG = os.path.join(ROOT, ".cache", "letters-svg", "hafs-kfqc")

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


def _extend_to_border(ink, start_rc, prefer_row_dir):
    """A* over non-ink pixels from `start_rc` to the raster border; returns the path
    (list of (r,c)) or None. `prefer_row_dir` (+1/-1/0) says which border the search
    aims at (the one the cut's end tangent points to)."""
    import heapq
    H, W = ink.shape
    r0, c0 = start_rc
    if ink[r0, c0]:
        return None
    target = (H - 1) if prefer_row_dir > 0 else 0
    h = (lambda r: abs(target - r)) if prefer_row_dir else (lambda r: min(r, H - 1 - r))
    dist = {(r0, c0): 0.0}
    prev = {}
    pq = [(h(r0), 0.0, r0, c0)]
    while pq:
        _, g, r, c = heapq.heappop(pq)
        if r in (0, H - 1) or c in (0, W - 1):
            path = [(r, c)]
            while path[-1] in prev:
                path.append(prev[path[-1]])
            return path[::-1]
        if g > dist.get((r, c), 1e18):
            continue
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < H and 0 <= nc < W and not ink[nr, nc]:
                ng = g + (1.0 if dr == 0 or dc == 0 else 1.4142)
                if ng < dist.get((nr, nc), 1e18):
                    dist[(nr, nc)] = ng
                    prev[(nr, nc)] = (r, c)
                    heapq.heappush(pq, (ng + h(nr), ng, nr, nc))
    return None


def _march_out(ink, rc, direction, z, max_units=3.0):
    """From pixel `rc`, walk along `direction` (unit vector, raster rows/cols) until a
    non-ink pixel; returns the pixels walked (ink ones included) or None."""
    H, W = ink.shape
    r, c = rc
    dr, dc = direction
    walked = []
    for k in range(int(max_units * z) + 1):
        rr, cc = int(round(r + dr * k)), int(round(c + dc * k))
        if not (0 <= rr < H and 0 <= cc < W):
            return None
        walked.append((rr, cc))
        if not ink[rr, cc]:
            return walked
    return None


def extend_cut(d_or_polys, cut, z=8, pad=1.5):
    """Extend a cut polyline (page units, crossing the stroke once) outside the ink
    to the padded bbox border on both ends, never crossing ink. Returns the extended
    polyline and the padded bbox (x0, y0, x1, y1)."""
    polys = flatten(d_or_polys) if isinstance(d_or_polys, str) else d_or_polys
    bx0, by0, bx1, by1 = bbox(polys)
    x0, y0, x1, y1 = bx0 - pad, by0 - pad, bx1 + pad, by1 + pad
    ink = raster(polys, x0, y0, x1 - x0, y1 - y0, z)
    H, W = ink.shape

    def to_rc(p):
        return (min(H - 1, max(0, int((p[1] - y0) * z))), min(W - 1, max(0, int((p[0] - x0) * z))))

    def to_xy(rc):
        return (x0 + (rc[1] + 0.5) / z, y0 + (rc[0] + 0.5) / z)

    ends = []
    for end, nxt in ((cut[0], cut[1]), (cut[-1], cut[-2])):
        dy, dx = end[1] - nxt[1], end[0] - nxt[0]
        n = math.hypot(dx, dy) or 1e-9
        rc = to_rc(end)
        pre = []
        if ink[rc]:
            walked = _march_out(ink, rc, (dy / n, dx / n), z)
            if walked is None:
                raise CutError("cut end inside ink and cannot leave it")
            pre = walked[:-1]
            rc = walked[-1]
        pref = 1 if dy > abs(dx) * 0.3 else (-1 if -dy > abs(dx) * 0.3 else 0)
        path = _extend_to_border(ink, rc, pref)
        if path is None:
            raise CutError("extension blocked")
        pts = [to_xy(q) for q in pre + path]
        ends.append(_simplify(pts, 0.6 / z) if len(pts) > 2 else pts)
    head = ends[0][::-1]     # from border down to cut[0]
    tail = ends[1]           # from cut[-1] out to border
    ext = head + list(cut) + tail
    ext[0] = _snap_border(ext[0], x0, y0, x1, y1)
    ext[-1] = _snap_border(ext[-1], x0, y0, x1, y1)
    return ext, (x0, y0, x1, y1)


def _snap_border(p, x0, y0, x1, y1):
    cands = [(abs(p[0] - x0), (x0, p[1])), (abs(p[0] - x1), (x1, p[1])),
             (abs(p[1] - y0), (p[0], y0)), (abs(p[1] - y1), (p[0], y1))]
    return min(cands)[1]


# The box perimeter is parametrised clockwise from the (x0, y0) corner: bottom edge
# (y = y0) left→right, right edge up, top edge right→left, left edge down. A cut that
# reaches the border at two points is a chord; the arc between them that contains the
# (x1, y0) corner (position W) is the chord's RIGHT side. Regions between chords are
# built from nested right sides, so pieces come out right→left.
def _perim(box):
    x0, y0, x1, y1 = box
    return 2 * (x1 - x0) + 2 * (y1 - y0)


def _border_pos(p, box):
    x0, y0, x1, y1 = box
    W, H = x1 - x0, y1 - y0
    if abs(p[1] - y0) < 1e-9:
        return p[0] - x0
    if abs(p[0] - x1) < 1e-9:
        return W + (p[1] - y0)
    if abs(p[1] - y1) < 1e-9:
        return W + H + (x1 - p[0])
    return 2 * W + H + (y1 - p[1])


def _pos_point(pos, box):
    x0, y0, x1, y1 = box
    W, H = x1 - x0, y1 - y0
    pos %= _perim(box)
    if pos < W:
        return (x0 + pos, y0)
    if pos < W + H:
        return (x1, y0 + pos - W)
    if pos < 2 * W + H:
        return (x1 - (pos - W - H), y1)
    return (x0, y1 - (pos - 2 * W - H))


def _border_walk(a, b, box):
    """Corner points strictly between perimeter positions a and b (forward, a < b)."""
    x0, y0, x1, y1 = box
    W, H = x1 - x0, y1 - y0
    P = _perim(box)
    corners = [W, W + H, 2 * W + H, P]
    out = []
    for cp in corners:
        k = math.floor((a - cp) / P) + 1            # first multiple of P that puts cp above a
        c = cp + k * P
        while c < b:
            out.append(_pos_point(c, box))
            c += P
    return out


def _chord(ext, box):
    """(a, b, polyline a→b) for an extended cut: positions with a < b such that the arc
    (a, b) is the chord's right side (contains position W)."""
    x0, y0, x1, y1 = box
    W = x1 - x0
    P = _perim(box)
    pa, pb = _border_pos(ext[0], box), _border_pos(ext[-1], box)
    pts = list(ext)
    if pa > pb:
        pa, pb = pb, pa
        pts = pts[::-1]
    if pa < W < pb:                          # arc (pa, pb) holds the right corner
        return pa, pb, pts
    # the other arc does: walk from pb to pa + P
    return pb, pa + P, pts[::-1]


def _poly_path(poly):
    reg = pathops.Path()
    pen = reg.getPen()
    pen.moveTo(poly[0])
    for q in poly[1:]:
        pen.lineTo(q)
    pen.closePath()
    reg.fillType = pathops.FillType.WINDING
    return reg


def cut_run(d, cuts, z=8, tol=0.005):
    """Split the run `d` (one evenodd path) by `cuts` (polylines in page units, each
    crossing the stroke once) into pieces ordered right→left. Raises CutError when the
    piece count, an empty piece, or the area balance says the cut did not do what was
    asked."""
    run = to_path(d)
    run.simplify()
    total = abs(run.area)
    if not cuts:
        return [path_d(run)]
    polys = flatten(d)
    chords, box = [], None
    for cut in cuts:
        ext, box = extend_cut(polys, cut, z=z)
        chords.append(_chord(ext, box))
    chords.sort(key=lambda c: c[1] - c[0])          # smallest right side = rightmost cut
    for (a1, b1, _), (a2, b2, _) in zip(chords, chords[1:]):
        if not (a2 <= a1 and b1 <= b2):
            raise CutError("cuts not nested")
    P = _perim(box)
    regions = []
    a, b, pts = chords[0]                            # rightmost: the chord's right side
    regions.append(pts[::-1] + _border_walk(a, b, box))
    for (aR, bR, pR), (aL, bL, pL) in zip(chords, chords[1:]):
        poly = list(pR) + _border_walk(bR, bL, box) + list(pL)[::-1] + _border_walk(aL, aR + (P if aR < aL else 0), box)
        regions.append(poly)
    a, b, pts = chords[-1]                           # leftmost: complement of the last right side
    regions.append(list(pts) + _border_walk(b, a + P, box))
    pieces = []
    for k, poly in enumerate(regions):
        piece = pathops.op(run, _poly_path(poly), pathops.PathOp.INTERSECTION)
        piece.simplify()
        ar = abs(piece.area)
        if ar < 0.05:
            raise CutError("empty piece", piece=k, area=ar)
        pieces.append((piece, ar))
    s = sum(ar for _, ar in pieces)
    if abs(s - total) > max(tol * total, 0.02):
        raise CutError("area not conserved", total=total, pieces=s)
    return [path_d(p) for p, _ in pieces]


# ----------------------------------------------------------------------------
# the word-level SVG as data
# ----------------------------------------------------------------------------
_WORD = re.compile(r'<g class="word"([^>]*)>(.*?)</g>\s*</g>', re.S)
_ATTR = re.compile(r'([a-zA-Z:-]+)="([^"]*)"')
_LIG = re.compile(r'<g class="ligature" data-text="([^"]*)">(.*?)</g>', re.S)
_PATH = re.compile(r'<path ([^>]*?)/>', re.S)


def parse_attrs(s):
    return dict(_ATTR.findall(s))


def read_words(page, svg_dir=WORDS_SVG):
    """Words of a page in reading order:
    {'wid','uthmani','attrs','span':(start,end),'ligatures':[{'text','paths':[…]}],
     'paths':[{'kind','mark','eid','d','attrs','raw'}…] (all paths, document order)}."""
    s = open(os.path.join(svg_dir, "%03d.svg" % page), encoding="utf-8").read()
    words = []
    for m in _WORD.finditer(s):
        attrs = parse_attrs(m.group(1))
        body = m.group(2) + "</g>"        # the inner text up to (excluding) the last </g>
        # the regex consumed one inner "</g>" as part of the word close; rebuild the inner
        inner = m.group(0)[len('<g class="word"') + len(m.group(1)) + 1:-len("</g>")]
        ligs, paths = [], []
        for lm in _LIG.finditer(inner):
            lp = []
            for pm in _PATH.finditer(lm.group(2)):
                a = parse_attrs(pm.group(1))
                rec = {"kind": a.get("data-kind"), "mark": a.get("data-mark"),
                       "eid": a.get("data-eid"), "d": a.get("d"), "attrs": a,
                       "raw": pm.group(0)}
                lp.append(rec)
                paths.append(rec)
            ligs.append({"text": lm.group(1), "paths": lp})
        # word-level paths outside any ligature (waqf signs etc.)
        rest = _LIG.sub("", inner)
        for pm in _PATH.finditer(rest):
            a = parse_attrs(pm.group(1))
            rec = {"kind": a.get("data-kind"), "mark": a.get("data-mark"),
                   "eid": a.get("data-eid"), "d": a.get("d"), "attrs": a,
                   "raw": pm.group(0), "loose": True}
            paths.append(rec)
        words.append({"wid": attrs.get("data-wid"), "uthmani": attrs.get("data-uthmani", ""),
                      "attrs": attrs, "span": m.span(), "ligatures": ligs, "paths": paths,
                      "inner": inner})
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
