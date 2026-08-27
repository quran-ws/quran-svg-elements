#!/usr/bin/env python3
"""Measure word-owned ink vs ayah-marker footprints (84:25:5 p590, item 33).

For every word-owned element, distance from its bbox center to the nearest
ayah-marker center (the ayah: groups' translate origins, viewBox frame).
True word ink should never sit inside a medallion; a theft does. The
distribution's empty band sets the footprint radius for the rule.

    python3 scratchpad/markerink_scan.py <page> [outdir]
"""
import json, os, re, sys

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT + "/tools")

MK = re.compile(r'transform="translate\(([\d.]+) ([\d.]+)\)[^"]*" ayah:x=')


def scan(pg, outdir):
    import assign_words as aw
    svg = open(ROOT + "/mushafs/hafs/kfqc/svg/%03d.svg" % pg, encoding="utf-8").read()
    markers = [(float(a), float(b)) for a, b in MK.findall(svg)]
    if not markers:
        json.dump({"page": pg, "near": []}, open(
            os.path.join(outdir, "%03d.json" % pg), "w")); return
    cap = {}
    orig = aw.rewrite
    def spy(page, assignment):
        cap["a"] = assignment
        return orig(page, assignment)
    aw.rewrite = spy
    aw.assign_page("hafs/kfqc", pg, ROOT + "/.cache/words")
    near = []
    for w, at in cap["a"]:
        if not w:
            continue
        for a in at:
            for e in a["els"]:
                cx, cy = (e["x1"] + e["x2"]) / 2, (e["y1"] + e["y2"]) / 2
                d = min(((cx - mx) ** 2 + (cy - my) ** 2) ** 0.5
                        for mx, my in markers)
                if d < 25:
                    near.append({"key": "%d:%d:%d" % (w["surah"], w["ayah"], w["pos"]),
                                 "kind": e["kind"], "mark": e.get("mark"),
                                 "w": round(e["x2"] - e["x1"], 1),
                                 "h": round(e["y2"] - e["y1"], 1),
                                 "d": round(d, 1)})
    json.dump({"page": pg, "near": near},
              open(os.path.join(outdir, "%03d.json" % pg), "w",
                   encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    pg = int(sys.argv[1])
    outdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, ".cache", "markerink")
    os.makedirs(outdir, exist_ok=True)
    scan(pg, outdir)
