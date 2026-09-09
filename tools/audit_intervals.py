#!/usr/bin/env python3
"""RTL interval audit.

Scan each line right-to-left. Each word's BODY ink gives an interval; the part
of it no other word touches is that word's *exclusive core*. A mark sitting in
another word's exclusive core is misplaced ink -- and unlike a mark count, this
stays true when two words swap marks, so it sees chain shifts and cycles.

A flag has two possible causes, and they need opposite fixes:
  BODY-STEAL  the holder lost a letter piece, so its interval is too short and
              its own marks fall inside the thief. Re-partition; do NOT move
              the mark -- that would strip the word of a vowel it really owns.
  MARK-STEAL  both words have healthy ink and the mark alone is in the wrong
              word. Safe to move.
Separating them needs the width prior and the joining-rule piece count.
"""
import importlib.util, json, os, sys
from collections import Counter

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT + "/tools")
# Honour QSVG_PIPE like audit_marks.py does: full_sweep.py runs both audits in one
# process, so if only one of them followed the switch a candidate sweep would mix
# marks from one build with intervals from another.
PIPE = os.environ.get("QSVG_PIPE", ROOT + "/tools/assign_words.py")
spec = importlib.util.spec_from_file_location("assign_words", PIPE)
aw = importlib.util.module_from_spec(spec); sys.modules["assign_words"] = aw
spec.loader.exec_module(aw)
cap = {}; _orig = aw.rewrite
def _spy(page, a): cap["a"] = a; return _orig(page, a)
aw.rewrite = _spy
QW = json.load(open(ROOT + "/.cache/qcf_widths.json"))


def eff_bodies(els):
    bods = [e for e in els if e["kind"] == "body"]
    out = []
    for b in bods:
        wb = b["x2"] - b["x1"]
        if not any(o is not b
                   and min(o["x2"], b["x2"]) - max(o["x1"], b["x1"]) >= 0.6 * wb
                   and (o["x2"] - o["x1"]) > wb for o in bods):
            out.append(b)
    return out


def scan(pg):
    aw.assign_page("hafs/kfqc", pg, ROOT + "/.cache/words")
    lines = {}
    for w, at in cap["a"]:
        if not w:
            continue
        els = [e for a in at for e in a["els"]]
        if els:
            lines.setdefault(els[0].get("line"), []).append((w, els))

    flags = []
    for ln, sub in lines.items():
        iv, meta = {}, {}
        for w, els in sub:
            b = [e for e in els if e["kind"] == "body"]
            if not b:
                continue
            iv[id(w)] = (min(e["x1"] for e in b), max(e["x2"] for e in b), w)
            meta[id(w)] = (els, eff_bodies(els))
        # width prior: share out the line's actual ink by the reference metrics
        tot_a = sum(t[1] - t[0] for t in iv.values())
        tot_q = sum(QW.get("%d:%d:%d" % (t[2]["surah"], t[2]["ayah"], t[2]["pos"]), 0)
                    for t in iv.values())
        def ratio(w):
            t = iv[id(w)]
            qw = QW.get("%d:%d:%d" % (w["surah"], w["ayah"], w["pos"]), 0)
            if not qw or not tot_q:
                return None
            exp = qw / tot_q * tot_a
            return (t[1] - t[0]) / exp if exp else None

        for w, els in sub:
            if id(w) not in iv:
                continue
            for e in els:
                if e["kind"] != "mark" or e.get("mkpart") or e.get("standalone"):
                    continue
                # A mark is wide enough that its centre can tip past its own
                # word's edge while the mark still stands squarely on that
                # word's last letter -- the kasrah under a word-initial lam
                # does exactly this. Overlap, not the centre, is the test:
                # ink that touches its holder at all is not foreign to it.
                cx = (e["x1"] + e["x2"]) / 2
                def ov(t):
                    return min(e["x2"], t[1]) - max(e["x1"], t[0])
                mine = iv[id(w)]
                if ov(mine) > 0.5:
                    continue                  # still touching its own word
                # The small waw of the pronoun suffix -hu and the small ya of
                # -hi are written clear of the word's own ink, past its left
                # edge, so they sit over whatever follows. When the text says
                # the word has one, its position is the script's doing and not
                # a defect -- and moving it would strip the suffix.
                if e.get("mark") == "small_waw" and "\u06e5" in w["rasm_uthmani"]:
                    continue
                if e.get("mark") == "small_yaa" and "\u06e6" in w["rasm_uthmani"]:
                    continue
                owners = [t for t in iv.values() if ov(t) > 0.5]
                if len(owners) != 1 or owners[0][2] is w:
                    continue
                other = owners[0][2]
                # X-OVERLAP IS NOT TERRITORY (Abdullah 2026-08-29, "what are
                # the issues here, I can't see it"). A dammah/tanwin_al_damm riding
                # on a final أ or ة sits high above the line and overhangs
                # the next word's x-range while clearing its LETTERS by a
                # wide margin -- it is over that word's empty air, not its
                # ink. Measured over every surviving record: vertical
                # clearance runs 0.0, 0.0 x7, 0.4, 0.7, 1.1, 1.4, 1.4, 2.9,
                # 3.1, 3.9, 4.4 -- then NOTHING until 9.2, 10.5, 11.2, 13.5.
                # An empty band 4.8u wide, and every record above it is that
                # same overhang shape (ٱلْمَلَأُ↔مِن twice, مَلَأࣱ↔مِّن,
                # مَلَٰٓئِكَةࣰۖ↔وَمَا), each with BOTH words' counts exact.
                # Threshold inside the band, not at its edge.
                _ob = [x for x in meta[id(other)][0]
                       if x["kind"] == "body"]
                if _ob:
                    _oy1 = min(x["y1"] for x in _ob)
                    _oy2 = max(x["y2"] for x in _ob)
                    if max(_oy1 - e["y2"], e["y1"] - _oy2) > 6.5:
                        continue

                # AND THE MARK MUST BE NEARER THE ACCUSED WORD THAN ITS OWN.
                # The x-overlap test above ("still touching its own word")
                # is one-dimensional, so a mark hugging its own word's last
                # letter slips past it by a fraction of a unit and is then
                # judged on x alone. Measured as the 2-D gap from the mark's
                # box to each word's nearest letter box, over every record:
                #   own-minus-neighbour = -151.4, -3.1, -2.7, -2.2, -1.4,
                #   -0.7, -0.4  |  +1.0, +1.2, +1.3, +2.0, +4.4, +4.7, +5.0,
                #   +5.6, +6.6, +6.9
                # An empty band 1.4u wide. Every record left of it has the
                # mark TOUCHING its own word (own gap 0.0-2.4) -- يُغَيِّرُ's
                # own two dots, ٱلْعَزِيزُ's own hamzat_al_wasl, and one case whose
                # "neighbour" is 151u away. Threshold inside the band.
                # HORIZONTALLY only. The 2-D form measured vertical distance
                # too, which is about how TALL the neighbouring letter is, not
                # about who owns the mark: on p350 رَأْفَةࣱ's tanwin overlaps its
                # own ة by 0.4u and فِى by 1.1u, so dx is 0 to both and the
                # decision fell entirely to dy — فِى's ف simply rises higher
                # (y 166.2) than the ة (y 167.4), and won the mark by 1.2u.
                # Abdullah, 2026-09-09: "we should measure that in x axis only,
                # not the distance." A mark that still overlaps its own word
                # horizontally has not gone anywhere.
                def _gap(bx):
                    g = 1e9
                    for b in bx:
                        g = min(g, max(0.0, b["x1"] - e["x2"], e["x1"] - b["x2"]))
                    return g
                _hb = [x for x in els if x["kind"] == "body"]
                if _hb and _ob and _gap(_hb) - _gap(_ob) < 0.3:
                    continue
                rA, rB = ratio(w), ratio(other)
                nsegA = max(1, len(aw.segment_word(w["rasm_uthmani"])))
                defA = nsegA - len(meta[id(w)][1])
                # Ink can bleed across a word boundary without a whole piece
                # changing hands, so the width prior -- not the piece count --
                # is what says the body partition is wrong. A piece deficit
                # only sharpens it.
                if rA is not None and rA < 0.75:
                    kind = "BODY-STEAL"          # holder starved: it lost ink
                elif rA is not None and rA > 1.35:
                    kind = "BODY-GRAB"           # holder swollen: it took ink
                elif rB is not None and not (0.7 <= rB <= 1.35):
                    kind = "NEIGHBOUR-BAD"       # the other word's ink is off
                else:
                    kind = "MARK-STEAL"          # both sound: the mark alone moved
                flags.append({"page": pg, "line": ln, "kind": kind,
                              "holder": w["rasm_uthmani"], "inside": other["rasm_uthmani"],
                              "key": "%d:%d:%d" % (w["surah"], w["ayah"], w["pos"]),
                              "mark": e.get("mark"), "x": round(cx, 1),
                              "rA": None if rA is None else round(rA, 2),
                              "rB": None if rB is None else round(rB, 2),
                              "pieces": "%d/%d" % (len(meta[id(w)][1]), nsegA),
                              "deficit": defA})
    return flags


if __name__ == "__main__":
    pages = [int(x) for x in sys.argv[1:]] or [1, 3, 20, 341, 350, 355, 366, 418]
    allf, per = [], Counter()
    for pg in pages:
        f = scan(pg)
        allf += f
        per[pg] = len(f)
    kinds = Counter(x["kind"] for x in allf)
    print("flags %d over %d pages   %s" % (len(allf), len(pages), dict(kinds)))
    print("per page:", {p: n for p, n in per.items() if n})
    for k in ("BODY-STEAL", "BODY-GRAB", "NEIGHBOUR-BAD", "MARK-STEAL"):
        rows = [x for x in allf if x["kind"] == k]
        if not rows:
            continue
        print("\n== %s (%d)" % (k, len(rows)))
        for x in rows[:14]:
            print("  p%-4d L%-3s %-14s holds %-11s inside %-14s  w %s/%s  pieces %s"
                  % (x["page"], x["line"], x["holder"], x["mark"], x["inside"],
                     x["rA"], x["rB"], x["pieces"]))
    json.dump(allf, open(os.path.dirname(os.path.abspath(__file__)) + "/interval_flags.json", "w"),
              ensure_ascii=False, indent=1)
