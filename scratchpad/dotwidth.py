"""The drawn WIDTH of every dot element, and the degenerate ones."""
import sys, os, io, contextlib, importlib.util, json
from collections import Counter
ROOT = os.environ["QSVG_ROOT"]
AW = None; CAP = {}
U = {"dot": 1, "two-dots": 2, "three-dots": 3}
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
        els = [e for a in at for e in a["els"]]
        held = sum(U.get(e.get("mark") or "", 0) for e in els if not e.get("mkpart"))
        want = AW.dot_budget(w["uthmani"])
        for e in els:
            if (e.get("mark") or "") not in U: continue
            out.append((round(e["x2"]-e["x1"], 3), e["mark"], pg,
                        "%d:%d:%d" % (w["surah"], w["ayah"], w["pos"]), w["uthmani"],
                        held - want, bool(e.get("mkpart"))))
    return pg, out
if __name__ == "__main__":
    from multiprocessing import Pool
    rows = []
    with Pool(int(sys.argv[3]), maxtasksperchild=8) as pool:
        for pg, out in pool.imap_unordered(page, range(int(sys.argv[1]), int(sys.argv[2])+1)):
            rows += out
    ws = sorted(r[0] for r in rows)
    print("dot elements: %d" % len(ws))
    import bisect
    print("\nwidth:")
    for lo, hi in ((0,0.5),(0.5,1.0),(1.0,1.5),(1.5,2.0),(2.0,2.5),(2.5,3.5),(3.5,4.5),(4.5,6.0),(6.0,99)):
        n = bisect.bisect_left(ws, hi) - bisect.bisect_left(ws, lo)
        print("   %4.1f - %-4.1f %7d" % (lo, hi, n))
    deg = [r for r in rows if r[0] < 0.5]
    print("\ndegenerate (< 0.5u wide): %d" % len(deg))
    print("   of those, in a word holding TOO MANY dots: %d"
          % sum(1 for r in deg if r[5] > 0))
    print("   in a word whose dots are exactly right:    %d"
          % sum(1 for r in deg if r[5] == 0))
    print("   in a word holding too FEW dots:            %d"
          % sum(1 for r in deg if r[5] < 0))
    for r in sorted(deg)[:20]:
        print("   p%-4d %-11s %-18s %-10s w %.3f  word delta %+d%s"
              % (r[2], r[3], r[4], r[1], r[0], r[5], "  [mkpart]" if r[6] else ""))
    json.dump([list(r) for r in deg], open(sys.argv[4], "w"), ensure_ascii=False)
