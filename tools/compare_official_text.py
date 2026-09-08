#!/usr/bin/env python3
"""Compare our emitted word text against the King Fahd Complex's own data.

The reference is `UthmanicHafs_v2-0` (`hafsData_v2-0.json`), the Complex's
published RasmUthmani text for the 1441H Hafs mushaf — 6,236 ayah records, each one
`ayah_text` plus `aya_text_emlaey`. This is the same body of text the artwork was
set from, which is what makes it worth checking against.

WHAT THIS FILE CAN AND CANNOT SETTLE
====================================

It is an **ayah-level** text. There are no word records in it at all. So:

  · It IS authoritative for spelling — every letter and mark of a word.
  · It is NOT a word list. Its whitespace encodes the RasmUthmani rasm, including
    the المقطوع والموصول convention that writes مَالِيَ joined and إِلۡ يَاسِينَ
    separated. Splitting `ayah_text` on spaces measures that convention, NOT our
    segmentation, and reports every mawṣūl pair in the Quran as a false defect.

`--segmentation` therefore prints its results as *candidates to adjudicate*
against sources that actually mark words (the KFGQPC V4 layout, DigitalKhatt,
MushafDatabase), never as defects. See docs/MAQTU-MAWSUL.md for the precedence
rule and for what the surviving candidates turned out to be.

    python3 tools/compare_official_text.py                 # exact-match rate
    python3 tools/compare_official_text.py --diff          # every differing word
    python3 tools/compare_official_text.py --segmentation  # word-count candidates
"""
import argparse
import glob
import json
import os
import re
import sys

ROOT = (os.environ.get("QSVG_ROOT")
        or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG = os.path.join(ROOT, ".cache", "words-svg", "hafs-kfqc")
OFFICIAL = os.path.join(REPO, ".cache", "official", "hafsData_v2-0.json")

# The ayah number is drawn as a marker, not written as a word: the Complex's
# text ends each ayah with one PUA glyph from the ayah_number range, preceded by
# U+00A0. We hold the number as a medallion, so it never enters a word.
_AYAH_MARK = re.compile(r"[ﯓ-﷿ﹰ-﻿۝]| ")
# Standalone furniture that is ink of its own in our decomposition, never part
# of a word: the rubʿ rosette and the ayah-end circle.
_FURNITURE = re.compile(r"^[۞۝\s]+$")


# ---------------------------------------------------------------------------
# Normalising the two encodings onto one convention
# ---------------------------------------------------------------------------
# CLAUDE.md: "Compare after normalising code points to families, or you measure
# encoding rather than content." Raw, the two texts disagree on 51,261 character
# edits and 46.7% of words — and 50,645 of those edits are six substitutions,
# each applied with perfect consistency. They are spelling conventions for the
# same drawn mark, not different content.
#
# DIRECTIONAL: the Complex's convention rewritten into ours. Applied
# SIMULTANEOUSLY via str.translate, because the first two are a SWAP — folding
# them one after another would send 06E1 to 0652 and then straight on to 06DF,
# collapsing sukun and the silent circle into one mark and destroying a real
# distinction.
_FOLD = {
    0x06E1: "ْ",   # 36,641  small high dotless head  -> sukun
    0x0652: "۟",   #  3,973  sukun -> small high rounded zero (silent)
    0x0657: "ࣰ",   #  2,901  inverted dammah -> open tanwin_al_fath
    0x0656: "ࣲ",   #  1,931  subscript alef -> open tanwin_al_kasr
    0x065E: "ࣱ",   #  1,799  fathah with two dots -> open tanwin_al_damm
}
# Multi-character, same direction: hamzah seats. The Complex writes the seat
# decomposed; we write it precomposed, and carries the hamzah of the maddah form
# on a tatweel (which is load-bearing ink — see the _clean_word commit).
_FOLD_SEQ = [("يٕ", "ئ"),
             ("أٓ", "ـَٔا")]
# BOTH sides: ya and alef maksura are drawn identically at word-final and
# pre-hamzah positions and the two texts choose differently there. Collapsing on
# both sides removes the distinction rather than folding one into the other,
# because a blanket directional fold would also rewrite every medial ya.
_FOLD_BOTH = {0x0649: "ي"}


def normalise_official(t):
    for a, b in _FOLD_SEQ:
        t = t.replace(a, b)
    return t.translate(_FOLD).translate(_FOLD_BOTH)


def normalise_ours(t):
    return t.translate(_FOLD_BOTH)


def official_words(path):
    """{"surah:ayah": [tokens]} — a WHITESPACE SPLIT, with all its limits."""
    with open(path, encoding="utf-8-sig") as fh:
        data = json.load(fh)
    out = {}
    for a in data:
        text = _AYAH_MARK.sub(" ", a["ayah_text"])
        toks = [t for t in text.split() if t and not _FURNITURE.match(t)]
        out["%d:%d" % (a["surah_no"], a["ayah_no"])] = toks
    return out


def our_words():
    """{"surah:ayah": {position: rasm_uthmani}} from the emitted pages."""
    out = {}
    pat = re.compile(r'data-word-key="(\d+):(\d+):(\d+)"[^>]*?data-rasm-uthmani="([^"]*)"')
    for p in sorted(glob.glob(os.path.join(SVG, "*.svg"))):
        with open(p, encoding="utf-8") as fh:
            for m in pat.finditer(fh.read()):
                key = "%s:%s" % (m.group(1), m.group(2))
                out.setdefault(key, {})[int(m.group(3))] = m.group(4)
    return out


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--diff", action="store_true",
                    help="print every word whose text differs")
    ap.add_argument("--segmentation", action="store_true",
                    help="ayahs whose word COUNT differs — candidates only")
    ap.add_argument("--data", default=OFFICIAL)
    args = ap.parse_args()

    if not os.path.exists(args.data):
        raise SystemExit("official data not found: %s" % args.data)

    off, ours = official_words(args.data), our_words()
    same = raw_same = total = 0
    diffs, segs = [], []

    for key in sorted(off, key=lambda k: [int(x) for x in k.split(":")]):
        if key not in ours:
            continue
        o, u = off[key], ours[key]
        mine = [u[p] for p in sorted(u)]
        if len(o) != len(mine):
            segs.append((key, len(o), len(mine), o, mine))
            continue          # counts differ: word-by-word-translation-translation comparison is moot
        for a, b in zip(o, mine):
            total += 1
            if a == b:
                raw_same += 1
            if normalise_official(a) == normalise_ours(b):
                same += 1
            elif args.diff:
                diffs.append((key, a, b))

    if args.segmentation:
        print("Word-count candidates: %d ayahs of %d.\n"
              "These are NOT defects. The official file is ayah-level text, so\n"
              "its spaces encode the rasm (المقطوع والموصول), not word bounds.\n"
              "Adjudicate each against a source that marks words — see\n"
              "docs/MAQTU-MAWSUL.md.\n" % (len(segs), len(off)))
        for key, no, nu, o, u in segs:
            i = next((j for j in range(min(no, nu)) if o[j] != u[j]), 0)
            print("  %-9s official %2d  ours %2d   diverge at %d" % (key, no, nu, i + 1))
            print("        official: %s" % " | ".join(o[i:i + 3]))
            print("        ours:     %s" % " | ".join(u[i:i + 3]))
        return

    if args.diff:
        for key, a, b in diffs:
            print("  %-9s official=%s  ours=%s" % (key, a, b))
        print()

    pct = 100.0 * same / total if total else 0.0
    raw = 100.0 * raw_same / total if total else 0.0
    print("comparable words:      %d" % total)
    print("  raw code points:     %d  = %.4f%%   (measures ENCODING, see _FOLD)"
          % (raw_same, raw))
    print("  normalised:          %d  = %.4f%%   <- the content figure"
          % (same, pct))
    print("word-count candidates: %d ayahs (run --segmentation)" % len(segs))


if __name__ == "__main__":
    main()
