#!/usr/bin/env python3
"""The letter labeller: a small U-Net over a run's raster, trained with set labels.

Input channels: ink (0/1), x and y coordinates in [0, 1], n/K (letter count).
Output: K logits per pixel, the letter position in the run (0 = rightmost).
Loss on ink pixels: −log Σ_{k ∈ set} softmax_k — the set is a bitmask; exact labels
are singleton sets, the black stretches between known letters are multi-bit sets.
"""
import math
import os
import sys

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.build_letter_labels import H, W, K, LABELS_DIR     # noqa: E402

MODEL_PATH = os.path.join(os.path.dirname(LABELS_DIR), "model.pt")


def _block(cin, cout):
    return nn.Sequential(nn.Conv2d(cin, cout, 3, padding=1), nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
                         nn.Conv2d(cout, cout, 3, padding=1), nn.BatchNorm2d(cout), nn.ReLU(inplace=True))


class UNet(nn.Module):
    def __init__(self, cin=4, base=24, k=K):
        super().__init__()
        self.e1 = _block(cin, base)
        self.e2 = _block(base, base * 2)
        self.e3 = _block(base * 2, base * 4)
        self.e4 = _block(base * 4, base * 8)
        self.d3 = _block(base * 8 + base * 4, base * 4)
        self.d2 = _block(base * 4 + base * 2, base * 2)
        self.d1 = _block(base * 2 + base, base)
        self.out = nn.Conv2d(base, k, 1)

    def forward(self, x):
        e1 = self.e1(x)
        e2 = self.e2(F.max_pool2d(e1, 2))
        e3 = self.e3(F.max_pool2d(e2, 2))
        e4 = self.e4(F.max_pool2d(e3, 2))
        d3 = self.d3(torch.cat([F.interpolate(e4, scale_factor=2, mode="nearest"), e3], 1))
        d2 = self.d2(torch.cat([F.interpolate(d3, scale_factor=2, mode="nearest"), e2], 1))
        d1 = self.d1(torch.cat([F.interpolate(d2, scale_factor=2, mode="nearest"), e1], 1))
        return self.out(d1)


def make_input(ink, n):
    """ink: (B, H, W) bool → (B, 4, H, W) float."""
    B = ink.shape[0]
    ys = torch.linspace(0, 1, H).view(1, 1, H, 1).expand(B, 1, H, W)
    xs = torch.linspace(0, 1, W).view(1, 1, 1, W).expand(B, 1, H, W)
    nn_ = (n.float() / K).view(B, 1, 1, 1).expand(B, 1, H, W)
    return torch.cat([ink.float().unsqueeze(1), xs, ys, nn_], 1)


def set_loss(logits, mask):
    """logits (B, K, H, W); mask (B, H, W) uint16 bitmask. Mean over pixels with a mask."""
    logp = F.log_softmax(logits, 1)
    bits = torch.stack([(mask >> k) & 1 for k in range(K)], 1).bool()       # (B, K, H, W)
    # log Σ_{k∈set} p_k = logsumexp over allowed classes
    masked = logp.masked_fill(~bits, -1e9)
    lse = torch.logsumexp(masked, 1)                                        # (B, H, W)
    valid = mask > 0
    if not valid.any():
        return logits.sum() * 0
    return -(lse[valid]).mean()


def load_pages(pages, need_known=False):
    inks, masks, ns, metas = [], [], [], []
    for p in pages:
        path = os.path.join(LABELS_DIR, "%03d.npz" % p)
        if not os.path.exists(path):
            continue
        z = np.load(path, allow_pickle=False)
        ink = np.unpackbits(z["ink"], axis=-1)[..., :W].astype(bool)
        mask = z["mask"]
        n = z["n"]
        import json
        meta = json.loads(str(z["meta"]))
        for i in range(len(n)):
            if need_known and not meta[i].get("known"):
                continue
            inks.append(ink[i])
            masks.append(mask[i])
            ns.append(int(n[i]))
            metas.append(dict(meta[i], page=p))
    if not inks:
        return None
    return (torch.from_numpy(np.stack(inks)), torch.from_numpy(np.stack(masks).astype(np.int64)),
            torch.tensor(ns, dtype=torch.int64), metas)


def predict(model, ink, n, batch=64):
    """ink (B, H, W) bool, n (B,) → labels (B, H, W) int64 (−1 off ink)."""
    model.eval()
    out = []
    with torch.no_grad():
        for i in range(0, ink.shape[0], batch):
            x = make_input(ink[i:i + batch], n[i:i + batch])
            logits = model(x)
            # letters beyond n are impossible
            nk = n[i:i + batch].view(-1, 1, 1, 1)
            ks = torch.arange(K).view(1, K, 1, 1)
            logits = logits.masked_fill(ks >= nk, -1e9)
            lab = logits.argmax(1)
            lab[~ink[i:i + batch]] = -1
            out.append(lab)
    return torch.cat(out)


def load_model(path=MODEL_PATH):
    m = UNet()
    m.load_state_dict(torch.load(path, map_location="cpu", weights_only=True))
    m.eval()
    return m


def label_run_with_model(model, run_polys, n, z_out=8, pad=2.0):
    """Labels for a run from the model, in the frame the cut placement expects:
    (labels, meta) like dk_lib.label_run — labels[r, c] = letter position or −1 off
    ink, meta with 'x0','y0','z','ink','masks' (one boolean mask per letter),
    'share'. The model sees the run at the training canvas scale; its prediction is
    resampled to z_out and every ink pixel takes the nearest predicted class."""
    from scipy import ndimage
    from tools.build_letter_labels import canvas_frame, raster_on_canvas
    from tools import letters_lib as L
    if n > K:
        return None, None
    frame = canvas_frame(run_polys)
    ink_c = raster_on_canvas(run_polys, frame)
    lab_c = predict(model, torch.from_numpy(ink_c[None]), torch.tensor([n]))[0].numpy()
    fx0, fy0, fz = frame
    bx0, by0, bx1, by1 = L.bbox(run_polys)
    x0, y0 = bx0 - pad, by0 - pad
    w, h = (bx1 - bx0) + 2 * pad, (by1 - by0) + 2 * pad
    ink = L.raster(run_polys, x0, y0, w, h, z_out)
    Hh, Ww = ink.shape
    # map every output pixel centre to the canvas pixel holding it
    rr, cc = np.mgrid[0:Hh, 0:Ww]
    px = x0 + (cc + 0.5) / z_out
    py = y0 + (rr + 0.5) / z_out
    cr = np.clip(((py - fy0) * fz).astype(int), 0, H - 1)
    cch = np.clip(((px - fx0) * fz).astype(int), 0, W - 1)
    labels = lab_c[cr, cch]
    labels = np.where(ink, labels, -1)
    # ink pixels the coarse prediction missed take the nearest predicted class
    missing = ink & (labels < 0)
    if missing.any():
        have = labels >= 0
        if have.any():
            _, (ir, ic) = ndimage.distance_transform_edt(~have, return_indices=True)
            labels[missing] = labels[ir[missing], ic[missing]]
    masks = [labels == k for k in range(n)]
    n_ink = max(1, int(ink.sum()))
    meta = {"x0": x0, "y0": y0, "z": z_out, "ink": ink, "masks": masks, "iou": 1.0,
            "share": [float(m.sum() / n_ink) for m in masks], "shape": labels.shape}
    return labels, meta
