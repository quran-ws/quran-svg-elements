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
| runs left uncut (`data-unsplit`) | 10,165 (11.3%) | **534 (0.6%)** |
| letters emitted | 285,741 | **321,403** |
| gate: count (letters vs the text) | 0 | **0** |
| gate: ink (pieces reproduce their contour, no overlap) | 0 | 6 pages |
| gate: pixels (raster vs the word build) | 35 pages | 18 pages |
| joint error vs the tajweed hand cuts, held out | 1.06u | **0.50u** (76.9% within 1u) |

Proof failures 24, all of them the boolean library's seam and sliver class. The two
priors that rank work rather than block it: shape 915 (islands and ragged cuts), size
5,764 (letters far from the area that letter takes elsewhere).

The model is `.cache/letters/model_ft5.pt`. Build with
`QSVG_LETTERS_TAG=model` → `.cache/letters/cuts-model`, `.cache/letters-svg-model`,
`.cache/letters/audit-model`.

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

Five rejected checkpoints in a row say the labels are no longer what limits this. Of the
42 failing runs on pages 1–60, **34 are runs where the model gave some letter under 2% of
the ink**: the boundary is in the right place, the letter is handed a sliver, and the
cutter refuses the whole run rather than accept a piece of almost nothing.

1. **Let a starved letter be grown, not fail.** In `cut_run_masks`, grow a letter whose
   share is a sliver from its own position instead of raising `letter without ink`. This
   is where the next 300 uncut runs are. **Do not fine-tune again until this is done** —
   the last five runs were wasted effort against this wall.
2. **Retire the boolean library.** An exact Bézier splitter removes the refit slivers
   behind the 6 ink pages, 18 pixel pages and most of the 915 shape flags in one move.
3. **More drawn pairs.** بم has nothing; ته has two. The page is built by
   `tools/build_letters_label_page.py --rank --pairs …`, served from `docs/defects` over
   a plain HTTP server, and every card turns green when its split is complete.
4. **Then re-measure the model.** Once the cutter tolerates a starved letter, the four
   measures should be run again from `model_cond_e3` — the training may well have been
   fine all along and the gate was reading the cutter's limits, not the model's.

---

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
