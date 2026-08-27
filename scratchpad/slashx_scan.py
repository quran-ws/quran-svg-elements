#!/usr/bin/env python3
"""Measure the slash-exchange family (reported.json item 32, p586 هو/بقول).

A fatha/kasra stroke drawn over a NEIGHBOUR word's letter ink while its own
word's letters lie elsewhere — in both directions at once — is a mutual,
budget-neutral theft no counting audit can see. This scan only MEASURES:
for every adjacent word pair on a line, each non-part slash mark's horizontal
overlap with its own word's bodies vs the neighbour's. Writes one JSON per
page; run under xargs -P for the mushaf.

    python3 scratchpad/slashx_scan.py <page> [outdir]
"""
import json, os, sys

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT + "/tools")

SLASH = {"fatha", "kasra", "fathatan", "kasratan"}


def overlap(a1, a2, b1, b2):
    return max(0.0, min(a2, b2) - max(a1, b1))


def scan(pg, outdir):
    import assign_words as aw
    cap = {}
    orig = aw.rewrite
    def spy(page, assignment):
        cap["a"] = assignment
        return orig(page, assignment)
    aw.rewrite = spy
    aw.assign_page("hafs/kfqc", pg, ROOT + "/.cache/words")
    words = []
    for w, at in cap["a"]:
        if not w:
            continue
        els = [e for a in at for e in a["els"]]
        bods = [e for e in els if e["kind"] == "body"]
        if not bods:
            continue
        ln = els[0].get("line")
        words.append({
            "key": "%d:%d:%d" % (w["surah"], w["ayah"], w["pos"]),
            "line": ln,
            "bx": [(b["x1"], b["x2"]) for b in bods],
            "slash": [{"mark": e["mark"], "x1": e["x1"], "x2": e["x2"],
                       "y1": e["y1"], "y2": e["y2"]}
                      for e in els if e.get("mark") in SLASH
                      and not e.get("mkpart")],
        })
    def cover(mk, w):
        return sum(overlap(mk["x1"], mk["x2"], b1, b2) for b1, b2 in w["bx"])
    out = []
    byline = {}
    for w in words:
        byline.setdefault(w["line"], []).append(w)
    for ln, ws in byline.items():
        ws.sort(key=lambda w: -max(b2 for _, b2 in w["bx"]))    # rtl order
        for i, w in enumerate(ws):
            for mk in w["slash"]:
                own = cover(mk, w)
                for j in (i - 1, i + 1):
                    if not (0 <= j < len(ws)):
                        continue
                    nb = ws[j]
                    theirs = cover(mk, nb)
                    wd = mk["x2"] - mk["x1"]
                    if theirs > 0.6 * wd and own < 0.25 * wd:
                        out.append({"line": ln, "holder": w["key"],
                                    "over": nb["key"], "mark": mk["mark"],
                                    "x": [round(mk["x1"], 1), round(mk["x2"], 1)],
                                    "own_cov": round(own, 2),
                                    "nb_cov": round(theirs, 2)})
    json.dump({"page": pg, "crossed": out},
              open(os.path.join(outdir, "%03d.json" % pg), "w",
                   encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    pg = int(sys.argv[1])
    outdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        ROOT, ".cache", "slashx")
    os.makedirs(outdir, exist_ok=True)
    scan(pg, outdir)
