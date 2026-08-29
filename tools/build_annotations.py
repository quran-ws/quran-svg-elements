#!/usr/bin/env python3
"""Schema v2 phase 1: the per-page annotation graph.

ADDITIVE. This builds a sidecar; the emitted SVG is untouched by it.

What a page record holds
------------------------
* **metadata** — the surahs opening on the page (number, both names, revelation
  place, ayah count), the juz / hizb / nisf / rubʿ divisions that begin on it,
  and, per ayah, which juz/hizb/rubʿ it belongs to. Same facts, same values, as
  the attributes the emitter now writes, so the SVG and the graph agree by
  construction — both call `tools/quran_meta.py`.
* **words** — `wid` "surah:ayah:word", the uthmani text, the rasm search key,
  the imlaei form, the QPC text, and the ligature texts in reading order.
* **logical marks** — ONE record per mark, however many `<path>`s the artwork
  needed for it (v2 §7: count records, never paths). A record lists the eids of
  the paths that draw it, so a fused pair is one record on one path and a split
  sign is one record on several.
* **relations** — muanaqah pairs, iqlab (tanween + small meem), the sajdah
  compound, the standalone hizb rosette, and ayah → marker.

Where the records come from
---------------------------
The pipeline's own internal element records, captured by spying on
`assign_words.rewrite()` — the same objects `emit()` writes out — plus the
eid map `QSVG_EIDMAP` already dumps, so every record can name the paths it is
drawn as. Nothing is re-derived from the SVG text, which is what makes
`validate_annotations.py`'s comparison against the SVG a real check.

Usage:
    python3 tools/build_annotations.py [first last] [-jN]
    python3 tools/build_annotations.py 350 350 --print
"""

import argparse
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import quran_meta as qm                                          # noqa: E402

ROOT = qm.ROOT
OUT = os.path.join(ROOT, ".cache", "annotations")
VERSION = "2.0"

_PATH = re.compile(r"<path\b([^>]*)>")
_ATTR = re.compile(r'([\w-]+)="([^"]*)"')


def _families():
    reg = json.load(open(os.path.join(ROOT, ".cache", "schema",
                                      "mark-taxonomy.v2.json"),
                         encoding="utf-8"))
    return reg["marks"]


def build_page(pg):
    """The annotation record for one page."""
    import assign_words as aw

    cap = {}
    real = aw.rewrite

    def spy(page, assignment):
        cap["assignment"] = assignment
        return real(page, assignment)

    aw.rewrite = spy
    fd, eidmap_path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.environ["QSVG_EIDMAP"] = eidmap_path
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            _, svg, _, _ = aw.assign_page(
                "hafs/kfqc", pg, os.path.join(ROOT, ".cache", "words"))
    finally:
        aw.rewrite = real
        os.environ.pop("QSVG_EIDMAP", None)
    # rewrite() publishes its eid map on the module (assign_words.LAST_EIDMAP),
    # so one process can build many pages without waiting for the atexit dump.
    eidmap = list(getattr(aw, "LAST_EIDMAP", []) or [])
    if os.path.exists(eidmap_path):
        os.unlink(eidmap_path)

    assignment = cap["assignment"]
    reg = _families()

    # ---- element -> eid, by (rounded bbox, kind, mark, part) --------------
    index = {}
    for row in eidmap:
        key = (row["x1"], row["y1"], row["x2"], row["y2"], row["kind"],
               row["mark"], row["part"])
        index.setdefault(key, []).append(row["eid"])

    def eid_of(e):
        key = (round(e["x1"], 1), round(e["y1"], 1), round(e["x2"], 1),
               round(e["y2"], 1), e["kind"], e.get("mark"),
               bool(e.get("mkpart")))
        lst = index.get(key)
        return lst.pop(0) if lst else None

    # ---- words, marks, relations -----------------------------------------
    words, marks, relations = [], [], []
    mid = [0]
    pair_of = {}
    ayat = {}

    def add_mark(e, wid, page_no=pg):
        """One logical-mark record for one master element.

        The NAME is resolved exactly as `emit()` resolves it: a `pause` whose
        outline the waqf-signature table recognises, or whose place the
        waqf-place table names, is that subtype. Doing it anywhere else would
        make the graph and the SVG disagree on 4,275 waqf marks.
        """
        nm = e.get("mark")
        if e.get("sig"):
            wq = aw.waqf_types().get(e["sig"])
            if not wq:
                rec0 = aw.waqf_places().get(str(int(page_no)), {}).get(
                    "%.1f,%.1f,%.1f,%.1f"
                    % (e["x1"], e["y1"], e["x2"], e["y2"]))
                wq = rec0.get("waqf") if isinstance(rec0, dict) else rec0
            if nm == "pause" and wq and wq != "muanaqah":
                nm = wq
        # Was it actually emitted as a mark? Not everything named in the
        # internal records reaches the page as one: ink on a surah-name or
        # basmalah line comes out as undecomposed `header-ink` (the one-item
        # header law), and HDRGUARD evicts a word's stolen title ink into the
        # same group. Those elements never pass through emit(), so they have no
        # eid — and a mark that is not drawn is not a mark.
        me = eid_of(e)
        if me is None:
            return None
        mid[0] += 1
        rid = "m%d" % mid[0]
        paths = [me]
        for m in e.get("mkmembers", []) or []:
            paths.append(eid_of(m))
        info = reg.get(nm, {})
        rec = {"id": rid, "wid": wid, "mark": nm,
               "category": info.get("category"),
               "family": info.get("family"),
               "paths": [x for x in paths if x],
               "box": [round(e["x1"], 1), round(e["y1"], 1),
                       round(e["x2"], 1), round(e["y2"], 1)]}
        if e.get("fused"):
            rec["fused"] = True
        if e.get("tanform"):
            rec["arrangement"] = e["tanform"]
        marks.append(rec)
        if e.get("mnqpair"):
            pair_of.setdefault(("muanaqah", e["mnqpair"]), []).append(rid)
        if e.get("iqpair"):
            pair_of.setdefault(("iqlab", e["iqpair"]), []).append(rid)
        return rid

    for word, atoms in assignment:
        if word is None:
            # The standalone signs — the hizb rosette and the sajdah compound —
            # belong to no word but ARE marks, and the SVG draws each as a
            # master path, so they need records too or the counts cannot match.
            for atom in atoms:
                sa = atom.get("sa")
                if not sa:
                    # Ink that belongs to no word and is not a standalone sign.
                    # It still emits as a named master path — six pages carry a
                    # whole banner line this way, where the DK header mapping
                    # did not claim the line and its glyphs were classified as
                    # marks — so the graph records it with wid=None or the
                    # counts cannot match the SVG.
                    for e in atom["els"]:
                        if e.get("mark") and not e.get("mkpart"):
                            add_mark(e, None)
                    continue
                aid = ("%s:%s" % (sa[1], sa[2])) if sa[1] else None
                ids = []
                for e in atom["els"]:
                    if e.get("mark") and not e.get("mkpart"):
                        r0 = add_mark(e, None)
                        if r0:
                            ids.append(r0)
                rel = {"type": sa[0], "aid": aid, "members": ids}
                if sa[0] == "hizb" and sa[1]:
                    st = qm.starts_at(sa[1], sa[2])
                    if st.get("rub"):
                        rel.update(qm.rub_position(st["rub"]))
                relations.append(rel)
            continue
        wid = "%d:%d:%d" % (word["surah"], word["ayah"], word["pos"])
        aid = "%d:%d" % (word["surah"], word["ayah"])
        ayat.setdefault(aid, 0)
        ayat[aid] += 1
        ligs = []
        for atom in atoms:
            seg = atom.get("seg")
            if seg and (not ligs or ligs[-1] != seg["text"]):
                ligs.append(seg["text"])
        words.append({
            "wid": wid, "aid": aid,
            "uthmani": word["uthmani"],
            "rasm": qm.rasm(word["uthmani"]),
            "imlaei": word["imlaei"],
            "qpc": word.get("qpc"),
            "ligatures": ligs,
        })
        for atom in atoms:
            for e in atom["els"]:
                if e.get("mark") and not e.get("mkpart"):
                    add_mark(e, wid)

    for (kind, key), members in sorted(pair_of.items()):
        relations.append({"type": kind, "key": key, "members": members})

    # ayah -> marker. The medallions are tagged after rewrite() (they live in
    # their own artwork layer), so they are read back off the emitted SVG. Each
    # one is bound to the ayah it CLOSES, by position — see tag_ayah_markers.
    # Attribute-order independent: the marker group gained an `id` between the
    # class and the aid (the ayah->marker link), and a pattern that assumed
    # they were adjacent silently matched nothing on all 604 pages.
    for aid in re.findall(r'<g class="ayah-marker"[^>]*?\bdata-aid="([^"]*)"',
                          svg):
        relations.append({"type": "ayah-marker", "aid": aid})

    # ---- metadata --------------------------------------------------------
    surahs, seen = [], set()
    ayah_recs = []
    divisions = []
    for aid in sorted(ayat, key=lambda k: tuple(int(x) for x in k.split(":"))):
        su, ay = (int(x) for x in aid.split(":"))
        if su not in seen:
            seen.add(su)
            c = qm.chapters().get(su)
            if c:
                surahs.append(c)
        p = qm.position(su, ay)
        ayah_recs.append({"aid": aid, "words": ayat[aid], "juz": p["juz"],
                          "hizb": p["hizb"], "rub": p["rub"],
                          "rub_in_hizb": p["rub_in_hizb"], "nisf": p["nisf"]})
        st = qm.starts_at(su, ay)
        if st:
            d = {"aid": aid}
            d.update(st)
            divisions.append(d)

    return {
        "schema": "annotations", "version": VERSION,
        "edition": "hafs-kfgqpc", "page": pg,
        "surahs": surahs,
        "divisions_starting_here": divisions,
        "ayat": ayah_recs,
        "words": words,
        "marks": marks,
        "relations": relations,
    }


def _child(pg):
    rec = build_page(pg)
    os.makedirs(OUT, exist_ok=True)
    tmp = os.path.join(OUT, "%03d.json.tmp" % pg)
    json.dump(rec, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, os.path.join(OUT, "%03d.json" % pg))
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("first", type=int, nargs="?", default=1)
    ap.add_argument("last", type=int, nargs="?", default=604)
    ap.add_argument("-j", type=int, default=24)
    ap.add_argument("--print", action="store_true", dest="show")
    args = ap.parse_args()

    if os.environ.get("QSVG_ANNCHILD"):
        rec = _child(args.first)
        print(json.dumps({"page": rec["page"], "marks": len(rec["marks"]),
                          "words": len(rec["words"]),
                          "relations": len(rec["relations"])}))
        return

    if args.show:
        print(json.dumps(build_page(args.first), ensure_ascii=False, indent=1))
        return

    import concurrent.futures as cf
    os.makedirs(OUT, exist_ok=True)

    def run(pg):
        env = dict(os.environ, QSVG_ANNCHILD="1", QSVG_ROOT=ROOT)
        r = subprocess.run([sys.executable, os.path.abspath(__file__),
                            str(pg)], capture_output=True, text=True, env=env)
        try:
            return json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            return {"page": pg, "error": (r.stderr or r.stdout)[-400:]}

    bad, marks, words = 0, 0, 0
    with cf.ThreadPoolExecutor(args.j) as ex:
        for res in ex.map(run, range(args.first, args.last + 1)):
            if "error" in res:
                bad += 1
                print("FAIL p%s: %s" % (res["page"], res["error"]),
                      file=sys.stderr)
            else:
                marks += res["marks"]
                words += res["words"]
    print("annotations %d-%d -> %s: %d words, %d logical marks, %d failures"
          % (args.first, args.last, OUT, words, marks, bad))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
