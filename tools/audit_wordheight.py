#!/usr/bin/env python3
"""Words TALLER than their line — the silhouette test for cross-line theft.

Abdullah (2026-08-28): words that stole a mark from the line above or below
resist every count and interval audit, but their SILHOUETTE gives them away —
the word's total vertical extent (letters plus every mark it holds) pokes out
of its line. One number per word: extent / median extent of the words on its
own line. No line tags, no budgets, no band edges — just height.

Usage: python3 tools/audit_wordheight.py [start] [end] [jobs] [--hist]
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))


def scan_page(pg):
    if not hasattr(scan_page, "_raw"):
        scan_page._raw = {}
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
    except Exception:
        return pg, [], []
    finally:
        aw.rewrite = orig
    if "a" not in cap:
        return pg, [], []
    # group words by drawn line: cluster on body-top
    words = []
    wrecs = []
    for word, atoms in cap["a"]:
        if not word:
            continue
        els = [e for a in atoms for e in a["els"]]
        if not els:
            continue
        bods = [e for e in els if e["kind"] == "body"]
        if not bods:
            continue
        btop = min(e["y1"] for e in bods)
        ext_top = min(e["y1"] for e in els)
        ext_bot = max(e["y2"] for e in els)
        key = "%d:%d:%d" % (word["surah"], word["ayah"], word["pos"])
        words.append((btop, ext_bot - ext_top, key, word["uthmani"]))
        wrecs.append((btop, key, word["uthmani"], els))
        scan_page._raw.setdefault(pg, []).append(
            (key, word["uthmani"], ext_bot - ext_top))
    if not words:
        return pg, [], []
    words.sort()
    # cluster into lines by body-top jumps > 20u
    lines, cur = [], [words[0]]
    for w in words[1:]:
        if w[0] - cur[-1][0] > 20.0:
            lines.append(cur)
            cur = []
        cur.append(w)
    lines.append(cur)
    flags, hist = [], []
    # the print's own line grid is the ruler (Abdullah 2026-08-28: "we
    # already have the line height — add 5% and call it a day"): the pitch
    # is the median distance between consecutive line clusters, and no
    # word's ink may stand taller than one pitch + 5%.
    tops = [ln[0][0] for ln in lines if ln]
    gaps = sorted(b - a for a, b in zip(tops, tops[1:]) if b - a > 20.0)
    pitch = gaps[len(gaps) // 2] if gaps else None
    if pitch:
        lim = pitch * 1.05
        for ln in lines:
            for _, h, key, txt in ln:
                hist.append(round(h / pitch, 2))
                if h > lim:
                    flags.append((key, txt, round(h / pitch, 2),
                                  round(h, 1), round(pitch, 1)))
    return pg, flags, hist


def main2(lo, hi, jobs):
    """Two-pass form: every word-form's heights mushaf-wide, then flag the
    words that deviate from their OWN form's median (Abdullah 2026-08-28:
    a compact word is compact everywhere — ما against ما, not against its
    line)."""
    from collections import defaultdict
    forms = defaultdict(list)
    rows = []
    with ProcessPoolExecutor(jobs) as ex:
        for pg, flags, hist, raw in ex.map(scan_raw, range(lo, hi + 1)):
            for key, txt, h in raw:
                forms[txt].append(h)
                rows.append((pg, key, txt, h))
    allf = {}
    for pg, key, txt, h in rows:
        hs = sorted(forms[txt])
        if len(hs) < 5:
            continue
        med = hs[len(hs) // 2]
        if med <= 0:
            continue
        r = h / med
        if r > 1.45 or r < 0.62:
            allf.setdefault(pg, []).append(
                (key, txt, round(r, 2), round(h, 1), round(med, 1)))
    total = sum(len(v) for v in allf.values())
    print("FORM pass %d-%d | words flagged %d on %d pages (forms with 5+ "
          "occurrences)" % (lo, hi, total, len(allf)))
    for pg in sorted(allf):
        for key, txt, r, h, med in allf[pg]:
            print("  p%d %s %s: %.2fx its own form (%.0fu vs %.0fu)"
                  % (pg, key, txt, r, h, med))
    out = os.path.join(ROOT, ".cache", "wordheight_form.json")
    json.dump({str(p): v for p, v in allf.items()}, open(out, "w"),
              ensure_ascii=False, indent=1)
    print("wrote", out)


def scan_raw(pg):
    pg, flags, hist = scan_page(pg)
    raw = getattr(scan_page, "_raw", {}).pop(pg, [])
    return pg, flags, hist, raw


def main():
    a = sys.argv[1:]
    lo = int(a[0]) if a else 1
    hi = int(a[1]) if len(a) > 1 else lo
    jobs = int(a[2]) if len(a) > 2 else 14
    hist_mode = "--hist" in a
    if "--form" in a:
        return main2(lo, hi, jobs)
    allf, H = {}, []
    with ProcessPoolExecutor(jobs) as ex:
        for pg, flags, hist in ex.map(scan_page, range(lo, hi + 1)):
            if flags:
                allf[pg] = flags
            H += hist
    if hist_mode and H:
        H.sort()
        n = len(H)
        print("height/line-median: n=%d med=%.2f p90=%.2f p99=%.2f "
              "p99.9=%.2f max=%.2f"
              % (n, H[n // 2], H[9 * n // 10], H[99 * n // 100],
                 H[999 * n // 1000], H[-1]))
    total = sum(len(v) for v in allf.values())
    print("pages %d-%d | words flagged %d on %d pages"
          % (lo, hi, total, len(allf)))
    for pg in sorted(allf):
        for key, txt, r, h, med in allf[pg]:
            print("  p%d %s %s: %.2fx its line (%.0fu vs median %.0fu)"
                  % (pg, key, txt, r, h, med))
    out = os.path.join(ROOT, ".cache", "wordheight.json")
    json.dump({str(p): v for p, v in allf.items()}, open(out, "w"),
              ensure_ascii=False, indent=1)
    print("wrote", out)


if __name__ == "__main__":
    main()
