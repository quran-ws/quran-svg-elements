#!/usr/bin/env python3
"""Word-owned elements drawn on a DK-declared header/basmalah line.

84:25:5 (p590) stole the dot of the ب in the surah title below it; header
ink must never enter a word. Measures the family mushaf-wide.

    python3 scratchpad/hdrink_scan.py <page> [outdir]
"""
import json, os, sys

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT + "/tools")


def scan(pg, outdir):
    import assign_words as aw
    hdr = aw.dk_header_lines().get(str(pg)) or aw.dk_header_lines().get(pg) or {}
    out = []
    if hdr:
        cap = {}
        orig = aw.rewrite
        def spy(page, assignment):
            cap["a"] = assignment
            return orig(page, assignment)
        aw.rewrite = spy
        aw.assign_page("hafs/kfqc", pg, ROOT + "/.cache/words")
        hl = {int(k) for k in hdr}
        for w, at in cap["a"]:
            if not w:
                continue
            for a in at:
                for e in a["els"]:
                    if e.get("line") in hl:
                        out.append({"key": "%d:%d:%d" % (w["surah"], w["ayah"], w["pos"]),
                                    "kind": e["kind"], "mark": e.get("mark"),
                                    "line": e["line"],
                                    "w": round(e["x2"] - e["x1"], 1),
                                    "h": round(e["y2"] - e["y1"], 1)})
    json.dump({"page": pg, "stolen": out},
              open(os.path.join(outdir, "%03d.json" % pg), "w",
                   encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    pg = int(sys.argv[1])
    outdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, ".cache", "hdrink")
    os.makedirs(outdir, exist_ok=True)
    scan(pg, outdir)
