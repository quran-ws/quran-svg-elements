#!/usr/bin/env python3
"""Every pause sign vs its dots (Abdullah 2026-08-27: قلى must always carry
its 2 dots, ج its dot).

For each pause-labeled element: its waqf type (waqf_types by sig), how many
dot elements it already carries (mkpart members / same-element contours are
invisible here, so count separate dot/two-dots elements overlapping its box
+-3u), and who owns them.

    python3 scratchpad/pausedots_scan.py <page>
"""
import json, os, sys

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT + "/tools")


def scan(pg, outdir):
    import assign_words as aw
    wt = {}
    for k, v in json.load(open(os.path.join(ROOT, ".cache", "marks",
                                            "waqf_types.json"))).items():
        wt[k] = v if isinstance(v, str) else (v.get("waqf") or v.get("label"))
    cap = {}
    orig = aw.rewrite
    def spy(page, assignment):
        cap["a"] = assignment
        return orig(page, assignment)
    aw.rewrite = spy
    aw.assign_page("hafs/kfqc", pg, ROOT + "/.cache/words")
    els = []
    for w, at in cap["a"]:
        for a in at:
            for e in a["els"]:
                els.append((e, ("%d:%d:%d" % (w["surah"], w["ayah"], w["pos"]))
                            if w else None))
    out = []
    for e, owner in els:
        if e.get("mark") != "pause" or e.get("mkpart"):
            continue
        typ = wt.get(e.get("sig"))
        near = []
        for d, downer in els:
            if d is e or d.get("mark") not in ("dot", "two-dots", "three-dots"):
                continue
            if (d["x1"] < e["x2"] + 3 and d["x2"] > e["x1"] - 3
                    and d["y1"] < e["y2"] + 3 and d["y2"] > e["y1"] - 3):
                near.append({"mark": d["mark"], "owner": downer,
                             "part": bool(d.get("mkpart"))})
        parts = sum(1 for d, _ in els if d.get("mkpart")
                    and d is not e
                    and e["x1"] - 1 <= (d["x1"] + d["x2"]) / 2 <= e["x2"] + 1
                    and e["y1"] - 1 <= (d["y1"] + d["y2"]) / 2 <= e["y2"] + 1)
        out.append({"owner": owner, "sig": e.get("sig"), "type": typ,
                    "contours": len(e.get("contours", [])),
                    "parts": parts, "near_dots": near})
    json.dump({"page": pg, "pauses": out},
              open(os.path.join(outdir, "%03d.json" % pg), "w",
                   encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    outdir = os.path.join(ROOT, ".cache", "pausedots")
    os.makedirs(outdir, exist_ok=True)
    scan(int(sys.argv[1]), outdir)
