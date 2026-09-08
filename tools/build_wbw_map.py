#!/usr/bin/env python3
"""Derive every word's GLOBAL word id from the word-by-word source.

`.cache/wbw/hafs.json` is the "quran-mushaf" release (format 1.0, generated
2026-09-01) of the KFGQPC UthmanicHafs v3.0 text — the text of the print this
artwork reproduces — with one record per word: `w` (a global id shared by
every mushaf that has the word), `t` (the v3.0 text), `pg`, `ln`, `e`
(imlaei skeleton) and a `marks` layer for the waqf / sajdah / hizb signs.
Abdullah's word-by-word product is built on it (2026-09-04), so a word group
in the SVG must carry the same id: `data-w`.

Measured against our build before adoption (docs/HAFS-JSON-SOURCE.md): page
membership agrees on all 604 pages; segmentation agrees on 6,235 of 6,236
ayahs — at 15:7 the print's spacing gives us لَّوْ / مَا as two groups where the
release writes one word — so the map is 77,433 wids onto 77,432 ids, exact
everywhere and shared by the two pieces of that one word.

Nothing here is hand-kept. The map is DERIVED, by ayah: positional when both
sides have the same number of words, and where they differ, by walking our
words and merging consecutive ones until their joined letter skeleton equals
the release's word. Any ayah that does not align stops the build; the emitter
refuses to write a page whose word is not in the map.

    python3 tools/build_wbw_map.py            # -> .cache/wbw/wid_to_w.json
"""
import collections
import json
import os
import re
import sys
import unicodedata

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, ".cache", "wbw", "hafs.json")
OUT = os.path.join(ROOT, ".cache", "wbw", "wid_to_w.json")

_MARKS = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭ࣓-ࣿـ]")


def skeleton(s):
    """Letters only, alef variants folded: what two spellings of one word share."""
    s = _MARKS.sub("", unicodedata.normalize("NFC", s))
    return (s.replace("ٱ", "ا").replace("أ", "ا")
             .replace("إ", "ا").replace("آ", "ا")
             .replace("ٔ", "").replace("ٕ", ""))


def align(ours, theirs):
    """{pos: w} for one ayah. `ours` is [(pos, text)] in order, `theirs` the
    release's word records in order. None when the two cannot be reconciled."""
    if len(ours) == len(theirs):
        return {p: t["w"] for (p, _), t in zip(ours, theirs)}
    out, i = {}, 0
    for t in theirs:
        want, acc, start = skeleton(t["t"]), "", i
        while i < len(ours) and len(acc) < len(want):
            acc += skeleton(ours[i][1])
            i += 1
        if acc != want:
            return None
        for p, _ in ours[start:i]:
            out[p] = t["w"]
    return out if i == len(ours) else None


def our_words(cache_dir):
    """{(surah, ayah): [(pos, uthmani)]} over the whole mushaf, from the same
    word cache the emitter reads (so the map matches what is emitted)."""
    sys.path.insert(0, TOOLS)
    import assign_words
    by_ayah = collections.defaultdict(dict)
    for pg in range(1, 605):
        for words in assign_words.page_words(pg, cache_dir).values():
            for w in words:
                by_ayah[(w["surah"], w["ayah"])][w["pos"]] = w["uthmani"]
    return {k: sorted(v.items()) for k, v in by_ayah.items()}


def build(src=SRC, cache_dir=None):
    d = json.load(open(src, encoding="utf-8"))
    words = sorted(d["words"], key=lambda w: w["w"])
    theirs = {}
    for a in d["ayat"]:
        lo, hi = a["words"]
        theirs[(a["sura"], a["n"])] = [w for w in words if lo <= w["w"] <= hi]
    ours = our_words(cache_dir or os.path.join(ROOT, ".cache", "words"))
    m, bad, shared = {}, [], []
    for key, ow in sorted(ours.items()):
        r = align(ow, theirs.get(key, []))
        if r is None:
            bad.append(key)
            continue
        for p, w in r.items():
            m["%d:%d:%d" % (key[0], key[1], p)] = w
        c = collections.Counter(r.values())
        shared += [("%d:%d" % key, w) for w, n in c.items() if n > 1]
    if bad:
        raise SystemExit("cannot align %d ayah(s): %s" % (len(bad), bad[:10]))
    return m, shared, len(words)


def main():
    m, shared, n = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(m, open(OUT, "w", encoding="utf-8"), ensure_ascii=False,
              separators=(",", ":"), sort_keys=True)
    print("wid_to_w: %d wids -> %d of %d ids; shared: %s" % (
        len(m), len(set(m.values())), n, shared or "none"))


if __name__ == "__main__":
    main()
