#!/usr/bin/env python3
"""Turn adjudicated reference disagreements into per-element overrides.

`tools/build_overrides.py` does this for a human reviewer's `move-element` edits: a
move is a fact about one place — *this ink, on this page, belongs to that word* — and
it is written as data keyed by geometry, never as a code edit. An adjudicated
disagreement with MushafDatabase is the same kind of fact, arrived at the same way,
and it is written the same way.

The rule that keeps this from turning us into a copy of the reference:

  **Only lines the adjudicator has convicted US on are touched, and no word it
  convicted THEM on is ever moved.**

The reference is wrong on 58 of the 478 words the two decompositions disagree about.
Following it blindly would import those. `adjudicate_ref.py` puts every disagreement to
a third source that has seen neither side — the QCF advance widths, and the joining-rule
piece count from `segment_word` — and only its `OURS` verdicts reach this tool.

Ownership is decided by overlap in the registered frame, not by label: for each of our
elements, the reference word whose own pieces cover most of it. Registration lands the
two frames within 0.01 of a unit, so "which word is this ink drawn inside" has an
unambiguous answer.

    python3 tools/ref_overrides.py "<ref>/SVG V1.01" --dry-run
    python3 tools/ref_overrides.py "<ref>/SVG V1.01" --jobs 8
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
OUT = os.path.join(ROOT, ".cache", "review", "overrides.json")

# An element is claimed by the reference word covering at least this much of it. Below
# it the ink is genuinely shared between two words' outlines and no override is written.
COVER = 0.60

# A fathah and a kasrah are the SAME stroke, named afterwards from where it sits and what
# the word's budget allows. Carrying one across a word boundary re-opens that decision
# for both words, and the renaming can come back differently — the neighbour transfer
# and the cross-line repair both refuse to move these for exactly that reason, and
# ignoring it here put fathah +14 and kasrah +16 on an otherwise clean round. The body
# ink these strokes sit over still moves; only the naming-unstable strokes stay put.
_UNSTABLE = ("fathah", "kasrah", "tanwin_al_fath", "tanwin_al_kasr")

# What a word's spelling says it can own, per mark family. The reference places a mark
# where the ink sits; the text says whether that word can own it at all. Both have to
# agree before a mark moves — on p552 the reference put a dot on `كُلِّهِۦ`, which has no
# dotted letter in it, because the `ن` of `ٱلدِّينِ` is drawn over its territory.
_WANT = {
    "fathah": ("َ",), "kasrah": ("ِ",), "dammah": ("ُ",),
    "tanwin_al_fath": ("ً", "ࣰ"), "tanwin_al_kasr": ("ٍ", "ࣲ"), "tanwin_al_damm": ("ٌ", "ࣱ"),
    "sukun": ("ْ", "ۡ"), "shaddah": ("ّ",), "maddah": ("ٓ", "ۤ"),
    "omitted_alif": ("ٰ",), "hamzat_al_wasl": ("ٱ",), "small_waw": ("ۥ",),
    "small_yaa": ("ۦ", "ۧ"),
    # taxonomy phase 1: the zeros split (the pipeline emits the new names;
    # a mark still named small_circle simply finds no budget here, as before)
    "rounded_zero": ("۟",), "rectangular_zero": ("۠",),
    "hamzah": ("أ", "إ", "ؤ", "ئ", "ٔ", "ٕ"),
    "small_noon": ("ۨ",),
}
_DOTU = {"dot": 1, "two_dots": 2, "three_dots": 3}


def _dot_budget(txt):
    """Dot units the word's letters own, by the same rule audit_marks.py uses."""
    raw = aw._LETTER.findall(txt)
    sk = [(aw.HAMZAH_MAP[c][0] if c in aw.HAMZAH_MAP else c, c in aw.HAMZAH_MAP) for c in raw]
    n = 0
    for i, (ch, seat) in enumerate(sk):
        if seat or ch not in aw.DOTS:
            continue
        if ch == "\u064a" and (i == len(sk) - 1
                                or (i + 1 < len(sk) and sk[i + 1][0] == "\u0621")):
            continue                       # see audit_marks.dot_want
        n += _DOTU.get(aw.DOTS[ch][0], 0)
    return n


def _budget(txt, fam):
    if fam in _DOTU:
        return _dot_budget(txt)
    chars = _WANT.get(fam)
    return None if chars is None else sum(txt.count(c) for c in chars)


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
        lns = [e.get("line") for e in body if e.get("line")]
        words[k] = {"line": max(set(lns), key=lns.count) if lns else 0,
                    "x1": min(e["x1"] for e in body), "x2": max(e["x2"] for e in body),
                    "y2": max(e["y2"] for e in body), "text": w["rasm_uthmani"]}
        for e in ee:
            if not e.get("mkpart"):        # a welded twin travels with its master
                els.append((k, e))
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


def _cover(box, pieces):
    """Fraction of `box` covered by the UNION of the reference word's pieces.

    The union, not the sum. A reference word's own pieces overlap each other freely —
    a diacritic box sits inside its ligature's box — so adding their intersections
    reported coverages of 1.44 and let a word with many stacked pieces outbid the word
    the ink is actually drawn in. Coordinate compression over at most a few dozen
    clipped rectangles is exact and costs nothing at this size.
    """
    x1, y1, x2, y2 = box
    area = max(1e-6, (x2 - x1) * (y2 - y1))
    clipped = []
    for _kind, _lab, (px1, py1, px2, py2) in pieces:
        cx1, cy1 = max(x1, px1), max(y1, py1)
        cx2, cy2 = min(x2, px2), min(y2, py2)
        if cx2 > cx1 and cy2 > cy1:
            clipped.append((cx1, cy1, cx2, cy2))
    if not clipped:
        return 0.0
    xs = sorted({v for r in clipped for v in (r[0], r[2])})
    ys = sorted({v for r in clipped for v in (r[1], r[3])})
    got = 0.0
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
            if any(r[0] <= cx <= r[2] and r[1] <= cy <= r[3] for r in clipped):
                got += (xs[i + 1] - xs[i]) * (ys[j + 1] - ys[j])
    return got / area


def plan_page(job):
    """Overrides for one page. Returns (page, {geom-key: 'surah:ayah:pos'}, stats)."""
    pg, convicted, acquitted, proven = job
    try:
        rp = refdb.read_page(os.path.join(REFDIR, "%03d.svg" % pg))
        ref = refdb.fold(rp)
        mine, els = our_page(pg)
        reg = _register(ref, mine)
    except Exception as exc:
        return pg, {}, Counter({"error": 1}), ["%s: %s" % (type(exc).__name__, exc)]
    if reg is None:
        return pg, {}, Counter({"no-registration": 1}), []

    # Only the lines a conviction sits on. A line nobody was convicted on is left
    # exactly as the pipeline produced it, however tempting the reference looks.
    lines = {mine[k]["line"] for k in convicted if k in mine}
    if not lines:
        return pg, {}, Counter({"no-line": 1}), []

    # Reference words are only usable as a destination if we agree they are the same
    # word and we have a word to move ink into.
    usable = {k for k in set(ref) & set(mine)
              if ref[k]["skel"] == refdb.skeleton(mine[k]["text"])}

    out, stats, notes, moves = {}, Counter(), [], []
    for k, e in els:
        if k not in mine or mine[k]["line"] not in lines:
            continue
        if e["kind"] != "body" and e.get("mark") in _UNSTABLE:
            stats["skipped: a slash stroke is renamed if it moves"] += 1
            continue
        box = (reg.x(e["x1"]), reg.y(e["y1"]), reg.x(e["x2"]), reg.y(e["y2"]))
        best, bestc = None, 0.0
        for rk in usable:
            c = _cover(box, ref[rk]["pieces"])
            if c > bestc:
                bestc, best = c, rk
        if best is None or bestc < COVER:
            stats["ink no reference word claims"] += 1
            continue
        if best == k:
            stats["already right"] += 1
            continue
        # An acquittal normally blocks the move — but not against proof. The two tests
        # can contradict: `فَقُلْ` (p331) is convicted OURS because it draws two
        # connected runs of ink where the spelling permits one, while the neighbour
        # holding its missing piece is acquitted on WIDTH. Drawing more runs than the
        # joining rules allow is not a judgement, it is arithmetic on the spelling and
        # cannot be wrong; the width prior is a proportion with real noise, where both
        # decompositions sit near 1.5% beyond the 1.5x mark. Proof outranks the prior.
        if (k in acquitted or best in acquitted) and k not in proven:
            stats["skipped: adjudicator says the reference is wrong here"] += 1
            continue
        moves.append((k, best, e, bestc))

    moves, split = _keep_each_word_on_one_line(moves, els, mine)
    stats["skipped: would leave a word straddling two lines"] += split
    moves, dropped = _keep_every_word_fed(moves, els)
    stats["skipped: would leave a word with no ink at all"] += dropped
    moves, overfed = _keep_within_text_budget(moves, els, mine)
    stats["skipped: the receiving word's spelling has no room for that mark"] += overfed
    for k, best, e, bestc in moves:
        out["%.1f,%.1f,%.1f,%.1f" % (e["x1"], e["y1"], e["x2"], e["y2"])] = \
            "%d:%d:%d" % best
        stats["override"] += 1
        if len(notes) < 6:
            notes.append("%s %s -> %s (%s x%.1f-%.1f, cover %.2f)"
                         % (e["kind"], "%d:%d:%d" % k, "%d:%d:%d" % best,
                            e.get("mark") or e.get("lab") or "", e["x1"], e["x2"], bestc))
    return pg, out, stats, notes


def _keep_each_word_on_one_line(moves, els, mine):
    """Allow ink to cross a line, but only as a matched pair that leaves no word split.

    A word we filed under the wrong line needs TWO moves: the ink it wrongly holds goes
    back to its neighbour on this line, and its own ink comes to it from the line below.
    Doing only the first empties the word — that is what refusing cross-line moves
    outright was protecting against, and it left `يَأْتِىَ` on p555 broken along with 70
    others. Doing only the second leaves it straddling two lines, which is worse than
    either. So a cross-line move is kept only when the word it feeds ends up with all of
    its letter ink on a single line; otherwise every move into that word is dropped and
    the word is left exactly as the pipeline produced it.

    Iterated, because dropping one word's incoming moves can leave another straddling.
    """
    lines = defaultdict(Counter)
    for k, e in els:
        if e["kind"] == "body" and e.get("line"):
            lines[k][e["line"]] += 1
    dropped = 0
    while True:
        after = {k: Counter(c) for k, c in lines.items()}
        for k, b, e, _c in moves:
            if e["kind"] != "body" or not e.get("line"):
                continue
            after.setdefault(k, Counter())[e["line"]] -= 1
            after.setdefault(b, Counter())[e["line"]] += 1
        straddling = set()
        for k, c in after.items():
            live = {ln for ln, n in c.items() if n > 0}
            was = {ln for ln, n in lines.get(k, {}).items() if n > 0}
            if len(live) > 1 and len(live) > len(was):
                straddling.add(k)
        if not straddling:
            return moves, dropped
        keep = [m for m in moves if m[1] not in straddling]
        if len(keep) == len(moves):
            return moves, dropped
        dropped += len(moves) - len(keep)
        moves = keep


def _keep_within_text_budget(moves, els, mine):
    """Drop a MARK move that would give a word more of a family than its spelling allows.

    The reference decides ownership from where the ink is drawn, and Arabic calligraphy
    draws a mark wherever there is room — the dot of a `ن` sits over the next word, the
    two dots of an initial `ya` over the previous word's `raa`. Following that blindly
    hands a word marks it cannot own. Bodies are exempt: a letter belongs to whichever
    word the letters spell, and the width and joining-rule tests already govern those.
    """
    held = defaultdict(Counter)
    for k, e in els:
        fam = e.get("mark")
        if fam and e["kind"] != "body":
            held[k][fam] += 1
    dropped = 0
    while True:
        gain = defaultdict(Counter)
        for k, b, e, _c in moves:
            fam = e.get("mark")
            if fam and e["kind"] != "body":
                gain[b][fam] += 1
                gain[k][fam] -= 1
        over = set()
        for k, fams in gain.items():
            if k not in mine:
                continue
            for fam, d in fams.items():
                if d <= 0:
                    continue
                cap = _budget(mine[k]["text"], fam)
                if cap is not None and held[k][fam] + d > cap:
                    over.add((k, fam))
        if not over:
            return moves, dropped
        keep = [m for m in moves
                if m[1] not in {k for k, _f in over}
                or m[2]["kind"] == "body"
                or (m[1], m[2].get("mark")) not in over]
        if len(keep) == len(moves):
            return moves, dropped
        dropped += len(moves) - len(keep)
        moves = keep


def _keep_every_word_fed(moves, els):
    """Drop any move that would leave a word with no letter ink at all.

    A word whose own ink is drawn on a different line than we filed it under is a
    *line* error, and the reference rightly says the ink we gave it belongs to a
    neighbour. Acting on only half of that — handing the wrong ink away without being
    able to hand the right ink back, because that half crosses a line — empties the
    word completely. It happened to eighteen words, `يَأْتِىَ` on p555 among them, and
    a word with no ink is worse than a word with the wrong ink.

    Dropping is iterated: releasing one word's ink can be what empties another.
    """
    bodies = Counter(k for k, e in els if e["kind"] == "body")
    dropped = 0
    while True:
        out_c = Counter(k for k, _b, e, _c in moves if e["kind"] == "body")
        in_c = Counter(b for _k, b, e, _c in moves if e["kind"] == "body")
        starved = {k for k in bodies if bodies[k] - out_c[k] + in_c[k] <= 0}
        if not starved:
            return moves, dropped
        keep = [m for m in moves if m[0] not in starved]
        dropped += len(moves) - len(keep)
        moves = keep


def main(argv=None):
    global REFDIR
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("refdir")
    ap.add_argument("--verdicts", default=os.path.join(ROOT, "docs", "defects",
                                                       "reference_verdicts.json"))
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    REFDIR = args.refdir

    verdicts = json.load(open(args.verdicts, encoding="utf-8"))["verdicts"]
    convicted, acquitted, proven = defaultdict(set), defaultdict(set), defaultdict(set)
    for v in verdicts:
        k = tuple(int(x) for x in v["key"].split(":"))
        if v["verdict"] == "OURS":
            convicted[v["page"]].add(k)
            if "pieces" in (v.get("why") or ""):
                proven[v["page"]].add(k)      # the joining rules, not a prior
        elif v["verdict"] == "THEIRS":
            acquitted[v["page"]].add(k)
    jobs = [(pg, convicted[pg], acquitted[pg], proven[pg]) for pg in sorted(convicted)]
    print("pages with a conviction: %d   words convicted: %d (%d of them by the joining "
          "rules)   words acquitted: %d"
          % (len(jobs), sum(len(v) for v in convicted.values()),
             sum(len(v) for v in proven.values()),
             sum(len(v) for v in acquitted.values())))

    from multiprocessing import Pool
    table, stats, notes = {}, Counter(), []
    with Pool(args.jobs, maxtasksperchild=6) as pool:
        for pg, per, st, nt in pool.imap_unordered(plan_page, jobs):
            stats.update(st)
            if per:
                table[str(pg)] = per
            notes += [("p%d " % pg) + n for n in nt[:2]]

    print("\n%-52s %s" % ("outcome", "elements"))
    for k, v in stats.most_common():
        print("   %-49s %6d" % (k, v))
    print("\npages receiving overrides: %d   elements moved: %d"
          % (len(table), sum(len(v) for v in table.values())))
    print("\nsample:")
    for n in notes[:20]:
        print("   " + n)

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0
    existing = {}
    if os.path.exists(args.out):
        try:
            existing = json.load(open(args.out, encoding="utf-8"))
        except Exception:
            existing = {}
    kept = 0
    for pg, per in table.items():
        tgt = existing.setdefault(pg, {})
        for kk, vv in per.items():
            if kk not in tgt:              # a human's override always wins
                tgt[kk] = vv
                kept += 1
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(existing, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print("\nwrote %s — %d new entries, %d pages total"
          % (args.out, kept, len(existing)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
