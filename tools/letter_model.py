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
    def __init__(self, cin=None, base=24, k=K):
        cin = cin or CIN
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


# the 28 base letters + the ones this script writes as their own shapes
ALPHABET = "ابتثجحخدذرزسشصضطظعغفقكلمنهويىةء"
CIN = 4 + 2 * K          # ink, x, y, n/K, then per position (letter id, form)


def letter_codes(letters):
    """letters: list of base chars for the run (reading order) → (K,) ids in [1, 40],
    0 for an empty slot."""
    out = torch.zeros(K, dtype=torch.long)
    for k, ch in enumerate(letters[:K]):
        i = ALPHABET.find(ch)
        out[k] = (i + 1) if i >= 0 else len(ALPHABET) + 1
    return out


def form_codes(n):
    """(K,) form per position: 0 empty, 1 isolated, 2 initial, 3 medial, 4 final — a run
    is a connected stroke, so its first letter is initial, its last final."""
    out = torch.zeros(K, dtype=torch.long)
    if n == 1:
        out[0] = 1
    else:
        out[0] = 2
        out[1:n - 1] = 3
        out[n - 1] = 4
    return out


def make_input(ink, n, codes=None):
    """ink: (B, H, W) bool; n: (B,); codes: (B, K) letter ids (None → zeros) →
    (B, CIN, H, W) float: ink, x, y, n/K, and per position its letter id/40 and form/4
    broadcast over the canvas."""
    B = ink.shape[0]
    ys = torch.linspace(0, 1, H).view(1, 1, H, 1).expand(B, 1, H, W)
    xs = torch.linspace(0, 1, W).view(1, 1, 1, W).expand(B, 1, H, W)
    nn_ = (n.float() / K).view(B, 1, 1, 1).expand(B, 1, H, W)
    if codes is None:
        codes = torch.zeros(B, K, dtype=torch.long)
    forms = torch.stack([form_codes(int(v)) for v in n])
    cond = torch.cat([codes.float() / 40.0, forms.float() / 4.0], 1)          # (B, 2K)
    cond = cond.view(B, 2 * K, 1, 1).expand(B, 2 * K, H, W)
    return torch.cat([ink.float().unsqueeze(1), xs, ys, nn_, cond], 1)


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
    """→ (ink, mask, n, metas, codes)."""
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
    codes = torch.stack([letter_codes(m.get("letters", [])) for m in metas])
    return (torch.from_numpy(np.stack(inks)), torch.from_numpy(np.stack(masks).astype(np.int64)),
            torch.tensor(ns, dtype=torch.int64), metas, codes)


def predict(model, ink, n, batch=64, codes=None):
    """ink (B, H, W) bool, n (B,), codes (B, K) → labels (B, H, W) int64 (−1 off ink)."""
    model.eval()
    out = []
    with torch.no_grad():
        for i in range(0, ink.shape[0], batch):
            x = make_input(ink[i:i + batch], n[i:i + batch], None if codes is None else codes[i:i + batch])
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


def label_run_with_model(model, run_polys, n, z_out=8, pad=2.0, letters=None):
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
    codes = letter_codes(letters)[None] if letters else None
    lab_c = predict(model, torch.from_numpy(ink_c[None]), torch.tensor([n]), codes=codes)[0].numpy()
    lab_c = clean_labels(lab_c, ink_c, n)
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
    labels = clean_labels(labels, ink, n)          # resampling leaves specks at the joints
    labels = np.where(ink, labels, -1)
    masks = [labels == k for k in range(n)]
    n_ink = max(1, int(ink.sum()))
    meta = {"x0": x0, "y0": y0, "z": z_out, "ink": ink, "masks": masks, "iou": 1.0,
            "share": [float(m.sum() / n_ink) for m in masks], "shape": labels.shape}
    return labels, meta


def clean_labels(lab, ink, n, small=0.08):
    """Continuity, in two moves. (1) A fragment of letter k under `small` of the
    letter's pixels that touches another letter goes to the letter it touches most.
    (2) A letter still in two regions on ONE connected piece of ink is joined: the
    cheapest ink path between its two largest regions, widened to the stroke, is
    relabelled to it — the way a ك after ل takes the lower stem that links its arm to
    its baseline. A repair that would leave another letter in pieces is not applied."""
    from scipy import ndimage
    import heapq
    lab = lab.copy()
    eight = np.ones((3, 3), dtype=bool)
    for _round in range(3):
        changed = False
        for k in range(n):
            m = lab == k
            tot = int(m.sum())
            if tot == 0:
                continue
            comp, nc = ndimage.label(m, structure=eight)
            if nc <= 1:
                continue
            sizes = np.bincount(comp.ravel())
            for cid in range(1, nc + 1):
                if sizes[cid] >= small * tot:
                    continue
                frag = comp == cid
                ring = ndimage.binary_dilation(frag, structure=eight) & ink & ~frag
                nb = lab[ring]
                nb = nb[(nb >= 0) & (nb != k)]
                if len(nb):
                    lab[frag] = int(np.bincount(nb).argmax())
                    changed = True
        if not changed:
            break
    # (2) join what is still in pieces on the same ink component
    ink_comp, _ = ndimage.label(ink, structure=eight)
    dt = ndimage.distance_transform_edt(ink)
    H, W = ink.shape
    for k in range(n):
        m = lab == k
        comp, nc = ndimage.label(m, structure=eight)
        if nc <= 1:
            continue
        sizes = np.bincount(comp.ravel())
        order = sorted(range(1, nc + 1), key=lambda c: -sizes[c])
        a, b = order[0], order[1]
        ra = comp == a
        rb = comp == b
        ca = np.bincount(ink_comp[ra].ravel()).argmax()
        cb = np.bincount(ink_comp[rb].ravel()).argmax()
        if ca != cb:
            continue                              # different contours: nothing to join
        # cheapest path through this ink component from region a to region b
        allowed = ink_comp == ca
        dist = np.full(ink.shape, np.inf)
        prev = {}
        pq = []
        for r, c in zip(*np.nonzero(ra)):
            dist[r, c] = 0.0
            pq.append((0.0, int(r), int(c)))
        heapq.heapify(pq)
        end = None
        while pq:
            g, r, c = heapq.heappop(pq)
            if g > dist[r, c]:
                continue
            if rb[r, c]:
                end = (r, c)
                break
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                nr, nc_ = r + dr, c + dc
                if 0 <= nr < H and 0 <= nc_ < W and allowed[nr, nc_]:
                    ng = g + (1.4142 if dr and dc else 1.0)
                    if ng < dist[nr, nc_]:
                        dist[nr, nc_] = ng
                        prev[(nr, nc_)] = (r, c)
                        heapq.heappush(pq, (ng, nr, nc_))
        if end is None:
            continue
        path = [end]
        while path[-1] in prev:
            path.append(prev[path[-1]])
        # widen the path to the local stroke width
        band = np.zeros(ink.shape, dtype=bool)
        for r, c in path:
            w = int(dt[r, c]) + 1
            band[max(0, r - w):r + w + 1, max(0, c - w):c + w + 1] = True
        band &= ink
        trial = lab.copy()
        trial[band] = k
        # no other letter may be left in pieces or emptied by the repair
        ok = True
        for j in range(n):
            if j == k:
                continue
            mj = trial == j
            if not mj.any() or ndimage.label(mj, structure=eight)[1] > ndimage.label(lab == j, structure=eight)[1]:
                ok = False
                break
        if ok:
            lab = trial
    # (3) what the join could not connect goes to the neighbour it touches: every
    # letter ends as ONE region (Abdullah's rule). On a shared لك stem this hands the
    # arm to the ل and leaves the ك the baseline — the partition his own lines draw.
    for k in range(n):
        m = lab == k
        tot = int(m.sum())
        if not tot:
            continue
        comp, nc = ndimage.label(m, structure=eight)
        if nc <= 1:
            continue
        sizes = np.bincount(comp.ravel())
        # keep the region that continues into the NEXT letter (the baseline of a ك,
        # not its arm); with no such contact, the largest
        keep = int(sizes[1:].argmax()) + 1
        if k + 1 < n:
            nxt = lab == k + 1
            best, best_c = -1, None
            for cid in range(1, nc + 1):
                contact = int((ndimage.binary_dilation(comp == cid, structure=eight) & nxt).sum())
                if contact > best:
                    best, best_c = contact, cid
            if best > 0:
                keep = best_c
        for cid in range(1, nc + 1):
            if cid == keep:
                continue
            frag = comp == cid
            ring = ndimage.binary_dilation(frag, structure=eight) & ink & ~frag
            nb = lab[ring]
            nb = nb[(nb >= 0) & (nb != k)]
            if len(nb):
                lab[frag] = int(np.bincount(nb).argmax())
    return lab


def region_count(lab, n, ink=None):
    """Regions per letter, counted within one connected piece of ink: a letter drawn
    partly on a separate contour is not "in pieces"."""
    from scipy import ndimage
    eight = np.ones((3, 3), dtype=bool)
    if ink is None:
        ink = lab >= 0
    ink_comp, _ = ndimage.label(ink, structure=eight)
    out = []
    for k in range(n):
        m = lab == k
        if not m.any():
            out.append(0)
            continue
        worst = 1
        for cid in np.unique(ink_comp[m]):
            worst = max(worst, ndimage.label(m & (ink_comp == cid), structure=eight)[1])
        out.append(int(worst))
    return out
