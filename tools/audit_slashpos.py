#!/usr/bin/env python3
"""Slash marks named AGAINST their drawn position.

fathah/kasrah (and their tanwin doubles) are one stroke; the pipeline derives
the name from position and budget. When a word's budget has no room for what
position says (p97 أَوْ: budget wants one fathah, zero kasrahs, so the stroke
drawn BELOW the letters was forced to be called fathah), the wrong name
survives every counting audit — the count is exactly what the text allows.
Position cannot be forced: a "fathah" drawn clear under its word's letter band,
or a "kasrah" riding clear above it, is either a mis-named stroke or a stolen
neighbour's mark. Both need eyes or an ownership pass, and neither is visible
to any other audit (Abdullah, 2026-08-28, the p97 e79 find).

Uses the pipeline's transformed coordinates (raw SVG d-strings live in
per-path local frames whose y flips — a regex scan reports 113k false hits).

Usage: python3 tools/audit_slashpos.py [start] [end] [jobs] [--hist]
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

ABOVE = ("fathah", "tanwin_al_fath")
BELOW = ("kasrah", "tanwin_al_kasr")


def scan_page(pg):
    import assign_words as aw
    cap = {}
    orig = aw.rewrite
    def spy(page, assignment):
        cap["a"] = assignment
        return orig(page, assignment)
    aw.rewrite = spy
    try:
        aw.assign_page("hafs/kfqc", pg,
                       os.path.join(ROOT, ".cache", "words"))
    except Exception as exc:
        return pg, [("CRASH", "", "", 0, str(exc)[:120])], []
    finally:
        aw.rewrite = orig
    if "a" not in cap:
        return pg, [], []
    cap = cap["a"]
    flags, hist = [], []
    for word, atoms in cap:
        if not word:
            continue
        els = [e for a in atoms for e in a["els"]]
        bods = [e for e in els if e["kind"] == "body"]
        if not bods:
            continue
        top = min(e["y1"] for e in bods)
        bot = max(e["y2"] for e in bods)
        for e in els:
            mk = e.get("mark")
            if mk not in ABOVE + BELOW or e.get("mkpart"):
                continue
            cy = (e["y1"] + e["y2"]) / 2
            # off > 0: the mark sits below the letter band's bottom;
            # off < 0 above the top; inside the band = 0
            off = cy - bot if cy > bot else (cy - top if cy < top else 0.0)
            hist.append((mk, round(off, 1)))
            key = "%d:%d:%d" % (word["surah"], word["ayah"], word["pos"])
            if mk in ABOVE and off > 2.0:
                flags.append((key, word["rasm_uthmani"], mk, round(off, 1),
                              "named %s, drawn %.1fu BELOW the letters"
                              % (mk, off)))
            elif mk in BELOW and off < -2.0:
                flags.append((key, word["rasm_uthmani"], mk, round(off, 1),
                              "named %s, drawn %.1fu ABOVE the letters"
                              % (mk, -off)))
    # SIDE-ORDER law (Abdullah 2026-08-28 23:09, refined): above-marks
    # (fathah/dammah) and below-marks (kasrah) each keep the TEXT's order
    # right-to-left; the first letter's harakah is rightmost ON ITS SIDE and
    # the last letter's leftmost on its side. Sides are not compared to
    # each other — a kasrah legitimately tucks under the ligature join.
    HK = {"\u064e": "fathah", "\u0650": "kasrah", "\u064f": "dammah"}
    for word, atoms in cap:
        if not word:
            continue
        txt = word["rasm_uthmani"]
        els = [e for a in atoms for e in a["els"]]
        seq = [HK[c] for c in txt if c in HK]
        above_txt = [f for f in seq if f in ("fathah", "dammah")]
        below_txt = [f for f in seq if f == "kasrah"]
        above = sorted([e for e in els if e.get("mark") in
                        ("fathah", "dammah") and not e.get("mkpart")],
                       key=lambda e: -(e["x1"] + e["x2"]))
        below = sorted([e for e in els if e.get("mark") == "kasrah"
                        and not e.get("mkpart")],
                       key=lambda e: -(e["x1"] + e["x2"]))
        key = "%d:%d:%d" % (word["surah"], word["ayah"], word["pos"])
        for side, want, have in (("above", above_txt, above),
                                 ("below", below_txt, below)):
            if len(want) != len(have) or len(want) < 2:
                continue        # counts differ -> other audits' domain
            got = [e.get("mark") for e in have]
            if got != want:
                flags.append((key, txt, got[0], 0.0,
                              "%s-marks drawn order %s but the text says %s"
                              % (side, ">".join(got), ">".join(want))))
    return pg, flags, hist


def main():
    a = sys.argv[1:]
    lo = int(a[0]) if a else 1
    hi = int(a[1]) if len(a) > 1 else lo
    jobs = int(a[2]) if len(a) > 2 else 14
    hist_mode = "--hist" in a
    allf, allh = {}, []
    with ProcessPoolExecutor(jobs) as ex:
        for pg, flags, hist in ex.map(scan_page, range(lo, hi + 1)):
            if flags:
                allf[pg] = flags
            allh += hist
    if hist_mode:
        from collections import Counter
        for fam in ABOVE + BELOW:
            offs = sorted(o for m, o in allh if m == fam)
            if not offs:
                continue
            n = len(offs)
            print("%s n=%d  p1=%.1f p25=%.1f med=%.1f p75=%.1f p99=%.1f "
                  "min=%.1f max=%.1f"
                  % (fam, n, offs[n // 100], offs[n // 4], offs[n // 2],
                     offs[3 * n // 4], offs[99 * n // 100],
                     offs[0], offs[-1]))
    total = sum(len(v) for v in allf.values())
    print("pages %d-%d | words flagged %d on %d pages" % (lo, hi, total,
                                                          len(allf)))
    for pg in sorted(allf):
        for key, txt, mk, off, why in allf[pg]:
            print("  p%d %s %s: %s" % (pg, key, txt, why))
    out = os.path.join(ROOT, ".cache", "slashpos.json")
    json.dump({str(p): v for p, v in allf.items()}, open(out, "w"),
              ensure_ascii=False, indent=1)
    print("wrote", out)


if __name__ == "__main__":
    main()
