# Waqf + dammah recoveries — round-7 verdicts and R11 blobs, applied

Repairs for Abdullah's round-7 waqf family (11 confirmed verdicts), the three
R11 dammah blobs, and a re-audit of the rounds-5/6 single-surplus words.
Detection was already done (two signals each, `docs/defects/marktype_rules.md`
R10/R11); this file records the repair per case, the mechanism, and the gates.

Baseline for every comparison: `.cache/sweeps/lsolve`.

## Mechanisms (in preference order used)

1. **`.cache/review/overrides.json`** — geometry-keyed move to the owning word
   (existing mechanism, pure data). Used wherever the drawn sign was held by a
   neighbour.
2. **`.cache/review/kinds.json`, extended** — the table already recorded
   "mark that is really a letter" (`"body"`). The consumer in
   `tools/assign_words.py` now also accepts a mark name as the value: ink read
   as a LETTER that a human confirmed is a mark becomes `kind="mark"` with
   that name. Env-gated `QSVG_KINDMK` (default on; the pass does nothing
   without data entries). Every entry added is backed by two signals: the
   word's text budget is short exactly that family, and the blob was located
   by eye — for the waqf signs additionally by signature
   (`f5581079d942b4ee` = the drawn ۖ, 1633 occurrences, purity 1.0 in
   `.cache/marks/waqf_types.json`).
3. **muʿānaqah second weld** — `waqf_places.json` entries were already
   complete; the defect was ordering: the weld ran before the movers, and a
   mover delivered a straggler triangle dot to the owning word afterwards
   (p114 counted waqf 2/1). A re-normalize of recorded occurrences now runs
   after the movers, env-gated `QSVG_WPL2` (default on). Nothing moves between
   words there.
4. **Count-pair trigger for the line-set solver** — `QSVG_LSCNT`, default
   **OFF** (category C, see below).

Controls: pages 1 and 3 byte-identical with the new code on and off, with and
without `QSVG_LSCNT`.

## A. Waqf (11 round-7 verdicts) — all fixed

| page | word | was | ink found | repair |
|---|---|---|---|---|
| 49 | وَأَطَعْنَاۖ | waqf 0/1 | ۖ in-word at 244.3,330.7 (8.8x6.9), kind=body, sig `f5581079d942b4ee` = waqf sali | kinds → waqf |
| 42 | خَلْفَهُمْۖ | waqf 0/1 | ۖ held by ٱلَّذِى (2:255:22, line 10) at 190.4,365.3 | override → 2:255:32 + kinds → waqf |
| 91 | تَقُولُۖ | waqf 0/1 | ۖ held by طَاعَةٌۭ (4:81:2, line 2) at 136.0,74.6 | override → 4:81:12 + kinds → waqf |
| 112 | ٱلْقَوْمِ | waqf 1/0 | the ۛ triangle of سَنَةًۛ, welded in the wrong word | override master 13.9,113.2 → 5:26:6 (carries both welded parts) |
| 112 | سَنَةًۛ | waqf 0/1 | same triangle | same move |
| 114 | قُلُوبُهُمْۛ | waqf 2/1 | own triangle split: master+part welded, third dot delivered by a later mover, counted separately | second weld (`QSVG_WPL2`) re-groups occ 1 into one master |
| 171 | وَٱلسَّلْوَىٰۖ | waqf 0/1 | ۖ held by وَظَلَّلْنَا (7:160:26, line 4) at 239.9,151.9 | override → 7:160:32 + kinds → waqf |
| 399 | لُوطٌۘ | waqf 0/1 | the ۘ held by وَمَأْوَىٰكُمُ (29:25:22) at 43.7,185.9, sig `201e3ba1e499b4f2` = waqf lazim | override → 29:26:3 + kinds → waqf |
| 503 | وَبَيْنَكُمْۖ | waqf 0/1 | ۖ held by ٱللَّهِ (46:8:11) at 292.0,145.9 | override → 46:8:22 + kinds → waqf |
| 504 | عَمِلُوا۟ۖ | waqf 0/1 | ۖ held by وَٱلْإِنسِ (46:18:14) at 136.8,399.0 | override → 46:19:4 + kinds → waqf |
| 525 | ٱلْمُصَۜيْطِرُونَ | waqf 0/1 | the ۜ held by مُسْتَمِعُهُم (52:38:7) as surplus waqf at 164.1,177.6, drawn inside line 5's band | override → 52:37:7 (already mark=waqf) |
| 525 | مُسْتَمِعُهُم | waqf 1/0 | same element | same move |

A caution learned locating these: the R10 flags' "drawn-sign candidate"
letter-boxes of 9.9x10.8 (p171 287.7,170.6; p503 320.5,169.4; p49
276.7,350.0) are the word's own final/initial **و** glyph
(sig `17355d85438becb0`), not the sign — the real ۖ was one word (usually one
line) away in every welded case. The signature separated them.

Not touched: p159 7:69:22 بَصْۜطَةًۭۖ (shaddah 1/0, waqf 1/2) — an R10 flag
but not among the round-7 verdicts; the ۜ there is genuinely welded and needs
its own adjudication.

## B. Dammah (3 R11 candidates) — all fixed, none had resolved on its own

| page | word | was | blob | repair |
|---|---|---|---|---|
| 39 | وَقُومُوا۟ | dammah 1/2 | 52.6,10.0 (5.3x6.6), kind=body, in-word, in the mark zone | kinds → dammah |
| 159 | وَءَابَآؤُكُم | dammah 1/2 | 67.9,277.5 (5.3x6.1), kind=body, in-word | kinds → dammah |
| 544 | يَـٰٓأَيُّهَا | dammah 0/1 | 311.6,11.8 (5.1x6.9), kind=body, in-word | kinds → dammah |

Each blob is exactly dammah-sized (the drawn dammah is 5.3x6.7 mushaf-wide) with
a one-off outline signature — which is why the classifier missed it (dammah is
excluded from auto shape labels; its curl matches a hamzah outline).

## C. Rounds-5/6 single-surplus words — status against the current build

Seven of the nineteen resolved by widening the solver's trigger
(`QSVG_LSCNT=1`): a budget-violating word whose movable surplus mark overlaps
a neighbour that is itself budget-violating now triggers a line-set solve; the
solve itself is unchanged (receiver-room guarded, applied only on a strict
unique improvement). Default **OFF** pending adoption.

| page | word (evidence) | status @ default | @ LSCNT=1 | diagnosis |
|---|---|---|---|---|
| 44 | 2:262:15 لَّهُمْ fathah 2/1 | flagged (+2:262:16 0/1) | **fixed, pair closed** | surplus stroke over the neighbour with the matching deficit |
| 51 | 3:14:18 مَتَـٰعُ fathah 3/2 | flagged (+3:15:2 1/2) | **fixed, pair closed** | same |
| 129 | 6:13:3 سَكَنَ fathah 4/3 | flagged (+6:14:4 1/2) | **fixed, pair closed** | same |
| 323 | 21:16:4 وَٱلْأَرْضَ fathah 4/3 | flagged (+21:17:6 3/4) | **fixed, pair closed** | same |
| 361 | 25:18:15 وَءَابَآءَهُمْ fathah 5/4 | flagged (+25:19:2 1/2) | **fixed, pair closed** | same |
| 486 | 42:23:12 أَسْـَٔلُكُمْ fathah 3/2 | flagged (+42:23:22 0/1) | **fixed, pair closed** | same |
| 543 | 58:7:1 أَلَمْ fathah 3/2 | flagged (+58:7:15 1/2) | **fixed, pair closed** | same |
| 272 | 16:48:10 ظِلَـٰلُهُۥ fathah 2/1 | **already fixed** | — | resolved by earlier work |
| 228 | 11:56:6 وَرَبِّكُمۚ fathah 3/2 | **already fixed** (page clean) | — | resolved by earlier work |
| 535 | 56:44:4 كَرِيمٍ fathah 2/1 | **already fixed** | — | page still holds tanwin_al_kasr 2/1 x2, tanwin_al_fath 1/0 — tanwin-weld artefacts, different defect |
| 526 | 53:26:5 ٱلسَّمَـٰوَٰتِ kasrah 2/1 | **already fixed** | — | 53:26:4 fathah 1/0 remains: likely the same stroke renamed; needs eyes |
| 576 | 74:31:48 يَعْلَمُ fathah 3/2 | **already fixed** | — | 74:31:38 kasrah 1/0 remains: surplus with no adjacent deficit, no two-signal route |
| 100 | 4:137:16 لِيَغْفِرَ fathah 3/2 | still flagged (+4:138:6 0/1) | solver examined, kept (V 2→2) | the deficit word's ink is NOT under the surplus stroke — no lawful move; needs eyes |
| 319 | 20:103:2 بَيْنَهُمْ fathah 3/2 | still flagged (+20:104:8 1/2) | no trigger | surplus stroke overlaps no budget-violating neighbour — the pair is not geometric neighbours |
| 355 | 24:39:6 يَحْسَبُهُ fathah 3/2 | still flagged (+24:38:14 0/1) | no trigger | same as p319 |
| 90 | 4:78:20 سَيِّئَةٌۢ fathah 4/2 | still flagged | no trigger | DOUBLE surplus; nearest deficits are tanwin_al_kasr 4:78:8 and the كُلٌّۭ dammah 4:78:26 (R11 family) — no matching-family neighbour |
| 222 | 11:8:16 عَنْهُمْ fathah 2/1 | still flagged | no trigger | no deficit word anywhere adjacent — surplus with no receiver; needs eyes |
| 499 | 45:8:10 لَّمْ fathah 2/1 | still flagged (+45:7:3 fathah 3/2, tanwin_al_kasr 0/1) | no trigger | two surpluses, the only deficit is INSIDE 45:7:3 itself (a fathah that is half an unwelded tanwin_al_kasr) — a naming/weld defect, not a transfer |
| 585 | 80:12:3 ذَكَرَهُۥ dammah 2/1 | still flagged | no trigger | page-wide: 4x dammah 2/1 + 2x dammah 1/0, ALL surpluses, no deficit anywhere — systematic dammah over-count on this page, not transfers |
| 543 | 58:7:38 kasrah 0/1 | still flagged | out of scope | the بِمَا (58:7:39) reference-confirmed LINE-error cluster; the solver already moved a kasrah 58:7:38 → 58:7:39 in that territory (`lsolve_proposals.json`, applied_for_reference) |

Where the solver stands on the still-flagged words: p222, p526, p535 and p576
appear in `lsolve_proposals.json` as `kept: no improvement` — examined, no
lawful move exists. p90, p100, p319, p355, p499 and p585 have no record at
all (p100 gains one under `QSVG_LSCNT=1`: examined, kept, V 2→2). Every
"needs eyes" row above is a genuine adjudication case, not a solver miss.

## Recommendation

Recommend adopting `QSVG_LSCNT=1`, with one review item first. The full
sweep (`.cache/sweeps/lscnt`, this build + `QSVG_LSCNT=1`) against
`.cache/sweeps/lsolve`:

- **total flags 316 → 273 (−43); 27 pages improved, 0 pages worse.**
- −16 of that is the A/B data fixes (on by default, already adopted above).
- The trigger closed the seven confirmed C pairs (p44, p51, p129, p323,
  p361, p486, p543) and, mushaf-wide, six more unreviewed pairs of the same
  shape: p239 12:35:7, p270 16:27:15/16:28:2, p277 16:90:16/16:91:8,
  p296 18:26:12/23, p403 29:60:11/29:61:7 — clean surplus/deficit closures.
- **Caveat — p254 (13:37, the بَعْدَ مَا cluster):** 7 flags → 3, but this is
  known BODY-STEAL territory (round-5 certain: ligature surplus, missing حا
  shape) and the flags changed shape rather than simply vanishing
  (13:37:8 fathah 4/3 → 2/3, 13:37:9 gained ligatures 4/3). A count
  improvement in a body-steal zone can hide a visible break; p254 and the
  five unreviewed pairs above should get eyes before the default flips.

## Gates

- bench: SCORE 79, FAILURES none, pixelfail 0 — identical with and without
  `QSVG_LSCNT=1` (gate: <=79 / none / 0).
- controls p1/p3: byte-identical across all switches.
- `tools/audit_intervals.py` on every touched page (2, 39, 42, 49, 91, 112,
  114, 159, 171, 399, 503, 504, 525, 544): 0 flags, matching baseline 0.
- audit_marks on the A/B pages: 16 baseline flags → 0, nothing new; p2
  (touched by the second weld) unchanged.
- full sweep `QSVG_LSCNT=1`: 316 → 273, no page worse (see above).

Data backups: `.cache/review/kinds.json.bak-pause`,
`.cache/review/overrides.json.bak-pause`,
`.cache/marks/waqf_places.json.bak-pause`.
