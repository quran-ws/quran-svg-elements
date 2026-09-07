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
| full run: runs left unsplit (`data-unsplit` in the emitted SVG) | **647** | ≈950 |

(`audit_letters.py`'s `unsplit` total is a different figure: it ADDS the ~460 whole words
that got no letter group at all — unregistered or text-mismatched words — to the
run-level count, giving 1,106 for `model_ft` and 1,409 for `model_ft2`. The table
quotes the run-level count, which is what the earlier 699 was.)

The tajweed yardstick cannot see the pairs the drawings cover, so it stays flat; the
drawn-pair agreement moves the right way on a tiny sample; but the gate says the model
leaves ~300 more runs uncut, mostly "letter without ink" (624 vs 274) and "empty piece"
(273 vs 45). A/B with `QSVG_LETTERS_REBAL=0` shows the run re-keying is neutral at the
cut builder (143 vs 142 hard failures) and at the emitter (57 vs 56 unsplit on pages
1–60); the regression is the checkpoint. `model_ft` stays the build; with the re-keying
its run-level unsplit went 699 → 647 (ink 9 pages, pixels 13, letters 320,883 — the
rest of the table above unchanged). Next try: the same data at lr 1e-4
(`model_ft3.pt`), and an eval that scores the model on drawn words from held-out pages
as the drawings grow.

### Third and fourth fine-tunes; `model_ft4` adopted (2026-09-06, 02:00)

Same 99 drawn words at 10×, from `model_ft`. `model_ft3` = a full quick epoch at lr 1e-4;
`model_ft4` = `--frac 0.12` (every drawn run plus a random 12% of the tajweed-labelled
runs, ~4,000 samples, nine minutes) at lr 1e-4. The base model `model_cond_e3` is shown
for scale.

| measure | e3 | ft | ft2 | ft3 | **ft4** |
|---|---|---|---|---|---|
| held-out exact-pixel, tajweed labels | — | 0.924 | 0.924 | 0.927 | 0.924 |
| held-out joint error median / within 1u | — | 0.50u / 76% | 0.51u / 76.4% | 0.50u / 76.4% | 0.50u / 76.6% |
| agreement with drawn labels, never-trained pages (8 words) | — | 0.816 | 0.854 | 0.880 | **0.921** |
| hard cut failures, pages 1–60 | 163 | 142 | 182 | 171 | 144 |

The runs the long fine-tunes broke are touching pairs no tajweed layer ever labels
(ون, نى at word end: the model starved the و to under 1% of the run). Nothing in
training constrains them — their masks allow both letters everywhere, zero gradient —
so a full epoch on the labelled subset drifts there while a short dose does not.

Full run with `model_ft4` under `QSVG_LETTERS_TAG=model`:

| | model_ft (restored, with the re-keying) | model_ft4 |
|---|---|---|
| runs left unsplit (`data-unsplit`) | 647 | 655 |
| letters emitted | 320,883 | 321,017 |
| gate: count | 0 | 0 |
| gate: ink | 9 pages | 9 pages |
| gate: pixels (largest alpha change > 72/255) | 13 pages | 17 pages (max 77–142, the boolean-refit sliver class; 10 pages shared, p100/p592 cleared, six new) |
| per-letter mark mismatches (prior) | 3,727 | 3,722 |

Adopted for the pairs the drawings cover — that is what the drawings are for — at the
cost of four more pages in the seam class the Bézier splitter is meant to retire, and
eight more unsplit runs. `model_ft` is kept on disk; rebuild with `--model
.cache/letters/model_ft.pt` to revert. Next data: batch 3 (هم, لم, كم, ها, به, كل …), then
re-measure the same five numbers; the drawn-word held-out set (pages ≡ 0 mod 10) is
only 8 words and should grow with it.

### The misfiled tail, fixed generally (2026-09-06)

Abdullah drew تُكَذِّبَانِ on p531 and the preview said five letters, three pieces. The
drawing was right: the group is texted تكذبا but its ink holds only تكذ, with با filed
in the ن group — the same defect as ٱلْحَرَامِ, where the ا sits in the م group. Over 61
sample pages 191 groups draw FEWER contours than their text needs and 360 draw more.

`align_runs` now moves a misfiled tail back on either of two proofs, and both need the
target's rightmost contour to stand clear of the rest of its ink:

* **the counts square** — the source is short of `_expected` (one contour, plus one per
  letter that never joins the letter after it), the group after it is over its own
  `_expected`, and moving the letters after the source's last break makes both counts
  exactly right. Letters that merely touch can only lower a count, never raise one, so
  the source being short is never proof on its own;
* **the moved letter is a lone ا or و** of the measured size (ا 123–169 px at 4 px/u,
  h/w 5.4; و 262–299 px at 1.09; a bare ء 154–179 px at 1.15 — the bands do not touch),
  which catches the cases where the moved ink touches its new neighbour so no count can
  square.

45 words on the 61 sample pages, ~450 mushaf-wide; every one rendered with its groups
coloured and checked by eye. Beyond تكذبا and لحرا it re-keys ٱلسَّمَآءِ, أَشْيَآءَهُمْ,
فَكَذَّبُوهُمَا, عِبَادِنَا, هَٰٓؤُلَآءِ, وَرَثَةِ. `QSVG_LETTERS_REBAL=0` turns it off for A/B.

Full rebuild after the fix (labels, cuts, emit, audit; model_ft4):

| | before | after |
|---|---|---|
| runs left unsplit (`data-unsplit`) | 655 | **634** |
| letters emitted | 321,017 | 321,116 |
| gate: count / ink / pixels | 0 / 9 / 17 | 0 / 9 / 17 |
| per-letter mark mismatches (prior) | 3,722 | 3,722 |
| drawn words the label builder accepts | 99 of 102 | **102 of 102** |

### The drawing page shows the split (2026-09-06)

`build_letters_label_page.py` now carries the run's own path data into the page and
re-implements `drawn_cut_labels` + `order_pieces` in the browser (4 px per unit, lines
3 px wide extended 1u, components of ink minus lines, a contour no line touches counts
as a letter only after one that never joins left, pieces ordered along the chain the
lines make). Under each word the pieces appear one letter at a time, in reading order,
with a green line when the count matches the text and a red one naming what is missing.
The port was checked against the Python masks on 16 accepted words — same piece count,
same letter order, matching pixel shares — and it reproduces the same rejection on the
words that were a line short. A word can no longer be sent in short.

### Two new audit rows: shape and size (2026-09-06)

Abdullah photographed a cut that wandered instead of crossing the stroke, with a
speck of one letter stranded inside the other, and asked for both an audit and a fix.

**shape** — inside one source contour, a letter's ink must be one piece, and a cut
between two letters must be a straight line across the stroke. Measured over 7,990
boundaries in the shipped build: a cut sits 0.09u from a straight line at the median,
0.23u at p90, 0.71u at p99, so `SHAPE_DEV = 0.85u` is past the tail. A boundary longer
than 2.5 stroke widths is a shared flank, not a cut, and is not judged. An island is a
disconnected piece of a letter under 15% of its ink and at least 40 px at 12 px/u —
below that it is the boolean library's refit sliver, which the ink row already covers.
Mushaf-wide: **997 flags, 809 islands and 188 ragged cuts.**

**size** — a letter far from the area that letter takes elsewhere in the same position
in its run. `--size-table` writes the medians (137 letter/position combinations) to
`.cache/letters/letter_sizes.json`. Over 31,000 letters the ratio to the median is
within 0.9–1.1 for half of them, below 0.34x for 1.5% and above 3x for 0.45%; that
tail is where the defects are (a letter reduced to a sliver at 0.01x, one that
swallowed its neighbour at 10x). Mushaf-wide: **6,103 flags, 4,834 too small and 1,269
too large**, of which 1,716 are past 6x or under 0.1x.

Both are priors, not proof rows: they rank work, they do not block a build.

**The geometric fix was measured and rejected.** Forcing the chord's half-plane on the
ink around each cut — the obvious way to make a boundary straight — breaks more letters
into islands than it straightens, at every band width tried (pages 41, 81, 141: shape 8
with it off, 25 at 0.5u, 23 at 1u, 39 at 2u), because a chord's line also slices the
parts of a letter that curve back past the cut. Moving small islands to the letter that
surrounds them changes nothing at all: the islands are not in the model's pixel
ownership, they are made later by the boolean piece construction. So the two fixes that
remain are the exact Bézier splitter, which retires that library, and more drawn
examples where the model's boundary is wrong.

### The mirror: a leading letter filed in the group before it (2026-09-06)

The same defect runs both ways. In وَٱلْمَوْقُوذَةُ the group texted المو draws one contour,
لمو, and the ا stands in the group before it, the one texted و, which holds two
contours: a waw of 270 px and a thin stroke of 164 px at 5.6 times its width. The two
overlap in x, which is why the word build filed them together — and why the `clear`
test the forward rule uses cannot apply here. The measured size bands do the work
instead. `_rebalance_back` moves the leading letter back when its own group is short
of `_expected`, the group before it is over its own, the extra contour has the size and
shape of an ا or a و, and the move squares both counts.

65 words on the 61 sample pages (~650 mushaf-wide), almost all the وَٱل and وَأَ openings;
every one rendered with its groups coloured and checked by eye. Hard cut failures on
pages 1–60 fall from 143 to 137.

Full rebuild with both rules (labels, cuts, emit, audit; model_ft4):

| | before | after |
|---|---|---|
| runs left unsplit (`data-unsplit`) | 634 | **592** |
| letters emitted | 321,116 | 321,239 |
| gate: count / ink / pixels | 0 / 9 / 17 | 0 / 9 / 17 |
| shape (islands + ragged cuts) | 997 | 985 |
| size (letters off their usual area) | 6,103 | 5,920 |
| drawn words accepted | 118 of 120 | **121 of 121** |

### `model_ft5` adopted (2026-09-06, 13:20)

`model_ft4` fine-tuned once more with `--frac 0.12 --lr 1e-4` on all 121 drawn words.
Measured the four ways before adopting:

| measure | ft4 | **ft5** |
|---|---|---|
| held-out exact-pixel, tajweed labels | 0.924 | 0.926 |
| held-out joint error median / within 1u | 0.50u / 76.6% | 0.50u / 76.9% |
| agreement with the drawn labels on never-trained pages (10 words) | 0.895 | **0.917** |
| hard cut failures, pages 1–60 | 137 | **129** |

Better or equal on all four, so it is the build. Full run:

| | ft4 build | **ft5 build** |
|---|---|---|
| runs left unsplit (`data-unsplit`) | 592 | **534** |
| letters emitted | 321,239 | 321,403 |
| gate: count / ink / pixels | 0 / 9 / 17 | 0 / **6** / 18 |
| shape (islands + ragged cuts) | 985 | **915** |
| size (letters off their usual area) | 5,920 | **5,764** |

The drawn-word agreement has gone 0.816 → 0.921 → 0.917 → 0.917 over the fine-tunes
while the tajweed yardstick barely moves, which is the point: the drawings cover the
pairs the tajweed layers never colour.

### The drawn set outgrew its weight (2026-09-06 evening)

Abdullah drew 45 more words, taking the set to 166 and covering ها and به for the first
time. Two fine-tunes from `model_ft5` were measured and **both rejected**:

| measure | ft5 (kept) | ft6 (10x, frac 0.12) | ft7 (4x, frac 0.30) |
|---|---|---|---|
| held-out exact-pixel | 0.926 | 0.924 | **0.928** |
| joint error median / within 1u | 0.50u / 76.9% | 0.50u / 76.3% | 0.51u / 76.1% |
| agreement with the drawn labels, held-out pages (15 words) | **0.901** | 0.897 | 0.893 |
| hard cut failures, pages 1–60 | **129** | 174 | 135 |
| of those, "letter without ink" | **12** | 51 | 20 |

The first failure has a clear cause: a drawn word carries 10x the loss of an ordinary
sample, which was 1% of the signal at 40 words and is **31%** at 166 with the short
epoch. The model stopped learning the mushaf and started memorising the drawings.
Re-weighting to 4x over a 30% epoch (8% of the signal) recovered the tajweed metric —
0.928 is the best held-out pixel accuracy so far — but did not recover the gate, and the
drawn agreement fell again.

So the recipe has to scale with the set: **share of loss, not a fixed multiplier**. And
something in the new batch is not helping the way the earlier ones did. The obvious
suspect is run length: 63 of the 166 drawn words are two-letter runs (ها, به, كم…),
against a mushaf where most runs are longer, and the model is conditioned on the letter
count. The next attempt should balance the drawn sample by run length before weighting
it, and hold the two-letter runs out to see whether they are what moves the gate.

