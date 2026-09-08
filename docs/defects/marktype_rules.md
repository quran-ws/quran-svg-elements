# Mark-type rules — measured, challenged, adopted or rejected

Companion to `tools/audit_marktype.py` (2026-08-26). Every threshold here was
derived from a mushaf-wide distribution measured FIRST on the CLEAN subset —
words with no flag in `.cache/sweeps/xband` and no confirmed visual verdict —
then challenged for legitimate exceptions before adoption. Flags:
`docs/defects/marktype_flags.json` (1,093 on the current build). Trial
corrector: `QSVG_MTYPE` in `tools/assign_words.py`, DEFAULT OFF.

Vertical measures, per mark master (never a `mkpart` twin, never standalone):

- `sbelow` = mark centre-y minus its word's body-band BOTTOM (+ve: below it)
- `sabove` = word's body-band TOP minus mark centre-y (+ve: above it, i.e.
  above even the ascenders)

Words on a line whose body band exceeds 1.6x the page-median band height
(headers, basmalah, ornate spread) are measured but never flagged.

## Clean-subset distributions (all 604 pages, n = masters)

`sbelow` histograms; every family's rule cites its row.

| family | n | <=0 | 0-1 | 1-2 | 2-3 | 3-4 | 4-8 | 8+ |
|---|---|---|---|---|---|---|---|---|
| fathah | 118,379 | 118,343 | 3 | 3 | 11 | 0 | 15 | 4 |
| tanwin_al_fath | 3,590 | all | | | | | | |
| kasrah | 44,437 | 21,510 | 4,392 | 6,486 | 9,352 | 3,455 | 4,138 | 9 |
| tanwin_al_kasr | 2,467 | 1,243 | 213 | 528 | 484 | 71 | 143 | 0 |
| dammah | 36,171 | all (max −2.8) | | | | | | |
| tanwin_al_damm / shaddah / sukun / maddah / hamzat_al_wasl / omitted_alif / small_circle / tanwin_al_fath / three_dots | — | ALL <= −4 | | | | | | |
| waqf | 4,216 | 4,215 | | | 1 (۪ exempt) | | | |
| small_meem | 1,462 | 1,354 | | | | | 60 | 48 |
| dot | 62,458 | 55,102 | 982 | 1,837 | 1,981 | 130 | 2 | 0 |
| two_dots | 36,322 | 31,338 | 1,633 | 1,112 | 1,817 | 420 | 2 | 0 |

`sabove`: kasrah — everything <= −4 except 3 in 0-1 and 1 at 2.3;
tanwin_al_kasr — EMPTY from −4 to +1, then 8 (all one defect pattern, below);
kasrah-family marks otherwise never approach the ascender top.

## Adopted rules

### R1 `fathah-below` (name-swap) — fathah/tanwin_al_fath centre > 2.0u below the band bottom
The 0-2u stragglers are a final letter's fathah grazing the band bottom
(لَهُمْ p100 +0.3, رَيْبَ p501 +0.3 — verified legitimate). Every sampled case
at 2u+ was a defect: the لأيات pattern strokes at ~2.5 (see R2) and stolen
strays (ٱلصَّلَوٰةَ p437 holds a fathah +14.6u below — it is تِجَـٰرَةًۭ's,
which audits fathah 1/2 on the same page; إِلَّا p576 holds one 54u ABOVE from
the line above while its own is gone). 40 flags.
*Challenged with:* kasrah's own distribution (hangs below to 8u — that is why
the rule reads the fathah families only); short low words; p129/p272/p535
dirty words distinguish steal-victims from swaps.

### R2 `kasrah-above` / `tanwin-al-kasr-above` (name-swap) — kasrah > 2.0u, tanwin_al_kasr > 0.0u above the band TOP
A kasrah tucked under a shaddah still sits far below the ascender top (KFQC
convention, `compose_tanwin` handles the shaddah case). tanwin_al_kasr's clean band
is empty from −4 to +1: the threshold 0.0 sits inside it, not at its edge.
The 10 clean hits are ONE pattern — **the لأيات name-crossing**: in
لَـَٔايَـٰتٍۢ (10 occurrences) the word's two stacked fathahs over لـَٔ are
welded as a "tanwin_al_kasr pair" at the TOP of the word, while its true tanwin_al_kasr —
QPC open tanwin ٖ, drawn as two strokes BELOW the word — is named
fathah+fathah. Counts balance perfectly (that is why every count audit called
these words clean); only position exposes it. 18 flags (R2 total).
*Challenged with:* shaddah-tucked kasrahs; stacked compositions (local ink vs
band edges — see rejected R-local); p508 غَيْرِ (+2.3, kept: matches the
stolen-slash pattern and sits beside a slash-move regression page).

### R3 `above-only-below` (invariant) — dammah, tanwin_al_damm, waqf, sukun, shaddah, small_circle, small_waw, omitted_alif, maddah, hamzat_al_wasl > 2.0u below the band
Clean corpus: NOTHING above −4 for any of these except one waqf. Live flags
today: ~0 — it is an invariant guard for future movers.
*Exceptions found while challenging:*
- **waqf**: the low stops ۪ ۣ are drawn below by the text's own instruction
  (مَجْر۪ىٰهَا p226, +2.9) — words whose text carries one are exempt.
- **small_meem** is EXCLUDED from the rule entirely: the low ۭ form
  legitimately hangs 4-11.5u below (19 clean words measured), and
  QSVG_IQFIX/IQLATE already police the high form with the text signal.

### R4 `half-pair` (pair-grouping) — a stroke-tanwin master with no twin where the print draws a pair
tanwin_al_fath/tanwin_al_kasr are drawn as TWO strokes (tanwin_al_damm alone has a one-outline
glyph and is exempt; `fused` compounds count as paired). Judged only when
masters == text budget exactly, so count errors stay with audit_marks.
**The single-stroke exception comes from the QPC encoding, not rasm_uthmani**
(below). 29 flags; sampled cases show the twin adjacent under another name
(جَزَآءًۭ p582: the twin sits 7u away named "fathah") or lost to a neighbour
(زَانِيَةً p350 line 6, the known rotation cluster).

### R5 `pair-spacing` (invariant) — welded tanwin strokes > 8u apart on either axis
Clean welded pairs: dx <= 6 for all but 10 tanwin_al_kasr at 6-8 — the open tanwin
ٖ drawn as a DIAGONAL pair (مُتَكَبِّرٍۢ p470 dx 7.4, شَجَرٍۢ p536 dx 7.5,
verified legitimate); dy <= 6 everywhere; nothing beyond 8 (the weld windows
cap at 8/7). Zero live flags — kept as a guard on future weld code.

### R6 `unwelded-tanwin` (pair-grouping) — text wants a tanwin, word holds none, but holds a surplus plain pair inside the weld windows
The residue of the weld passes (`:3608`, `:3653`, `compose_tanwin`). Zero
live flags on the current build — the welds catch everything reachable; kept
because it is the direct test of Abdullah's "two kasrahs that are really one
tanwin_al_kasr" case.

### R7 `meem-not-in-print` (name-swap) — a small_meem element in a word whose QPC text draws no meem — **926 flags, the largest family found**
rasm_uthmani writes tanwin + small meem (U+06E2/06ED) at EVERY non-izhar tanwin
— idgham and ikhfa included — while the print draws the م only at IQLAB.
QPC encodes the difference: iqlab = plain harakah + meem char; the others =
open signs ٖ/ٗ/ٞ with NO meem char, drawn as a stroke pair. Verified in the
ink: لأيات (10 words) draws the pair below with no meem glyph anywhere;
p275/p85/p536 show the stacked pair. Shape statistics second the text: the
571 QPC-confirmed meems are one uniform glyph (w 3.2-3.3, h 9.5) while the
926 QPC-meemless "meems" measure w 4.5-11.0 (median 8.6) — stroke ink or a
welded pair outline, not a م. The family is invisible to every count audit
because small_meem is deliberately never demanded (`audit_marks.py:33`).
Root cause: `_IQTAN` (:4929) and the late rescue key on the RASM_UTHMANI meem.
*Challenged with:* QPC reliability (the one property QPC encodes about this
print's drawing convention, per `iqlab_notation.md`; the geometry split above
is the independent second signal). One flag lands on a no-issue verdict
word (p350 مُشْرِكٌۭ) — that verdict judged its WIDTH (0.45x), not this
naming; noted, not treated as a counter-example.

### R8 `dot-content` — a dot-family label whose measured blob count (width / 2.38u, members included) disagrees with it
OVER direction (blob wider than the label): ZERO in the whole mushaf.
UNDER direction with the budget confirming: 0; without budget confirmation:
4 weak flags for eyes. The reviewer's note that sig 9514d038… covers both
2- and 3-dot drawings is real but almost always compensated by the members'
widths: my first single-width measurement "found" 33 defects that vanished
when members were counted — the bbox-lies confounder caught in the act
(recorded under threats below).

### R9 `outband` (ownership-suspect) — mark centre > 10u outside its own line's band
Deliberate overlap with `audit_crossband`/QSVG_XBAND, never a new verdict:
XBAND repairs >= 15u where budgets agree, so a survivor here is exactly the
residue whose budget gate said no, plus the 10-15u zone (26 mushaf-wide).
45 flags, including the four reference-confirmed line errors' territory.

### R10 `waqf-vs-ink` — waqf budget (RANGE across the two editions, as audit_marks treats it) vs held waqf marks, with the drawn sign located
17 flags; fires on **all 11 round-7 verdicts**. Deficits list in-word
candidates (unnamed marks, letter-classified boxes 3-13u square); where no
candidate exists the sign is welded into a neighbour or that word's letter
ink (p525: the neighbour مُسْتَمِعُهُم holds a surplus waqf — the missing
small-seen of ٱلْمُصَۜيْطِرُونَ). QSVG_RARESTOP covers only the round stops
۪ ۫ ۬ ۣ and only when mislabeled "dot" and oversized — the seen-shaped ۜ and
the ۘ stop have no path into a `waqf` label unless their outline is in
labels.json (p525/p399 both MISSED by it; see report).

### R11 `dammah-deficit` — dammah-family budget deficit, with dammah-sized recovery candidates located
Dammah is excluded from auto shape labels (its curl matches a hamzah outline),
so unlabeled dammah-shaped blobs are EXPECTED; only the deficit+blob two-signal
combination flags. 14 flags mushaf-wide; 3 carry an in-word candidate box
(وَقُومُوا۟ p39, وَءَابَآؤُكُم p159, يَـٰٓأَيُّهَا p544), 8 are the كُلٌّۭ
family — a tanwin-al-damm-iqlab whose QPC-aware budget needs the same treatment R7
gives tanwin_al_kasr (single dammah + م drawn), the rest sit in known clusters
(لَهُۥ p341).

## Rejected rules

- **Slash side vs LOCAL ink midpoint** (fathah must be above the letter ink at
  its x, kasrah below). The pipeline derives these names from exactly that
  test using contour polylines (`local_pos` :1562); re-deriving it from
  bounding boxes disagrees wherever a wide ligature body's box carries an
  ascender top over a flat letter — thousands of false sides. Box-based local
  midpoints are unusable; only word-band EDGES are safe, where the box error
  is conservative. (This is why R1/R2 use band edges.)
- **Fathah far ABOVE the band** — legitimate everywhere (شَجَرٍۢ p536 +7.4:
  a short word's fathahs ride high). No empty band exists.
- **Waqf high tail** — waqf rides to +19u above legitimately (sits over the
  line); no rule possible on position alone.
- **Narrow dot masters by master-width only** — 33 candidates, all but 4
  compensated by welded members' widths (مِثْلَ p143: master 2.4 + member 4.5
  = 3 blobs, label three_dots, correct). Adopted only with members counted
  (R8).
- **small_meem below the band** — the ۭ low form hangs legitimately;
  text-driven passes already police it.
- **Intra-pair spacing tighter than 8u** — the diagonal open-tanwin pairs
  at 6-8u are genuine; threshold would sit inside a populated zone.

## Threats to validity, and what was done about each

1. **Circularity** — distributions measured on the assignment being audited.
   Mitigation: baselines from the clean subset only (xband sweep + confirmed
   verdicts as the dirty filter); clean-vs-dirty compared per family — where
   they differ (fathah sbelow tail, tanwin_al_kasr sabove) the difference IS the
   defect signal and sampling confirmed defects, not noise. Residual risk:
   the clean subset still contains count-invisible defects — that is
   precisely what R2/R7 found (10 clean لأيات words, 926 clean R7 words), so
   "clean outliers" were individually inspected, never auto-trusted.
2. **Bounding boxes lie.** Demonstrated concretely twice: the rejected local
   midpoint rule, and the 33→4 collapse of narrow-dot flags once members were
   counted. mkpart twins are never counted separately anywhere in the audit.
3. **Wrong owner upstream.** A stray mark makes band-relative position
   meaningless — R1/R2 flags overlapping R9 (>10u out of line band) are
   categorized ownership-suspect INSTEAD of name-swap (the `continue` after
   R9), so a steal is never "corrected" by renaming.
4. **Band geometry.** Lines wider than 1.6x the page median band height
   (headers/basmalah/ornate spread) are excluded from flagging; the odd_line
   bucket was tracked separately through calibration.
5. **Encoding and convention.** The waqf budget is a RANGE across editions
   (R10); iqlab/open-tanwin is decided by the QPC encoding after the rasm_uthmani
   heuristic was PROVEN wrong (R7 — rasm_uthmani writes the meem at idgham/ikhfa
   too); low waqf stops exempt R3; ۭ exempts small_meem entirely.
6. **Label-table artifacts.** Composite "+" labels: the two `hamzah+kasrah`
   fused composites appear as their own family and are never split-counted.
   Derived families are never judged by shape, only by position+budget.
7. **Family medians mix shapes.** No size-vs-median rule here at all
   (audit_marksize owns size); the one place shape statistics are used (R7)
   splits the population by the QPC text first, and the two sub-populations
   separate cleanly (3.2-3.3 wide vs 4.5-11).
8. **Sample bias / juz 30.** Calibration ran a separate clean30 bucket
   (pages 582-604): every adopted rule's clean30 distribution matches the
   global clean one (fathah sbelow all <= −4 but 3 in −4..−2; tanwin_al_kasr sabove
   empty above −4; no new tails). No juz-30-specific exception was needed.
9. **The judge can be wrong twice.** All flags cross-checked against
   `visual_verdicts.json`: 0 collisions with no-issue verdicts among R1-R6 and
   R8-R11; the single R7 collision is a width verdict on a different
   property. All 11 round-7 waqf verdicts and both earlier waqf verdicts
   are flagged.

### Flagged cases REVERSED by a confounder during calibration
- 29 narrow "three_dots"/"two_dots" masters (bbox confounder #2): members'
  widths complete the count — removed.
- مُتَكَبِّرٍۢ p470 / شَجَرٍۢ p536 tanwin_al_kasr pairs at dx 7.4-7.7 (encoding
  confounder #5): the diagonal open-tanwin drawing — R5 threshold moved
  outside them.
- مَجْر۪ىٰهَا p226 waqf 2.9u below band (encoding confounder #5): the text's
  own low stop — exempted in R3.
- 19 clean small_meem 4-11.5u below band (convention #5): the ۭ low form —
  small_meem excluded from R3.
- p1's basmalah-line marks (band confounder #4): odd_line exclusion.

## Trial corrector — QSVG_MTYPE (default OFF)

Renames/regroups only; no ink crosses a word boundary; no atom changes; zero
pixel change; zero count change. Two families, both two-signal:

- **(a) لأيات name-crossing** (R2 pattern): top welded "tanwin_al_kasr pair"
  becomes the two fathahs; the two below-band strokes become the welded
  tanwin_al_kasr pair. Guarded by: tanwin_al_kasr pair above band top AND fathah masters
  == fathah budget AND >= 2 strokes > 1.5u below band within weld windows.
- **(b) R7 meems**: at a QPC-meemless word, a small_meem within 16u
  (p95 = 13.6) of the word's tanwin master is renamed to that tanwin as a
  welded part.

Measured (2026-08-26): bench identical ON vs OFF (SCORE 79, FAILURES none,
pixelfail 0, same 5 budget-mismatch words); audit_marks on the 20 touched
pages: 6 flagged words before, 6 after, zero rows added or resolved;
audit_marktype on those pages: **97 flags → 10**, every survivor a genuine
ownership/lost-twin case, no new flags anywhere.
