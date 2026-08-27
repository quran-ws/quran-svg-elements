# DKSEG migration — the print's segmentation of بَعْدَ مَا is now canonical

**Summary.** The three بَعْدَ مَا compounds (2:181 p27, 8:6 p177, 13:37 p254) are
now keyed as TWO words each, exactly as the DigitalKhatt DB of this print and
MushafDatabase both segment them; every later position in those ayahs shifts +1.
The other two letter-space compounds stay ONE word because the DK DB fuses them
too: 37:130:3 إِلْ يَاسِينَ (p451; MushafDatabase splits it, DK wins per
Abdullah's decision) and 5:52:12 (p117), where quran.com's internal space
`دَآئِرَ ةٌۭ` is quran.com's own typo — DK writes `دَآئِرَةࣱۚ`, one word.
Gate: `QSVG_DKSEG` (default ON; `=0` reverts everything to quran.com's fused
keying). All gates pass; bench SCORE improved 79 → 78. The rebuild also
uncovered and fixed two latent line errors the old dk_lines.json carried in
2:181/8:6 (built without their merge mapping), and one place where the DK
layout DB itself disagrees with the ink (p254 مَا, pinned to line 7).

## Per-compound before → after keys

| page | ayah | fused (before) | split (after) | line(s) |
|---|---|---|---|---|
| 27 | 2:181 | `2:181:3` بَعْدَ مَا; 4–14 follow | `2:181:3` بَعْدَ, `2:181:4` مَا; 5–15 follow (+1) | both line 14 |
| 177 | 8:6 | `8:6:4` بَعْدَ مَا; 5–12 follow | `8:6:4` بَعْدَ, `8:6:5` مَا; 6–13 follow (+1) | both line 11 |
| 254 | 13:37 | `13:37:8` بَعْدَ مَا; 9–19 follow | `13:37:8` بَعْدَ, `13:37:9` مَا; 10–20 follow (+1) | بَعْدَ line 6, مَا line 7 |

All half texts come from splitting the cached quran.com/QPC fused texts on the
internal space (never hand-typed). Verified directly against
`.cache/digitalkhatt/digital-khatt-v2.db`: 13:37 → ids 34301 بَعْدَ / 34302 مَا
(positions 8/9), 2:181 → positions 3/4, 8:6 → positions 4/5.

## Code changes (all in this repo, uncommitted)

- **`tools/assign_words.py`**
  - `_DKSEG_SPLITS` + helpers (`_dkseg_on/_dkseg_fused/_dkseg_split_data/
    _dkseg_qpc/_dkseg_lines_convert/_dkseg_half_lw/_dkseg_widths`).
  - `page_words()` rewrites the quran.com payload to the print's segmentation
    on load; QPC text maps back through the fused key and splits its two
    tokens per half.
  - `_qcf_lines()` now knows dk_lines.json is DK-canonical and qcf_lines.json
    is fused, and converts whichever it loads to the keying QSVG_DKSEG
    selects (so `QSVG_DKLINES=0` and `QSVG_DKSEG=0` compose correctly).
  - `qcf_widths()` remaps the fused advance table once at load: later keys
    +1; each compound's advance splits between the halves in proportion to
    their calibrated letter widths (1.5524 → 0.9874/0.5650 for 13:37;
    1.846 → 1.1741/0.6719 for 2:181; 1.9132 → 1.2168/0.6964 for 8:6). Every
    width consumer reads through this one choke point.
  - `_space_halves` docstring updated: under DKSEG it fires only for
    p117/p451. No pass logic changed — the SPACESPLIT machinery, the
    hillclimb compound guard, and the audit rtl/compound skips all key on an
    internal space, which the migrated words no longer have, so they retire
    for these three pairs automatically and keep serving p117/p451.
- **`tools/build_dk_words.py`**
  - `SPLITS` covers all three ayahs (was 13:37 only — the words-dk cache had
    WRONG texts for every 2:181/8:6 word after the compound; pages 27/177/254
    regenerated).
  - New `--lines` mode: the previously script-less builder of
    `.cache/dk_lines.json`, emitting DK-canonical keys, medallions excluded.
    Contains one documented ink override: the DK layout DB (a typesetting
    model) ends p254 line 6 with مَا, but the print draws مَا first on line 7
    (reported.json item 20, Abdullah's eye; MushafDatabase agrees) — pinned
    `254/13:37:9 → 7`.

## Data changes

- **`.cache/dk_lines.json`** — rebuilt via `--lines` (backup of the old file in
  the session scratchpad). Diff vs old, fused view: exactly 4 keys, all inside
  2:181/8:6 — the old table had been built WITHOUT the merge mapping for those
  two ayahs, so it silently told the pipeline فَإِنَّمَآ (p27) is on line 14
  (print: 15) and وَهُمْ (p177) on line 11 (print: 12). Both now match
  MushafDatabase. Everything outside the three ayahs is unchanged.
- **`.cache/review/overrides.json`** (backup: `overrides.json.bak-dkseg`), p254 —
  3 entries remapped:
  - `322.4,231.2,333.5,247.5` (مَا body) `13:37:8 → 13:37:9`
  - `326.0,232.5,333.0,236.1` (مَا fatha) `13:37:8 → 13:37:9`
  - `314.1,248.5,316.5,250.8` (جَآءَكَ mark) `13:37:9 → 13:37:10`
  - بَعْدَ's five line-6 entries stay `13:37:8`; `28.4,200.9,45.2,217.4` stays
    `13:37:7`. Note: under `QSVG_DKSEG=0` these three entries are keyed for the
    wrong (split) scheme — the revert switch is for A/B only.
- **`docs/defects/visual_verdicts.json`** — 12 keys shifted (+1 past the split);
  migration note appended to the file's `note`.
- **`docs/defects/proposals.json`** — 0 keys needed shifting (only `13:37:7`
  appears); note appended.
- **`docs/defects/queue.json`** — 1 key shifted (`13:37:9 → 13:37:10`);
  regenerable via `make_queue`.
- **`.cache/review/kinds.json` / `marks.json`, `docs/defects/reference_confirmed.json`** —
  scanned, no entries in the affected ayahs.
- **`.cache/words-dk/page-{027,177,254}.json`** — regenerated with the fixed
  join (texts in 2:181/8:6 after the compound were shifted one word before).

## Gate numbers

| gate | result |
|---|---|
| bench | **SCORE 78** (was 79 — one aggregate metric improved), FAILURES none, pixelfail 0, budget-mismatch 5/1655, width bad 1/1655 |
| marks+intervals, p27/p117/p177/p254/p451 vs `.cache/sweeps/reseat` | 27: 0/0→0/0 · 117: 0/0→0/0 · 177: 0/0→0/0 · 254: 0/0→0/0 · 451: 1/0→1/0 (the pre-existing إِلْ يَاسِينَ ligature-surplus flag, untouched) — **no page worse** |
| 10 control pages (5, 50, 100, 150, 200, 300, 350, 400, 500, 600), HEAD build vs migrated build | **all byte-identical** |
| p254 emitted SVG | TWO groups: `data-word="8"` بَعْدَ (ligature بعد, body+fatha, inside the line-6 wrapper) and `data-word="9"` مَا (ligature ما, body+fatha, inside the line-7 wrapper); جَآءَكَ is `data-word="10"` |
| MushafDatabase, all 5 pages | line disagreements **0**; every position in 2:181/8:6/13:37 aligns 1:1 (incl. both halves); residual text diffs are orthography only (kashida, ى/ي) |

## For Abdullah

1. **p451 إِلْ يَاسِينَ**: MushafDatabase splits it in two; the DK DB fuses it.
   Kept fused per your decision (DK is source of truth) — say the word if the
   ink argues otherwise and it becomes a fourth split.
2. The old dk_lines.json line errors (فَإِنَّمَآ p27, وَهُمْ p177) were live
   until now and no audit flagged them; the pages stayed clean through the
   change, but a by-eye glance at p27 line 14/15 and p177 line 11/12 on the
   review server would close the loop (use **Rebuild this page** first — the
   server cache predates this change, as do the caches for p254).
3. `.cache/qcf_widths.json` has 13 keys for 2:181 (14 words) and 11 for 8:6
   (12 words) — the fused table was already missing each ayah's last word.
   Unchanged by this migration (missing keys fall back to the letter sum), just
   now documented.
4. Nothing committed; the dk_lines backup lives in the session scratchpad —
   `tools/build_dk_words.py --lines` reproduces the new file exactly.
