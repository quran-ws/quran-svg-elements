# Closing the gap to MushafDatabase

**Goal (26 Aug 2026):** the same or better word-level accuracy than
`mushafdatabase/MushafDatabase-Ligature-Based-SVG`, and the same attribute
vocabulary in our output.

**Status: parity on one measure of four, ~100 words short on the rest.**

## 1. Where we actually stand

`tools/score_both.py` scores **both** decompositions over **every** word against
evidence that comes from neither of them — the QCF v2 advance widths, the Arabic
joining rules, and the King Fahd Complex's own text of this print. All 604 pages,
77,383 words compared on both sides:

| | at session start | **now** | MushafDatabase |
|---|---|---|---|
| width, mean \|log(measured/expected)\| | 0.0829 | **0.0822** | 0.0818 |
| width, 99th percentile | 0.4925 | **0.4886** | 0.4884 |
| words off by more than 1.5x | 1241 | **1208** | 1193 |
| **words off by more than 2x** | 159 | **139** | 141 — **we are ahead** |
| pieces beyond the joining rules | 34 | **19** | 0 |
| dot count wrong | 144 | **66** | 0 |

Bench SCORE 76 (from 77), no failures, pixelfail 0.

### Do not quote the adjudicator as an accuracy comparison

An earlier version of this document reported "our defects 352, theirs 58". That
number comes from `adjudicate_ref.py`, which only ever looks at the ~500 words the
two decompositions DISAGREE about. "Theirs" is the reference's error rate on that
subset — not over the corpus — and setting it beside ours compares two different
things. It is useful for *routing repair work*, which is what it exists for, and
useless as a measure of accuracy. `score_both.py` is the measure.

### Three measurement fixes that changed the answer

Each of these moved the reported gap by more than any repair did, so they are
recorded here as findings, not as housekeeping.

- **Count pieces as connected runs of ink, not as drawn objects.** `أَلِيمٌۢ` on
  p136 is two paths for the reference and three contours for us at *identical*
  extent. Counting objects charged that difference in draughtsmanship as theft:
  piece surplus 5 -> 1 on the sample when fixed.
- **A ya before a hamzah is drawn undotted.** Both decompositions independently
  count three dots in `شَيۡءٖ`; the budget demanded five. Every one of the 21 words
  where the two sources agreed and the budget did not was `شيء` or `بشيء`. Dots
  went 26 vs 19 -> 7 vs 0 on the sample — the shared noise had been hiding the
  real gap.
- **Match ink by IoU, not intersection-over-the-smaller.** A dot lies wholly
  inside its letter's bounding box, so the letter scored a perfect 1.0 and tied
  with it. Every dot signature came back ~50% "pure" with ligatures as runners-up.
  On IoU, `dot -> dot` is ~100%.

### What is left, and what it is not

The override route is **exhausted**: `close_ref_gap.py` settles at 307 overrides
with zero new ones in the second round. What blocks the rest:

```
   slash strokes, never moved by design      4047
   the adjudicator says THEY are wrong         43
   ink no reference word claims                31
   the receiving word has no room for it       10
   would leave a word straddling two lines      9
```

- **66 dot errors.** Not a label-table problem — `dot -> dot` is ~100% pure. Not an
  ownership problem — the ink is in the right word in every case traced. They are
  per-occurrence welding and clustering defects: `فَبَعَثَ` (p33) has a three-dot
  `ث` cluster whose master is labelled `two_dots`, and `بِٱلۡمَعۡرُوفِ` (p27) welds
  two dots fifty units apart.
- **19 piece surpluses.** Real body fragments. `لِّلَّهِ` (p15) and `بَيِّنَةٍۢ`
  (p33) are the type.
- **15 width outliers.** The residue of a tail where both sources sit near 1.5%,
  so the prior itself is noisy at that threshold.

### Things measured and rejected — do not retry

- **Restricting the nested-dot weld to ج.** Only ج has a dot below it, and
  `بِٱلۡمَعۡرُوفِ` on p27 visibly loses its `ف`'s dot to the صلى beside it, so the
  rule looks plainly too broad. It is not: dot errors went from 66 mushaf-wide to
  **150 over the first 120 pages**. Un-welding turns a sign's own dot into a
  spurious extra far more often than it recovers a letter's.
- **Counting welded twins as strokes** (7 -> 358 disagreements), and **counting
  only twins drawn clear of their master** (also 358). A master's label already
  accounts for its members.
- Two harness bugs worth remembering: a rollback that fired *before* any override
  was written destroyed the previous round's 222 accepted fixes and made the run a
  no-op; and a stop rule that halted on the reference's count rising by one while
  ours fell by two hundred.

### The defect set the adjudicator routes (baseline figures)

These describe the 352 words the adjudicator convicted us on before this
session's repairs — the work list, not the accuracy measure. 307 of them
now carry overrides. The shape of the set is what matters here.

| | |
|---|---|
| Line errors (word filed under the wrong line) | 11 |
| Boundary errors (word holds the wrong ink) | 341 |
| Size of a boundary error | median 7.1 units, p90 15.3, max 35.4 |
| Pages holding them | 179 of 604 — **425 pages are already clean** |
| Juz 30 (p582–604) | 1.87 per page vs 0.53 elsewhere — **3.5×** |

### Why our own audits could not find them

| audit | sees | of our 352 |
|---|---|---|
| `audit_marks.py` | mark counts vs the text | 127 (36%) |
| `audit_intervals.py` | a mark in a neighbour's exclusive core | 95 (27%) |
| `audit_width.py` | a word the wrong size for its line share | 92 (26%) |
| **any of the three** | | 241 (68%) |
| **none of them** | | **111 (32%)** |

A third of our confirmed defects are invisible to every internal audit. And the
best internal detector is mostly noise: `audit_width.py` raises 1,643 flags of
which **92 are real — 5.6% precision**.

### The queue is not the work list

The largest family in `docs/defects/queue.json` is `waqf`, 202 flags. Putting
each to a three-way vote between the text budget, our ink and the reference's ink:

```
TEXT is the odd one out (we and the reference agree)   181   90%
WE are the odd one out (a real defect)                  17    8%
not comparable                                           4    2%
```

The cause is concrete and checkable: the KFGQPC artwork draws a `ۚ` after
`بَلَىٰ` on p12 that quran.com's word text does not carry at all, and quran.com
puts a `ۙ` on `رِّزْقًۭا` (p5) that the artwork does not draw. `audit_marks.py`
takes quran.com's word text as ground truth for what is printed. For waqf signs
it is not. **Nine of every ten waqf "defects" are audit artefacts.**

Across the whole flag set the same vote gives roughly a quarter real. So of the
659 mark flags, the honest defect count is nearer 170 than 659 — and it is a
*different* 170 from the 352 the reference finds.

---

## 2. What is now in place

Seven new tools. All but one are measurement; none change the decomposition:

| tool | what it does |
|---|---|
| `tools/refdb.py` | reads the reference SVGs as data; registers their coordinates onto ours |
| `tools/audit_ref_words.py` | per-word edge, line and piece-count agreement → `docs/defects/reference_words.json` |
| `tools/adjudicate_ref.py` | decides each disagreement OURS / THEIRS / UNCLEAR → `docs/defects/reference_verdicts.json` |
| `tools/audit_ref_marks.py` | three-way vote on every mark flag → `docs/defects/mark_votes.json` |
| `tools/score_both.py` | scores BOTH decompositions against outside evidence — the accuracy measure |
| `tools/ref_overrides.py` | turns adjudicated convictions into geometry-keyed overrides |
| `tools/close_ref_gap.py` | drives audit → adjudicate → override to a fixed point, gated each round |
| `tools/sig_labels_from_ref.py` | what the reference calls each of our shape signatures, with purity |
| `tools/waqf_table.py` | writes `.cache/marks/waqf_types.json` — the ج / صلى / قلى split |

Registration deserves a note, because three attempts were wrong before this one:

- Least squares over the ayah medallions — one bad landmark dragged whole pages;
  p397, p431 and p551 reported 258 defects that did not exist.
- Medallions at all — their source data is broken on some pages.
- A fixed 3/4 scale — true on body pages, false on pages 1 and 2, which are set
  on their own spacing and drawn at 0.867.

What works: landmarks from the ~120 words per page both sources agree on, scale
from the median of widely separated pairwise slopes, offsets from the median
residual. Medians because a few of the landmarks *are* the defects being looked
for, and a mean would let them hide themselves. Worst page MAD is now 0.50; it
was 131.

One more correction worth keeping: the two sources spell the same rasm with
different code points (`ى` vs `ي`, `ٱ` vs `ا`). Comparing raw code points dropped
**4,025 words** out of the audit — including the visibly broken `يَأْتِىَ` on
p555, while flagging the words either side of it. Folding same-rasm forms took
comparable words from 73,399 to 77,383.

---

## 3. The plan

Ordered by leverage. Every step ends at the same gate (§4). No step is accepted
on reasoning; each is accepted on a number that moved the right way.

### Step 0 — stop working the wrong list  *(no code change)*

Re-base the queue on the votes before spending a day on 202 waqf flags that are
90% artefacts.

```bash
python3 tools/audit_ref_marks.py "<ref>/SVG V1.01" --jobs 8
python3 tools/make_queue.py <sweep-dir> --votes docs/defects/mark_votes.json
```

`make_queue.py` needs to learn to drop `TEXT-ODD` rows. Deliverable: a queue
whose every entry is a defect some source confirms.

Also fix the budget itself, so the artefacts stop being generated: `audit_marks.py`
should take the waqf expectation from the ink both decompositions agree on, not
from quran.com's word text. Expected effect: mark flags 659 → ~470, with no
change to the pipeline.

### Step 1 — the 341 boundary defects, root-caused, not patched

This is the whole gap. Work it in families, not one word at a time.

The shape of the defect is already known: 65% of them have their immediate
neighbour flagged too, and they come in matched pairs — one word too wide, the
adjacent one too narrow by the same amount. `بِمَا` on p136 is 2.5 units wide
where it should be 17.6, and `كَانُوا۟` beside it is 55 where it should be 36.
Same on p331: `فَقُلْ` is 4 units instead of 22 and `تَوَلَّوْاْ` has the rest.
The cut between two words is landing in the wrong gap.

1. **Classify.** Group the 341 by the pass that placed the cut. `QSVG_TRACE=<x>`
   prints every `_omove` hand-off with the calling line number; `_omove` is the
   single choke point for the ~20 movers. Ten traced examples should name the two
   or three passes responsible for most of them.
2. **Fix the pass, one at a time**, cheapest first. After each, the gate.
3. **Never** drive a repair from the reference alone. The rule that has worked in
   this project is two independent signals agreeing, and it still holds: the
   reference says *where* the boundary is, and `adjudicate_ref.py`'s third source
   — the QCF advance widths, or the joining-rule piece count from `segment_word`
   — says *whether we are the ones who are wrong*. 58 of the 478 disagreements
   are the reference's own errors. Copying it blindly would import those.

Target: 352 → under 100.

### Step 2 — juz 30

3.5× the defect rate of the rest of the mushaf, and now with a clean list of
which 43 words. `CLAUDE.md` records that the cause tracks **ayahs per page**
rather than word density, and that medallion proximity and metric bias were both
tested and are dead. The untested hypothesis is band geometry: surah headers and
basmalahs take whole lines in juz 30, so the number of *text* lines per page
differs and the line-mapping stage sees a different grid. Compare band heights
and the line-mapping stage's behaviour on p582–604 against a body page.

Cheap first check: of the 43, how many are on a page carrying a surah header?

### Step 3 — the residue, as data

Whatever no rule can reach goes to `.cache/review/overrides.json` via
`tools/build_overrides.py`, keyed by geometry so it survives pipeline changes.
Last resort, one word each — and note that **`overrides.json` is currently `{}`**.
The 447 words Abdullah marked in the review platform are all recorded as
`kind: "note"`, status `proposed`; only 4 are `move-element`. None of them are
being applied. Either they should be converted, or the platform should be
capturing moves rather than notes.

### Step 4 — the attribute vocabulary

The reference's per-path labelling is richer than ours, and the goal includes
matching it. Current state:

| | reference | ours |
|---|---|---|
| path type | `data-type`: text, diacritic, dots, kaf-hamzah, waqf, sajdah-line, sajdah-mehrab, juz-star | `data-kind`: body, mark, ayah_mark_ornament, ayah_number |
| diacritics | `data-diacritic`, 25 named values | `data-mark`, 17 values, dots mixed into the same attribute |
| waqf signs | `data-waqf`: madd_lazim, jaiz, sali, qila, taanuq | **all collapsed to `waqf`** |
| grouping | `md-ligature-*` / `md-diacritic-*` per cluster | none |
| word attrs | + `line-number`, `waw-alatf`, `type` | missing all three |
| missing entirely | | kaf-hamzah, juz-star, sajdah-mehrab, sajdah-line, small seen, small meem, the successive-tanwin and iqlab distinctions, rectangular vs rounded zero |

**The cheap way to get all of it.** Every one of our paths carries a `data-sig`
shape signature, and `.cache/marks/labels.json` maps a signature to a label for
the whole mushaf. Registration puts our paths and theirs in the same frame to
0.01 units. So: for every signature, collect what the reference calls the
overlapping path *everywhere it occurs*, and take the majority with its purity.
That yields an evidence-backed signature→label table covering the full
vocabulary, built as **data, not code** — which is this project's standing rule
for outside input.

This also settles Lane B: 72 shapes are unlabelled or contested and cause 196
flagged words. A signature whose reference label is 99% pure over 400
occurrences does not need a human.

Guard rails, both learned the hard way and both non-negotiable:

- **Measure every label change.** `scratchpad/label_bisect.py` applies confirmed
  labels one at a time against an 11-page sample and keeps only those that do not
  make things worse. It found the one bad entry out of 18 last time. One wrong
  entry cost +527 flags mushaf-wide.
- **Never collapse a composite.** `fathah+hamzah` is one outline carrying two
  marks. Collapsing it to `hamzah` deleted a fathah everywhere and took flags from
  991 to 1601. `apply_labels.py` refuses without `--force`; leave it refusing.

Distinguishing the five waqf subtypes is the same mechanism: they are five
distinct outlines, so five signatures, and the reference names each one.

### Step 5 — prove it

Re-run §1 end to end. The claim "same or better than MushafDatabase" is only
earned when `adjudicate_ref.py` reports OURS ≤ THEIRS on the same corpus — and
when the 58 THEIRS have been looked at, because some of them are places where we
are already right and should stay that way.

---

## 4. The gate

Unchanged from `docs/PROCESS.md`, plus one new line that the goal requires.

```bash
. env.sh
python3 scratchpad/bench.py                       # SCORE, FAILURES, pixelfail
python3 scratchpad/cmp_pages.py <the pages aimed at>
QSVG_OUT="$QSVG_SWEEPS/cand/pages" QSVG_JOBS=8 python3 scratchpad/full_sweep.py 1 604
python3 scratchpad/cmp_full.py cand
python3 tools/audit_ref_words.py "<ref>/SVG V1.01" --jobs 8   # NEW
python3 tools/adjudicate_ref.py "<ref>/SVG V1.01" --jobs 8    # NEW
```

Accept only if **all** of:

1. no bench case fails and `pixelfail` is 0;
2. total mark flags do not rise and no page worsens by more than +1;
3. **`adjudicate_ref.py` OURS falls, and THEIRS does not rise** — a change that
   trades our errors for agreement with the reference's errors is not progress;
4. after anything touching the artwork or the line cut: `audit_split.py` stays 0,
   `audit_lines.py` does not worsen, and `verify_render.py`'s largest
   single-pixel alpha change does not grow past 17/255.

Re-pin `tools/_pipeline_baseline.py` on accept. Restore from
`~/Documents/quran-svg-backups/` on reject.

Every fix becomes a bench case. And `bench.py` has a hole worth closing first: a
case whose word key stops being produced neither passes nor fails — it silently
disappears. Two of the seventeen cases did not run in this session's run. A case
that can vanish is worse than no case.

---

## 5. Risks

- **Becoming a copy of the reference.** It is wrong on 58 words we currently get
  right. The adjudicator exists precisely so that the reference proposes and a
  third source disposes; do not shortcut it.
- **Both sources wrong the same way.** Two independent decompositions agreeing
  is strong evidence but not proof. The 425 pages with no disagreement are
  *probably* clean, not *certainly* clean.
- **The 68 UNCLEAR.** The QCF width prior cannot separate the two sides there,
  and 57 of them are line disagreements where a width comparison means little.
  `.cache/qcf_lines.json` is the natural third source for the line question and
  is not yet wired into the adjudicator.
- **Regression through labels.** One signature applied mushaf-wide moves hundreds
  of flags at once, in either direction. `label_bisect.py` before every adoption.
