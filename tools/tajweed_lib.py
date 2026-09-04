#!/usr/bin/env python3
"""The QUL V4 tajweed page fonts as hand-cut letter evidence.

Each page font (`.cache/tajweed/fonts/pN.ttf`, COLRv0) draws every word as one glyph
built from 1–6 layer glyphs. The coloured layers are letters (body + own marks) cut by
hand on the SAME 1441H artwork our pages are, so once a word glyph is registered onto
our word ink (one uniform scale per page, one translation per word) the layer outline
runs along our contour everywhere except where the hand cut through the stroke — and
those interior stretches ARE the cut lines. Measured 2026-09-04 on p50: scale 0.00616,
123/135 words registered, ~37% of letter joints hand-cut; mushaf-wide ~90k letter
layers.

Spec: docs/superpowers/specs/2026-09-05-letter-level-decomposition-design.md
"""
import os
import statistics

import numpy as np
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

from tools import letters_lib as L

FONTS = os.path.join(L.ROOT, ".cache", "tajweed", "fonts")
FIRST_WORD_CODE = 0xFC41
DEFAULT_SCALE = 0.00616           # font units → page-path units, p50 fit
COVERAGE_TOL = 0.15               # u: our outline sample counts as "on" the glyph outline
COVERAGE_MIN = 0.97
INTERIOR_TOL = 0.25               # u: a layer point this far from our outline is a cut point
CUT_END_TOL = 0.45                # u: a cut's ends must sit on the run contour

# medallion colours (ayah markers, not letters) and black-ish "rest of word" layers
_MEDALLION = {(255, 0, 128), (216, 233, 216), (44, 164, 171)}


class PageFont:
    def __init__(self, page):
        self.page = page
        self.font = TTFont(os.path.join(FONTS, "p%d.ttf" % page))
        self.gs = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()
        self.codes = sorted(k for k in self.cmap if k >= FIRST_WORD_CODE)
        self.layers_of = self.font["COLR"].ColorLayers
        self.palette = self.font["CPAL"].palettes[0]
        self._cache = {}

    def glyph(self, code):
        return self.cmap[code]

    def layers(self, code):
        """[(layer glyph name, colorID)] — a glyph without COLR entry is its own layer."""
        g = self.cmap[code]
        ls = self.layers_of.get(g)
        return [(l.name, l.colorID) for l in ls] if ls else [(g, 0)]

    def colour(self, color_id):
        if color_id >= len(self.palette):
            return None
        c = self.palette[color_id]
        return (c.red, c.green, c.blue)

    def is_letter_layer(self, color_id):
        c = self.colour(color_id)
        if c is None or c in _MEDALLION:
            return False
        return sum(c) > 30                  # black and near-black are the "rest of word"

    def outline(self, glyph_name):
        """Flattened closed polylines in font units."""
        if glyph_name not in self._cache:
            pen = SVGPathPen(self.gs)
            self.gs[glyph_name].draw(pen)
            self._cache[glyph_name] = L.flatten(pen.getCommands(), steps=8)
        return self._cache[glyph_name]

    def outline_page(self, glyph_name, s, tx, ty):
        return L.transform_polys(self.outline(glyph_name), s, tx, ty)


# ----------------------------------------------------------------------------
# registration
# ----------------------------------------------------------------------------
def _largest(polys):
    return max(polys, key=lambda poly: abs(_shoelace(poly)))


def _shoelace(poly):
    a = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        a += x0 * y1 - x1 * y0
    return a / 2


def register(word_polys, glyph_polys_font, s, iters=4):
    """Translation (tx, ty) putting the glyph (font units × s) onto our word polys, and
    the coverage of our outline by the glyph outline. Bbox-align the largest contours,
    then ICP on translation only. Returns (tx, ty, coverage) or None."""
    if not word_polys or not glyph_polys_font:
        return None
    g = L.transform_polys(glyph_polys_font, s, 0, 0)
    ours, theirs = _largest(word_polys), _largest(g)
    ob, gb = L.bbox([ours]), L.bbox([theirs])
    tx = (ob[0] + ob[2]) / 2 - (gb[0] + gb[2]) / 2
    ty = (ob[1] + ob[3]) / 2 - (gb[1] + gb[3]) / 2
    tree, _ = L.outline_tree(g, 0.05)
    src = np.array(L.resample(word_polys, 0.1), dtype=float)
    for _ in range(iters):
        d, idx = tree.query(src - (tx, ty))
        keep = d < 0.6                      # ignore ink the glyph does not draw
        if keep.sum() < 10:
            return None
        delta = (src[keep] - (tx, ty)) - tree.data[idx[keep]]
        tx += float(np.median(delta[:, 0]))
        ty += float(np.median(delta[:, 1]))
    d, _ = tree.query(src - (tx, ty))
    cov = float((d < COVERAGE_TOL).mean())
    return tx, ty, cov


def page_scale(words, font, sample=40):
    """Median ratio of largest-contour widths over words that register at the default
    scale; falls back to DEFAULT_SCALE when too few do."""
    ratios = []
    n = len(words)
    step = max(1, n // sample)
    j = 0
    for w in words[::step]:
        polys = L.word_polys(w)
        if not polys:
            continue
        ours = _largest(polys)
        ob = L.bbox([ours])
        best = None
        for code in font.codes[max(0, j - 2):j + 6]:
            g = font.outline(font.glyph(code))
            if not g:
                continue
            r = register(polys, g, DEFAULT_SCALE)
            if r and (best is None or r[2] > best[0]):
                best = (r[2], code, g)
        if best and best[0] >= COVERAGE_MIN:
            gb = L.bbox([_largest(best[2])])
            ratios.append((ob[2] - ob[0]) / (gb[2] - gb[0]))
            j = font.codes.index(best[1]) + 1
        j += step - 1
    if len(ratios) < 5:
        return DEFAULT_SCALE
    return statistics.median(ratios)


def pair_glyphs(words, font, s, lookahead=6):
    """wid → {'code','tx','ty','cov'} by reading order with verification. Glyph codes
    run in reading order but include a waqf-sign glyph after words carrying one, the
    ayah medallions, and surah header + basmalah, so the pointer skips forward. A word
    that registers with none of the next `lookahead` glyphs is left unpaired (its
    neighbours still pair). Two of our words drawn as ONE glyph (إل ياسين 37:130) pair
    as a union: both get the same code."""
    out = {}
    j = 0
    i = 0
    n = len(words)
    while i < n:
        w = words[i]
        polys = L.word_polys(w)
        if not polys:
            i += 1
            continue
        hit = None
        for k in range(j, min(len(font.codes), j + lookahead)):
            g = font.outline(font.glyph(font.codes[k]))
            if not g:
                continue
            r = register(polys, g, s)
            if r and r[2] >= COVERAGE_MIN:
                hit = (k, r)
                break
        if hit is None and i + 1 < n:
            both = polys + L.word_polys(words[i + 1])
            for k in range(j, min(len(font.codes), j + lookahead)):
                g = font.outline(font.glyph(font.codes[k]))
                if not g:
                    continue
                r = register(both, g, s)
                if r and r[2] >= COVERAGE_MIN:
                    out[w["wid"]] = {"code": font.codes[k], "tx": r[0], "ty": r[1], "cov": r[2], "union": True}
                    out[words[i + 1]["wid"]] = dict(out[w["wid"]])
                    j = k + 1
                    i += 2
                    break
            else:
                i += 1
            continue
        if hit is None:
            i += 1
            continue
        k, r = hit
        out[w["wid"]] = {"code": font.codes[k], "tx": r[0], "ty": r[1], "cov": r[2]}
        j = k + 1
        i += 1
    return out


# ----------------------------------------------------------------------------
# lifting cuts
# ----------------------------------------------------------------------------
def lift_cuts(layer_polys, word_tree, run_polys, step=0.04):
    """Cut polylines (page units) where the layer outline crosses the INSIDE of the run:
    layer points farther than INTERIOR_TOL from our word outline, grouped consecutively,
    kept when both ends land on the run contour. `word_tree` is outline_tree() of ALL
    our word paths (marks included: the layer holds the letter's marks too)."""
    run_tree, _ = L.outline_tree(run_polys, 0.05)
    cuts = []
    for poly in layer_polys:
        pts = L.resample([poly], step)
        if not pts:
            continue
        arr = np.array(pts, dtype=float)
        d, _ = word_tree.query(arr)
        interior = d > INTERIOR_TOL
        if not interior.any():
            continue
        # rotate so the sequence starts on an exterior point (closed polyline)
        n = len(pts)
        start = next((i for i in range(n) if not interior[i]), None)
        if start is None:
            continue
        order = [(start + i) % n for i in range(n)]
        seg = []
        for i in order:
            if interior[i]:
                seg.append(i)
            elif seg:
                cuts.append(_finish(seg, arr, interior, run_tree, n))
                seg = []
        if seg:
            cuts.append(_finish(seg, arr, interior, run_tree, n))
    return [c for c in cuts if c]


def _finish(seg, arr, interior, run_tree, n):
    # extend by one exterior point on each side so the cut reaches the contour
    a, b = (seg[0] - 1) % n, (seg[-1] + 1) % n
    idx = [a] + seg + [b]
    pts = [tuple(arr[i]) for i in idx]
    da, _ = run_tree.query(arr[a])
    db, _ = run_tree.query(arr[b])
    if da > CUT_END_TOL or db > CUT_END_TOL:
        return None
    if len(pts) < 2:
        return None
    length = sum(np.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1))
    if length < 0.25:
        return None
    return L._simplify(pts, 0.03)


def layer_area(font, layer_glyph, s):
    return L.area(font.outline(layer_glyph)) * s * s
