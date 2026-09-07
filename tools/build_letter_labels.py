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
    the assignment survives any change in how pieces are ordered."""
    out = {}
    if not os.path.exists(HAND_CUTS_PATH):
        return out
    for line in open(HAND_CUTS_PATH, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        e = json.loads(line)
        out[(e["page"], e["wid"], e["text"])] = ([[tuple(p) for p in c] for c in e["cuts"]],
                                                 e.get("assign"))
    return out


NOJOIN = set("اأإآٱدذرزوؤءةى")          # letters that never join the letter after them


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


def drawn_cut_labels(polys, cuts, n, frame, ink, letters=None, assign=None):
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
        (pieces if wc in touched else extras).append(c)
    if len(pieces) < n and letters:
        # after a letter that never joins left (و then ة, ر then ا) the next letter is a
        # contour of its own that no line needs to touch; the text says how many such
        # letters this run may hold, and the largest untouched contours are they
        allowed = sum(1 for ch in letters[:-1] if ch in NOJOIN)
        extras.sort(key=lambda c: -sizes[c])
        for c in extras[:min(allowed, n - len(pieces))]:
            pieces.append(c)
        extras = [c for c in extras if c not in pieces]
    if assign:
        if len(assign) != len(pieces):
            return None
        # each piece takes the letter of the nearest named centre
        letter_of, seen = {}, set()
        for c in pieces:
            ys, xs = np.nonzero(lab == c)
            cx, cy = x0 + xs.mean() / z, y0 + ys.mean() / z
            k = min(assign, key=lambda a: (a[0] - cx) ** 2 + (a[1] - cy) ** 2)[2]
            if not 0 <= int(k) < n:
                return None
            letter_of[c] = int(k)
            seen.add(int(k))
        if len(seen) != n:
            return None                          # every letter must hold some ink
    elif len(pieces) != n:
        return None
    pieces = order_pieces(pieces, lab, cuts, frame, ink)
    mask = np.zeros((H, W), dtype=np.uint16)
    span = {}
    for k, c in enumerate(pieces):
        bit = letter_of[c] if assign else k
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


def run_sample(word, lig, idx, run_rec, font, pair, scale, drawn=None):
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
        mask = drawn_cut_labels(polys, drawn[0], n, frame, ink, letters, drawn[1])
        if mask is not None:
            return {"ink": ink, "mask": mask, "n": n, "frame": frame, "known": n, "drawn": True,
                    "exact_px": int(ink.sum()), "ink_px": int(ink.sum()), "wid": word["wid"],
                    "text": lig["text"], "letters": [L.letters_of(word["uthmani"])[i]["ch"] for i in idx]}
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
    exact = int(((mask & (mask - 1)) == 0).sum() - (mask == 0).sum())
    return {"ink": ink, "mask": mask, "n": n, "frame": frame, "known": len(known),
            "exact_px": exact, "ink_px": int(ink.sum()), "wid": word["wid"],
            "text": lig["text"], "letters": [word and L.letters_of(word["uthmani"])[i]["ch"] for i in idx]}


def build_page(page):
    cuts_path = os.path.join(L.CUTS_DIR, "%03d.json" % page)
    if not os.path.exists(cuts_path):
        return None
    rec = json.load(open(cuts_path, encoding="utf-8"))
    words, _ = L.read_words(page)
    font = T.PageFont(page) if os.path.exists(os.path.join(T.FONTS, "p%d.ttf" % page)) else None
    scale = rec.get("scale", T.DEFAULT_SCALE)
    samples = []
    drawn_all = load_hand_cuts()
    for w in words:
        wrec = rec["words"].get(w["wid"])
        if not wrec:
            continue
        if wrec.get("flags") and not any(k[:2] == (page, w["wid"]) for k in drawn_all):
            continue                      # no tajweed registration; drawn cuts need none
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
        for lig, idx in runs:
            if len(idx) < 2:
                continue
            run_rec = by_letters.get(tuple(idx), {})
            drawn = drawn_all.get((page, w["wid"], lig["text"]))
            try:
                s = run_sample(w, lig, idx, run_rec, font, pair, scale, drawn=drawn)
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
