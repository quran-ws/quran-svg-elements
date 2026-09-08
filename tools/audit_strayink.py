"""Ink held by a word whose letters are nowhere near it, HORIZONTALLY.

The distance from a mark to the nearest letter of the word holding it is bimodal with
an empty band: 2,735 marks within 2u, two between 20 and 40, nothing at all between
40 and 150, then 17 at 280-308 — a full line width. Those 17 are one defect, the word
at one end of a line holding a mark drawn at the other, because the last word of a
line and the first of the next are neighbours in READING order.

    python3 tools/audit_strayink.py 1 604 8 out.json
"""
import sys, os, io, contextlib, importlib.util, json
from collections import Counter
ROOT = os.environ["QSVG_ROOT"]
sys.path.insert(0, os.path.join(ROOT, "tools"))

def _load():
    sp = importlib.util.spec_from_file_location("assign_words", os.path.join(ROOT,"tools","assign_words.py"))
    aw = importlib.util.module_from_spec(sp); sys.modules["assign_words"] = aw; sp.loader.exec_module(aw)
    return aw

AW = None; CAP = {}
def page(pg):
    global AW
    if AW is None:
        AW = _load()
        _o = AW.rewrite
        def spy(p, a): CAP["a"] = a; return _o(p, a)
        AW.rewrite = spy
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            AW.assign_page("hafs/kfqc", pg, os.path.join(ROOT, ".cache", "words"))
    except Exception as e:
        return pg, [], "%s: %s" % (type(e).__name__, e)
    out = []
    W = []
    for w, at in CAP["a"]:
        if not w: continue
        els = [e for a in at for e in a["els"]]
        b = [e for e in els if e["kind"] == "body"]
        if not b: continue
        W.append((w, els, b))
    boxes = [(min(e["x1"] for e in b), max(e["x2"] for e in b), b[0].get("line"),
              "%d:%d:%d" % (w["surah"], w["ayah"], w["pos"]), w["rasm_uthmani"]) for w, _, b in W]
    for w, els, b in W:
        for e in els:
            if e["kind"] == "body" or e.get("mkpart"): continue
            gap = -max((min(x["x2"], e["x2"]) - max(x["x1"], e["x1"])) for x in b)
            if gap <= 0: continue
            cx = (e["x1"] + e["x2"]) / 2.0
            ln = b[0].get("line")
            over = [t for x1, x2, l, k, t in boxes if l == ln and x1 - 1 <= cx <= x2 + 1]
            out.append((round(gap, 1), e.get("mark") or e["kind"],
                        "%d:%d:%d" % (w["surah"], w["ayah"], w["pos"]), w["rasm_uthmani"],
                        bool(over)))
    return pg, out, None

if __name__ == "__main__":
    from multiprocessing import Pool
    a, b, j = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    rows, errs = [], 0
    with Pool(j, maxtasksperchild=8) as pool:
        for pg, out, err in pool.imap_unordered(page, range(a, b + 1)):
            if err: errs += 1; continue
            rows += [(pg,) + r for r in out]
    print("pages failed: %d   marks clear of their own word: %d" % (errs, len(rows)))
    gaps = sorted(r[1] for r in rows)
    import bisect as _b
    print("\ngap (units clear of the word's own ink):")
    for lo, hi in ((0,2),(2,5),(5,10),(10,20),(20,40),(40,80),(80,150),(150,10000)):
        n = _b.bisect_left(gaps, hi) - _b.bisect_left(gaps, lo)
        print("   %5s - %-5s %6d  %5.1f%%" % (lo, hi, n, 100.0*n/max(1,len(gaps))))
    print("\nby family, marks more than 40u clear:")
    for k, n in Counter(r[2] for r in rows if r[1] > 40).most_common(12):
        print("   %-14s %4d" % (k, n))
    far = sorted([r for r in rows if r[1] > 40], key=lambda r: -r[1])
    print("\nworst 25:")
    for pg, g, m, k, t, over in far[:25]:
        print("   p%-4d %-11s %-16s %-11s %7.1fu  %s" % (pg, k, t, m, g,
              "lands over a word on its line" if over else "lands over nothing"))
    json.dump([list(r) for r in far], open(sys.argv[4], "w"), ensure_ascii=False)
    print("\nwrote %s (%d rows over 40u)" % (sys.argv[4], len(far)))
