#!/usr/bin/env python3
"""The same word, drawn the same way -- everywhere but here.

Consistency across REPETITIONS. A word-form occurs many times in the mushaf,
and the number of separate CONTOURS its letter bodies draw is fixed by the
letters themselves: outer strokes plus their counters. Unlike width, unlike
height, unlike the bounding box, this number is invariant under the print's
justification -- a kashida stretches a run, it never opens or closes a hole.
So if وَٱلَّذِينَ draws 5 body contours 161 times and 7 once, the once is a
candidate: the word is holding a piece it should not, or has lost one.

This sees the defect NOTHING else sees -- a stolen BODY piece. The mark audit
counts marks; a letter is not a mark. The interval and crossline audits ask
where ink is drawn relative to other words; a stolen alif sits exactly where
it always sat, it merely belongs to the wrong `<g class="word">`. audit_width
flags a word the wrong SIZE, but a thief and its victim overlap, so both stay
within their share.

TWO AXES, because they fail on different thefts and together they close a
chain that either one alone leaves half-visible:

  CONTOURS  the number of separate closed outlines the word's bodies draw,
            counting counters/holes. Changes when a piece is added or lost.
  RUNS      the number of x-disjoint ink clusters. Changes when a piece is
            added or lost in a place that does not touch the rest.

Both are invariant under the print's justification -- a kashida stretches a
run, it never opens a hole and never splits or merges a cluster. INK AREA is
NOT invariant and was measured and rejected: مِن is drawn at area 191 most
times and at 536 when stretched, a 2.8x legitimate spread (see the report).

MEASURED, all 604 pages, 77,432 words, 21,201 distinct forms (2026-08-29),
degenerate contours excluded first (audit_nullink):

  forms seen 20+ times: 458.  36,082 occurrences of them.
    CONTOURS  419 forms (91.5%) draw ONE count always
              deviation: -1: 454   0: 35,391   +1: 237   (nothing beyond +-1)
              hapax (k=1): 8
    RUNS      300 forms (65.5%) draw ONE count always
              deviation: -2: 16  -1: 2,926   0: 32,782   +1: 358
              hapax (k=1): 19

    the minority count k, i.e. how many occurrences share the odd value
    (contours axis): k=1: 8  k=2: 4  k=3: 3  k=4: 4  k=5: 5  k=6: 18 ...
    share k/N of a k=1 hit: 0.0014 .. 0.0455, then a 0.030 gap to 0.0759

There is NO empty band in the integer deviation: this is a strong PRIOR, not a
proof, and it is reported as such. The band that does exist is in rarity, and
it is a shallow one, so the rule is the conservative end of it: MIN_N=20
occurrences and k==1 (a true hapax). That leaves 8 words in the whole mushaf,
down from 712 raw outliers -- and 33 of the raw ones were the null-contour
family, which is why the degenerate filter runs first.

SECOND SIGNAL. A stolen piece leaves a complementary hole: the thief is +1 and
the victim -1. Any flagged word that has a neighbour on the same page with the
opposite deviation is promoted to PAIRED, and a pair is close to proof (the
p384 27:78 chain -- وَهُوَ +1 contour, ٱلْعَلِيمُ -1 contour, and ٱلْعَزِيزُ
in the middle, which the CONTOURS axis cannot see at all because it lost its
own alif and gained the next word's for a net change of zero: only the RUNS
axis reports it, at 1 run where its other 45 occurrences draw 2. Confirmed by
reading the ink.)

KNOWN BLIND SPOT, measured, do not mistake a clean run for an absent defect.
This detector needs the form REPEATED, and the three body thefts Abdullah
confirmed by eye are on forms that barely repeat: غَالِبَ / بَعْدِهِۦۗ (p71)
occur twice each in the whole mushaf and يَحْزُنكَ (p413) five times, all
below MIN_N. Nothing here can see them. It covers the common vocabulary, which
is most of the book by occurrence and none of it by form.

Needs the FULL mushaf: the reference distribution is built from the pages
scanned, so a short range makes every form a hapax. The tool refuses to
believe itself on a range under 200 pages unless --force.

Usage: python3 tools/audit_formshape.py [start] [end] [jobs] [--hist] [--force]
"""
import json
import os
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

MIN_N = 20        # a form must be this common before an odd one out means much
MAX_K = 1         # ... and the odd count must be a true hapax
NULL_AREA = 0.5   # audit_nullink's empty band


def scan_page(pg):
    import assign_words as aw
    from svg_lines import transform_box
    cap = {}
    orig = aw.rewrite

    def spy(page, assignment):
        cap["p"] = page
        cap["a"] = assignment
        return orig(page, assignment)

    aw.rewrite = spy
    try:
        aw.assign_page("hafs/kfqc", pg, os.path.join(ROOT, ".cache", "words"))
    except Exception:
        return pg, []
    finally:
        aw.rewrite = orig
    if "a" not in cap:
        return pg, []
    page = cap["p"]
    rows = []
    for word, atoms in cap["a"]:
        if not word:
            continue
        n, xs, boxes = 0, [], []
        for at in atoms:
            for el in at["els"]:
                if el["kind"] != "body":
                    continue
                M = page.paths[el["path"]]["M"]
                alive = False
                for c in el["contours"]:
                    sp = c["sp"]
                    try:
                        b = transform_box(M, sp["xmin"], sp["ymin"],
                                          sp["xmax"], sp["ymax"])
                    except Exception:
                        n += 1
                        alive = True
                        continue
                    if (b[2] - b[0]) * (b[3] - b[1]) >= NULL_AREA:
                        n += 1
                        alive = True
                xs.append(el["x1"])
                if alive:
                    boxes.append((el["x1"], el["x2"]))
        # x-disjoint ink clusters ("runs"): merge overlapping spans, 0.6u of
        # slack so a hairline between two contours of one stroke is not a split
        runs, reach = 0, None
        for lo, hi in sorted(boxes):
            if reach is None or lo > reach + 0.6:
                runs += 1
                reach = hi
            else:
                reach = max(reach, hi)
        rows.append({
            "page": pg, "key": "%d:%d:%d" % (word["surah"], word["ayah"],
                                             word["pos"]),
            "form": word["uthmani"], "n": n, "runs": runs,
            "x": round(min(xs), 2) if xs else None,
        })
    return pg, rows


def main():
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    b = int(sys.argv[2]) if len(sys.argv) > 2 else 604
    jobs = int(sys.argv[3]) if len(sys.argv) > 3 else 32
    rows = []
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for pg, rr in ex.map(scan_page, range(a, b + 1)):
            rows.extend(rr)
    if b - a + 1 < 200 and "--force" not in sys.argv:
        print("audit_formshape needs the whole mushaf for its reference "
              "distribution (got %d pages). Re-run 1 604, or --force."
              % (b - a + 1))
        return

    order = defaultdict(list)
    for r in rows:
        order[r["page"]].append(r)
    for pg in order:
        order[pg].sort(key=lambda r: -(r["x"] if r["x"] is not None else 0))

    stats = {}
    for axis in ("n", "runs"):
        f = defaultdict(Counter)
        for r in rows:
            f[r["form"]][r[axis]] += 1
        stats[axis] = (f, {t: sum(c.values()) for t, c in f.items()},
                       {t: f[t].most_common(1)[0][0] for t in f})

    flags = []
    for axis, label in (("n", "CONTOURS"), ("runs", "RUNS")):
        f, total, mode = stats[axis]
        for r in rows:
            t = r["form"]
            if total[t] < MIN_N or r[axis] == mode[t]:
                continue
            if f[t][r[axis]] > MAX_K:
                continue
            dev = r[axis] - mode[t]
            # second signal: a neighbour on the page deviating the opposite way
            # on EITHER axis -- the thief is heavy where the victim is light
            page_rows = order[r["page"]]
            i = page_rows.index(r)
            mates = []
            for j in (i - 2, i - 1, i + 1, i + 2):
                if not 0 <= j < len(page_rows):
                    continue
                q = page_rows[j]
                for ax2 in ("n", "runs"):
                    f2, tot2, mode2 = stats[ax2]
                    if tot2.get(q["form"], 0) < MIN_N:
                        continue
                    d2 = q[ax2] - mode2[q["form"]]
                    if d2 and d2 * dev < 0:
                        mates.append({"key": q["key"], "form": q["form"],
                                      "axis": ax2, "dev": d2})
            flags.append({
                "page": r["page"], "key": r["key"], "form": t,
                "axis": label, "n": r[axis], "mode": mode[t], "dev": dev,
                "form_n": total[t], "spread": f[t].most_common(4),
                "paired_with": mates,
                # the RUNS axis has a MEASURED false-positive mode: how tightly
                # a line is set decides whether two neighbouring letters' boxes
                # touch, so a form set tight draws one run where it usually
                # draws two. Spot-checking four RUNS hits by ink gave three
                # kerning artefacts (p556 وَٱلْأَرْضَ, p271 ٱلنَّاسِ,
                # p604 وَمِن -- every piece merely overlapping its neighbour)
                # against one real theft (p384 ٱلْعَزِيزُ). So a bare RUNS
                # hapax is REVIEW, never a claim; only a complementary
                # neighbour lifts it.
                "grade": ("PAIRED" if mates
                          else ("REVIEW" if axis == "runs" else "HAPAX")),
            })

    print("audit_formshape  pages %d-%d" % (a, b))
    print("  words %d   distinct forms %d" % (len(rows), len(stats["n"][0])))
    for axis, label in (("n", "CONTOURS"), ("runs", "RUNS   ")):
        f, total, mode = stats[axis]
        common = [t for t in f if total[t] >= MIN_N]
        pure = sum(1 for t in common if len(f[t]) == 1)
        hist = Counter(r[axis] - mode[r["form"]]
                       for r in rows if total[r["form"]] >= MIN_N)
        print("  %s forms seen %d+ times %d, always the same: %d (%.1f%%)"
              % (label, MIN_N, len(common), pure,
                 100.0 * pure / max(1, len(common))))
        print("           deviation histogram: %s" % sorted(hist.items()))
    print("  FLAGS (hapax, k<=%d): %d   of which PAIRED: %d"
          % (MAX_K, len(flags), sum(1 for f in flags if f["paired_with"])))
    for fl in sorted(flags, key=lambda f: (f["axis"], -f["form_n"])):
        print("   %-8s p%-4d %-12s %-18s draws %d, the other %d times %d  [%s]"
              % (fl["axis"], fl["page"], fl["key"], fl["form"], fl["n"],
                 fl["form_n"] - 1, fl["mode"], fl["grade"]))
        for m in fl["paired_with"]:
            print("        pairs with %-12s %-16s %s dev %+d"
                  % (m["key"], m["form"], m["axis"], m["dev"]))
    if "--hist" in sys.argv:
        for axis in ("n", "runs"):
            f, total, mode = stats[axis]
            ks = Counter(f[r["form"]][r[axis]] for r in rows
                         if total[r["form"]] >= MIN_N
                         and r[axis] != mode[r["form"]])
            print("\n  %s minority-count k histogram: %s"
                  % (axis, sorted(ks.items())[:20]))
    p = os.path.join(ROOT, ".cache", "formshape.json")
    with open(p, "w") as f:
        json.dump({"range": [a, b], "min_n": MIN_N, "max_k": MAX_K,
                   "flags": flags}, f, ensure_ascii=False, indent=1)
    print("\n  wrote %s" % p)


if __name__ == "__main__":
    main()
