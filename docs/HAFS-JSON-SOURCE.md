# The word-by-word-translation-translation source (`.cache/word_by_word_translation/hafs.json`) — measured, and what it is used for

Abdullah's word-by-word-translation-translation Quran is built on a "quran-mushaf" release (format
1.0, generated 2026-09-01) of the **KFGQPC UthmanicHafs v3.0** text (release
year 2026), the text of the print this artwork reproduces. He asked for it to
be used (2026-09-04). This file records what was measured against our build
before adopting anything, and what was adopted.

## What the file holds

| layer | records | note |
|---|---:|---|
| `words` | 77,432 | `w` global id (the same number for this word in every mushaf that has it; gaps at 25685 and 73951), `t` the v3.0 text, `pg`, `ln`, `e` (rasm_imlai skeleton, 77,356 of them), `marks` on 4,489 words (waqf / sajdah / hizb signs, with position) |
| `ayahs` | 6,236 | word id range per ayah |
| `pages` | 604 | word id range per page, **read from the release's explicit page breaks** |
| `surahs`, `juz` | 114, 30 | |
| `line_disagreements` | 105 | the release does not encode printed lines; `ln` is reconstructed and the file says where that reconstruction disagrees with the v2.0 CSV |

## Measured against our build (bundle of 2026-09-04)

| what | result |
|---|---|
| page membership | **identical on all 604 pages** — including the 25 pages where quran.com's layout is wrong (CLAUDE.md "Juz 30"), so this independently confirms the pipeline's page repair |
| segmentation | agreed on **6,235 of 6,236 ayahs** when measured; the one difference was 15:7, where we emitted لَّوْ / مَا as two groups and the release writes `لَّوۡمَا` as one. **Adopted 2026-09-08** — the release's boundaries are now the pipeline's, so the two sides agree on all 6,236 and our groups are 77,432, one per id (see "Adopted" below) |
| `t` vs our `qpc` form | equal on 45,757 raw, **66,757 after Unicode canonical ordering**. The rest are conventions, not content: the release keeps waqf signs in its `marks` layer (only 2 of 77,432 `t` values contain one); v3.0 writes open tanwin as U+08F0–08F2 where the v2 text we carry writes U+0656/0657; hamzah seats differ (`أٓ` vs `ـَٔا`) |
| `t` vs our `rasm_uthmani` | equal on 65,502 after ordering and the sukun map (U+06E1 → U+0652); remaining differences are the same three conventions |
| `e` vs our `search` | equal on **76,563 of 77,356**; of the 793 differences, 417 are the vocative (`ياأيها` vs our `يا أيها`) and ~374 the rasm_imlai convention for سموات / سماوات — neither side is wrong, the conventions differ |
| `ln` vs our `data-line` | 76,998 of 77,430 agree; the release itself flags its lines as reconstructed. Our lines are validated against the print (100% by `audit_wordline.py`); theirs are not a line source |

## Adopted

**The release's segmentation, as the pipeline's only boundary source.** What
was adopted from this file is not a number but the WORD LIST: where one word
ends and the next begins. `data-w` (the global id) was adopted 2026-09-04 and
withdrawn 2026-09-08 — see below.

**The cross-mushaf word id: measured, then dropped (2026-09-08).** The release
carries a global word number, and `data-w` used to ride along on every word
group. It is gone. A word is identified by `data-word-key="surah:ayah:word"` —
three ordinals, dense, in order, Hafs-specific — and that is the only word key;
ayah groups likewise carry `data-ayah-key="surah:ayah"` (Abdullah's call).

The global number is none of those things, and the two ways it departs are
worth recording, because they are exactly what a consumer joining on it has to
handle:

| | what it is | what it does to the ids |
|---|---|---|
| `numbering.missing` = **25685** | the `مِن` of 9:100, which the global scheme has and this mushaf does not write (`جَنَّٰتࣲ تَجۡرِي تَحۡتَهَا`) | the id is never used: 9:100 runs …25684, **25686**… |
| `numbering.written_joined` at 72:16:1 | `وَأَلَّوِ`, ONE written word where the scheme numbers TWO (written apart it is `وَأَن` `لَّوِ`) | it carries **73950 and 73951**; the word takes the first, the next word is **73952** |

So its space is **1–77,434** over **77,432** written words, and an ayah's id
RANGE can be wider than its word count — 72:16 is 73950–73957, eight ids for
seven words. Both are properties of a scheme spanning every mushaf, not of this
one, which is why they have no place in a Hafs-specific export.

What the release still decides is the SEGMENTATION, and that is what keeps the
triple meaningful: **word N of an ayah here is word N of that ayah there**,
proven for all 6,236 ayahs by `audit_segmentation.py`. A consumer holding the
release's own data can join on position without either side carrying a number.

**The release's word BOUNDARIES, everywhere — and it is the ONLY source of
them (2026-09-08).** Abdullah asked for our segmentation to be the release's,
and then for the release to be the single authority on where words split.

Before, boundaries were quran.com's word list corrected by a hand-written table
of four sites (`_DKSEG_SPLITS`: the three `بَعْدَ مَا` compounds and
`إِلۡ يَاسِينَ`), each argued from a different source — DigitalKhatt,
MushafDatabase, the V4 layout. Now `tools/build_word_by_word_translation_seg.py` DERIVES the whole
plan by aligning quran.com's raw word list against the release, letter by
letter:

    .cache/word_by_word_translation/seg_plan.json
      splits  2:181 [3, 27]   8:6 [4, 177]   13:37 [8, 254]   37:130 [3, 451]
      fuses   15:7  [1, 2]

The four splits come out at exactly the positions and pages the hand table had
— which is the evidence that nothing moved when the authority changed — and the
fuse is 15:7 `لَّوۡمَا`, the one place the release disagreed with us. The word
list still ARRIVES from quran.com (page membership, per-word text, positions);
its boundaries are made the release's before anything downstream sees them, and
no other source has a vote. `assign_words.py` refuses to run without the plan
rather than falling back to a different segmentation.

`tools/audit_segmentation.py` asks the question of the finished article, over
all 6,236 ayahs and 77,432 words: same word count per ayah, same letters per
word (spelling conventions folded), same global id per position. **count 0,
skeleton 0, ids 0**, both from the pipeline and from the emitted SVGs
(`--svg`). Two sites needed care and are not boundaries: 11:13:3, where
quran.com writes the typo `ٱفۡتَرَاهُ` for `ٱفۡتَرَىٰهُ`, and 27:26, where it
carries a bidi control after the sajdah sign.

Adopting the release's boundaries changed the output of exactly one page. All
five plan sites (p27, p177, p254, p451, p262) emit byte-identical SVGs to the
build before the authority moved.

Measured on the one page it touches, p262: pixel-identical (`audit_pixels`
FAILURES 0), mark flags 0 both ways, interval flags 0 both ways, width flags 3
both ways (all pre-existing, none of them the fused word), `audit_ligatures` 0,
`audit_wordline` clean, `audit_export` clean over all 604 pages. p262 is now a
bench page and `لَّوْمَا` a bench case (two bodies `لو` / `ما`, all four marks):
**SCORE 136 over 24 pages, no failures, pixelfail 0**, against an aggregate of
137 for the same 24 pages with `QSVG_WBWSEG=0` — the change is neutral on the
bench's own metrics. The fused word emits as one `<g class="word">` holding both
ligature groups `لو` / `ما` — the same ink, the joining rules unchanged.

One bench defect was found doing that A/B and fixed: `bench.py` read the RAW
`qcf_widths.json` rather than `assign_words.qcf_widths()`, so it keyed the
advance table pre-segmentation and manufactured 6 width flags on p262 (and
would have on any `_DKSEG_SPLITS` page in its set). It now asks the pipeline.

## Not adopted, and why

- **`t` as the text of record.** It is the official v3.0 text and a candidate
  to replace the composite `data-rasm-uthmani` (quran.com rasm_uthmani + KFGQPC waqf +
  DigitalKhatt at iqlab sites), but it needs the same measured contest the
  earlier sources went through (`docs/defects/text_contest_eyes.json`), with its
  `marks` layer folded back in. Not done today.
- **`e` as the search key.** Conventions differ (vocative spacing, سموات); ours
  is documented and the library's loose pass already covers the dagger-alef
  cases. Swapping would change 793 keys for no measured gain.
- **`ln`.** Reconstructed by the release's own admission; ours are proven.
