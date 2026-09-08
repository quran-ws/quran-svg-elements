# The word-by-word source (`.cache/wbw/hafs.json`) — measured, and what it is used for

Abdullah's word-by-word Quran is built on a "quran-mushaf" release (format
1.0, generated 2026-09-01) of the **KFGQPC UthmanicHafs v3.0** text (release
year 2026), the text of the print this artwork reproduces. He asked for it to
be used (2026-09-04). This file records what was measured against our build
before adopting anything, and what was adopted.

## What the file holds

| layer | records | note |
|---|---:|---|
| `words` | 77,432 | `w` global id (the same number for this word in every mushaf that has it; gaps at 25685 and 73951), `t` the v3.0 text, `pg`, `ln`, `e` (imlaei skeleton, 77,356 of them), `marks` on 4,489 words (waqf / sajdah / hizb signs, with position) |
| `ayat` | 6,236 | word id range per ayah |
| `pages` | 604 | word id range per page, **read from the release's explicit page breaks** |
| `suras`, `juz` | 114, 30 | |
| `line_disagreements` | 105 | the release does not encode printed lines; `ln` is reconstructed and the file says where that reconstruction disagrees with the v2.0 CSV |

## Measured against our build (bundle of 2026-09-04)

| what | result |
|---|---|
| page membership | **identical on all 604 pages** — including the 25 pages where quran.com's layout is wrong (CLAUDE.md "Juz 30"), so this independently confirms the pipeline's page repair |
| segmentation | agrees on **6,235 of 6,236 ayahs**. The one difference: 15:7, where we emit لَّوْ / مَا as two groups (the print's spacing, `docs/MAQTU-MAWSUL.md`) and the release writes `لَّوۡمَا` as one word. Hence 77,433 groups against 77,432 ids |
| `t` vs our `qpc` form | equal on 45,757 raw, **66,757 after Unicode canonical ordering**. The rest are conventions, not content: the release keeps waqf signs in its `marks` layer (only 2 of 77,432 `t` values contain one); v3.0 writes open tanween as U+08F0–08F2 where the v2 text we carry writes U+0656/0657; hamza seats differ (`أٓ` vs `ـَٔا`) |
| `t` vs our `uthmani` | equal on 65,502 after ordering and the sukun map (U+06E1 → U+0652); remaining differences are the same three conventions |
| `e` vs our `search` | equal on **76,563 of 77,356**; of the 793 differences, 417 are the vocative (`ياأيها` vs our `يا أيها`) and ~374 the imlaei convention for سموات / سماوات — neither side is wrong, the conventions differ |
| `ln` vs our `data-line` | 76,998 of 77,430 agree; the release itself flags its lines as reconstructed. Our lines are validated against the print (100% by `audit_wordline.py`); theirs are not a line source |

## Adopted

**`data-w` on every word group, both profiles, and `w` in `index/by-page/NNN.json`
and `index/words.json`.** Derived, never hand-kept: `tools/build_wbw_map.py`
aligns each ayah — positionally when the counts agree, by letter-skeleton
merging where they do not — and writes `.cache/wbw/wid_to_w.json`; the emitter
refuses a word the map does not know. 77,433 wids map onto all 77,432 ids, the
two pieces of 15:7 sharing id 33536. Gated by `audit_export.py` (`wbw`) and
`verify_bundle.py` (every word has an integer `w`; distinct `w` count is
77,432).

## Not adopted, and why

- **`t` as the text of record.** It is the official v3.0 text and a candidate
  to replace the composite `data-uthmani` (quran.com uthmani + KFGQPC waqf +
  DigitalKhatt at iqlab sites), but it needs the same measured contest the
  earlier sources went through (`docs/defects/text_contest_eyes.json`), with its
  `marks` layer folded back in. Not done today.
- **`e` as the search key.** Conventions differ (vocative spacing, سموات); ours
  is documented and the library's loose pass already covers the dagger-alef
  cases. Swapping would change 793 keys for no measured gain.
- **`ln`.** Reconstructed by the release's own admission; ours are proven.
