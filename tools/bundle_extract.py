#!/usr/bin/env python3
"""Read an emitted page SVG and return the facts the index files are built from.

The SVG is authoritative (FORMAT.md §10.9): every index value here is read out
of the shipped page, never out of a pipeline-internal cache. That is what makes
the checker's cross-reference test meaningful — if the two disagreed, the index
would be wrong and nothing would notice.
"""
import os
import xml.etree.ElementTree as ET

from bundle_geom import IDENTITY, mat_mul, parse_transform, path_extremes, union

SVGNS = "{http://www.w3.org/2000/svg}"

TEXT_FIELDS = ("uthmani", "rasm", "imlaei", "search", "qpc")


def _tag(e):
    return e.tag[len(SVGNS):] if e.tag.startswith(SVGNS) else e.tag


def _box_of(el, M):
    """Tight box of every <path d> under `el`, in the frame reached by M.

    Transforms are composed all the way down, INCLUDING a transform on the
    <path> itself: 6,700-odd paths carry one (the emitter's frame compensation
    for ink moved between lines), and ignoring it puts the box in the wrong
    place — caught on p144 `6:125:9`, whose box was 8.4 units short until the
    path transform was applied.
    """
    box = None
    stack = [(el, M)]
    while stack:
        node, frame = stack.pop()
        for child in node:
            f = frame
            tr = child.get("transform")
            if tr:
                f = mat_mul(parse_transform(tr), frame)
            if _tag(child) == "path":
                d = child.get("d")
                if d:
                    box = union(box, path_extremes(d, f))
            else:
                stack.append((child, f))
    return box


def read_page(path, page):
    """Return a dict of everything the index needs from one page SVG.

    Boxes are in **viewBox units** — the page frame and the line frame are both
    applied — so a consumer can overlay them on the rendered page directly.
    """
    root = ET.parse(path).getroot()
    view_box = root.get("viewBox")

    words = []          # in document order == reading order (FORMAT §5.4)
    lines_seen = []
    marks = 0
    surahs = []
    ayat = []           # aid, in document order, first appearance
    seen_aid = set()
    divisions = {}      # aid -> {juz|hizb|nisf|rub: n} for divisions starting here

    def walk(el, M):
        nonlocal marks
        for child in el:
            t = _tag(child)
            if t != "g":
                continue
            cls = child.get("class") or ""
            N = M
            tr = child.get("transform")
            if tr:
                N = mat_mul(parse_transform(tr), M)
            if cls == "word":
                wid = child.get("data-wid")
                rec = {"wid": wid, "line": cur_line[0],
                       "aid": wid.rsplit(":", 1)[0]}
                for f in TEXT_FIELDS:
                    rec[f] = child.get("data-" + f)
                rec["box"] = _box_of(child, N)
                for node in child.iter():
                    if node.get("data-kind") == "mark" \
                            and not node.get("data-mark-part"):
                        marks += 1
                words.append(rec)
                if rec["aid"] not in seen_aid:
                    seen_aid.add(rec["aid"])
                    ayat.append(rec["aid"])
                continue
            if cls == "line":
                cur_line[0] = int(child.get("data-line"))
                lines_seen.append(cur_line[0])
            if cls == "ayah":
                # the four division attributes repeat on every fragment of the
                # ayah (FORMAT §6.2), so first writer wins and the rest agree
                got = {k: int(child.get("data-%s-start" % k))
                       for k in ("juz", "hizb", "nisf", "rub")
                       if child.get("data-%s-start" % k) is not None}
                if got:
                    divisions.setdefault(child.get("data-aid"), got)
            if cls in ("surah-name", "basmalah"):
                sid = child.get("data-sid")
                if cls == "surah-name" and sid:
                    surahs.append(int(sid))
            walk(child, N)

    cur_line = [None]
    walk(root, IDENTITY)

    # every surah with ink on the page, not only those whose banner is here
    page_surahs = sorted({int(a.split(":")[0]) for a in seen_aid})

    return {
        "page": page,
        "view_box": view_box,
        "lines": sorted(set(lines_seen)),
        "words": words,
        "marks": marks,
        "ayat": ayat,
        "surahs": page_surahs,
        "banners": sorted(set(surahs)),
        "divisions": divisions,
    }


def read_page_n(args):
    """ProcessPool entry point: (dir, page) -> record."""
    d, page = args
    return read_page(os.path.join(d, "%03d.svg" % page), page)
