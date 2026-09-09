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

CP = collections.defaultdict(set)
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

# the ink families this audit judges; letter dots are not spelled by the text
SKIP_INK = {"dot", "two_dots", "three_dots"}

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
        for src in ("data-rasm-uthmani", "data-qpc"):
            t = a.get(src)
            if t is None:
                continue
            table = CP_QPC if src == "data-qpc" else CP
            miss, sur = compare(ink, flatten(text_marks(t, table)))
            if miss or sur:
                rows.append({
                    "page": page, "word_key": key, "source": src[5:],
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
