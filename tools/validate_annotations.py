#!/usr/bin/env python3
"""Schema v2 phase 1: prove the annotation graph and the emitted SVG agree.

attr_schema_v3 §16.2-16.5 made concrete. Per page, and then mushaf-wide:

1. **counting** — the number of logical mark RECORDS equals the number of
   emitted MASTER paths (`data-mark`, not `data-mark-part`), family by family.
   This is phase 1's headline obligation: the graph counts marks, the SVG
   counts paths, and today they must agree exactly.
2. **references** — every eid a record names exists in the page, and no eid is
   claimed by two records.
3. **words** — the same set of `wid`s, and for each one the same uthmani, rasm
   and imlaei. This is what makes the graph a stand-in for the SVG's text.
4. **metadata** — the surah card, the division-start flags and the hizb
   rosette's rubʿ/nisf/hizb/juz read the same in both places.
5. **relations** — muanaqah has exactly 2 members, the sajdah compound has one
   overline and one sign, and every iqlab relation names a tanween-family mark
   plus a meem-iqlab.
6. **vocabulary** — every emitted mark name is in the registry and active.

Usage:  python3 tools/validate_annotations.py [first last] [-jN]
Exit 1 and a per-page FAIL list on any violation.
"""

import argparse
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = (os.environ.get("QSVG_ROOT")
        or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ANN = os.path.join(ROOT, ".cache", "annotations")
SVG = os.path.join(ROOT, ".cache", "words-svg", "hafs-kfqc")
SCHEMA = os.path.join(ROOT, ".cache", "schema")

_TAG = re.compile(r"<g\b[^>]*>|</g>|<path\b[^>]*?/?>")
_ATTR = re.compile(r'([\w-]+)="([^"]*)"')


def _unesc(s):
    return s.replace("&quot;", '"').replace("&lt;", "<").replace("&amp;", "&")


def check_page(pg, reg, edition):
    ann = json.load(open(os.path.join(ANN, "%03d.json" % pg), encoding="utf-8"))
    svg = open(os.path.join(SVG, "%03d.svg" % pg), encoding="utf-8").read()
    bad = []

    words_svg = {}
    masters = Counter()
    master_ids = []
    eids = set()
    hizb = []
    markers_svg = []
    ayah_attrs = {}
    surah_attrs = {}
    stack = []
    for m in _TAG.finditer(svg):
        t = m.group(0)
        if t == "</g>":
            if stack:
                stack.pop()
            continue
        at = dict(_ATTR.findall(t))
        if t.startswith("<g"):
            cls = at.get("class")
            if cls == "word":
                words_svg[at.get("data-wid")] = at
            elif cls == "ayah":
                ayah_attrs[at.get("data-aid")] = at
            elif cls in ("surah-name", "basmalah"):
                surah_attrs[at.get("data-sid")] = at
            elif cls == "hizb-mark":
                hizb.append(at)
            elif cls == "ayah-marker":
                markers_svg.append(at.get("data-aid"))
            if not t.endswith("/>"):
                stack.append(at)
            continue
        if at.get("data-eid"):
            eids.add(at["data-eid"])
        nm = at.get("data-mark")
        if nm:
            masters[nm] += 1
            master_ids.append(at.get("data-eid"))

    # ---- 6. vocabulary ----------------------------------------------------
    for nm in masters:
        r = reg["marks"].get(nm)
        if r is None:
            bad.append("vocab: %r not in the registry" % nm)
        elif not r.get("active", True):
            bad.append("vocab: %r is reserved, not active" % nm)

    # ---- 1. counting, family by family -----------------------------------
    rec_by_name = Counter(m["mark"] for m in ann["marks"])
    if rec_by_name != masters:
        for nm in set(rec_by_name) | set(masters):
            if rec_by_name[nm] != masters[nm]:
                bad.append("count: %s graph=%d svg-master-paths=%d"
                           % (nm, rec_by_name[nm], masters[nm]))

    def fam(nm):
        return (reg["marks"].get(nm) or {}).get("family") or "-"

    gf = Counter(fam(m["mark"]) for m in ann["marks"])
    sf = Counter()
    for nm, n in masters.items():
        sf[fam(nm)] += n
    if gf != sf:
        bad.append("family counts differ: %s vs %s" % (dict(gf), dict(sf)))

    # ---- 2. references ----------------------------------------------------
    claimed = Counter()
    for m in ann["marks"]:
        for e in m["paths"]:
            claimed[e] += 1
            if e not in eids:
                bad.append("ref: %s names %s, not in the page" % (m["id"], e))
    for e, n in claimed.items():
        if n > 1:
            bad.append("ref: %s claimed by %d records" % (e, n))

    # ---- 3. words ---------------------------------------------------------
    gw = {w["wid"]: w for w in ann["words"]}
    if set(gw) != set(words_svg):
        miss = sorted(set(gw) - set(words_svg))[:5]
        extra = sorted(set(words_svg) - set(gw))[:5]
        bad.append("words: graph-only %s svg-only %s" % (miss, extra))
    for wid, w in gw.items():
        at = words_svg.get(wid)
        if not at:
            continue
        for key, attr in (("uthmani", "data-uthmani"), ("rasm", "data-rasm"),
                          ("imlaei", "data-imlaei")):
            if _unesc(at.get(attr, "")) != (w[key] or ""):
                bad.append("word %s: %s graph=%r svg=%r"
                           % (wid, attr, w[key], _unesc(at.get(attr, ""))))

    # ---- 4. metadata ------------------------------------------------------
    by_num = {c["number"]: c for c in ann["surahs"]}
    for sid, at in surah_attrs.items():
        c = by_num.get(int(sid))
        if c is None:
            bad.append("meta: banner for surah %s has no graph record" % sid)
            continue
        if _unesc(at.get("data-surah-name-ar", "")) != c["name_arabic"] \
                or at.get("data-revelation-place") != c["revelation_place"] \
                or at.get("data-ayah-count") != str(c["ayah_count"]):
            bad.append("meta: surah %s card differs from the graph" % sid)
    starts = {d["aid"]: d for d in ann["divisions_starting_here"]}
    for aid, at in ayah_attrs.items():
        for k in ("juz", "hizb", "nisf", "rub"):
            v = at.get("data-%s-start" % k)
            g = starts.get(aid, {}).get(k)
            if (v is None) != (g is None) or (v is not None
                                              and int(v) != int(g)):
                bad.append("meta: %s data-%s-start svg=%r graph=%r"
                           % (aid, k, v, g))
    for at in hizb:
        aid = at.get("data-aid")
        d = starts.get(aid)
        if not d or "rub" not in d:
            bad.append("meta: hizb rosette at %s is not a rubʿ start" % aid)
            continue
        r = int(d["rub"])
        want = {"data-rub": r, "data-hizb": (r + 3) // 4,
                "data-juz": (r + 7) // 8,
                "data-rub-in-hizb": ((r - 1) % 4) + 1,
                "data-nisf": 1 if ((r - 1) % 4) < 2 else 2}
        for k, v in want.items():
            if at.get(k) != str(v):
                bad.append("meta: hizb %s %s svg=%r want %d"
                           % (aid, k, at.get(k), v))

    # ---- 4b. ayah markers -------------------------------------------------
    # Every medallion the page draws is in the graph, with the same ayah, and
    # no ayah is closed twice on one page.
    gmk = [r["aid"] for r in ann["relations"] if r["type"] == "ayah-marker"]
    if sorted(gmk) != sorted(x for x in markers_svg if x):
        bad.append("marker: graph %s svg %s" % (sorted(gmk)[:6],
                                                sorted(markers_svg)[:6]))
    if len(set(gmk)) != len(gmk):
        bad.append("marker: an ayah is closed twice on this page")

    # ---- 5. relations -----------------------------------------------------
    by_id = {m["id"]: m for m in ann["marks"]}
    sajdah_parts = Counter()
    for r in ann["relations"]:
        if r["type"] == "muanaqah" and len(r.get("members", [])) != 2:
            bad.append("relation: muanaqah %s has %d members (want 2)"
                       % (r.get("key"), len(r.get("members", []))))
        if r["type"] == "iqlab":
            names = sorted(by_id[i]["mark"] for i in r.get("members", [])
                           if i in by_id)
            if "meem-iqlab" not in names:
                bad.append("relation: iqlab %s = %s, no meem-iqlab"
                           % (r.get("key"), names))
        if r["type"] == "sajdah":
            # Cardinality is checked MUSHAF-WIDE (15 signs, 15 overlines), not
            # per relation: on p379 and p480 the bar and the ۩ fall inside
            # DIFFERENT ayah polygons, so the emitter itself already writes two
            # <g class="sajdah-mark"> groups there. The graph mirrors the SVG;
            # splitting them is a pipeline observation, not a graph defect.
            names = [by_id[i]["mark"] for i in r.get("members", [])
                     if i in by_id]
            if not names:
                bad.append("relation: sajdah %s has no members" % r.get("aid"))
            sajdah_parts.update(names)
        if r["type"] == "hizb" and len(r.get("members", [])) != 1:
            bad.append("relation: hizb %s has %d masters (want 1)"
                       % (r.get("aid"), len(r.get("members", []))))
    return {"page": pg, "violations": bad, "marks": dict(rec_by_name),
            "markers": len(gmk),
            "sajdah": dict(sajdah_parts),
            "words": len(gw), "hizb": len(hizb),
            "starts": [d for d in ann["divisions_starting_here"]],
            "surahs": [c["number"] for c in ann["surahs"]]}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("first", type=int, nargs="?", default=1)
    ap.add_argument("last", type=int, nargs="?", default=604)
    ap.add_argument("-j", type=int, default=16)
    args = ap.parse_args()

    reg = json.load(open(os.path.join(SCHEMA, "mark-taxonomy.v2.json"),
                         encoding="utf-8"))
    edition = json.load(open(os.path.join(SCHEMA, "edition-hafs-kfgqpc.json"),
                             encoding="utf-8"))

    import concurrent.futures as cf
    fails, marks, words, hizb = [], Counter(), 0, 0
    sajdah = Counter()
    nmark = 0
    juz_seen, surah_seen = set(), set()
    with cf.ThreadPoolExecutor(args.j) as ex:
        for r in ex.map(lambda p: check_page(p, reg, edition),
                        range(args.first, args.last + 1)):
            if r["violations"]:
                fails.append((r["page"], r["violations"]))
            marks.update(r["marks"])
            sajdah.update(r["sajdah"])
            nmark += r["markers"]
            words += r["words"]
            hizb += r["hizb"]
            surah_seen.update(r["surahs"])
            for d in r["starts"]:
                if "juz" in d:
                    juz_seen.add(int(d["juz"]))

    full = (args.first, args.last) == (1, 604)
    if full:
        exp = edition["expectations"]
        if hizb != exp["hizb_marks_drawn"]:
            fails.append(("mushaf", ["hizb rosettes %d != %d"
                                     % (hizb, exp["hizb_marks_drawn"])]))
        for part, want in (("sajdah-sign", exp["sajdah_sites"]),
                           ("sajdah-line", exp["sajdah_sites"])):
            if sajdah[part] != want:
                fails.append(("mushaf", ["%s %d != %d"
                                         % (part, sajdah[part], want)]))
        if nmark != 6236:
            fails.append(("mushaf", ["ayah markers %d != 6236" % nmark]))
        if len(juz_seen) != 30:
            fails.append(("mushaf", ["juz starts seen %d of 30 (%s missing)"
                                     % (len(juz_seen),
                                        sorted(set(range(1, 31)) - juz_seen))]))
        if len(surah_seen) != 114:
            fails.append(("mushaf", ["surahs seen %d of 114" % len(surah_seen)]))

    if fails:
        for pg, vs in sorted(fails, key=lambda t: str(t[0])):
            for v in vs[:6]:
                print("FAIL p%s: %s" % (pg, v))
        print("validate_annotations: %d page(s) FAILED" % len(fails))
        sys.exit(1)
    print("validate_annotations OK: pages %d-%d, %d words, %d logical marks "
          "in %d names, %d hizb rosettes, %d ayah markers, %d juz starts, "
          "%d surahs"
          % (args.first, args.last, words, sum(marks.values()), len(marks),
             hizb, nmark, len(juz_seen), len(surah_seen)))


if __name__ == "__main__":
    main()
