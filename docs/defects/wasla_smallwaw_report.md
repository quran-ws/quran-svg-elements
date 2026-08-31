# The two frozen families: wasla (27) and small-waw (26)

## Plain-language summary

Both families were one systematic cause each, plus two loose ends.

**Wasla.** The wasla sign is drawn as a tiny ص above its word's first alef. In
thirteen ayah-final divine-name pairs (ٱلْعَزِيزُ ٱلْحَكِيمُ and its family)
the two words are kerned so tightly that the first word's final letter sweeps
UNDER the second word's alef — so when ink is first handed to words, the second
word's wasla lands on the FIRST word. That is 26 of the 27 flags: thirteen
pairs, each flagged twice (one word holding two waslas, its neighbour none).

**Small-waw.** The suffix sign ۥ trails after its word's final ه, hanging in
the gap BEFORE the next word — and gets picked up one word late the same way.
Ten pair/chains (20 flags) are exactly this, some chained through a run of
ـهُۥ words (p205 لَهُۥٓ أَنَّهُۥ عَدُوٌّۭ shifts every sign one word left; p538
runs three deep). The other five (p255, p293, p396, p603, p604) are the same
sign falling off the other edge: the ۥ hangs low, the line cut tags it one line
DOWN, and it ends up inside an UNOWNED furniture atom (the ayah medallion
below) — the word simply loses it and no count audit can see furniture.

**Why every earlier fix wave left them frozen.** The mid-pipeline reconcilers
all test budgets, and at the time they run the theft is a CHAIN, not a pair:
traced on p273, at oracle time ٱلْعَزِيزُ held only the stolen wasla — its own
was still with وَهُوَ — so it looked at-budget and the trial move scored flat
(base=2.0, d=2.0) and was reverted. The chain unwinds link by link across later
passes, and the clean surplus/deficit pair only exists after the LAST mover,
where nothing ran. Hence stability through every unrelated fix.

## The fix — QSVG_RESEAT (default ON, =0 reverts)

One late pass in `tools/assign_words.py`, immediately before `rewrite()`:

1. **Line re-seat** (both families): per line, when the words' text budget for
   the family balances in TOTAL but not per word, re-deal the held marks in
   reading order — rightmost mark to the first slot; both the signs and their
   anchor letters are monotonic along the line. Commit only if EVERY reseated
   mark sits within its new owner's reach (x window 8u); one miss aborts the
   whole line. Budget-neutral across the line by construction. Text and
   geometry must both agree — the two-signals rule.
2. **Unowned adoption** (small-waw): a ۥ held by an UNOWNED atom is claimed by
   a word that (a) spells one it does not hold, (b) contains the sign's y in
   its own band, (c) covers its x within reach — and only when exactly ONE word
   qualifies. Moves go through `put_in_ligature`; line tags follow the owner.

## Gate numbers

| gate | result |
|---|---|
| bench (14 pages, 4 new cases on p205/p273) | SCORE 78, no failures, pixelfail 0 |
| bench, previous 12-page set | unchanged — the new pages add no mismatch and all old cases pass |
| full sweep vs `.cache/sweeps/r7fix` | MARK 155 → 107 (−48), intervals 80 → 80, fully clean 469 → **489** (+20) |
| wasla flags | 27 → **1** |
| small-waw flags | 26 → **1** |
| pages worse (RESEAT on vs off, current tree) | **0** |
| controls p1/p3 | byte-identical with the pass on vs off |

Attribution notes:
- The sweep-vs-sweep diff also shows ±3 fatha/kasratan drift on six pages
  (p111/p129/p155/p433/p518/p529, all iqlab-kasratan words). Verified NOT this
  change: identical flags with `QSVG_RESEAT=0` — it is pre-existing drift
  between the r7fix sweep and the current tree (item-29 family). Net for those
  six pages: 3 improved, 3 new, 0 caused here.
- p384 trades 2 mark flags for +1 interval flag: ٱلْعَلِيمُ now correctly holds
  its wasla, which is DRAWN tucked inside ٱلْعَزِيزُ's kerned territory — the
  same named-mark visibility pattern as the iqlab fix (item 18), ownership
  right, page's mark budget clean. (Offset by p431's interval −1; total flat.)
- New sweep: `.cache/sweeps/reseat`.

## The two that remain — needs-eye

Crops in `docs/defects/wasla_smallwaw_samples/`, proposal items ready to append
in `docs/defects/wasla_smallwaw_proposals.json` (not appended to proposals.json).

1. **p337 22:40:31 يَنصُرُهُۥٓ (small-waw 2/1).** The "second small-waw" is the
   word's own final ه — a letter read as a mark (the R7 pattern); the word is
   also one letter piece short (1 body where ينصر+ه allow 2). The real ۥ sits
   just left with the maddah above. Correct fix is letter restoration through
   the label/signature channel — labels.json untouched per this task's brief.
2. **p223 11:13:3 ٱفْتَرَىٰهُ (wasla 1/0, also small-alef 1/0).** The ink is
   RIGHT — wasla + dagger alef, exactly the 1441H print. quran.com's
   `text_uthmani` for this one word carries the imlaei spelling (افْتَرَاهُ),
   so the budget demands zero of each. An upstream word-source data defect
   (their uthmani equals their imlaei for word id 15424); needs a decision on
   the channel — patch the cached word from a verified source (QPC and
   DigitalKhatt both carry the print's spelling) or widen the audit budget to a
   range where uthmani==imlaei and QPC disagrees, the same shape as the
   waqf-range rule.
