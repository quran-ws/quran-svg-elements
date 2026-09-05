#!/usr/bin/env python3
"""Train the letter labeller on the hand-cut labels.

    python3 tools/train_letter_model.py --epochs 8            # → .cache/letters/model.pt
    python3 tools/train_letter_model.py --pages 1 200 --epochs 2 --quick

Pages ≡ 0 (mod 10) are held out (never trained on); the rest train. Runs with no
resolved layer are kept but weighted 0.2: they only carry the ordering constraint.
Prints the held-out exact-pixel accuracy after every epoch.
"""
import argparse
import os
import sys
import time

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import letter_model as M          # noqa: E402


def held_out(page):
    return page % 10 == 0


def exact_accuracy(model, ink, mask, n, codes, batch=128):
    """Accuracy on pixels whose set is a singleton."""
    pred = M.predict(model, ink, n, batch, codes=codes)
    single = (mask > 0) & ((mask & (mask - 1)) == 0)
    if not single.any():
        return float("nan")
    truth = torch.log2(mask[single].float()).round().long()
    return float((pred[single] == truth).float().mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, nargs=2, default=(1, 604))
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--quick", action="store_true", help="only runs with a resolved layer")
    ap.add_argument("--out", default=M.MODEL_PATH)
    ap.add_argument("--init", help="start from this checkpoint (fine-tune)")
    ap.add_argument("--frac", type=float, default=1.0,
                    help="each epoch sees every drawn run plus this fraction of the others (short fine-tunes)")
    ap.add_argument("--drawn-weight", type=float, default=10.0, help="loss weight of a hand-drawn run")
    a = ap.parse_args()
    torch.set_num_threads(os.cpu_count())          # all cores: Abdullah wants the machine saturated
    pages = list(range(a.pages[0], a.pages[1] + 1))
    tr = M.load_pages([p for p in pages if not held_out(p)], need_known=a.quick)
    te = M.load_pages([p for p in pages if held_out(p)], need_known=True)
    if tr is None:
        print("no training data")
        return
    ink, mask, n, meta, codes = tr
    # runs cut by hand on letters_label.html are few and cover what nothing else does
    weight = torch.tensor([a.drawn_weight if m.get("drawn") else (1.0 if m.get("known") else 0.2) for m in meta])
    drawn_idx = torch.tensor([i for i, m in enumerate(meta) if m.get("drawn")], dtype=torch.long)
    other_idx = torch.tensor([i for i, m in enumerate(meta) if not m.get("drawn")], dtype=torch.long)
    per_epoch = len(drawn_idx) + int(round(a.frac * len(other_idx)))
    print("train runs %d (with a resolved layer %d), held-out runs %d"
          % (len(n), int((weight == 1).sum()), 0 if te is None else len(te[2])), flush=True)
    model = M.UNet()
    if a.init:
        model.load_state_dict(torch.load(a.init, map_location="cpu", weights_only=True))
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-4)
    steps = a.epochs * ((per_epoch + a.batch - 1) // a.batch)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=steps)
    for epoch in range(a.epochs):
        model.train()
        if a.frac < 1.0:
            pick = other_idx[torch.randperm(len(other_idx))[:per_epoch - len(drawn_idx)]]
            perm = torch.cat([drawn_idx, pick])
            perm = perm[torch.randperm(len(perm))]
        else:
            perm = torch.randperm(len(n))
        t0, tot, cnt = time.time(), 0.0, 0
        for i in range(0, len(perm), a.batch):
            idx = perm[i:i + a.batch]
            x = M.make_input(ink[idx], n[idx], codes[idx])
            # random horizontal jitter (the canvas is right-aligned; shift a little)
            shift = int(torch.randint(-6, 1, (1,)))
            if shift:
                x = torch.roll(x, shift, dims=3)
                mk = torch.roll(mask[idx], shift, dims=2)
            else:
                mk = mask[idx]
            logits = model(x)
            # per-sample weight: loss over pixels of each sample, weighted
            losses = torch.stack([M.set_loss(logits[j:j + 1], mk[j:j + 1]) for j in range(len(idx))])
            loss = (losses * weight[idx]).sum() / weight[idx].sum()
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
            tot += float(loss) * len(idx)
            cnt += len(idx)
            if (i // a.batch) % 200 == 0:
                print("  epoch %d  %d/%d  loss %.4f  %.0fs" % (epoch, i, len(perm), tot / max(1, cnt), time.time() - t0), flush=True)
        acc = exact_accuracy(model, te[0], te[1], te[2], te[4]) if te is not None else float("nan")
        print("epoch %d done: train loss %.4f  held-out exact-pixel accuracy %.4f  %.0fs"
              % (epoch, tot / max(1, cnt), acc, time.time() - t0), flush=True)
        torch.save(model.state_dict(), a.out)
    print("saved", a.out)


if __name__ == "__main__":
    main()
