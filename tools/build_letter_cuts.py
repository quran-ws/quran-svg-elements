#!/usr/bin/env python3
"""Decide where every multi-letter run is cut, and store the decision as data.

    python3 tools/build_letter_cuts.py 1 604 --jobs 32      # → .cache/letters/cuts/NNN.json
    python3 tools/build_letter_cuts.py 50                    # one page, prints a summary

Per run (a `<g class="ligature">` drawing 2+ letters), in falling order of proof:
  1. hand cuts lifted from the QUL tajweed page font (tajweed_lib) — every joint a
     coloured letter layer touches;
  2. DigitalKhatt template labels (dk_lib) say which ink is which letter; each joint
     the hand did not cut gets the neck cut nearest the label boundary.
The hand cuts are mapped to joints by the DK letter centroids, and the whole set is
dry-run through letters_lib.cut_run() so the record only ever holds cuts that
produce len(text) pieces conserving area; anything else is a flag, never a guess.

Record shape: see the spec (docs/superpowers/specs/2026-09-05-…-design.md).
"""
import argparse
import json
import math
import os
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import letters_lib as L          # noqa: E402
from tools import tajweed_lib as T          # noqa: E402
from tools import dk_lib as D               # noqa: E402

MIN_AGREE = 0.35       # below this the labels and the cut disagree badly enough to review
MODEL = None           # set by --model: the learned labeller replaces the DK templates


def _mid(poly):
    return (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))


def _piece_masks(pieces, meta):
    z, x0, y0 = meta["z"], meta["x0"], meta["y0"]
    shape = meta["shape"]
    out = []
    for d in pieces:
        m = L.raster(L.flatten(d), x0, y0, shape[1] / z, shape[0] / z, z)
        m = m[:shape[0], :shape[1]]
        pad = np.zeros(shape, dtype=bool)
        pad[:m.shape[0], :m.shape[1]] = m
        out.append(pad)
    return out


def align_runs(word):
    """Pair the emitted ligature groups (with body ink) to the letter indices they
    draw. The groups are not in reading order in the file, so they are ordered by ink
    position (rightmost first) and their texts must then concatenate to the word's
    rasm — the emitter's runs are the truth of the INK, which joins letters the rules
    split (كفروا drawn as one stroke) and splits some the rules join. When ink order
    fails (stacked groups overlap in x) the groups are matched by text against the
    rule-based runs instead. A bare ء drawn as its own group becomes a body letter.
    Returns (letters, [(lig, [letter idx…])…] in reading order) or (letters, None)."""
    letters = L.letters_of(word["uthmani"])
    ligs = [l for l in word["ligatures"] if any(p["kind"] == "body" for p in l["paths"])]
    if any(l["text"] == "ء" for l in ligs):
        for l in letters:
            if l["ch"] == "ء" and not l["body"]:
                l["body"] = True
                l["marks"] = [m for m in l["marks"] if m != "hamza"]
    body_idx = [i for i, l in enumerate(letters) if l["body"]]
    rasm = "".join(letters[i]["ch"] for i in body_idx)

    def xpos(l):
        return max(L.bbox(L.flatten(p["d"]))[2] for p in l["paths"] if p["kind"] == "body" and p["d"])

    ordered = sorted(ligs, key=xpos, reverse=True)
    if "".join(l["text"] for l in ordered) == rasm:
        out, pos = [], 0
        for l in ordered:
            out.append((l, body_idx[pos:pos + len(l["text"])]))
            pos += len(l["text"])
        return letters, (_rebalance(out, letters) if os.environ.get("QSVG_LETTERS_REBAL", "1") != "0" else out)
    runs = [r for r in L.runs_of(letters) if letters[r[0]]["body"]]
    expected = ["".join(letters[i]["ch"] for i in r) for r in runs]
    texts = [l["text"] for l in ligs]
    if sorted(expected) != sorted(texts):
        return letters, None
    by_text = {}
    for l in ligs:
        by_text.setdefault(l["text"], []).append(l)
    for t in by_text:
        by_text[t].sort(key=xpos, reverse=True)
    return letters, [(by_text[t].pop(0), idx) for t, idx in zip(expected, runs)]


NOJOIN = set("اأإآٱدذرزوؤءةى")          # letters that never join the letter after them


def _contours(lig, side="right"):
    """The separate pieces of ink in the group (8-connected, 4 px per unit): their
    count; whether the piece on the given side stands clear of the others in x (nothing
    else reaches past half its width — a misfiled و carries the ا it was filed with
    under its tail, so half the width, not the whole of it, is the test); and that
    piece's box in page units with its pixel count."""
    from scipy import ndimage
    polys = [poly for p in lig["paths"] if p["kind"] == "body" and p["d"] for poly in L.flatten(p["d"])]
    x0, y0, x1, y1 = L.bbox(polys)
    m = L.raster(polys, x0 - 1, y0 - 1, x1 - x0 + 2, y1 - y0 + 2, 4)
    lab, n = ndimage.label(m, structure=np.ones((3, 3), dtype=bool))
    if n < 2:
        return n, False, None, 0
    boxes = []
    for k in range(1, n + 1):
        ys, xs = np.nonzero(lab == k)
        boxes.append((int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max()), int(len(xs))))
    boxes.sort(key=(lambda bx: -bx[1]) if side == "right" else (lambda bx: bx[0]))
    bx = boxes[0]
    clear = (max(o[1] for o in boxes[1:]) <= bx[1] - 0.5 * (bx[1] - bx[0])) if side == "right" \
        else (min(o[0] for o in boxes[1:]) >= bx[0] + 0.5 * (bx[1] - bx[0]))
    box = (x0 - 1 + bx[0] / 4, x0 - 1 + bx[1] / 4, y0 - 1 + bx[2] / 4, y0 - 1 + bx[3] / 4)
    return n, clear, box, bx[4]


def _expected(chars):
    """Contours the text says this letter sequence must draw: one, plus one for every
    letter that never joins the letter after it."""
    return sum(1 for ch in chars[:-1] if ch in NOJOIN) + 1


ALEFS = set("اأإآٱ")


def _rebalance(out, letters):
    """The word build sometimes files a letter's ink in the NEXT group (ٱلْحَرَامِ: the
    group texted لحرا holds one contour, لحر, and the ا sits in the م group;
    تُكَذِّبَانِ: the group texted تكذبا holds تكذ and با sits in the ن group). Two
    independent proofs, either one enough, and both verified by eye over the words
    they move (41 and 33 words on 61 sample pages, 2026-09-06):

    * the counts square. The source draws FEWER contours than its text needs (one per
      letter that never joins the letter after it, plus one), the group after it draws
      MORE than its own text needs, and moving the letters after the source's last
      break makes both counts exactly right. Letters that merely touch (ر against و)
      can only lower a count, never raise one, so the source being short is not proof
      on its own — the target's surplus is the second witness.
    * the moved letter is an ا or a و of the measured size. Over 3,718 lone groups at
      4 px per unit an ا is 123-169 px with height 5.4x its width, a و 262-299 px at
      1.09, a bare ء — which also sits clear at the right of a group — 154-179 px at
      1.15; the bands do not touch. This catches the ones where the moved ink touches
      its new neighbour, so the target's count cannot square.

    Both require the target's rightmost contour to stand clear of the rest of its ink:
    a final ه ring, a hamza seat or a kaf arm add a contour to a group, but never a
    clear one at its right edge."""
    out = [(l, list(idx)) for l, idx in out]
    for k in range(len(out) - 1):
        lig, idx = out[k]
        chars = [letters[i]["ch"] for i in idx]
        breaks = [j for j in range(len(chars) - 1) if chars[j] in NOJOIN]
        if not breaks:
            continue
        have = _contours(lig)[0]
        if have >= _expected(chars):
            continue                                   # the source is not short
        nlig, nidx = out[k + 1]
        nchars = [letters[i]["ch"] for i in nidx]
        nhave, clear, box, npx = _contours(nlig)
        if not clear or nhave <= _expected(nchars):
            continue                                   # the target holds no clear surplus
        j = breaks[-1]
        moved = chars[j + 1:]
        squares = (have == _expected(chars[:j + 1]) and nhave == _expected(moved + nchars))
        shaped = len(moved) == 1 and _shaped(moved[0], box, npx)
        if not (squares or shaped):
            continue
        nidx[0:0] = idx[j + 1:]
        del idx[j + 1:]
        out[k] = (lig, idx)
    return _rebalance_back(out, letters)


def _shaped(ch, box, px):
    """Does a lone contour have the measured size and shape of this letter? Over 3,718
    lone groups at 4 px per unit an ا is 123-169 px with height 5.4x its width, a و
    262-299 px at 1.09 and a bare ء 154-179 px at 1.15; the bands do not touch."""
    if box is None:
        return False
    ratio = (box[3] - box[2]) / max(box[1] - box[0], 0.25)
    if ch in ALEFS:
        return 100 <= px <= 200 and ratio >= 3.5
    if ch == "و":
        return 220 <= px <= 330 and 0.8 <= ratio <= 1.5
    return False


def _rebalance_back(out, letters):
    """The mirror of _rebalance: a group's FIRST letter whose ink was filed in the
    group BEFORE it (وَٱلْمَوْقُوذَةُ: the group texted المو draws one contour, لمو, and the
    ا stands in the و group). The witnesses are the same counts read the other way —
    this group short, the one before it over its own text, and the moved letter's ink
    the right size and shape at that group's left edge. The `clear` test is not used
    here: an ا filed with a و is drawn hard against it and overlaps it in x, which is
    exactly why the word build put them together."""
    out = [(l, list(idx)) for l, idx in out]
    for k in range(1, len(out)):
        lig, idx = out[k]
        if len(idx) < 2:
            continue
        chars = [letters[i]["ch"] for i in idx]
        lead = chars[0]
        if lead not in ALEFS and lead != "و":
            continue
        have = _contours(lig)[0]
        if have >= _expected(chars):
            continue
        plig, pidx = out[k - 1]
        pchars = [letters[i]["ch"] for i in pidx]
        phave, _, box, px = _contours(plig, side="left")
        if phave <= _expected(pchars) or not _shaped(lead, box, px):
            continue
        if have != _expected(chars[1:]) or phave != _expected(pchars + [lead]):
            continue
        pidx.append(idx.pop(0))
        out[k] = (lig, idx)
    return [(l, idx) for l, idx in out if idx]


def cut_run_record(word, lig, idx, letters, lg, font, pair, scale, word_tree):
    """The cuts for one multi-letter run. Returns the run record."""
    bodies = [p for p in lig["paths"] if p["kind"] == "body" and p["d"]]
    main = max(bodies, key=lambda p: L.area(p["d"]))
    rp = [poly for p in bodies for poly in L.flatten(p["d"])]
    main_polys = L.flatten(main["d"])
    text = lig["text"]
    rec = {"text": text, "letters": idx, "eid": [p["eid"] for p in bodies], "main": main["eid"],
           "cuts": [], "flags": [], "extra": {}}
    n = len(idx)
    # --- labels: which ink is which letter — the learned model when given, else DK
    entries = [lg[i] for i in idx]
    labels = meta = None
    if MODEL is not None:
        from tools import letter_model as LM
        labels, meta = LM.label_run_with_model(MODEL, rp, n, letters=[letters[i]["ch"] for i in idx])
        if labels is not None:
            rec["model"] = {"share": [round(s, 3) for s in meta["share"]],
                            "regions": LM.region_count(labels, n, meta["ink"])}
    elif all(e is not None for e in entries):
        labels, meta = D.label_run(rp, entries)
        if labels is not None:
            meta["shape"] = labels.shape
            rec["dk"] = {"iou": round(meta["iou"], 3), "share": [round(s, 3) for s in meta["share"]]}
    if labels is None:
        rec["flags"].append("dk-unshaped")
        rec["cuts"] = []
        return rec
    # reference points on the MAIN contour only (a kaf's separate stroke is cut nowhere)
    z_, mx0, my0 = meta["z"], meta["x0"], meta["y0"]
    mm = L.raster(main_polys, mx0, my0, meta["shape"][1] / z_, meta["shape"][0] / z_, z_)[:meta["shape"][0], :meta["shape"][1]]
    main_mask = np.zeros(meta["shape"], dtype=bool)
    main_mask[:mm.shape[0], :mm.shape[1]] = mm
    main_labels = np.where(main_mask, labels, -1)
    anchors_ = D.anchors(main_labels, meta, n=n)
    refs = [a[0] if a else None for a in anchors_]
    rec["anchors"] = [[[round(x, 3), round(y, 3)] for x, y in a] for a in anchors_]
    rec["refs"] = [[round(r[0], 3), round(r[1], 3)] if r else None for r in refs]
    # letters drawn on the main contour (a group can hold a separate contour for a
    # letter — ة after و — which needs no cut, only its contour assigned)
    on_main = [k for k in range(n) if anchors_[k]]
    # a letter with no labelled pixel on the main contour and no separate contour to
    # be is still on the main contour (the text says it exists, the ink is one piece):
    # anchor it on the main-contour pixel nearest its template's centre
    others_n = len([p for p in bodies if p is not main])
    missing = [k for k in range(n) if k not in on_main]
    if len(missing) > others_n:
        mys, mxs = np.nonzero(main_mask)
        for k in missing[:len(missing) - others_n]:
            tm = meta["masks"][k]
            if tm.any():
                tys, txs = np.nonzero(tm)
                cy, cx = tys.mean(), txs.mean()
            else:
                cy, cx = mys.mean(), mxs.mean()
            j = int(np.argmin((mxs - cx) ** 2 + (mys - cy) ** 2))
            anchors_[k] = [(meta["x0"] + (mxs[j] + 0.5) / meta["z"], meta["y0"] + (mys[j] + 0.5) / meta["z"])]
            rec["flags"].append("anchor-forced:%d" % k)
        on_main = [k for k in range(n) if anchors_[k]]
        rec["anchors"] = [[[round(x, 3), round(y, 3)] for x, y in a] for a in anchors_]
    rec["main_letters"] = on_main
    joints = [(on_main[j], on_main[j + 1]) for j in range(len(on_main) - 1)]
    if not on_main:
        rec["flags"].append("no-main-letters")
        return rec
    if MODEL is not None:
        return _model_cuts(rec, main, main_polys, rp, labels, meta, anchors_, on_main, joints,
                           bodies, n, [letters[i]["ch"] for i in idx])
    # --- hand cuts, each mapped to the joint its midpoint sits on
    cuts = {}
    if pair is not None and font is not None:
        for name, cid in font.layers(pair["code"]):
            if not font.is_letter_layer(cid):
                continue
            lp = font.outline_page(name, scale, pair["tx"], pair["ty"])
            for c in T.lift_cuts(lp, word_tree, main_polys):
                j = D.joint_of_cut(labels, meta, c, anchors_=anchors_)
                if j is None or j >= n - 1:
                    rec["flags"].append("hand-cut-unmapped")
                    continue
                if j in cuts:                       # the neighbouring layer cut the same joint
                    continue
                cuts[j] = {"poly": [(round(x, 3), round(y, 3)) for x, y in c], "src": "tajweed",
                           "after": j, "conf": 1.0, "layer": name,
                           "layer_area": round(T.layer_area(font, name, scale), 3)}
    # --- DK joints for the rest (a joint between letters i and i2 that share the main
    # contour; the record's `after` is i)
    for i, i2 in joints:
        if i in cuts:
            continue
        why = None
        if MODEL is not None:
            nc, why = D.boundary_cuts(rp, labels, meta, i, anchors_=anchors_)
        else:
            nc = D.joint_cut(rp, labels, meta, i, anchors_=anchors_)
        if nc is None:
            rec["flags"].append("neck-missing:%d%s" % (i, ":" + why if why else ""))
            continue
        conf = 1.0
        if nc["thick"] > 0:
            conf *= min(1.0, nc["thick"] / max(nc["neck"], 1e-6))      # a long chord for its stroke
        conf *= max(0.0, 1.0 - nc["boundary_dist"] / 1.5)
        cuts[i] = {"poly": [(round(x, 3), round(y, 3)) for x, y in nc["poly"]],
                   "polys": [[(round(x, 3), round(y, 3)) for x, y in pl] for pl in nc.get("polys", [nc["poly"]])],
                   "src": "dk", "how": nc.get("how", "neck"),
                   "after": i, "conf": round(conf, 3), "neck": round(nc["neck"], 3),
                   "boundary_dist": round(nc["boundary_dist"], 3), "thick": round(nc["thick"], 3)}
    ordered = [cuts[i] for i, _ in joints if i in cuts]
    if len(ordered) != len(joints):
        rec["flags"].append("incomplete")
    # --- dry run of the full set, and side agreement with the labels
    if ordered and "incomplete" not in rec["flags"]:
        try:
            pieces = L.cut_run(main["d"], [c.get("polys", [c["poly"]]) for c in ordered],
                               refs=[anchors_[k] for k in on_main])
        except L.CutError as e:
            rec["flags"].append("cut-failed:%s" % e.why)
            pieces = None
        if pieces is not None:
            masks = _piece_masks(pieces, meta)
            agree = []
            for k, m in zip(on_main, masks):
                li = labels == k
                agree.append(float((li & m).sum() / max(1, li.sum())))
            rec["agree"] = [round(a, 3) for a in agree]
            if min(agree) < MIN_AGREE:
                rec["flags"].append("side-disagreement")
            for k, c in enumerate(ordered):
                if c["src"] == "dk":
                    c["conf"] = round(min(c["conf"], (agree[k] + agree[k + 1]) / 2), 3)
    # --- other contours of the run. Letters with no ink on the main contour must be
    # these (the text says they exist): pair them right→left when the counts match;
    # otherwise each contour goes to its majority label (a kaf's separate stroke).
    z, x0, y0 = meta["z"], meta["x0"], meta["y0"]
    others = [p for p in bodies if p is not main]
    missing = [k for k in range(n) if k not in on_main]
    # Which letter a detached body belongs to is a question the labels already answer,
    # so ask them first and pair by position only when they cannot. Pairing right-to-left
    # whenever the counts happen to match is a guess dressed as a rule: it ignores the
    # evidence, and where the two disagree it is the guess that is wrong.
    by_label = {}
    for p in others:
        m = L.raster(L.flatten(p["d"]), x0, y0, meta["shape"][1] / z, meta["shape"][0] / z, z)
        m = m[:meta["shape"][0], :meta["shape"][1]]
        sub = labels[:m.shape[0], :m.shape[1]][m]
        sub = sub[sub >= 0]
        by_label[p["eid"]] = int(np.bincount(sub).argmax()) if len(sub) else None
    if others and all(v is not None for v in by_label.values()):
        rec["extra"].update(by_label)
    elif others and len(others) == len(missing):
        others_sorted = sorted(others, key=lambda p: -L.bbox(L.flatten(p["d"]))[2])
        for p, k in zip(others_sorted, missing):
            rec["extra"][p["eid"]] = k
    else:
        for p in others:
            rec["extra"][p["eid"]] = by_label.get(p["eid"]) or 0
        # a missing letter must still get a contour: the free one nearest its template
        held = {}
        for eid, k in rec["extra"].items():
            held.setdefault(k, []).append(eid)
        by_eid = {p["eid"]: p for p in others}
        for k in missing:
            if held.get(k):
                continue
            tm = meta["masks"][k]
            if tm.any():
                tys, txs = np.nonzero(tm)
                cx = meta["x0"] + (txs.mean() + 0.5) / z
            else:
                cx = None
            cands = [eid for eid, kk in rec["extra"].items() if kk in on_main or len(held.get(kk, [])) > 1]
            if not cands:
                continue
            if cx is not None:
                eid = min(cands, key=lambda e: abs(sum(L.bbox(L.flatten(by_eid[e]["d"]))[0::2]) / 2 - cx))
            else:
                eid = cands[0]
            held.setdefault(rec["extra"][eid], []).remove(eid)
            rec["extra"][eid] = k
            held.setdefault(k, []).append(eid)
    rec["cuts"] = ordered
    return rec


def _feed_empty_masks(masks, on_main, chars, z):
    """A letter on the main contour with no pixel of it: take some from its neighbour.

    `repair_starved` does this over the whole run; this repeats it on the main contour
    alone, because that is what the cut is made on and a letter can own ink only elsewhere.
    The rule itself lives in `letter_model.feed_starved_masks`.
    """
    from tools import letter_model as LM
    LM.feed_starved_masks(masks, [chars[k] if k < len(chars) else "" for k in on_main], z)


def _model_cuts(rec, main, main_polys, rp, labels, meta, anchors_, on_main, joints, bodies, n,
                chars=()):
    """MODEL mode: the label map is the ownership; chords only straighten boundaries."""
    ordered = []
    for i, i2 in joints:
        polys = D.boundary_chords(main_polys, labels, meta, i)
        ordered.append({"poly": polys[0] if polys else [], "polys": polys, "src": "model", "how": "boundary",
                        "after": i, "conf": 1.0, "chords": len(polys)})
    if any(r > 1 for r in rec.get("model", {}).get("regions", [])):
        rec["flags"].append("letter-in-pieces:%s" % ",".join(str(r) for r in rec["model"]["regions"]))
    masks = [meta["masks"][k] for k in on_main]
    # ownership restricted to the main contour
    z, x0, y0 = meta["z"], meta["x0"], meta["y0"]
    mm = L.raster(main_polys, x0, y0, meta["shape"][1] / z, meta["shape"][0] / z, z)
    main_mask = np.zeros(meta["shape"], dtype=bool)
    main_mask[:mm.shape[0], :mm.shape[1]] = mm[:meta["shape"][0], :meta["shape"][1]]
    masks = [m & main_mask for m in masks]
    from tools import letter_model as _LM
    if _LM.FORCE_STARVE:
        _feed_empty_masks(masks, on_main, chars, meta["z"])
    try:
        pieces = L.cut_run_masks(main["d"], masks, [c["polys"] for c in ordered], (x0, y0, z))
    except L.CutError as e:
        rec["flags"].append("cut-failed:%s" % e.why)
        pieces = None
    if pieces is not None:
        rec["agree"] = [1.0] * len(on_main)
    others = [p for p in bodies if p is not main]
    missing = [k for k in range(n) if k not in on_main]
    if len(missing) > len(others):
        rec["flags"].append("cut-failed:letter without ink")     # the model gave it no pixel anywhere
    _assign_extras(rec, others, missing, on_main, labels, meta, n)
    rec["cuts"] = ordered
    rec["mode"] = "model"
    return rec


def _assign_extras(rec, others, missing, on_main, labels, meta, n):
    """Separate contours of a run go to letters: paired right→left with the letters
    that have no ink on the main contour when the counts match; else each by majority
    label, and then every still-empty missing letter takes, from letters holding more
    than one body, the contour nearest to where it should sit."""
    z, x0, y0 = meta["z"], meta["x0"], meta["y0"]
    if not others:
        return
    xc = {p["eid"]: (lambda b: (b[0] + b[2]) / 2)(L.bbox(L.flatten(p["d"]))) for p in others}
    if len(others) == len(missing):
        for p, k in zip(sorted(others, key=lambda p: -xc[p["eid"]]), missing):
            rec["extra"][p["eid"]] = k
        return
    for p in others:
        m = L.raster(L.flatten(p["d"]), x0, y0, meta["shape"][1] / z, meta["shape"][0] / z, z)
        m = m[:meta["shape"][0], :meta["shape"][1]]
        sub = labels[:m.shape[0], :m.shape[1]][m]
        sub = sub[sub >= 0]
        rec["extra"][p["eid"]] = int(np.bincount(sub).argmax()) if len(sub) else 0
    # letter x positions on the main contour, for "where it should sit"
    pos = {}
    for k in on_main:
        ys, xs = np.nonzero(meta["masks"][k])
        if len(xs):
            pos[k] = x0 + xs.mean() / z
    for k in missing:
        if k in rec["extra"].values():
            continue
        bodies_of = {}
        for eid, o in rec["extra"].items():
            bodies_of.setdefault(o, []).append(eid)
        cands = [eid for o, eids in bodies_of.items() if (o in on_main and eids) or len(eids) > 1 for eid in eids]
        if not cands:
            continue
        nb = [pos[j] for j in (k - 1, k + 1) if j in pos]
        if nb:
            want = sum(nb) / len(nb)
        else:
            want = max(xc.values()) if k == 0 else min(xc.values())
        best = min(cands, key=lambda eid: abs(xc[eid] - want))
        rec["extra"][best] = k


def build_page(page, use_tajweed=True):
    words, _ = L.read_words(page)
    font = pairs = None
    scale = T.DEFAULT_SCALE
    if use_tajweed and os.path.exists(os.path.join(T.FONTS, "p%d.ttf" % page)):
        font = T.PageFont(page)
        scale = T.page_scale(words, font)
        pairs = T.pair_glyphs(words, font, scale)
    out = {"page": page, "scale": scale, "words": {}, "model": MODEL_PATH if MODEL is not None else None}
    for w in words:
        wrec = {"runs": [], "flags": []}
        if pairs is not None:
            p = pairs.get(w["wid"])
            wrec["reg"] = ({"code": "%04X" % p["code"], "tx": round(p["tx"], 3), "ty": round(p["ty"], 3),
                            "cov": round(p["cov"], 3)} if p else None)
            if p is None:
                wrec["flags"].append("no-registration")
        try:
            letters, runs = align_runs(w)
        except ValueError as e:
            wrec["flags"].append("text:%s" % e)
            out["words"][w["wid"]] = wrec
            continue
        if runs is None:
            wrec["flags"].append("run-text-mismatch")
            out["words"][w["wid"]] = wrec
            continue
        lg = D.letter_glyphs(w["uthmani"], letters)
        word_tree = None
        if pairs is not None and pairs.get(w["wid"]):
            allp = [poly for q in w["paths"] if q["d"] for poly in L.flatten(q["d"])]
            word_tree, _ = L.outline_tree(allp, 0.05)
        for lig, idx in runs:
            if len(idx) < 2:
                bodies = [p["eid"] for p in lig["paths"] if p["kind"] == "body"]
                wrec["runs"].append({"text": lig["text"], "letters": idx, "eid": bodies, "cuts": [], "flags": []})
                continue
            try:
                rec = cut_run_record(w, lig, idx, letters, lg, font,
                                     pairs.get(w["wid"]) if pairs else None, scale, word_tree)
            except Exception:                    # never lose a page to one run
                rec = {"text": lig["text"], "letters": idx, "cuts": [], "flags": ["error"],
                       "trace": traceback.format_exc()[-800:]}
            wrec["runs"].append(rec)
        out["words"][w["wid"]] = wrec
    return out


def summary(rec):
    runs = [r for w in rec["words"].values() for r in w["runs"] if len(r["letters"]) > 1]
    cuts = [c for r in runs for c in r["cuts"]]
    flagged = [r for r in runs if r["flags"]]
    return {"page": rec["page"], "multi_runs": len(runs), "cuts": len(cuts),
            "hand": sum(1 for c in cuts if c["src"] == "tajweed"),
            "dk": sum(1 for c in cuts if c["src"] == "dk"),
            "flagged_runs": len(flagged),
            "word_flags": sum(1 for w in rec["words"].values() if w["flags"])}


MODEL_PATH = None


def _init_model(path):
    """Worker initialiser: load the labeller once per process."""
    global MODEL
    if path:
        import torch
        torch.set_num_threads(1)
        from tools import letter_model as LM
        MODEL = LM.load_model(path)


def _one(page):
    t = time.time()
    if MODEL is None and MODEL_PATH:
        _init_model(MODEL_PATH)
    rec = build_page(page)
    os.makedirs(L.CUTS_DIR, exist_ok=True)
    with open(os.path.join(L.CUTS_DIR, "%03d.json" % page), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False)
    s = summary(rec)
    s["secs"] = round(time.time() - t, 1)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("first", type=int)
    ap.add_argument("last", type=int, nargs="?")
    ap.add_argument("--jobs", type=int, default=32)
    ap.add_argument("--model", help="path of a trained letter labeller (.pt); replaces the DK templates")
    a = ap.parse_args()
    pages = range(a.first, (a.last or a.first) + 1)
    tot = {"multi_runs": 0, "cuts": 0, "hand": 0, "dk": 0, "flagged_runs": 0, "word_flags": 0}
    global MODEL_PATH
    MODEL_PATH = a.model
    with ProcessPoolExecutor(min(a.jobs, len(pages)), initializer=_init_model, initargs=(a.model,)) as ex:
        for s in ex.map(_one, pages):
            print("p%03d runs %4d cuts %4d hand %4d dk %4d flagged %3d word-flags %2d  %ss"
                  % (s["page"], s["multi_runs"], s["cuts"], s["hand"], s["dk"], s["flagged_runs"],
                     s["word_flags"], s["secs"]), flush=True)
            for k in tot:
                tot[k] += s[k]
    print("TOTAL", json.dumps(tot))


if __name__ == "__main__":
    main()
