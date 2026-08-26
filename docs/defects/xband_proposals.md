# Cross-line steal family — QSVG_XBAND trial proposals

Generated 2026-08-26. TRIAL ONLY: the pass lives in `tools/assign_words.py` behind
`QSVG_XBAND` (**default OFF**). Nothing is committed and nothing runs unless the
switch is set. Every measurement below was taken with `QSVG_XBAND=1` explicitly.

## The mechanism

A word can hold a mark drawn in the ADJACENT line's band — stolen from the word
directly above or below. Proof-class position evidence (measured empty bands:
4,203 marks sit ≤10u outside their line band, 26 in 10–15u, nothing legitimate at
15u+; horizontally nothing sits 40–150u from its word) plus the receiving word's
text budget for the mark's family after position-aware renaming (`_POS_SWAP`:
a fatha descending to the word below arrives as its kasra candidate).

Three shapes of repair, all two-signal:
- **move** — receiver has a family deficit AND the donor a surplus (slash/damma
  moves additionally require the deficit/surplus per FAMILY, not just per group);
- **move as the receiver's letter ء** — the receiver spells a standalone ء it does
  not hold; the stolen "hamza" is that letter and is demoted on arrival (welded
  twins travel with it and re-master as marks);
- **exchange** — the full receiver itself holds a same-group mark ≥10u out of ITS
  band drawn over the donor: budget-neutral swap, both renamed in place.

## Measurements (QSVG_XBAND=1)

| gate | result |
|---|---|
| `scratchpad/bench.py` | no FAILURE, pixelfail 0, SCORE 79 — byte-identical to the pass being off |
| `audit_marks` over all 23 candidate pages | **45 flags → 35**, no page worse, zero new flag rows |
| `audit_intervals` same pages | **40 → 40** (unchanged) |
| repairs applied | **10** on 10 pages: 7 moved, 3 exchanged |

Abdullah's 13 mark-steal verdicts: **6 resolved** (p63, p64, p71, p222, p234,
p260 — the mark now sits with the owner his note names, renamed where position
demands). **7 refused with cause** (p129, p231, p267, p341, p350, p371, p535 —
each is a chain, a letter steal, or a word-level line error; details per row).
Three siblings not on his list were also repaired: p436 (pause, same صلى shape),
p439 (maddah exchange), p599 (kasra exchange, his HIGH cluster).

## Proposals

Conf = both-signals (applied) / position-only (proposed, NOT applied) / none
(below the 15u proof threshold; listed for completeness).

| pg | holder | word | mark | evidence | proposed owner | new name | budgets r:have/want d:have/want | conf | decision | Abdullah |
|---|---|---|---|---|---|---|---|---|---|---|
| 45 | 2:265:23 | فَطَلٌّۭ ۗ | pause | below proof threshold (10-15u zone) | —  | — | - | none | listed only: inside the 10-15u zone (26 such marks mushaf-wide); not eligible | — |
| 63 | 3:108:6 | بِٱلْحَقِّ ۗ | pause | band_out 40.9u | 3:107:7 ٱللَّهِ | pause | r:0/1 d:2/1 | both-signals | moved | stole صلى pause from the word above |
| 64 | 3:115:6 | يُكْفَرُوهُ ۗ | pause | band_out 37.4u | 3:114:12 ٱلْخَيْرَٰتِ | pause | r:0/1 d:2/1 | both-signals | moved | stole صلى from the word above |
| 71 | 3:161:6 | وَمَن | fatha | band_out 17.6u | 3:160:14 بَعْدِهِۦ ۗ | kasra | r:2/3 d:3/2 | both-signals | moved | extra fatha/kasra at top stolen from the word above |
| 90 | 4:78:20 | سَيِّئَةٌۭ | fatha | below proof threshold (10-15u zone) | —  | — | - | none | listed only: inside the 10-15u zone (26 such marks mushaf-wide); not eligible | — |
| 90 | 4:78:20 | سَيِّئَةٌۭ | fatha | below proof threshold (10-15u zone) | —  | — | - | none | listed only: inside the 10-15u zone (26 such marks mushaf-wide); not eligible | — |
| 93 | 4:94:25 | كَثِيرَةٌۭ ۚ | pause | below proof threshold (10-15u zone) | —  | — | - | none | listed only: inside the 10-15u zone (26 such marks mushaf-wide); not eligible | — |
| 108 | 5:8:15 | تَعْدِلُوا۟ ۚ | pause | below proof threshold (10-15u zone) | —  | — | - | none | listed only: inside the 10-15u zone (26 such marks mushaf-wide); not eligible | — |
| 129 | 6:17:12 | بِخَيْرٍۢ | meem-iqlab | band_out 25.5u | —  | — | - | position-only | refused: no word drawn under the mark | stole haa LETTER and a kasra below it from the word below (+extra fatha) |
| 129 | 6:17:12 | بِخَيْرٍۢ | kasratan | band_out 32.2u | 6:18:4 عِبَادِهِۦ ۚ | kasratan | r:4/4 d:5/3 | position-only | refused: receiver full | stole haa LETTER and a kasra below it from the word below (+extra fatha) |
| 140 | 6:101:11 | صَـٰحِبَةٌۭ ۖ | pause | below proof threshold (10-15u zone) | —  | — | - | none | listed only: inside the 10-15u zone (26 such marks mushaf-wide); not eligible | — |
| 149 | 6:157:17 | وَرَحْمَةٌۭ ۚ | pause | below proof threshold (10-15u zone) | —  | — | - | none | listed only: inside the 10-15u zone (26 such marks mushaf-wide); not eligible | — |
| 201 | 9:92:20 | أَلَّا | fatha | below proof threshold (10-15u zone) | —  | — | - | none | listed only: inside the 10-15u zone (26 such marks mushaf-wide); not eligible | — |
| 214 | 10:53:8 | لَحَقٌّۭ ۖ | pause | below proof threshold (10-15u zone) | —  | — | - | none | listed only: inside the 10-15u zone (26 such marks mushaf-wide); not eligible | — |
| 222 | 11:8:16 | عَنْهُمْ | fatha | below proof threshold (10-15u zone) | —  | — | - | none | listed only: inside the 10-15u zone (26 such marks mushaf-wide); not eligible | — |
| 222 | 11:12:15 | كَنزٌ | hamza | band_out 27.3u | 11:12:26 شَىْءٍۢ | letter-hamza | r:0/0 d:1/0 | both-signals | moved as the receiver's letter ء | stole hamza from the word below |
| 231 | 11:88:13 | حَسَنًۭا ۚ | meem-iqlab | band_out 21.8u | 11:88:2 يَـٰقَوْمِ | meem-iqlab | r:0/0 d:1/1 | position-only | refused: receiver full | stole meem from a word above |
| 234 | 11:116:25 | وَكَانُوا۟ | fatha | band_out 34.0u | 11:117:6 بِظُلْمٍۢ | kasra | r:1/2 d:3/2 | both-signals | moved | stole KASRA from the word below |
| 241 | 12:47:5 | دَأَبًۭا | fatha | below proof threshold (10-15u zone) | —  | — | - | none | listed only: inside the 10-15u zone (26 such marks mushaf-wide); not eligible | — |
| 260 | 14:39:5 | لِى | hamza | band_out 18.9u | 14:38:13 شَىْءٍۢ | letter-hamza | r:0/0 d:1/0 | both-signals | moved as the receiver's letter ء | stole hamza+kasratan from the word above |
| 267 | 16:2:11 | أَنْ | fatha | band_out 35.2u | 16:3:2 ٱلسَّمَـٰوَٰتِ | kasra | r:4/4 d:1/1 | position-only | refused: receiver full | stole kasra from the word below |
| 341 | 22:73:25 | مِنْهُ ۚ | small-waw | band_out 17.7u | 22:73:17 ٱجْتَمَعُوا۟ | small-waw | r:0/0 d:1/0 | position-only | refused: receiver full | stole (small) waw from the word above; reference-confirmed line error |
| 350 | 24:3:9 | لَا | fatha | band_out 26.1u | 24:3:8 وَٱلزَّانِيَةُ | fatha | r:4/4 d:1/1 | position-only | refused: receiver full | stole a far away fatha |
| 355 | 24:39:6 | يَحْسَبُهُ | fatha | below proof threshold (10-15u zone) | —  | — | - | none | listed only: inside the 10-15u zone (26 such marks mushaf-wide); not eligible | — |
| 371 | 26:97:4 | لَفِى | kasra | stray gap 303.4u | 26:97:5 ضَلَـٰلٍۢ | fatha | r:2/3 d:4/2 | position-only | refused: receiver full | stole kasras far away |
| 371 | 26:97:4 | لَفِى | kasra | band_out 30.3u | 26:97:5 ضَلَـٰلٍۢ | kasra | r:2/3 d:4/2 | position-only | refused: receiver full | stole kasras far away |
| 380 | 27:37:11 | أَذِلَّةًۭ | fatha | below proof threshold (10-15u zone) | —  | — | - | none | listed only: inside the 10-15u zone (26 such marks mushaf-wide); not eligible | — |
| 415 | 32:10:8 | خَلْقٍۢ | meem-iqlab | band_out 16.6u | 32:9:11 وَٱلْأَفْـِٔدَةَ ۚ | meem-iqlab | r:0/0 d:1/1 | position-only | refused: receiver full | — |
| 418 | 33:3:4 | وَكَفَىٰ | fatha | stray gap 289.8u | 33:3:3 ٱللَّهِ ۚ | kasra | r:2/2 d:5/3 | position-only | refused: receiver full | — |
| 418 | 33:3:4 | وَكَفَىٰ | fatha | band_out 29.4u | 33:3:3 ٱللَّهِ ۚ | kasra | r:2/2 d:5/3 | position-only | refused: receiver full | — |
| 436 | 35:13:20 | ٱلْمُلْكُ ۚ | pause | band_out 38.2u | 35:13:11 وَٱلْقَمَرَ | pause | r:0/1 d:2/1 | both-signals | moved | — |
| 437 | 35:29:7 | ٱلصَّلَوٰةَ | fatha | below proof threshold (10-15u zone) | —  | — | - | none | listed only: inside the 10-15u zone (26 such marks mushaf-wide); not eligible | — |
| 439 | 35:41:15 | بَعْدِهِۦٓ ۚ | maddah | below proof threshold (10-15u zone) | —  | — | - | none | listed only: inside the 10-15u zone (26 such marks mushaf-wide); not eligible | — |
| 439 | 35:42:6 | جَآءَهُمْ | maddah | band_out 24.5u | 35:41:15 بَعْدِهِۦٓ ۚ | maddah | r:1/1 d:1/1 | both-signals | exchanged | — |
| 443 | 36:52:6 | مَّرْقَدِنَا ۜ ۗ | pause | below proof threshold (10-15u zone) | —  | — | - | none | listed only: inside the 10-15u zone (26 such marks mushaf-wide); not eligible | — |
| 446 | 37:5:3 | وَٱلْأَرْضِ | fatha | band_out 16.8u | 37:2:1 فَٱلزَّٰجِرَٰتِ | kasra | r:4/5 d:3/3 | position-only | refused: donor would go below budget | — |
| 507 | 47:4:4 | كَفَرُوا۟ | fatha | band_out 19.8u | 47:4:16 فِدَآءً | fatha | r:3/3 d:2/2 | position-only | refused: receiver full | — |
| 507 | 47:4:34 | سَبِيلِ | damma | band_out 22.9u | 47:4:23 يَشَآءُ | damma | r:1/1 d:1/0 | position-only | refused: receiver full | — |
| 507 | 47:8:3 | فَتَعْسًۭا | damma | band_out 16.7u | 47:7:3 ءَامَنُوٓا۟ | damma | r:1/1 d:1/0 | position-only | refused: receiver full | — |
| 524 | 52:21:16 | ٱمْرِئٍۭ | meem-iqlab | below proof threshold (10-15u zone) | —  | — | - | none | listed only: inside the 10-15u zone (26 such marks mushaf-wide); not eligible | — |
| 525 | 52:38:7 | مُسْتَمِعُهُم | pause | below proof threshold (10-15u zone) | —  | — | - | none | listed only: inside the 10-15u zone (26 such marks mushaf-wide); not eligible | — |
| 535 | 56:33:3 | وَلَا | fatha | band_out 17.2u | 56:33:2 مَقْطُوعَةٍۢ | kasra | r:3/3 d:4/2 | position-only | refused: receiver full | — |
| 535 | 56:33:3 | وَلَا | fatha | stray gap 302.0u | 56:33:2 مَقْطُوعَةٍۢ | kasra | r:3/3 d:4/2 | position-only | refused: receiver full | — |
| 535 | 56:35:2 | أَنشَأْنَـٰهُنَّ | fatha | below proof threshold (10-15u zone) | —  | — | - | none | listed only: inside the 10-15u zone (26 such marks mushaf-wide); not eligible | — |
| 564 | 68:12:4 | أَثِيمٍ | fatha | below proof threshold (10-15u zone) | —  | — | - | none | listed only: inside the 10-15u zone (26 such marks mushaf-wide); not eligible | — |
| 567 | 69:9:5 | وَٱلْمُؤْتَفِكَـٰتُ | kasra | band_out 15.5u | 69:10:5 أَخْذَةًۭ | fatha | r:3/3 d:4/4 | position-only | refused: receiver full | — |
| 576 | 74:31:13 | كَفَرُوا۟ | fatha | below proof threshold (10-15u zone) | —  | — | - | none | listed only: inside the 10-15u zone (26 such marks mushaf-wide); not eligible | — |
| 576 | 74:31:22 | وَلَا | fatha | band_out 34.5u | 74:31:13 كَفَرُوا۟ | fatha | r:2/2 d:2/2 | position-only | refused: receiver full | — |
| 576 | 74:31:38 | مَثَلًۭا ۚ | fatha | below proof threshold (10-15u zone) | —  | — | - | none | listed only: inside the 10-15u zone (26 such marks mushaf-wide); not eligible | — |
| 576 | 74:31:48 | يَعْلَمُ | fatha | below proof threshold (10-15u zone) | —  | — | - | none | listed only: inside the 10-15u zone (26 such marks mushaf-wide); not eligible | — |
| 576 | 74:31:51 | إِلَّا | fatha | band_out 35.5u | 74:31:39 كَذَٰلِكَ | fatha | r:4/4 d:2/2 | position-only | refused: receiver full | — |
| 577 | 74:53:4 | يَخَافُونَ | fatha | below proof threshold (10-15u zone) | —  | — | - | none | listed only: inside the 10-15u zone (26 such marks mushaf-wide); not eligible | — |
| 577 | 74:56:3 | إِلَّآ | fatha | band_out 26.1u | 74:53:4 يَخَافُونَ | fatha | r:3/3 d:2/2 | position-only | refused: receiver full | — |
| 599 | 98:6:2 | ٱلَّذِينَ | kasra | band_out 15.7u | 98:6:11 خَـٰلِدِينَ | fatha | r:4/4 d:3/3 | both-signals | exchanged | — |
| 599 | 98:6:11 | خَـٰلِدِينَ | fatha | below proof threshold (10-15u zone) | —  | — | - | none | listed only: inside the 10-15u zone (26 such marks mushaf-wide); not eligible | — |
| 599 | 98:7:3 | ءَامَنُوا۟ | fatha | below proof threshold (10-15u zone) | —  | — | - | none | listed only: inside the 10-15u zone (26 such marks mushaf-wide); not eligible | — |
| 59 | 3:75:19 | مَا | (whole word body) | bodyless word; يُؤَدِّهِۦٓ 3:75:8 holds 4 pieces where th... | 3:75:19 مَا | letter body | - | both-signals (diagnosed, not wired) | NOT applied: letter-piece move, out of scope for QSVG_XBAND (constraint 7); route through the segment-budget mechanism (assign_words.py:5108) — donor piece surplus == receiver deficit, position proof in hand | word swallow: يُؤَدِّهِۦٓ 3:75:8 stole the ما |
| 535 | 56:44:2 | بَارِدٍۢ | (word لَّا + diacritics) | بَارِدٍۢ holds 4 pieces where the joining rules allow 3; ... | 56:44:1 لَّا | letter body | - | diagnosed, not wired | NOT applied: this is a word-level line-boundary error (like p341 لَهُۥ): the line cut put لَّا on the previous line. Needs the word re-lined (or a geometry override), not a mark move | word swallow: stole the word before it with its diacritics لا |

## Refusal notes (the 7 unresolved verdicts)

- **p129 بِخَيْرٍۢ**: the "meem-iqlab"+"kasratan" 26–32u below its band sit at
  عِبَادِهِۦ's final هِ (x178–184; عبادِهِۦ starts x186 — 2.2u past the overlap
  gate). Abdullah reads them as عبادِهِۦ's ه LETTER + kasra, but عبادِهِۦ counts
  kasra 3/3 — one of the three it holds must itself be wrong. Letter steal +
  chain: adjudicate; letter-piece moves are out of scope (constraint 7).
- **p231 حَسَنًۭا ۚ**: no word on the line above spells ۢ/ۭ; the word directly
  above under the ink is يَـٰقَوْمِ, which ENDS IN م (2 pieces allowed). The
  "meem-iqlab" is its final م letter — letter steal, segment-budget mechanism.
- **p267 أَنْ**: receiver ٱلسَّمَـٰوَٰتِ is family-full (kasra 1/1 within slash
  4/4) and donor أَنْ holds ONLY the stray as its fatha — a chain (أَنْ's real
  fatha is elsewhere). Moving would break the donor below budget.
- **p341 مِنْهُ ۚ**: no word on line 2 spells ۥ. The true owner لَهُۥ is itself
  on the wrong line (reference-confirmed, docs/defects/reference_confirmed.json).
  The WORD needs re-lining; a mark move cannot express the repair.
- **p350 لَا**: the worked example. Receiver وَٱلزَّانِيَةُ is fatha-full; the
  x14.9 stroke is wanted by NO word's budget (likely not a fatha at all — possibly
  ة letter ink). Correct refusal; the chain repair (لَا's true fatha back from
  يَنكِحُهَآ) has no position proof on that side and needs its own mechanism.
- **p371 لَفِى**: receiver ضَلَـٰلٍۢ is missing its KASRATAN, but the nearer stray
  sits fatha-side of its letters — a single move would install a surplus fatha
  (the per-family veto caught exactly this; group counts alone had accepted it).
  The two strays are 19u apart so they are not a tanween pair. Adjudicate.
- **p535 وَلَا (56:33:3) / بَارِدٍۢ (56:44:2)**: the two strays ARE a kasratan
  pair (4.5u apart) under مَقْطُوعَةٍۢ's ة — but مقطوعةٍۢ already counts
  kasratan 1/1 via a suspicious element at (20,233) (every other ٍ on that line
  sits at y≈248–253), and holds a fatha at (10,221) that is itself out of band.
  Chain of three; adjudicate. 56:44:2 is a word-level line error: بَارِدٍۢ holds
  4/3 pieces, the extra standing where لَّا is printed at its line's start, while
  لَّا is credited with ink at the end of the PREVIOUS line. Re-line the word.

## Knobs and provenance

- Pass: `tools/assign_words.py`, late in `assign_page` (after `QSVG_IQLATE`,
  before `QSVG_IQFIX`), behind `QSVG_XBAND` (default "0").
- `QSVG_XBDBG=1` prints every candidate+decision; `QSVG_XBOUT=<file>` appends
  one JSON line per candidate (this report was built from it).
- All moves go through `put_in_ligature()`; moved ink is re-tagged to the
  receiver's line (without this, p222 grew a phantom rtl-order flag).
- The exchange's give-back overlap is strict (−2u). Relaxing to −6u admits a
  p577 إِلَّآ/يَخَافُونَ swap but the returned fatha lands in يَذْكُرُونَ's
  exclusive core (+1 interval flag) — a three-way chain; left refused.
