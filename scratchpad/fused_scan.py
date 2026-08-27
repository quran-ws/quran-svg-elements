#!/usr/bin/env python3
"""List every fused (compound-named) mark element in a page's fresh build."""
import json, os, sys

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT + "/tools")


def scan(pg, outdir):
    import assign_words as aw
    cap = {}
    orig = aw.rewrite
    def spy(page, assignment):
        cap["a"] = assignment
        return orig(page, assignment)
    aw.rewrite = spy
    aw.assign_page("hafs/kfqc", pg, ROOT + "/.cache/words")
    out = []
    for w, at in cap["a"]:
        for a in at:
            for e in a["els"]:
                if "+" in (e.get("mark") or ""):
                    out.append({"key": "%d:%d:%d" % (w["surah"], w["ayah"], w["pos"]) if w else None,
                                "mark": e["mark"], "sig": e.get("sig"),
                                "contours": len(e.get("contours", [])),
                                "fused": bool(e.get("fused"))})
    json.dump({"page": pg, "fused": out},
              open(os.path.join(outdir, "%03d.json" % pg), "w",
                   encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    outdir = os.path.join(ROOT, ".cache", "fusedscan")
    os.makedirs(outdir, exist_ok=True)
    scan(int(sys.argv[1]), outdir)
