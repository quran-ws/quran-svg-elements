#!/usr/bin/env python3
"""Proof of concept for the SHIPPED INDEX files — measurement only.

Builds the three index artefacts the shipping proposal recommends, straight
from the already-built annotation sidecars (`.cache/annotations/NNN.json`) and
the edition manifest, then reports their real sizes raw / gzip / brotli.

Writes into docs/shipping/out/ (gitignored by intent — regenerate on demand).
Nothing here touches the pipeline.
"""
import json
import os
import gzip
import sys
from collections import defaultdict

try:
    import brotli
except ImportError:
    brotli = None

ROOT = os.environ.get("QSVG_ROOT", os.getcwd())
ANN = os.path.join(ROOT, ".cache/annotations")
SCHEMA = os.path.join(ROOT, ".cache/schema")
OUT = os.path.join(ROOT, "docs/shipping/out")


def sizes(path):
    b = open(path, "rb").read()
    g = len(gzip.compress(b, 9))
    br = len(brotli.compress(b, quality=11)) if brotli else 0
    return len(b), g, br


def main():
    os.makedirs(OUT, exist_ok=True)
    edition = json.load(open(os.path.join(SCHEMA, "edition-hafs-kfgqpc.json")))

    pages = []
    words = []          # flat word index
    boxes = defaultdict(list)   # page -> [[wid, x0,y0,x1,y1], ...]
    ayah_pages = defaultdict(list)

    for n in range(1, 605):
        d = json.load(open(os.path.join(ANN, f"{n:03d}.json")))
        aids = [a["aid"] for a in d["ayat"]]
        pages.append({
            "page": n,
            "surahs": [s["number"] for s in d["surahs"]],
            "first_ayah": aids[0] if aids else None,
            "last_ayah": aids[-1] if aids else None,
            "words": len(d["words"]),
            "lines": edition.get("lines_per_page", 15),
        })
        for a in aids:
            ayah_pages[a].append(n)
        for w in d["words"]:
            words.append([w["wid"], n, w["rasm"], w["imlaei"]])
        # per-word boxes are the union of that word's mark boxes; a real
        # builder would take them from the pipeline's own word extents.
        wb = defaultdict(lambda: [1e9, 1e9, -1e9, -1e9])
        for m in d["marks"]:
            wid = m.get("wid")
            if not wid or not m.get("box"):
                continue
            b = m["box"]
            c = wb[wid]
            c[0] = min(c[0], b[0]); c[1] = min(c[1], b[1])
            c[2] = max(c[2], b[2]); c[3] = max(c[3], b[3])
        boxes[n] = [[k] + [round(v, 1) for v in b] for k, b in wb.items()]

    # -------- 1. corpus index: everything a consumer needs without an SVG
    corpus = {
        "schema": "quran-svg-index",
        "version": "1",
        "edition": edition["id"],
        "print": edition.get("print"),
        "pages": len(pages),
        "lines_per_page": edition.get("lines_per_page"),
        "surahs": edition.get("surahs"),
        "divisions": edition.get("divisions"),
        "expectations": edition.get("expectations"),
        "page_index": pages,
        "ayah_pages": {k: v for k, v in ayah_pages.items() if len(v) > 1},
    }
    p = os.path.join(OUT, "index.json")
    json.dump(corpus, open(p, "w"), ensure_ascii=False, separators=(",", ":"))

    # -------- 2. word index (search): wid, page, rasm, imlaei
    p2 = os.path.join(OUT, "words.json")
    json.dump({"schema": "quran-svg-words", "version": "1",
               "fields": ["wid", "page", "rasm", "imlaei"], "rows": words},
              open(p2, "w"), ensure_ascii=False, separators=(",", ":"))

    # -------- 3. per-page word boxes (highlight without rendering)
    p3 = os.path.join(OUT, "boxes.json")
    json.dump({"schema": "quran-svg-boxes", "version": "1",
               "fields": ["wid", "x0", "y0", "x1", "y1"],
               "pages": {str(k): v for k, v in boxes.items()}},
              open(p3, "w"), ensure_ascii=False, separators=(",", ":"))

    print(f"{'file':16}{'raw KiB':>10}{'gzip KiB':>10}{'brotli KiB':>12}")
    for f in (p, p2, p3):
        r, g, b = sizes(f)
        print(f"{os.path.basename(f):16}{r/1024:10.0f}{g/1024:10.0f}{b/1024:12.0f}")
    print(f"\nwords indexed: {len(words)}   ayahs spanning >1 page: "
          f"{len(corpus['ayah_pages'])}")


if __name__ == "__main__":
    main()
