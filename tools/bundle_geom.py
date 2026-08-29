#!/usr/bin/env python3
"""Exact bounding boxes for SVG path data, and 2-D affine transforms.

Used by build_bundle.py to ship word boxes that a consumer can trust for
hit-testing without rendering.

Why exact and not the control-point hull: a cubic's control points lie
OUTSIDE the curve, so the hull is a superset — on this artwork it overstates
a word's box by up to several units, which is enough to make two adjacent
words' boxes overlap when the ink does not.  Here the extrema of each Bezier
segment are solved for directly (quadratic in t for cubics, linear for
quadratics), so the box is the true tight box of the outline.

Arcs (A/a) are not implemented: the mushaf artwork contains none — measured
over all 604 pages, the command set is M m L l H h V v C c S s Q q T t Z z.
An arc raises ValueError rather than being silently mis-measured.
"""
import math
import re

_NUM = re.compile(r'[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?')
_CMD = re.compile(r'[MmLlHhVvCcSsQqTtAaZz]')

# how many coordinate numbers each command consumes per repetition
_ARITY = {"M": 2, "L": 2, "T": 2, "H": 1, "V": 1,
          "C": 6, "S": 4, "Q": 4, "A": 7, "Z": 0}


# --------------------------------------------------------------- transforms

IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def mat_mul(M, N):
    """Return M then N applied after it, i.e. the matrix for N(M(p))."""
    a, b, c, d, e, f = M
    na, nb, nc, nd, ne, nf = N
    return (na * a + nc * b, nb * a + nd * b,
            na * c + nc * d, nb * c + nd * d,
            na * e + nc * f + ne, nb * e + nd * f + nf)


def parse_transform(t):
    """Parse an SVG transform attribute into a single matrix.

    Handles matrix/translate/scale/rotate; the artwork uses the first three.
    Transforms compose left-to-right as SVG specifies: the leftmost is applied
    last to a point, so the child frame is the rightmost.
    """
    M = IDENTITY
    for name, args in re.findall(
            r'(matrix|translate|scale|rotate)\s*\(([^)]*)\)', t or ""):
        v = [float(x) for x in _NUM.findall(args)]
        if name == "matrix":
            N = tuple(v[:6])
        elif name == "translate":
            N = (1.0, 0.0, 0.0, 1.0, v[0], v[1] if len(v) > 1 else 0.0)
        elif name == "scale":
            N = (v[0], 0.0, 0.0, v[1] if len(v) > 1 else v[0], 0.0, 0.0)
        else:
            r = math.radians(v[0])
            N = (math.cos(r), math.sin(r), -math.sin(r), math.cos(r), 0.0, 0.0)
        M = mat_mul(N, M)          # N is the parent of everything seen so far
    return M


def apply(M, x, y):
    a, b, c, d, e, f = M
    return a * x + c * y + e, b * x + d * y + f


# ------------------------------------------------------------ path segments

def _cubic_extrema(p0, p1, p2, p3):
    """Parameter values in (0,1) where a cubic's derivative vanishes."""
    out = []
    a = -p0 + 3 * p1 - 3 * p2 + p3
    b = 2 * (p0 - 2 * p1 + p2)
    c = p1 - p0
    if abs(a) < 1e-12:
        if abs(b) > 1e-12:
            t = -c / b
            if 0 < t < 1:
                out.append(t)
        return out
    disc = b * b - 4 * a * c
    if disc < 0:
        return out
    r = math.sqrt(disc)
    for t in ((-b + r) / (2 * a), (-b - r) / (2 * a)):
        if 0 < t < 1:
            out.append(t)
    return out


def _cubic_at(p0, p1, p2, p3, t):
    u = 1 - t
    return (u * u * u * p0 + 3 * u * u * t * p1
            + 3 * u * t * t * p2 + t * t * t * p3)


def path_extremes(d, M=IDENTITY):
    """Return (x0, y0, x1, y1) of the path `d` after transform `M`.

    Returns None for a path that draws nothing.
    """
    lo_x = lo_y = math.inf
    hi_x = hi_y = -math.inf

    def hit(x, y):
        nonlocal lo_x, lo_y, hi_x, hi_y
        tx, ty = apply(M, x, y)
        if tx < lo_x:
            lo_x = tx
        if ty < lo_y:
            lo_y = ty
        if tx > hi_x:
            hi_x = tx
        if ty > hi_y:
            hi_y = ty

    def curve(p0, p1, p2, p3):
        """Cubic from p0 to p3; record endpoints and interior extrema."""
        hit(*p3)
        for coord in (0, 1):
            vals = (p0[coord], p1[coord], p2[coord], p3[coord])
            for t in _cubic_extrema(*vals):
                other = 1 - coord
                v = _cubic_at(*vals, t)
                w = _cubic_at(p0[other], p1[other], p2[other], p3[other], t)
                hit(*((v, w) if coord == 0 else (w, v)))

    x = y = sx = sy = 0.0
    prev_c2 = None          # last cubic's second control point (for S)
    prev_q1 = None          # last quadratic's control point (for T)
    started = False

    toks = [(m.group(0), m.start(), m.end()) for m in _CMD.finditer(d)]
    for k, (cmd, _s, e) in enumerate(toks):
        end = toks[k + 1][1] if k + 1 < len(toks) else len(d)
        nums = [float(v) for v in _NUM.findall(d[e:end])]
        rel = cmd.islower()
        c = cmd.upper()
        if c == "A":
            raise ValueError("elliptical arc in path data is not supported")
        if c == "Z":
            x, y = sx, sy
            prev_c2 = prev_q1 = None
            continue
        step = _ARITY[c]
        first = True
        for j in range(0, len(nums) - step + 1, step):
            g = nums[j:j + step]
            bx, by = (x, y) if rel else (0.0, 0.0)
            if c == "H":
                nx, ny = (x + g[0] if rel else g[0]), y
                hit(nx, ny)
                prev_c2 = prev_q1 = None
            elif c == "V":
                nx, ny = x, (y + g[0] if rel else g[0])
                hit(nx, ny)
                prev_c2 = prev_q1 = None
            elif c in ("M", "L"):
                nx, ny = bx + g[0], by + g[1]
                hit(nx, ny)
                if c == "M" and first:
                    sx, sy = nx, ny
                    started = True
                prev_c2 = prev_q1 = None
            elif c == "C":
                c1 = (bx + g[0], by + g[1])
                c2 = (bx + g[2], by + g[3])
                nx, ny = bx + g[4], by + g[5]
                curve((x, y), c1, c2, (nx, ny))
                prev_c2, prev_q1 = c2, None
            elif c == "S":
                c1 = (2 * x - prev_c2[0], 2 * y - prev_c2[1]) if prev_c2 \
                    else (x, y)
                c2 = (bx + g[0], by + g[1])
                nx, ny = bx + g[2], by + g[3]
                curve((x, y), c1, c2, (nx, ny))
                prev_c2, prev_q1 = c2, None
            elif c in ("Q", "T"):
                if c == "Q":
                    q = (bx + g[0], by + g[1])
                    nx, ny = bx + g[2], by + g[3]
                else:
                    q = (2 * x - prev_q1[0], 2 * y - prev_q1[1]) if prev_q1 \
                        else (x, y)
                    nx, ny = bx + g[0], by + g[1]
                # exact degree elevation: a quadratic IS a cubic
                c1 = (x + 2.0 / 3 * (q[0] - x), y + 2.0 / 3 * (q[1] - y))
                c2 = (nx + 2.0 / 3 * (q[0] - nx), ny + 2.0 / 3 * (q[1] - ny))
                curve((x, y), c1, c2, (nx, ny))
                prev_q1, prev_c2 = q, c2
            x, y = nx, ny
            first = False
    if not started or lo_x is math.inf:
        return None
    return lo_x, lo_y, hi_x, hi_y


def union(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))
