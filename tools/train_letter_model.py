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


def exact_accuracy(model, ink, mask, n, batch=128):
    """Accuracy on pixels whose set is a singleton."""
    pred = M.predict(model, ink, n, batch)
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
    a = ap.parse_args()
    torch.set_num_threads(max(1, os.cpu_count() - 2))
    pages = list(range(a.pages[0], a.pages[1] + 1))
    tr = M.load_pages([p for p in pages if not held_out(p)], need_known=a.quick)
    te = M.load_pages([p for p in pages if held_out(p)], need_known=True)
    if tr is None:
        print("no training data")
        return
    ink, mask, n, meta = tr
    weight = torch.tensor([1.0 if m.get("known") else 0.2 for m in meta])
    print("train runs %d (with a resolved layer %d), held-out runs %d"
          % (len(n), int((weight == 1).sum()), 0 if te is None else len(te[2])), flush=True)
    model = M.UNet()
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-4)
    steps = a.epochs * ((len(n) + a.batch - 1) // a.batch)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=steps)
    for epoch in range(a.epochs):
        model.train()
        perm = torch.randperm(len(n))
        t0, tot, cnt = time.time(), 0.0, 0
        for i in range(0, len(n), a.batch):
            idx = perm[i:i + a.batch]
            x = M.make_input(ink[idx], n[idx])
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
                print("  epoch %d  %d/%d  loss %.4f  %.0fs" % (epoch, i, len(n), tot / max(1, cnt), time.time() - t0), flush=True)
        acc = exact_accuracy(model, *te[:3]) if te is not None else float("nan")
        print("epoch %d done: train loss %.4f  held-out exact-pixel accuracy %.4f  %.0fs"
              % (epoch, tot / max(1, cnt), acc, time.time() - t0), flush=True)
        torch.save(model.state_dict(), a.out)
    print("saved", a.out)


if __name__ == "__main__":
    main()
