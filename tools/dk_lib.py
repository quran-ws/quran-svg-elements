#!/usr/bin/env python3
"""DigitalKhatt letter templates: WHICH ink is which letter, and the neck cut.

`DigitalKhattV2.otf` (in `.cache/digitalkhatt/`) shaped with HarfBuzz yields one glyph
per letter, stacked joints included (`hah.medi.afterbeh`, `lam.init.lam_hah`…). The
font models this print rather than reproducing it (IoU 0.46–0.77 against the ink,
measured 2026-09-04), so its outlines are used only as TEMPLATES: every ink pixel of a
run takes the label of the nearest registered letter template, which gave the correct
partition on every p50 word tried. The cut itself is then placed at the thinnest
crossing of the stroke near the label boundary — the neck — which is where a hand
cuts too. The hand cuts from tajweed_lib are the yardstick for these.

Spec: docs/superpowers/specs/2026-09-05-letter-level-decomposition-design.md
"""
import os

import numpy as np
import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from scipy import ndimage, signal

from tools import letters_lib as L

FONT = os.path.join(L.ROOT, ".cache", "digitalkhatt", "DigitalKhattV2.otf")
_MARK_WORDS = ("fatha", "kasra", "damma", "sukun", "shadda", "dot", "wasla", "tanween",
               "small", "madda", "hamzaabove", "hamzabelow", "hamza.", "dammatan",
               "fathatan", "kasratan", "waqf", "meemiqlab", "lowmeem", "circle", "sifr",
               "space", "null", "linefeed", "cgj", ".notdef")
_JOIN_STROKE = ("tatweel", "kashida")


class _DK:
    def __init__(self):
        self.tt = TTFont(FONT)
        self.gs = self.tt.getGlyphSet()
        blob = hb.Blob.from_file_path(FONT)
        self.face = hb.Face(blob)
        self.font = hb.Font(self.face)
        self._cache = {}

    def outline(self, name):
        if name not in self._cache:
            pen = SVGPathPen(self.gs)
            self.gs[name].draw(pen)
            self._cache[name] = L.flatten(pen.getCommands(), steps=8)
        return self._cache[name]


_dk = None


def dk():
    global _dk
    if _dk is None:
        _dk = _DK()
    return _dk


def is_body(name):
    return not any(m in name for m in _MARK_WORDS)


def shape(text):
    """Body glyphs of `text` in visual order left→right:
    [(glyph, cluster, x, y_off, advance)] with x the pen position (font units)."""
    D = dk()
    buf = hb.Buffer()
    buf.add_str(text)
    buf.direction, buf.script, buf.language = "rtl", "Arab", "ar"
    hb.shape(D.font, buf)
    out, x = [], 0
    for i, p in zip(buf.glyph_infos, buf.glyph_positions):
        name = D.font.glyph_to_string(i.codepoint)
        if is_body(name):
            out.append((name, i.cluster, x + p.x_offset, p.y_offset, p.x_advance))
        x += p.x_advance
    return out


def letter_glyphs(text, letters):
    """One DK body glyph (name, x, y_off) per letter index, or None. Clusters are char
    indices into `text`; a letter's base char index is recovered by walking the text
    the way letters_of() does. Joining strokes (tatweel) go to the letter on their
    right (the previous one in reading order)."""
    base_idx = []
    for ci, ch in enumerate(text):
        if ch in L.HARAKA or ch in ("ـ", " "):
            continue
        base_idx.append(ci)
    if len(base_idx) != len(letters):
        return [None] * len(letters)
    by_cluster = {ci: li for li, ci in enumerate(base_idx)}
    out = [None] * len(letters)
    for name, cluster, x, y, adv in shape(text):
        li = by_cluster.get(cluster)
        if li is None:
            # a cluster on a mark char (rare): nearest base to the right in reading order
            cands = [c for c in base_idx if c <= cluster]
            li = by_cluster[max(cands)] if cands else None
        if li is None:
            continue
        if any(j in name for j in _JOIN_STROKE):
            continue
        if out[li] is None:
            out[li] = (name, x, y)
        else:                                 # two glyphs for one letter: keep both
            out[li] = out[li] + (name, x, y)
    return out


def _glyph_polys(entry):
    """Font-unit polys of a letter's glyph(s), positioned by their pen offsets."""
    polys = []
    for k in range(0, len(entry), 3):
        name, x, y = entry[k:k + 3]
        polys += L.transform_polys(dk().outline(name), 1.0, x, y)
    return polys


def label_run(run_polys, entries, z=8, pad=2.0, scales=(0.92, 1.0, 1.08)):
    """Label every ink pixel of the run with the nearest registered letter template.
    `entries` = letter_glyphs() entries for the run's letters, in reading order.
    Returns (labels, meta): labels[r, c] = letter position in the run or -1 outside the
    ink; meta = {'x0','y0','z','scale','dx','dy','iou','share':[fraction per letter]}."""
    if not run_polys or any(e is None for e in entries):
        return None, None
    bx0, by0, bx1, by1 = L.bbox(run_polys)
    x0, y0 = bx0 - pad, by0 - pad
    w, h = (bx1 - bx0) + 2 * pad, (by1 - by0) + 2 * pad
    ink = L.raster(run_polys, x0, y0, w, h, z)
    tpl_font = [_glyph_polys(e) for e in entries]
    gb = L.bbox([p for t in tpl_font for p in t])
    s0 = (bx1 - bx0) / max(1e-6, (gb[2] - gb[0]))
    best = None
    for sf in scales:
        s = s0 * sf
        # place the templates with their bbox top-left on the ink bbox top-left, then
        # let the correlation find the shift
        tx = bx0 - gb[0] * s
        ty = by0 - gb[1] * s
        masks = [L.raster(L.transform_polys(t, s, tx, ty), x0, y0, w, h, z) for t in tpl_font]
        union = np.any(masks, axis=0)
        if not union.any():
            continue
        corr = signal.correlate(ink.astype(np.float32), union.astype(np.float32), mode="full", method="fft")
        dy, dx = np.unravel_index(int(corr.argmax()), corr.shape)
        dy -= union.shape[0] - 1
        dx -= union.shape[1] - 1
        shifted = [ndimage.shift(m.astype(np.uint8), (dy, dx), order=0) > 0 for m in masks]
        u = np.any(shifted, axis=0)
        iou = float((ink & u).sum() / max(1, (ink | u).sum()))
        if best is None or iou > best[0]:
            best = (iou, s, dx, dy, shifted)
    if best is None:
        return None, None
    iou, s, dx, dy, masks = best
    masks = refine_templates(ink, masks, z)
    u = np.any(masks, axis=0)
    iou = float((ink & u).sum() / max(1, (ink | u).sum()))
    dist = np.stack([ndimage.distance_transform_edt(~m) if m.any() else np.full(ink.shape, 1e9) for m in masks])
    labels = np.where(ink, dist.argmin(axis=0), -1)
    n_ink = max(1, int(ink.sum()))
    share = [float((labels == i).sum() / n_ink) for i in range(len(entries))]
    meta = {"x0": x0, "y0": y0, "z": z, "scale": s, "dx": dx / z, "dy": dy / z, "iou": iou, "share": share,
            "masks": masks, "ink": ink}
    return labels, meta


def refine_templates(ink, masks, z, reach=1.3, order_tol=0.4):
    """Slide each registered template locally (±reach u) to where it covers the most
    ink and the least paper, keeping reading order: a template may not move past its
    neighbours' centres by more than order_tol u. The global placement matches the word
    as a whole; the print's letters sit a little differently from the model's."""
    field = ink.astype(np.float32) - 0.5 * (~ink).astype(np.float32)
    R = int(reach * z)
    out = []
    cx0 = []
    for m in masks:
        ys, xs = np.nonzero(m)
        cx0.append(xs.mean() if len(xs) else None)
    for i, m in enumerate(masks):
        if not m.any():
            out.append(m)
            continue
        corr = signal.correlate(field, m.astype(np.float32), mode="same", method="fft")
        H, W = ink.shape
        r0, c0 = H // 2, W // 2
        win = corr[max(0, r0 - R):r0 + R + 1, max(0, c0 - R):c0 + R + 1]
        dr, dc = np.unravel_index(int(win.argmax()), win.shape)
        dr += max(0, r0 - R) - r0
        dc += max(0, c0 - R) - c0
        moved = ndimage.shift(m.astype(np.uint8), (dr, dc), order=0) > 0
        # reading order: right→left means x centres decreasing with i
        cx = cx0[i] + dc
        ok = True
        if i > 0 and cx0[i - 1] is not None and cx > cx0[i - 1] + order_tol * z:
            ok = False
        if i + 1 < len(masks) and cx0[i + 1] is not None and cx < cx0[i + 1] - order_tol * z:
            ok = False
        out.append(moved if ok and moved.any() else m)
    return out


def centroids(labels, meta, n=None):
    """Per letter: the labelled ink pixel nearest the label's centroid (a point ON the
    letter's ink — a bowl's true centroid lies in empty space). None for a letter with
    no labelled pixel; the list has `n` entries (default: the number of templates)."""
    out = []
    if n is None:
        n = len(meta.get("masks", [])) or int(labels.max()) + 1
    for i in range(n):
        ys, xs = np.nonzero(labels == i)
        if not len(xs):
            out.append(None)
            continue
        cx, cy = xs.mean(), ys.mean()
        k = int(np.argmin((xs - cx) ** 2 + (ys - cy) ** 2))
        out.append((meta["x0"] + (xs[k] + 0.5) / meta["z"], meta["y0"] + (ys[k] + 0.5) / meta["z"]))
    return out


def anchors(labels, meta, n=None, min_px=15, min_frac=0.15):
    """Per letter: one ink point per connected region of its label (a medial kaf is an
    arm AND a baseline; a letter is every region its label covers). Each region's
    point is the region pixel nearest the region's centroid; regions under min_px or
    under min_frac of the letter's pixels are dropped. The first entry of each list is
    the largest region's point (the reference used to walk from)."""
    if n is None:
        n = len(meta.get("masks", [])) or int(labels.max()) + 1
    z, x0, y0 = meta["z"], meta["x0"], meta["y0"]
    masks = meta.get("masks")
    out = []
    for i in range(n):
        m = labels == i
        tot = int(m.sum())
        pts = []
        if tot:
            lab, k = ndimage.label(m, structure=np.ones((3, 3), dtype=bool))
            sizes = np.bincount(lab.ravel())
            covered = ndimage.binary_dilation(masks[i], iterations=2) if masks is not None else None
            for rank, cid in enumerate(sorted(range(1, k + 1), key=lambda c: -sizes[c])):
                if sizes[cid] < max(min_px, min_frac * tot):
                    continue
                # a second region counts only when the letter's own template covers it:
                # the label bleeds into neighbours where no template reaches
                if rank > 0 and covered is not None and (covered & (lab == cid)).sum() < 0.6 * sizes[cid]:
                    continue
                ys, xs = np.nonzero(lab == cid)
                cx, cy = xs.mean(), ys.mean()
                j = int(np.argmin((xs - cx) ** 2 + (ys - cy) ** 2))
                pts.append((x0 + (xs[j] + 0.5) / z, y0 + (ys[j] + 0.5) / z))
        out.append(pts)
    return out


def outer_polys(polys):
    """Contours not contained in another contour (holes are not cut endpoints)."""
    from tools.letters_lib import _pip
    return [p for i, p in enumerate(polys)
            if not any(j != i and _pip(p[0], q) for j, q in enumerate(polys))]


def neck_cut(run_polys, labels, meta, i, radius=1.8):
    """The shortest crossing of the stroke near the boundary between letter i and i+1.
    Returns {'poly':[A,B], 'neck', 'boundary_dist', 'thick'} or None."""
    z, x0, y0 = meta["z"], meta["x0"], meta["y0"]
    a, b = labels == i, labels == (i + 1)
    if not a.any() or not b.any():
        return None
    touch = a & ndimage.binary_dilation(b, iterations=1)
    touch |= b & ndimage.binary_dilation(a, iterations=1)
    if not touch.any():
        return None
    ys, xs = np.nonzero(touch)
    c = (x0 + (xs.mean() + 0.5) / z, y0 + (ys.mean() + 0.5) / z)
    ink = labels >= 0
    ink_d = ndimage.binary_dilation(ink, iterations=1)      # interior test tolerant to edge pixels
    dt = ndimage.distance_transform_edt(ink)
    thick = 2 * float(dt[int((c[1] - y0) * z), int((c[0] - x0) * z)]) / z
    pts = np.array(L.resample(run_polys, 0.05), dtype=float)      # holes too: a loop's wall can BE the joint
    near = pts[np.hypot(pts[:, 0] - c[0], pts[:, 1] - c[1]) < radius]
    if len(near) < 4:
        return None
    n = len(near)
    A = near[:, None, :]
    B = near[None, :, :]
    d = np.hypot(A[..., 0] - B[..., 0], A[..., 1] - B[..., 1])
    ok = d >= max(0.5 * thick, 0.2)
    # chord interior must be ink: sample 5 interior points
    for t in (0.2, 0.35, 0.5, 0.65, 0.8):
        px = A[..., 0] * (1 - t) + B[..., 0] * t
        py = A[..., 1] * (1 - t) + B[..., 1] * t
        cc = np.clip(((px - x0) * z).astype(int), 0, ink.shape[1] - 1)
        rr = np.clip(((py - y0) * z).astype(int), 0, ink.shape[0] - 1)
        ok &= ink_d[rr, cc]
    # the chord must pass near the boundary centroid
    mx = (A[..., 0] + B[..., 0]) / 2
    my = (A[..., 1] + B[..., 1]) / 2
    md = np.hypot(mx - c[0], my - c[1])
    ok &= md < max(0.9, 0.7 * thick)
    iu = np.triu_indices(n, 1)
    okf = ok[iu]
    if not okf.any():
        return None
    score = d[iu] + 0.35 * md[iu]
    score[~okf] = np.inf
    k = int(score.argmin())
    ia, ib = iu[0][k], iu[1][k]
    Apt, Bpt = tuple(map(float, near[ia])), tuple(map(float, near[ib]))
    return {"poly": [Apt, Bpt], "neck": float(d[ia, ib]), "boundary_dist": float(md[ia, ib]), "thick": thick}


def side_agreement(labels, meta, piece_masks):
    """For pieces produced by cutting, how well the label map agrees: for each letter
    the fraction of its labelled pixels inside the piece it was assigned to."""
    out = []
    for i, m in enumerate(piece_masks):
        li = labels == i
        out.append(float((li & m).sum() / max(1, li.sum())))
    return out


def joint_of_cut(labels, meta, polys, anchors_=None):
    """Which joint a cut (one or more polylines) closes: paint it over the run's ink
    and see on which side every ink region of every letter falls. Valid when all of a
    letter's regions agree and the letters split as {0..j} | {j+1..}; returns j."""
    ink, z, x0, y0 = meta["ink"], meta["z"], meta["x0"], meta["y0"]
    n = len(meta["masks"])
    if anchors_ is None:
        anchors_ = anchors(labels, meta, n)
    if any(not a for a in anchors_):
        return None
    if polys and isinstance(polys[0][0], (int, float)):
        polys = [polys]
    H, W = ink.shape
    strip = np.zeros(ink.shape, dtype=bool)
    for poly in polys:
        strip |= L._paint(poly, x0, y0, z, W, H)
    free = ink & ~strip
    lab, _n = ndimage.label(free, structure=L._FOUR)
    comp = []
    for pts in anchors_:
        ids = set()
        for p in pts:
            q = L._nearest_true(free, (min(H - 1, max(0, int((p[1] - y0) * z))), min(W - 1, max(0, int((p[0] - x0) * z)))), 3)
            ids.add(int(lab[q]) if q else 0)
        if 0 in ids:
            return None
        comp.append(ids)
    # letters split into two groups of components: {0..j} and {j+1..}
    for j in range(n - 1):
        a = set().union(*comp[:j + 1])
        b = set().union(*comp[j + 1:])
        if a & b:
            continue
        # the cut must be what separates them: without it they would be one
        return j
    return None


def _chord_at(run_polys, ink, ink_d, dt, c, x0, y0, z, radius=1.5, md_max=0.35):
    """Shortest contour-to-contour chord through the ink passing within md_max of c."""
    pts = np.array(L.resample(run_polys, 0.05), dtype=float)
    near = pts[np.hypot(pts[:, 0] - c[0], pts[:, 1] - c[1]) < radius]
    if len(near) < 4:
        return None
    n = len(near)
    A = near[:, None, :]
    B = near[None, :, :]
    d = np.hypot(A[..., 0] - B[..., 0], A[..., 1] - B[..., 1])
    thick = 2 * float(dt[int((c[1] - y0) * z), int((c[0] - x0) * z)]) / z
    ok = d >= max(0.8 * thick, 0.15)          # a crossing, not a nick in one edge
    for t in (0.2, 0.35, 0.5, 0.65, 0.8):
        px = A[..., 0] * (1 - t) + B[..., 0] * t
        py = A[..., 1] * (1 - t) + B[..., 1] * t
        cc = np.clip(((px - x0) * z).astype(int), 0, ink.shape[1] - 1)
        rr = np.clip(((py - y0) * z).astype(int), 0, ink.shape[0] - 1)
        ok &= ink_d[rr, cc]
    # the chord must pass through c: distance from c to the segment
    ax, ay = A[..., 0], A[..., 1]
    bx, by = B[..., 0], B[..., 1]
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy + 1e-9
    tt = np.clip(((c[0] - ax) * vx + (c[1] - ay) * vy) / L2, 0, 1)
    md = np.hypot(ax + tt * vx - c[0], ay + tt * vy - c[1])
    ok &= md < md_max
    iu = np.triu_indices(n, 1)
    okf = ok[iu]
    if not okf.any():
        return None
    score = d[iu] + 0.5 * md[iu]
    score[~okf] = np.inf
    k = int(score.argmin())
    ia, ib = iu[0][k], iu[1][k]
    Apt, Bpt = tuple(map(float, near[ia])), tuple(map(float, near[ib]))
    return {"poly": [Apt, Bpt], "neck": float(d[ia, ib]), "boundary_dist": float(md[ia, ib]), "thick": thick}


def _core(mask, ink):
    for it in (3, 2, 1):
        c = ndimage.binary_erosion(mask & ink, iterations=it)
        if c.sum() >= 12:
            return c
    return mask & ink


def _path(ink, cost, src_pts, dst_pts, blocked):
    """Cheapest path through ink (minus `blocked`) from any of src_pts to any of
    dst_pts; None when disconnected."""
    import heapq
    H, W = ink.shape
    free = ink & ~blocked
    dist = np.full(ink.shape, np.inf)
    prev = {}
    pq = []
    for p in src_pts:
        if free[p]:
            dist[p] = 0.0
            pq.append((0.0, p[0], p[1]))
    heapq.heapify(pq)
    dst = set(dst_pts)
    while pq:
        g, r, c = heapq.heappop(pq)
        if g > dist[r, c]:
            continue
        if (r, c) in dst:
            path = [(r, c)]
            while path[-1] in prev:
                path.append(prev[path[-1]])
            return path[::-1]
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < H and 0 <= nc < W and free[nr, nc]:
                ng = g + cost[nr, nc] * (1.4142 if dr and dc else 1.0)
                if ng < dist[nr, nc]:
                    dist[nr, nc] = ng
                    prev[(nr, nc)] = (r, c)
                    heapq.heappush(pq, (ng, nr, nc))
    return None


def joint_cut(run_polys, labels, meta, i, anchors_=None, max_chords=4):
    """The cut between letter i and i+1: the set of chords (usually one) that separates
    every ink region of letters ≤ i from every region of letters > i.

    Repeat until no path connects the two sides through ink not yet painted: take the
    cheapest path (along the stroke's centre line), try every point on it for the
    shortest crossing of the stroke through it, keep the crossings that separate the
    path's two ends, and choose the FIRST one after letter i's template ends — the
    connecting stroke belongs to the letter it enters — or the first one at all when
    the template overshoots. A chord across a loop's wall never separates (the ring
    connects around it), so a loop letter is cut right after its loop. A medial kaf
    needs two chords (its arm and its baseline both meet the stem); the second comes
    from the second path."""
    ink, masks, z, x0, y0 = meta["ink"], meta["masks"], meta["z"], meta["x0"], meta["y0"]
    n = len(masks)
    if i + 1 >= n:
        return None
    if anchors_ is None:
        anchors_ = anchors(labels, meta, n)
    H, W = ink.shape

    def rc(p):
        return (min(H - 1, max(0, int((p[1] - y0) * z))), min(W - 1, max(0, int((p[0] - x0) * z))))

    left = [rc(p) for k in range(i + 1) for p in anchors_[k]]
    right = [rc(p) for k in range(i + 1, n) for p in anchors_[k]]
    primary = {rc(a[0]) for a in anchors_ if a}          # each letter's main region
    left = [p for p in left if ink[p]]
    right = [p for p in right if ink[p]]
    if not left or not right:
        return None
    dt = ndimage.distance_transform_edt(ink)
    ink_d = ndimage.binary_dilation(ink, iterations=1)
    cost = 1.0 / (dt + 0.5)
    in_a = ndimage.binary_dilation(masks[i], iterations=1)
    blocked = np.zeros(ink.shape, dtype=bool)
    chords = []
    for nchord in range(max_chords):
        path = _path(ink, cost, left, right, blocked)
        if path is None:
            break
        if nchord and path[-1] in primary:
            # a second chord only ever serves a right-side letter's SECOND region (a
            # medial kaf's baseline); a main region still joined after the first chord
            # means the first chord is wrong, not that another is missing
            return None
        exit_a = next((k for k, p in enumerate(path) if not in_a[p]), None)
        hits = []
        tried = set()
        for k in range(0, len(path), 2):
            r, c = path[k]
            key = (r // 2, c // 2)
            if key in tried:
                continue
            tried.add(key)
            cpt = (x0 + (c + 0.5) / z, y0 + (r + 0.5) / z)
            cand = _chord_at(run_polys, ink, ink_d, dt, cpt, x0, y0, z, radius=1.4, md_max=0.3)
            if cand is None:
                continue
            strip = L._paint(cand["poly"], x0, y0, z, W, H)
            if any(strip[p] for p in left + right):
                continue                          # a chord over an anchor decides nothing
            free = ink & ~blocked & ~strip
            lab, _n = ndimage.label(free, structure=L._FOUR)
            if lab[path[0]] == 0 or lab[path[-1]] == 0 or lab[path[0]] == lab[path[-1]]:
                continue
            hits.append((k, cand, strip))
        if not hits:
            return None
        after = [h for h in hits if exit_a is not None and h[0] >= exit_a]
        k, cand, strip = after[0] if after else hits[0]
        cand["walk"] = float(k / z)
        chords.append(cand)
        blocked |= strip
    else:
        return None
    if not chords:
        return None
    # still connected after max_chords?  (the for-else above returns None in that case)
    res = {"poly": chords[0]["poly"], "polys": [c["poly"] for c in chords],
           "neck": max(c["neck"] for c in chords), "boundary_dist": chords[0]["boundary_dist"],
           "thick": chords[0]["thick"], "walk": chords[0]["walk"], "how": "path", "chords": len(chords)}
    return res
