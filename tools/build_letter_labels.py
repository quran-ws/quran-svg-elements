#!/usr/bin/env python3
"""Training data for the letter labeller, from the hand-cut tajweed layers.

    python3 tools/build_letter_labels.py 1 604 --jobs 32     # → .cache/letters/labels/NNN.npz
    python3 tools/build_letter_labels.py 50 --stats

Per multi-letter run (one sample): the run's ink at Z px/u on a H × W canvas, the
letter count n, and per pixel a bitmask of the letter positions the pixel may belong
to (bit k = letter k of the run, 0 = rightmost). Bit sources, in falling order of
certainty:

  * a coloured tajweed layer whose letter index is known from the cut record (a hand
    cut `after=i` lying right of the layer makes it letter i+1, left of it letter i):
    its pixels get the single bit;
  * the black remainder falls into stretches between the resolved letters; each black
    component gets the bits of the letters that can lie there by reading order (a
    stretch holding one letter is exact by elimination);
  * a run with no resolved layer: every ink pixel gets all n bits (ordering only).

Non-ink pixels have mask 0 and are ignored by the loss. Spec:
docs/superpowers/specs/2026-09-05-learned-letter-labels-design.md
"""
import argparse
import json
import os
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import letters_lib as L          # noqa: E402
from tools import tajweed_lib as T          # noqa: E402
from tools.build_letter_cuts import align_runs   # noqa: E402

LABELS_DIR = os.path.join(L.ROOT, ".cache", "letters", "labels")
Z = 4                 # px per unit
H, W = 96, 256        # canvas: 24 u tall, 64 u wide; larger runs are scaled down to fit
K = 10                # letter positions supported (bits)


def canvas_frame(polys):
    """(x0, y0, z): the run's bbox right-aligned on the canvas, top-aligned, scaled
    down when it does not fit."""
    bx0, by0, bx1, by1 = L.bbox(polys)
    w, h = bx1 - bx0, by1 - by0
    z = Z
    if w * z > W - 4 or h * z > H - 4:
        z = min((W - 4) / max(w, 1e-6), (H - 4) / max(h, 1e-6))
    # right-align: the canvas x1 sits 2 px past bx1
    x0 = bx1 + 2 / z - W / z
    y0 = by0 - 2 / z
    return x0, y0, z


def raster_on_canvas(polys, frame):
    x0, y0, z = frame
    m = L.raster(polys, x0, y0, W / z, H / z, z)
    out = np.zeros((H, W), dtype=bool)
    h, w = min(H, m.shape[0]), min(W, m.shape[1])
    out[:h, :w] = m[:h, :w]
    return out


def resolve_layers(run, font, pair, scale):
    """{layer glyph name: letter position in the run} from the record's hand cuts."""
    by_layer = {}
    for c in run.get("cuts", []):
        if c.get("src") != "tajweed" or "layer" not in c:
            continue
        by_layer.setdefault(c["layer"], []).append(c)
    out = {}
    for name, cuts in by_layer.items():
        lp = font.outline_page(name, scale, pair["tx"], pair["ty"])
        pts = [p for poly in lp for p in poly]
        cx = sum(p[0] for p in pts) / len(pts)
        idx = set()
        for c in cuts:
            mx = sum(p[0] for p in c["poly"]) / len(c["poly"])
            idx.add(c["after"] + 1 if mx > cx else c["after"])
        if len(idx) == 1:
            out[name] = idx.pop()
    return out


HAND_CUTS_PATH = os.path.join(L.ROOT, "docs", "defects", "letters_hand_cuts.jsonl")


def load_hand_cuts():
    """Drawn by hand on letters_label.html, keyed (page, wid, run text) → (cuts, assign).
    `cuts` are polylines in page units. `assign` is optional and is what a shape needs
    when no set of lines can give one piece per letter (the medial ك+ل ligature: the
    kaf is an arm plus a bowl and the lam a stem plus a foot, four pieces for two
    letters): [[x, y, k], …], one entry per piece, x/y the piece's centre in page units
    and k the letter it belongs to. Pieces are matched to entries by nearest centre, so
    the assignment survives any change in how pieces are ordered.

    `regions` are freehand loops: {path, letter}. Where no straight line can part two
    letters -- the kaf's arm and the alef interleave on ضاحكا -- he draws round the ink
    that IS one letter, and the pixels inside the loop are that letter outright.

    The key is the run's text, and a run's text is not for ever: when the word build
    stops filing the alef in the group before it, وَٱنْحَرْ's run انحر becomes نحر and
    every drawing keyed to the old name would rot. So the text is only the first way in
    -- `drawing_for` falls back to where the ink actually is, which no rebuild can change.
    """
    out = {}
    if not os.path.exists(HAND_CUTS_PATH):
        return out
    for line in open(HAND_CUTS_PATH, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        e = json.loads(line)
        out.setdefault((e["page"], e["wid"]), []).append(
            (e["text"],
             [[tuple(p) for p in c] for c in e.get("cuts", [])],
             e.get("assign"),
             [{"path": [tuple(q) for q in r["path"]], "letter": int(r["letter"])}
              for r in e.get("regions", [])]))
    return out


def drawing_for(recs, text, polys, used, named=()):
    """The drawing meant for this run: by name, or failing that by where it was drawn.

    A cut's MIDPOINT lies on the stroke it parts and a loop encloses ink, so each line of
    a drawing places itself in one run. That is a fact about the artwork, so it survives a
    change in how the word build names or groups its runs -- and it survives a run being
    SPLIT, which whole-record matching did not: p240's `اسه` and p531's `تكذبا` became two
    runs each after the ligature-grouping fix, and their drawings were dropped whole.
    Endpoints are no guide, because a cut is drawn past the ink on purpose (p240's
    overshoots by 1.8u).

    `named` holds the texts of every run in the word, so a drawing that some OTHER run
    will claim by name is off limits here: neighbouring runs sit a unit or two apart and
    a padded bbox reaches into the next one, which is how p227's `ين` drawing was taken
    by `لخسر` and lost (measured 2026-09-13, the only such theft in 280 drawings).

    The geometry path returns no `assign`: those letter indices count from the run the
    drawing was made on, and a split run renumbers them.
    """
    for i, (t, cuts, assign, regions) in enumerate(recs):
        if t == text and used.get(i) != "all":
            used[i] = "all"
            return cuts, assign, regions
    x0, y0, x1, y1 = L.bbox(polys)
    pad = 1.0

    def inside(px, py):
        return x0 - pad <= px <= x1 + pad and y0 - pad <= py <= y1 + pad

    gcuts, gregions = [], []
    for i, (t, cuts, assign, regions) in enumerate(recs):
        if used.get(i) == "all" or t in named:
            continue
        u = used.setdefault(i, set())
        for j, c in enumerate(cuts):
            if ("c", j) in u:
                continue
            if inside((c[0][0] + c[1][0]) / 2.0, (c[0][1] + c[1][1]) / 2.0):
                gcuts.append(c)
                u.add(("c", j))
        for j, r in enumerate(regions):
            if ("r", j) in u:
                continue
            if all(inside(px, py) for px, py in r["path"]):
                gregions.append(r)
                u.add(("r", j))
    if not gcuts and not gregions:
        return None
    return gcuts, None, gregions


CONFIRMED_PATH = os.path.join(L.ROOT, "docs", "defects", "letters_confirmed.jsonl")


def load_confirmations():
    """Runs Abdullah looked at and called right, keyed (page, wid, run text).

    Confirming a split is as exact a label as drawing one: it says every pixel of the run
    is where it belongs. It costs a click instead of two drawn lines, so the drawing page
    now opens on the split as it stands and asks for a verdict -- most cuts are already
    right, and redrawing a right one spends the only scarce thing here.

    The value is the split that was confirmed, as one path list per letter, or True for
    the older records that kept none. A confirmation with no split is only as good as the
    build it was given for: three of the first 117 stopped being exact labels when the
    run they named lost a letter in a later build.
    """
    out = {}
    if not os.path.exists(CONFIRMED_PATH):
        return out
    for line in open(CONFIRMED_PATH, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        e = json.loads(line)
        if e.get("verdict") != "right" or e.get("superseded"):
            continue
        out[(e["page"], e["wid"], e.get("text", ""))] = e.get("model") or True
    return out


def build_letter_masks(page, wid, idx, frame, ink):
    """One boolean mask per letter of the run, from the letters build's own split."""
    import re as _re
    if page is None:
        return None
    path = os.path.join(L.LETTERS_SVG, "%03d.svg" % page)
    if not os.path.exists(path):
        return None
    words, _ = L.read_words(page, L.LETTERS_SVG)
    w = next((x for x in words if x["wid"] == wid), None)
    if w is None:
        return None
    out = [None] * len(idx)
    for m in _re.finditer(r'<g class="letter"([^>]*)>(.*?)</g>', w["inner"], _re.S):
        at = L.parse_attrs(m.group(1))
        if at.get("data-unsplit") == "1":
            continue
        try:
            li = int(at.get("data-index", -1))
        except ValueError:
            continue
        if li not in idx:
            continue
        k = idx.index(li)
        polys = []
        for pm in _re.finditer(r'<path ([^>]*?)/>', m.group(2)):
            pa = L.parse_attrs(pm.group(1))
            if pa.get("data-kind") == "body" and pa.get("d"):
                polys += L.flatten(pa["d"])
        if not polys:
            continue
        mk = raster_on_canvas(polys, frame) & ink
        if mk.any():
            out[k] = mk if out[k] is None else (out[k] | mk)
    return out


def masks_from_model(model, frame, ink):
    """One mask per letter from the path lists a confirmation kept."""
    out = []
    for ds in model:
        polys = [poly for d in (ds or []) for poly in L.flatten(d)]
        m = (raster_on_canvas(polys, frame) & ink) if polys else None
        out.append(m if m is not None and m.any() else None)
    return out


def confirmed_mask(page, wid, lig_text, idx, frame, ink, n, model=None):
    """The split that was confirmed, as a single-bit mask per pixel -- the one the record
    kept, or failing that the letters build's own."""
    masks = masks_from_model(model, frame, ink) if isinstance(model, list) else \
        build_letter_masks(page, wid, idx, frame, ink)
    if masks is None or sum(1 for m in masks if m is not None) != n:
        return None                      # the build does not hold every letter: not exact
    mask = np.zeros((H, W), dtype=np.uint16)
    for k, mk in enumerate(masks):
        mask[mk] = np.uint16(1 << k)
    if (mask[ink] == 0).any():
        rest = ink & (mask == 0)
        mask[rest] = np.uint16((1 << n) - 1)    # a stray pixel keeps every option
    return mask


SHAPE_TRIMS_PATH = os.path.join(L.ROOT, "docs", "defects", "letter_shape_verdicts.jsonl")


def load_shape_trims():
    """Loops drawn on the shapes page, keyed (page, wid) → [{index, path}].

    A trim is a loop around the ink that IS one letter, drawn on the word itself. All 87
    of them mean the ink INSIDE the loop (87 of 87, measured 2026-09-08), so a trim is a
    stronger statement than a cut line: it names the letter's pixels outright, and by
    the same stroke denies that letter every other pixel of the run. Both halves are
    written into the bitmask.
    """
    out = {}
    if not os.path.exists(SHAPE_TRIMS_PATH):
        return out
    for line in open(SHAPE_TRIMS_PATH, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        e = json.loads(line)
        if e.get("verdict") != "trim" or not e.get("trim"):
            continue
        t = e["trim"]
        if t.get("kind") != "loop" or t.get("select", "in") != "in":
            continue                      # a line cut is a cut, not a region
        out.setdefault((e["page"], e["wid"]), []).append(
            {"index": e["index"], "path": [tuple(q) for q in t["page_path"]], "id": e["id"]})
    return out


def loop_on_canvas(path, frame):
    """A drawn loop rasterised onto the label canvas."""
    from PIL import Image, ImageDraw
    x0, y0, z = frame
    im = Image.new("1", (W, H), 0)
    ImageDraw.Draw(im).polygon([(int((qx - x0) * z), int((qy - y0) * z)) for qx, qy in path],
                               fill=1)
    return np.array(im, dtype=bool)


def apply_trims(mask, ink, frame, trims, idx, n):
    """Fold the drawn loops into the bitmask. Returns how many were used."""
    used = 0
    for t in trims:
        if t["index"] not in idx:
            continue
        k = idx.index(t["index"])
        if k >= n:
            continue
        loop = loop_on_canvas(t["path"], frame)
        inside = ink & loop
        if not inside.any():
            continue
        mask[inside] = np.uint16(1 << k)
        rest = ink & ~loop
        if rest.any():
            cleared = mask[rest] & np.uint16(~(1 << k) & 0xFFFF)
            # a pixel left with no letter at all is a contradiction between the layers
            # and the drawing; the drawing wins, so give it every position but this one
            cleared[cleared == 0] = np.uint16(((1 << n) - 1) & ~(1 << k))
            mask[rest] = cleared
        used += 1
    return used


NOJOIN = set("اأإآٱدذرزوؤءةى")          # letters that never join the letter after them
RULE_PART = os.environ.get("QSVG_RULEPART", "1") != "0"


def rule_partition(ink, chars, n):
    """The partition the joining rules prove, or None.

    A letter in NOJOIN never joins the one after it, so a run holding b such boundaries
    is drawn in b+1 pieces. Where the ink IS in exactly b+1 pieces, which letters each
    piece may hold is settled -- no model, no drawing, no layer. Measured over the whole
    mushaf (tools/audit_nojoin_contours.py): of 2,032 such boundaries the build already
    splits 567, this settles 181 more, and 546 the print fuses anyway, so those still
    need a drawn line. Over pages 1-120 it makes 99,859 ambiguous pixels single-letter
    and contradicts the tajweed layers on 0.47% of pixels, which is seam width; a
    contradicted pixel is left as it was rather than emptied.
    """
    breaks = [i for i, ch in enumerate(chars[:-1]) if ch in NOJOIN]
    if not breaks:
        return None
    lab, nc = ndimage.label(ink, structure=np.ones((3, 3), dtype=bool))
    if nc != len(breaks) + 1:
        return None
    groups, start = [], 0
    for i in breaks:
        groups.append((start, i))
        start = i + 1
    groups.append((start, n - 1))
    order = sorted(range(1, nc + 1), key=lambda c: -int(np.nonzero(lab == c)[1].max()))
    out = []
    for c, (a, b) in zip(order, groups):
        bits = 0
        for k in range(a, b + 1):
            bits |= 1 << k
        out.append((lab == c, bits))
    return out


def order_pieces(pieces, lab, cuts, frame, ink):
    """Reading order of the pieces. Mean x alone is wrong where a letter swings back
    under the one before it (the ح bowl of لح lies right of the ل stem), so walk the
    chain the drawn lines make — each line joins the two pieces it touches — from the
    end whose ink lies furthest right; separate chains (a letter after one that does not
    join) follow in order of their mean x."""
    x0, y0, z = frame
    from PIL import Image, ImageDraw
    meanx = {c: np.nonzero(lab == c)[1].mean() for c in pieces}
    adj = {c: set() for c in pieces}
    have = np.isin(lab, pieces)
    _, (ir, ic) = ndimage.distance_transform_edt(~have, return_indices=True)
    nearest = lab[ir, ic]
    for c in cuts:
        # the pixels the line took out of the ink, each given to its nearest piece:
        # the two pieces holding most of them are the two the line separates (the
        # line's 1u extension may graze a third letter; the stroke it crosses cannot)
        im = Image.new("1", (W, H), 0)
        ImageDraw.Draw(im).line([((x - x0) * z, (y - y0) * z) for x, y in c], fill=1, width=3)
        took = nearest[np.array(im, dtype=bool) & ink]
        touched = [(int((took == k).sum()), k) for k in pieces]
        touched = [k for cnt, k in sorted(touched, reverse=True) if cnt > 0][:2]
        if len(touched) == 2:
            adj[touched[0]].add(touched[1])
            adj[touched[1]].add(touched[0])
    out, seen = [], set()
    ends = sorted((c for c in pieces if len(adj[c]) <= 1), key=lambda c: -meanx[c])
    for start in ends + sorted(pieces, key=lambda c: -meanx[c]):
        if start in seen:
            continue
        chain = [start]
        seen.add(start)
        while True:
            nxt = [k for k in adj[chain[-1]] if k not in seen]
            if not nxt:
                break
            chain.append(nxt[0])
            seen.add(nxt[0])
        out.append(chain)
    # chains in order of the ink they start from; a chain's start is its rightmost end
    out.sort(key=lambda ch: -max(meanx[c] for c in ch))
    return [c for ch in out for c in ch]


def drawn_cut_labels(polys, cuts, n, frame, ink, letters=None, assign=None,
                     model_masks=None, regions=None):
    """Exact labels from drawn cut lines: paint the lines (extended 1u past their ends
    over the canvas), take the ink components, and number them right→left. Returns the
    mask or None when the lines do not give exactly n pieces."""
    x0, y0, z = frame
    from PIL import Image, ImageDraw
    im = Image.new("1", (W, H), 0)
    dr = ImageDraw.Draw(im)
    for c in cuts:
        (ax, ay), (bx, by) = c[0], c[-1]
        dx, dy = bx - ax, by - ay
        nn = (dx * dx + dy * dy) ** 0.5 or 1e-9
        ext = 1.0
        pts = [(ax - dx / nn * ext, ay - dy / nn * ext)] + list(c) + [(bx + dx / nn * ext, by + dy / nn * ext)]
        dr.line([((x - x0) * z, (y - y0) * z) for x, y in pts], fill=1, width=3)
    line = np.array(im, dtype=bool)
    free = ink & ~line
    four = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool)
    eight = np.ones((3, 3), dtype=bool)
    lab, nc = ndimage.label(free, structure=four)
    sizes = np.bincount(lab.ravel())
    # a contour no line touches (a final kaf's arm) is not a piece: it joins the piece
    # it overlaps most in x
    whole, _ = ndimage.label(ink, structure=eight)
    touched = set(np.unique(whole[line & ink]))
    pieces, extras = [], []
    for c in range(1, nc + 1):
        if sizes[c] < 12:
            continue
        wc = int(np.bincount(whole[lab == c]).argmax())
        # with no line drawn nothing is "touched": the run's own contours ARE the pieces,
        # which is what a drawing carrying only loops has to carve out of
        (pieces if (not cuts or wc in touched) else extras).append(c)
    if len(pieces) < n and letters:
        # after a letter that never joins left (و then ة, ر then ا) the next letter is a
        # contour of its own that no line needs to touch; the text says how many such
        # letters this run may hold, and the largest untouched contours are they
        allowed = sum(1 for ch in letters[:-1] if ch in NOJOIN)
        extras.sort(key=lambda c: -sizes[c])
        for c in extras[:min(allowed, n - len(pieces))]:
            pieces.append(c)
        extras = [c for c in extras if c not in pieces]
    if len(pieces) < n and model_masks:
        # A drawn line is a correction, not the whole answer: he draws where the cut is
        # wrong and leaves the rest. His lines are authoritative BOUNDARIES -- a piece may
        # not cross one -- but inside a piece the build's own split still knows where the
        # letters are, so a piece holding more than one of them is divided by it. Without
        # this, one line across a three-letter run threw the build's split away and the
        # run was dropped for "not giving 3 pieces" (9 of his 198 drawings).
        nxt = int(lab.max()) + 1
        for c in list(pieces):
            here = []
            cm = lab == c
            tot = int(cm.sum())
            for k, mk in enumerate(model_masks):
                if mk is not None and int((cm & mk).sum()) >= 0.12 * tot:
                    here.append(k)
            if len(here) < 2:
                continue
            first = True
            for k in here:
                part = cm & model_masks[k]
                if not part.any():
                    continue
                if first:
                    first = False
                    continue                     # the first keeps the piece's own id
                lab[part] = nxt
                pieces.append(nxt)
                nxt += 1
        sizes = np.bincount(lab.ravel())
    # A loop is a piece, not an afterthought. Carving it here, before any letter is
    # named, is what the drawing page does, so the pieces the page showed and the pieces
    # named here are the same ones -- and its letter comes from the loop itself rather
    # than from the nearest clicked centre. Applied at the end instead, p488 أَلَآ was
    # refused: both model-split pieces fell nearest the loop's own centre, the alef was
    # left holding nothing, and a good drawing was thrown away.
    region_letter = {}
    for r in (regions or []):
        k = r["letter"]
        if not 0 <= k < n:
            continue
        inside = ink & loop_on_canvas(r["path"], frame) & np.isin(lab, pieces)
        if not inside.any():
            continue
        nxt = int(lab.max()) + 1
        lab[inside] = nxt
        pieces.append(nxt)
        region_letter[nxt] = k
    if region_letter:
        pieces = [c for c in pieces if (lab == c).any()]
        sizes = np.bincount(lab.ravel())
    letter_of = None
    if assign:
        # Each piece takes the letter of the nearest named centre, so the list of clicks
        # need not be as long as the list of pieces -- it was checked for equal length,
        # and subdividing a piece by the build (above) then made every clicked run fail.
        # What must hold is that every letter ends up with ink, and that is checked below.
        #
        # A loop carries its own letter, and where the page recorded one deliberately that
        # beats a nearest-centre guess (p488 أَلَآ). But the page writes 0 on a loop it has
        # no answer for, so on a three-letter run both loops can claim the first letter and
        # the rest are left empty: p588 كلا, where his three clicks say ك, ل, ا and both
        # loops said ك. Neither source is right on its own, so try the loops' letters first
        # and the clicks alone second, and take the naming under which every letter holds
        # ink. That is the property the label has to have; which source supplied it is not
        # something a drawing needs to say twice.
        def _named(use_regions):
            out, got = {}, set()
            for c in pieces:
                ys, xs = np.nonzero(lab == c)
                cx, cy = x0 + xs.mean() / z, y0 + ys.mean() / z
                k = (region_letter[c] if use_regions and c in region_letter
                     else min(assign, key=lambda a: (a[0] - cx) ** 2 + (a[1] - cy) ** 2)[2])
                if not 0 <= int(k) < n:
                    return None, None
                out[c] = int(k)
                got.add(int(k))
            return out, got

        letter_of, seen = _named(True)
        if letter_of is None or len(seen) != n:
            alt, alt_seen = _named(False)
            if alt is not None and len(alt_seen) == n:
                letter_of, seen = alt, alt_seen
        if letter_of is None:
            return None
    elif len(pieces) != n:
        # One line can leave a letter in two pieces: on p240 رَّأْسِهِۦ the run اسه is a
        # single fused contour, his one line parted ه from اس, and the build's split then
        # divided BOTH sides, putting the س on either side of his line -- 4 pieces for 3
        # letters, and the drawing was thrown away with "does not give 3 pieces". A piece
        # per letter was never the requirement. What must hold is that no piece crosses a
        # drawn line and that every letter holds ink; which letter a piece is, the build
        # already knows. So ask it, instead of asking him for a line he has drawn.
        if not model_masks:
            return None
        letter_of, seen = {}, set()
        for c in pieces:
            if c in region_letter:
                letter_of[c] = region_letter[c]
                seen.add(region_letter[c])
                continue
            cm = lab == c
            best, bv = None, 0
            for k, mk in enumerate(model_masks):
                v = int((cm & mk).sum()) if mk is not None else 0
                if v > bv:
                    bv, best = v, k
            if best is None:
                return None                      # a piece the build has no letter for
            letter_of[c] = best
            seen.add(best)
    if letter_of is not None:
        if len(seen) != n:
            return None                          # every letter must hold some ink
    pieces = order_pieces(pieces, lab, cuts, frame, ink)
    mask = np.zeros((H, W), dtype=np.uint16)
    span = {}
    for k, c in enumerate(pieces):
        bit = letter_of[c] if letter_of is not None else k
        mask[lab == c] = 1 << bit
        xs = np.nonzero(lab == c)[1]
        lo, hi = xs.min(), xs.max()
        if bit in span:
            span[bit] = (min(span[bit][0], lo), max(span[bit][1], hi))
        else:
            span[bit] = (lo, hi)
    for c in extras:
        xs = np.nonzero(lab == c)[1]
        lo, hi = xs.min(), xs.max()
        best = max(range(n), key=lambda k: min(hi, span[k][1]) - max(lo, span[k][0]))
        if min(hi, span[best][1]) - max(lo, span[best][0]) < 0:
            best = min(range(n), key=lambda k: abs((span[k][0] + span[k][1]) / 2 - (lo + hi) / 2))
        mask[lab == c] = 1 << best
    # the line pixels themselves take the nearest piece
    rest = ink & (mask == 0)
    if rest.any():
        have = mask > 0
        _, (ir, ic) = ndimage.distance_transform_edt(~have, return_indices=True)
        mask[rest] = mask[ir[rest], ic[rest]]
    return mask


def run_sample(word, lig, idx, run_rec, font, pair, scale, drawn=None, trims=None,
               confirmed=None, page=None):
    bodies = [p for p in lig["paths"] if p["kind"] == "body" and p["d"]]
    polys = [poly for p in bodies for poly in L.flatten(p["d"])]
    if not polys:
        return None
    n = len(idx)
    if n > K:
        return None
    frame = canvas_frame(polys)
    ink = raster_on_canvas(polys, frame)
    if drawn:
        letters = [L.letters_of(word["uthmani"])[i]["ch"] for i in idx]
        mm = build_letter_masks(page, word["wid"], idx, frame, ink)
        mask = drawn_cut_labels(polys, drawn[0], n, frame, ink, letters, drawn[1],
                                model_masks=mm, regions=drawn[2] if len(drawn) > 2 else None)
        if mask is not None:
            if trims:
                apply_trims(mask, ink, frame, trims, idx, n)
            return {"ink": ink, "mask": mask, "n": n, "frame": frame, "known": n, "drawn": True,
                    "exact_px": int(ink.sum()), "ink_px": int(ink.sum()), "wid": word["wid"],
                    "text": lig["text"], "letters": [L.letters_of(word["uthmani"])[i]["ch"] for i in idx]}
    if confirmed:
        cm = confirmed_mask(page, word["wid"], lig["text"], idx, frame, ink, n,
                            model=confirmed)
        if cm is not None:
            if trims:
                apply_trims(cm, ink, frame, trims, idx, n)
            return {"ink": ink, "mask": cm, "n": n, "frame": frame, "known": n,
                    "confirmed": True, "exact_px": int(ink.sum()), "ink_px": int(ink.sum()),
                    "wid": word["wid"], "text": lig["text"],
                    "letters": [L.letters_of(word["uthmani"])[i]["ch"] for i in idx]}
    mask = np.zeros((H, W), dtype=np.uint16)
    known = {}                                   # letter position → pixel mask
    if pair is not None and font is not None:
        for name, k in resolve_layers(run_rec, font, pair, scale).items():
            if 0 <= k < n:
                lp = font.outline_page(name, scale, pair["tx"], pair["ty"])
                m = raster_on_canvas(lp, frame) & ink
                if m.any():
                    known[k] = known.get(k, np.zeros((H, W), dtype=bool)) | m
    for k, m in known.items():
        mask[m] = 1 << k
    rest = ink.copy()
    for m in known.values():
        rest &= ~m
    # black stretches: bits of the letters that can lie there by reading order
    if known:
        kx = {k: np.nonzero(m)[1].mean() for k, m in known.items()}     # column means
        lab, nc = ndimage.label(rest, structure=np.ones((3, 3), dtype=bool))
        for cid in range(1, nc + 1):
            comp = lab == cid
            cx = np.nonzero(comp)[1].mean()
            right = [k for k, x in kx.items() if x > cx]      # resolved letters to the right (earlier)
            left = [k for k, x in kx.items() if x <= cx]      # to the left (later)
            lo = max(right) + 1 if right else 0
            hi = min(left) - 1 if left else n - 1
            bits = 0
            for k in range(max(0, lo), min(n - 1, hi) + 1):
                bits |= 1 << k
            if bits == 0:                                     # contradictory order: all
                bits = (1 << n) - 1
            mask[comp] = bits
    else:
        mask[ink] = (1 << n) - 1
    chars = [L.letters_of(word["uthmani"])[i]["ch"] for i in idx]
    rp = rule_partition(ink, chars, n) if RULE_PART and len(chars) == n else None
    for pm, bits in (rp or []):
        cur = mask[pm]
        new = cur & np.uint16(bits)
        keep = new == 0
        new[keep] = cur[keep]                # a contradiction leaves the pixel as it was
        mask[pm] = new
    trimmed = apply_trims(mask, ink, frame, trims, idx, n) if trims else 0
    exact = int(((mask & (mask - 1)) == 0).sum() - (mask == 0).sum())
    return {"ink": ink, "mask": mask, "n": n, "frame": frame, "known": len(known),
            "trimmed": trimmed,
            "exact_px": exact, "ink_px": int(ink.sum()), "wid": word["wid"],
            "text": lig["text"], "letters": [word and L.letters_of(word["uthmani"])[i]["ch"] for i in idx]}


def build_page(page):
    cuts_path = os.path.join(L.CUTS_DIR, "%03d.json" % page)
    if not os.path.exists(cuts_path):
        return None
    rec = json.load(open(cuts_path, encoding="utf-8"))
    if rec.get("model"):
        # The tajweed layer is the teacher: `resolve_layers` reads it off cuts whose src is
        # "tajweed", and a MODEL-mode record has none -- every cut in it says src "model".
        # Building labels from one trains the model on its own output and silently drops the
        # teacher: measured 2026-09-13, runs with a resolved layer went 36,390 -> 439 and
        # nothing in the output said why. So refuse, and name the fix.
        raise SystemExit("%s was built by a model (%s). Labels come from the tajweed/DK cut "
                         "records: rebuild them with `python3 tools/build_letter_cuts.py 1 604` "
                         "and no QSVG_LETTERS_TAG, or unset the tag you are running with."
                         % (cuts_path, rec["model"]))
    words, _ = L.read_words(page)
    font = T.PageFont(page) if os.path.exists(os.path.join(T.FONTS, "p%d.ttf" % page)) else None
    scale = rec.get("scale", T.DEFAULT_SCALE)
    samples = []
    drawn_all = load_hand_cuts()
    drawn_used = {}
    trims_all = load_shape_trims()
    confirmed_all = load_confirmations()
    for w in words:
        wrec = rec["words"].get(w["wid"])
        if not wrec:
            continue
        if (wrec.get("flags") and (page, w["wid"]) not in drawn_all
                and (page, w["wid"]) not in trims_all):
            continue                      # no tajweed registration; a drawing needs none
        reg = wrec.get("reg")
        pair = None
        if reg and font is not None:
            pair = {"tx": reg["tx"], "ty": reg["ty"]}
        try:
            letters, runs = align_runs(w)
        except ValueError:
            continue
        if runs is None:
            continue
        by_letters = {tuple(r["letters"]): r for r in wrec["runs"]}
        run_texts = {lig["text"] for lig, _ in runs}
        for lig, idx in runs:
            if len(idx) < 2:
                continue
            run_rec = by_letters.get(tuple(idx), {})
            recs = drawn_all.get((page, w["wid"]))
            drawn = None
            if recs:
                rp = [poly for p in lig["paths"] if p["kind"] == "body" and p["d"]
                      for poly in L.flatten(p["d"])]
                if rp:
                    drawn = drawing_for(recs, lig["text"], rp,
                                        drawn_used.setdefault((page, w["wid"]), {}),
                                        named=run_texts)
            trims = [t for t in trims_all.get((page, w["wid"]), []) if t["index"] in idx]
            ok = confirmed_all.get((page, w["wid"], lig["text"]))
            try:
                s = run_sample(w, lig, idx, run_rec, font, pair, scale, drawn=drawn,
                               trims=trims, confirmed=ok, page=page)
            except Exception:
                s = None
            if drawn and (s is None or not s.get("drawn")):
                print("  drawn cuts of p%d %s %s do not give %d pieces" % (page, w["wid"], lig["text"], len(idx)))
            if s:
                samples.append(s)
    return samples


def save_page(page):
    t = time.time()
    samples = build_page(page)
    if samples is None:
        return page, 0, 0, 0
    os.makedirs(LABELS_DIR, exist_ok=True)
    ink = np.stack([s["ink"] for s in samples]) if samples else np.zeros((0, H, W), bool)
    mask = np.stack([s["mask"] for s in samples]) if samples else np.zeros((0, H, W), np.uint16)
    meta = [{k: v for k, v in s.items() if k not in ("ink", "mask")} for s in samples]
    np.savez_compressed(os.path.join(LABELS_DIR, "%03d.npz" % page), ink=np.packbits(ink, axis=-1), mask=mask,
                        n=np.array([s["n"] for s in samples], dtype=np.int8),
                        meta=json.dumps(meta, ensure_ascii=False))
    with_known = sum(1 for s in samples if s["known"])
    exact = sum(s["exact_px"] for s in samples)
    inkpx = sum(s["ink_px"] for s in samples)
    return page, len(samples), with_known, round(exact / max(1, inkpx), 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("first", type=int)
    ap.add_argument("last", type=int, nargs="?")
    ap.add_argument("--jobs", type=int, default=32)
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args()
    pages = range(a.first, (a.last or a.first) + 1)
    tot = Counter()
    with ProcessPoolExecutor(min(a.jobs, len(pages))) as ex:
        for page, n, known, exact in ex.map(save_page, pages):
            print("p%03d runs %4d with-resolved-layer %4d exact-pixel share %.3f" % (page, n, known, exact), flush=True)
            tot["runs"] += n
            tot["known"] += known
    print("TOTAL", dict(tot))


if __name__ == "__main__":
    main()
