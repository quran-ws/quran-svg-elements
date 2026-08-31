#!/usr/bin/env python3
"""Build the line table from the KFGQPC V4 (1441H) layout — the print's own edition.

WHY THIS REPLACED THE DIGITALKHATT TABLE
========================================

`dk_lines.json` came from DigitalKhatt's layout database, which models the
**KFGQPC V2, 1421H** printing. The artwork here is the **V4, 1441H** printing.
QUL lists them as separate resources (Digital Khatt is id 21, "KFGQPC V2 1421H
print"; V4 is id 19, "KFGQPC V4 layout (1441H print)"), and the DK database says
so in its own `info` table, in a string that ships with the download.

Measured against the emitted pages, all 77,432 words:

    DigitalKhatt V2 (1421H)    96.33%   121 pages differ
    KFGQPC V4    (1441H)      100.0000%   0 pages differ

118 of those 121 pages have EVERY word shifted by the same amount — a layout
offset between two printings, not scattered disagreement. That is why it never
looked like ordinary noise, and why it survived so long as an accepted residue.

It cost real work: of 71 pages the pipeline had to reflow, 50 were DK-drift
pages. With 121 of 604 pages carrying drift, chance would put about 14 there.

See `docs/EDITION-1441-FINDING.md` for the full measurement.

THE SOURCE
==========

`github.com/MohamadHajjRabee/quran-qcf4` publishes the 1441H layout as one JSON
per page, each line listing its words with `verse_key` and `position`. That is
all this needs; the QCF4 fonts themselves are not read (their glyphs are
anonymous word-pictures — `glyph4`, `glyph5` — with no text to recover).

TWO THINGS THE V4 DATA COUNTS DIFFERENTLY
=========================================

  · The 15 sajdah signs are `type: "word"` there and marks here. Skipped —
    a modelling difference, not a disagreement.
  · V4 splits `إِلْ يَاسِينَ` (37:130) into two words where the older source
    held one. That is the print, and it closes the p451 open item.

    python3 tools/build_v4_lines.py --src /path/to/quran-qcf4/pages
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, ".cache", "v4_lines.json")


def build(src):
    """{page: {"surah:ayah:word": line}} — the same shape dk_lines.json had."""
    table, pages, words, skipped = {}, 0, 0, 0
    for n in range(1, 605):
        f = os.path.join(src, "%03d.json" % n)
        if not os.path.exists(f):
            print("missing page %d at %s" % (n, f), file=sys.stderr)
            continue
        with open(f, encoding="utf-8") as fh:
            page = json.load(fh)
        per = {}
        for line in page.get("lines", []):
            ln = line.get("line")
            for w in line.get("words", []):
                # "word" excludes the ayah markers, the quarter/hizb glyphs and
                # the sajdah signs, all of which this project holds as marks.
                if w.get("type") != "word":
                    skipped += 1
                    continue
                # The 15 sajdah signs are typed "word" here but carry a glyph
                # placeholder for text (`#1969`, all 15 and nothing else). This
                # project holds them as marks, not words, so they must not enter
                # a WORD line table — a word id nothing can resolve would look
                # like a missing word rather than a modelling difference.
                if re.match(r"^#\d+$", str(w.get("text", ""))):
                    skipped += 1
                    continue
                vk, pos = w.get("verse_key"), w.get("position")
                if not (vk and pos):
                    skipped += 1
                    continue
                per["%s:%s" % (vk, pos)] = ln
        if per:
            table[str(n)] = per
            pages += 1
            words += len(per)
    return table, pages, words, skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="quran-qcf4/pages directory")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    table, pages, words, skipped = build(args.src)
    if pages != 604:
        raise SystemExit("built %d pages, expected 604 — refusing to write a "
                         "partial line table" % pages)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(table, fh, ensure_ascii=False, sort_keys=True,
                  separators=(",", ":"))
    print("%s: %d pages, %d words (%d non-word glyphs skipped)"
          % (args.out, pages, words, skipped))


if __name__ == "__main__":
    main()
