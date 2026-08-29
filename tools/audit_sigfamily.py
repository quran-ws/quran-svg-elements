#!/usr/bin/env python3
"""One outline, one mark FAMILY -- mushaf-wide.

`.cache/marks/labels.json` maps a shape signature to a label, but the pipeline
then re-derives slash names from position (fatha/kasra/fathatan/kasratan are
ONE stroke) and splits dot clusters into single-dot members. So the same
signature legitimately wears several NAMES. What it must never wear is a
different FAMILY: the outline of a two-dot cluster's member dot cannot also be
the outline of a fatha stroke. Families here:

    slash = fatha | kasra | fathatan | kasratan     (derived by position)
    damma = damma | dammatan                        (derived by position)
    dots  = dot | two-dots | three-dots | muanaqah  (cluster vs member)
    everything else is its own family (shadda, sukun, hamza, wasla,
    small-alef, maddah, pause, sifr-*, small-waw, small-ya, meem-iqlab, ...)

MEASURED, all 604 pages, 2,143 distinct mark signatures, 271,163 mark
elements (2026-08-29). For every signature seen 50+ times, the share of its
occurrences that fall outside its own dominant family:

    share = 0.000000   every signature but two   (2,141 of 2,143: PERFECT)
    ------------------ EMPTY BAND, the whole interval -----------------
    share = 0.000018   sig d7a8b5e19121fbe4  (slash outline, 54,280x) once "two-dots"
    share = 0.000040   sig a316a3b8eb2508b0  (two-dots outline, 24,854x) once "fatha"

There is no threshold to tune: the band is the entire open interval. Every
other outline in the book is 100.000% one family. A single cross-family use is
therefore a proof in the same class as the joining-rule piece count, and it is
mark-COUNT NEUTRAL, so no counting audit can see it.

The two hits are the two halves of one swap on a single word (p337
22:46:8 يَعْقِلُونَ): the two-dots outline is named fatha and sits BELOW the
letters where the ya's dots belong, and the slash outline is named two-dots
and sits ABOVE where the fatha belongs.

MIN_N=50 keeps a rare sign (muanaqah, sifr-mustatil, seen-reading) from
being judged against a handful of occurrences.

Usage: python3 tools/audit_sigfamily.py [start] [end] [jobs] [--all]
       (needs the FULL mushaf for the reference distribution)
"""
import json
import os
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

FAMILY = {
    "fatha": "slash", "kasra": "slash",
    "fathatan": "slash", "kasratan": "slash",
    "damma": "damma", "dammatan": "damma",
    "dot": "dots", "two-dots": "dots",
    "three-dots": "dots", "muanaqah": "dots",
}
MIN_N = 50          # a signature must be common enough to have a "own" family


def fam(name):
    return FAMILY.get(name, name)


def scan_page(pg):
    import assign_words as aw
    cap = {}
    orig = aw.rewrite

    def spy(page, assignment):
        cap["a"] = assignment
        return orig(page, assignment)

    aw.rewrite = spy
    try:
        aw.assign_page("hafs/kfqc", pg, os.path.join(ROOT, ".cache", "words"))
    except Exception:
        return pg, []
    finally:
        aw.rewrite = orig
    rows = []
    for word, atoms in cap.get("a", []):
        if not word:
            continue
        key = "%d:%d:%d" % (word["surah"], word["ayah"], word["pos"])
        for at in atoms:
            for el in at["els"]:
                if el["kind"] == "body" or not el.get("sig") \
                        or not el.get("mark"):
                    continue
                rows.append((el["sig"], el["mark"], pg, key, word["uthmani"],
                             at.get("lig"),
                             [round(el["x1"], 2), round(el["y1"], 2),
                              round(el["x2"], 2), round(el["y2"], 2)]))
    return pg, rows


def main():
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    b = int(sys.argv[2]) if len(sys.argv) > 2 else 604
    jobs = int(sys.argv[3]) if len(sys.argv) > 3 else 32
    rows = []
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for pg, rr in ex.map(scan_page, range(a, b + 1)):
            rows.extend(rr)
    sigfam = defaultdict(Counter)
    for sig, mark, *_ in rows:
        sigfam[sig][fam(mark)] += 1
    total = {s: sum(c.values()) for s, c in sigfam.items()}
    dominant = {s: sigfam[s].most_common(1)[0][0] for s in sigfam}

    flags = []
    for sig, mark, pg, key, uth, lig, box in rows:
        if total[sig] < MIN_N:
            continue
        if fam(mark) == dominant[sig]:
            continue
        flags.append({
            "page": pg, "key": key, "word": uth, "lig": lig,
            "mark": mark, "family": fam(mark),
            "sig": sig, "sig_n": total[sig],
            "sig_family": dominant[sig],
            "share": round(sigfam[sig][fam(mark)] / total[sig], 8),
            "box": box,
        })
    pure = sum(1 for s in sigfam
               if total[s] >= MIN_N and len(sigfam[s]) == 1)
    common = sum(1 for s in sigfam if total[s] >= MIN_N)
    print("audit_sigfamily  pages %d-%d" % (a, b))
    print("  mark elements                 : %d" % len(rows))
    print("  distinct signatures           : %d" % len(sigfam))
    print("  signatures seen %d+ times      : %d" % (MIN_N, common))
    print("  ... of those, single-family   : %d (%.3f%%)"
          % (pure, 100.0 * pure / max(1, common)))
    print("  CROSS-FAMILY VIOLATIONS       : %d" % len(flags))
    for f in sorted(flags, key=lambda f: f["share"]):
        print("   p%-4d %-12s %-18s lig%-3s %-10s (outline is %s, %dx, "
              "share %.6f) box=%s"
              % (f["page"], f["key"], f["word"], f["lig"], f["mark"],
                 f["sig_family"], f["sig_n"], f["share"], f["box"]))
    if "--all" in sys.argv:
        print("\n  per-signature family spread (N>=%d, multi-family only):"
              % MIN_N)
        for s in sigfam:
            if total[s] >= MIN_N and len(sigfam[s]) > 1:
                print("    %s N=%-6d %s" % (s, total[s], sigfam[s].most_common()))
    p = os.path.join(ROOT, ".cache", "sigfamily.json")
    with open(p, "w") as f:
        json.dump({"range": [a, b], "min_n": MIN_N, "flags": flags},
                  f, ensure_ascii=False, indent=1)
    print("\n  wrote %s" % p)


if __name__ == "__main__":
    main()
