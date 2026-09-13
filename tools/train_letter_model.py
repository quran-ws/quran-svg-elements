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
    ap.add_argument("--threads", type=int, default=0,
                    help="torch threads; 0 = physical cores (hyperthreads cost 2.9x here)")
    ap.add_argument("--compile", action="store_true",
                    help="torch.compile the net (worth ~6%%, pays a minute of warm-up)")
    ap.add_argument("--drawn-min-letters", type=int, default=0,
                    help="drop hand-drawn runs shorter than this from the epoch (they are the ones "
                         "over-represented in the drawn set against the mushaf)")
    a = ap.parse_args()
    # Cores, not hyperthreads. `os.cpu_count()` is 32 on this box and the convolutions run
    # 2.9x slower at 32 threads than at 24 -- see `letter_model.physical_cores`.
    torch.set_num_threads(a.threads or M.physical_cores())
    pages = list(range(a.pages[0], a.pages[1] + 1))
    tr = M.load_pages([p for p in pages if not held_out(p)], need_known=a.quick)
    te = M.load_pages([p for p in pages if held_out(p)], need_known=True)
    if tr is None:
        print("no training data")
        return
    ink, mask, n, meta, codes = tr
    # runs cut by hand on letters_label.html are few and cover what nothing else does
    # A loop drawn on the shapes page is as exact a label as a drawn cut line -- it names
    # the letter's pixels outright -- so it carries the same weight. Without this the 84
    # trims sat at the weight of an ordinary run and the review would not have reached
    # the model at all.
    weight = torch.tensor([a.drawn_weight if (m.get("drawn") or m.get("trimmed")
                                              or m.get("confirmed"))
                           else (1.0 if m.get("known") else 0.2) for m in meta])
    dropped = 0
    if a.drawn_min_letters:
        keep = []
        for i, m in enumerate(meta):
            if m.get("drawn") and int(n[i]) < a.drawn_min_letters:
                dropped += 1
                continue
            keep.append(i)
        print("dropped %d hand-drawn runs under %d letters" % (dropped, a.drawn_min_letters), flush=True)
        keep = set(keep)
    else:
        keep = None
    print("exact runs in the epoch: %d drawn, %d trimmed, %d confirmed"
          % (sum(1 for m in meta if m.get("drawn")),
             sum(1 for m in meta if m.get("trimmed")),
             sum(1 for m in meta if m.get("confirmed"))), flush=True)
    drawn_idx = torch.tensor([i for i, m in enumerate(meta)
                              if m.get("drawn") and (keep is None or i in keep)], dtype=torch.long)
    other_idx = torch.tensor([i for i, m in enumerate(meta)
                              if not m.get("drawn") and (keep is None or i in keep)], dtype=torch.long)
    per_epoch = len(drawn_idx) + int(round(a.frac * len(other_idx)))
    print("train runs %d (with a resolved layer %d), held-out runs %d"
          % (len(n), int((weight == 1).sum()), 0 if te is None else len(te[2])), flush=True)
    model = M.UNet()
    if a.init:
        model.load_state_dict(torch.load(a.init, map_location="cpu", weights_only=True))
    # oneDNN wants NHWC for a convnet: 1.5x on this box, and the weights are unchanged, so
    # a checkpoint saved from here loads anywhere. (bfloat16 autocast was measured too and
    # is 2.6x SLOWER -- this CPU has AVX-VNNI but no AMX, so bf16 convolutions emulate.)
    model = model.to(memory_format=torch.channels_last)
    if a.compile:
        model = torch.compile(model)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-4)
    steps = a.epochs * ((per_epoch + a.batch - 1) // a.batch)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=steps)
    for epoch in range(a.epochs):
        model.train()
        if a.frac < 1.0 or a.drawn_min_letters:
            want = max(0, per_epoch - len(drawn_idx))
            pick = other_idx[torch.randperm(len(other_idx))[:want]]
            perm = torch.cat([drawn_idx, pick])
            perm = perm[torch.randperm(len(perm))]
        else:
            perm = torch.randperm(len(n))
        t0, tot, cnt = time.time(), 0.0, 0
        for i in range(0, len(perm), a.batch):
            idx = perm[i:i + a.batch]
            # random horizontal jitter (the canvas is right-aligned; shift a little)
            shift = int(torch.randint(-6, 1, (1,)))
            x = M.make_input(ink[idx], n[idx], codes[idx], shift=shift)
            x = x.contiguous(memory_format=torch.channels_last)
            mk = torch.roll(mask[idx], shift, dims=2) if shift else mask[idx]
            logits = model(x)
            # per-sample weight: loss over pixels of each sample, weighted
            losses = M.set_loss_batch(logits, mk)
            loss = (losses * weight[idx]).sum() / weight[idx].sum()
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
            tot += float(loss.detach()) * len(idx)
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
