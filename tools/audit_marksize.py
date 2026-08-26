"""A mark the wrong SIZE for what it is called.

The art draws one glyph per mark, so each family's drawn area is a point, not a
range: over all 604 pages sukun is 13.0 at both the median and the 99th percentile,
damma 35.4/35.4, wasla 22.6/22.6. Anything outside a third to three times the median
is therefore not that mark, and only 46 elements in the whole mushaf are.

BOTH tails matter. The high tail is a letter read as a mark — five fathas of area
~80.4 against a median of 25.1, each one a word's missing letter. The low tail is a
mark from somewhere else: Abdullah found `الصالحات` on p590 holding a "kasra" of area
4.4 where its own two kasras are 21, a dot from the line below.

    python3 tools/audit_marksize.py 1 604 8 out.json
"""
import sys, os, io, contextlib, importlib.util, json
from collections import defaultdict, Counter
ROOT = os.environ["QSVG_ROOT"]
AW = None; CAP = {}
def page(pg):
    global AW
    if AW is None:
        sp = importlib.util.spec_from_file_location("assign_words", os.path.join(ROOT,"tools","assign_words.py"))
        AW = importlib.util.module_from_spec(sp); sys.modules["assign_words"] = AW; sp.loader.exec_module(AW)
        _o = AW.rewrite; AW.rewrite = lambda p, a: (CAP.__setitem__("a", a), _o(p, a))[1]
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            AW.assign_page("hafs/kfqc", pg, os.path.join(ROOT, ".cache", "words"))
    except Exception:
        return pg, []
    out = []
    for w, at in CAP["a"]:
        if not w: continue
        for e in [x for a in at for x in a["els"]]:
            if e["kind"] == "body" or e.get("mkpart") or e.get("standalone"): continue
            fam = e.get("mark")
            if not fam: continue
            out.append((fam, round((e["x2"]-e["x1"])*(e["y2"]-e["y1"]), 2), pg,
                        "%d:%d:%d" % (w["surah"], w["ayah"], w["pos"]), w["uthmani"],
                        round(e["x1"],1), round(e["y1"],1)))
    return pg, out
if __name__ == "__main__":
    from multiprocessing import Pool
    by = defaultdict(list)
    with Pool(int(sys.argv[3]), maxtasksperchild=8) as pool:
        for pg, out in pool.imap_unordered(page, range(int(sys.argv[1]), int(sys.argv[2])+1)):
            for fam, a, p, k, t, x, y in out:
                by[fam].append((a, p, k, t, x, y))
    print("%-14s %7s %8s %8s %8s %8s %8s   %s"
          % ("family","n","median","p99","max","med*3","big/small","biggest"))
    flag = []
    for fam in sorted(by, key=lambda f: -len(by[f])):
        rows = sorted(by[fam])
        n = len(rows)
        med = rows[n//2][0]; p99 = rows[min(n-1, int(n*0.99))][0]; mx = rows[-1][0]
        # BOTH tails. Abdullah found `ٱلصَّـٰلِحَـٰتِ` on p590 holding a "kasra" of area
        # 4.4 where every real kasra in the same word is 21 — a dot from another line,
        # labelled a kasra. A mark too SMALL for its family is as impossible as one too
        # big, and only the high tail was being looked at.
        over = [r for r in rows if r[0] > 3*med or r[0] < med/3.0]
        flag += [(fam,)+r for r in over]
        lo = [r for r in rows if r[0] < med/3.0]
        print("%-14s %7d %8.1f %8.1f %8.1f %8.1f %5d/%-5d p%-4d %s %s"
              % (fam, n, med, p99, mx, 3*med, len(over)-len(lo), len(lo),
                 rows[-1][1], rows[-1][2], rows[-1][3]))
    print("\nmarks outside a third to three times their family's median size: %d" % len(flag))
    flag.sort(key=lambda r: -r[1])
    for fam, a, p, k, t, x, y in flag[:30]:
        print("   p%-4d %-11s %-16s %-12s area %6.1f   at x %.1f y %.1f" % (p, k, t, fam, a, x, y))
    json.dump([list(r) for r in flag], open(sys.argv[4], "w"), ensure_ascii=False)
    print("\nwrote %s" % sys.argv[4])
