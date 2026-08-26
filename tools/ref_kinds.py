#!/usr/bin/env python3
"""Ink we hold in the right word but call a mark, where it is a letter.

`ref_overrides.py` fixes ownership: this piece of ink belongs to that word. There is a
second kind of defect it cannot touch, because nothing needs to move — the ink is
already in the right word, and only its *identity* is wrong. A letter read as a mark
drops out of the word's letter extent, so the word measures short of its share of the
line and the width audit convicts it, while every piece of ink is exactly where it
belongs.

Two families found this way:

  * the `ه` of a pronominal suffix. `يَدَهُۥ` (p164) reads it as a `damma`, `بَعْدِهِۦ`
    (p71) as a `pause`. The `ۥ` is recovered correctly in both — it is the `ه` in front
    of it that is lost. Only 8 of 2,160 suffix words are affected, so this is a tail,
    not a rule: writing a general rule to catch 8 would put the other 2,152 at risk.
  * `ذَٰلِكَ`, whose `ذ` reads as an iqlab meem. That one *did* generalise — text says no
    iqlab, geometry says baseline — and is handled in the pipeline.

The rest are per-occurrence facts, and this writes them the way this project writes
facts: adjudicated, keyed by geometry, as data.

Three guards, all necessary:

  * only words the adjudicator convicted OURS — never on the reference's say-so alone;
  * only where the reference calls that exact ink `text`, covering most of it;
  * only words already SHORT of letter pieces by the Arabic joining rules, so a mark can
    never be promoted into a word that has all the letters its spelling allows.

    python3 tools/ref_kinds.py "<ref>/SVG V1.01" --dry-run
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
OUT = os.path.join(ROOT, ".cache", "review", "kinds.json")
REFDIR = None

# Our element and a reference piece are the same ink at this IoU. NOT "how much of our
# box the reference's letters cover" — that was the first attempt and it is the same
# trap that made the label evidence useless: a diacritic lies wholly inside its letter's
# bounding box, so coverage scores it a perfect 1.0 and every shadda, sukun and kasra
# came out a letter. IoU charges for the letter's unused area, so only ink that actually
# occupies the same space matches.
IOU = 0.35

# What each mark family is spelled with. A mark the word's own text still calls for is
# never promoted to a letter, however much the reference's letter ink overlaps it: on
# p222 `مَّعْدُودَةٍۢ` had its kasratan promoted and was left with none, which also broke
# the reading order of the word beside it — two new flags from one entry, the only page
# in the run to worsen by more than one.
_WANT = {
    "fatha": ("َ",), "kasra": ("ِ",), "damma": ("ُ",),
    "fathatan": ("ً", "ࣰ"), "kasratan": ("ٍ", "ࣲ"), "dammatan": ("ٌ", "ࣱ"),
    "sukun": ("ْ", "ۡ"), "shadda": ("ّ",), "maddah": ("ٓ", "ۤ"),
    "small-alef": ("ٰ",), "wasla": ("ٱ",), "small-waw": ("ۥ",),
    "small-ya": ("ۦ", "ۧ"), "small-circle": ("۟", "۠"),
    "hamza": ("أ", "إ", "ؤ", "ئ", "ٔ", "ٕ"),
    "small-noon": ("ۨ",),
}
# `meem-iqlab` is deliberately absent. This art fuses the iqlab meem into the tanween
# glyph — a measured finding of this project, which is why audit_marks.py's budget has
# no such family and never demands one. Listing it here made the guard reason that a
# word spelling `ۢ` still needs its `meem-iqlab` element, and so refused to correct the
# very defect this tool exists for: in `قَوْمٍۭ` (p93) the reference has `text م` at
# 253.34..261.58 — the meem of قوم, a letter — where we have a `meem-iqlab` mark at
# 253.33..261.56, the same ink to a hundredth of a unit. Same in `شَىْءٍۢ`, where it is
# the `ء`. The tanween itself is present either way; what was lost was the letter.


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
            "y2": max(e["y2"] for e in body), "text": w["uthmani"],
            "els": els, "body": body,
            "nseg": max(1, len(aw.segment_word(w["uthmani"]))),
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
        have = _groups([(e["x1"], e["x2"]) for e in m["body"]])
        if have >= m["nseg"]:
            stats["word already has every letter its spelling allows"] += 1
            continue
        if not any(p[0] == "text" for p in r["pieces"]):
            continue
        for e in m["els"]:
            if e["kind"] == "body" or e.get("mkpart"):
                continue
            box = (reg.x(e["x1"]), reg.y(e["y1"]), reg.x(e["x2"]), reg.y(e["y2"]))
            kind, f = _best(box, r["pieces"])
            if kind != "text" or f < IOU:
                continue
            _fam = e.get("mark")
            _chars = _WANT.get(_fam)
            if _chars:
                _txt = m["text"]
                _need = sum(_txt.count(c) for c in _chars)
                _held = sum(1 for x in m["els"]
                            if x.get("mark") == _fam and not x.get("mkpart"))
                if _held <= _need:
                    stats["the word's spelling still needs that mark"] += 1
                    continue
            out["%.1f,%.1f,%.1f,%.1f" % (e["x1"], e["y1"], e["x2"], e["y2"])] = "body"
            stats["mark promoted to letter"] += 1
            if len(notes) < 4:
                notes.append("%s %s read as %s" % ("%d:%d:%d" % k, m["text"],
                                                   e.get("mark") or "?"))
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
        if v["verdict"] == "OURS":
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
