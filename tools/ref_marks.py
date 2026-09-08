#!/usr/bin/env python3
"""Dot clusters whose label overstates the ink, recorded per place.

A dot label names how many dots the cluster stands for, and most of the time it is
right. Where it is not, no ink is in the wrong word and nothing needs to move — the
count is simply wrong, so the word is credited with dots the page does not draw.

The pipeline already narrows a label to the blobs it measures, using the fact that the
art draws every dot at 2.38 units and every pair at ~4.55 (see `QSVG_DOTLBL` in
assign_words.py). What survives that is genuinely ambiguous from the ink: on p142
`شَىْءٍۢ` holds a `dot` plus a `three_dots` master with one twin, three blobs called
four, while elsewhere the same master-and-twin shape really does stand for three. Label,
contour count and member count are identical in both cases.

So the residue is written as facts about places, adjudicated, keyed by geometry — the
same way `ref_overrides.py` records ownership and `ref_kinds.py` records identity.

Guards:

  * only words the adjudicator convicted OURS on the DOT evidence — that verdict means
    the spelling and the reference agree with each other and against us;
  * only elements whose best-matching reference piece is `dots`, by IoU rather than
    coverage (a dot lies inside its letter's box, so coverage matches the letter);
  * the reference's own count for that piece is what gets written — never a guess.

    python3 tools/ref_marks.py "<ref>/SVG V1.01" --dry-run
"""

import argparse
import contextlib
import importlib.util
import io
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import refdb                                                            # noqa: E402

PIPE = os.environ.get("QSVG_PIPE", os.path.join(ROOT, "tools", "assign_words.py"))
_spec = importlib.util.spec_from_file_location("assign_words", PIPE)
aw = importlib.util.module_from_spec(_spec)
sys.modules["assign_words"] = aw
_spec.loader.exec_module(aw)

_cap = {}
_orig = aw.rewrite


def _spy(page, a):
    _cap["a"] = a
    return _orig(page, a)


aw.rewrite = _spy
OUT = os.path.join(ROOT, ".cache", "review", "marks.json")
REFDIR = None

# Best-match IoU, never coverage — a dot lies wholly inside its letter's bounding box,
# so a coverage test matches the letter every time.
IOU = 0.35

_NAME = {"dot": "dot", "two dots": "two_dots", "three dots": "three_dots"}


def our_page(pg):
    with contextlib.redirect_stdout(io.StringIO()):
        aw.assign_page("hafs/kfqc", pg, os.path.join(ROOT, ".cache", "words"))
    out = {}
    for w, at in _cap["a"]:
        if not w:
            continue
        els = [e for a in at for e in a["els"]]
        body = [e for e in els if e["kind"] == "body"]
        if not body:
            continue
        out[(w["surah"], w["ayah"], w["pos"])] = {
            "x1": min(e["x1"] for e in body), "x2": max(e["x2"] for e in body),
            "y2": max(e["y2"] for e in body), "text": w["rasm_uthmani"],
            "els": els, "body": body,
            "nseg": max(1, len(aw.segment_word(w["rasm_uthmani"]))),
        }
    return out


def _register(ref, mine):
    xs, ys = [], []
    for k in set(ref) & set(mine):
        r, m = ref[k], mine[k]
        if "body_x1" not in r or r["skel"] != refdb.skeleton(m["text"]):
            continue
        xs.append((m["x1"], r["body_x1"]))
        xs.append((m["x2"], r["body_x2"]))
        if "body_y2" in r:
            ys.append((m["y2"], r["body_y2"]))
    return refdb.register(xs, ys, "words") if xs and ys else None


def _groups(spans, join=0.4):
    if not spans:
        return 0
    spans = sorted(spans)
    n, cur = 1, spans[0][1]
    for a, b in spans[1:]:
        if a <= cur + join:
            cur = max(cur, b)
        else:
            n += 1
            cur = b
    return n


def _iou(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    inter = w * h
    ua = (a[2] - a[0]) * (a[3] - a[1])
    ub = (b[2] - b[0]) * (b[3] - b[1])
    return inter / max(1e-6, ua + ub - inter)


def _best(box, pieces):
    """The reference piece that best occupies the same space: (kind, IoU)."""
    best, bi = None, 0.0
    for kind, _lab, pb in pieces:
        f = _iou(box, pb)
        if f > bi:
            bi, best = f, kind
    return best, bi


def plan_page(job):
    pg, convicted = job
    try:
        rp = refdb.read_page(os.path.join(REFDIR, "%03d.svg" % pg))
        ref = refdb.fold(rp)
        mine = our_page(pg)
        reg = _register(ref, mine)
    except Exception as exc:
        return pg, {}, Counter({"error": 1}), ["%s: %s" % (type(exc).__name__, exc)]
    if reg is None:
        return pg, {}, Counter({"no-registration": 1}), []

    out, stats, notes = {}, Counter(), []
    for k in convicted:
        m, r = mine.get(k), ref.get(k)
        if not m or not r or r["skel"] != refdb.skeleton(m["text"]):
            continue
        for e in m["els"]:
            if e["kind"] == "body" or e.get("mkpart"):
                continue
            if (e.get("mark") or "") not in _NAME.values():
                continue
            box = (reg.x(e["x1"]), reg.y(e["y1"]), reg.x(e["x2"]), reg.y(e["y2"]))
            best, lab, f = None, None, 0.0
            for kind, plab, pb in r["pieces"]:
                v = _iou(box, pb)
                if v > f:
                    f, best, lab = v, kind, plab
            if best != "dots" or f < IOU:
                stats["no dot piece of theirs occupies that ink"] += 1
                continue
            want = _NAME.get(lab)
            if not want or want == e["mark"]:
                stats["already agrees"] += 1
                continue
            out["%.1f,%.1f,%.1f,%.1f" % (e["x1"], e["y1"], e["x2"], e["y2"])] = want
            stats["dot label corrected"] += 1
            if len(notes) < 4:
                notes.append("%s %s  %s -> %s" % ("%d:%d:%d" % k, m["text"],
                                                  e["mark"], want))
    return pg, out, stats, notes


def main(argv=None):
    global REFDIR
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("refdir")
    ap.add_argument("--verdicts", default=os.path.join(ROOT, "docs", "defects",
                                                       "reference_verdicts.json"))
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    REFDIR = args.refdir

    verdicts = json.load(open(args.verdicts, encoding="utf-8"))["verdicts"]
    convicted = defaultdict(set)
    for v in verdicts:
        if v["verdict"] == "OURS" and "dot" in (v.get("why") or ""):
            convicted[v["page"]].add(tuple(int(x) for x in v["key"].split(":")))
    jobs = sorted(convicted.items())
    print("pages with a conviction: %d   words convicted: %d"
          % (len(jobs), sum(len(v) for v in convicted.values())))

    from multiprocessing import Pool
    table, stats, notes = {}, Counter(), []
    with Pool(args.jobs, maxtasksperchild=6) as pool:
        for pg, per, st, nt in pool.imap_unordered(plan_page, jobs):
            stats.update(st)
            if per:
                table[str(pg)] = per
            notes += [("p%d " % pg) + n for n in nt[:2]]

    for k, v in stats.most_common():
        print("   %-52s %5d" % (k, v))
    print("\nsample:")
    for n in notes[:20]:
        print("   " + n)
    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(table, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print("\nwrote %s — %d pages, %d elements"
          % (args.out, len(table), sum(len(v) for v in table.values())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
