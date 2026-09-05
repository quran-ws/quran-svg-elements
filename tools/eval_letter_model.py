#!/usr/bin/env python3
"""Held-out report for the letter labeller.

    python3 tools/eval_letter_model.py                 # pages ≡ 0 mod 10
    python3 tools/eval_letter_model.py --pages 50 50 --show 24 --out /tmp/x.png

Reports, on held-out runs that carry at least one resolved hand layer:
  * exact-pixel accuracy (pixels whose set is a singleton);
  * per joint (adjacent letters i, i+1): whether the predicted labels put a boundary
    where the hand did — the predicted boundary column vs the hand-layer edge, in
    units, summarised per letter pair; pairs with no hand cut anywhere are listed
    from the whole label set so the human labelling sample can be chosen.
"""
import argparse
import json
import os
import sys
from collections import defaultdict

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import letter_model as M          # noqa: E402
from tools.build_letter_labels import H, W, K   # noqa: E402


def boundary_x(lab, k):
    """Mean column of the boundary pixels between label k and k+1 (None if absent)."""
    a = lab == k
    b = lab == k + 1
    if not a.any() or not b.any():
        return None
    from scipy import ndimage
    touch = (a & ndimage.binary_dilation(b)) | (b & ndimage.binary_dilation(a))
    if not touch.any():
        return None
    return float(np.nonzero(touch)[1].mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, nargs=2, default=(1, 604))
    ap.add_argument("--model", default=M.MODEL_PATH)
    ap.add_argument("--show", type=int, default=0, help="render this many runs to --out")
    ap.add_argument("--out", default="/tmp/letter_eval.png")
    ap.add_argument("--all", action="store_true", help="every page, not only held-out")
    a = ap.parse_args()
    pages = [p for p in range(a.pages[0], a.pages[1] + 1) if a.all or p % 10 == 0]
    data = M.load_pages(pages, need_known=True)
    if data is None:
        print("no held-out data")
        return
    ink, mask, n, meta, codes = data
    model = M.load_model(a.model)
    pred = M.predict(model, ink, n, codes=codes)
    single = (mask > 0) & ((mask & (mask - 1)) == 0)
    truth = torch.full(mask.shape, -1, dtype=torch.int64)
    truth[single] = torch.log2(mask[single].float()).round().long()
    acc = float((pred[single] == truth[single]).float().mean())
    print("held-out runs %d  exact-pixel accuracy %.4f" % (len(n), acc))
    # per joint: hand boundary vs predicted boundary
    per_pair = defaultdict(list)
    for i in range(len(n)):
        t = truth[i].numpy()
        p = pred[i].numpy()
        z = meta[i]["frame"][2]
        letters = meta[i]["letters"]
        for k in range(int(n[i]) - 1):
            hx = boundary_x(t, k)
            if hx is None:
                continue                      # the hand did not cut this joint
            px = boundary_x(p, k)
            pair = letters[k] + letters[k + 1]
            per_pair[pair].append(None if px is None else abs(px - hx) / z)
    allv = sorted(v for vs in per_pair.values() for v in vs if v is not None)
    miss = sum(1 for vs in per_pair.values() for v in vs if v is None)
    print("hand-cut joints %d, predicted boundary missing on %d" % (len(allv) + miss, miss))
    if allv:
        for q in (0.5, 0.75, 0.9, 0.95):
            print("  p%02d  %.2fu" % (q * 100, allv[min(len(allv) - 1, int(q * len(allv)))]))
        print("  within 0.5u: %.1f%%  within 1u: %.1f%%" % (100 * sum(1 for v in allv if v <= 0.5) / len(allv),
                                                           100 * sum(1 for v in allv if v <= 1) / len(allv)))
    rows = sorted(per_pair.items(), key=lambda kv: -len(kv[1]))
    print("worst pairs (≥10 joints):")
    worst = [(pr, np.median([v for v in vs if v is not None]) if any(v is not None for v in vs) else 9.9, len(vs))
             for pr, vs in rows if len(vs) >= 10]
    for pr, med, cnt in sorted(worst, key=lambda x: -x[1])[:12]:
        print("   %s  median %.2fu  n=%d" % (pr, med, cnt))
    if a.show:
        from PIL import Image, ImageOps
        cols = [(230, 25, 75), (60, 180, 75), (67, 99, 216), (245, 130, 48), (145, 30, 180),
                (66, 212, 244), (240, 50, 230), (191, 239, 69), (154, 99, 36), (0, 128, 128)]
        tiles = []
        for i in range(min(a.show, len(n))):
            rgb = np.full((H, W * 2 + 8, 3), 255, np.uint8)
            for k in range(K):
                rgb[:, :W][truth[i].numpy() == k] = cols[k]
                rgb[:, W + 8:][pred[i].numpy() == k] = cols[k]
            rgb[:, :W][(truth[i].numpy() == -1) & ink[i].numpy()] = (200, 200, 200)
            tiles.append(ImageOps.flip(Image.fromarray(rgb)))
        out = Image.new("RGB", (W * 2 + 8, len(tiles) * (H + 4)), "white")
        for j, t in enumerate(tiles):
            out.paste(t, (0, j * (H + 4)))
        out.save(a.out)
        print("wrote", a.out, "(left: hand labels, grey = no label; right: predicted)")


if __name__ == "__main__":
    main()
