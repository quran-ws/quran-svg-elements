# Letter splitting — where it stands

State of play on the `feat/letter-splitting` branch, 2026-09-08. `docs/LETTERS.md` is the
method: how a run is cut, what the gate proves, and a dated log of every measurement.
This file is the short answer to *where are we, what worked, what did not, and what next*.

Branch: `feat/letter-splitting`, 76 commits off `main`. Nothing here is on `main`.

---

## Where we are

Every multi-letter run of the mushaf is cut into one group per letter, and the build is
proven against the word build it comes from.

| | rule cutter (first attempt) | **shipped now** |
|---|---|---|
| multi-letter runs | 90,244 | 90,313 |
| runs left uncut (`data-unsplit`) | 10,165 (11.3%) | **109 (0.12%)** |
| letters emitted | 285,741 | **322,758** |
| gate: count (letters vs the text) | 0 | **0** |
| gate: ink (pieces reproduce their contour, no overlap) | 0 | 6 pages |
| gate: pixels (raster vs the word build) | 35 pages | 18 pages |
| joint error vs the tajweed hand cuts, held out | 1.06u | **0.50u** (76.9% within 1u) |

Proof failures 24, all of them the boolean library's seam and sliver class. The two
priors that rank work rather than block it: shape 956 (islands and ragged cuts), size
4,641 (letters far from the area that letter takes elsewhere).

The model is `.cache/letters/model_ft5.pt`. Build with
`QSVG_LETTERS_TAG=model` → `.cache/letters/cuts-model`, `.cache/letters-svg-model`,
`.cache/letters/audit-model`.

Shape verdicts are **complete for the common pass**: all 738 shapes covering 90% of every
letter drawn in the mushaf are reviewed (`docs/defects/letter_shape_verdicts.jsonl`), 648
right and **90 corrected by hand** with a drawn loop. The corrections cluster where the
letters are: ل 20, ي 9, ا 8, م 8, ن 7, and ك و ه 6 each. Three of the ninety were withdrawn on review (the split was already
right), leaving **87**.

**The loop is the letter.** Of the 87, **82 mean the ink INSIDE the drawn loop**, including
all thirteen Abdullah confirmed by eye after they resolved the other way. The reason the
side was ever in doubt is measured: the click that names the side lands ON the drawn line
in 83 of 87 cases (median 0.4% of the loop's span away from it), so a rasterised
containment probe is deciding a knife edge, and it fell the wrong way 13 times. The page
now resolves the side by exact ray casting on the drawn points, and records the answer in
the trim as `select`, so nothing downstream re-derives it. The five that still resolve
`out` are marked `needs_confirm` in `letter_trims_review.html`.

Abdullah has drawn **166 words** by hand (`docs/defects/letters_hand_cuts.jsonl`), all
of them accepted into the training labels. They cover the letter pairs the tajweed
layers never colour: لك 44, عل 26, كم 25, لم 23, هم 20, لح 17, ها 14, به 14, and
smaller counts for كذ, كف, فس, سل, كل, ته, فل. Nothing drawn yet for بم.

---

## What worked

**The QUL tajweed page fonts as ground truth.** The same artwork, hand-cut into coloured
letter layers for tajweed. Registered to our ink (ICP, 100% coverage) they give 51,818
hand-cut joints, 31% of all 168,009, covering 436 of 661 letter pairs. Everything else
is built on top of that.

**A learned labeller instead of geometry.** A U-Net that owns every ink pixel
(`tools/letter_model.py`), trained on the tajweed layers as partial labels. It replaced
a rule-based cutter that fitted chords to DigitalKhatt glyph templates: uncut runs fell
11.3% → 0.6% and joint error halved, 1.06u → 0.50u.

**Telling the model what it is looking at.** Feeding the letter identity and its form
(isolated, initial, medial, final) as extra input channels, alongside the run raster and
the letter count. Abdullah asked for this; it is in every model since.

**Continuity as an unconditional rule.** One letter, one region. A region the ink-join
cannot connect goes to the neighbour it touches, and a letter keeps the region that
continues into the NEXT letter. On a shared لك stem that gives the arm to the ل and the
baseline to the ك, which is what Abdullah's own drawn lines do.

**Hand-drawn cuts for the pairs nothing else covers.** A page where he draws a line
across each joint (`tools/build_letters_label_page.py`), the lines becoming exact labels
weighted above the partial ones. Agreement with his conventions on pages the model never
trained on went 0.816 → 0.901.

**The drawing page telling him the answer as he draws.** The label builder's rules
re-implemented in the browser, so each card shows every letter on its own the moment a
line lands, green when the pieces match the letter count. Checked against the Python
masks on 16 words: same piece count, same order, matching pixel shares. Before it, words
came back a line short and had to be redrawn.

**The repo file, not the browser, is the record of a review.** A second lesson came with
the first: the page's storage key was made page-specific mid-review, which orphaned 90
drawn trims under the old key `letter_shape_verdicts` and made the page look empty. They
were recovered from the browser itself. `restore()` now reads the legacy key as a fallback,
and a storage key must never change under a review in progress. The shapes page used to
remember only in `localStorage`, and a browser stores only what differs from the default,
so a rebuild — or a second machine — showed judged shapes as fresh green and the copy
button re-emitted them as *good*. Fifteen drawn trims came back that way. The page is now
seeded from `docs/defects/letter_shape_verdicts.jsonl` at build time, the browser may only
override it, and each card carries an explicit REVIEWED flag set by *mark section reviewed*
under its heading. Copy and Download emit **only reviewed shapes**, so a default green can
never again be mistaken for a judgement.

**Naming a piece by hand where no line can work.** The medial ك+ل ligature is an arm
plus a bowl and a stem plus a foot — four pieces for two letters, and no chord can give
one piece per letter. Clicking a piece assigns it to a letter; the assignment is stored
by centroid so it survives any change in how pieces are ordered.

**Fixing the word build's misfiled letters.** The emitter sometimes files a letter's ink
in the group next to it. Two rules in `align_runs`, each proven by contour counts plus a
measured size band (ا 123–169 px at h/w 5.4, و 262–299 px at 1.09, ء 154–179 px at 1.15
— the bands do not touch), move a trailing letter forward or a leading one back. About
1,100 words mushaf-wide; every one on the sample pages rendered and checked by eye. Uncut
runs 655 → 592 → 534.

**Short fine-tune doses.** Every drawn run plus a slice of the labelled ones, nine
minutes, rather than a full epoch.

**Measuring before believing.** Every model went through four measures — held-out pixel
accuracy, joint error against the tajweed cuts, agreement with the drawings on pages never
trained on, and hard cut failures on pages 1–60 from a tagged A/B build. Six checkpoints
were adopted on that evidence and six rejected.

---

## What did not work

**A rule-based chord cutter alone.** Chords fitted to glyph templates cannot express a
letter drawn in two pieces, and left 11.3% of runs uncut. Kept only as a comparison.

**Forcing cuts to be straight lines.** Abdullah photographed a cut that wandered instead
of crossing the stroke. Imposing the chord's half-plane on the ink around each cut breaks
more letters into islands than it straightens, at every band width tried (pages 41, 81,
141: 8 shape flags with it off, 25 at 0.5u, 23 at 1u, 39 at 2u), because a straight line
also slices the parts of a letter that curve back past the cut. Not adopted.

**Moving small islands to the letter that surrounds them.** Changed nothing at all: the
islands are not in the model's pixel ownership, they are made later by the boolean
library that builds the final paths.

**Full fine-tune epochs.** Two of them (lr 5e-4 and 1e-4) drifted on touching pairs the
tajweed layers never label — word-final ون and نى, where the و starved to under 1% of the
run — and doubled hard failures. A short dose on the same data did not.

**Letting the drawn set keep a fixed weight.** A drawn word carries 10× an ordinary one.
That was 1% of the loss at 40 words and **31%** at 166: the model stopped learning the
mushaf and memorised the drawings. Weight has to be set as a share of the loss.

**Holding out the two-letter drawn runs.** Tested because 39 of the 166 are two letters
against a mushaf of longer runs. Removing them cost 13 more failures than keeping them,
so they were helping.

**Training from the base model with everything present.** Three full epochs from
`model_cond_e3`, the drawings at 4.9% of the loss. Best held-out pixel accuracy the
project has recorded, 0.928, and still 158 hard failures against 129. Rejected.

**Adopting on the pixel metric.** Every model trained further since `model_ft5` is better
at labelling pixels and worse at cutting. The pixel metric and the gate have come apart,
and the gate is the one that ships.

---

## The bottleneck, and what to do next

**The starved letter is fixed (2026-09-08).** Of 533 runs the cutter could not realise,
452 had a letter under 2% of the ink, and rendering them showed the same thing every
time: the boundary roughly right, the labels shifted by one, one letter covering two.
`repair_starved` takes that share back — the donor is the neighbour furthest over the
area its letter draws elsewhere in the mushaf, it gives only what brings both toward
that size, and it gives it from the end the starved letter reads on. Mushaf-wide:

| | before | after |
|---|---|---|
| runs the cutter could not realise | 533 | **108** |
| empty piece | 272 | **8** |
| letter without ink | 216 | **55** |
| pieces do not reproduce the run | 36 | 36 |
| area not conserved | 9 | 9 |
| runs left uncut in the output | 534 | **109** |
| letters emitted | 321,403 | **322,758** |
| size flags | 5,764 | **4,641** |

The two failures it does not aim at did not move by one, which is the signature of a
repair that did what it claimed. `QSVG_LETTERS_STARVE=off` reverts it.

Two repairs were measured and rejected on the way: growing the letter from the model's
own probability (it bites the donor's middle, the donor splits, the cleanup undoes it)
and splitting whichever neighbour is widest (wrong donor wherever letters overlap in x).
So was **recursive halving of long runs** — runs of eight or nine letters used to fail
every time, so halving them and labelling each half looked obvious, but it made things
worse (pages 1–60: 97 hard failures to 103, long-run failures 2 of 26 to 8 of 26)
because the halving leaves a fake stroke end the model has never seen. It needs no
fixing: the starved-letter repair already took long runs from failing always to failing
twice in twenty-six.

What is left, in order:

1. **Retire the boolean library.** The 36 reproduce failures, the 9 area failures, the 6
   ink pages, the 18 pixel pages and most of the 956 shape flags are one cause: skia
   re-fits curves and clips hole corners. An exact Bézier splitter removes them all.
2. **More drawn pairs.** بم has nothing, ته has two. The page is built by
   `tools/build_letters_label_page.py --rank --pairs …`.
3. **The five rejected checkpoints were re-measured against the fixed cutter
   (2026-09-08), and none is re-adopted.** The gate had indeed been reading the
   cutter's fragility: the spread across six checkpoints was 45 points before
   (129–174 hard failures on pages 1–60) and is 11 after (97–108). But `model_ft5`
   still leads on the gate (97), on joint error within 1u (76.9%) and on agreement
   with the drawings (0.901); the two with better held-out pixel accuracy, ft7 and the
   base-trained model, are behind on all three. Note they were all trained on labels
   built before the alignment fixes and this repair, so a short fine-tune on today's
   labels is a different experiment from the ones that failed — worth doing once بم
   and ته are drawn.

## Where things live

| | |
|---|---|
| method, gate, full dated log | `docs/LETTERS.md` |
| geometry core, cutting | `tools/letters_lib.py` |
| tajweed layer registration | `tools/tajweed_lib.py`, `tools/fetch_tajweed_fonts.py` |
| DigitalKhatt shaping (templates, comparison) | `tools/dk_lib.py` |
| training labels from the layers and the drawings | `tools/build_letter_labels.py` |
| the model, training, evaluation | `tools/letter_model.py`, `tools/train_letter_model.py`, `tools/eval_letter_model.py` |
| cuts, emission | `tools/build_letter_cuts.py`, `tools/emit_letters.py` |
| the gate | `tools/audit_letters.py` |
| drawing page, review sheets | `tools/build_letters_label_page.py`, `tools/build_letters_page.py` |
| the drawings themselves | `docs/defects/letters_hand_cuts.jsonl` |
| checkpoints | `.cache/letters/model_*.pt` (`model_ft5.pt` is the build) |
| unit tests | `python3 -m unittest tools.tests.test_letters` (28 tests) |
