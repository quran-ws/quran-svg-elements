#!/usr/bin/env python3
"""What does MushafDatabase call each of our shapes? Evidence, per signature.

Every path we emit carries a `data-sig` outline hash, and `.cache/marks/labels.json`
maps a signature to one label applied mushaf-wide. That is enormous leverage in both
directions: one right answer fixes every occurrence, one wrong answer costs hundreds of
flags at once (`letter-hamza` -> `hamza`, one entry, +527 flags).

The reference names every path it draws — 25 diacritics, three dot counts, five waqf
signs, and the special elements. Registration puts our ink and theirs in the same frame
to a hundredth of a unit, so for each occurrence of one of our signatures we can read
off what they call that exact ink. Over the whole mushaf a signature is then not a
judgement call but a tally: 412 occurrences, 99.8% of them called `waqf jaiz`.

This writes evidence, not labels. Nothing is applied. `tools/apply_labels.py` folds an
answer in, and `scratchpad/label_bisect.py` measures it first — a label change is never
adopted on the strength of the tally alone.

What it is for, concretely: our pipeline collapses every pause sign to one label
`pause`, so a `ۚ` (ج) and a `ۗ` (قلى) come out indistinguishable. They cannot be told
apart from the text either — quran.com's uthmani text and this print disagree about the
waqf sign at 424 of 4,416 positions (9.6%), including 87 where the text says قلى and the
page draws ج. The shapes, however, are distinct outlines, so the signature tally settles
them from the ink.

    python3 tools/sig_labels_from_ref.py "<ref>/SVG V1.01" --jobs 6
    python3 tools/sig_labels_from_ref.py "<ref>/SVG V1.01" 1 120 --only pause
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

REFDIR = None
# Our element and their path are the same ink at this IoU. Their vectorisation splits
# and joins differently from ours, so this is loose — but IoU already excludes a piece
# that merely contains ours.
OVERLAP = 0.35


def our_page(pg):
    with contextlib.redirect_stdout(io.StringIO()):
        aw.assign_page("hafs/kfqc", pg, os.path.join(ROOT, ".cache", "words"))
    words, els = {}, []
    for w, at in _cap["a"]:
        if not w:
            continue
        ee = [e for a in at for e in a["els"]]
        body = [e for e in ee if e["kind"] == "body"]
        if not body:
            continue
        k = (w["surah"], w["ayah"], w["pos"])
        words[k] = {"x1": min(e["x1"] for e in body), "x2": max(e["x2"] for e in body),
                    "y2": max(e["y2"] for e in body), "text": w["uthmani"]}
        els += [e for e in ee if e.get("sig")]
    return words, els


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


def _frac(a, b):
    """Intersection over UNION.

    Not intersection-over-the-smaller, which was the first attempt and is useless here:
    a dot lies wholly inside its letter's bounding box, so that measure scores the
    letter a perfect 1.0 and the dot ties with it. Every dot signature came back around
    50% pure with `text/من`, `text/لذ` and other ligatures as the runners-up — an
    artefact of the test, not a real ambiguity. IoU charges for the letter's unused
    area, so the piece that actually occupies the same space wins.
    """
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    inter = w * h
    ua = (a[2] - a[0]) * (a[3] - a[1])
    ub = (b[2] - b[0]) * (b[3] - b[1])
    return inter / max(1e-6, ua + ub - inter)


def scan(pg):
    try:
        rp = refdb.read_page(os.path.join(REFDIR, "%03d.svg" % pg))
        ref = refdb.fold(rp)
        mine, els = our_page(pg)
        reg = _register(ref, mine)
    except Exception as exc:
        return pg, None, "%s: %s" % (type(exc).__name__, exc)
    if reg is None:
        return pg, None, "no registration"
    pieces = [(kind, lab, b) for r in ref.values() for kind, lab, b in r["pieces"]]
    out = Counter()
    for e in els:
        box = (reg.x(e["x1"]), reg.y(e["y1"]), reg.x(e["x2"]), reg.y(e["y2"]))
        best, bf = None, OVERLAP
        for kind, lab, pb in pieces:
            f = _frac(box, pb)
            if f > bf:
                bf, best = f, (kind, lab)
        if best is None:
            out[(e["sig"], e.get("mark") or e.get("lab") or "", "(nothing there)", "")] += 1
        else:
            out[(e["sig"], e.get("mark") or e.get("lab") or "", best[0], best[1])] += 1
    return pg, out, None


def main(argv=None):
    global REFDIR
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("refdir")
    ap.add_argument("first", nargs="?", type=int, default=1)
    ap.add_argument("last", nargs="?", type=int, default=604)
    ap.add_argument("--pages", help="comma-separated page numbers instead of a range. "
                                    "The rare signs need this: waqf lazim is drawn 21 "
                                    "times in the whole mushaf and the muʿānaqah 6, so a "
                                    "sample of consecutive pages will not contain them.")
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--only", help="report only signatures we currently call this")
    ap.add_argument("--min", type=int, default=3, help="ignore signatures seen fewer times")
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "defects", "sig_ref_labels.json"))
    args = ap.parse_args(argv)
    REFDIR = args.refdir

    todo = ([int(x) for x in args.pages.split(",")] if args.pages
            else list(range(args.first, args.last + 1)))
    from multiprocessing import Pool
    tally = Counter()
    bad = []
    with Pool(args.jobs, maxtasksperchild=6) as pool:
        for pg, out, err in pool.imap_unordered(scan, todo):
            if err:
                bad.append((pg, err))
                continue
            tally.update(out)

    per = defaultdict(Counter)
    ourname = {}
    for (sig, mine, kind, lab), n in tally.items():
        per[sig][(kind, lab)] += n
        ourname[sig] = ourname.get(sig) or mine
    print("pages scanned %d (failed %d)   signatures seen %d"
          % (len(todo) - len(bad), len(bad), len(per)))

    rows = []
    for sig, c in per.items():
        tot = sum(c.values())
        if tot < args.min:
            continue
        (kind, lab), n = c.most_common(1)[0]
        rows.append({"sig": sig, "ours": ourname[sig], "n": tot,
                     "ref_kind": kind, "ref_label": lab,
                     "purity": round(n / tot, 4),
                     "alts": [["%s/%s" % k2, v2] for k2, v2 in c.most_common()[1:4]]})
    rows.sort(key=lambda r: -r["n"])
    if args.only:
        rows = [r for r in rows if r["ours"] == args.only]

    print("\n%-18s %-13s %6s %-11s %-20s %7s" %
          ("signature", "we call it", "n", "ref kind", "ref label", "purity"))
    for r in rows[:60]:
        print("%-18s %-13s %6d %-11s %-20s %6.1f%%"
              % (r["sig"][:16], r["ours"], r["n"], r["ref_kind"], r["ref_label"],
                 100 * r["purity"]))

    print("\nsignatures we collapse that the reference splits:")
    byours = defaultdict(Counter)
    for r in rows:
        byours[r["ours"]][r["ref_label"]] += r["n"]
    for ours in sorted(byours, key=lambda o: -len(byours[o])):
        if len(byours[ours]) > 1:
            print("   %-13s -> %s" % (ours, ", ".join("%s(%d)" % t for t in byours[ours].most_common())))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"rows": rows, "failed": bad}, fh, ensure_ascii=False, indent=1)
    print("\nwrote %s (%d signatures)" % (args.out, len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
