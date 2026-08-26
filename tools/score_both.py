#!/usr/bin/env python3
"""Score OUR decomposition and MushafDatabase's against the same outside evidence.

`audit_ref_words.py` measures where the two decompositions disagree, and
`adjudicate_ref.py` says which of us is wrong in each of those places. Neither answers
the question the goal actually asks, which is *whose decomposition is more accurate*:

  * they only ever look at words the two sides disagree about, so words both get wrong
    the same way are invisible to them, and
  * "THEIRS = 58" counts disagreements adjudicated against the reference, which is not
    the reference's error rate over the corpus — it is its error rate on the subset we
    happened to disagree with it about. Comparing that with our own count is not
    like for like.

This scores both decompositions, over every word, against evidence that comes from
neither of them:

  WIDTH   the QCF v2 page fonts' own advance width per word. Share a line's drawn ink
          out in that proportion and each word has an expected size derived from the
          print's metrics and the spelling. Each side is measured against its own line
          membership, so neither is charged for the other's line assignment. Label-free
          and completely symmetric — this is the primary number.

  PIECES  the Arabic joining rules (`segment_word`) cap how many separate letter groups
          a word can be drawn in. Fewer is normal, since the art joins letters the rules
          allow to separate; MORE is impossible.

          A letter group is counted as a run of ink connected along x, NOT as a path or
          a contour. The two sources cut the same glyph into different numbers of pieces
          — `أَلِيمٌۢ` on p136 is two paths for them and three contours for us, with
          identical extent — so counting pieces as drawn objects measures draughtsmanship
          and charges it as theft. Merging overlapping x-intervals first makes the
          measure the same question for both sides.

  DOTS    the letter dots a word's spelling owns, taken from the King Fahd Complex's own
          text of this print. `dot`/`two dots`/`three dots` need no label mapping, so
          both sides are counted the same way.

    python3 tools/score_both.py "<ref>/SVG V1.01" --jobs 8
"""

import argparse
import contextlib
import importlib.util
import io
import json
import math
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

_DOTU = {"dot": 1, "two-dots": 2, "three-dots": 3,
         "two dots": 2, "three dots": 3}


# Two runs of ink closer than this along x are one letter group. A real inter-letter
# break in this art is several units wide; this only closes the seam where one source
# ends a contour and starts another inside the same glyph.
_JOIN = 0.4


def _groups(spans):
    """How many runs of ink, merging anything that overlaps or nearly touches along x."""
    if not spans:
        return 0
    spans = sorted(spans)
    n, cur = 1, spans[0][1]
    for a, b in spans[1:]:
        if a <= cur + _JOIN:
            cur = max(cur, b)
        else:
            n += 1
            cur = b
    return n


def dot_budget(txt):
    raw = aw._LETTER.findall(txt)
    sk = [(aw.HAMZA_MAP[c][0] if c in aw.HAMZA_MAP else c, c in aw.HAMZA_MAP) for c in raw]
    n = 0
    for i, (ch, seat) in enumerate(sk):
        if seat or ch not in aw.DOTS:
            continue
        if ch == "ي" and (i == len(sk) - 1
                          or (i + 1 < len(sk) and sk[i + 1][0] == "ء")):
            continue                  # see audit_marks.dot_want
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
        out[(w["surah"], w["ayah"], w["pos"])] = {
            "line": max(set(lns), key=lns.count) if lns else 0,
            "x1": min(e["x1"] for e in body), "x2": max(e["x2"] for e in body),
            "y2": max(e["y2"] for e in body),
            "pieces": _groups([(e["x1"], e["x2"]) for e in body]),
            "text": w["uthmani"], "qpc": w.get("qpc") or "",
            # Welded twins excluded, exactly as audit_marks.py counts — a master's
            # label already accounts for its members. Two alternatives were measured and
            # both are worse: counting every twin as a stroke, and counting only twins
            # drawn clear of their master, each took the disagreement from 7 words to
            # 358. Where our count really is short, the defect is upstream: the third dot
            # of the `ث` in `فَبَعَثَ` (p33) makes a three-dot cluster our table labels
            # `two-dots`, and `بِٱلۡمَعۡرُوفِ` (p27) welds two dots fifty units apart.
            "dots": sum(_DOTU.get(e.get("mark") or "", 0)
                        for e in els if not e.get("mkpart")),
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


def _expect(widths, qw):
    known = [k for k in widths if qw.get(k)]
    tq = sum(qw[k] for k in known)
    tm = sum(widths[k] for k in known)
    if tq <= 0 or tm <= 0:
        return {}
    return {k: qw[k] / tq * tm for k in known}


def scan(pg):
    try:
        rp = refdb.read_page(os.path.join(REFDIR, "%03d.svg" % pg))
        ref = refdb.fold(rp)
        mine = our_page(pg)
        reg = _register(ref, mine)
    except Exception as exc:
        return pg, None, "%s: %s" % (type(exc).__name__, exc)
    if reg is None:
        return pg, None, "no registration"

    both = [k for k in set(ref) & set(mine)
            if "body_x1" in ref[k] and ref[k]["skel"] == refdb.skeleton(mine[k]["text"])]
    qw = {k: QCF["%d:%d:%d" % k] for k in both if QCF.get("%d:%d:%d" % k)}

    ourw = {k: reg.x(mine[k]["x2"]) - reg.x(mine[k]["x1"]) for k in both}
    refw = {k: ref[k]["body_x2"] - ref[k]["body_x1"] for k in both}
    our_lines, ref_lines = defaultdict(dict), defaultdict(dict)
    for k in both:
        our_lines[mine[k]["line"]][k] = ourw[k]
        ref_lines[ref[k]["line"]][k] = refw[k]
    our_exp, ref_exp = {}, {}
    for ws in our_lines.values():
        our_exp.update(_expect(ws, qw))
    for ws in ref_lines.values():
        ref_exp.update(_expect(ws, qw))

    st = Counter()
    _W50 = []
    ologs, rlogs = [], []
    for k in both:
        st["words"] += 1
        # --- WIDTH -------------------------------------------------------------
        if k in our_exp and k in ref_exp and our_exp[k] > 0 and ref_exp[k] > 0:
            st["width_words"] += 1
            lo = math.log(max(ourw[k], 1e-3) / our_exp[k])
            lr = math.log(max(refw[k], 1e-3) / ref_exp[k])
            ologs.append(abs(lo))
            rlogs.append(abs(lr))
            for tag, v in (("our", abs(lo)), ("ref", abs(lr))):
                if v > math.log(1.5):
                    st[tag + "_w50"] += 1
                if v > math.log(2.0):
                    st[tag + "_w100"] += 1
            # the words that separate the two totals, so a gap of three can be read
            # rather than guessed at
            if (abs(lo) > math.log(1.5)) != (abs(lr) > math.log(1.5)):
                _W50.append((pg, "%d:%d:%d" % k, mine[k]["text"],
                             "ours" if abs(lo) > abs(lr) else "theirs",
                             round(abs(lo), 3), round(abs(lr), 3),
                             round(ourw[k], 1), round(our_exp[k], 1),
                             round(refw[k], 1), round(ref_exp[k], 1)))
        # --- PIECES: more than the joining rules permit is impossible ----------
        ns = mine[k]["nseg"]
        st["piece_words"] += 1
        if mine[k]["pieces"] > ns:
            st["our_piece_surplus"] += 1
        their = _groups([(b[0], b[2]) for kind, _l, b in ref[k]["pieces"] if kind == "text"])
        if their > ns:
            st["ref_piece_surplus"] += 1
        # --- DOTS against the print's own text --------------------------------
        txt = mine[k]["qpc"] or mine[k]["text"]
        want = dot_budget(txt)
        rd = sum(_DOTU.get(lab, 0) for kind, lab, _b in ref[k]["pieces"] if kind == "dots")
        st["dot_words"] += 1
        if mine[k]["dots"] != want:
            st["our_dot_off"] += 1
        if rd != want:
            st["ref_dot_off"] += 1
    return pg, (st, ologs, rlogs, _W50), None


def main(argv=None):
    global REFDIR
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("refdir")
    ap.add_argument("first", nargs="?", type=int, default=1)
    ap.add_argument("last", nargs="?", type=int, default=604)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "defects", "score_both.json"))
    args = ap.parse_args(argv)
    REFDIR = args.refdir

    from multiprocessing import Pool
    tot = Counter()
    O, R = [], []
    W50 = []
    bad = []
    with Pool(args.jobs, maxtasksperchild=6) as pool:
        for pg, res, err in pool.imap_unordered(scan, range(args.first, args.last + 1)):
            if err:
                bad.append((pg, err))
                continue
            st, o, r, w50 = res
            tot.update(st)
            O += o
            R += r
            W50 += w50
    O.sort()
    R.sort()

    def pct(v, p):
        return v[min(len(v) - 1, int(p * len(v)))] if v else 0.0

    n = max(1, tot["width_words"])
    print("pages scored %d (skipped %d)   words scored on both sides %d"
          % (args.last - args.first + 1 - len(bad), len(bad), tot["words"]))
    print("\nEvidence: QCF advance widths, the Arabic joining rules, and the KFGQPC text.")
    print("Neither decomposition is used to judge the other.\n")
    print("%-46s %12s %12s" % ("", "OURS", "MUSHAFDATABASE"))
    print("%-46s %12s %12s" % ("-" * 46, "-" * 12, "-" * 12))
    print("%-46s %12.4f %12.4f" % ("WIDTH  mean |log(measured/expected)|",
                                   sum(O) / max(1, len(O)), sum(R) / max(1, len(R))))
    print("%-46s %12.4f %12.4f" % ("       median", pct(O, .5), pct(R, .5)))
    print("%-46s %12.4f %12.4f" % ("       90th percentile", pct(O, .9), pct(R, .9)))
    print("%-46s %12.4f %12.4f" % ("       99th percentile", pct(O, .99), pct(R, .99)))
    print("%-46s %10d   %10d  " % ("       words off by more than 1.5x",
                                   tot["our_w50"], tot["ref_w50"]))
    print("%-46s %10d   %10d  " % ("       words off by more than 2x",
                                   tot["our_w100"], tot["ref_w100"]))
    print("%-46s %10d   %10d  " % ("PIECES more pieces than the spelling allows",
                                   tot["our_piece_surplus"], tot["ref_piece_surplus"]))
    print("%-46s %10d   %10d  " % ("DOTS   dot count disagrees with the text",
                                   tot["our_dot_off"], tot["ref_dot_off"]))
    print("\nas a rate over %d scored words:" % n)
    for name, a, b in (("width off >1.5x", tot["our_w50"], tot["ref_w50"]),
                       ("width off >2x", tot["our_w100"], tot["ref_w100"]),
                       ("piece surplus", tot["our_piece_surplus"], tot["ref_piece_surplus"]),
                       ("dots wrong", tot["our_dot_off"], tot["ref_dot_off"])):
        v = "OURS BETTER" if a < b else ("EQUAL" if a == b else "reference better")
        print("   %-22s ours %6.3f%%   theirs %6.3f%%   %s"
              % (name, 100.0 * a / n, 100.0 * b / n, v))
    if W50:
        print("\nthe %d word(s) where only ONE side is beyond 1.5x "
              "(ours worse %d, theirs worse %d):"
              % (len(W50), sum(1 for r in W50 if r[3] == "ours"),
                 sum(1 for r in W50 if r[3] == "theirs")))
        for r in sorted(W50, key=lambda r: -max(r[4], r[5]))[:24]:
            print("   p%-4d %-11s %-18s %-6s ours %.2f (%.1f of %.1f)  "
                  "theirs %.2f (%.1f of %.1f)"
                  % (r[0], r[1], r[2], r[3], r[4], r[6], r[7], r[5], r[8], r[9]))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"totals": dict(tot), "not_scored": bad, "w50_split": W50}, fh, ensure_ascii=False, indent=1)
    print("\nwrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
