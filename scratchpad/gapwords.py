"""The exact words behind our two remaining deficits: piece surplus and wrong dots.

Uses score_both's own definitions so the list matches the scoreboard: pieces are
connected x-runs of body ink (join 0.4), dot units exclude a welded twin.
"""
import sys, os, io, contextlib, importlib.util, json
from collections import Counter
ROOT = os.environ["QSVG_ROOT"]
sys.path.insert(0, os.path.join(ROOT, "tools"))
import score_both as SB                                              # noqa: E402
AW = SB.aw
CAP = {}
_o = AW.rewrite
AW.rewrite = lambda p, a: (CAP.__setitem__("a", a), _o(p, a))[1]

def page(pg):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            AW.assign_page("hafs/kfqc", pg, os.path.join(ROOT, ".cache", "words"))
    except Exception as e:
        return pg, [], []
    piece, dots = [], []
    for w, at in CAP["a"]:
        if not w: continue
        els = [e for a in at for e in a["els"]]
        b = [e for e in els if e["kind"] == "body"]
        if not b: continue
        runs = SB._groups([(e["x1"], e["x2"]) for e in b])
        allowed = max(1, len(AW.segment_word(w["uthmani"])))
        if runs > allowed:
            piece.append((pg, "%d:%d:%d" % (w["surah"], w["ayah"], w["pos"]),
                          w["uthmani"], runs, allowed))
        got = 0
        for e in els:
            if e.get("mkpart"): continue
            m = e.get("mark") or ""
            got += {"dot": 1, "two-dots": 2, "three-dots": 3}.get(m, 0)
        want = AW.dot_budget(w["uthmani"])
        if got != want:
            dots.append((pg, "%d:%d:%d" % (w["surah"], w["ayah"], w["pos"]),
                         w["uthmani"], got, want))
    return pg, piece, dots

if __name__ == "__main__":
    from multiprocessing import Pool
    P, D = [], []
    with Pool(int(sys.argv[3]), maxtasksperchild=8) as pool:
        for pg, p, d in pool.imap_unordered(page, range(int(sys.argv[1]), int(sys.argv[2]) + 1)):
            P += p; D += d
    print("PIECE SURPLUS — %d words (draw more runs of ink than the spelling allows)" % len(P))
    for pg, k, t, r, a in sorted(P):
        print("   p%-4d %-11s %-18s %d runs, %d allowed" % (pg, k, t, r, a))
    print("\nDOTS WRONG — %d words" % len(D))
    for pg, k, t, g, w in sorted(D):
        print("   p%-4d %-11s %-18s holds %d, spells %d" % (pg, k, t, g, w))
    json.dump({"pieces": P, "dots": D}, open(sys.argv[4], "w"), ensure_ascii=False, indent=1)
