# Letter-level decomposition

Every word of the emitted mushaf becomes a sequence of `<g class="letter">` groups, one
per letter of its text, each holding the letter's body ink and its own marks. The
output is `.cache/letters-svg/hafs-kfqc/NNN.svg`, a post-pass over the word build in
`.cache/words-svg/hafs-kfqc/`. Pixel identity holds up to the chord seams (below).

Spec: `docs/superpowers/specs/2026-09-05-letter-level-decomposition-design.md`.
Plan: `docs/superpowers/plans/2026-09-05-letter-level-decomposition.md`.

## Run

```bash
python3 tools/fetch_tajweed_fonts.py                 # once: 604 QUL V4 tajweed page fonts, ~160 MB
python3 tools/build_letter_cuts.py 1 604 --jobs 32    # → .cache/letters/cuts/NNN.json   (~3 min)
python3 tools/emit_letters.py 1 604 --jobs 32         # → .cache/letters-svg/hafs-kfqc/  (~1 min)
python3 tools/audit_letters.py 1 604 --jobs 32        # the gate: PROOF FAILURES must be 0
python3 tools/audit_letters.py 1 604 --calib          # DK cuts vs hand cuts, per joint pair
python3 tools/build_letters_page.py                   # docs/defects/letters_review.html
python3 -m unittest tools.tests.test_letters -v       # unit tests
```

Needs `uharfbuzz` and `skia-pathops` (`pip install --user --break-system-packages
uharfbuzz skia-pathops`), `rsvg-convert`, and the word build present for the pages.

## Output

```xml
<g class="word" data-wid="3:3:5" data-uthmani="مُصَدِّقࣰا" …>
  <g class="letter" data-text="م" data-index="0" data-run="0" data-src="tajweed" data-conf="1.00">
    <path data-eid="e83-0" data-kind="body" data-cut="1" d="…"/>
    <path data-eid="e84" data-kind="mark" data-mark="damma" …/>
  </g>
  …
  <path data-kind="mark" data-mark="waqf-jaiz" …/>       <!-- word-level marks stay on the word -->
</g>
```

- `data-index` — letter position in the word's text (0 = first read). `data-text` — the
  letter as written (`ٱ`, `أ`, `ة` kept).
- `data-run` — which connected stroke the letter belongs to (dev information; the
  `ligature` wrapper is gone).
- `data-src` — where the cuts bounding the letter came from: `tajweed` (a hand cut lifted
  from the QUL tajweed font), `dk` (a DigitalKhatt-template joint), `none` (a run of one
  letter), or `tajweed+dk`. `data-conf` — the lowest confidence of those cuts.
- A run the builder could not cut is emitted UNSPLIT: one group with the run's whole
  text and `data-unsplit="1"`. A word whose ligature texts do not concatenate to its
  rasm is left exactly as the word build had it. Never a guess.
- Cut pieces carry `data-cut="1"` and the source contour's `data-eid` suffixed `-k`;
  every other path is byte-identical to the word build.

## How a run is cut

1. **Hand cuts.** The QUL "QPC V4 Tajweed" page fonts are this same 1441H artwork with
   every tajweed-coloured letter cut by hand into a COLR layer. Each word glyph is
   registered onto our word ink (one scale per page, ICP translation per word, accepted
   at ≥97% outline coverage — on p50 every word registers at 100%). Where a layer's
   outline runs through the inside of our stroke, that stretch is the hand's cut.
2. **DigitalKhatt joints.** The DK font shaped with HarfBuzz gives one glyph per letter.
   Registered to the run as templates (global correlation, then each template slid
   locally, reading order kept), every ink pixel takes the nearest template's label and
   each letter gets a reference point on its own ink. For a joint the hand did not cut,
   the stroke's centre line is walked from letter i's reference point to letter i+1's;
   every point is tried for the shortest crossing of the stroke through it, a crossing
   counts only if painting it separates the two reference points (a chord across a
   loop's wall never does — the ring connects around it — so a loop letter is cut
   right after its loop); of the crossings that count, the last one before letter
   i+1's template region begins is the joint: the connecting stroke stays with the
   letter it leaves.
3. **The cut itself** (`letters_lib.cut_run`). All chords of a run are painted three
   pixels wide over its raster (8 px/u); each letter is the connected side holding its
   reference point; the exact piece is the run intersected with that side's one-pixel
   envelope, and inside the painted strip with the chord's half-plane — so every
   boundary curve is the run's own except the chord. Checks: every chord separates
   letters k and k+1, no empty piece, areas conserve to 0.5%. Any failure is a flag,
   and the run is emitted unsplit.
4. **Marks.** Each letter's expected marks come from the text (`letters_of`, using the
   pipeline's own tables). Every (mark, letter) pair whose family fits an open slot is
   scored by the distance from the mark's centre to the letter's outline, and pairs are
   taken nearest first. Word-level marks (waqf signs, hizb…) stay on the word.

## The gate (`tools/audit_letters.py`)

| row | what | class |
|---|---|---|
| count | letters emitted == letters in the text, every letter with body ink | proof |
| ink | every non-cut path verbatim in both builds; cut pieces sum to their contour ±0.5% | proof |
| pixels | raster diff letters vs words at 1400 px: max ≤ 72/255 and over-24 pixels ≤ 10 + 8 × cuts | proof |
| marks | per-letter mark counts vs the text (tanween ≈ haraka; iqlab meem ignored) | prior |
| unsplit | runs/words emitted unsplit | count |

**Why the pixel row has a per-cut budget.** A chord is an abutting seam: two anti-aliased
edges meet and the pixel lightens by up to ~64/255 on 1–3 pixels per cut. `audit_pixels.py`
measured the same for split strokes (26–60) against 100+ for a real defect. Overlapping
the pieces to hide the seam makes it worse (measured: 0.1u overlap → 46/255), so pieces
never overlap.

## Numbers (full run, 2026-09-05)

| | |
|---|---|
| words | 77,433 |
| letters emitted | 285,741 |
| multi-letter runs | 90,244 |
| runs cut | 80,079 (88.7%) |
| runs left unsplit (honest gaps) | 10,165 runs, 10,587 counting word-level; blocked by: no separating crossing found 6,407 · DK labels disagree with the cut 2,499 · chord fails to separate 904 · flank/letter mismatch 780 · other 31 |
| words not registered to the tajweed font | 251 (a waqf-sign glyph the font draws apart, mostly) |
| words whose groups do not concatenate to the rasm | 188 |
| cuts | 160,735 = 51,818 hand (tajweed, 32%) + 108,917 DigitalKhatt; 1,211 joints need two chords |
| gate: count / ink | 0 / 0 on all 604 pages |
| gate: pixels | 569 pages pass; 35 pages carry edge slivers with max 76–108/255 on a handful of pixels (see below) |
| per-letter mark mismatches (prior) | 3,835 of 285,741 letters (1.3%) |
| DK cut vs hand cut, joints with both (every 15th page, 2,826) | midpoint distance median 1.06u · p75 2.1u · p90 3.7u · p99 8.4u |

**The 35 pixel pages.** `skia-pathops` re-fits curves when it intersects the run with
the pixel envelope; almost everywhere the deviation is sub-pixel at 1400 px, but on
these pages a sliver under 0.1u wide survives the reproduce check (which catches
strips ≥ 2 px at 12 px/u — the p70 ه counter corner it was written for). They are
edge pixels, not moved ink: on each of those pages ONE or TWO pixels exceed 72
(measured on p7, p16, p33, p40, p77). The proper fix is to stop using boolean
ops for the free-space boundary altogether: split the run's own Bézier segments at
the chord endpoints and stitch faces (exact, no refit). That is the next step.

**The largest unsplit family** is "no separating crossing found" (6,407 joints): a
medial ه whose two loops the template does not cover, لو ligatures where the و loop
sits on the ل stem, and ك after ل when the label gives the ك's baseline to a
neighbour. Every one is emitted unsplit with `data-unsplit="1"`, never guessed.

**Calibration reading.** Half the DigitalKhatt joints sit within one unit of the hand
cut, a quarter beyond two: the placement convention ("first crossing after the
letter's template ends") differs from the hand's. With 51,818 hand cuts on the same
joints a per-joint-pair offset can be learned; that is the second next step, before
any DK cut is trusted for tajweed colouring at the sub-unit level.

## Human loop

`docs/defects/letters_review.html` shows every flagged run and a seeded 2% blind sample of
accepted DigitalKhatt cuts, each letter in its own colour with the chords drawn, with a
verdict selector and a note box. "Copy decisions" emits JSON lines for
`docs/defects/letters_verdicts.jsonl`. Decisions become data (an override for a place, a
threshold for a joint pair), never code.

## The learned labeller (2026-09-05 afternoon)

The rule-based placement above is superseded by a model trained on the hand cuts
(spec: `docs/superpowers/specs/2026-09-05-learned-letter-labels-design.md`).

```bash
python3 tools/build_letter_labels.py 1 604 --jobs 32        # samples from the hand layers (partial labels)
python3 tools/train_letter_model.py --epochs 3 --batch 48 --quick --out .cache/letters/model_full.pt
python3 tools/eval_letter_model.py --model .cache/letters/model_full.pt      # held-out report
QSVG_LETTERS_TAG=model python3 tools/build_letter_cuts.py 1 604 --jobs 32 --model .cache/letters/model_full.pt
QSVG_LETTERS_TAG=model python3 tools/emit_letters.py 1 604 --jobs 32
QSVG_LETTERS_TAG=model python3 tools/audit_letters.py 1 604 --jobs 32
```

Every multi-letter run is a sample: its raster on a 96 × 256 canvas at 4 px/u and, per
ink pixel, a bitmask of the letter positions it may belong to — exact inside a hand-cut
layer whose letter index the cut record resolves, a set on the black stretches between
resolved letters (by reading order), all bits when nothing is resolved. The loss is
−log of the probability mass on the set. A small U-Net (24-channel base) labels every
ink pixel with its letter position; pages divisible by 10 are held out.

With `--model`, the label map IS the ownership: each letter's piece is the run
intersected with its pixels' envelope, and a straight chord through each boundary
component (its principal axis, clipped to the ink) replaces the pixel staircase
inside its strip. The emitter re-runs the model, so nothing about the labels is
stored beyond the chords.

Held-out pages (every 10th, 9,054 runs). The learned column is the model conditioned
on letter identity and form after three epochs (`model_cond_e3.pt`); its block rate is
with continuity enforced (a letter left in two regions is not split).

| | rules (DK templates) | learned labels |
|---|---|---|
| runs blocked (unsplit) | 1,002 (11.1%) | 671 (7.4%, epoch 2) |
| joint error vs hand cuts, median | 1.06u | 0.50u |
| within 1u of the hand cut | 47% | 75% |
| exact-pixel accuracy on hand-labelled pixels | — | 0.923 |
| gate: count / ink | 0 / 0 | 0 / 0 |
| gate: pixels | 4 pages | 3 pages (slivers, max 73–119) |

**Hand-drawn cuts.** `tools/build_letters_label_page.py` writes `docs/defects/letters_label.html`,
where Abdullah draws cut lines on sampled words of the letter pairs the tajweed layers never
cover (لك, عل, لح, كل, فل, كف, ته…). The lines land in `docs/defects/letters_hand_cuts.jsonl`
(page-path units) and `build_letter_labels.py` turns them into exact labels (a contour no
line touches, such as a final ك's arm, joins the piece it overlaps). 43 words so far; they
are weighted 10× in training and used to fine-tune the epoch-3 model (`--init`).

Rules the drawn-cut label builder needed, each found on a real drawing (2026-09-05 night):

- **Pieces are numbered along the chain the lines make, not by mean x.** Each drawn line
  joins the two pieces that hold most of the ink it removed; the chain is walked from the
  end whose ink lies furthest right. Mean x had swapped ل and ح in every لح/لج drawing
  (the ح bowl swings back under the ل stem, so it lies RIGHT of it). Found by rendering
  all masks on one contact sheet — do that after any change here.
- **A separate contour after a letter that never joins left is its own piece** (و then ه,
  ر then ا): no line is needed across a gap, and asking for one was wrong. Only after a
  joining letter does an untouched contour join the piece it overlaps (the kaf arm).
- **The word build sometimes files a trailing ا or و in the NEXT group** (ٱلْحَرَامِ: the ا
  sits in the م group; كَفَرُوا۟: the و in the ا group). `align_runs` moves it back on three
  witnesses that must all hold: the text says the group must break into more contours
  than it holds; the next group holds more contours than its text allows and its
  rightmost contour stands clear of the rest; and that contour has the measured size and
  shape of the letter (ا 123–169 px at 4 px/u, h/w 5.4; و 262–299 px, h/w 1.09; a bare
  ء, which also sits clear at the right of a group, is 154–179 px — the bands do not
  touch). Any one witness alone over-moves: ر against و merely touching lowers the
  first count, a final ه ring or a hamza seat raises the second. 33 words on 61 sample
  pages, all 33 checked right by eye.
- **Drawn cuts count on words the tajweed font never registered** (`no-registration`),
  which had silently dropped some.
- **Words drawn one line short are rejected, not guessed** ("do not give n pieces"); the
  page rebuilds with them on a Redo row that says which joint is missing
  (`build_letters_label_page.py --rank --words page:wid,…`, headings per pair with the
  measured joint counts, unsplit runs first).

Remaining blocks are "letter without ink" (274: the model gave a letter no pixel on
the shared contour, mostly a thin ا inside a ligature), area not conserved (56) and
empty pieces (45). Uncovered letter pairs (لك, عل, لح, كل, فل…) are cut by transfer
from covered ones; a hand-labelled sample of those pairs is the next data to add.

### Full run with the fine-tuned model (2026-09-05, evening)

`model_ft.pt` = the conditioned model after three epochs, fine-tuned one epoch with
Abdullah's 43 drawn words at 10× weight; continuity unconditional (a letter keeps the
region that continues into the next letter; the rest goes to the neighbour it touches).
Build under `QSVG_LETTERS_TAG=model` (`.cache/letters/cuts-model`, `.cache/letters-svg-model`).

| | rules (night) | learned (final) |
|---|---|---|
| multi-letter runs | 90,244 | 90,244 |
| runs left unsplit | 10,165 (11.3%) | 699 (0.8%) |
| letters emitted | 285,741 | 320,870 |
| gate: count | 0 | 0 |
| gate: ink (pieces reproduce their contour, no overlap, on 12 px/u rasters) | 0 | 9 pages, chord slivers of 40–60 px |
| gate: pixels (1400 px raster vs the word build) | 35 pages | 13 pages, one or two edge pixels each |
| per-letter mark mismatches (prior) | 3,835 | 3,726 |
| joint error vs the tajweed hand cuts, held-out median | 1.06u | 0.50u (76% within 1u) |

The remaining 699 unsplit runs are runs whose pieces do not reproduce the contour
(the boolean library's refit) or whose letter got no pixel at all. The exact Bézier
splitter (no boolean ops) is still the right fix for the first family.

### Second fine-tune, measured and NOT adopted (2026-09-05 night)

`model_ft2.pt` = `model_ft.pt` fine-tuned one more epoch (lr 5e-4, quick set) with the
87 drawn words then on file at 10×. Held-out pages (≡ 0 mod 10):

| measure | model_ft | model_ft2 |
|---|---|---|
| exact-pixel accuracy, tajweed labels | 0.924 | 0.924 |
| joint error vs tajweed cuts, median / within 1u | 0.50u / 76% | 0.51u / 76.4% |
| agreement with the drawn labels on never-trained pages (8 words) | 0.816 | 0.854 |
| hard cut failures, pages 1–60, same alignment code | 142 | 182 |
| full run: runs left unsplit | 699 | 1,409 |

The tajweed yardstick cannot see the pairs the drawings cover, so it stays flat; the
drawn-pair agreement moves the right way on a tiny sample; but the gate says the model
now leaves twice as many runs uncut, mostly "letter without ink" (624 vs 274) and
"empty piece" (273 vs 45). A/B with `QSVG_LETTERS_REBAL=0` shows the run re-keying is
neutral (143 vs 142), so the regression is the checkpoint. `model_ft` stays the build.
Next try: the same data at lr 1e-4 (`model_ft3.pt`), and an eval that scores the model
on drawn words from held-out pages as the drawings grow.

