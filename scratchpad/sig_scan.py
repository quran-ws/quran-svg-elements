#!/usr/bin/env python3
"""How many distinct SHAPES sit behind the remaining flags?

Every path carries a data-sig outline hash, and .cache/marks/labels.json maps
a signature to a label for the whole mushaf. So a flag caused by a mislabelled
shape costs ONE human decision, however many times it occurs. This counts the
signatures on the marks of every flagged word, so the manual queue can be
ordered by how many flags each decision would settle.
"""
import io, contextlib, json, os, sys
from collections import Counter, defaultdict
S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, S)
import audit_marks as AM

LAB = json.load(open(AM.ROOT + "/.cache/marks/labels.json"))


def scan(pg):
    aw = AM._load()
    cap = {}
    orig = aw.rewrite
    def spy(page, a):
        cap["a"] = a
        return orig(page, a)
    aw.rewrite = spy
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            aw.assign_page("hafs/kfqc", pg, AM.ROOT + "/.cache/words")
    except Exception as e:
        return pg, []
    _, rows = AM.scan(pg)
    bad = {r[0] for r in rows}
    fam_of = {r[0]: tuple(sorted({b[0] for b in r[2]})) for r in rows}
    out = []
    for w, at in cap["a"]:
        if not w:
            continue
        key = "%d:%d:%d" % (w["surah"], w["ayah"], w["pos"])
        if key not in bad:
            continue
        for a in at:
            for e in a["els"]:
                sg = e.get("sig")
                if not sg:
                    continue
                out.append({"page": pg, "key": key, "sig": sg,
                            "mark": e.get("mark"), "kind": e["kind"],
                            "fams": fam_of[key],
                            "known": LAB.get(sg, {}).get("label"),
                            "auto": LAB.get(sg, {}).get("auto")})
    return pg, out


if __name__ == "__main__":
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    b = int(sys.argv[2]) if len(sys.argv) > 2 else 604
    from multiprocessing import Pool
    allr = []
    with Pool(2, maxtasksperchild=6) as pool:
        for pg, rows in pool.imap_unordered(scan, range(a, b + 1)):
            allr += rows
    json.dump(allr, open(S + "/sig_flags.json", "w"), ensure_ascii=False)
    # a signature's "cost" = how many distinct flagged words it appears in
    per_sig = defaultdict(set)
    for r in allr:
        per_sig[r["sig"]].add((r["page"], r["key"]))
    ranked = sorted(per_sig.items(), key=lambda t: -len(t[1]))
    print("flagged words touched: %d" % len({(r["page"], r["key"]) for r in allr}))
    print("distinct signatures on their ink: %d" % len(per_sig))
    for cut in (10, 25, 50, 100):
        cov = len(set().union(*[s for _, s in ranked[:cut]])) if ranked else 0
        print("  top %-4d signatures touch %d flagged words" % (cut, cov))
    print("\n%-20s %-6s %-14s %s" % ("signature", "words", "current label", "auto?"))
    for sg, ws in ranked[:20]:
        info = LAB.get(sg, {})
        print("%-20s %-6d %-14s %s" % (sg, len(ws), info.get("label") or "(none)",
                                       info.get("auto")))
