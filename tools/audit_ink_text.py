#!/usr/bin/env python3
"""Does each emitted word's TEXT describe its own INK?

Every other audit compares the ink to the BUDGET source (the DK text, under
QSVG_DKTEXT) and reads 0. This one compares the ink to the text the artefact
actually carries — `data-rasm-uthmani`, and `data-qpc` beside it — because that
is what a consumer of the SVG reads. A word whose ink draws a waqf its own
text does not spell is a defect in the artefact even when every budget balances.

Marks only: letter dots (dot/two_dots/three_dots) are a property of the letter,
not something the diacritic text spells, so they are excluded.

Usage: python3 tools/audit_ink_text.py [first] [last] [--json OUT]
"""
import collections
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scratchpad"))
from audit_marks import TEXT_WANT  # the one code-point table, not a second copy

PAGES = os.path.join(ROOT, ".cache", "words-svg", "hafs-kfqc")
FONT = os.path.join(ROOT, ".cache", "fonts", "UthmanicHafs-v-3.0.ttf")

# Three texts, and it matters which KFGQPC release is meant. `data-qpc` in the
# emitted SVG is UthmanicHafs v2.0 (.cache/official/hafsData_v2-0.json, aligned
# by scratchpad/warm_qpc.py); quran-ws/quran-text ships v3.0. They are NOT the
# same text — 61.8% of words identical, the rest almost all the shaddah/harakah
# ORDER (v2.0 writes 0651 064E, v3.0 writes 064E 0651). Mark multisets are
# order-free, so that difference cannot reach this audit, but the two must
# still be reported separately or "qpc" silently means whichever you assumed.
LIB = os.path.join(ROOT, ".cache", "word_by_word_translation", "hafs.json")


# quran-ws keeps three kinds of sign OUT of the word text, in a marks[] layer
# tagged by `k`: waqf 4277, hizb 199, sajdah 15. Only waqf belongs back in the
# word — our SVG carries waqf inside the word group, but draws the rubu_al_hizb
# rosette and the sajdah sign as their own groups, exactly as quran-ws does.
# Folding in all three was this audit's own bug: it put a ۞ on the first word of
# 199 ayahs and made them look like word-numbering drift, one every 2-3 pages
# across the whole mushaf.
FOLD_KINDS = {"waqf"}


def quran_ws():
    """quran-ws/quran-text v3.0, keyed surah:ayah:word, waqf layer folded in."""
    if not os.path.exists(LIB):
        return {}
    h = json.load(open(LIB, encoding="utf-8"))
    by = {x["w"]: x for x in h["words"]}
    out = {}
    for a in h["ayat"]:
        lo, hi = a["words"]
        # The release's `w` index space HAS GAPS — 1-77,434 over 77,432 words
        # (docs/HAFS-JSON-SOURCE.md). Numbering positions from the raw index
        # RANGE therefore shifts every word after a hole by one, which looked
        # like a word-boundary disagreement running to the end of the ayah at
        # 9:100 (7 words) and 72:16 (5 words). Number the words that EXIST.
        for pos, i in enumerate([j for j in range(lo, hi + 1) if j in by], 1):
            w = by[i]
            if w:
                out["%d:%d:%d" % (a["sura"], a["n"], pos)] = (
                    w.get("t", "")
                    + "".join(m.get("sign", "") for m in (w.get("marks") or [])
                              if m.get("k") in FOLD_KINDS))
    return out


WS = quran_ws()

# invert TEXT_WANT: code point -> mark name. A code point claimed by two names
# (ۜ is both saktah and seen_al_qiraah; ۬ both ishmam and tashil) is ambiguous
# from the text alone, so it is recorded under both and a mismatch is only
# reported when the ink name is in NEITHER.
# audit_marks buckets all five waqf signs under one name "waqf" because it only
# ever counts them; the ink names each sign. Split the bucket, or every waqf in
# the mushaf reads as a disagreement. The mapping is not chosen — it is what the
# artefact itself pairs, one-to-one over all 604 pages: U+06DA->2081 mustawi,
# U+06D6->1649 wasl_awla, U+06D7->511 waqf_awla, U+06D8->21 lazim, U+06DB->6
# muanaqah, with no code point ever pairing to two names (U+06DC excepted, which
# is the documented saktah/seen_al_qiraah split TEXT_WANT already records).
WAQF = {
    "\u06da": "waqf_jaiz_mustawi_al_tarafayn",
    "\u06d6": "waqf_jaiz_wasl_awla",
    "\u06d7": "waqf_jaiz_waqf_awla",
    "\u06d8": "waqf_lazim",
}

# U+0622 (alef with madda above) is one code point carrying a letter AND a
# maddah; rasm_uthmani decomposes it as U+0627 U+0653 and quran-ws v3.0 does
# not. Without this, every alef-madda in the mushaf reads as a maddah the text
# forgot — 2,934 phantom words, the single largest class against quran-ws.
PRECOMPOSED = {"\u0622": "maddah"}

# The imalah dot is written U+06EA by rasm_uthmani and U+065C by quran-ws.
# One site in the mushaf (11:41:6 مَجْر۪ىٰهَا), a clean 1<->1 swap: ours writes
# U+06EA once and U+065C never, quran-ws the reverse. Same dot, same place.
IMALAH_ALT = {"\u065c": "imalah"}

CP = collections.defaultdict(set)
for ch, name in IMALAH_ALT.items():
    CP[ch].add(name)
for ch, name in PRECOMPOSED.items():
    CP[ch].add(name)
for ch, name in WAQF.items():
    CP[ch].add(name)
for name, cps in TEXT_WANT.items():
    if name == "waqf":
        continue

    for s in cps:
        for ch in s:
            CP[ch].add(name)

# data-qpc is a DIFFERENT ENCODING of the same marks, not a different spelling,
# so it must be read in its own alphabet or every word carrying one of these
# four signs reads as a disagreement. The correspondence is derived, not
# assumed: over 604 pages these are the only code points qpc writes where
# rasm-uthmani writes something else, each maps to exactly one counterpart, and
# no word pairs a code point two ways (U+0652 <-> U+06DF 2774, U+0657 <->
# U+08F0 1933, U+065E <-> U+08F1 1298, U+0656 <-> U+08F2 1133).
QPC_AS = {
    "\u0652": "rounded_zero",       # uthmani U+06DF; qpc reserves U+06E1 for sukun
    "\u0657": "tanwin_al_fath",     # uthmani U+08F0, the open tanwin
    "\u065e": "tanwin_al_damm",     # uthmani U+08F1
    "\u0656": "tanwin_al_kasr",     # uthmani U+08F2
}
CP_QPC = dict(CP)
for ch, name in QPC_AS.items():
    CP_QPC[ch] = {name}

# U+0653 is not one mark. Shaped by the print's own font it draws EITHER a
# wavy madda (alone, or on a bare alef: آ) OR, absorbed into the لأ ligature,
# a straight slash indistinguishable from a fathah — which is what the print
# draws and what this pipeline labels `fathah`. Measured over the 277 sites
# where the two readings disagreed: 277/277 absorb into a ligature, and the
# only two words that ALSO yield a standalone madda glyph (18:5:7, 33:5:2) are
# the two carrying a second, agreed maddah in بَآئِ. So the name depends on the
# shaping context, not on the code point, and a flat table gets it wrong 277
# times. Abdullah's reading of the ink; confirmed with HarfBuzz against
# UthmanicHafs v3.0.
# lam + (optional fathah) + alef-hamza + madda. HarfBuzz shapes this whole run
# into ONE ligature glyph in UthmanicHafs (578/579/580), and that glyph draws
# the madda as a straight slash — the fathah shape the print uses and this
# pipeline labels `fathah`. Outside the ligature the SAME U+0653 draws as the
# wavy madda (أٓ alone, آ, بَآئِ all do). So the mark's name depends on the
# shaping context, not the code point.
LAM_ALEF_HAMZA = re.compile(
    "\u0644[\u064b-\u0655\u0670\u06e1\u08f0-\u08f2]*\u0623\u0653")

# the ink families this audit judges; letter dots are not spelled by the text
SKIP_INK = {"dot", "two_dots", "three_dots"}

# Letters only, for the alignment check below. Marks are exactly what is in
# dispute, so they cannot be part of deciding whether two records are the same
# word; the letter skeleton can.
_MARKS = set("\u064b\u064c\u064d\u064e\u064f\u0650\u0651\u0652\u0653"
             "\u0654\u0655\u0656\u0657\u065e\u0670\u06d6\u06d7\u06d8"
             "\u06d9\u06da\u06db\u06dc\u06df\u06e0\u06e1\u06e2\u06e3"
             "\u06e4\u06e5\u06e6\u06e8\u06e9\u06ea\u06eb\u06ec\u06ed"
             "\u0640\u08f0\u08f1\u08f2\u065c\u0655\u0656\u0657")
# a hamzah is written as a LETTER (U+0621) or as a MARK over a seat (U+0654);
# the skeleton must not treat that as two different words
_FOLD = {"\u0621": "", "\u0622": "\u0627", "\u0623": "\u0627", "\u0625": "\u0627",
         "\u0671": "\u0627", "\u0649": "\u064a", "\u0624": "\u0648",
         "\u0626": "\u064a", "\u0629": "\u0647"}


def skeleton(t):
    return "".join(_FOLD.get(c, c) for c in (t or "") if c not in _MARKS)


WORD = re.compile(r'<g class="word" ([^>]*)>(.*?)(?=<g class="word" |</g></g>|$)', re.S)
ATTR = re.compile(r'([a-z-]+)="([^"]*)"')
MARK = re.compile(r'data-mark="([^"]+)"')


def text_marks(t, table=None):
    """The mark names a spelling calls for, as a multiset."""
    table = CP if table is None else table
    c = collections.Counter()
    for ch in t or "":
        names = table.get(ch)
        if names:
            c[tuple(sorted(names))] += 1
    return c


def flatten(c):
    """Counter keyed by name-tuples -> Counter keyed by a single name where the
    code point is unambiguous, plus the ambiguous ones kept as tuples."""
    out = collections.Counter()
    for k, n in c.items():
        out[k[0] if len(k) == 1 else k] += n
    return out


def compare(ink, txt):
    """Return (missing, surplus) as Counters of mark names.

    An ambiguous code point satisfies any of its names, so it is resolved
    greedily against whatever the ink actually drew before anything is called
    a difference.
    """
    ink = collections.Counter(ink)
    want = collections.Counter()
    for k, n in txt.items():
        if isinstance(k, tuple):
            for _ in range(n):
                hit = next((x for x in k if ink[x] > want[x]), k[0])
                want[hit] += 1
        else:
            want[k] += n
    return want - ink, ink - want


def page_rows(path):
    s = open(path, encoding="utf-8").read()
    page = int(os.path.basename(path)[:3])
    rows = []
    cov = collections.Counter()
    for attrs, body in WORD.findall(s):
        a = dict(ATTR.findall(attrs))
        key = a.get("data-word-key")
        if not key:
            continue
        ink = [m for m in MARK.findall(body) if m not in SKIP_INK]
        cov["words"] += 1
        cov["marks"] += len(ink)
        for src in ("data-rasm-uthmani", "data-qpc", "quran-ws"):
            t = WS.get(key) if src == "quran-ws" else a.get(src)
            if t is None:
                continue
            # quran-ws numbers words by its own scheme, which drifts from ours
            # at the split/fuse sites (72:16 وَأَلَّوِ holds two of its numbers).
            # A drifted row compares one word's ink to another word's text and
            # reports pure noise, so it is counted apart, never as a mismatch.
            if skeleton(t) != skeleton(a.get("data-rasm-uthmani")):
                cov["misaligned_" + src] += 1
                continue
            # v2.0 and v3.0 share the KFGQPC alphabet; only rasm_uthmani differs
            table = CP if src == "data-rasm-uthmani" else CP_QPC
            want = flatten(text_marks(t, table))
            n = len(LAM_ALEF_HAMZA.findall(t))
            if n:
                want["maddah"] = want.get("maddah", 0) - n
                if want["maddah"] <= 0:
                    want.pop("maddah", None)
                want["fathah"] = want.get("fathah", 0) + n
            miss, sur = compare(ink, want)
            if miss or sur:
                rows.append({
                    "page": page, "word_key": key,
                    "source": src[5:] if src.startswith("data-") else src,
                    "text": t,
                    "ink_draws_text_omits": dict(sur),
                    "text_spells_ink_omits": dict(miss),
                })
    return rows, cov


def main():
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    first = int(args[0]) if args else 1
    last = int(args[1]) if len(args) > 1 else 604
    out = None
    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]

    rows = []
    seen = collections.Counter()
    pages = 0
    for p in sorted(glob.glob(os.path.join(PAGES, "*.svg"))):
        n = int(os.path.basename(p)[:3])
        if first <= n <= last:
            pages += 1
            r, c = page_rows(p)
            rows.extend(r)
            seen.update(c)

    # A clean result is only meaningful beside the work that produced it: this
    # audit's ancestor reported "0 pages" for weeks because it matched 0 of
    # 77,432 words on an attribute-name mismatch. Print the coverage first, and
    # refuse the range outright if a page never got emitted.
    missing = (last - first + 1) - pages
    print("compared %d words / %d mark elements over %d pages"
          % (seen["words"], seen["marks"], pages))
    for k in sorted(seen):
        if k.startswith("misaligned_"):
            print("  %s: %d words the two sources do not key to the same word "
                  "(skipped, not a mismatch)" % (k[11:], seen[k]))
    if missing:
        raise SystemExit("REFUSING: %d page(s) missing from %s — regenerate "
                         "them first, or this reads clean by not looking"
                         % (missing, PAGES))

    by_src = collections.Counter(r["source"] for r in rows)
    fam = collections.Counter()
    for r in rows:
        for d, sign in ((r["ink_draws_text_omits"], "ink+"),
                        (r["text_spells_ink_omits"], "text+")):
            for k, n in d.items():
                fam[(r["source"], sign, str(k))] += n

    print("words where the emitted text disagrees with the emitted ink")
    for src, n in by_src.most_common():
        print("  %-14s %6d words" % (src, n))
    print("\n  %-14s %-6s %-34s %s" % ("source", "side", "mark", "count"))
    for (src, sign, k), n in fam.most_common(40):
        print("  %-14s %-6s %-34s %d" % (src, sign, k, n))
    print("\npages touched: %d" % len({r["page"] for r in rows}))
    if out:
        json.dump(rows, open(out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("wrote %s (%d rows)" % (out, len(rows)))


if __name__ == "__main__":
    main()
