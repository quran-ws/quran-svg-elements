#!/usr/bin/env python3
"""When we and MushafDatabase disagree about a word, decide which of us is wrong.

A disagreement is not a defect. The reference is an independent decomposition, not
ground truth: the last time our line placement was checked against it, of fifteen real
disagreements only four were ours. Counting raw disagreements as our error rate
therefore overstates it by roughly three times, and — worse — points repair work at
words that are already correct.

So every disagreement is put to a third source that has seen neither decomposition:

  WIDTH   `.cache/qcf_widths.json` holds the QCF v2 advance width of all 77,376 words,
          derived from the font metrics and the spelling. Share out a line's drawn ink
          in proportion to those widths and every word has an expected size that owes
          nothing to either party's geometry. Whoever's measured width is closer to it
          is holding the right amount of ink.

  PIECES  `assign_words.segment_word()` applies the Arabic joining rules to the
          spelling and returns how many connected letter groups the word can possibly
          be drawn in. Fewer is normal — the art joins letters the rules allow to
          separate — but MORE is impossible, so a side drawing more pieces than the
          spelling permits is provably holding ink that is not its own. This is a
          one-sided test and only ever convicts.

  DOTS    the letter dots a word's spelling owns. A dot that drifted to a neighbour
          moves no letter, so it changes neither word's width and neither of the tests
          above can see it. Whichever side matches the budget is holding the right dots.

Verdicts: OURS (we are wrong), THEIRS (the reference is wrong), UNCLEAR (the third
source does not separate them). Only OURS is work.

    python3 tools/adjudicate_ref.py                       # reads docs/defects/reference_words.json
    python3 tools/adjudicate_ref.py --flags F --out G --jobs 8
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

QCF = json.load(open(os.path.join(ROOT, ".cache", "qcf_widths.json"), encoding="utf-8"))
REFDIR = None

# A verdict is only recorded when the third source separates the two sides by a real
# margin. Below these the disagreement stands unresolved rather than being guessed at.
MARGIN_ABS = 1.5        # reference units of width error
MARGIN_REL = 0.25       # and a quarter of the better side's error

_DOTU = {"dot": 1, "two_dots": 2, "three_dots": 3, "two dots": 2, "three dots": 3}


def _dot_budget(txt):
    """Dot units the word's letters own — the rule audit_marks.dot_want uses."""
    raw = aw._LETTER.findall(txt)
    sk = [(aw.HAMZAH_MAP[c][0] if c in aw.HAMZAH_MAP else c, c in aw.HAMZAH_MAP) for c in raw]
    n = 0
    for i, (ch, seat) in enumerate(sk):
        if seat or ch not in aw.DOTS:
            continue
        if ch == "\u064a" and (i == len(sk) - 1
                                or (i + 1 < len(sk) and sk[i + 1][0] == "\u0621")):
            continue
        n += _DOTU.get(aw.DOTS[ch][0], 0)
    return n


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
        lns = [e.get("line") for e in body if e.get("line")]
        # A piece is a connected letter group. A stroke drawn on top of a wider sibling
        # is part of it, not another piece — the same rule audit_marks.py uses.
        eff = []
        for b in body:
            wb = b["x2"] - b["x1"]
            if not any(o is not b
                       and min(o["x2"], b["x2"]) - max(o["x1"], b["x1"]) >= 0.6 * wb
                       and (o["x2"] - o["x1"]) > wb for o in body):
                eff.append(b)
        out[(w["surah"], w["ayah"], w["pos"])] = {
            "line": max(set(lns), key=lns.count) if lns else 0,
            "x1": min(e["x1"] for e in body), "x2": max(e["x2"] for e in body),
            "y1": min(e["y1"] for e in body), "y2": max(e["y2"] for e in body),
            "pieces": len(eff), "text": w["rasm_uthmani"], "qpc": w.get("qpc") or "",
            "dots": sum(_DOTU.get(e.get("mark") or "", 0)
                        for e in els if not e.get("mkpart")),
            "nseg": max(1, len(aw.segment_word(w["rasm_uthmani"]))),
        }
    return out


def register_from_words(ref, mine):
    """The same word-landmark frame `audit_ref_words.py` fits, for the same reasons.

    Not the ayah medallions: their data is broken on a handful of pages and a page
    registered on them alone comes out shifted by most of its width.
    """
    xs, ys = [], []
    for k in set(ref) & set(mine):
        r, m = ref[k], mine[k]
        if "body_x1" not in r or r["skel"] != refdb.skeleton(m["text"]):
            continue
        xs.append((m["x1"], r["body_x1"]))
        xs.append((m["x2"], r["body_x2"]))
        if "body_y2" in r:
            ys.append((m["y2"], r["body_y2"]))
    if not xs or not ys:
        return None
    return refdb.register(xs, ys, "words")


def _expected(words, widths):
    """Share the ink actually drawn on a line out by the QCF advance widths.

    `words` is {key: measured width}; `widths` the QCF width of each. Returns
    {key: expected width}. Words the QCF table does not know drop out of both sides
    of the proportion rather than being given a zero share.
    """
    known = [k for k in words if widths.get(k)]
    if not known:
        return {}
    tot_q = sum(widths[k] for k in known)
    tot_m = sum(words[k] for k in known)
    if tot_q <= 0 or tot_m <= 0:
        return {}
    return {k: widths[k] / tot_q * tot_m for k in known}


def judge_page(pg_and_keys):
    pg, keys = pg_and_keys
    p = os.path.join(REFDIR, "%03d.svg" % pg)
    try:
        rp = refdb.read_page(p)
        ref = refdb.fold(rp)
        mine = our_page(pg)
        reg = register_from_words(ref, mine)
    except Exception as exc:
        return pg, [{"key": k, "verdict": "ERROR", "why": str(exc)[:80]} for k in keys]
    if reg is None:
        return pg, [{"key": k, "verdict": "ERROR", "why": "no registration"} for k in keys]

    # Measured widths per line, in reference units, for both sides independently.
    our_lines, ref_lines = defaultdict(dict), defaultdict(dict)
    for k, m in mine.items():
        our_lines[m["line"]][k] = reg.x(m["x2"]) - reg.x(m["x1"])
    for k, r in ref.items():
        if "body_x1" in r:
            ref_lines[r["line"]][k] = r["body_x2"] - r["body_x1"]
    qw = {}
    for k in set(mine) | set(ref):
        v = QCF.get("%d:%d:%d" % k)
        if v:
            qw[k] = v
    our_exp = {}
    for ln, ws in our_lines.items():
        our_exp.update(_expected(ws, qw))
    ref_exp = {}
    for ln, ws in ref_lines.items():
        ref_exp.update(_expected(ws, qw))

    out = []
    for k in keys:
        rec = {"key": k, "page": pg}
        rec["ref_dots"] = sum(_DOTU.get(lab, 0)
                              for kind, lab, _b in ref[k]["pieces"]
                              if kind == "dots") if k in ref else None
        r, m = ref.get(k), mine.get(k)
        if not r or not m or "body_x1" not in r:
            rec["verdict"] = "ERROR"
            rec["why"] = "word missing from one side"
            out.append(rec)
            continue
        rec["word"] = r["hafs"]
        ow = reg.x(m["x2"]) - reg.x(m["x1"])
        rw = r["body_x2"] - r["body_x1"]
        rec["our_w"], rec["ref_w"] = round(ow, 2), round(rw, 2)

        # --- PIECES: one-sided, and it convicts outright -----------------------
        rec["nseg"] = m["nseg"]
        rec["our_pieces"], rec["ref_pieces"] = m["pieces"], r["nbody"]
        our_surplus = m["pieces"] > m["nseg"]
        ref_surplus = r["nbody"] > m["nseg"]
        if our_surplus and not ref_surplus:
            rec["verdict"], rec["why"] = "OURS", "we draw %d pieces, the spelling allows %d" % (m["pieces"], m["nseg"])
            out.append(rec)
            continue
        if ref_surplus and not our_surplus:
            rec["verdict"], rec["why"] = "THEIRS", "they draw %d pieces, the spelling allows %d" % (r["nbody"], m["nseg"])
            out.append(rec)
            continue

        # --- DOTS: the spelling says exactly how many the word owns ------------
        want = _dot_budget(m["qpc"] or m["text"])
        od, rd = m["dots"], rec.get("ref_dots")
        if rd is not None:
            rec["dot_want"], rec["our_dots"], rec["ref_dots"] = want, od, rd
            if od != want and rd == want:
                rec["verdict"] = "OURS"
                rec["why"] = "we hold %d dot units, the spelling and the reference both say %d" % (od, want)
                out.append(rec)
                continue
            if rd != want and od == want:
                rec["verdict"] = "THEIRS"
                rec["why"] = "they hold %d dot units, the spelling and we both say %d" % (rd, want)
                out.append(rec)
                continue

        # --- WIDTH: the QCF share of the line ---------------------------------
        oe, re_ = our_exp.get(k), ref_exp.get(k)
        if oe is None or re_ is None:
            rec["verdict"], rec["why"] = "UNCLEAR", "no QCF width for this word"
            out.append(rec)
            continue
        eo, er = abs(ow - oe), abs(rw - re_)
        rec["our_exp"], rec["ref_exp"] = round(oe, 2), round(re_, 2)
        rec["our_err"], rec["ref_err"] = round(eo, 2), round(er, 2)
        lo, hi = min(eo, er), max(eo, er)
        if hi - lo < MARGIN_ABS or (hi - lo) < MARGIN_REL * hi:
            rec["verdict"], rec["why"] = "UNCLEAR", "width errors %.2f vs %.2f are too close" % (eo, er)
        elif eo > er:
            rec["verdict"], rec["why"] = "OURS", "our width is off by %.2f, theirs by %.2f" % (eo, er)
        else:
            rec["verdict"], rec["why"] = "THEIRS", "their width is off by %.2f, ours by %.2f" % (er, eo)
        out.append(rec)
    return pg, out


def main(argv=None):
    global REFDIR
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("refdir", nargs="?",
                    default=os.environ.get("QSVG_REFDIR", ""),
                    help='the reference "SVG V1.01" directory')
    ap.add_argument("--flags", default=os.path.join(ROOT, "docs", "defects", "reference_words.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "defects", "reference_verdicts.json"))
    ap.add_argument("--jobs", type=int, default=6)
    args = ap.parse_args(argv)
    REFDIR = args.refdir
    if not REFDIR or not os.path.isdir(REFDIR):
        raise SystemExit("give the reference directory (or set QSVG_REFDIR)")

    data = json.load(open(args.flags, encoding="utf-8"))
    by_page = defaultdict(list)
    for f in data["flags"]:
        s, a, p = (int(x) for x in f["key"].split(":"))
        by_page[f["page"]].append((s, a, p))
    jobs = sorted(by_page.items())
    print("adjudicating %d disagreements over %d pages" % (len(data["flags"]), len(jobs)))

    from multiprocessing import Pool
    verdicts = []
    with Pool(args.jobs, maxtasksperchild=6) as pool:
        for pg, rows in pool.imap_unordered(judge_page, jobs):
            verdicts += rows

    tally = Counter(v["verdict"] for v in verdicts)
    print("\n%-9s %6s" % ("verdict", "words"))
    for k in ("OURS", "THEIRS", "UNCLEAR", "ERROR"):
        print("%-9s %6d   (%.1f%%)" % (k, tally[k], 100.0 * tally[k] / max(1, len(verdicts))))
    print("\nby the evidence that settled it:")
    why = Counter(("pieces" if "pieces" in v.get("why", "") else
                   "width" if "width" in v.get("why", "") else "none")
                  for v in verdicts if v["verdict"] in ("OURS", "THEIRS"))
    for k, n in why.most_common():
        print("   %-8s %d" % (k, n))
    ours = [v for v in verdicts if v["verdict"] == "OURS"]
    print("\nOUR defects by page (worst first):")
    per = Counter(v["page"] for v in ours)
    print("   %d pages hold them; worst: %s"
          % (len(per), ", ".join("p%d(%d)" % (p, n) for p, n in per.most_common(10))))
    print("\nsample of OUR defects:")
    for v in sorted(ours, key=lambda v: -abs(v.get("our_err", 0)))[:15]:
        print("   p%-4d %-11s %-16s %s"
              % (v["page"], "%d:%d:%d" % tuple(v["key"]) if isinstance(v["key"], (list, tuple)) else v["key"],
                 v.get("word", ""), v.get("why", "")))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"tally": dict(tally),
                   "verdicts": [dict(v, key="%d:%d:%d" % tuple(v["key"])
                                     if isinstance(v["key"], (list, tuple)) else v["key"])
                                for v in verdicts]}, fh, ensure_ascii=False, indent=1)
    print("\nwrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
