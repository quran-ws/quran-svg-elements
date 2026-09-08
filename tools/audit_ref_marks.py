#!/usr/bin/env python3
"""Does a mark flag mean the pipeline is wrong, or that the text budget is?

`audit_marks.py` counts each mark family in a word's ink and compares it with the
count implied by the word's `text_uthmani` from quran.com. A mismatch is reported as a
defect. That is only sound if the printed page and the text edition agree about what is
drawn — and on waqf signs they demonstrably do not. The KFGQPC artwork draws a `ۚ`
after `بَلَىٰ` on p12 that quran.com's word text does not carry at all, and carries a
`ۙ` on `رِّزْقًۭا` (p5) that the artwork does not draw. Both are reported as pipeline
defects. Neither is one.

So each flag is put to a three-way vote between the text budget, our ink, and the
reference's ink:

  TEXT-ODD    we and the reference partition the same ink the same way, and only the
              text budget disagrees. Not a defect — an audit artefact.
  OURS        the reference holds ink in this word that we gave to another word, or
              the reverse. A real defect, and the reference says where the ink goes.
  UNCLEAR     all three differ, or the word cannot be compared.

The comparison is by GEOMETRY, never by label. The two sources name marks differently
(they write one `successive tanwin_al_fath` where we write two `tanwin_al_fath` strokes, they fuse
the iqlab meem into `fathah iqlab`), and any mapping between the two vocabularies would
manufacture disagreements out of naming. Positions cannot be argued with: registration
lands the two frames within 0.01 of a unit, so a mark either sits inside the same word
in both decompositions or it does not.

    python3 tools/audit_ref_marks.py "<ref>/SVG V1.01" [--jobs N] [--out F]
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
SWEEP = os.environ.get("QSVG_SWEEPS", os.path.join(ROOT, ".cache", "sweeps")) + "/baseline/pages"

# Two marks are "the same ink" when their boxes overlap, grown by this much first — the
# two sources trace the same stroke to within a hundredth of a unit, so the pad only has
# to cover a stroke that one side ends where the other begins.
PAD = 0.3

MARK_KINDS = ("diacritic", "dots", "waqf")


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
            "y1": min(e["y1"] for e in body), "y2": max(e["y2"] for e in body),
            "text": w["rasm_uthmani"],
            "marks": [e for e in els if e["kind"] != "body"],
        }
    return out


def _boxes_ours(rec, reg):
    return [(reg.x(e["x1"]), reg.y(e["y1"]), reg.x(e["x2"]), reg.y(e["y2"]),
             e.get("mark") or "?") for e in rec["marks"]]


def _boxes_ref(rec):
    return [(b[0], b[1], b[2], b[3], lab or kind)
            for kind, lab, b in rec["pieces"] if kind in MARK_KINDS]


def _overlap(p, q):
    return (min(p[2], q[2]) >= max(p[0], q[0]) - PAD
            and min(p[3], q[3]) >= max(p[1], q[1]) - PAD)


def _pair(a, b):
    """Which marks on each side have no counterpart on the other.

    Deliberately NOT a one-to-one pairing. The two sources cut the same ink into
    different numbers of pieces — the pair of strokes we call two `tanwin_al_fath` is one path
    they call `successive tanwin_al_fath`, and the iqlab meem they fuse into `fathah iqlab` we
    carry separately. Insisting on a bijection reports that difference in draughtsmanship
    as stolen ink: it turned 2:25:18, where every one of the seven marks lines up to a
    hundredth of a unit, into a defect. What matters is whether each mark has ANY
    counterpart in the same word on the other side.
    """
    only_a = [t for t in a if not any(_overlap(t, u) for u in b)]
    only_b = [t for t in b if not any(_overlap(t, u) for u in a)]
    return len(a) - len(only_a), only_a, only_b


def scan(pg):
    """Vote on every mark flag of one page."""
    swp = os.path.join(SWEEP, "%03d.json" % pg)
    if not os.path.exists(swp):
        return pg, {"skip": "no sweep record"}
    flags = []
    for w in json.load(open(swp, encoding="utf-8")).get("marks", []):
        for b in w["bad"]:
            if b[0] in ("rtl-order", "error"):
                continue
            flags.append((w["key"], w["word"], b[0], b[1], b[2]))
    if not flags:
        return pg, {"votes": Counter(), "rows": []}
    try:
        rp = refdb.read_page(os.path.join(REFDIR, "%03d.svg" % pg))
        ref = refdb.fold(rp)
        mine = our_page(pg)
        reg = _register(ref, mine)
    except Exception as exc:
        return pg, {"err": "%s: %s" % (type(exc).__name__, exc)}
    if reg is None:
        return pg, {"skip": "no registration"}

    votes = Counter()
    rows = []
    for key, word, fam, have, want in flags:
        k = tuple(int(x) for x in key.split(":"))
        r, m = ref.get(k), mine.get(k)
        if not r or not m or refdb.skeleton(r["hafs"]) != refdb.skeleton(m["text"]):
            votes["UNCLEAR"] += 1
            rows.append({"page": pg, "key": key, "word": word, "family": fam,
                         "have": have, "want": want, "vote": "UNCLEAR",
                         "why": "the two sources do not agree this is the same word"})
            continue
        matched, only_ours, only_ref = _pair(_boxes_ours(m, reg), _boxes_ref(r))
        if not only_ours and not only_ref:
            v, why = "TEXT-ODD", "both decompositions hold exactly the same %d marks" % matched
        else:
            v, why = "OURS", ("we hold %d mark(s) the reference puts elsewhere, and lack %d "
                              "it puts here" % (len(only_ours), len(only_ref)))
        votes[v] += 1
        rows.append({"page": pg, "key": key, "word": word, "family": fam,
                     "have": have, "want": want, "vote": v, "why": why,
                     "matched": matched,
                     "only_ours": [[round(t[0], 1), round(t[1], 1), t[4]] for t in only_ours],
                     "only_ref": [[round(t[0], 1), round(t[1], 1), t[4]] for t in only_ref]})
    return pg, {"votes": votes, "rows": rows}


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


def main(argv=None):
    global REFDIR
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("refdir")
    ap.add_argument("first", nargs="?", type=int, default=1)
    ap.add_argument("last", nargs="?", type=int, default=604)
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "defects", "mark_votes.json"))
    args = ap.parse_args(argv)
    REFDIR = args.refdir

    from multiprocessing import Pool
    votes, rows, bad = Counter(), [], []
    with Pool(args.jobs, maxtasksperchild=6) as pool:
        for pg, r in pool.imap_unordered(scan, range(args.first, args.last + 1)):
            if "err" in r or "skip" in r:
                bad.append((pg, r.get("err") or r["skip"]))
                continue
            votes.update(r["votes"])
            rows += r["rows"]

    n = max(1, sum(votes.values()))
    print("mark flags voted on: %d   (pages not compared: %d)" % (n, len(bad)))
    for k in ("TEXT-ODD", "OURS", "UNCLEAR"):
        print("   %-10s %5d  (%.1f%%)" % (k, votes[k], 100.0 * votes[k] / n))

    per = defaultdict(Counter)
    for r in rows:
        per[r["family"]][r["vote"]] += 1
    print("\n%-12s %7s %8s %7s %9s   %s" % ("family", "flags", "TEXT-ODD", "OURS", "UNCLEAR", "real share"))
    for fam in sorted(per, key=lambda f: -sum(per[f].values())):
        c = per[fam]
        t = sum(c.values())
        print("%-12s %7d %8d %7d %9d   %.0f%%"
              % (fam, t, c["TEXT-ODD"], c["OURS"], c["UNCLEAR"], 100.0 * c["OURS"] / t))
    real = [r for r in rows if r["vote"] == "OURS"]
    print("\nREAL defects: %d, on %d pages" % (real and len(real) or 0,
                                               len({r["page"] for r in real})))
    print("worst pages: %s" % ", ".join(
        "p%d(%d)" % t for t in Counter(r["page"] for r in real).most_common(10)))
    print("\nsample:")
    for r in real[:12]:
        print("   p%-4d %-11s %-16s %-11s have %s want %s  %s"
              % (r["page"], r["key"], r["word"], r["family"], r["have"], r["want"], r["why"]))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"votes": dict(votes),
                   "per_family": {k: dict(v) for k, v in per.items()},
                   "rows": rows, "not_compared": bad}, fh, ensure_ascii=False, indent=1)
    print("\nwrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
