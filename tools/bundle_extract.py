#!/usr/bin/env python3
"""Read an emitted page SVG and return the facts the index files are built from.

The SVG is authoritative (FORMAT.md §10.9): every index value here is read out
of the shipped page, never out of a pipeline-internal cache. That is what makes
the checker's cross-reference test meaningful — if the two disagreed, the index
would be wrong and nothing would notice.

One exception, by design (2026-09-04): a production page carries `data-word-key`
and `data-rasm-uthmani` only. The four derived text forms — rasm, rasm_imlai, search,
qpc — are a text index, not geometry, and ship once, here, from the same word
cache and the same derivations the emitter uses (`text_forms`). The SVG still
rules where the two meet: the cache's rasm_uthmani must equal the page's
`data-rasm-uthmani` for every word, or the build stops.
"""
import os
import sys
import xml.etree.ElementTree as ET

from bundle_geom import IDENTITY, mat_mul, parse_transform, path_extremes, union

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
SVGNS = "{http://www.w3.org/2000/svg}"

TEXT_FIELDS = ("rasm_uthmani", "rasm", "rasm_imlai", "search", "qpc")


def text_forms(page, cache_dir=None):
    """{word_key: {rasm_uthmani, rasm, rasm_imlai, search, qpc}} for one page, from the
    verified word cache, derived exactly as the dev profile writes them
    inline: rasm = quran_meta.rasm(rasm_uthmani), search = quran_meta.rasm(rasm_imlai)
    (FORMAT.md §6.1)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import assign_words
    import quran_meta
    cache_dir = cache_dir or os.path.join(ROOT, ".cache", "words")
    out = {}
    # The word source (quran.com's page layout) disagrees with the print about
    # which words sit on 25 pages (CLAUDE.md "Juz 30"); the pipeline repairs
    # page membership from the artwork's own markers, so an emitted page can
    # hold a word the cache files under its neighbour (p120 holds 5:77:1,
    # cached on p121). Never by more than one page: read the neighbours too.
    for pg in (page - 1, page, page + 1):
        if not 1 <= pg <= 604:
            continue
        for words in assign_words.page_words(pg, cache_dir).values():
            for w in words:
                word_key = "%d:%d:%d" % (w["surah"], w["ayah"], w["pos"])
                out[word_key] = {"rasm_uthmani": w["rasm_uthmani"],
                            "rasm": quran_meta.rasm(w["rasm_uthmani"]),
                            "rasm_imlai": w["rasm_imlai"],
                            "search": quran_meta.rasm(w["rasm_imlai"]),
                            "qpc": w.get("qpc") or None}
    return out


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


def _int(v):
    return int(v) if v is not None else None


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
    ayahs = []           # aid, in document order, first appearance
    seen_aid = set()
    divisions = {}      # aid -> {juz|hizb|nisf|rubu_al_hizb: n} for divisions starting here
    division_marks = []  # the drawn rosettes, a separate layer from the boundaries

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
                word_key = child.get("data-word-key")
                rec = {"word_key": word_key, "line": cur_line[0],
                       "ayah_key": word_key.rsplit(":", 1)[0]}
                for f in TEXT_FIELDS:
                    # the ATTRIBUTE keeps the hyphen (data-rasm-uthmani) while
                    # the code name is snake_case (rasm_uthmani) — CLAUDE.md,
                    # "attribute NAMES keep the hyphen". Concatenating the code
                    # name read data-rasm_uthmani, which no page has ever
                    # carried, so rasm_uthmani and rasm_imlai came back None and
                    # the cross-check against the word cache stopped the build.
                    rec[f] = child.get("data-" + f.replace("_", "-"))
                rec["box"] = _box_of(child, N)
                for node in child.iter():
                    if node.get("data-kind") == "mark" \
                            and not node.get("data-mark-part"):
                        marks += 1
                words.append(rec)
                if rec["ayah_key"] not in seen_aid:
                    seen_aid.add(rec["ayah_key"])
                    ayahs.append(rec["ayah_key"])
                continue
            if cls == "line":
                cur_line[0] = int(child.get("data-line"))
                lines_seen.append(cur_line[0])
            if cls == "ayah-fragment":
                # the group is `ayah-fragment`, not `ayah` — renamed in the
                # terminology adoption (CLAUDE.md: g.ayah -> g.ayah-fragment).
                # Testing the old name meant this block never ran at all, so
                # EVERY division was dropped, not just the rubu.
                # The four division attributes repeat on every fragment of the
                # ayah (FORMAT §6.2), so first writer wins and the rest agree.
                # Same hyphen rule as the text fields above: the attribute is
                # data-rubu-al-hizb-start, not data-rubu_al_hizb-start. juz,
                # hizb and nisf are single words and so were unaffected, which
                # is why this showed up as rubu_al_hizb_boundaries: 0 in
                # VERSION.json rather than as an error — 240 boundaries silently
                # dropped from the index.
                got = {k: int(child.get("data-%s-start" % k.replace("_", "-")))
                       for k in ("juz", "hizb", "nisf", "rubu_al_hizb")
                       if child.get("data-%s-start"
                                    % k.replace("_", "-")) is not None}
                if got:
                    divisions.setdefault(child.get("data-ayah-key"), got)
            if cls == "division-mark":
                # The DRAWN rosette (۞), which is a layer of its own — 199 in
                # the mushaf, against 240 rubu BOUNDARIES. The 41 without a
                # rosette all fall on an ayah 1, where the surah header stands
                # in its place; quran-ws records the same 199 as `division`
                # marks, a strict subset of our 240. The two answer different
                # questions and neither replaces the other. NOTE the attributes
                # here are CONTEXT, not series: `data-nisf` is the half (1 or 2),
                # not the 1..60 ordinal that `data-nisf-start` carries.
                division_marks.append({
                    "ayah_key": child.get("data-ayah-key"),
                    "rubu_al_hizb": _int(child.get("data-rubu-al-hizb")),
                    "rubu_al_hizb_in_hizb":
                        _int(child.get("data-rubu-al-hizb-in-hizb")),
                    "half": _int(child.get("data-nisf")),
                    "hizb": _int(child.get("data-hizb")),
                    "juz": _int(child.get("data-juz")),
                })
            if cls in ("surah-name", "basmalah"):
                sid = child.get("data-sid")
                if cls == "surah-name" and sid:
                    surahs.append(int(sid))
            walk(child, N)

    cur_line = [None]
    walk(root, IDENTITY)

    # production pages: fill the four forms the page does not carry, and
    # prove the cache and the page agree on the one they share
    if any(w[f] is None for w in words for f in TEXT_FIELDS):
        forms = text_forms(page)
        for w in words:
            rec = forms.get(w["word_key"])
            if rec is None:
                raise RuntimeError("page %d: %s is on the page but not in the "
                                   "word cache" % (page, w["word_key"]))
            if w["rasm_uthmani"] != rec["rasm_uthmani"]:
                raise RuntimeError("page %d: %s data-rasm-uthmani %r != cache %r"
                                   % (page, w["word_key"], w["rasm_uthmani"], rec["rasm_uthmani"]))
            for f in TEXT_FIELDS:
                if w[f] is None:
                    w[f] = rec[f]

    # every surah with ink on the page, not only those whose banner is here
    page_surahs = sorted({int(a.split(":")[0]) for a in seen_aid})

    return {
        "page": page,
        "view_box": view_box,
        "lines": sorted(set(lines_seen)),
        "words": words,
        "marks": marks,
        "ayahs": ayahs,
        "surahs": page_surahs,
        "banners": sorted(set(surahs)),
        "divisions": divisions,
        "division_marks": division_marks,
    }


def read_page_n(args):
    """ProcessPool entry point: (dir, page) -> record."""
    d, page = args
    return read_page(os.path.join(d, "%03d.svg" % page), page)
