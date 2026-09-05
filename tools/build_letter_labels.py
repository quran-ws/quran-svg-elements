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


def run_sample(word, lig, idx, run_rec, font, pair, scale):
    bodies = [p for p in lig["paths"] if p["kind"] == "body" and p["d"]]
    polys = [poly for p in bodies for poly in L.flatten(p["d"])]
    if not polys:
        return None
    n = len(idx)
    if n > K:
        return None
    frame = canvas_frame(polys)
    ink = raster_on_canvas(polys, frame)
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
    for w in words:
        wrec = rec["words"].get(w["wid"])
        if not wrec or wrec.get("flags"):
            continue
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
            try:
                s = run_sample(w, lig, idx, run_rec, font, pair, scale)
            except Exception:
                s = None
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
