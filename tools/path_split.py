#!/usr/bin/env python3
"""Split an outline by a straight chord, exactly, on the curves themselves.

The letter cutter has always split a run by rasterising it, deciding ownership per pixel,
tracing a polygon around each letter's pixels and intersecting the run with that polygon.
The polygon is a PIXEL STAIRCASE, and that is where the cutter's remaining defects come
from: a staircase step crossing a thin stroke shears off a sliver, so a letter that is one
stroke is emitted as two pieces (3,531 letters, measured 2026-09-08), and the same
staircase is what the area and reproduce checks trip over.

This module does the cut where it belongs -- on the outline. A chord is a straight
segment; every place it crosses the outline is found by solving the segment against the
line or cubic it crosses, the outline is divided at exactly those parameters with de
Casteljau, and each side is closed along the chord itself. No pixel ever enters it, so:

  * every boundary curve of a piece is either the run's own curve, bit for bit, or a
    straight run along the chord -- nothing is refitted;
  * the two pieces share their cut edge exactly, so their union is the original and
    their areas sum to it, to floating point rather than to a tolerance;
  * a letter cannot gain a sliver, because there is no staircase to shear one off.

Holes are handled by the same walk: a contour the chord misses goes whole to the side it
lies on, which is decided by the winding of the piece it falls inside.
"""
import math

EPS = 1e-9


# --- curve primitives ------------------------------------------------------------

def _bez_point(seg, p0, t):
    """Point at t on a segment given its start point."""
    kind, v = seg
    if kind == "L":
        return (p0[0] + (v[0] - p0[0]) * t, p0[1] + (v[1] - p0[1]) * t)
    u = 1 - t
    if kind == "Q":
        return (u * u * p0[0] + 2 * u * t * v[0] + t * t * v[2],
                u * u * p0[1] + 2 * u * t * v[1] + t * t * v[3])
    return (u ** 3 * p0[0] + 3 * u * u * t * v[0] + 3 * u * t * t * v[2] + t ** 3 * v[4],
            u ** 3 * p0[1] + 3 * u * u * t * v[1] + 3 * u * t * t * v[3] + t ** 3 * v[5])


def _split_seg(seg, p0, t):
    """de Casteljau: (first half, second half), each as (kind, values), exact at t."""
    kind, v = seg
    if kind == "L":
        m = _bez_point(seg, p0, t)
        return ("L", m), ("L", v)
    if kind == "Q":
        c, p1 = (v[0], v[1]), (v[2], v[3])
        a = _lerp(p0, c, t)
        b = _lerp(c, p1, t)
        m = _lerp(a, b, t)
        return ("Q", (a[0], a[1], m[0], m[1])), ("Q", (b[0], b[1], p1[0], p1[1]))
    c1, c2, p1 = (v[0], v[1]), (v[2], v[3]), (v[4], v[5])
    a = _lerp(p0, c1, t)
    b = _lerp(c1, c2, t)
    c = _lerp(c2, p1, t)
    d = _lerp(a, b, t)
    e = _lerp(b, c, t)
    m = _lerp(d, e, t)
    return (("C", (a[0], a[1], d[0], d[1], m[0], m[1])),
            ("C", (e[0], e[1], c[0], c[1], p1[0], p1[1])))


def _lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _seg_end(seg):
    kind, v = seg
    return (v[0], v[1]) if kind == "L" else (v[2], v[3]) if kind == "Q" else (v[4], v[5])


def _roots(coeffs):
    """Real roots of a polynomial given highest power first, for degree <= 3."""
    c = list(coeffs)
    while c and abs(c[0]) < 1e-14:
        c.pop(0)
    n = len(c) - 1
    if n <= 0:
        return []
    if n == 1:
        return [-c[1] / c[0]]
    if n == 2:
        a, b, cc = c
        disc = b * b - 4 * a * cc
        if disc < 0:
            return []
        s = math.sqrt(disc)
        return [(-b + s) / (2 * a), (-b - s) / (2 * a)]
    a, b, cc, d = c
    b, cc, d = b / a, cc / a, d / a
    p = cc - b * b / 3.0
    q = 2 * b ** 3 / 27.0 - b * cc / 3.0 + d
    disc = (q / 2.0) ** 2 + (p / 3.0) ** 3
    out = []
    if disc >= 0:
        s = math.sqrt(disc)
        u = math.copysign(abs(-q / 2.0 + s) ** (1 / 3.0), -q / 2.0 + s)
        v = math.copysign(abs(-q / 2.0 - s) ** (1 / 3.0), -q / 2.0 - s)
        out.append(u + v - b / 3.0)
    else:
        r = math.sqrt(-(p ** 3) / 27.0)
        phi = math.acos(max(-1.0, min(1.0, -q / (2 * r))))
        m = 2 * math.sqrt(-p / 3.0)
        for k in range(3):
            out.append(m * math.cos((phi + 2 * math.pi * k) / 3.0) - b / 3.0)
    return out


def seg_line_crossings(seg, p0, a, b):
    """Parameters t in (0,1) where the segment crosses the INFINITE line through a,b,
    with the signed side function; returned sorted."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    # side(p) = (p - a) x (b - a) ; zero on the line
    def side_of(px, py):
        return (px - a[0]) * dy - (py - a[1]) * dx

    kind, v = seg
    if kind == "L":
        s0, s1 = side_of(*p0), side_of(v[0], v[1])
        if abs(s0 - s1) < EPS:
            return []
        t = s0 / (s0 - s1)
        return [t] if EPS < t < 1 - EPS else []
    if kind == "Q":
        c0 = side_of(*p0)
        c1 = side_of(v[0], v[1])
        c2 = side_of(v[2], v[3])
        # (1-t)^2 c0 + 2(1-t)t c1 + t^2 c2
        A = c0 - 2 * c1 + c2
        B = -2 * c0 + 2 * c1
        C = c0
        ts = _roots([A, B, C])
    else:
        c0 = side_of(*p0)
        c1 = side_of(v[0], v[1])
        c2 = side_of(v[2], v[3])
        c3 = side_of(v[4], v[5])
        A = -c0 + 3 * c1 - 3 * c2 + c3
        B = 3 * c0 - 6 * c1 + 3 * c2
        C = -3 * c0 + 3 * c1
        D = c0
        ts = _roots([A, B, C, D])
    return sorted(t for t in ts if EPS < t < 1 - EPS)


# --- splitting a contour ---------------------------------------------------------

def contour_segments(sub):
    """[('M',p)] + segments  ->  (start point, [segments]) with the closing line added."""
    start = sub[0][1]
    segs = list(sub[1:])
    if not segs:
        return start, []
    if _dist(_seg_end(segs[-1]), start) > 1e-7:
        segs.append(("L", start))
    return start, segs


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def split_contour(start, segs, a, b):
    """Cut a closed contour at every crossing of the line a-b.

    Returns [(side, [(seg, p0), …]), …] arcs in order, side = +1/-1 telling which side
    of the line the arc lies on, and the crossing points between consecutive arcs.
    """
    pieces = []
    p = start
    for seg in segs:
        ts = seg_line_crossings(seg, p, a, b)
        cur_p, cur_seg = p, seg
        prev_t = 0.0
        for t in ts:
            tt = (t - prev_t) / (1.0 - prev_t)
            first, second = _split_seg(cur_seg, cur_p, tt)
            pieces.append((cur_p, first))
            cur_p = _seg_end(first)
            cur_seg = second
            prev_t = t
        pieces.append((cur_p, cur_seg))
        p = _seg_end(seg)
    return pieces


def side_of_point(pt, a, b):
    return (pt[0] - a[0]) * (b[1] - a[1]) - (pt[1] - a[1]) * (b[0] - a[0])


def split_subpath_by_line(sub, a, b, tol=1e-7):
    """Split one closed subpath by the infinite line a-b.

    Returns (pieces_pos, pieces_neg): each a list of subpaths (in parse_d form) lying
    wholly on that side. A subpath the line misses comes back whole on its own side.
    """
    start, segs = contour_segments(sub)
    if not segs:
        return [], []
    parts = split_contour(start, segs, a, b)
    # Which side each arc lies on, judged at its midpoint. The side is read from the arcs
    # rather than from the crossing count, because a contour can cross the line exactly at
    # a vertex -- a circle cut through its centre touches at two segment ends and no
    # crossing falls strictly inside any segment. Counting parts would call that a miss.
    sides = []
    for p0, seg in parts:
        mid = _bez_point(seg, p0, 0.5)
        sides.append(1 if side_of_point(mid, a, b) >= 0 else -1)
    if len(set(sides)) == 1:                        # wholly one side
        whole = [("M", start)] + [seg for _, seg in parts]
        return ([whole], []) if sides[0] >= 0 else ([], [whole])
    runs = []
    i = 0
    n = len(parts)
    # rotate so a run starts at index 0
    shift = 0
    for k in range(n):
        if sides[k] != sides[k - 1]:
            shift = k
            break
    parts = parts[shift:] + parts[:shift]
    sides = sides[shift:] + sides[:shift]
    while i < n:
        j = i
        while j + 1 < n and sides[j + 1] == sides[i]:
            j += 1
        runs.append((sides[i], parts[i:j + 1]))
        i = j + 1
    pos, neg = [], []
    for s, run in runs:
        sub_out = [("M", run[0][0])] + [seg for _, seg in run]
        end = _seg_end(run[-1][1])
        if _dist(end, run[0][0]) > tol:
            sub_out.append(("L", run[0][0]))        # close along the chord
        (pos if s >= 0 else neg).append(sub_out)
    return pos, neg


def to_d(subs, prec=6):
    """parse_d form -> a path string."""
    out = []
    for sub in subs:
        for k, (kind, v) in enumerate(sub):
            if kind == "M":
                out.append("M%s %s" % (_n(v[0], prec), _n(v[1], prec)))
            elif kind == "L":
                out.append("L%s %s" % (_n(v[0], prec), _n(v[1], prec)))
            elif kind == "Q":
                out.append("Q%s %s %s %s" % tuple(_n(x, prec) for x in v))
            else:
                out.append("C%s %s %s %s %s %s" % tuple(_n(x, prec) for x in v))
        out.append("Z")
    return "".join(out)


def _n(v, prec):
    s = ("%." + str(prec) + "f") % v
    s = s.rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


# 3-point Gauss-Legendre on [0,1]: exact for polynomials up to degree 5, which is what
# x*y' - y*x' is for a cubic. So the area below is exact, not sampled -- the check on a
# split has to be sharper than the thing it is checking.
_GAUSS = (((1 - (3 / 5) ** 0.5) / 2, 5 / 18),
          (0.5, 8 / 18),
          ((1 + (3 / 5) ** 0.5) / 2, 5 / 18))


def _seg_deriv(seg, p0, t):
    kind, v = seg
    if kind == "L":
        return (v[0] - p0[0], v[1] - p0[1])
    u = 1 - t
    if kind == "Q":
        return (2 * u * (v[0] - p0[0]) + 2 * t * (v[2] - v[0]),
                2 * u * (v[1] - p0[1]) + 2 * t * (v[3] - v[1]))
    return (3 * u * u * (v[0] - p0[0]) + 6 * u * t * (v[2] - v[0]) + 3 * t * t * (v[4] - v[2]),
            3 * u * u * (v[1] - p0[1]) + 6 * u * t * (v[3] - v[1]) + 3 * t * t * (v[5] - v[3]))


def poly_area(sub):
    """Signed area of a closed subpath, curves included, exactly."""
    total = 0.0
    p = sub[0][1]
    start = p
    for kind, v in sub[1:]:
        seg = (kind, v)
        for t, w in _GAUSS:
            x, y = _bez_point(seg, p, t)
            dx, dy = _seg_deriv(seg, p, t)
            total += w * (x * dy - y * dx)
        p = _seg_end(seg)
    if _dist(p, start) > 1e-9:                      # implicit closing line
        x0, y0 = p
        x1, y1 = start
        total += (x0 * y1 - x1 * y0)
    return total / 2.0

# --- splitting a whole path (all its contours at once) ---------------------------

class SplitError(Exception):
    pass


def _reverse_run(run):
    """The same arc walked the other way. A hole is wound against its outer contour, so
    the walk meets its arcs end-first and has to be able to run one backwards."""
    out = []
    for p0, seg in reversed(run):
        kind, v = seg
        end = _seg_end(seg)
        if kind == "L":
            rev = ("L", (p0[0], p0[1]))
        elif kind == "Q":
            rev = ("Q", (v[0], v[1], p0[0], p0[1]))
        else:
            rev = ("C", (v[2], v[3], v[0], v[1], p0[0], p0[1]))
        out.append((end, rev))
    return out


def split_path_by_line(subs, a, b, tol=1e-7):
    """Split a whole outline (outer contours and holes together) by the line a-b.

    Returns (pos, neg), each a list of closed subpaths.

    Closing each arc with a straight line from its own end back to its own start is
    wrong the moment the line crosses a contour more than twice: the closure then runs
    through the GAPS between strokes and encloses them, which is how a piece came out
    three times the area of the run it was cut from. The line is only inside the shape
    on alternate intervals between its crossings, so the closure has to follow it there
    and nowhere else.

    So every contour's crossings go into one list, sorted along the line; sorted
    crossings alternate entering and leaving, which pairs them (0,1), (2,3), … Each pair
    spans one interval of the line that lies inside the shape. An arc is then closed by
    jumping from its end crossing to that crossing's partner and picking up the arc that
    starts there. Holes need no special case: their crossings are in the same list, so
    an interval that a hole interrupts is split by the hole's own crossings.

    Raises SplitError on an odd number of crossings (a tangency), where entering and
    leaving cannot be told apart and the caller should fall back.
    """
    dx, dy = b[0] - a[0], b[1] - a[1]
    nn = math.hypot(dx, dy)
    if nn < EPS:
        raise SplitError("degenerate chord")
    ux, uy = dx / nn, dy / nn

    arcs = []            # (side, [ (p0, seg) … ], start_xy, end_xy)
    whole = []           # (side, subpath) for contours the line misses
    for sub in subs:
        start, segs = contour_segments(sub)
        if not segs:
            continue
        parts = split_contour(start, segs, a, b)
        sides = []
        for p0, seg in parts:
            mid = _bez_point(seg, p0, 0.5)
            sides.append(1 if side_of_point(mid, a, b) >= 0 else -1)
        if len(set(sides)) == 1:
            whole.append((sides[0], [("M", start)] + [seg for _, seg in parts]))
            continue
        shift = next(k for k in range(len(parts)) if sides[k] != sides[k - 1])
        parts = parts[shift:] + parts[:shift]
        sides = sides[shift:] + sides[:shift]
        i, n = 0, len(parts)
        while i < n:
            j = i
            while j + 1 < n and sides[j + 1] == sides[i]:
                j += 1
            run = parts[i:j + 1]
            arcs.append((sides[i], run, run[0][0], _seg_end(run[-1][1])))
            i = j + 1

    if not arcs:
        pos = [sub for s, sub in whole if s >= 0]
        neg = [sub for s, sub in whole if s < 0]
        return pos, neg

    # every arc end is a crossing; gather them once, in order along the line
    pts = []
    for _, _, s_xy, e_xy in arcs:
        pts.append(s_xy)
        pts.append(e_xy)
    uniq = []
    for q in pts:
        for k, r in enumerate(uniq):
            if _dist(q, r) <= 1e-6:
                break
        else:
            uniq.append(q)
    if len(uniq) % 2:
        raise SplitError("odd number of crossings (tangency)")
    order = sorted(range(len(uniq)), key=lambda k: (uniq[k][0] - a[0]) * ux + (uniq[k][1] - a[1]) * uy)
    partner = {}
    for k in range(0, len(order), 2):
        i, j = order[k], order[k + 1]
        partner[i] = j
        partner[j] = i

    def cid(q):
        for k, r in enumerate(uniq):
            if _dist(q, r) <= 1e-6:
                return k
        raise SplitError("crossing lost")

    out = {1: [], -1: []}
    for side in (1, -1):
        mine = [(cid(s_xy), cid(e_xy), run) for sd, run, s_xy, e_xy in arcs if sd == side]
        by_start, by_end = {}, {}
        for k, (s, e, run) in enumerate(mine):
            by_start.setdefault(s, []).append(k)
            by_end.setdefault(e, []).append(k)
        used = set()
        for k0 in range(len(mine)):
            if k0 in used:
                continue
            segs_out = []
            k, rev = k0, False
            first = mine[k0][0]
            guard = 0
            while True:
                guard += 1
                if guard > 4 * len(mine) + 8:
                    raise SplitError("walk does not close")
                used.add(k)
                s, e, run = mine[k]
                if rev:
                    run = _reverse_run(run)
                    s, e = e, s
                if segs_out:
                    segs_out.append(("L", run[0][0]))       # along the line, inside the shape
                else:
                    segs_out.append(("M", run[0][0]))
                segs_out += [seg for _, seg in run]
                nxt = partner.get(e)
                if nxt is None:
                    raise SplitError("crossing without a partner")
                if nxt == first:
                    break
                cand = [c for c in by_start.get(nxt, []) if c not in used]
                if cand:
                    k, rev = cand[0], False
                else:
                    back = [c for c in by_end.get(nxt, []) if c not in used]
                    if not back:
                        raise SplitError("no arc continues the walk")
                    k, rev = back[0], True
            out[side].append(segs_out)
    for s, sub in whole:
        out[1 if s >= 0 else -1].append(sub)
    return out[1], out[-1]


def sample_contour(sub, per=8):
    """A closed polyline through a subpath, for containment tests only."""
    pts = [sub[0][1]]
    p = sub[0][1]
    for kind, v in sub[1:]:
        seg = (kind, v)
        for k in range(1, per + 1):
            pts.append(_bez_point(seg, p, k / float(per)))
        p = _seg_end(seg)
    return pts


def point_in(poly, pt):
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            xx = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if xx > x:
                inside = not inside
    return inside


def path_area(subs):
    """Material area of a set of closed subpaths under evenodd.

    Signed areas cannot be summed here: evenodd does not care which way a contour is
    wound, and in this artwork a hole is often wound the same way as the contour holding
    it, so the signs do not cancel. Nesting is what decides -- a contour lying inside an
    odd number of others is a hole -- so the depth is counted and the sign taken from its
    parity.
    """
    if not subs:
        return 0.0
    polys = [sample_contour(sub) for sub in subs]
    total = 0.0
    for i, sub in enumerate(subs):
        depth = 0
        for j, other in enumerate(polys):
            if i != j and point_in(other, polys[i][0]):
                depth += 1
        total += (-1 if depth % 2 else 1) * abs(poly_area(sub))
    return abs(total)


def inside(subs, pt):
    """Is the point inside the region under the evenodd rule?"""
    n = 0
    for sub in subs:
        if point_in(sample_contour(sub), pt):
            n += 1
    return bool(n % 2)


def split_contour_by_chord(sub, A, B, tol=1e-6, margin=0.75):
    """Cut one closed contour with the chord SEGMENT A-B, not with its line.

    A chord is drawn across a stroke and crosses the outline twice, there and nowhere
    else. Its infinite line, though, reaches the whole run and cuts wherever it lands,
    which is how an exact split still produced a letter in four pieces. So only crossings
    that lie within the segment count, and the two arcs are closed along the chord itself.

    Returns (piece_a, piece_b) as subpaths, or None when the segment does not cross this
    contour exactly twice -- a tangency, a graze, or a chord that misses.
    """
    start, segs = contour_segments(sub)
    if not segs:
        return None
    ax, ay = A
    bx, by = B
    dx, dy = bx - ax, by - ay
    den = dx * dx + dy * dy
    if den < EPS:
        return None
    # A chord is drawn between the two banks of the stroke, so its ends sit ON the
    # outline or just short of it, and the crossings then fall a hair outside [0,1].
    # `margin` (in page units) lets the segment reach that far past each end and no
    # further, which keeps the cut local without demanding the chord be drawn long.
    ext = margin / max(math.sqrt(den), EPS)
    hits = []                       # (segment index, t, u along the chord)
    p = start
    for i, seg in enumerate(segs):
        for t in seg_line_crossings(seg, p, A, B):
            q = _bez_point(seg, p, t)
            u = ((q[0] - ax) * dx + (q[1] - ay) * dy) / den
            if -ext - tol <= u <= 1 + ext + tol:
                hits.append((i, t, u))
        p = _seg_end(seg)
    if len(hits) != 2:
        return None
    hits.sort()
    parts = []                      # rebuild the contour, split at the two hits
    p = start
    cut_pts = []
    for i, seg in enumerate(segs):
        ts = [t for (si, t, _) in hits if si == i]
        cur_p, cur_seg, prev = p, seg, 0.0
        for t in sorted(ts):
            tt = (t - prev) / (1.0 - prev)
            first, second = _split_seg(cur_seg, cur_p, tt)
            parts.append((cur_p, first, True))
            cut_pts.append(_seg_end(first))
            cur_p, cur_seg, prev = _seg_end(first), second, t
        parts.append((cur_p, cur_seg, False))
        p = _seg_end(seg)
    # The closure runs straight between the two crossings, so it has to lie inside the
    # contour: where it does not, the piece bulges past the outline and adds ink that was
    # never there (one pixel at 223/255 on p74, which the pixel gate rightly caught).
    poly = sample_contour(sub, per=16)
    q1, q2 = cut_pts[0], cut_pts[1]
    for i in range(1, 40):
        f = i / 40.0
        mid = (q1[0] + (q2[0] - q1[0]) * f, q1[1] + (q2[1] - q1[1]) * f)
        if not point_in(poly, mid):
            return None
    # walk from one cut point to the other, twice
    idx = [k for k, (_, _, ends_at_cut) in enumerate(parts) if ends_at_cut]
    if len(idx) != 2:
        return None
    k0, k1 = idx
    arc1 = parts[k0 + 1:k1 + 1]
    arc2 = parts[k1 + 1:] + parts[:k0 + 1]
    out = []
    for arc in (arc1, arc2):
        if not arc:
            return None
        sp = [("M", arc[0][0])] + [seg for _, seg, _ in arc]
        if _dist(_seg_end(arc[-1][1]), arc[0][0]) > tol:
            sp.append(("L", arc[0][0]))
        out.append(sp)
    return out[0], out[1]


def chord_hits(sub, A, B, margin=0.75, tol=1e-6):
    """How many times the chord SEGMENT (with its margin) crosses this contour."""
    start, segs = contour_segments(sub)
    if not segs:
        return 0
    ax, ay = A
    dx, dy = B[0] - ax, B[1] - ay
    den = dx * dx + dy * dy
    if den < EPS:
        return 0
    ext = margin / max(math.sqrt(den), EPS)
    n = 0
    p = start
    for seg in segs:
        for t in seg_line_crossings(seg, p, A, B):
            q = _bez_point(seg, p, t)
            u = ((q[0] - ax) * dx + (q[1] - ay) * dy) / den
            if -ext - tol <= u <= 1 + ext + tol:
                n += 1
        p = _seg_end(seg)
    return n
