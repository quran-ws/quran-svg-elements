#!/usr/bin/env python3
"""Apply the letter cuts and regroup every word as letters.

    python3 tools/emit_letters.py 1 604 --jobs 32     # → .cache/letters-svg/hafs-kfqc/NNN.svg
    python3 tools/emit_letters.py 50

Reads the word-level page (.cache/words-svg) and the cut record
(.cache/letters/cuts/NNN.json). Inside each <g class="word"> the ligature wrappers
are dropped and replaced by one <g class="letter"> per letter of the text, holding
the letter's body ink (a run's main contour cut by letters_lib.cut_run, every other
contour verbatim) and its own marks; word-level marks (waqf signs, hizb…) stay direct
children of the word. Everything outside word groups is copied byte for byte, and so
is every path that is not a cut piece — contour conservation still proves them.

A run whose record carries a blocking flag is emitted UNSPLIT: one letter group with
data-text of the whole run and data-unsplit="1" — an honest gap, never a guess.
"""
import argparse
import json
import os
import sys
import time

import numpy as np
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import letters_lib as L          # noqa: E402
from tools.build_letter_cuts import align_runs   # noqa: E402

SOFT_FLAGS = ("hand-cut-unmapped", "anchor-forced")     # side-disagreement blocks: a wrong split is worse than none
# how emitted mark labels map onto the letter expectation's families
_FAMILY = {"fathatan": "fatha", "dammatan": "damma", "kasratan": "kasra",
           "sifr-mustadir": "sifr-mustadir", "sifr-mustatil": "sifr-mustatil"}
_DOTS = ("dot", "two-dots", "three-dots")


def _family(label):
    return _FAMILY.get(label, label)


def _is_word_level(label):
    return label is None or any(label.startswith(p) for p in L.WORD_LEVEL) or label in ("sajdah",)


def _bbox_centre(d):
    x0, y0, x1, y1 = L.bbox(L.flatten(d))
    return ((x0 + x1) / 2, (y0 + y1) / 2)


def assign_marks(letters, letter_polys, marks):
    """Give every mark path to a letter. Returns (per-letter lists of mark records,
    word-level mark records, notes). Every (mark, letter) pair whose family fits an
    open slot of the letter's expectation is a candidate scored by the distance from
    the mark's centre to the letter's body outline; pairs are taken nearest first,
    each mark and each slot once. A mark no slot fits goes to the nearest letter
    (noted). A bare ء (no body) takes the hamza mark nearest to where it should be:
    between its neighbours' ink."""
    per = [[] for _ in letters]
    word_level, notes = [], []
    slots = []
    for l in letters:
        want = [_family(m) for m in l["marks"]]
        if l["dots"]:
            want.append(l["dots"])
        slots.append(want)
    # a mark-only letter is placed between its neighbours for distance purposes
    anchors = []
    for k, polys in enumerate(letter_polys):
        if polys:
            anchors.append(polys)
            continue
        near = [letter_polys[j] for j in (k - 1, k + 1) if 0 <= j < len(letters) and letter_polys[j]]
        anchors.append([q for pl in near for q in pl])
    centres = {}
    pending = []
    for i, m in enumerate(marks):
        label = m["mark"]
        if _is_word_level(label):
            word_level.append(m)
            continue
        centres[i] = _bbox_centre(m["d"])
        pending.append(i)
    pairs = []
    for i in pending:
        fam = _family((marks[i]["mark"] or "").split("+")[0])
        for k in range(len(letters)):
            if not anchors[k]:
                continue
            if fam in slots[k]:                      # dots must match exactly: two-dots is not dot
                pairs.append((L.point_poly_dist(centres[i], anchors[k]), i, k))
    pairs.sort()
    taken = set()
    for dd, i, k in pairs:
        if i in taken:
            continue
        fam = _family((marks[i]["mark"] or "").split("+")[0])
        if fam not in slots[k]:
            continue
        slots[k].remove(fam)
        per[k].append(marks[i])
        taken.add(i)
        if dd > 8.0:
            notes.append("mark-far:%s:%d:%.1f" % (marks[i]["mark"], k, dd))
    for i in pending:
        if i in taken:
            continue
        cands = [(L.point_poly_dist(centres[i], anchors[k]), k) for k in range(len(letters)) if anchors[k]]
        if not cands:
            word_level.append(marks[i])
            continue
        dd, k = min(cands)
        per[k].append(marks[i])
        notes.append("mark-unslotted:%s:%d:%.1f" % (marks[i]["mark"], k, dd))
    return per, word_level, notes


def _piece_path(main, d, k, n):
    """A cut piece as a <path>: the main path's attributes, new d, eid suffixed."""
    at = dict(main["attrs"])
    at["d"] = d
    if "data-eid" in at:
        at["data-eid"] = "%s-%d" % (at["data-eid"], k)
    at.pop("data-sig", None)                 # the signature named the whole contour
    at["data-cut"] = "1"
    return "<path " + " ".join('%s="%s"' % (a, v) for a, v in at.items()) + "/>"


_MODEL = None
_MODEL_PATH = None


def _model_pieces(main, bodies, idx, cuts, on_main, letters=None):
    """Recompute the label map with the model (deterministic) and cut by ownership."""
    global _MODEL
    from tools import letter_model as LM
    if _MODEL is None:
        import torch
        torch.set_num_threads(1)
        _MODEL = LM.load_model(_MODEL_PATH)
    rp = [poly for p in bodies for poly in L.flatten(p["d"])]
    labels, meta = LM.label_run_with_model(_MODEL, rp, len(idx), letters=letters)
    if labels is None:
        raise L.CutError("model has no labels")
    z, x0, y0 = meta["z"], meta["x0"], meta["y0"]
    main_polys = L.flatten(main["d"])
    mm = L.raster(main_polys, x0, y0, meta["shape"][1] / z, meta["shape"][0] / z, z)
    main_mask = np.zeros(meta["shape"], dtype=bool)
    main_mask[:mm.shape[0], :mm.shape[1]] = mm[:meta["shape"][0], :meta["shape"][1]]
    masks = [meta["masks"][k] & main_mask for k in on_main]
    return L.cut_run_masks(main["d"], masks, [c.get("polys", []) for c in cuts], (x0, y0, z))


def emit_word(word, wrec):
    """The new inner text of a word group, and notes."""
    notes = []
    letters, runs = align_runs(word) if not (wrec or {}).get("flags") else (None, None)
    if letters is None or runs is None:
        return None, ["word-unsplit"]
    n = len(letters)
    groups = [[] for _ in range(n)]          # path texts per letter
    polys = [[] for _ in range(n)]           # body outlines per letter (for marks)
    src = ["none"] * n
    conf = [1.0] * n
    unsplit = {}                             # run index → letter indices it covers
    used = set()
    run_recs = {tuple(r["letters"]): r for r in (wrec or {}).get("runs", [])}
    for ri, (lig, idx) in enumerate(runs):
        rec = run_recs.get(tuple(idx))
        bodies = [p for p in lig["paths"] if p["kind"] == "body"]
        if len(idx) == 1:
            for p in bodies:
                groups[idx[0]].append(p["raw"])
                polys[idx[0]] += L.flatten(p["d"])
                used.add(id(p))
            continue
        blocking = [f for f in (rec or {}).get("flags", ["no-record"]) if not f.startswith(SOFT_FLAGS)]
        cuts = (rec or {}).get("cuts", [])
        on_main = (rec or {}).get("main_letters", list(range(len(idx))))
        if rec is None or blocking or len(cuts) != len(on_main) - 1:
            unsplit[ri] = idx
            for p in bodies:
                groups[idx[0]].append(p["raw"])
                polys[idx[0]] += L.flatten(p["d"])
                used.add(id(p))
            notes.append("run-unsplit:%s:%s" % (lig["text"], ",".join(blocking) or "incomplete"))
            continue
        main = next(p for p in bodies if p["eid"] == rec["main"])
        anchors = rec.get("anchors") or [[tuple(r)] if r else [] for r in rec.get("refs", [])]
        refs = [anchors[k] for k in on_main]
        try:
            if rec.get("mode") == "model":
                pieces = _model_pieces(main, bodies, idx, cuts, on_main, letters=[letters[i]["ch"] for i in idx])
            else:
                pieces = L.cut_run(main["d"], [c.get("polys", [c["poly"]]) for c in cuts], refs=refs)
        except L.CutError as e:
            unsplit[ri] = idx
            for p in bodies:
                groups[idx[0]].append(p["raw"])
                polys[idx[0]] += L.flatten(p["d"])
                used.add(id(p))
            notes.append("run-unsplit:%s:cut-failed:%s" % (lig["text"], e.why))
            continue
        for k, (mi, d) in enumerate(zip(on_main, pieces)):
            li = idx[mi]
            groups[li].append(_piece_path(main, d, k, len(idx)))
            polys[li] += L.flatten(d)
        used.add(id(main))
        for p in bodies:
            if p is main:
                continue
            li = idx[min(len(idx) - 1, int(rec.get("extra", {}).get(p["eid"], 0)))]
            groups[li].append(p["raw"])
            polys[li] += L.flatten(p["d"])
            used.add(id(p))
        for k, li in enumerate(idx):
            around = [c for c in cuts if c["after"] in (k - 1, k)]
            src[li] = "+".join(sorted({c["src"] for c in around})) if around else "none"
            conf[li] = min([c.get("conf", 1.0) for c in around] or [1.0])
    marks = [p for p in word["paths"] if p["kind"] == "mark"]
    per, word_level, mnotes = assign_marks(letters, polys, marks)
    notes += mnotes
    for p in marks:
        used.add(id(p))
    leftovers = [p for p in word["paths"] if id(p) not in used]
    out = []
    ri_of = {}
    for ri, (lig, idx) in enumerate(runs):
        for li in idx:
            ri_of[li] = ri
    skip = set()
    for li, l in enumerate(letters):
        if li in skip:
            continue
        ri = ri_of.get(li)
        if ri in unsplit:
            span = unsplit[ri]
            text = "".join(letters[j].get("src", letters[j]["ch"]) for j in span)
            out.append('<g class="letter" data-text="%s" data-index="%d" data-run="%d" data-unsplit="1">'
                       % (text, span[0], ri))
            for j in span:
                out += groups[j]
                out += [m["raw"] for m in per[j]]
                skip.add(j)
            out.append("</g>")
            continue
        out.append('<g class="letter" data-text="%s" data-index="%d" data-run="%s" data-src="%s" data-conf="%.2f">'
                   % (l.get("src", l["ch"]), li, "" if ri is None else ri, src[li], conf[li]))
        out += groups[li]
        out += [m["raw"] for m in per[li]]
        out.append("</g>")
    out += [m["raw"] for m in word_level]
    out += [p["raw"] for p in leftovers]
    if leftovers:
        notes.append("leftover-paths:%d" % len(leftovers))
    return "".join(out), notes


def emit_page(page, out_dir=L.LETTERS_SVG):
    words, s = L.read_words(page)
    cuts_path = os.path.join(L.CUTS_DIR, "%03d.json" % page)
    rec = json.load(open(cuts_path, encoding="utf-8")) if os.path.exists(cuts_path) else {"words": {}}
    global _MODEL_PATH
    _MODEL_PATH = rec.get("model")
    pieces = []
    pos = 0
    notes = {}
    for w in sorted(words, key=lambda w: w["span"][0]):
        a, b = w["span"]
        pieces.append(s[pos:a])
        inner, wn = emit_word(w, rec["words"].get(w["wid"]))
        if inner is None:
            pieces.append(s[a:b])                          # untouched
        else:
            pieces.append(w["open"] + inner + "</g>")
        if wn:
            notes[w["wid"]] = wn
        pos = b
    pieces.append(s[pos:])
    text = "".join(pieces).replace('data-decomposition="word"', 'data-decomposition="letter"', 1)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "%03d.svg" % page), "w", encoding="utf-8") as f:
        f.write(text)
    with open(os.path.join(out_dir, "%03d.notes.json" % page), "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False)
    return notes


def _one(page):
    t = time.time()
    notes = emit_page(page)
    unsplit = sum(1 for v in notes.values() for x in v if x.startswith(("run-unsplit", "word-unsplit")))
    marks = sum(1 for v in notes.values() for x in v if x.startswith("mark-"))
    return page, unsplit, marks, round(time.time() - t, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("first", type=int)
    ap.add_argument("last", type=int, nargs="?")
    ap.add_argument("--jobs", type=int, default=32)
    a = ap.parse_args()
    pages = range(a.first, (a.last or a.first) + 1)
    tu = tm = 0
    with ProcessPoolExecutor(min(a.jobs, len(pages))) as ex:
        for page, unsplit, marks, secs in ex.map(_one, pages):
            print("p%03d unsplit-runs %3d mark-notes %3d  %ss" % (page, unsplit, marks, secs), flush=True)
            tu += unsplit
            tm += marks
    print("TOTAL unsplit-runs %d mark-notes %d" % (tu, tm))


if __name__ == "__main__":
    main()
