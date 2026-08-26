"""Ink held by a word but drawn in ANOTHER LINE'S BAND.

The vertical counterpart of audit_strayink. 4,203 marks sit between 5 and 10 units
outside their word's line band and only 26 between 10 and 15 — a 160x cliff — so ten
units is the whole of what a mark legitimately does vertically.

This is also why the orphan pass tests POSITION rather than an element's `line` tag:
the tag is wrong exactly where it matters, on marks that hang low at a line edge.

    python3 tools/audit_crossband.py 1 604 8 out.json
"""
import sys, os, io, contextlib, importlib.util, json
from collections import Counter
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
        return pg, [], Counter({"page-error": 1})
    W = []
    for w, at in CAP["a"]:
        if not w: continue
        els = [e for a in at for e in a["els"]]
        b = [e for e in els if e["kind"] == "body"]
        if not b: continue
        ln = [e.get("line") for e in b if e.get("line")]
        W.append({"k": "%d:%d:%d" % (w["surah"], w["ayah"], w["pos"]), "t": w["uthmani"],
                  "ln": max(set(ln), key=ln.count) if ln else 0, "els": els, "b": b,
                  "y1": min(e["y1"] for e in b), "y2": max(e["y2"] for e in b)})
    # line bands from the body ink of every word on the line
    band = {}
    for x in W:
        lo, hi = band.get(x["ln"], (1e9, -1e9))
        band[x["ln"]] = (min(lo, x["y1"]), max(hi, x["y2"]))
    out = []; c = Counter()
    for x in W:
        lo, hi = band[x["ln"]]
        for e in x["els"]:
            if e["kind"] == "body" or e.get("mkpart") or e.get("standalone"): continue
            cy = (e["y1"] + e["y2"]) / 2
            # distance OUTSIDE its own line's band
            d = max(lo - cy, cy - hi, 0.0)
            c["marks"] += 1
            if d <= 0: continue
            out.append((pg, round(d, 1), e.get("mark") or e["kind"], x["k"], x["t"],
                        x["ln"], e.get("line"), round(e["x1"], 1), round(e["x2"], 1),
                        round((e["x2"] - e["x1"]) * (e["y2"] - e["y1"]), 1)))
    return pg, out, c
if __name__ == "__main__":
    from multiprocessing import Pool
    rows = []; tot = Counter()
    with Pool(int(sys.argv[3]), maxtasksperchild=8) as pool:
        for pg, out, c in pool.imap_unordered(page, range(int(sys.argv[1]), int(sys.argv[2]) + 1)):
            rows += out; tot.update(c)
    ds = sorted(r[1] for r in rows)
    print("marks examined %d | outside their own line's band %d (%.3f%%)"
          % (tot["marks"], len(ds), 100.0 * len(ds) / max(1, tot["marks"])))
    import bisect
    print("\nunits BELOW/ABOVE the band its word's letters occupy:")
    for lo, hi in ((0,2),(2,5),(5,10),(10,15),(15,20),(20,30),(30,50),(50,10000)):
        n = bisect.bisect_left(ds, hi) - bisect.bisect_left(ds, lo)
        print("   %5s - %-6s %5d" % (lo, hi, n))
    far = sorted([r for r in rows if r[1] > 10], key=lambda r: -r[1])
    print("\n%d marks more than 10u outside; by family:" % len(far))
    for k, n in Counter(r[2] for r in far).most_common(10):
        print("   %-14s %4d" % (k, n))
    print("\nlargest 25 by AREA (a big blob is a letter, not a mark):")
    for r in sorted(far, key=lambda r: -r[9])[:25]:
        print("   p%-4d %-11s %-16s %-11s %5.1fu out  line %s vs tag %s  area %6.1f  x %.1f-%.1f"
              % (r[0], r[3], r[4], r[2], r[1], r[5], r[6], r[9], r[7], r[8]))
    json.dump([list(r) for r in far], open(sys.argv[4], "w"), ensure_ascii=False)
    print("\nwrote %s" % sys.argv[4])
