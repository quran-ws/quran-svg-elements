#!/usr/bin/env python3
"""Does a header group hold ink drawn in the OTHER header group's band?

A page that opens a surah draws two header lines: the ornamented surah name and
the basmalah below it. The emitter files each line's ink under
`<g class="surah-name">` / `<g class="basmalah">` from the DK layout DB's
line_type. Each of those groups is ONE compound path, so a mis-cut inside the
artwork's line assignment moves whole CONTOURS between the two — as on p77,
where four contours of the surah name's ink (y 42.8-57.6) are filed under the
basmalah, whose own ink stops at y 31.8.

The test needs no reference and no eye:

  1. Each group's ink is one tight horizontal band. Cluster the group's
     contours on y; the DOMINANT band is the cluster holding the most drawn
     area.
  2. Any contour outside its own group's dominant band is an OUTLIER.
  3. An outlier whose y-midpoint lies inside the OTHER group's dominant band is
     ink held by the wrong group. That is the flag.

Both groups must exist on the page for the test to run, so it examines the 114
surah-opening pages and is silent elsewhere. Step 3 is what makes it safe: an
outlier that sits in neither band (an ornament finial, say) is reported as
`stray`, not as a defect.

By default it reads the emitted pages in `.cache/words-svg/hafs-kfqc`, like
every other product-level audit here. `--build` renders the pages it needs
through the pipeline instead, so CI can run this gate without a full 604-page
build first: only the pages the DK layout DB declares BOTH a surah name and a
basmalah on are candidates, which is 96 of 604.

Usage:
    python3 tools/audit_headerbands.py [first] [last] [--dir D] [--json OUT]
                                       [--build [--jobs N]]
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from audit_wordline import path_bbox  # noqa: E402

DEFAULT_DIR = os.path.join(os.environ.get("QSVG_ROOT", ROOT),
                           ".cache", "words-svg", "hafs-kfqc")
GROUPS = ("surah-name", "basmalah")
# The two header bands are ~10u apart at their closest over the mushaf; a
# contour is called part of a band only when its own box overlaps it, so the
# clustering gap is set well inside that: contours of one line of text never
# leave a vertical hole this large.
CLUSTER_GAP = 6.0


def contours(d):
    return ["M" + p for p in d.split("M") if p.strip()]


def group_paths(svg, cls):
    """Contours of each header group of this class, keyed by `data-sid`. A page
    can open three surahs (p604 opens 112, 113 and 114), so the groups must be
    paired by surah — merging every `basmalah` on the page into one set puts
    three text bands in one cluster and the test measures nothing."""
    out = {}
    for m in re.finditer(r'<g class="%s"([^>]*)>(.*?)</g>' % cls, svg, re.S):
        sid = re.search(r'data-sid="(\d+)"', m.group(1))
        sid = sid.group(1) if sid else "?"
        boxes = out.setdefault(sid, [])
        for d in re.findall(r'\sd="([^"]+)"', m.group(2)):
            boxes.extend(path_bbox(c) for c in contours(d))
    return out


def dominant_band(boxes):
    """(lo, hi) of the y-cluster holding the most drawn area."""
    if not boxes:
        return None
    order = sorted(boxes, key=lambda b: b[1])
    clusters, cur = [], [order[0]]
    for b in order[1:]:
        if b[1] - max(c[3] for c in cur) > CLUSTER_GAP:
            clusters.append(cur)
            cur = []
        cur.append(b)
    clusters.append(cur)
    best = max(clusters,
               key=lambda cl: sum((b[2] - b[0]) * (b[3] - b[1]) for b in cl))
    return min(b[1] for b in best), max(b[3] for b in best)


def audit_svg(svg):
    by_cls = {g: group_paths(svg, g) for g in GROUPS}
    sids = sorted(set(by_cls[GROUPS[0]]) & set(by_cls[GROUPS[1]]))
    if not sids:
        return None
    rec = {"surahs": {}, "flags": [], "stray": []}
    for sid in sids:
        boxes = {g: by_cls[g][sid] for g in GROUPS}
        bands = {g: dominant_band(boxes[g]) for g in GROUPS}
        rec["surahs"][sid] = bands
        for g in GROUPS:
            other = GROUPS[1 - GROUPS.index(g)]
            lo, hi = bands[g]
            olo, ohi = bands[other]
            for b in boxes[g]:
                mid = (b[1] + b[3]) / 2.0
                if lo <= mid <= hi:
                    continue
                item = {"group": g, "sid": sid, "band": bands[g],
                        "box": [round(v, 2) for v in b]}
                if olo <= mid <= ohi:
                    item["belongs_to"] = other
                    rec["flags"].append(item)
                else:
                    rec["stray"].append(item)
    return rec


def audit_page(path):
    return audit_svg(open(path, encoding="utf-8").read())


def header_pages():
    """Every page the DK layout DB declares a header line on — 116 of 604.

    A superset on purpose. The DB's own pairing is not the emitted one: on p77
    it declares the basmalah alone, and rewrite() recovers the surah name from
    the ART (QSVG_HDRART), so selecting pages that carry BOTH kinds in the DB
    drops real header pairs. Pages that turn out to have only one band are
    skipped by audit_svg anyway, at the cost of building them.""" 
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from assign_words import dk_header_lines
    return sorted(int(pg) for pg in dk_header_lines())


def _build_one(pg):
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import assign_words as A
    cache = os.path.join(A.ROOT, ".cache", "words")
    return pg, audit_svg(A.assign_page("hafs/kfqc", pg, cache)[1])


def main(argv):
    first, last = 1, 604
    d, out = DEFAULT_DIR, None
    build, jobs = False, 4
    pos = []
    i = 0
    while i < len(argv):
        if argv[i] == "--dir":
            i += 1
            d = argv[i]
        elif argv[i] == "--json":
            i += 1
            out = argv[i]
        elif argv[i] == "--build":
            build = True
        elif argv[i] == "--jobs":
            i += 1
            jobs = int(argv[i])
        else:
            pos.append(argv[i])
        i += 1
    if pos:
        first = int(pos[0])
        last = int(pos[1]) if len(pos) > 1 else first

    if build:
        todo = [n for n in header_pages() if first <= n <= last]
        pages = {}
        if jobs > 1:
            from multiprocessing import Pool
            with Pool(jobs) as pool:
                for n, r in pool.imap_unordered(_build_one, todo):
                    if r:
                        pages[n] = r
        else:
            for n in todo:
                _, r = _build_one(n)
                if r:
                    pages[n] = r
        return report(pages, len(todo), out)

    pages, missing = {}, []
    for n in range(first, last + 1):
        p = os.path.join(d, "%03d.svg" % n)
        if not os.path.exists(p):
            missing.append(n)
            continue
        r = audit_page(p)
        if r:
            pages[n] = r
    if missing:
        print("REFUSING: %d page(s) not built, first %s"
              % (len(missing), missing[0]))
        return 2
    return report(pages, last - first + 1, out)


def report(pages, examined, out):
    nflag = sum(len(r["flags"]) for r in pages.values())
    nstray = sum(len(r["stray"]) for r in pages.values())
    bad = sorted(n for n, r in pages.items() if r["flags"])
    print("header pages examined: %d of %d" % (len(pages), examined))
    for n in bad:
        r = pages[n]
        for f in r["flags"]:
            b = f["box"]
            print("p%03d  surah %-3s  %-10s holds  x %7.2f..%7.2f"
                  "  y %7.2f..%7.2f   -> %s  (own band %.2f..%.2f)"
                  % (n, f["sid"], f["group"], b[0], b[2], b[1], b[3],
                     f["belongs_to"],
                     f["band"][0], f["band"][1]))
    print("FLAGS %d over %d page(s);  stray (in neither band) %d"
          % (nflag, len(bad), nstray))
    if out:
        json.dump({"pages": pages}, open(out, "w"), indent=1)
    return 1 if nflag else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
