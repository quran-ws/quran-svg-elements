#!/usr/bin/env python3
"""Derive the whole word SEGMENTATION from the word-by-word-translation-translation release.

`.cache/word_by_word_translation/hafs.json` (quran-ws/quran-text, `data/mushaf/hafs.json` — the
"quran-mushaf" release of the KFGQPC UthmanicHafs v3.0 text) is the audited
word-by-word-translation-translation source Abdullah's product is keyed on. This file takes WHERE
WORDS SPLIT from it, and it is the ONLY source of that (Abdullah,
2026-09-08). Its cross-muṣḥaf word number is deliberately not used — see
release_words() for why.

What that replaces: the pipeline's word list arrives from quran.com, whose
boundaries were then corrected by a hand-written table of four sites
(`_DKSEG_SPLITS` — the three `بَعْدَ مَا` compounds and `إِلۡ يَاسِينَ`), each
argued from a different source. Those four are now DERIVED, together with the
one fuse (15:7 `لَّوۡمَا`), by aligning quran.com's raw word list against the
release. The four come out exactly as the hand table had them, which is the
evidence that nothing moved when the authority changed — but they are no longer
claims this repo makes: they are what the release says.

The plan is written as `.cache/word_by_word_translation/seg_plan.json`:

    {"splits": {"2:181": [3, 27], ...},   # at position 3, one word becomes two
     "fuses":  {"15:7": [1, 2]}}          # at position 1, two words become one

with the page number carried on a split because the advance-splitting pass
reads the compound's cached page. `assign_words.py` applies it under
QSVG_WBWSEG (default on); with it off the raw quran.com boundaries are used and
nothing here is consulted.

A site that cannot be expressed — a split into more than two, an ayah needing
both a split and a fuse, a fuse whose halves are drawn on different lines
(one word cannot express a line break), a split quran.com does not write as one
word with an internal space — stops the build rather than being guessed at.

    python3 tools/build_word_by_word_translation_seg.py            # -> .cache/word_by_word_translation/seg_plan.json

`tools/audit_segmentation.py` then proves, over all 6,236 ayahs, that what the
pipeline emits IS the release's segmentation.
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
SRC = os.path.join(ROOT, ".cache", "word_by_word_translation", "hafs.json")
OUT = os.path.join(ROOT, ".cache", "word_by_word_translation", "seg_plan.json")

_MARKS = re.compile("[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u08d3-\u08ff\u0640]")


def skeleton(s):
    """Letters only, with the conventions the two spellings differ in folded:
    alef and ya variants, hamzah seats, tatweel. What two spellings of one word
    share — the release writes `فِي` where we write `فِى`, `بَِٔايَٰتِ` where we
    write `بِـَٔايَٰتِ`, and neither is a boundary difference."""
    s = _MARKS.sub("", unicodedata.normalize("NFC", s))
    for a, b in (("\u0671", "\u0627"), ("\u0623", "\u0627"),
                 ("\u0625", "\u0627"), ("\u0622", "\u0627"),
                 ("\u0649", "\u064a"), ("\u0624", "\u0648"),
                 ("\u0626", "\u064a"), ("\u0629", "\u0647")):
        s = s.replace(a, b)
    for c in ("\u0654", "\u0655", "\u0621",
              " ", "\u200c", "\u200d", "\u200e", "\u200f"):
        # spaces go too: quran.com writes the fused compounds as one token with
        # an internal space, and that space is the thing being adjudicated.
        # The bidi controls are typesetting furniture it carries after ۩.
        s = s.replace(c, "")
    return s


def release_words(src=SRC):
    """{(surah, ayah): [word text]} — the release's own word list, in order.

    Two shipped shapes are read: the flat one (`words` a list of strings with
    `ayah_starts` / `surahs`) and the record one (`words` carrying `w`/`t` with
    an `ayahs` index). They are the same words; only the packing differs.

    The release also carries a cross-muṣḥaf word NUMBER, and this pipeline
    deliberately does not use it (Abdullah, 2026-09-08): a word is identified
    by `surah:ayah:word`, three ordinals, dense, in order, Ḥafṣ-specific. That
    number is none of those things — its space is 1-77,434 over 77,432 written
    words, because 25685 is a word this muṣḥaf does not write (the `مِن` of
    9:100) and 72:16:1 `وَأَلَّوِ` is one written word carrying both 73950 and
    73951. Both are properties of a scheme spanning every muṣḥaf, not of this
    one. What the release still decides here is the SEGMENTATION, so position N
    of an ayah is word N of that ayah in the release — which is exactly what
    tools/audit_segmentation.py proves, for all 6,236.
    """
    d = json.load(open(src, encoding="utf-8"))
    w = d["words"]
    out = {}
    if w and isinstance(w[0], str):
        starts = d["ayah_starts"]
        for s in d["surahs"]:
            for j in range(s["ayah_count"]):
                i = s["first_ayah"] + j
                en = starts[i + 1] if i + 1 < len(starts) else len(w)
                out[(s["number"], j + 1)] = w[starts[i]:en]
    else:
        by_id = {x["w"]: x["t"] for x in w}
        # The two keys below are the release's own, quoted as it writes them
        # (docs/HAFS-JSON-SOURCE.md); what this project calls them once read is
        # ayah and surah.  terminology: ignore
        for a in d["ayat"]:
            lo, hi = a["words"]
            out[(a["sura"], a["n"])] = [by_id[i] for i in range(lo, hi + 1)
                                        if i in by_id]
    return out


def our_words():
    """{(surah, ayah): [(pos, rasm_uthmani, page)]} as the word source delivers it,
    with the whole plan OFF — the raw boundaries the plan is computed against."""
    os.environ["QSVG_WBWSEG"] = "0"
    # and the DK text with it: DK segments the بَعْدَ مَا compounds itself, so
    # with the plan off its positions run ahead of quran.com's and the word
    # text stops being quran.com's own. Boundaries are read from the word
    # source's own tokens, which is what the plan is a plan ABOUT.
    os.environ["QSVG_DKTEXT"] = "0"
    sys.path.insert(0, TOOLS)
    import assign_words
    by_ayah = collections.defaultdict(dict)
    for pg in range(1, 605):
        for words in assign_words.page_words(
                pg, os.path.join(ROOT, ".cache", "words")).values():
            for w in words:
                by_ayah[(w["surah"], w["ayah"])][w["pos"]] = (w["rasm_uthmani"], pg)
    return {k: [(p,) + v[p] for p in sorted(v)] for k, v in by_ayah.items()}


def plan_ayah(ours, theirs):
    """([split], [fuse]) for one ayah, or a string saying why it cannot be made.

    Walks the two word lists together. Our word matching theirs one for one is
    the common case; several of ours joining to make one of theirs is a FUSE;
    one of ours covering several of theirs is a SPLIT, and is only expressible
    where quran.com wrote the compound as one word with an internal space, one
    space part per released word (that is what the splitting pass acts on).
    """
    splits, fuses, i, j = [], [], 0, 0
    while i < len(ours) and j < len(theirs):
        a, b = skeleton(ours[i][1]), skeleton(theirs[j])
        if a == b or len(a) == len(b):
            # equal skeletons, or two spellings of the same length: one word
            # against one word either way. A boundary difference always shows
            # as one side's word covering more letters than the other's, so an
            # equal-length mismatch is spelling (11:13:3, where quran.com
            # writes the typo ٱفۡتَرَاهُ), never a boundary.
            i, j = i + 1, j + 1
            continue
        if len(a) < len(b):                             # ours are smaller: fuse
            acc, start = a, i
            while acc != b and i + 1 < len(ours) and len(acc) < len(b):
                i += 1
                acc += skeleton(ours[i][1])
            if acc != b:
                return "cannot align at our %d / their %d" % (i, j)
            fuses.append((ours[start][0], i - start + 1))
            i, j = i + 1, j + 1
            continue
        acc, start = b, j                               # theirs are smaller: split
        while acc != a and j + 1 < len(theirs) and len(acc) < len(a):
            j += 1
            acc += skeleton(theirs[j])
        if acc != a:
            return "cannot align at our %d / their %d" % (i, j)
        n = j - start + 1
        parts = [t for t in ours[i][1].split(" ") if t]
        if len(parts) != n:
            return ("%s is %d released words but the word source writes it as "
                    "one token without %d space-separated parts"
                    % (ours[i][1], n, n))
        if n != 2:
            return "%s splits into %d, and only two is expressible" % (
                ours[i][1], n)
        splits.append((ours[i][0], ours[i][2]))
        i, j = i + 1, j + 1
    if i != len(ours) or j != len(theirs):
        return "ran out: %d/%d ours, %d/%d theirs" % (i, len(ours), j,
                                                      len(theirs))
    return splits, fuses


def main():
    theirs_all = release_words()
    ours_all = our_words()
    import assign_words                       # imported by our_words()
    lines = assign_words._qcf_lines()
    splits, fuses, bad = {}, {}, []
    for k in sorted(ours_all):
        theirs = theirs_all.get(k)
        if theirs is None:
            bad.append("%d:%d absent from the release" % k)
            continue
        res = plan_ayah(ours_all[k], theirs)
        if isinstance(res, str):
            bad.append("%d:%d %s" % (k[0], k[1], res))
            continue
        sp, fu = res
        if len(sp) > 1 or len(fu) > 1 or (sp and fu):
            bad.append("%d:%d needs %d split(s) and %d fuse(s); one of one "
                       "kind per ayah is what the pipeline expresses"
                       % (k[0], k[1], len(sp), len(fu)))
            continue
        for pos, n in fu:
            # one word cannot express a line break running through it
            # (docs/MAQTU-MAWSUL.md), so a fuse whose halves are drawn on
            # different lines is not representable and must not be written.
            lns = {ln for d in lines.values()
                   for p2 in range(pos, pos + n)
                   for ln in [d.get("%d:%d:%d" % (k[0], k[1], p2))]
                   if ln is not None}
            if len(lns) > 1:
                bad.append("%d:%d: the halves are drawn on lines %s — a fuse "
                           "cannot express a line break"
                           % (k[0], k[1], sorted(lns)))
                continue
            fuses["%d:%d" % k] = [pos, n]
        for pos, pg in sp:
            splits["%d:%d" % k] = [pos, pg]
    if bad:
        print("\n".join(bad))
        return 1
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"splits": splits, "fuses": fuses},
              open(OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, sort_keys=True)
    print("%s: %d split(s), %d fuse(s)" % (OUT, len(splits), len(fuses)))
    for k, (pos, pg) in sorted(splits.items()):
        s0, a0 = (int(x) for x in k.split(":"))
        w = next(x[1] for x in ours_all[(s0, a0)] if x[0] == pos)
        print("  split %-8s p%-4d %s -> %s" % (k, pg, w, " / ".join(w.split())))
    for k, (pos, n) in sorted(fuses.items()):
        s0, a0 = (int(x) for x in k.split(":"))
        o = [w for p, w, _ in ours_all[(s0, a0)] if pos <= p < pos + n]
        print("  fuse  %-8s %s -> %s" % (k, " / ".join(o), "".join(o)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
